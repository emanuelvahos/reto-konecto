"""Textos (es/en) de los actos conversacionales deterministas: saludo, gracias, capacidades, proyecto, ayuda, fuera de tema,
atributo ausente, contexto de aplicación, aclaraciones de tamaño y recomendación sin criterios blandos.

Sin cifras escritas a mano: {n} (nº de modelos) llega de la base de datos; los textos no citan ningún valor del catálogo.
"""
from typing import Any, Dict

ACT_TEXT: Dict[str, Dict[str, str]] = {
    "greeting": {
        "en": "Hi! I'm the technical assistant for the Series 76 electric actuators: I read the catalog to give you spec sheets, comparisons and recommendations. Where shall we start?",
        "es": "¡Hola! Soy el asistente técnico de los actuadores eléctricos Serie 76: consulto el catálogo para darte fichas, comparaciones y recomendaciones. ¿Por dónde empezamos?",
    },
    "thanks": {
        "en": "You're welcome! If you need another spec sheet, comparison or recommendation, I'm here.",
        "es": "¡Con gusto! Si necesitas otra ficha, comparación o recomendación, aquí sigo.",
    },
    "bye": {
        "en": "Goodbye! Come back whenever you need a Series 76 spec sheet, comparison or recommendation.",
        "es": "¡Hasta luego! Vuelve cuando necesites una ficha, comparación o recomendación de la Serie 76.",
    },
    "capabilities": {
        "en": "I can give you the spec sheet of a model from its part number, compare models, recommend actuators by voltage, torque, hazardous area, service type and other requirements, and explain concepts such as S4 duty, FLA and LRA. I do not have prices, lead times, stock, warranty or other brands.",
        "es": "Puedo darte la ficha de un modelo a partir de su número de parte, comparar modelos, recomendar actuadores según voltaje, torque, zona clasificada, tipo de servicio y otros requisitos, y explicar conceptos como el ciclo S4, FLA y LRA. No tengo precios, plazos de entrega, stock, garantía ni datos de otras marcas.",
    },
    "about_project": {
        "en": "I'm a technical assistant for the Konecto Series 76 heavy-duty electric actuator catalog, with {n} models available. I answer by querying a catalog database, so every figure you see comes from it and not from a language model's memory.",
        "es": "Soy un asistente técnico del catálogo de actuadores eléctricos de servicio pesado Serie 76 de Konecto, con {n} modelos disponibles. Respondo consultando una base de datos del catálogo, así que cada cifra que ves sale de ahí y no de la memoria de un modelo de lenguaje.",
    },
    "about_project_nodb": {
        "en": "I'm a technical assistant for the Konecto Series 76 heavy-duty electric actuator catalog. I answer by querying a catalog database, so every figure you see comes from it and not from a language model's memory.",
        "es": "Soy un asistente técnico del catálogo de actuadores eléctricos de servicio pesado Serie 76 de Konecto. Respondo consultando una base de datos del catálogo, así que cada cifra que ves sale de ahí y no de la memoria de un modelo de lenguaje.",
    },
    "help_question": {
        "en": "Sure, I'll guide you. What would you like to do?",
        "es": "Claro, te guío. ¿Qué quieres hacer?",
    },
    "unclear": {
        "en": "I'm not sure I understood. I can help with spec sheets, comparisons, recommendations and concepts of the Series 76 actuators. What would you like to do?",
        "es": "No estoy seguro de haber entendido. Puedo ayudarte con fichas, comparaciones, recomendaciones y conceptos de los actuadores Serie 76. ¿Qué quieres hacer?",
    },
    "off_topic": {
        "en": "That is outside what I do: I only cover the Series 76 electric actuators. I can give you a spec sheet, compare models or help you choose one.",
        "es": "Eso queda fuera de lo que hago: solo cubro los actuadores eléctricos Serie 76. Puedo darte una ficha, comparar modelos o ayudarte a elegir uno.",
    },
    "attribute": {
        "en": "{what} is not listed in the Series 76 catalog, so I can't confirm it. What I do have: enclosure type (Weatherproof or Explosionproof), certifications (CSA, CE/UKCA, and ATEX/IECEx for Explosionproof), torque, S4 duty, speed, current and motor power.",
        "es": "{what} no figura en el catálogo de la Serie 76, así que no puedo confirmarlo. Lo que sí tengo: tipo de carcasa (Weatherproof o Explosionproof), certificaciones (CSA, CE/UKCA y ATEX/IECEx en Explosionproof), torque, ciclo S4, velocidad, corriente y potencia.",
    },
    "application": {
        "en": "The catalog does not size actuators by valve type, size or pressure: the torque you need is set by the valve manufacturer. Give me that torque in Nm or in-lbs (and whether the service is On/Off or modulating) and I'll propose models that cover it.",
        "es": "El catálogo no dimensiona el actuador por tipo de válvula, tamaño o presión: el par que necesitas lo define el fabricante de la válvula. Dime ese par en Nm o in-lbs (y si el servicio es On/Off o modulante) y te propongo modelos que lo cubran.",
    },
    "ask_criteria": {
        "en": "With only one model there is nothing to weigh it against. Tell me what matters for your application (torque, speed, current draw, enclosure or voltage) or name a second model to compare.",
        "es": "Con un solo modelo no hay contra qué compararlo. Dime qué te importa en tu aplicación (par, velocidad, consumo, carcasa o voltaje) o nombra otro modelo para compararlos.",
    },
    "translate_which": {
        "en": "There is no earlier answer in this conversation to repeat. Ask me something about the Series 76 (a spec sheet, a comparison or a recommendation) and I can answer it in English or Spanish.",
        "es": "Aún no hay una respuesta anterior en esta conversación para repetir. Pregúntame algo de la Serie 76 (una ficha, una comparación o una recomendación) y te respondo en español o en inglés.",
    },
    "clarify_which": {
        "en": "Which model do you mean? Give me its part number (or size code) and I'll answer.",
        "es": "¿De qué modelo hablas? Dame su número de parte (o el código de tamaño) y te respondo.",
    },
    "supply_question": {
        "en": "The {size} comes in several power supplies. Which one do you need?",
        "es": "El {size} existe con varias alimentaciones. ¿Cuál necesitas?",
    },
    "supply_not_offered": {
        "en": "The {size} is not offered with that power supply. These are the ones it does come in:",
        "es": "El {size} no existe con esa alimentación. Estas son las que sí tiene:",
    },
    "reco_neutral": {
        "en": "There are {n} models that meet {req}. I'm showing the first ones from lowest to highest torque, with no ranking because you gave no torque, speed or other soft requirement. Tell me the torque you need to narrow it down.",
        "es": "Hay {n} modelos que cumplen {req}. Te muestro los primeros de menor a mayor torque, sin ranking porque no indicaste torque, velocidad ni otro requisito blando. Dime el par que necesitas para afinar la elección.",
    },
    "reco_neutral_one": {
        "en": "Only one model meets {req}: the one in the card. Tell me the torque you need if you want to confirm it is enough.",
        "es": "Solo hay un modelo que cumple {req}: el de la ficha. Dime el par que necesitas si quieres confirmar que alcanza.",
    },
    "reco_neutral_all": {
        "en": "There are {n} models in the catalog. I'm showing the first ones from lowest to highest torque, with no ranking because you gave no requirement. Tell me the torque you need to narrow it down.",
        "es": "Hay {n} modelos en el catálogo. Te muestro los primeros de menor a mayor torque, sin ranking porque no indicaste ningún requisito. Dime el par que necesitas para afinar la elección.",
    },
}

