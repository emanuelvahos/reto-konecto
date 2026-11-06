"""Actos conversacionales deterministas (sin LLM, sin herramientas de catálogo).

Primero se identifica el ACTO del usuario y luego se ejecuta el camino de ese acto. Aquí viven los actos seguros y frecuentes:
greeting, thanks (+ despedida), capabilities, about_project, help_request, off_topic, out_of_catalog_attribute y
application_context, más la resolución de referencias de tamaño («763B00», «763 b 00 de 110 voltios») contra la base.

Los patrones corren sobre el texto en minúsculas y sin tildes. Las listas (atributos que el catálogo no trae, temas ajenos,
palabras de aplicación) viven en config/conversation.json. Los textos están en app/i18n_acts.py (es/en). Estas respuestas
no modifican filtros ni partes activas, no usan herramientas y no llevan cifras salvo el nº de modelos, que sale de la base.
"""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.database import get_db_cursor
from app.i18n import PHASE_WORD, render_followup
from app.i18n_acts import HELP_MENU, HELP_MENU_ORDER, NEW_TITLE, t_act, truncate_title

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "conversation.json"
FLAGS = re.IGNORECASE | re.UNICODE
MAX_CONVERSATIONAL_WORDS = 28   # un mensaje más largo no es un acto conversacional simple


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def load_config() -> Dict[str, Any]:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["_attributes"] = [(a["key"], re.compile(a["pattern"], FLAGS), a["label"]) for a in cfg["attributes"]]
    cfg["_off_topic"] = [re.compile(p, FLAGS) for p in cfg["off_topic"]]
    cfg["_application"] = re.compile(cfg["application"], FLAGS)
    return cfg


# --------------------------------------------------------------------------------------------- patrones de actos
_GREETING = re.compile(
    r"^(?:hola+|hello|hi|hey|howdy|sup|wass?up|what['’]?s up|whats up|buen[oa]s?(?:\s+(?:dias|tardes|noches))?|good\s+(?:morning|afternoon|evening)|saludos|que tal|ola)\b"
    r"[\s,!.¡¿?]*(?:(?:amigo|amiga|ingeniero|ingeniera|ing|asistente|there|bot|friend|a todos|que tal|como estas|como andas|como te va|"
    r"how are you|how's it going|what's up|todo bien)[\s,!.¡¿?]*)*$", FLAGS)
_BYE = re.compile(r"\b(?:adios|chao|chau|hasta luego|hasta pronto|nos vemos|bye|goodbye|see you|eso es todo|that'?s all|that is all)\b", FLAGS)
_THANKS = re.compile(r"\b(?:gracias|thanks|thank you|thx|te lo agradezco|muy amable)\b", FLAGS)
_CAP_HELP_Q = re.compile(r"\b(?:en|con) que (?:me )?(?:puedes|podrias|sabes) ayud\w*|\bhow can you help|\bwhat can you help", FLAGS)
_HELP = re.compile(
    r"\bgu[i]a(?:me|rme|rnos)?\b|\bayuda(?:me|rme)?\b|\bnecesito ayuda\b|\bhelp me\b|\bguide me\b|\bcan you guide\b|\bi need (?:some )?help\b|"
    r"\bpor donde (?:empiezo|empezar|comienzo|comenzar)\b|\bno se por donde\b|\bwhere (?:do i|to) start\b", FLAGS)
_ABOUT = re.compile(
    r"\bde que (?:trata|va|se trata)\b|\bquien eres\b|\bque eres\b|\bwho are you\b|\bwhat are you\b|\bwhat is this(?: (?:app|project|assistant|bot|thing))?\b|"
    r"\bque es (?:esto|este proyecto|esta app|esta aplicacion|este asistente)\b|\ba que te dedicas\b|\btell me about (?:this|yourself|you)\b|"
    r"\bacerca de (?:este|ti)\b|\bsobre (?:este proyecto|ti)\b|\bwho (?:made|built|created) you\b|\bthis project\b|\beste proyecto\b", FLAGS)
_CAPS = re.compile(
    r"\bque (?:puedes|sabes|podrias) (?:hacer|ofrecer)\b|\bque sabes\b|\bpara que sirves\b|"
    r"\bque (?:datos|informacion|cosas|tipo de (?:preguntas|consultas)) (?:manejas|tienes|conoces|puedo|te puedo)\b|"
    r"\bwhat (?:can|do) you (?:do|know|offer)\b|\bwhat kind of (?:questions|things|data)\b|\bwhat (?:data|information) do you\b|"
    r"\bhow do you work\b|\bcomo funcionas\b|\bwhat puedes\b|\bque haces\b", FLAGS)


def detect_conversational(text: str) -> Optional[str]:
    """greeting | thanks | bye | capabilities | about_project | help_request | off_topic, o None. Solo se llama cuando el
    mensaje NO tiene contenido técnico (parte, criterios, verbos de selección...)."""
    t = norm(text).strip()
    if not t or len(t.split()) > MAX_CONVERSATIONAL_WORDS:
        return None
    if _GREETING.match(t):
        return "greeting"
    if any(rx.search(t) for rx in load_config()["_off_topic"]):
        return "off_topic"
    if _BYE.search(t):
        return "bye"
    if _THANKS.search(t) and len(t.split()) <= 8:
        return "thanks"
    if _CAP_HELP_Q.search(t):
        return "capabilities"
    if _HELP.search(t):
        return "help_request"
    if _ABOUT.search(t):
        return "about_project"
    if _CAPS.search(t):
        return "capabilities"
    return None


