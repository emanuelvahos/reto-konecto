try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import json
import re
import time
import unicodedata
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool

from app.database import get_db_cursor, sanitize_rows
from app import recommend as rec
from app.i18n import alert_severity, render_alert_message

# ContextVars por turno. LangChain ejecuta tools síncronas en una copia del contexto: un ``.set()``
# dentro de la tool se perdería. Se enlaza un contenedor MUTABLE nuevo en reset_turn_telemetry() (contexto
# padre) y las tools SOLO lo mutan en sitio (.append / [k] = v).
current_turn_tool_traces: ContextVar[List[Dict[str, Any]]] = ContextVar(
    "current_turn_tool_traces", default=[]
)
# id de actuador -> id (conserva el orden de aparición); las filas de la UI se leen de la DB al final del turno
current_turn_actuators: ContextVar[Dict[Any, Any]] = ContextVar(
    "current_turn_actuators", default={}
)
# alertas internas {code, params}; se localizan (es/en) al construir el ui_payload
current_turn_alerts: ContextVar[List[Dict[str, Any]]] = ContextVar(
    "current_turn_alerts", default=[]
)
# Recomendación estructurada del turno ({status, hard, relaxed, items}); se localiza al armar el ui_payload
current_turn_recommendation: ContextVar[Dict[str, Any]] = ContextVar("current_turn_recommendation", default={})
# Aclaración pedida en el turno ({topic, options, args}); vacío si no hubo
current_turn_clarification: ContextVar[Dict[str, Any]] = ContextVar("current_turn_clarification", default={})
# Argumentos de una aclaración del turno anterior (solo lectura): la respuesta del usuario se resuelve en el mismo contexto
current_pending_args: ContextVar[Dict[str, Any]] = ContextVar("current_pending_args", default={})
# Mensajes del usuario de la sesión (solo lectura): se descartan argumentos de recommend que el usuario nunca dijo
current_user_text: ContextVar[str] = ContextVar("current_user_text", default="")

# Claves de números de parte fundamentados en el turno (activos de la sesión + devueltos por herramientas): el LLM no puede consultar
# un número de parte que el usuario nunca mencionó (p. ej. "uno de ejemplo")
current_grounded_pns: ContextVar[set] = ContextVar("current_grounded_pns", default=set())

# Grupos de campos que el LLM puede necesitar según la intención de la pregunta
FOCUS_GROUPS: Dict[str, List[str]] = {
    "torque": ["on_off_torque_nm", "on_off_torque_in_lbs", "modulating_torque_nm", "modulating_torque_in_lbs"],
    "duty": ["on_off_duty_cycle_pct", "cycles_per_hour", "modulating_duty_cycle_pct", "starts_per_hour"],
    "speed": ["speed_60hz_sec", "speed_50hz_sec", "speed_dc_or_fixed_sec"],
    "current": ["fla_60hz_amps", "fla_50hz_amps", "fla_dc_or_fixed_amps",
                "lra_60hz_amps", "lra_50hz_amps", "lra_dc_or_fixed_amps"],
    "power": ["motor_power_watts"],
}

# Columnas que consume la tarjeta móvil (ActuatorDto); se leen de la DB, nunca de la salida del LLM
UI_COLUMNS = [
    "id", "base_part_number", "size_code", "frame_size", "enclosure_type", "power_supply", "voltage_num",
    "phase_type", "service_support", "is_available",
    *FOCUS_GROUPS["torque"], *FOCUS_GROUPS["duty"], *FOCUS_GROUPS["speed"], *FOCUS_GROUPS["current"],
    "motor_power_watts", "csa_certified", "ce_ukca_certified", "hazardous_classification",
    "source_page", "source_method",
]


def reset_turn_telemetry() -> None:
    current_turn_tool_traces.set([])
    current_turn_actuators.set({})
    current_turn_alerts.set([])
    current_turn_recommendation.set({})
    current_turn_clarification.set({})
    current_pending_args.set({})
    current_user_text.set("")
    current_grounded_pns.set(set())


def record_tool_trace(
    tool_name: str,
    arguments: Dict[str, Any],
    sql_executed: str,
    raw_output: Any,
    elapsed_ms: float,
) -> None:
    current_turn_tool_traces.get().append(
        {
            "tool_name": tool_name,
            "arguments": arguments,
            "sql_executed": sql_executed.strip(),
            "raw_output": raw_output,
            "execution_time_ms": round(elapsed_ms, 2),
        }
    )


def register_ui_actuators(rows: List[Dict[str, Any]]) -> None:
    store = current_turn_actuators.get()
    for r in rows:
        if "id" in r:
            store[r["id"]] = r["id"]
        if r.get("base_part_number"):
            current_grounded_pns.get().add(re.sub(r"[^A-Z0-9]", "", str(r["base_part_number"]).upper()))


def record_alert(code: str, **params: Any) -> Dict[str, str]:
    """Registra la alerta en el contenedor del turno (mutación en sitio) y devuelve su forma para el LLM (en)."""
    alerts = current_turn_alerts.get()
    entry = {"code": code, "params": params}
    if entry not in alerts:
        alerts.append(entry)
    return {"code": code, "message": render_alert_message(code, params, "en")}


def order_by_mention(rows: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
    """Reordena las filas según el orden en que el usuario nombró los modelos en `text` (número de parte completo o código de
    tamaño). Las filas no nombradas conservan su orden y van al final. Las tools pueden correr en paralelo, así que el orden
    de llegada no es fiable."""
    key = re.sub(r"[^A-Z0-9]", "", (text or "").upper())
    if not key or len(rows) < 2:
        return list(rows)

    def pos(r: Dict[str, Any]) -> int:
        pn = re.sub(r"[^A-Z0-9]", "", str(r.get("base_part_number", "")).upper())
        for cand in (pn, pn[:-1] if pn.endswith("A") else pn, str(r.get("size_code") or "").upper()):
            i = key.find(cand) if cand else -1
            if i >= 0:
                return i
        return 10**9

    return sorted(rows, key=pos)    # sorted es estable


def fetch_ui_actuators(ids: List[Any]) -> List[Dict[str, Any]]:
    """Filas de la tarjeta móvil leídas de PostgreSQL, en el orden en que las tools las devolvieron."""
    if not ids:
        return []
    with get_db_cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(UI_COLUMNS)} FROM actuators WHERE id = ANY(%s) "
            "ORDER BY array_position(%s::int[], id);",
            (list(ids), list(ids)),
        )
        return sanitize_rows(cur.fetchall())


