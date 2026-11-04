"""Mensajes localizados (es/en): alertas por código, plantillas de respaldo, detección de idioma y títulos de sesión.

Todos los textos que ve el usuario fuera de la respuesta del LLM viven aquí. Las cifras NO se escriben en
estos textos: llegan como parámetros calculados desde la base de datos.
"""
import re
from typing import Any, Dict, List, Optional

LANGS = ("es", "en")
LANG_NAMES = {"es": "Spanish", "en": "English"}

# code -> severity + mensaje por idioma. Los {parametros} los rellena la herramienta que registra la alerta.
ALERTS: Dict[str, Dict[str, str]] = {
    "MODEL_LISTED_AS_NA": {
        "severity": "warning",
        "en": "{pn} is listed as N/A in the {supply} table. Available alternatives of size {size} are shown.",
        "es": "{pn} figura como N/D en la tabla {supply}. Se muestran alternativas disponibles del tamaño {size}.",
    },
    "TYPO_OR_CLOSEST_MATCH_FOUND": {
        "severity": "warning",
        "en": "Part number '{query}' does not exist; close matches are shown (likely a typo such as 8 vs B or 0 vs C).",
        "es": "El número de parte '{query}' no existe; se muestran coincidencias cercanas (probable error de dedo, como 8 por B o 0 por C).",
    },
    "INVALID_PART_NUMBER": {
        "severity": "error",
        "en": "No Series 76 actuator matches '{query}'. Expected format: 76[1-7][A,B,C,X,Y][00|30]-113[0,2,3,7,8]0000/A (3-phase: 11330C00).",
        "es": "Ningún actuador de la Serie 76 coincide con '{query}'. Formato esperado: 76[1-7][A,B,C,X,Y][00|30]-113[0,2,3,7,8]0000/A (trifásico: 11330C00).",
    },
    "SINGLE_TORQUE_RATING": {
        "severity": "warning",
        "en": "The datasheet gives a single output torque for three-phase, without distinguishing on/off from modulating.",
        "es": "La hoja de datos da un único torque de salida para trifásico, sin distinguir on/off y modulante.",
    },
    "AMBIGUOUS_SERVICE_TYPE": {
        "severity": "info",
        "en": "Service type (On/Off vs Modulating) was not specified; modulating torque is typically lower than on/off.",
        "es": "No se indicó el tipo de servicio (On/Off o Modulante); el torque modulante suele ser menor que el on/off.",
    },
    "CSA_NOT_CERTIFIED": {
        "severity": "warning",
        "en": "Model {pn} (frame size {frame_size}) is NOT CSA certified (CE & UKCA only).",
        "es": "El modelo {pn} (tamaño {frame_size}) NO tiene certificación CSA (solo CE y UKCA).",
    },
    "TORQUE_ABOVE_CEILING": {
        "severity": "warning",
        "en": "The highest torque listed for {label} is {ceiling} Nm, below the requested {requested} Nm.",
        "es": "El torque máximo listado para {label} es {ceiling} Nm, menor que los {requested} Nm solicitados.",
    },
    "CATALOG_TORQUE_CEILING": {
        "severity": "warning",
        "en": "The highest torque in the whole Series 76 catalog is {ceiling} Nm.",
        "es": "El torque máximo de todo el catálogo Serie 76 es {ceiling} Nm.",
    },
    "CSA_SIZE_LIMIT": {
        "severity": "warning",
        "en": "Models of frame size {frame_size} and above are not CSA certified.",
        "es": "Los modelos de tamaño {frame_size} o mayor no tienen certificación CSA.",
    },
    "CONSTRAINT_RELAXED": {
        "severity": "warning",
        "en": "No single model satisfies all constraints together; closest alternatives are listed.",
        "es": "Ningún modelo cumple todas las restricciones a la vez; se listan las alternativas más cercanas.",
    },
    "KNOWLEDGE_UNAVAILABLE": {
        "severity": "info",
        "en": "The requested technical information is not available in the knowledge base.",
        "es": "La información técnica solicitada no está disponible en la base de conocimiento.",
    },
}