def detect_attribute(text: str) -> Optional[Dict[str, str]]:
    """Atributo que el catálogo no trae (peso, dimensiones, material, IP...): devuelve su etiqueta {es, en}."""
    t = norm(text)
    for _key, rx, label in load_config()["_attributes"]:
        if rx.search(t):
            return label
    return None


def is_application_context(text: str) -> bool:
    return bool(load_config()["_application"].search(norm(text)))


def is_conversational_only(text: str) -> bool:
    """Para el título de sesión: saludos, gracias, capacidades... no son una consulta técnica."""
    return detect_conversational(text) is not None


# --------------------------------------------------------------------------------------------- datos de la base
def catalog_counts() -> Optional[Dict[str, int]]:
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_available) AS available FROM actuators;")
            r = cur.fetchone()
        return {"total": int(r["total"]), "available": int(r["available"])}
    except Exception:  # noqa: BLE001  (base caída: el texto se entrega sin el conteo)
        return None


def sample_models() -> Optional[Tuple[str, Optional[str]]]:
    """Un modelo real del catálogo y el siguiente tamaño de la misma alimentación, para los botones de ejemplo."""
    try:
        from app.followups import _next_size_part
        with get_db_cursor() as cur:
            cur.execute("SELECT * FROM actuators WHERE is_available ORDER BY frame_size, base_part_number LIMIT 1;")
            row = cur.fetchone()
        if not row:
            return None
        return row["base_part_number"], _next_size_part(row)
    except Exception:  # noqa: BLE001
        return None


def _followups(keys: List[str], lang: str) -> List[Dict[str, str]]:
    sample = sample_models() if any(k in ("sample_spec", "sample_compare") for k in keys) else None
    out: List[Dict[str, str]] = []
    for k in keys:
        if k == "sample_spec" and sample:
            out.append(render_followup(k, lang, pn=sample[0]))
        elif k == "sample_compare" and sample and sample[1]:
            out.append(render_followup(k, lang, pn=sample[0], other=sample[1]))
        elif k not in ("sample_spec", "sample_compare"):
            out.append(render_followup(k, lang))
    return out


def help_menu(lang: str) -> List[Dict[str, str]]:
    sample = sample_models()
    opts: List[Dict[str, str]] = []
    for key in HELP_MENU_ORDER:
        e = HELP_MENU[key]
        if key in ("spec", "compare") and not sample:
            continue
        if key == "compare" and not sample[1]:
            continue
        kw = {"pn": sample[0], "other": sample[1]} if sample else {}
        opts.append({"label": e[f"label_{lang}"], "value": e[f"value_{lang}"].format(**kw)})
    return opts


# --------------------------------------------------------------------------------------------- respuestas deterministas
_FOLLOW_KEYS = {
    "greeting": ["sample_spec", "start_recommend", "sample_compare"],        # contrato: máximo 3 botones (ficha, recomendar, comparar)
    "capabilities": ["sample_spec", "start_recommend", "sample_compare"],
    "data": ["sample_spec", "start_recommend", "ask_capabilities"],
    "about_project": ["ask_capabilities", "sample_spec", "start_recommend"],
    "thanks": ["start_recommend", "ask_capabilities"],
    "bye": [],
    "off_topic": ["sample_spec", "start_recommend", "ask_capabilities"],
    "attribute": ["sample_spec", "ask_certs", "start_recommend"],
    "application": ["start_recommend", "ask_s4", "ask_capabilities"],
    "clarify_which": ["sample_spec", "start_recommend"],
    "ask_criteria": ["start_recommend", "sample_compare"],
}


def _payload(display: str, followups: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"display_type": display, "actuators": [], "engineering_warnings": [], "alerts": [], "suggested_followups": followups}


