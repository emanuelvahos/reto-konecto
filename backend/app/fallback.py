"""Respuesta de respaldo determinista (sin LLM): 1-2 frases construidas solo con filas de PostgreSQL.

Mismo estilo que la respuesta del LLM (corta, sin ficha completa: la app muestra la tarjeta). Solo se nombran los grupos
de campos que se preguntaron (focus del lookup o palabras clave de la consulta); por defecto torque y potencia.
"""
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.i18n import t

DEFAULT_GROUPS = ("torque", "power")
_GROUP_KEYWORDS = {
    "torque": r"torque|\bpar\b|\bnm\b|in-?lbs?",
    "duty": r"duty|ciclo|arranque|starts?|cycles?|por hora|per hour",
    "speed": r"speed|velocidad|tiempo|giro|segundos|seconds|\bsec\b|travel",
    "current": r"current|corriente|\bfla\b|\blra\b|amp|consum|draw",
    "power": r"power|potencia|watt|vatio|\bw\b",
}


def infer_groups(query: str, focus: Optional[Sequence[str]] = None) -> List[str]:
    if focus:
        groups = [g for g in focus if g in _GROUP_KEYWORDS]
        if groups:
            return groups
    low = (query or "").lower()
    groups = [g for g, pat in _GROUP_KEYWORDS.items() if re.search(pat, low)]
    return groups or list(DEFAULT_GROUPS)


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


def describe_row(lang: str, row: Dict[str, Any], groups: Sequence[str] = DEFAULT_GROUPS) -> str:
    single = (
        row.get("phase_type") == "3 Phase"
        and row.get("modulating_torque_nm") is None
        and row.get("on_off_torque_nm") is not None
    )
    bits: List[str] = []
    if "torque" in groups:
        if single:
            bits.append(t(lang, "single_torque", nm=_fmt(row["on_off_torque_nm"]), inlbs=_fmt(row["on_off_torque_in_lbs"])))
        elif row.get("on_off_torque_nm") is not None:
            bits.append(t(lang, "onoff_torque", nm=_fmt(row["on_off_torque_nm"]), inlbs=_fmt(row["on_off_torque_in_lbs"])))
        if row.get("modulating_torque_nm") is not None:
            bits.append(t(lang, "mod_torque", nm=_fmt(row["modulating_torque_nm"]), inlbs=_fmt(row["modulating_torque_in_lbs"])))
    if "duty" in groups:
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
    pieces = []
    if "speed" in groups:
        pieces.append(_pair(lang, row, "speed_60hz_sec", "speed_50hz_sec", "speed_dc_or_fixed_sec", "speed", False))
    if "current" in groups:
        pieces.append(_pair(lang, row, "fla_60hz_amps", "fla_50hz_amps", "fla_dc_or_fixed_amps", "fla", True))
        pieces.append(_pair(lang, row, "lra_60hz_amps", "lra_50hz_amps", "lra_dc_or_fixed_amps", "lra", True))
    bits += [p for p in pieces if p]
    if "power" in groups and row.get("motor_power_watts") is not None:
        bits.append(t(lang, "power", w=row["motor_power_watts"]))
    return f"{row['base_part_number']}: " + ", ".join(bits)


KNOWLEDGE_MAX_WORDS = 45


def _knowledge_text(tool_outputs: Iterable[Any], query: str = "") -> Optional[str]:
    """Texto del fragmento de conocimiento recuperado, recortado a las frases que comparten palabras con la pregunta
    (máx. KNOWLEDGE_MAX_WORDS palabras): el fragmento completo puede traer varias definiciones ajenas a lo preguntado."""
    texts: List[str] = []
    for out in tool_outputs:
        if isinstance(out, dict) and out.get("status") == "KNOWLEDGE_RETRIEVED":
            texts += [c["content"] for c in out.get("chunks", [])[:1]]
    if not texts:
        return None
    text = " ".join(texts)
    if len(text.split()) <= KNOWLEDGE_MAX_WORDS:
        return text
    q = {w for w in re.findall(r"[a-záéíóúñ0-9]{2,}", query.lower()) if w not in _STOP and not w.isdigit()}
    sentences = [x.strip() for x in re.split(r"(?<=[.;])\s+", text) if x.strip()]
    merged: List[str] = []
    for x in sentences:                      # frases muy cortas ("1.", títulos) se pegan a la siguiente
        if merged and len(merged[-1].split()) < 4:
            merged[-1] += " " + x
        else:
            merged.append(x)
    sentences = merged
    if not any(q & set(re.findall(r"[a-záéíóúñ0-9]{2,}", x.lower())) for x in sentences):
        return " ".join(text.split()[:KNOWLEDGE_MAX_WORDS]).rstrip(",;:") + "…"      # nada coincide (otro idioma): el comienzo del fragmento
    ranked = sorted(range(len(sentences)), key=lambda i: (-len(q & set(re.findall(r"[a-záéíóúñ0-9]{2,}", sentences[i].lower()))), i))
    chosen, words = [], 0
    for i in ranked:
        n = len(sentences[i].split())
        if chosen and words + n > KNOWLEDGE_MAX_WORDS:
            continue
        if not chosen and n > KNOWLEDGE_MAX_WORDS:
            return " ".join(sentences[i].split()[:KNOWLEDGE_MAX_WORDS]).rstrip(",;:") + "…"
        if q & set(re.findall(r"[a-záéíóúñ0-9]{2,}", sentences[i].lower())) or not chosen:
            chosen.append(i)
            words += n
    out = " ".join(sentences[i] for i in sorted(chosen))
    if len(out.split()) < 6:                 # solo coincidió un título: mejor el comienzo del fragmento
        return " ".join(text.split()[:KNOWLEDGE_MAX_WORDS]).rstrip(",;:") + "…"
    return out


_STOP = {"what", "does", "mean", "for", "the", "these", "this", "that", "is", "are", "of", "qué", "que", "es", "son", "significa",
         "para", "los", "las", "el", "la", "de", "del", "un", "una", "actuators", "actuator", "actuadores", "actuador", "series", "serie"}


def build_fallback_answer(
    lang: str,
    rows: List[Dict[str, Any]],
    alert_messages: List[str],
    tool_outputs: Iterable[Any],
    groups: Optional[Sequence[str]] = None,
    recommend: bool = False,
    query: str = "",
    compare: bool = False,
) -> str:
    groups = tuple(groups or DEFAULT_GROUPS)
    if rows and compare and len(rows) >= 2 and not recommend:   # comparación de números de parte explícitos: una frase por modelo
        q = (query or "").upper()
        ordered = sorted(rows, key=lambda r: q.find(r["base_part_number"]) if r["base_part_number"] in q else 10**6)  # orden de la pregunta
        return " ".join(describe_row(lang, r, groups) + "." for r in ordered[:3])
    if rows:
        sentence = describe_row(lang, rows[0], groups)
        if recommend:
            sentence = t(lang, "best", row=sentence)
        sentence += "."
        if len(rows) > 1:
            sentence += " " + t(lang, "more", n=len(rows) - 1)
        if alert_messages:
            sentence += " " + alert_messages[0]
        return sentence
    kb = _knowledge_text(tool_outputs, query)
    if kb:
        return kb
    if alert_messages:
        return alert_messages[0]
    return t(lang, "unavailable")