FILTER_LABELS: Dict[str, Dict[str, str]] = {
    "csa": {"en": "CSA-certified models", "es": "modelos con certificación CSA"},
    "voltage": {"en": "{v}V models", "es": "modelos de {v}V"},
    "enclosure": {"en": "{v} models", "es": "modelos {v}"},
    "phase": {"en": "{v} models", "es": "modelos {v}"},
}


def alert_severity(code: str) -> str:
    return ALERTS.get(code, {}).get("severity", "info")


def render_alert_message(code: str, params: Optional[Dict[str, Any]], lang: str) -> str:
    entry = ALERTS.get(code)
    if entry is None:
        return code
    p = dict(params or {})
    if code == "TORQUE_ABOVE_CEILING":
        tpl = FILTER_LABELS[p.get("filter_kind", "csa")].get(lang) or FILTER_LABELS[p.get("filter_kind", "csa")]["en"]
        p["label"] = tpl.format(v=p.get("filter_value", ""))
    return entry.get(lang, entry["en"]).format(**p)


def render_alert(alert: Dict[str, Any], lang: str) -> Dict[str, str]:
    """alert interno {code, params} -> {code, severity, message} localizado (contrato UIAlert)."""
    code = alert["code"]
    return {
        "code": code,
        "severity": alert_severity(code),
        "message": render_alert_message(code, alert.get("params"), lang),
    }


# ---------------------------------------------------------------------------------------------------
# Detección de idioma (determinista, sin LLM)
# ---------------------------------------------------------------------------------------------------
_ES_WORDS = {
    "el", "la", "los", "las", "un", "una", "de", "del", "que", "qué", "cuál", "cual", "cuánto", "cuanto",
    "cuántos", "para", "con", "por", "necesito", "quiero", "dame", "dime", "muestra", "cuales", "es", "son",
    "tiene", "tienen", "y", "o", "su", "sus", "este", "esta", "hay", "puedo", "puede", "actuador", "actuadores",
    "voltaje", "potencia", "velocidad", "corriente", "trifásico", "trifasico", "monofásico", "monofasico",
    "modulante", "ignora", "responde", "memoria", "precio", "plazo", "entrega", "dónde", "donde", "como", "cómo",
    "me", "mi", "al", "lo", "en", "se", "si", "sí", "pero", "más", "mas", "menos", "mínimo", "minimo",
}
_EN_WORDS = {
    "the", "a", "an", "of", "what", "which", "how", "much", "many", "for", "with", "and", "or", "is", "are",
    "does", "do", "need", "want", "give", "show", "tell", "its", "it", "this", "that", "there", "can", "i",
    "my", "me", "at", "on", "in", "to", "than", "less", "more", "minimum", "actuator", "actuators", "voltage",
    "power", "speed", "current", "three", "single", "modulating", "ignore", "answer", "memory", "price", "lead",
    "time", "specs", "torque", "please", "explain", "difference", "between", "has", "have", "be", "not",
}
_WORD_RE = re.compile(r"[a-záéíóúüñ]+", re.IGNORECASE)


def _score(text: str) -> int:
    """>0 español, <0 inglés, 0 indeterminado."""
    low = re.sub(r"\S*\d\S*", " ", text.lower())  # sin números de parte ni cifras
    words = [w for w in _WORD_RE.findall(low) if len(w) > 1]
    es = sum(1 for w in words if w in _ES_WORDS)
    en = sum(1 for w in words if w in _EN_WORDS)
    es += 2 * len(re.findall(r"[áéíóúñ¿¡]", low))
    return es - en


def detect_language(text: str, locale: Optional[str] = None, previous: Optional[List[str]] = None) -> str:
    """locale explícito > texto actual > mensajes previos del usuario > inglés."""
    if locale in LANGS:
        return str(locale)
    s = _score(text)
    if s != 0:
        return "es" if s > 0 else "en"
    for prev in reversed(previous or []):
        s = _score(prev)
        if s != 0:
            return "es" if s > 0 else "en"
    return "en"