def render_act(act: str, lang: str, attr_label: Optional[Dict[str, str]] = None) -> Tuple[str, Dict[str, Any], str]:
    """(texto, ui_payload, intent) de un acto determinista. intent usa los valores existentes: knowledge / clarify."""
    if act == "help_request":
        ui = _payload("CLARIFICATION", [])
        ui["clarification"] = {"question": t_act(lang, "help_question"), "options": help_menu(lang)}
        return t_act(lang, "help_question"), ui, "clarify"
    if act == "unclear":          # el clasificador no pudo (o no quiso) decidir: menú neutro, nunca una recomendación al azar
        ui = _payload("CLARIFICATION", [])
        ui["clarification"] = {"question": t_act(lang, "unclear"), "options": help_menu(lang)}
        return t_act(lang, "unclear"), ui, "clarify"
    if act == "application":      # explica que el par lo da el fabricante de la válvula y ofrece caminos como botones
        text = t_act(lang, "application")
        ui = _payload("CLARIFICATION", [])
        ui["clarification"] = {"question": text, "options": help_menu(lang)}
        return text, ui, "clarify"
    if act == "ask_criteria":
        return t_act(lang, "ask_criteria"), _payload("TEXT_ONLY", _followups(_FOLLOW_KEYS["ask_criteria"], lang)), "clarify"
    if act == "clarify_which":
        return t_act(lang, "clarify_which"), _payload("TEXT_ONLY", _followups(_FOLLOW_KEYS["clarify_which"], lang)), "clarify"
    kw: Dict[str, Any] = {}
    key = act
    if act == "about_project":
        counts = catalog_counts()
        if counts:
            kw["n"] = counts["available"]
        else:
            key = "about_project_nodb"
    elif act == "attribute":
        kw["what"] = (attr_label or {}).get(lang) or (attr_label or {}).get("en") or ("este dato" if lang == "es" else "That data")
        kw["what"] = kw["what"][:1].upper() + kw["what"][1:]
    text = t_act(lang, key, **kw)
    return text, _payload("TEXT_ONLY", _followups(_FOLLOW_KEYS.get(act, []), lang)), "knowledge"


# --------------------------------------------------------------------------------------------- referencias de tamaño
def _supply_label(row: Dict[str, Any], lang: str) -> Tuple[str, str]:
    """(etiqueta visible, texto para reenviar) de una alimentación: «110 V monofásico» / «24 V DC»."""
    v, ph = int(row["voltage_num"]), row["phase_type"]
    word = PHASE_WORD[ph][lang] if ph in PHASE_WORD else ph
    return f"{v} V {word}".strip(), f"{v}V {word}".strip()


def resolve_size_reference(size: str, voltage: Optional[int], phase: Optional[str], lang: str) -> Dict[str, Any]:
    """Código de tamaño (+ voltaje/fase opcionales) -> un modelo, o las opciones REALES de la base.
    {"kind": "lookup", "pn"} | {"kind": "clarify", "size", "options": [{label, value}], "not_offered": bool} | {"kind": "none"}"""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM actuators WHERE size_code = %s ORDER BY voltage_num, phase_type;", (size,))
        rows = cur.fetchall()
    if not rows:
        return {"kind": "none"}

    def match(r: Dict[str, Any]) -> bool:
        if voltage is not None and int(r["voltage_num"]) != int(voltage):
            return False
        if phase and r["phase_type"] != phase:
            return False
        return True

    filtered = [r for r in rows if match(r)]
    avail = [r for r in filtered if r["is_available"]]
    if len(filtered) == 1:
        return {"kind": "lookup", "pn": filtered[0]["base_part_number"]}      # incluye un único modelo N/A: el lookup explica el N/A
    if len(avail) == 1:
        return {"kind": "lookup", "pn": avail[0]["base_part_number"]}
    pool = avail or filtered
    not_offered = False
    if not filtered:                                                         # el filtro pedido no existe en este tamaño
        pool, not_offered = [r for r in rows if r["is_available"]] or rows, True
    elif not avail:
        return {"kind": "lookup", "pn": filtered[0]["base_part_number"]}
    prefix = pool[0]["base_part_number"].split("-")[0]
    options = []
    for r in pool:
        label, value = _supply_label(r, lang)
        options.append({"label": label, "value": f"{prefix} {value}"})
    if len(options) == 1:
        return {"kind": "lookup", "pn": pool[0]["base_part_number"]}
    return {"kind": "clarify", "size": size, "options": options, "not_offered": not_offered}


def render_supply_clarification(res: Dict[str, Any], lang: str) -> Tuple[str, Dict[str, Any]]:
    key = "supply_not_offered" if res["not_offered"] else "supply_question"
    question = t_act(lang, key, size=res["size"])
    ui = _payload("CLARIFICATION", [])
    ui["clarification"] = {"question": question, "options": res["options"]}
    return question, ui


def new_session_title(lang: str) -> str:
    return NEW_TITLE.get(lang, NEW_TITLE["en"])


def data_followups(lang: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    v = (filters or {}).get("voltage_num")
    if v:   # «¿hay de 24 V?»: botones útiles sobre ese voltaje (ranking, recomendación) en vez de los genéricos
        if lang == "es":
            return [{"label": f"Recomendar de {v} V", "query": f"Ayúdame a elegir un actuador de {v} V"},
                    {"label": f"Más rápido en {v} V", "query": f"¿Cuál es el más rápido en {v} V?"},
                    {"label": f"Más potente en {v} V", "query": f"¿Cuál es el más potente en {v} V?"}]
        return [{"label": f"Recommend a {v} V", "query": f"Help me choose a {v} V actuator"},
                {"label": f"Fastest at {v} V", "query": f"Which is the fastest at {v} V?"},
                {"label": f"Most powerful at {v} V", "query": f"Which is the most powerful at {v} V?"}]
    return _followups(_FOLLOW_KEYS["data"], lang)


__all__ = ["data_followups", "detect_conversational", "detect_attribute", "is_application_context", "is_conversational_only", "render_act",
           "resolve_size_reference", "render_supply_clarification", "truncate_title", "new_session_title", "norm"]