# =====================================================================
# SALIDA COMPACTA PARA EL LLM
# =====================================================================
def is_single_torque(row: Dict[str, Any]) -> bool:
    """Trifásico: la hoja solo da un 'Output Torque' (guardado como on/off; modulante NULL)."""
    return (
        row.get("phase_type") == "3 Phase"
        and row.get("modulating_torque_nm") is None
        and row.get("on_off_torque_nm") is not None
    )


def _num(v: Any) -> Any:
    return int(v) if isinstance(v, float) and v.is_integer() else v


def compact_row(row: Dict[str, Any], focus: Optional[List[str]] = None) -> Dict[str, Any]:
    # la potencia del motor es un solo dato y "consume/draw" se confunde con corriente: siempre se incluye
    groups = [g for g in (focus or list(FOCUS_GROUPS)) if g in FOCUS_GROUPS]
    if "power" not in groups:
        groups.append("power")
    out: Dict[str, Any] = {
        "base_part_number": row["base_part_number"],
        "power_supply": row["power_supply"],
        "enclosure_type": row["enclosure_type"],
    }
    if not row.get("is_available", True):
        out["available"] = False
    if not row.get("csa_certified", True):
        out["csa_certified"] = False
    single = is_single_torque(row)
    for g in groups:
        for col in FOCUS_GROUPS[g]:
            v = row.get(col)
            if v is None:
                continue
            if single and col in ("on_off_torque_nm", "on_off_torque_in_lbs"):
                # nunca se presenta como torque on/off ni modulante
                col = col.replace("on_off_torque", "single_torque")
            # enteros solo para torque/velocidad (ahorra tokens); las corrientes conservan su precisión (3.0 A)
            out[col] = _num(v) if g in ("torque", "speed") else v
    if single and "torque" in groups:
        out["alert"] = "SINGLE_TORQUE_RATING"
    return out


