"""Sugerencias de seguimiento deterministas (ui_payload.suggested_followups): {label, query}, maximo 3, es/en.

Se generan segun el intent y las filas del turno; ningun texto ni cifra viene del LLM. El `query` se reenvia tal cual
como siguiente mensaje del usuario, asi que debe ser autocontenido (lleva el numero de parte).
"""
from typing import Any, Dict, List, Optional

from app.database import get_db_cursor
from app.i18n import PHASE_WORD, render_followup, render_rank_text
from app.i18n_acts import RECO_LABEL, RECO_QUERY

MAX_FOLLOWUPS = 3


def _next_size_part(row: Dict[str, Any]) -> Optional[str]:
    """Modelo de la misma alimentacion y carcasa con el torque disponible inmediatamente mayor."""
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT base_part_number FROM actuators
            WHERE is_available AND power_supply = %s AND enclosure_type = %s
              AND COALESCE(on_off_torque_nm, modulating_torque_nm) >
                  COALESCE(%s::numeric, %s::numeric, 0)
            ORDER BY COALESCE(on_off_torque_nm, modulating_torque_nm) ASC, base_part_number ASC
            LIMIT 1;
            """,
            (row["power_supply"], row["enclosure_type"], row.get("on_off_torque_nm"), row.get("modulating_torque_nm")),
        )
        r = cur.fetchone()
    return r["base_part_number"] if r else None


def _has_hz_values(row: Dict[str, Any]) -> bool:
    return row.get("speed_50hz_sec") is not None or row.get("fla_50hz_amps") is not None


def build_followups(
    intent: str,
    ui_payload: Dict[str, Any],
    lang: str,
    recommendation: Optional[Dict[str, Any]] = None,
    asked_hz: Optional[int] = None,
) -> List[Dict[str, str]]:
    rows = ui_payload.get("actuators") or []
    out: List[Dict[str, str]] = []

    def add(key: str, **kw: Any) -> None:
        item = render_followup(key, lang, **kw)
        if item not in out:
            out.append(item)

    if intent == "clarify":
        return []
    if intent == "lookup" and rows:
        row = rows[0]
        pn = row["base_part_number"]
        other = _next_size_part(row)
        if other:
            add("compare_next", pn=pn, other=other)
        if _has_hz_values(row):
            add("hz60" if asked_hz == 50 else "hz50", pn=pn)
        add("same_voltage", pn=pn, voltage=row["voltage_num"])
    elif intent == "recommend" and rows:
        state = recommendation or {}
        relaxed = state.get("relaxed_labels") or []
        for label in relaxed[:2]:
            add("relax", what=label)
        if len(rows) >= 2:
            add("compare_top", pn=rows[0]["base_part_number"], other=rows[1]["base_part_number"])
        if _has_hz_values(rows[0]) and not relaxed:
            add("hz50", pn=rows[0]["base_part_number"])
    elif intent == "recommend":
        # sin modelos (restricciones duras imposibles): ofrecer lo que si existe
        state = recommendation or {}
        if state.get("available_enclosure_voltage"):
            add("hazard_models", voltage=state["available_enclosure_voltage"])
        add("start_recommend")
    elif intent == "knowledge":
        add("ask_certs")
        add("start_recommend")
    elif intent == "error" or not rows:
        add("start_recommend")
    return out[:MAX_FOLLOWUPS]


def relaxed_labels(items: List[Dict[str, Any]], lang: str) -> List[str]:
    return [render_rank_text(c["code"], c.get("params"), lang) for c in items]


def _row_torque(row: Dict[str, Any]) -> Optional[float]:
    vals = [float(v) for v in (row.get("on_off_torque_nm"), row.get("modulating_torque_nm")) if v is not None]
    return min(vals) if vals else None


def _fmt_num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _hard_phrase(args: Dict[str, Any], lang: str) -> str:
    bits: List[str] = []
    if args.get("voltage_num") is not None:
        bits.append((" de " if lang == "es" else " ") + f"{int(args['voltage_num'])}V")
    if args.get("phase_type") in PHASE_WORD:
        bits.append(" " + PHASE_WORD[args["phase_type"]][lang])
    if args.get("hazardous_area") or args.get("enclosure_type") == "Explosionproof":
        bits.append(" Explosionproof")
    elif args.get("enclosure_type") == "Weatherproof":
        bits.append(" Weatherproof")
    return "".join(bits)


def neutral_reco_followups(rows: List[Dict[str, Any]], args: Dict[str, Any], lang: str) -> List[Dict[str, str]]:
    """Recomendación sin criterios blandos: botones «Al menos X Nm» con X tomado de los torques REALES de los modelos mostrados
    (el más bajo, uno intermedio y el más alto) para afinar la elección."""
    vals = [v for v in (_row_torque(r) for r in rows) if v is not None]
    if not vals:
        return []
    vals = sorted(set(vals))
    picks = sorted({vals[0], vals[len(vals) // 2], vals[-1]})
    hard = _hard_phrase(args, lang)
    return [{"label": RECO_LABEL[lang].format(nm=_fmt_num(v)), "query": RECO_QUERY[lang].format(hard=hard, nm=_fmt_num(v))} for v in picks][:MAX_FOLLOWUPS]


def describe_requirements(args: Dict[str, Any], lang: str) -> str:
    """Restricciones duras en una frase corta: «220 V, trifásico, Explosionproof» (vacío si no hay ninguna)."""
    bits: List[str] = []
    if args.get("voltage_num") is not None:
        bits.append(f"{int(args['voltage_num'])} V")
    if args.get("phase_type") in PHASE_WORD:
        bits.append(PHASE_WORD[args["phase_type"]][lang])
    if args.get("hazardous_area") or args.get("enclosure_type") == "Explosionproof":
        bits.append("Explosionproof")
    elif args.get("enclosure_type") == "Weatherproof":
        bits.append("Weatherproof")
    return ", ".join(bits)
