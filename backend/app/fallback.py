"""Respuesta de respaldo determinista (sin LLM) construida solo con filas de PostgreSQL y alertas localizadas."""
from typing import Any, Dict, Iterable, List, Optional

from app.i18n import t

MAX_ROWS = 3


def _fmt(v: Any, amps: bool = False) -> str:
    f = float(v)
    if amps:
        return f"{f:.1f}" if round(f * 10) == f * 10 else f"{f:.2f}".rstrip("0")
    return str(int(f)) if f.is_integer() else f"{f:g}"


def _pair(lang: str, row: Dict[str, Any], c60: str, c50: str, cfix: str, key: str, amps: bool) -> Optional[str]:
    parts: List[str] = []
    for col, k in ((c60, f"{'amps' if amps else 'speed'}_60"), (c50, f"{'amps' if amps else 'speed'}_50")):
        if row.get(col) is not None:
            parts.append(t(lang, k, v=_fmt(row[col], amps)))
    if row.get(cfix) is not None:
        parts.append(t(lang, "amps_fixed" if amps else "speed_fixed", v=_fmt(row[cfix], amps)))
    return t(lang, key, parts=", ".join(parts)) if parts else None


def describe_row(lang: str, row: Dict[str, Any]) -> str:
    single = (
        row.get("phase_type") == "3 Phase"
        and row.get("modulating_torque_nm") is None
        and row.get("on_off_torque_nm") is not None
    )
    bits: List[str] = []
    if single:
        bits.append(t(lang, "single_torque", nm=_fmt(row["on_off_torque_nm"]), inlbs=_fmt(row["on_off_torque_in_lbs"])))
    elif row.get("on_off_torque_nm") is not None:
        bits.append(t(lang, "onoff_torque", nm=_fmt(row["on_off_torque_nm"]), inlbs=_fmt(row["on_off_torque_in_lbs"])))
    if row.get("modulating_torque_nm") is not None:
        bits.append(t(lang, "mod_torque", nm=_fmt(row["modulating_torque_nm"]), inlbs=_fmt(row["modulating_torque_in_lbs"])))
    if row.get("on_off_duty_cycle_pct") is not None:
        s = t(lang, "onoff_duty", pct=row["on_off_duty_cycle_pct"])
        if row.get("cycles_per_hour") is not None:
            s += f", {t(lang, 'cycles', n=row['cycles_per_hour'])}"
        bits.append(s)
    if row.get("modulating_duty_cycle_pct") is not None or row.get("starts_per_hour") is not None:
        s = t(lang, "mod_duty", pct=row["modulating_duty_cycle_pct"]) if row.get("modulating_duty_cycle_pct") is not None else ""
        if row.get("starts_per_hour") is not None:
            s += (", " if s else "") + t(lang, "starts", n=row["starts_per_hour"])
        bits.append(s)
    for piece in (
        _pair(lang, row, "speed_60hz_sec", "speed_50hz_sec", "speed_dc_or_fixed_sec", "speed", False),
        _pair(lang, row, "fla_60hz_amps", "fla_50hz_amps", "fla_dc_or_fixed_amps", "fla", True),
        _pair(lang, row, "lra_60hz_amps", "lra_50hz_amps", "lra_dc_or_fixed_amps", "lra", True),
    ):
        if piece:
            bits.append(piece)
    if row.get("motor_power_watts") is not None:
        bits.append(t(lang, "power", w=row["motor_power_watts"]))
    return f"{row['base_part_number']} ({row['power_supply']}, {row['enclosure_type']}): " + "; ".join(bits) + "."


def _knowledge_text(tool_outputs: Iterable[Any]) -> Optional[str]:
    texts: List[str] = []
    for out in tool_outputs:
        if isinstance(out, dict) and out.get("status") == "KNOWLEDGE_RETRIEVED":
            texts += [f"{c['title']}: {c['content']}" for c in out.get("chunks", [])]
    return "\n".join(texts) if texts else None


def build_fallback_answer(
    lang: str,
    rows: List[Dict[str, Any]],
    alert_messages: List[str],
    tool_outputs: Iterable[Any],
) -> str:
    if rows:
        lines = [t(lang, "header")] + [describe_row(lang, r) for r in rows[:MAX_ROWS]]
        if len(rows) > MAX_ROWS:
            lines.append(t(lang, "more", n=len(rows) - MAX_ROWS))
        lines += alert_messages
        return "\n".join(lines)
    kb = _knowledge_text(tool_outputs)
    if kb:
        return kb
    if alert_messages:
        return "\n".join(alert_messages)
    return t(lang, "unavailable")
