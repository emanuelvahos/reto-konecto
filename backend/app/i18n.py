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
    "VOLTAGE_ENCLOSURE_UNAVAILABLE": {
        "severity": "warning",
        "en": "There are no {voltage}V {enclosure} models in Series 76; {voltage}V is only offered as {available}.",
        "es": "No existen modelos de {voltage}V {enclosure} en la Serie 76; {voltage}V solo se ofrece como {available}.",
    },
    "HAZARDOUS_NEEDS_EXPLOSIONPROOF": {
        "severity": "warning",
        "en": "A hazardous area requires Explosionproof; Weatherproof models cannot be used there.",
        "es": "Un área peligrosa exige Explosionproof; los modelos Weatherproof no se pueden usar allí.",
    },
    "HARD_CONSTRAINTS_UNSATISFIABLE": {
        "severity": "warning",
        "en": "No Series 76 model meets the required voltage, enclosure and phase together.",
        "es": "Ningún modelo de la Serie 76 cumple a la vez el voltaje, la carcasa y la fase requeridos.",
    },
    "DC_NO_FREQUENCY": {
        "severity": "info",
        "en": "24V models are DC/AC-DC with a fixed speed and current: they have no separate 50 Hz / 60 Hz values.",
        "es": "Los modelos de 24V son DC/AC-DC con velocidad y corriente fijas: no tienen valores separados a 50 Hz / 60 Hz.",
    },
    "OUT_OF_SCOPE": {
        "severity": "info",
        "en": "Outside the technical catalog: prices, lead times, stock, warranty and other brands are not available here.",
        "es": "Fuera del catálogo técnico: aquí no hay precios, plazos de entrega, stock, garantía ni otras marcas.",
    },
    "LLM_UNAVAILABLE": {
        "severity": "error",
        "en": "The language model is temporarily unavailable. Please try again in a moment.",
        "es": "El modelo de lenguaje no está disponible temporalmente. Inténtalo de nuevo en un momento.",
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
# Respuestas deterministas del router (fuera de alcance / inyección); sin cifras
# ---------------------------------------------------------------------------------------------------
ROUTER_TEXT: Dict[str, Dict[str, str]] = {
    "out_of_scope": {
        "en": "That is not in the technical catalog: I have no prices, lead times, stock, warranty or other brands. I can help with specifications, selection and technical rules.",
        "es": "Eso no está en el catálogo técnico: no tengo precios, plazos de entrega, stock, garantía ni otras marcas. Puedo ayudarte con especificaciones, selección y reglas técnicas.",
    },
    "injection": {
        "en": "I can't skip my rules or share my instructions: every figure I give comes from the technical catalog. Ask me about a part number or your requirements.",
        "es": "No puedo saltarme mis reglas ni mostrar mis instrucciones: cada cifra que doy sale del catálogo técnico. Pregúntame por un número de parte o por tus requisitos.",
    },
    "oos_note": {
        "en": "Prices, lead times and stock are not in the technical catalog.",
        "es": "Los precios, plazos de entrega y stock no están en el catálogo técnico.",
    },
}


def t_router(lang: str, key: str) -> str:
    return ROUTER_TEXT[key].get(lang, ROUTER_TEXT[key]["en"])


# ---------------------------------------------------------------------------------------------------
# Recomendación: restricciones duras, why / why_not y restricciones relajadas (las cifras llegan como parámetros)
# ---------------------------------------------------------------------------------------------------
KIND = {
    "onoff": {"en": "on/off", "es": "on/off"},
    "mod": {"en": "modulating", "es": "modulante"},
    "single": {"en": "single-rating", "es": "de valor único"},
}
ENCLOSURE_NAMES = {
    "Weatherproof": {"en": "Weatherproof", "es": "Weatherproof (intemperie)"},
    "Explosionproof": {"en": "Explosionproof", "es": "Explosionproof (antiexplosión)"},
}
RANK_TEXT: Dict[str, Dict[str, str]] = {
    "HC_HAZARDOUS": {"en": "Hazardous area: Explosionproof only", "es": "Área peligrosa: solo Explosionproof"},
    "HC_VOLTAGE": {"en": "Voltage {v} V", "es": "Voltaje {v} V"},
    "HC_ENCLOSURE": {"en": "{v} enclosure", "es": "Carcasa {v}"},
    "HC_PHASE": {"en": "Phase: {v}", "es": "Fase: {v}"},
    "RC_TORQUE": {"en": "Minimum torque {required} {unit}", "es": "Torque mínimo {required} {unit}"},
    "RC_DUTY": {"en": "Minimum duty cycle S4 {required}%", "es": "Ciclo de trabajo S4 mínimo {required}%"},
    "RC_SPEED": {"en": "Maximum 90° travel time {required} s", "es": "Tiempo de giro de 90° máximo {required} s"},
    "RC_FLA": {"en": "Maximum FLA {required} A", "es": "FLA máxima {required} A"},
    "RC_CSA": {"en": "CSA certification", "es": "Certificación CSA"},
    "W_TORQUE_MET": {
        "en": "{kind} torque {actual} {unit} vs {required} {unit} required (+{margin_pct}%)",
        "es": "Torque {kind} {actual} {unit} frente a {required} {unit} requeridos (+{margin_pct}%)",
    },
    "W_DUTY_MET": {"en": "Duty S4 {actual}% vs {required}% required", "es": "Ciclo S4 {actual}% frente a {required}% requerido"},
    "W_SPEED_MET": {"en": "90° travel {actual} s{hz} vs {required} s maximum", "es": "Giro de 90° en {actual} s{hz} frente a {required} s máximo"},
    "W_FLA_MET": {"en": "FLA {actual} A{hz} vs {required} A maximum", "es": "FLA {actual} A{hz} frente a {required} A máximo"},
    "W_CSA_OK": {"en": "CSA certified", "es": "Certificado CSA"},
    "W_LEAST_OVERSIZED": {"en": "Smallest model that meets every requirement", "es": "El modelo más pequeño que cumple todos los requisitos"},
    "N_TORQUE_SHORT": {
        "en": "{kind} torque {actual} {unit} is {shortfall_pct}% below the {required} {unit} required",
        "es": "Torque {kind} {actual} {unit}: {shortfall_pct}% por debajo de los {required} {unit} requeridos",
    },
    "N_TORQUE_NO_RATING": {"en": "The datasheet gives no {kind} torque for this model", "es": "La hoja de datos no da torque {kind} para este modelo"},
    "N_DUTY_SHORT": {"en": "Duty S4 {actual}% is {shortfall_pct}% below the {required}% required", "es": "Ciclo S4 {actual}%: {shortfall_pct}% por debajo del {required}% requerido"},
    "N_DUTY_NO_RATING": {"en": "The datasheet gives no duty cycle for this service", "es": "La hoja de datos no da ciclo de trabajo para este servicio"},
    "N_SPEED_SHORT": {"en": "90° travel {actual} s{hz} is {shortfall_pct}% slower than the {required} s limit", "es": "Giro de 90° en {actual} s{hz}: {shortfall_pct}% más lento que el límite de {required} s"},
    "N_SPEED_NO_RATING": {"en": "The datasheet gives no travel time for this model", "es": "La hoja de datos no da tiempo de giro para este modelo"},
    "N_FLA_SHORT": {"en": "FLA {actual} A{hz} is {shortfall_pct}% above the {required} A limit", "es": "FLA {actual} A{hz}: {shortfall_pct}% por encima del límite de {required} A"},
    "N_FLA_NO_RATING": {"en": "The datasheet gives no FLA for this model", "es": "La hoja de datos no da FLA para este modelo"},
    "N_CSA_NO": {"en": "Not CSA certified (frame size {frame_size})", "es": "Sin certificación CSA (tamaño {frame_size})"},
    "N_OVERSIZED": {"en": "Torque is {margin_pct}% above the requirement", "es": "El torque supera el requisito en {margin_pct}%"},
}
_HZ = {"en": " at {hz} Hz", "es": " a {hz} Hz"}


def render_rank_text(code: str, params: Optional[Dict[str, Any]], lang: str) -> str:
    entry = RANK_TEXT.get(code)
    if entry is None:
        return code
    p = dict(params or {})
    if "hz" in p:
        p["hz"] = _HZ.get(lang, _HZ["en"]).format(hz=p["hz"]) if p["hz"] else ""
    if p.get("kind") in KIND:
        word = KIND[p["kind"]].get(lang, KIND[p["kind"]]["en"])
        p["kind"] = word[:1].upper() + word[1:] if lang == "en" and code != "N_TORQUE_NO_RATING" else word
    if code == "HC_ENCLOSURE" and p.get("v") in ENCLOSURE_NAMES:
        p["v"] = ENCLOSURE_NAMES[p["v"]].get(lang, p["v"])
    return entry.get(lang, entry["en"]).format(**p)


# ---------------------------------------------------------------------------------------------------
# Aclaración: una pregunta con 2-4 opciones. El `value` de cada opción se reenvía tal cual como siguiente mensaje.
# ---------------------------------------------------------------------------------------------------
CLARIFY: Dict[str, Dict[str, Any]] = {
    "voltage": {
        "question": {"en": "Which supply voltage does the actuator need?", "es": "¿Qué voltaje de alimentación necesita el actuador?"},
    },
    "service": {
        "question": {"en": "Which type of service will it run?", "es": "¿Qué tipo de servicio realizará?"},
        "options": {
            "On/Off": {"label": {"en": "On/Off", "es": "On/Off"}, "value": {"en": "On/Off service", "es": "Servicio On/Off"}},
            "Modulating": {"label": {"en": "Modulating", "es": "Modulante"}, "value": {"en": "Modulating service", "es": "Servicio modulante"}},
        },
    },
    "hazard": {
        "question": {"en": "Will it be installed in a hazardous (explosive) area?", "es": "¿Se instalará en un área peligrosa (explosiva)?"},
        "options": {
            True: {"label": {"en": "Hazardous area", "es": "Área peligrosa"}, "value": {"en": "Hazardous area (Explosionproof)", "es": "Área peligrosa (Explosionproof)"}},
            False: {"label": {"en": "Non-hazardous area", "es": "Área no peligrosa"}, "value": {"en": "Non-hazardous area", "es": "Área no peligrosa"}},
        },
    },
}


def render_clarification(topic: str, options: List[Dict[str, Any]], lang: str) -> Dict[str, Any]:
    """options: [{"args": {...}}] -> {"question", "options": [{"label", "value"}]} localizado."""
    spec = CLARIFY[topic]
    out: List[Dict[str, str]] = []
    for o in options:
        args = o["args"]
        if topic == "voltage":
            v = args["voltage_num"]
            out.append({"label": f"{v} V", "value": f"{v}V"})
        elif topic == "service":
            e = spec["options"][args["application_type"]]
            out.append({"label": e["label"][lang], "value": e["value"][lang]})
        else:
            e = spec["options"][bool(args["hazardous_area"])]
            out.append({"label": e["label"][lang], "value": e["value"][lang]})
    return {"question": spec["question"].get(lang, spec["question"]["en"]), "options": out}


def resolve_clarification_answer(topic: str, text: str) -> Dict[str, Any]:
    """Respuesta del usuario (el `value` de una opción u otra forma natural) -> argumentos; {} si no se reconoce."""
    low = text.lower()
    if topic == "voltage":
        m = re.search(r"(?<!\d)(24|110|220)(?!\d)", low)
        return {"voltage_num": int(m.group(1))} if m else {}
    if topic == "service":
        if re.search(r"modul", low):
            return {"application_type": "Modulating"}
        if re.search(r"on\s*/?\s*off", low):
            return {"application_type": "On/Off"}
        return {}
    if re.search(r"non[- ]?hazard|no[- ]?peligros|no es peligros|weatherproof|intemperie", low):
        return {"hazardous_area": False}
    if re.search(r"peligros|hazard|explosi", low):
        return {"hazardous_area": True}
    return {}


# ---------------------------------------------------------------------------------------------------
# Sugerencias de seguimiento (label visible + query que se reenvía como mensaje)
# ---------------------------------------------------------------------------------------------------
FOLLOWUPS: Dict[str, Dict[str, str]] = {
    "compare_next": {
        "label_en": "Compare with the next size", "label_es": "Compara con el tamaño siguiente",
        "query_en": "Compare {pn} with {other}", "query_es": "Compara {pn} con {other}",
    },
    "hz50": {
        "label_en": "Show 50 Hz values", "label_es": "Ver valores a 50 Hz",
        "query_en": "What are the 50 Hz values of {pn}?", "query_es": "¿Cuáles son los valores a 50 Hz del {pn}?",
    },
    "hz60": {
        "label_en": "Show 60 Hz values", "label_es": "Ver valores a 60 Hz",
        "query_en": "What are the 60 Hz values of {pn}?", "query_es": "¿Cuáles son los valores a 60 Hz del {pn}?",
    },
    "same_voltage": {
        "label_en": "Alternatives with the same voltage", "label_es": "Alternativas del mismo voltaje",
        "query_en": "Show alternatives to {pn} with the same voltage ({voltage}V)",
        "query_es": "Muestra alternativas al {pn} con el mismo voltaje ({voltage}V)",
    },
    "compare_top": {
        "label_en": "Compare the top 2", "label_es": "Compara las 2 primeras",
        "query_en": "Compare {pn} with {other}", "query_es": "Compara {pn} con {other}",
    },
    "relax": {
        "label_en": "Relax: {what}", "label_es": "Relajar: {what}",
        "query_en": "Relax the requirement \"{what}\" and recommend again",
        "query_es": "Relaja el requisito \"{what}\" y recomienda de nuevo",
    },
    "hazard_models": {
        "label_en": "Explosionproof models", "label_es": "Modelos Explosionproof",
        "query_en": "Show the Explosionproof models available at {voltage}V",
        "query_es": "Muestra los modelos Explosionproof disponibles de {voltage}V",
    },
    "start_recommend": {
        "label_en": "Recommend an actuator", "label_es": "Recomendar un actuador",
        "query_en": "Help me select an actuator for my application", "query_es": "Ayúdame a seleccionar un actuador para mi aplicación",
    },
    "ask_certs": {
        "label_en": "Hazardous-area certifications", "label_es": "Certificaciones de área peligrosa",
        "query_en": "What hazardous area certifications do Explosionproof models have?",
        "query_es": "¿Qué certificaciones de área peligrosa tienen los modelos Explosionproof?",
    },
}


def render_followup(key: str, lang: str, **kw: Any) -> Dict[str, str]:
    f = FOLLOWUPS[key]
    return {"label": f[f"label_{lang}"].format(**kw), "query": f[f"query_{lang}"].format(**kw)}


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
        "more": "(+{n} more in the card)",
        "best": "Best match: {row}",
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
        "more": "(+{n} más en la ficha)",
        "best": "Mejor opción: {row}",
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
