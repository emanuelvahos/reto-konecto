"""Los textos que ve el usuario no mencionan proveedor, modelo, códigos HTTP, LLM, herramientas ni SQL (detalle solo en debug_trace)."""
import re

import pytest

import app.i18n as i18n

FORBIDDEN = re.compile(
    r"\bllm\b|language model|modelo de lenguaje|provider|proveedor|\bhttps?\b|\b[45]\d\d\b|\btools?\b|herramienta|\bsql\b|"
    r"postgres|database|base de datos|nvidia|openrouter|nemotron|knowledge base|base de conocimiento|\bnim\b|exception|traceback",
    re.I,
)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def _user_dicts():
    skip = {"LANG_NAMES"}   # nombres de idioma para el prompt del LLM, no se muestran
    for name, val in vars(i18n).items():
        if name.isupper() and name not in skip and isinstance(val, (dict, list, tuple)):
            yield name, val


@pytest.mark.parametrize("name,val", list(_user_dicts()), ids=[n for n, _ in _user_dicts()])
def test_no_internal_details_in_user_visible_templates(name, val):
    bad = [s for s in _strings(val) if FORBIDDEN.search(s)]
    assert not bad, f"{name}: {bad}"


def test_every_alert_has_a_localized_title_and_message():
    for code, entry in i18n.ALERTS.items():
        for lang in ("es", "en"):
            assert i18n.ALERT_TITLES[code][lang].strip() and entry[lang].strip()
            assert len(i18n.ALERT_TITLES[code][lang].split()) <= 6
    assert set(i18n.ALERT_TITLES) == set(i18n.ALERTS)


def test_llm_unavailable_message_is_the_plain_text_requested():
    assert i18n.render_alert_message("LLM_UNAVAILABLE", {}, "es") == "No pude completar la consulta en este momento. Inténtalo de nuevo en unos segundos."
    assert i18n.render_alert({"code": "HAZARDOUS_NEEDS_EXPLOSIONPROOF", "params": {}}, "es")["title"] == "Área clasificada"
    assert i18n.render_alert({"code": "SINGLE_TORQUE_RATING", "params": {}}, "es")["title"] == "Torque de salida único"