# Menú de ayuda (4 opciones). {pn}/{other} salen de la base de datos.
HELP_MENU: Dict[str, Dict[str, str]] = {
    "spec": {"label_en": "Spec sheet of a model", "label_es": "Ficha de un modelo", "value_en": "Specs of {pn}", "value_es": "Ficha del {pn}"},
    "compare": {"label_en": "Compare two models", "label_es": "Comparar dos modelos", "value_en": "Compare {pn} with {other}", "value_es": "Compara {pn} con {other}"},
    "recommend": {"label_en": "Recommend an actuator", "label_es": "Recomendar un actuador",
                  "value_en": "Help me select an actuator for my application", "value_es": "Ayúdame a seleccionar un actuador para mi aplicación"},
    "concept": {"label_en": "Explain a concept (S4, FLA, LRA)", "label_es": "Explicar un concepto (S4, FLA, LRA)",
                "value_en": "What is the S4 duty cycle?", "value_es": "¿Qué es el ciclo de trabajo S4?"},
}
HELP_MENU_ORDER = ("spec", "compare", "recommend", "concept")

# Frase de la consulta de recomendación que se arma desde las restricciones duras (para los botones de torque)
RECO_QUERY = {
    "en": "Recommend an actuator{hard} of at least {nm} Nm",
    "es": "Recomiéndame un actuador{hard} de al menos {nm} Nm",
}
RECO_LABEL = {"en": "At least {nm} Nm", "es": "Al menos {nm} Nm"}

NEW_TITLE = {"en": "New query", "es": "Nueva consulta"}
TITLE_MAX = 28   # la app recorta el título a 28 caracteres: el backend lo entrega ya cortado en límite de palabra


def t_act(lang: str, key: str, **kw: Any) -> str:
    e = ACT_TEXT[key]
    return e.get(lang, e["en"]).format(**kw)


def truncate_title(text: str, limit: int = TITLE_MAX) -> str:
    """Título que nunca corta una palabra: límite de palabra + «…»."""
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    cut = clean[: limit - 1]
    if clean[limit - 1] != " " and " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:.-¿¡?!") + "…"