def _compact_rows(rows: List[Dict[str, Any]], focus: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    return [compact_row(r, focus) for r in rows]


def _single_torque_alerts(rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    if any(is_single_torque(r) for r in rows):
        return [record_alert("SINGLE_TORQUE_RATING")]
    return []


# =====================================================================
# TOOL 1: BÚSQUEDA EXACTA Y DIFUSA POR BASE PART NUMBER
# =====================================================================
class LookupPartNumberInput(BaseModel):
    part_number: str = Field(
        ...,
        description="Base Part Number of the Series 76 actuator (e.g. '761A00-11300000/A'; 3-phase ends in '11330C00/A'), or a partial/typo code.",
    )
    focus: Optional[List[str]] = Field(
        None,
        description="Only the field groups the user asked about: torque, duty, speed, current, power. Omit for all.",
    )
    frequency_hz: Optional[int] = Field(None, description="50 or 60 only if the user asks for values at a specific frequency.")


@tool("lookup_actuator_by_part_number", args_schema=LookupPartNumberInput)
def lookup_actuator_by_part_number(part_number: str, focus: Optional[List[str]] = None, frequency_hz: Optional[int] = None) -> Dict[str, Any]:
    """
    Looks up Series 76 actuator specs by Base Part Number. Handles exact matches, missing '/A',
    N/A models in 220V 3-Phase, and typos (pg_trgm fuzzy match).
    """
    t0 = time.perf_counter()
    args = {"part_number": part_number, **({"focus": focus} if focus else {}),
            **({"frequency_hz": frequency_hz} if frequency_hz else {})}
    part_number = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", part_number)[:120]  # sin NUL/controles; la base rechaza NUL
    clean_input = part_number.strip().upper()
    user_text = current_user_text.get()
    if user_text:                                   # en el pipeline (no en llamadas directas): solo números de parte que el usuario dio
        k = re.sub(r"[^A-Z0-9]", "", part_number.upper())
        text_key = re.sub(r"[^A-Z0-9]", "", user_text.upper())
        grounded = current_grounded_pns.get()
        if not (k in text_key or (k.endswith("A") and k[:-1] in text_key) or any(k == g or k in g or g in k for g in grounded)):
            result = {"status": "UNGROUNDED_PART_NUMBER", "queried_part_number": part_number,
                      "instruction": "The user never mentioned this part number. Do not look up or invent part numbers; answer only about what the user asked."}
            record_tool_trace("lookup_actuator_by_part_number", args, "", result, (time.perf_counter() - t0) * 1000)
            return result
    norm_input = re.sub(r"[^A-Z0-9]", "", clean_input)
    # Si el usuario omitió el '/A' al final, también probamos agregando 'A' al normalizado
    norm_with_a = norm_input if norm_input.endswith("A") else norm_input + "A"

    # Solo se busca por tamaño si el input es un código de tamaño puro (ej. "761A")
    size_param = clean_input if re.fullmatch(r"76[1-7][A-Z]", clean_input) else None

    sql_exact = """
        SELECT * FROM actuators
        WHERE UPPER(base_part_number) = %s
           OR normalized_part_number IN (%s, %s)
           OR size_code = %s
        ORDER BY is_available DESC, voltage_num ASC;
    """
    sql_fuzzy = ""
    with get_db_cursor() as cur:
        cur.execute(sql_exact, (clean_input, norm_input, norm_with_a, size_param))
        exact_rows = sanitize_rows(cur.fetchall())

        if exact_rows:
            available_rows = [r for r in exact_rows if r["is_available"]]
            na_rows = [r for r in exact_rows if not r["is_available"]]

            # Modelo listado como N/A (ej. 761A00-11330C00/A en 220V 3-Phase): se devuelven alternativas del mismo tamaño
            if not available_rows and na_rows:
                target_size = na_rows[0]["size_code"]
                cur.execute(
                    "SELECT * FROM actuators WHERE size_code = %s AND is_available = TRUE ORDER BY voltage_num ASC;",
                    (target_size,),
                )
                alternatives = sanitize_rows(cur.fetchall())
                register_ui_actuators(alternatives)
                alerts = [
                    record_alert(
                        "MODEL_LISTED_AS_NA",
                        pn=na_rows[0]["base_part_number"],
                        supply=na_rows[0]["power_supply"],
                        size=target_size,
                    )
                ] + _single_torque_alerts(alternatives)
                result: Dict[str, Any] = {
                    "status": "MODEL_LISTED_AS_NA",
                    "queried_part_number": part_number,
                    "na_part_number": na_rows[0]["base_part_number"],
                    "na_power_supply": na_rows[0]["power_supply"],
                    "available_alternatives_same_size": _compact_rows(alternatives, focus),
                    "alerts": alerts,
                }
                record_tool_trace("lookup_actuator_by_part_number", args, sql_exact, result,
                                  (time.perf_counter() - t0) * 1000)
                return result

            register_ui_actuators(available_rows)
            result = {
                "status": "EXACT_MATCH",
                "count": len(exact_rows),
                "actuators": _compact_rows(exact_rows, focus),
            }
            alerts = _single_torque_alerts(exact_rows)
            if frequency_hz and any(r["voltage_num"] == 24 for r in exact_rows):
                alerts.append(record_alert("DC_NO_FREQUENCY"))
            if alerts:
                result["alerts"] = alerts
            record_tool_trace("lookup_actuator_by_part_number", args, sql_exact, result,
                              (time.perf_counter() - t0) * 1000)
            return result

        # Sin coincidencia exacta -> búsqueda difusa con pg_trgm
        sql_fuzzy = """
            SELECT *, similarity(base_part_number, %s) AS sim_score
            FROM actuators
            WHERE similarity(base_part_number, %s) > 0.42
            ORDER BY sim_score DESC, is_available DESC
            LIMIT 20;
        """
        cur.execute(sql_fuzzy, (clean_input, clean_input))
        fuzzy_rows = _plausible_typo_rows(clean_input, sanitize_rows(cur.fetchall()))[:4]

    if fuzzy_rows:
        register_ui_actuators([r for r in fuzzy_rows if r["is_available"]])
        alerts = [record_alert("TYPO_OR_CLOSEST_MATCH_FOUND", query=part_number)] + _single_torque_alerts(fuzzy_rows)
        result = {
            "status": "TYPO_OR_CLOSEST_MATCH_FOUND",
            "queried_part_number": part_number,
            "suggested_actuators": _compact_rows(fuzzy_rows, focus),
            "alerts": alerts,
        }
    else:
        result = {
            "status": "INVALID_PART_NUMBER",
            "queried_part_number": part_number,
            "alerts": [record_alert("INVALID_PART_NUMBER", query=part_number)],
        }
    record_tool_trace("lookup_actuator_by_part_number", args, sql_fuzzy, result,
                      (time.perf_counter() - t0) * 1000)
    return result


# Confusiones ópticas/tipográficas típicas del PDF (Trampa 5): solo estas sustituciones, o un carácter de más/menos, cuentan como typo.
_OCR_PAIRS = {frozenset(p) for p in ("B8", "0O", "0C", "O0", "1I", "1L", "5S", "2Z", "6G", "OC")}


def _typo_distance(query: str, cand: str) -> Optional[int]:
    """Distancia entre un número de parte consultado y uno del catálogo si es un typo plausible, o None si no lo es.
    Plausible = los 3 primeros caracteres (serie y tamaño) iguales, y a lo sumo UN carácter de más/menos o UNA sustitución no óptica
    (más las confusiones ópticas B/8, 0/O, 0/C...). Un dígito de tamaño distinto (768A00 vs 767A00) NO es un typo: es otro modelo."""
    q = re.sub(r"[^A-Z0-9]", "", query.upper())
    c = re.sub(r"[^A-Z0-9]", "", cand.upper())
    if q == c:
        return 0
    if abs(len(q) - len(c)) > 1:
        return None
    if q[:3] != c[:3]:                         # serie/tamaño distintos: es otro modelo, no un typo
        return None
    if len(q) == len(c):
        diffs = [(x, y) for x, y in zip(q, c) if x != y]
        non_ocr = [d for d in diffs if frozenset(d) not in _OCR_PAIRS]
        return len(diffs) if len(non_ocr) <= 1 and len(diffs) <= 3 else None
    short, long_ = (q, c) if len(q) < len(c) else (c, q)
    for i in range(len(long_)):
        if long_[:i] + long_[i + 1:] == short:
            return 1
    return None


def _plausible_typo_rows(query: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored = [(d, i, r) for i, r in enumerate(rows) for d in [_typo_distance(query, r["base_part_number"])] if d is not None]
    return [r for _, _, r in sorted(scored, key=lambda x: (x[0], x[1]))]



# =====================================================================
# TOOL 2: RECOMENDACIÓN CON RESTRICCIONES DURAS Y BLANDAS (lógica y fórmula del score en app/recommend.py)
# =====================================================================
class RecommendActuatorsInput(BaseModel):
    min_torque_nm: Optional[float] = Field(None, description="Minimum required output torque in Nm.")
    min_torque_in_lbs: Optional[float] = Field(None, description="Minimum required output torque in in-lbs.")
    application_type: Optional[str] = Field(
        None,
        description="'On/Off' or 'Modulating'. Leave empty if the user did not say; the tool then asks the user.",
    )
    enclosure_type: Optional[str] = Field(None, description="'Weatherproof' or 'Explosionproof', only if the user requires it (hard constraint).")
    hazardous_area: Optional[bool] = Field(None, description="True if the user says the area is hazardous/explosive (hard: Explosionproof only); False if non-hazardous.")
    voltage_num: Optional[int] = Field(None, description="Supply voltage: 24, 110, or 220 (hard constraint).")
    phase_type: Optional[str] = Field(None, description="'Single Phase', '3 Phase', 'AC/DC', or 'DC' (hard constraint).")
    frequency_hz: Optional[int] = Field(None, description="50 or 60 (Hz) when checking speed or current.")
    max_speed_sec: Optional[float] = Field(None, description="Maximum seconds for a 90-degree turn.")
    max_fla_amps: Optional[float] = Field(None, description="Maximum Full Load Current (FLA) in Amps.")
    min_duty_cycle_pct: Optional[int] = Field(None, description="Minimum duty cycle (S4%).")
    require_csa_certification: Optional[bool] = Field(None, description="True only if the user requires CSA certification.")
    safety_factor: Optional[float] = Field(None, description="Multiplier > 1 applied to the requested torque ONLY if the user explicitly asks for a safety/service factor (e.g. 1.5, or 25% -> 1.25). The datasheet defines none: never invent one.")


def _torque_ceiling(cur, where: str, params: List[Any]) -> Optional[float]:
    cur.execute(
        "SELECT MAX(GREATEST(COALESCE(on_off_torque_nm, 0), COALESCE(modulating_torque_nm, 0))) AS m "
        f"FROM actuators WHERE is_available = TRUE AND {where};",
        tuple(params),
    )
    m = cur.fetchone()["m"]
    return float(m) if m is not None else None


RECOMMEND_SQL = (
    "SELECT * FROM actuators WHERE is_available = TRUE;  -- restricciones duras, filtros blandos y score: app.recommend"
)


def _clarification_result(gate: Dict[str, Any], merged: Dict[str, Any], ignored: List[str]) -> Dict[str, Any]:
    pending = current_turn_clarification.get()
    pending.clear()
    pending.update({"topic": gate["topic"], "options": gate["options"], "args": merged})
    return {
        "status": "NEEDS_CLARIFICATION",
        "missing": gate["topic"],
        **({"ignored_arguments": ignored} if ignored else {}),
        "instruction": "The app now asks the user this question with buttons. Do not recommend or state any figure; reply with one short neutral sentence.",
    }


def _relaxation_diagnostics(cur, a: Dict[str, Any], want_nm: Optional[float]) -> List[Dict[str, Any]]:
    diag: List[Dict[str, Any]] = []
    if want_nm is not None:
        checks = []
        if a.get("require_csa_certification"):
            checks.append(("csa", "", "csa_certified = TRUE", []))
        if a.get("voltage_num") is not None:
            checks.append(("voltage", a["voltage_num"], "voltage_num = %s", [a["voltage_num"]]))
        if a.get("enclosure_type") or a.get("hazardous_area"):
            enc = "Explosionproof" if a.get("hazardous_area") else a["enclosure_type"]
            checks.append(("enclosure", enc, "LOWER(enclosure_type) = LOWER(%s)", [enc]))
        if a.get("phase_type"):
            checks.append(("phase", a["phase_type"], "LOWER(phase_type) = LOWER(%s)", [a["phase_type"]]))
        for kind, value, where, p in checks:
            ceiling = _torque_ceiling(cur, where, p)
            if ceiling is not None and want_nm > ceiling:
                diag.append({"code": "TORQUE_ABOVE_CEILING", "params": {
                    "filter_kind": kind, "filter_value": value, "ceiling": _num(ceiling), "requested": _num(want_nm)}})
        catalog_max = _torque_ceiling(cur, "TRUE", [])
        if catalog_max is not None and want_nm > catalog_max:
            diag.append({"code": "CATALOG_TORQUE_CEILING", "params": {"ceiling": _num(catalog_max)}})
        if a.get("require_csa_certification"):
            cur.execute("SELECT MIN(frame_size) AS f FROM actuators WHERE is_available AND NOT csa_certified;")
            f = cur.fetchone()["f"]
            if f is not None:
                diag.append({"code": "CSA_SIZE_LIMIT", "params": {"frame_size": f}})
    if not diag:
        diag.append({"code": "CONSTRAINT_RELAXED", "params": {}})
    return diag


def _hard_failure_alert(rows: List[Dict[str, Any]], a: Dict[str, Any]) -> Dict[str, Any]:
    if a.get("hazardous_area") and a.get("enclosure_type") == "Weatherproof":
        return {"code": "HAZARDOUS_NEEDS_EXPLOSIONPROOF", "params": {}}
    if a.get("voltage_num") is not None and (a.get("enclosure_type") or a.get("hazardous_area")):
        enc = "Explosionproof" if a.get("hazardous_area") else a["enclosure_type"]
        offered = sorted({r["enclosure_type"] for r in rows if r["voltage_num"] == a["voltage_num"]})
        if offered and enc not in offered:
            return {"code": "VOLTAGE_ENCLOSURE_UNAVAILABLE",
                    "params": {"voltage": a["voltage_num"], "enclosure": enc, "available": " / ".join(offered)}}
    return {"code": "HARD_CONSTRAINTS_UNSATISFIABLE", "params": {}}


@tool("recommend_actuators", args_schema=RecommendActuatorsInput)
def recommend_actuators(
    min_torque_nm: Optional[float] = None,
    min_torque_in_lbs: Optional[float] = None,
    application_type: Optional[str] = None,
    enclosure_type: Optional[str] = None,
    hazardous_area: Optional[bool] = None,
    voltage_num: Optional[int] = None,
    phase_type: Optional[str] = None,
    frequency_hz: Optional[int] = None,
    max_speed_sec: Optional[float] = None,
    max_fla_amps: Optional[float] = None,
    min_duty_cycle_pct: Optional[int] = None,
    require_csa_certification: Optional[bool] = None,
    safety_factor: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Recommends Series 76 actuators. Hard constraints (voltage, enclosure, phase, hazardous area => Explosionproof)
    filter; soft ones (torque, duty, speed, FLA, CSA) score the candidates (formula in app/recommend.py).
    If a decisive datum is missing (voltage, On/Off vs Modulating, hazardous area) it returns NEEDS_CLARIFICATION.
    """
    t0 = time.perf_counter()
    given = {k: v for k, v in locals().items() if k != "t0" and v is not None}
    given, ignored = rec.ground_args(given, current_user_text.get())
    # Respuesta a una aclaración previa: los argumentos pendientes se completan con lo que ahora envía el modelo
    merged = {**current_pending_args.get(), **given}
    a = rec.clean_args(merged)
    args_dict = dict(a)

    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM actuators WHERE is_available = TRUE;")
        rows = sanitize_rows(cur.fetchall())

        asked_nm = a.get("min_torque_nm")
        if asked_nm is None and a.get("min_torque_in_lbs") is not None:
            cur.execute("SELECT MIN(on_off_torque_nm / NULLIF(on_off_torque_in_lbs, 0)) AS r FROM actuators "
                        "WHERE is_available AND on_off_torque_in_lbs IS NOT NULL;")
            ratio = cur.fetchone()["r"]
            asked_nm = float(ratio) * a["min_torque_in_lbs"] if ratio else None
        if asked_nm is not None:
            asked_nm *= float(a.get("safety_factor") or 1)
            ceiling = _torque_ceiling(cur, "TRUE", [])
            if ceiling is not None and asked_nm > ceiling:      # ningún modelo del catálogo llega: nada que recomendar ni preguntar
                store = current_turn_recommendation.get()
                store.clear()
                store.update({"hard": [], "relaxed": [], "items": [], "status": "NO_MATCH_HARD_CONSTRAINTS"})
                msg = record_alert("CATALOG_TORQUE_CEILING", ceiling=_num(ceiling))["message"]
                result = {"status": "NO_MATCH_HARD_CONSTRAINTS", "count": 0, "diagnostics": [msg]}
                record_tool_trace("recommend_actuators", args_dict, RECOMMEND_SQL, result, (time.perf_counter() - t0) * 1000)
                return result

        gate = rec.gate(rows, a)
        if gate:
            result = _clarification_result(gate, a, ignored)
            record_tool_trace("recommend_actuators", args_dict, RECOMMEND_SQL, result, (time.perf_counter() - t0) * 1000)
            return result

        candidates = [r for r in rows if rec.passes_hard(r, a)]
        hard = rec.hard_codes(a)
        focus = ["torque", "power"]
        if a.get("min_duty_cycle_pct") is not None:
            focus.append("duty")
        if a.get("max_speed_sec") is not None:
            focus.append("speed")
        if a.get("max_fla_amps") is not None:
            focus.append("current")

        soft = any(a.get(k) not in (None, False) for k in rec.SOFT_ARG_KEYS)
        store = current_turn_recommendation.get()
        store.clear()
        store.update({"hard": hard, "relaxed": [], "items": [], "status": "", "soft": soft, "candidates": len(candidates)})

        if not candidates:
            alert = _hard_failure_alert(rows, a)
            msg = record_alert(alert["code"], **alert["params"])["message"]
            result = {"status": "NO_MATCH_HARD_CONSTRAINTS", "count": 0, "diagnostics": [msg]}
            store["status"] = result["status"]
            record_tool_trace("recommend_actuators", args_dict, RECOMMEND_SQL, result, (time.perf_counter() - t0) * 1000)
            return result

        ranked = rec.rank(candidates, a)
        full = [x for x in ranked if x["all_met"]]
        shown = (full if full else ranked)[: rec.TOP_N]
        register_ui_actuators([x["row"] for x in shown])
        for i, item in enumerate(shown):
            r = rec.reasons(item, is_top_full_match=(i == 0 and bool(full)))
            store["items"].append({"id": item["row"]["id"], "pn": item["row"]["base_part_number"],
                                   "score": item["score"], **r})
        ranking_for_llm = []
        for item in shown:
            entry: Dict[str, Any] = {"part_number": item["row"]["base_part_number"], "score": item["score"]}
            for c in item["criteria"]:
                if c["key"] == "torque" and c["met"]:
                    entry["torque_margin_pct"] = c["margin_pct"]
            ranking_for_llm.append(entry)

        alerts: List[Dict[str, str]] = []
        if not a.get("application_type") and (a.get("min_torque_nm") is not None or a.get("min_torque_in_lbs") is not None):
            alerts.append(record_alert("AMBIGUOUS_SERVICE_TYPE"))
        if a.get("frequency_hz") and any(x["row"]["voltage_num"] == 24 for x in shown):
            alerts.append(record_alert("DC_NO_FREQUENCY"))
        alerts += _single_torque_alerts([x["row"] for x in shown])
        if a.get("safety_factor"):
            unit = "Nm" if a.get("min_torque_nm") is not None else "in-lbs"
            asked = float(a["min_torque_nm"] if unit == "Nm" else a["min_torque_in_lbs"]) if (
                a.get("min_torque_nm") is not None or a.get("min_torque_in_lbs") is not None) else None
            if asked is not None:
                alerts.append(record_alert("SAFETY_FACTOR_APPLIED", factor=a["safety_factor"], requested=asked,
                                           effective=round(asked * a["safety_factor"], 2), unit=unit))

        if full:
            result: Dict[str, Any] = {
                "status": "MATCHES_FOUND",
                "count": len(full),
                "has_soft_criteria": soft,
                "recommended_actuators": _compact_rows([x["row"] for x in shown], focus),
                "ranking": ranking_for_llm,
            }
            store["status"] = "MATCHES_FOUND"
        else:
            want_nm = a.get("min_torque_nm")
            if want_nm is None and a.get("min_torque_in_lbs") is not None:
                cur.execute(
                    "SELECT MIN(on_off_torque_nm / NULLIF(on_off_torque_in_lbs, 0)) AS r FROM actuators "
                    "WHERE is_available AND on_off_torque_in_lbs IS NOT NULL;"
                )
                ratio = cur.fetchone()["r"]
                want_nm = float(ratio) * a["min_torque_in_lbs"] if ratio else None
            diag = _relaxation_diagnostics(cur, a, want_nm)
            store["relaxed"] = rec.relaxed_codes(ranked[0], a)
            store["status"] = "NO_EXACT_MATCH_CONSTRAINT_RELAXATION"
            result = {
                "status": "NO_EXACT_MATCH_CONSTRAINT_RELAXATION",
                "count": 0,
                "diagnostics": [record_alert(d["code"], **d["params"])["message"] for d in diag],
                "closest_alternative_actuators": _compact_rows([x["row"] for x in shown[:3]], focus),
                "ranking": ranking_for_llm[:3],
                "unmet_constraints": [c["key"] for c in ranked[0]["criteria"] if not c["met"]],
            }
        if alerts:
            result["alerts"] = alerts
        if ignored:
            result["ignored_arguments"] = ignored  # el usuario no los dijo: no se aplicaron
    record_tool_trace("recommend_actuators", args_dict, RECOMMEND_SQL, result, (time.perf_counter() - t0) * 1000)
    return result


# =====================================================================
# TOOL 3: CONOCIMIENTO TECNICO DETERMINISTA (palabras clave + pg_trgm, sin LLM)
# =====================================================================
KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge.json"
FUZZY_MIN_SIM = 0.4


class SearchKnowledgeInput(BaseModel):
    query: str = Field(
        ...,
        description="Technical question about Series 76 concepts, voltage/frequency tolerances, certifications (CSA, ATEX, Class I Div 1), or definitions (FLA, LRA, Duty Cycle S4%).",
    )


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def _load_knowledge() -> List[Dict[str, Any]]:
    return json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))


def _tag_in(tag: str, norm_query: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(_norm_text(tag)) + r"(?![a-z0-9])", norm_query) is not None


@tool("search_engineering_knowledge", args_schema=SearchKnowledgeInput)
def search_engineering_knowledge(query: str) -> Dict[str, Any]:
    """
    Returns the Series 76 knowledge fragment (definitions, voltage +/-10% and frequency +/-5% tolerances,
    hazardous-area certifications, CSA exception for Sizes 6 and 7) that best matches the query by keywords.
    """
    t0 = time.perf_counter()
    sql_used = "(keyword match over data/knowledge.json tags)"
    try:
        chunks = _load_knowledge()
        norm_q = _norm_text(query)
        # Puntaje: cada etiqueta presente suma su numero de palabras (las frases largas son mas especificas)
        scored = [
            (sum(len(t.split()) for t in c["tags"] if _tag_in(t, norm_q)), c) for c in chunks
        ]
        mode = "keyword"
        if not any(sc > 0 for sc, _ in scored):
            # Sin coincidencia exacta: recuperacion de typos con pg_trgm sobre las etiquetas
            mode = "pg_trgm"
            words = sorted({w for w in re.findall(r"[a-z0-9]{4,}", norm_q)})
            tag_owner = {_norm_text(t): c["chunk_key"] for c in chunks for t in c["tags"]}
            sql_used = (
                "SELECT w.word, t.tag, similarity(w.word, t.tag) FROM unnest(%s::text[]) w(word), "
                f"unnest(%s::text[]) t(tag) WHERE similarity(w.word, t.tag) >= {FUZZY_MIN_SIM};"
            )
            hits: List[Dict[str, Any]] = []
            if words:
                with get_db_cursor() as cur:
                    cur.execute(sql_used, (words, list(tag_owner)))
                    hits = cur.fetchall()
            by_key: Dict[str, float] = {}
            for h in hits:
                k = tag_owner[h["tag"]]
                by_key[k] = by_key.get(k, 0.0) + float(h["similarity"])
            scored = [(by_key.get(c["chunk_key"], 0.0), c) for c in chunks]

        scored = [(sc, c) for sc, c in scored if sc > 0]
        # Orden determinista: puntaje desc, luego orden de aparicion en knowledge.json
        scored.sort(key=lambda x: -x[0])
        if not scored:
            result: Dict[str, Any] = {
                "status": "NO_KNOWLEDGE_MATCH",
                "message": "No knowledge fragment matches the query. Do not answer from memory.",
            }
        else:
            top = scored[0][0]
            best = [c for sc, c in scored if sc >= top][:2]
            result = {
                "status": "KNOWLEDGE_RETRIEVED",
                "retrieval_mode": mode,
                "chunks": [
                    {"chunk_key": c["chunk_key"], "title": c["title"], "content": c["content"]} for c in best
                ],
            }
    except Exception as exc:  # estado de error explicito: nunca se devuelven fragmentos "por si acaso"
        result = {
            "status": "KNOWLEDGE_ERROR",
            "message": f"Knowledge lookup failed ({type(exc).__name__}). Tell the user the information is unavailable.",
        }
    if result["status"] in ("KNOWLEDGE_ERROR", "NO_KNOWLEDGE_MATCH"):
        record_alert("KNOWLEDGE_UNAVAILABLE")
    record_tool_trace(
        "search_engineering_knowledge",
        {"query": query},
        sql_used,
        result,
        (time.perf_counter() - t0) * 1000,
    )
    return result


# =====================================================================
# CATÁLOGO Y RANKING (solo lectura, SQL directo; los textos los arma app/overview.py desde estas salidas)
# =====================================================================
OVERVIEW_ASPECTS = ("summary", "count", "voltages", "sizes", "enclosures", "phases", "compare_sizes")
RANK_METRICS: Dict[str, Dict[str, Any]] = {
    # lista blanca: la métrica llega como nombre, nunca como SQL. N/A y valores NULL se excluyen siempre.
    "torque": {"expr": "GREATEST(on_off_torque_nm, modulating_torque_nm)", "unit": "Nm", "best": "max"},
    "power": {"expr": "motor_power_watts", "unit": "W", "best": "max"},
    "speed": {"expr": "COALESCE(speed_60hz_sec, speed_dc_or_fixed_sec)", "unit": "s", "best": "min"},
    "fla": {"expr": "COALESCE(fla_60hz_amps, fla_dc_or_fixed_amps)", "unit": "A", "best": "min"},
    "lra": {"expr": "COALESCE(lra_60hz_amps, lra_dc_or_fixed_amps)", "unit": "A", "best": "min"},
    "duty": {"expr": "GREATEST(on_off_duty_cycle_pct, modulating_duty_cycle_pct)", "unit": "%", "best": "max"},
}
RANK_FILTER_COLS = {"voltage_num": "voltage_num", "phase_type": "phase_type", "enclosure_type": "enclosure_type"}
RANK_MAX_ROWS = 4          # empates: se muestran hasta este número de tarjetas (el recuento total se informa)


def _where(filters: Dict[str, Any]) -> (str, List[Any]):
    clauses, params = [], []
    for k, col in RANK_FILTER_COLS.items():
        if filters.get(k) is not None:
            clauses.append(f"{col} = %s")
            params.append(filters[k])
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


class CatalogOverviewInput(BaseModel):
    aspect: str = Field("summary", description="summary | count | voltages | sizes | enclosures | phases | compare_sizes")
    sizes: Optional[List[int]] = Field(None, description="Frame sizes (1-7, from 761-767) to compare when aspect=compare_sizes.")
    voltage_num: Optional[int] = Field(None, description="Filter for aspect=count: 24, 110 or 220.")
    phase_type: Optional[str] = Field(None, description="Filter for aspect=count: 'Single Phase', '3 Phase', 'AC/DC' or 'DC'.")
    enclosure_type: Optional[str] = Field(None, description="Filter for aspect=count: 'Weatherproof' or 'Explosionproof'.")


def _na_groups(cur: Any, w: str = "", params: Any = ()) -> tuple:
    """Modelos listados como N/A (is_available = FALSE) agrupados por voltaje y alimentación, leídos de la base."""
    sql = ("SELECT voltage_num v, phase_type ph, array_agg(size_code ORDER BY size_code) sizes FROM actuators "
           f"WHERE NOT is_available{w} GROUP BY 1, 2 ORDER BY 1, 2;")
    cur.execute(sql, params)
    return sql, [{"voltage": int(g["v"]), "phase_type": g["ph"], "sizes": list(g["sizes"])} for g in cur.fetchall()]


@tool("catalog_overview", args_schema=CatalogOverviewInput)
def catalog_overview(aspect: str = "summary", sizes: Optional[List[int]] = None, voltage_num: Optional[int] = None,
                     phase_type: Optional[str] = None, enclosure_type: Optional[str] = None) -> Dict[str, Any]:
    """Read-only catalog facts from the database: how many models, which voltages/phases/enclosures/sizes exist,
    available vs N/A counts, torque range per frame size, and a comparison of two frame sizes."""
    t0 = time.perf_counter()
    aspect = aspect if aspect in OVERVIEW_ASPECTS else "summary"
    filters = {"voltage_num": voltage_num, "phase_type": phase_type, "enclosure_type": enclosure_type}
    sql_used = ""
    try:
        with get_db_cursor() as cur:
            if aspect == "compare_sizes":
                fs = sorted({int(x) for x in (sizes or []) if 1 <= int(x) <= 7})[:2]
                sql_used = ("SELECT frame_size, COUNT(*) n, SUM(is_available::int) av, MIN(LEAST(on_off_torque_nm, modulating_torque_nm)) tmin, "
                            "MAX(GREATEST(on_off_torque_nm, modulating_torque_nm)) tmax, MIN(motor_power_watts) pmin, MAX(motor_power_watts) pmax "
                            "FROM actuators WHERE frame_size = ANY(%s) GROUP BY frame_size ORDER BY frame_size;")
                cur.execute(sql_used, (fs,))
                rows = cur.fetchall()
                result: Dict[str, Any] = {"status": "CATALOG_OVERVIEW", "aspect": aspect, "sizes": [
                    {"size": 760 + int(r["frame_size"]), "models": int(r["n"]), "available": int(r["av"]),
                     "torque_min_nm": _num(float(r["tmin"])) if r["tmin"] is not None else None,
                     "torque_max_nm": _num(float(r["tmax"])) if r["tmax"] is not None else None,
                     "power_min_w": r["pmin"], "power_max_w": r["pmax"]} for r in rows]}
                if len(rows) < 2:
                    result = {"status": "CATALOG_NOT_FOUND", "aspect": aspect, "message": "Two valid frame sizes (761-767) are needed."}
            elif aspect == "count":
                w, params = _where(filters)
                sql_used = f"SELECT COUNT(*) n, SUM(is_available::int) av FROM actuators WHERE TRUE{w};"
                cur.execute(sql_used, params)
                r = cur.fetchone()
                result = {"status": "CATALOG_OVERVIEW", "aspect": aspect, "filters": {k: v for k, v in filters.items() if v is not None},
                          "models": int(r["n"]), "available": int(r["av"] or 0)}
                if not any(v is not None for v in filters.values()) and result["models"] > result["available"]:
                    sql_n, result["na_groups"] = _na_groups(cur)
                    sql_used += " " + sql_n
                if result["models"] == 0 and voltage_num is not None:     # voltaje inexistente (12 V, 48 V...): se listan los que sí hay
                    sql_v = ("SELECT voltage_num v, array_agg(DISTINCT enclosure_type) encs FROM actuators WHERE is_available GROUP BY voltage_num ORDER BY voltage_num;")
                    cur.execute(sql_v)
                    sql_used += " " + sql_v
                    result["voltages_available"] = [{"voltage": int(x["v"]), "enclosures": sorted(x["encs"])} for x in cur.fetchall()]
                if any(v is not None for v in filters.values()):          # desglose por carcasa y sufijo (para «¿hay de 24 V?»)
                    sql_g = ("SELECT enclosure_type e, split_part(split_part(base_part_number, '-', 2), '/', 1) suf, COUNT(*) n, "
                             f"SUM(is_available::int) av FROM actuators WHERE TRUE{w} GROUP BY 1, 2 ORDER BY 1, 2;")
                    cur.execute(sql_g, params)
                    sql_used += " " + sql_g
                    result["groups"] = [{"enclosure": g["e"], "suffix": g["suf"], "models": int(g["n"]), "available": int(g["av"] or 0)} for g in cur.fetchall()]
            elif aspect == "sizes":
                sql_used = ("SELECT frame_size, COUNT(*) n, MIN(LEAST(on_off_torque_nm, modulating_torque_nm)) tmin, "
                            "MAX(GREATEST(on_off_torque_nm, modulating_torque_nm)) tmax FROM actuators WHERE is_available GROUP BY frame_size ORDER BY frame_size;")
                cur.execute(sql_used)
                result = {"status": "CATALOG_OVERVIEW", "aspect": aspect, "sizes": [
                    {"size": 760 + int(r["frame_size"]), "models": int(r["n"]), "torque_min_nm": _num(float(r["tmin"])),
                     "torque_max_nm": _num(float(r["tmax"]))} for r in cur.fetchall()]}
            elif aspect in ("voltages", "phases", "enclosures"):
                col = {"voltages": "voltage_num", "phases": "phase_type", "enclosures": "enclosure_type"}[aspect]
                sql_used = f"SELECT {col} v, COUNT(*) n FROM actuators WHERE is_available GROUP BY {col} ORDER BY {col};"
                cur.execute(sql_used)
                result = {"status": "CATALOG_OVERVIEW", "aspect": aspect, "values": [{"value": r["v"], "models": int(r["n"])} for r in cur.fetchall()]}
            else:
                sql_used = "SELECT COUNT(*) n, SUM(is_available::int) av, COUNT(DISTINCT frame_size) fs FROM actuators;"
                cur.execute(sql_used)
                r = cur.fetchone()
                cur.execute("SELECT DISTINCT voltage_num FROM actuators WHERE is_available ORDER BY 1;")
                volts = [int(x["voltage_num"]) for x in cur.fetchall()]
                cur.execute("SELECT DISTINCT enclosure_type FROM actuators WHERE is_available ORDER BY 1;")
                encs = [x["enclosure_type"] for x in cur.fetchall()]
                result = {"status": "CATALOG_OVERVIEW", "aspect": "summary", "models": int(r["n"]), "available": int(r["av"]),
                          "not_available": int(r["n"]) - int(r["av"]), "frame_sizes": int(r["fs"]), "voltages": volts, "enclosures": encs}
                if result["not_available"]:
                    sql_n, result["na_groups"] = _na_groups(cur)
                    sql_used += " " + sql_n
    except Exception as exc:  # noqa: BLE001
        result = {"status": "CATALOG_ERROR", "message": f"Catalog lookup failed ({type(exc).__name__})."}
    record_tool_trace("catalog_overview", {"aspect": aspect, **{k: v for k, v in filters.items() if v is not None},
                                           **({"sizes": sizes} if sizes else {})}, sql_used, result, (time.perf_counter() - t0) * 1000)
    return result


class RankActuatorsInput(BaseModel):
    metric: str = Field(..., description="torque | power | speed | fla | lra | duty")
    order: Optional[str] = Field(None, description="'max' or 'min'. Omit to use the natural direction (torque/power/duty: max; speed/FLA/LRA: min).")
    voltage_num: Optional[int] = Field(None, description="Hard filter: 24, 110 or 220.")
    phase_type: Optional[str] = Field(None, description="Hard filter: 'Single Phase', '3 Phase', 'AC/DC' or 'DC'.")
    enclosure_type: Optional[str] = Field(None, description="Hard filter: 'Weatherproof' or 'Explosionproof'.")


@tool("rank_actuators", args_schema=RankActuatorsInput)
def rank_actuators(metric: str, order: Optional[str] = None, voltage_num: Optional[int] = None,
                   phase_type: Optional[str] = None, enclosure_type: Optional[str] = None) -> Dict[str, Any]:
    """Which available model has the highest or lowest value of one metric (torque, power, speed, FLA, LRA, duty), with optional
    hard filters. Not-available (N/A) models and missing values are excluded; ties are all returned."""
    t0 = time.perf_counter()
    spec = RANK_METRICS.get(metric)
    filters = {"voltage_num": voltage_num, "phase_type": phase_type, "enclosure_type": enclosure_type}
    args = {"metric": metric, "order": order, **{k: v for k, v in filters.items() if v is not None}}
    if spec is None:
        result: Dict[str, Any] = {"status": "RANK_INVALID_METRIC", "message": "Unsupported metric."}
        record_tool_trace("rank_actuators", args, "", result, (time.perf_counter() - t0) * 1000)
        return result
    direction = order if order in ("max", "min") else spec["best"]
    w, params = _where(filters)
    expr = spec["expr"]
    sql_used = (f"WITH r AS (SELECT id, base_part_number, {expr} AS v FROM actuators WHERE is_available AND {expr} IS NOT NULL{w}) "
                f"SELECT id, base_part_number, v FROM r WHERE v = (SELECT {direction.upper()}(v) FROM r) ORDER BY base_part_number;")
    try:
        with get_db_cursor() as cur:
            cur.execute(sql_used, params)
            rows = cur.fetchall()
        if not rows:
            result = {"status": "RANK_NO_DATA", "metric": metric, "order": direction, "filters": {k: v for k, v in filters.items() if v is not None}}
        else:
            shown = rows[:RANK_MAX_ROWS]
            register_ui_actuators(shown)
            result = {"status": "RANKED", "metric": metric, "order": direction, "unit": spec["unit"],
                      "value": _num(float(rows[0]["v"])), "ties": len(rows),
                      "part_numbers": [r["base_part_number"] for r in shown],
                      "filters": {k: v for k, v in filters.items() if v is not None}}
    except Exception as exc:  # noqa: BLE001
        result = {"status": "RANK_ERROR", "message": f"Ranking failed ({type(exc).__name__})."}
    record_tool_trace("rank_actuators", args, sql_used, result, (time.perf_counter() - t0) * 1000)
    return result


# El LLM que redacta solo puede llamar a estas tres; catalog_overview y rank_actuators las fuerzan el router o el clasificador.
LLM_TOOLS = [
    lookup_actuator_by_part_number,
    recommend_actuators,
    search_engineering_knowledge,
]
ALL_SERIES76_TOOLS = LLM_TOOLS + [catalog_overview, rank_actuators]