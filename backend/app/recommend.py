"""Motor de recomendación determinista (sin LLM, sin DB: trabaja sobre filas ya leidas de PostgreSQL).

RESTRICCIONES DURAS (filtran; nunca se relajan):
  - voltaje (voltage_num), enclosure (si el usuario lo exige), fase (phase_type),
  - area peligrosa (hazardous_area=True) => solo Explosionproof.
  Hechos del catalogo que lo hacen consistente: 24V existe SOLO en Explosionproof y no tiene valores a 50/60 Hz
  (sus velocidades/corrientes son fijas: *_dc_or_fixed_*).

RESTRICCIONES BLANDAS (puntúan; se pueden relajar): torque minimo, duty S4 minimo, tiempo de giro maximo,
  FLA maximo y certificacion CSA.

SCORE (0..1) de un candidato que pasa las duras:
    satisfaccion = sum(w_i * s_i) / sum(w_i)         sobre los criterios blandos pedidos
    s_i = 1                                  si se cumple
    s_i = max(0, 1 - desviacion_relativa_i)  si no, con desviacion = |actual - pedido| / pedido
                                             (s_i = 0 si la hoja no da ese dato, p. ej. duty modulante en trifasico)
    economia     = 1 / (1 + holgura_torque_pct / 100)  si hay torque pedido y se cumple (menos sobredimensionado = mejor)
                   0                                    si hay torque pedido y no se cumple
                   0.5                                  si no se pidio torque (neutro)
    score        = (1 - ECONOMY_SHARE) * satisfaccion + ECONOMY_SHARE * economia
  Pesos: torque 3, duty 2, tiempo de giro 2, CSA 2, FLA 1.5. Sin criterios blandos, satisfaccion = 1.
  Desempate: menor torque, luego numero de parte. Todas las cifras (holgura %, desviacion %) se calculan aqui
  a partir de las filas; why / why_not se generan como {code, params} y se localizan en app.i18n.

ACLARACION: gate() pregunta (UNA dimension a la vez: voltaje, tipo de servicio, area peligrosa) solo si la dimension
  falta y es DECISIVA: al menos dos de sus opciones producen conjuntos de modelos distintos que cumplen todo lo pedido.
"""
from typing import Any, Dict, List, Optional

SOFT_WEIGHTS = {"torque": 3.0, "duty": 2.0, "speed": 2.0, "fla": 1.5, "csa": 2.0}
ECONOMY_SHARE = 0.1
OVERSIZE_PCT = 100.0   # holgura de torque a partir de la cual se avisa de sobredimensionamiento
TOP_N = 5

SPEED_COLS = ("speed_60hz_sec", "speed_50hz_sec", "speed_dc_or_fixed_sec")
FLA_COLS = ("fla_60hz_amps", "fla_50hz_amps", "fla_dc_or_fixed_amps")


# --------------------------------------------------------------------------------------------- normalización
def service_mode(application_type: Optional[str]) -> Optional[str]:
    s = (application_type or "").strip().lower().replace(" ", "")
    if s in ("on/off", "on_off", "onoff", "on-off"):
        return "onoff"
    if s.startswith("modul"):
        return "mod"
    return None


def clean_args(args: Dict[str, Any]) -> Dict[str, Any]:
    a = {k: v for k, v in args.items() if v is not None and not str(k).startswith("_")}
    enc = str(a.get("enclosure_type") or "").strip().lower()
    if enc:
        a["enclosure_type"] = "Weatherproof" if enc.startswith("weather") else "Explosionproof" if enc.startswith("explo") else a["enclosure_type"].strip()
    else:
        a.pop("enclosure_type", None)
    ph = str(a.get("phase_type") or "").strip().lower()
    if ph:
        a["phase_type"] = "3 Phase" if ("3" in ph or "three" in ph or "tri" in ph) else "Single Phase" if ("single" in ph or "1" in ph or "mono" in ph) else "DC" if ph == "dc" else a["phase_type"].strip()
    else:
        a.pop("phase_type", None)
    mode = service_mode(a.get("application_type"))
    if mode:
        a["application_type"] = "On/Off" if mode == "onoff" else "Modulating"
    else:
        a.pop("application_type", None)
    try:  # factor de seguridad: solo si el usuario lo pidió (ground_args) y es un multiplicador razonable
        f = float(a["safety_factor"]) if a.get("safety_factor") is not None else None
    except (TypeError, ValueError):
        f = None
    if f is not None and 1.0 < f <= 5.0:
        a["safety_factor"] = f
    else:
        a.pop("safety_factor", None)
    return a


