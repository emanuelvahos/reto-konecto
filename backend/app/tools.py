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
]


def reset_turn_telemetry() -> None:
    current_turn_tool_traces.set([])
    current_turn_actuators.set({})
    current_turn_alerts.set([])


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


def record_alert(code: str, **params: Any) -> Dict[str, str]:
    """Registra la alerta en el contenedor del turno (mutación en sitio) y devuelve su forma para el LLM (en)."""
    alerts = current_turn_alerts.get()
    entry = {"code": code, "params": params}
    if entry not in alerts:
        alerts.append(entry)
    return {"code": code, "message": render_alert_message(code, params, "en")}


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


@tool("lookup_actuator_by_part_number", args_schema=LookupPartNumberInput)
def lookup_actuator_by_part_number(part_number: str, focus: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Looks up Series 76 actuator specs by Base Part Number. Handles exact matches, missing '/A',
    N/A models in 220V 3-Phase, and typos (pg_trgm fuzzy match).
    """
    t0 = time.perf_counter()
    args = {"part_number": part_number, **({"focus": focus} if focus else {})}
    clean_input = part_number.strip().upper()
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
            LIMIT 4;
        """
        cur.execute(sql_fuzzy, (clean_input, clean_input))
        fuzzy_rows = sanitize_rows(cur.fetchall())

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


# =====================================================================
# TOOL 2: MOTOR DE RECOMENDACIÓN CON RELAJACIÓN DE RESTRICCIONES
# =====================================================================
class RecommendActuatorsInput(BaseModel):
    min_torque_nm: Optional[float] = Field(None, description="Minimum required output torque in Nm.")
    min_torque_in_lbs: Optional[float] = Field(None, description="Minimum required output torque in in-lbs.")
    application_type: Optional[str] = Field(
        None,
        description="'On/Off', 'Modulating', or None if not specified by the user.",
    )
    enclosure_type: Optional[str] = Field(None, description="'Weatherproof' or 'Explosionproof'.")
    voltage_num: Optional[int] = Field(None, description="Supply voltage: 24, 110, or 220.")
    phase_type: Optional[str] = Field(None, description="'Single Phase', '3 Phase', 'AC/DC', or 'DC'.")
    frequency_hz: Optional[int] = Field(None, description="50 or 60 (Hz) when checking speed or current.")
    max_speed_sec: Optional[float] = Field(None, description="Maximum seconds for a 90-degree turn.")
    max_fla_amps: Optional[float] = Field(None, description="Maximum Full Load Current (FLA) in Amps.")
    min_duty_cycle_pct: Optional[int] = Field(None, description="Minimum duty cycle (S4%).")
    require_csa_certification: Optional[bool] = Field(None, description="True only if the user requires CSA certification.")


def _torque_ceiling(cur, where: str, params: List[Any]) -> Optional[float]:
    cur.execute(
        "SELECT MAX(GREATEST(COALESCE(on_off_torque_nm, 0), COALESCE(modulating_torque_nm, 0))) AS m "
        f"FROM actuators WHERE is_available = TRUE AND {where};",
        tuple(params),
    )
    m = cur.fetchone()["m"]
    return float(m) if m is not None else None


@tool("recommend_actuators", args_schema=RecommendActuatorsInput)
def recommend_actuators(
    min_torque_nm: Optional[float] = None,
    min_torque_in_lbs: Optional[float] = None,
    application_type: Optional[str] = None,
    enclosure_type: Optional[str] = None,
    voltage_num: Optional[int] = None,
    phase_type: Optional[str] = None,
    frequency_hz: Optional[int] = None,
    max_speed_sec: Optional[float] = None,
    max_fla_amps: Optional[float] = None,
    min_duty_cycle_pct: Optional[int] = None,
    require_csa_certification: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Recommends Series 76 actuators for technical requirements. If none satisfies all of them,
    runs constraint relaxation and returns diagnostics and the closest alternatives.
    """
    t0 = time.perf_counter()
    args_dict = {k: v for k, v in locals().items() if k != "t0" and v is not None}

    conditions = ["is_available = TRUE"]
    params: List[Any] = []
    ambiguous_service = False

    app_mode = (application_type or "").strip().lower()
    if app_mode in ("on/off", "on_off", "onoff"):
        if min_torque_nm is not None:
            conditions.append("on_off_torque_nm >= %s")
            params.append(min_torque_nm)
        if min_torque_in_lbs is not None:
            conditions.append("on_off_torque_in_lbs >= %s")
            params.append(min_torque_in_lbs)
        if min_duty_cycle_pct is not None:
            conditions.append("on_off_duty_cycle_pct >= %s")
            params.append(min_duty_cycle_pct)
        conditions.append("on_off_torque_nm IS NOT NULL")
    elif app_mode == "modulating":
        # Trifásico: un único torque de salida (guardado como on/off). Es candidato con advertencia
        # SINGLE_TORQUE_RATING, salvo que se exija un duty modulante, que la hoja no permite verificar.
        mod_parts = ["modulating_torque_nm IS NOT NULL"]
        mod_params: List[Any] = []
        single_parts = ["phase_type = '3 Phase'", "modulating_torque_nm IS NULL", "on_off_torque_nm IS NOT NULL"]
        single_params: List[Any] = []
        if min_torque_nm is not None:
            mod_parts.append("modulating_torque_nm >= %s")
            mod_params.append(min_torque_nm)
            single_parts.append("on_off_torque_nm >= %s")
            single_params.append(min_torque_nm)
        if min_torque_in_lbs is not None:
            mod_parts.append("modulating_torque_in_lbs >= %s")
            mod_params.append(min_torque_in_lbs)
            single_parts.append("on_off_torque_in_lbs >= %s")
            single_params.append(min_torque_in_lbs)
        if min_duty_cycle_pct is not None:
            mod_parts.append("modulating_duty_cycle_pct >= %s")
            mod_params.append(min_duty_cycle_pct)
            conditions.append("(" + " AND ".join(mod_parts) + ")")
            params.extend(mod_params)
        else:
            conditions.append("((" + " AND ".join(mod_parts) + ") OR (" + " AND ".join(single_parts) + "))")
            params.extend(mod_params + single_params)
    else:
        # Sin tipo de servicio: cumple en CUALQUIERA de los dos
        if min_torque_nm is not None or min_torque_in_lbs is not None:
            ambiguous_service = True
        if min_torque_nm is not None:
            conditions.append("(COALESCE(on_off_torque_nm, 0) >= %s OR COALESCE(modulating_torque_nm, 0) >= %s)")
            params.extend([min_torque_nm, min_torque_nm])
        if min_torque_in_lbs is not None:
            conditions.append("(COALESCE(on_off_torque_in_lbs, 0) >= %s OR COALESCE(modulating_torque_in_lbs, 0) >= %s)")
            params.extend([min_torque_in_lbs, min_torque_in_lbs])
        if min_duty_cycle_pct is not None:
            conditions.append("(COALESCE(on_off_duty_cycle_pct, 0) >= %s OR COALESCE(modulating_duty_cycle_pct, 0) >= %s)")
            params.extend([min_duty_cycle_pct, min_duty_cycle_pct])

    if enclosure_type:
        conditions.append("LOWER(enclosure_type) = LOWER(%s)")
        params.append(enclosure_type.strip())

    if voltage_num is not None:
        conditions.append("voltage_num = %s")
        params.append(voltage_num)

    if phase_type:
        p_clean = phase_type.strip().lower()
        if "3" in p_clean or "three" in p_clean:
            conditions.append("phase_type = '3 Phase'")
        elif "single" in p_clean or "1" in p_clean:
            conditions.append("phase_type = 'Single Phase'")
        elif p_clean == "dc":
            conditions.append("phase_type IN ('DC', 'AC/DC')")
        else:
            conditions.append("LOWER(phase_type) = LOWER(%s)")
            params.append(phase_type.strip())

    if max_speed_sec is not None:
        if frequency_hz == 50:
            conditions.append("COALESCE(speed_50hz_sec, speed_dc_or_fixed_sec) <= %s")
            params.append(max_speed_sec)
        elif frequency_hz == 60:
            conditions.append("COALESCE(speed_60hz_sec, speed_dc_or_fixed_sec) <= %s")
            params.append(max_speed_sec)
        else:
            conditions.append(
                "(COALESCE(speed_60hz_sec, 9999) <= %s OR COALESCE(speed_50hz_sec, 9999) <= %s OR COALESCE(speed_dc_or_fixed_sec, 9999) <= %s)"
            )
            params.extend([max_speed_sec, max_speed_sec, max_speed_sec])

    if max_fla_amps is not None:
        if frequency_hz == 50:
            conditions.append("COALESCE(fla_50hz_amps, fla_dc_or_fixed_amps) <= %s")
            params.append(max_fla_amps)
        elif frequency_hz == 60:
            conditions.append("COALESCE(fla_60hz_amps, fla_dc_or_fixed_amps) <= %s")
            params.append(max_fla_amps)
        else:
            conditions.append(
                "(COALESCE(fla_60hz_amps, 9999) <= %s OR COALESCE(fla_50hz_amps, 9999) <= %s OR COALESCE(fla_dc_or_fixed_amps, 9999) <= %s)"
            )
            params.extend([max_fla_amps, max_fla_amps, max_fla_amps])

    if require_csa_certification is True:
        conditions.append("csa_certified = TRUE")

    where_clause = " AND ".join(conditions)
    order_col = (
        "COALESCE(modulating_torque_nm, on_off_torque_nm)"
        if app_mode == "modulating"
        else "COALESCE(on_off_torque_nm, modulating_torque_nm)"
    )
    sql_query = f"""
        SELECT * FROM actuators
        WHERE {where_clause}
        ORDER BY {order_col} ASC, voltage_num ASC
        LIMIT 6;
    """

    # Campos que el LLM necesita según lo preguntado (la tarjeta móvil muestra todo desde la DB)
    focus = ["torque", "power"]
    if min_duty_cycle_pct is not None:
        focus.append("duty")
    if max_speed_sec is not None:
        focus.append("speed")
    if max_fla_amps is not None:
        focus.append("current")

    with get_db_cursor() as cur:
        cur.execute(sql_query, tuple(params))
        matches = sanitize_rows(cur.fetchall())

        if matches:
            register_ui_actuators(matches)
            alerts = [record_alert("AMBIGUOUS_SERVICE_TYPE")] if ambiguous_service else []
            alerts += _single_torque_alerts(matches)
            result: Dict[str, Any] = {
                "status": "MATCHES_FOUND",
                "count": len(matches),
                "recommended_actuators": _compact_rows(matches, focus),
            }
            if alerts:
                result["alerts"] = alerts
            record_tool_trace("recommend_actuators", args_dict, sql_query, result,
                              (time.perf_counter() - t0) * 1000)
            return result

        # =================================================================
        # RELAJACIÓN DE RESTRICCIONES: todas las cifras salen de la DB
        # =================================================================
        want_nm = min_torque_nm
        if want_nm is None and min_torque_in_lbs is not None:
            cur.execute(
                "SELECT MIN(on_off_torque_nm / NULLIF(on_off_torque_in_lbs, 0)) AS r FROM actuators "
                "WHERE is_available AND on_off_torque_in_lbs IS NOT NULL;"
            )
            ratio = cur.fetchone()["r"]
            want_nm = float(ratio) * min_torque_in_lbs if ratio else None

        diag: List[Dict[str, Any]] = []  # [{code, params}] -> se localizan al construir el ui_payload
        if want_nm is not None:
            checks = []
            if require_csa_certification:
                checks.append(("csa", "", "csa_certified = TRUE", []))
            if voltage_num is not None:
                checks.append(("voltage", voltage_num, "voltage_num = %s", [voltage_num]))
            if enclosure_type:
                checks.append(("enclosure", enclosure_type.strip(), "LOWER(enclosure_type) = LOWER(%s)", [enclosure_type.strip()]))
            if phase_type:
                checks.append(("phase", phase_type.strip(), "LOWER(phase_type) = LOWER(%s)", [phase_type.strip()]))
            for kind, value, where, p in checks:
                ceiling = _torque_ceiling(cur, where, p)
                if ceiling is not None and want_nm > ceiling:
                    diag.append({"code": "TORQUE_ABOVE_CEILING", "params": {
                        "filter_kind": kind, "filter_value": value, "ceiling": _num(ceiling), "requested": _num(want_nm)}})
            catalog_max = _torque_ceiling(cur, "TRUE", [])
            if catalog_max is not None and want_nm > catalog_max:
                diag.append({"code": "CATALOG_TORQUE_CEILING", "params": {"ceiling": _num(catalog_max)}})
            if require_csa_certification:
                cur.execute("SELECT MIN(frame_size) AS f FROM actuators WHERE is_available AND NOT csa_certified;")
                f = cur.fetchone()["f"]
                if f is not None:
                    diag.append({"code": "CSA_SIZE_LIMIT", "params": {"frame_size": f}})
        if not diag:
            diag.append({"code": "CONSTRAINT_RELAXED", "params": {}})

        if want_nm is not None:
            cur.execute(
                "SELECT * FROM actuators WHERE is_available = TRUE "
                "ORDER BY ABS(COALESCE(on_off_torque_nm, modulating_torque_nm) - %s) ASC LIMIT 3;",
                (want_nm,),
            )
        else:
            cur.execute(
                "SELECT * FROM actuators WHERE is_available = TRUE "
                "ORDER BY COALESCE(on_off_torque_nm, modulating_torque_nm) ASC LIMIT 3;"
            )
        relaxed_candidates = sanitize_rows(cur.fetchall())

    register_ui_actuators(relaxed_candidates)
    diagnostics = [record_alert(d["code"], **d["params"])["message"] for d in diag]
    single_alerts = _single_torque_alerts(relaxed_candidates)
    result = {
        "status": "NO_EXACT_MATCH_CONSTRAINT_RELAXATION",
        "count": 0,
        "diagnostics": diagnostics,
        "closest_alternative_actuators": _compact_rows(relaxed_candidates, focus),
    }
    if single_alerts:
        result["alerts"] = single_alerts
    record_tool_trace("recommend_actuators", args_dict, sql_query, result,
                      (time.perf_counter() - t0) * 1000)
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


ALL_SERIES76_TOOLS = [
    lookup_actuator_by_part_number,
    recommend_actuators,
    search_engineering_knowledge,
]