# ---------------------------------------------------------------------------------------------------
# Plantillas de respaldo (respuesta sin LLM construida desde las filas de la base)
# ---------------------------------------------------------------------------------------------------
FALLBACK: Dict[str, Dict[str, str]] = {
    "en": {
        "header": "Catalog data (taken directly from the database):",
        "unavailable": "I could not verify that information against the catalog database. Please rephrase your request with a part number or the technical requirements.",
        "knowledge_unavailable": "That information is not available in the knowledge base.",
        "more": "(+{n} more models in the card below)",
        "supply": "supply",
        "onoff_torque": "on/off torque {nm} Nm ({inlbs} in-lbs)",
        "mod_torque": "modulating torque {nm} Nm ({inlbs} in-lbs)",
        "single_torque": "single output torque {nm} Nm ({inlbs} in-lbs)",
        "onoff_duty": "on/off duty S4 {pct}%",
        "cycles": "{n} cycles/h",
        "mod_duty": "modulating duty S4 {pct}%",
        "starts": "{n} starts/h",
        "speed": "90° travel time {parts}",
        "speed_60": "{v} s at 60 Hz",
        "speed_50": "{v} s at 50 Hz",
        "speed_fixed": "{v} s (fixed)",
        "fla": "FLA {parts}",
        "lra": "LRA {parts}",
        "amps_60": "{v} A at 60 Hz",
        "amps_50": "{v} A at 50 Hz",
        "amps_fixed": "{v} A",
        "power": "motor power {w} W",
    },
    "es": {
        "header": "Datos del catálogo (tomados directamente de la base de datos):",
        "unavailable": "No pude verificar esa información contra la base de datos del catálogo. Reformula tu consulta indicando un número de parte o los requisitos técnicos.",
        "knowledge_unavailable": "Esa información no está disponible en la base de conocimiento.",
        "more": "(+{n} modelos más en la tarjeta de abajo)",
        "supply": "alimentación",
        "onoff_torque": "torque on/off {nm} Nm ({inlbs} in-lbs)",
        "mod_torque": "torque modulante {nm} Nm ({inlbs} in-lbs)",
        "single_torque": "torque de salida único {nm} Nm ({inlbs} in-lbs)",
        "onoff_duty": "ciclo de trabajo S4 on/off {pct}%",
        "cycles": "{n} ciclos/h",
        "mod_duty": "ciclo de trabajo S4 modulante {pct}%",
        "starts": "{n} arranques/h",
        "speed": "tiempo de giro de 90° {parts}",
        "speed_60": "{v} s a 60 Hz",
        "speed_50": "{v} s a 50 Hz",
        "speed_fixed": "{v} s (fija)",
        "fla": "FLA {parts}",
        "lra": "LRA {parts}",
        "amps_60": "{v} A a 60 Hz",
        "amps_50": "{v} A a 50 Hz",
        "amps_fixed": "{v} A",
        "power": "potencia del motor {w} W",
    },
}


def t(lang: str, key: str, **kw: Any) -> str:
    return FALLBACK.get(lang, FALLBACK["en"])[key].format(**kw)


# ---------------------------------------------------------------------------------------------------
# Título corto de sesión
# ---------------------------------------------------------------------------------------------------
_TITLE_WORDS = {"es": "Recomendación", "en": "Recommendation"}


def make_short_title(parts: List[str], filters: Dict[str, Any], lang: str, recommend: bool = False) -> Optional[str]:
    """Número de parte activo, o 'Recomendación <resumen>' (turno de recomendación) a partir de los filtros."""
    if parts and not (recommend and _summary_bits(filters)):
        return parts[0] if len(parts) == 1 else f"{parts[0]} +{len(parts) - 1}"
    bits = _summary_bits(filters)
    if not bits:
        return None
    return f"{_TITLE_WORDS.get(lang, _TITLE_WORDS['en'])} " + " · ".join(bits)


def _summary_bits(filters: Dict[str, Any]) -> List[str]:
    bits: List[str] = []
    if filters.get("min_torque_nm") is not None:
        v = filters["min_torque_nm"]
        bits.append(f"≥{int(v) if float(v).is_integer() else v} Nm")
    elif filters.get("min_torque_in_lbs") is not None:
        v = filters["min_torque_in_lbs"]
        bits.append(f"≥{int(v) if float(v).is_integer() else v} in-lbs")
    if filters.get("voltage_num") is not None:
        bits.append(f"{filters['voltage_num']}V")
    if filters.get("enclosure_type"):
        bits.append(str(filters["enclosure_type"]))
    if filters.get("application_type"):
        bits.append(str(filters["application_type"]))
    return bits