def hard_codes(a: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if a.get("hazardous_area") is True:
        out.append({"code": "HC_HAZARDOUS", "params": {}})
    if a.get("voltage_num") is not None:
        out.append({"code": "HC_VOLTAGE", "params": {"v": int(a["voltage_num"])}})
    if a.get("enclosure_type") and not (a.get("hazardous_area") is True and a["enclosure_type"] == "Explosionproof"):
        out.append({"code": "HC_ENCLOSURE", "params": {"v": a["enclosure_type"]}})
    if a.get("phase_type"):
        out.append({"code": "HC_PHASE", "params": {"v": a["phase_type"]}})
    return out


def passes_hard(row: Dict[str, Any], a: Dict[str, Any]) -> bool:
    if not row.get("is_available", True):
        return False
    enc = a.get("enclosure_type")
    if a.get("hazardous_area") is True:
        if enc and enc != "Explosionproof":
            return False
        enc = "Explosionproof"
    if enc and str(row["enclosure_type"]).lower() != enc.lower():
        return False
    if a.get("voltage_num") is not None and row["voltage_num"] != int(a["voltage_num"]):
        return False
    ph = a.get("phase_type")
    if ph == "DC":
        return row["phase_type"] in ("DC", "AC/DC")
    if ph and row["phase_type"] != ph:
        return False
    return True


# --------------------------------------------------------------------------------------------- criterios blandos
def _f(v: Any) -> Optional[float]:
    return None if v is None else float(v)


def is_single_rating(row: Dict[str, Any]) -> bool:
    return row.get("phase_type") == "3 Phase" and row.get("modulating_torque_nm") is None and row.get("on_off_torque_nm") is not None


def torque_of(row: Dict[str, Any], mode: Optional[str], unit: str) -> Dict[str, Any]:
    suffix = "nm" if unit == "Nm" else "in_lbs"
    on, mod = _f(row.get(f"on_off_torque_{suffix}")), _f(row.get(f"modulating_torque_{suffix}"))
    if mode == "onoff":
        return {"value": on, "kind": "single" if is_single_rating(row) else "onoff"}
    if mode == "mod":
        if mod is None and is_single_rating(row) and on is not None:
            return {"value": on, "kind": "single"}  # trifasico: unico torque de salida (alerta SINGLE_TORQUE_RATING)
        return {"value": mod, "kind": "mod"}
    cands = [(v, k) for v, k in ((on, "single" if is_single_rating(row) else "onoff"), (mod, "mod")) if v is not None]
    if not cands:
        return {"value": None, "kind": "onoff"}
    v, k = max(cands)
    return {"value": v, "kind": k}


def _freq_value(row: Dict[str, Any], cols, freq: Optional[int]):
    v60, v50, vfx = (_f(row.get(c)) for c in cols)
    if freq == 50:
        return (v50, "50") if v50 is not None else (vfx, None)
    if freq == 60:
        return (v60, "60") if v60 is not None else (vfx, None)
    options = [(v, h) for v, h in ((v60, "60"), (v50, "50"), (vfx, None)) if v is not None]
    return min(options, key=lambda x: x[0]) if options else (None, None)


def _min_crit(key: str, required: float, actual: Optional[float], unit: str, **extra: Any) -> Dict[str, Any]:
    c: Dict[str, Any] = {"key": key, "required": required, "actual": actual, "unit": unit, "dir": "min", **extra}
    if actual is None:
        c.update(met=False, no_data=True, dev=1.0)
    elif actual >= required:
        c.update(met=True, margin_pct=round((actual - required) / required * 100, 1), dev=0.0)
    else:
        c.update(met=False, shortfall_pct=round((required - actual) / required * 100, 1), dev=(required - actual) / required)
    return c


def _max_crit(key: str, required: float, actual: Optional[float], unit: str, **extra: Any) -> Dict[str, Any]:
    c: Dict[str, Any] = {"key": key, "required": required, "actual": actual, "unit": unit, "dir": "max", **extra}
    if actual is None:
        c.update(met=False, no_data=True, dev=1.0)
    elif actual <= required:
        c.update(met=True, margin_pct=round((required - actual) / required * 100, 1), dev=0.0)
    else:
        c.update(met=False, shortfall_pct=round((actual - required) / required * 100, 1), dev=(actual - required) / required)
    return c


def evaluate(row: Dict[str, Any], a: Dict[str, Any]) -> List[Dict[str, Any]]:
    mode = service_mode(a.get("application_type"))
    freq = a.get("frequency_hz")
    crits: List[Dict[str, Any]] = []
    if a.get("min_torque_nm") is not None or a.get("min_torque_in_lbs") is not None:
        unit = "Nm" if a.get("min_torque_nm") is not None else "in-lbs"
        req = float(a["min_torque_nm"] if unit == "Nm" else a["min_torque_in_lbs"])
        if a.get("safety_factor"):   # SOLO si el usuario lo pidió; el PDF no define ningún factor de seguridad
            req = round(req * float(a["safety_factor"]), 2)
        t = torque_of(row, mode, unit)
        crits.append(_min_crit("torque", req, t["value"], unit, kind=t["kind"]))
    if a.get("min_duty_cycle_pct") is not None:
        on, mod = _f(row.get("on_off_duty_cycle_pct")), _f(row.get("modulating_duty_cycle_pct"))
        val = on if mode == "onoff" else mod if mode == "mod" else max([v for v in (on, mod) if v is not None], default=None)
        crits.append(_min_crit("duty", float(a["min_duty_cycle_pct"]), val, "%"))
    if a.get("max_speed_sec") is not None:
        v, hz = _freq_value(row, SPEED_COLS, freq)
        crits.append(_max_crit("speed", float(a["max_speed_sec"]), v, "s", hz=hz))
    if a.get("max_fla_amps") is not None:
        v, hz = _freq_value(row, FLA_COLS, freq)
        crits.append(_max_crit("fla", float(a["max_fla_amps"]), v, "A", hz=hz))
    if a.get("require_csa_certification") is True:
        ok = bool(row.get("csa_certified"))
        crits.append({"key": "csa", "met": ok, "dev": 0.0 if ok else 1.0, "frame_size": row.get("frame_size"), "dir": "flag"})
    return crits


def _torque_sort_key(row: Dict[str, Any]) -> float:
    vals = [_f(row.get("on_off_torque_nm")), _f(row.get("modulating_torque_nm"))]
    vals = [v for v in vals if v is not None]
    return min(vals) if vals else 0.0


def score_candidate(row: Dict[str, Any], a: Dict[str, Any]) -> Dict[str, Any]:
    crits = evaluate(row, a)
    if crits:
        wsum = sum(SOFT_WEIGHTS[c["key"]] for c in crits)
        sat = sum(SOFT_WEIGHTS[c["key"]] * max(0.0, 1.0 - c["dev"]) for c in crits) / wsum
    else:
        sat = 1.0
    tq = next((c for c in crits if c["key"] == "torque"), None)
    if tq is None:
        economy = 0.5
    elif tq["met"]:
        economy = 1.0 / (1.0 + tq["margin_pct"] / 100.0)
    else:
        economy = 0.0
    score = round((1 - ECONOMY_SHARE) * sat + ECONOMY_SHARE * economy, 3)
    return {"row": row, "criteria": crits, "all_met": all(c["met"] for c in crits), "score": score}


def rank(candidates: List[Dict[str, Any]], a: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = [score_candidate(r, a) for r in candidates]
    items.sort(key=lambda x: (-x["score"], _torque_sort_key(x["row"]), x["row"]["base_part_number"]))
    return items


def full_matches(rows: List[Dict[str, Any]], a: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [r for r in rows if passes_hard(r, a) and all(c["met"] for c in evaluate(r, a))]


# --------------------------------------------------------------------------------------------- why / why_not
def reasons(item: Dict[str, Any], is_top_full_match: bool) -> Dict[str, List[Dict[str, Any]]]:
    why: List[Dict[str, Any]] = []
    why_not: List[Dict[str, Any]] = []
    for c in item["criteria"]:
        k = c["key"]
        if k == "csa":
            if c["met"]:
                why.append({"code": "W_CSA_OK", "params": {}})
            else:
                why_not.append({"code": "N_CSA_NO", "params": {"frame_size": c["frame_size"]}})
            continue
        base = {"actual": _n(c["actual"]), "required": _n(c["required"]), "unit": c["unit"], "hz": c.get("hz"), "kind": c.get("kind")}
        if c["met"]:
            why.append({"code": f"W_{k.upper()}_MET", "params": {**base, "margin_pct": _n(c["margin_pct"])}})
        elif c.get("no_data"):
            why_not.append({"code": f"N_{k.upper()}_NO_RATING", "params": base})
        else:
            why_not.append({"code": f"N_{k.upper()}_SHORT", "params": {**base, "shortfall_pct": _n(c["shortfall_pct"])}})
    tq = next((c for c in item["criteria"] if c["key"] == "torque"), None)
    if tq and tq["met"] and tq["margin_pct"] >= OVERSIZE_PCT:
        why_not.append({"code": "N_OVERSIZED", "params": {"margin_pct": _n(tq["margin_pct"])}})
    if is_top_full_match and item["criteria"]:
        why.append({"code": "W_LEAST_OVERSIZED", "params": {}})
    return {"why": why, "why_not": why_not}


def _n(v: Any) -> Any:
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def relaxed_codes(item: Dict[str, Any], a: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Restricciones blandas que el mejor candidato NO cumple (las que hay que relajar)."""
    out: List[Dict[str, Any]] = []
    for c in item["criteria"]:
        if c["met"]:
            continue
        if c["key"] == "csa":
            out.append({"code": "RC_CSA", "params": {}})
        else:
            out.append({"code": f"RC_{c['key'].upper()}", "params": {"required": _n(c["required"]), "unit": c["unit"]}})
    return out


# --------------------------------------------------------------------------------------------- aclaración
def gate(rows: List[Dict[str, Any]], a: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Devuelve {"topic", "options": [{"args": {...}}]} si falta un dato decisivo; None si se puede recomendar."""
    avail = [r for r in rows if r.get("is_available", True)]

    def pns(args: Dict[str, Any]):
        return frozenset(r["base_part_number"] for r in full_matches(avail, args))

    if a.get("voltage_num") is None:
        # combinaciones (voltaje, fase) que EXISTEN en la base dadas las restricciones ya conocidas y que tienen coincidencias
        combos = sorted({
            (int(r["voltage_num"]), r["phase_type"] if r["phase_type"] in ("Single Phase", "3 Phase") else None)
            for r in avail if passes_hard(r, {**a, "voltage_num": r["voltage_num"]})
        }, key=lambda k: (k[0], k[1] or ""))
        opts = []
        for v, ph in combos:
            args = {"voltage_num": v, **({"phase_type": ph} if ph else {})}
            if pns({**a, **args}):
                opts.append(args)
        if len(opts) >= 2:
            return {"topic": "voltage", "options": [{"args": o} for o in opts]}

    wants_service = any(a.get(k) is not None for k in ("min_torque_nm", "min_torque_in_lbs", "min_duty_cycle_pct"))
    if a.get("application_type") is None and wants_service:
        sets = {m: pns({**a, "application_type": m}) for m in ("On/Off", "Modulating")}
        live = [m for m, s in sets.items() if s]
        if len(live) == 2 and sets["On/Off"] != sets["Modulating"]:
            return {"topic": "service", "options": [{"args": {"application_type": m}} for m in live]}

    if a.get("hazardous_area") is None and a.get("enclosure_type") is None:
        wp = pns({**a, "enclosure_type": "Weatherproof"})
        ep = pns({**a, "enclosure_type": "Explosionproof"})
        if wp and ep:
            return {"topic": "hazard", "options": [{"args": {"hazardous_area": True}}, {"args": {"hazardous_area": False}}]}
    return None


# --------------------------------------------------------------------------------------------- argumentos con respaldo
import re  # noqa: E402

_CATEGORICAL_PATTERNS = {
    "application_type": r"on\s*/?\s*-?\s*off|modul",
    "enclosure_type": r"weather|intemperie|exterior|outdoor|explosi|antiexplos|hazard|peligros|atex",
    "safety_factor": r"factor|safety|seguridad|margen|margin",
    "phase_type": r"fase|phase|monof|trif|three|single|\b[13]\s?ph\b|\bdc\b|\bcc\b|corriente continua|ac/dc",
    "require_csa_certification": r"csa",
    "frequency_hz": r"(?<!\d)(?:50|60)\s?hz",
}
_HAZARD_TRUE = r"peligros|hazard|explosi|atex|class\s*i\b|clase\s*i\b|zona|zone"
_HAZARD_FALSE = r"\bno\s+(?:es\s+|est[aá]\s+)?(?:un[ao]?\s+)?(?:[aá]rea\s+|zona\s+)?peligros|non[- ]?hazard|not\s+(?:a\s+)?hazard|safe area|[aá]rea segura"
_NUMERIC_ARGS = ("min_torque_nm", "min_torque_in_lbs", "max_speed_sec", "max_fla_amps", "min_duty_cycle_pct", "voltage_num")


def _norm_user_text(text: str) -> str:
    t = re.sub(r"(?<=\d)[,\u00a0\u202f ](?=\d{3}\b)", "", text.lower())
    return re.sub(r"(?<=\d),(?=\d)", ".", t)


def ground_args(given: Dict[str, Any], user_text: str) -> tuple:
    """Descarta argumentos que el usuario NO dijo (el LLM a veces inventa application_type, hazardous_area, voltaje...).
    user_text = mensajes del usuario de la sesion. Devuelve (argumentos con respaldo, nombres descartados)."""
    if not user_text.strip():
        return dict(given), []
    text = _norm_user_text(user_text)
    kept: Dict[str, Any] = {}
    dropped: List[str] = []
    for k, v in given.items():
        ok = True
        if k in _CATEGORICAL_PATTERNS:
            ok = re.search(_CATEGORICAL_PATTERNS[k], text) is not None
        elif k == "hazardous_area":
            negated = re.search(_HAZARD_FALSE, text) is not None
            ok = negated if not v else (re.search(_HAZARD_TRUE, text) is not None and not negated)
        elif k in _NUMERIC_ARGS:
            num = float(v)
            reprs = {f"{num:g}", str(int(num)) if num.is_integer() else f"{num:g}"}
            ok = any(re.search(rf"(?<![\d.]){re.escape(r)}(?![\d]|\.\d)", text) for r in reprs)
        if ok:
            kept[k] = v
        else:
            dropped.append(k)
    return kept, dropped
