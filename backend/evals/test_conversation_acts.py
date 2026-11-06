"""Fase 6B: actos conversacionales deterministas, referencias de tamaño, sinónimos, higiene de estado, recomendación neutra y título."""
import pytest

import app.agent as agent
from app import acts
from app.i18n_acts import truncate_title
from app.router import route

KEYS = agent._known_keys()


@pytest.fixture(autouse=True)
def _router_on(monkeypatch):
    monkeypatch.setattr(agent, "ROUTER_ENABLED", True)


def go(q, active=None, **kw):
    return route(q, active or [], KEYS, **kw)


# 1) fuera de alcance: precio sí, «cuestión» no
@pytest.mark.parametrize("q", ["cuánto cuesta el 763B00", "los costos", "precio", "cotización por favor"])
def test_price_forms_are_out_of_scope(q):
    assert go(q).reply == "out_of_scope"


@pytest.mark.parametrize("q", ["tengo una cuestión sobre el 763B", "un cuestionario sobre el 763B00-11300000/A"])
def test_cuestion_is_not_a_price(q):
    assert go(q).reply != "out_of_scope" and not go(q).out_of_scope


# 2) referencias de tamaño flexibles
@pytest.mark.parametrize("q", ["763B00", "763 b 00 de 110 voltios", "763B 110V", "el 763B de 110 voltios", "763B00 monofásico"])
def test_size_reference_forms_resolve(q):
    d = go(q)
    assert d.kind == "resolve" and d.resolve["size"] == "763B"


def test_y_is_not_size_letter():
    assert go("diferencia entre el 761 y el 762").kind != "resolve"


@pytest.mark.parametrize("size,volt,phase,expect", [
    ("763B", 110, None, "763B00-11300000/A"), ("763B", 220, "3 Phase", "763B00-11330C00/A"), ("767C", None, None, "767C00-11320000/A"),
    ("761A", 220, "3 Phase", "761A00-11330C00/A"),    # modelo N/A: el lookup lo explica
])
def test_size_resolution_to_one_model(size, volt, phase, expect):
    assert acts.resolve_size_reference(size, volt, phase, "es") == {"kind": "lookup", "pn": expect}


def test_size_resolution_offers_real_options_including_single_phase_220():
    r = acts.resolve_size_reference("763B", None, None, "es")
    assert r["kind"] == "clarify" and len(r["options"]) == 3
    assert any("220V monofásico" in o["value"] for o in r["options"])
    r = acts.resolve_size_reference("761A", None, None, "es")      # el trifásico N/A no se ofrece
    assert len(r["options"]) == 2
    r = acts.resolve_size_reference("763B", 24, None, "es")
    assert r["kind"] == "clarify" and r["not_offered"]


# 3) sinónimos
@pytest.mark.parametrize("q,group", [("¿cuánto tarda?", "speed"), ("y cuánto demora", "speed"), ("cuánto consume", "current"), ("cuánto gasta", "current"), ("3F 220V 500 Nm", None)])
def test_synonyms(q, group):
    if group:
        assert group in go(q, active=["763B00-11300000/A"]).calls[0]["args"]["focus"]
    else:
        assert go(q).calls[0]["args"]["phase_type"] == "3 Phase"


# 4) actos deterministas
@pytest.mark.parametrize("q,act", [
    ("hola", "greeting"), ("buenas tardes ingeniero", "greeting"), ("gracias", "thanks"), ("adiós", "bye"), ("en qué puedes ayudarme?", "capabilities"),
    ("de qué trata este proyecto?", "about_project"), ("puedes guiarme con tus tareas", "help_request"), ("cuéntame un chiste", "off_topic"),
    ("cuánto pesa el 763B00?", "attribute"), ("necesito un actuador para una válvula de mariposa de 12 pulgadas", "application"),
])
def test_acts(q, act):
    assert go(q).reply == act


@pytest.mark.parametrize("q", ["hola, necesito las specs del 763B00-11300000/A", "ficha del 763B00-11300000/A", "necesito 500 Nm a 110V"])
def test_technical_content_is_not_conversational(q):
    assert go(q).reply is None


def run(q, filters=None, parts=None, history=None):
    return agent.run_agent_turn(q, history or [], parts or [], filters or {}, locale="es")


def test_greeting_turn_has_buttons_no_tools_and_keeps_state(monkeypatch):
    monkeypatch.setattr(agent, "build_llm", lambda: (_ for _ in ()).throw(RuntimeError("sin LLM")))   # prueba que no usa LLM
    answer, ui, dbg, parts, filters, meta = run("hola", {"voltage_num": 220}, ["763B00-11300000/A"])
    assert len(ui["suggested_followups"]) >= 3 and not ui["actuators"] and not dbg["tool_calls"]
    assert parts == ["763B00-11300000/A"] and filters["voltage_num"] == 220 and meta["technical"] is False


def test_help_request_is_a_menu_never_the_voltage_question():
    answer, ui, *_ = run("puedes guiarme con tus tareas", {"voltage_num": 220, "phase_type": "3 Phase"})
    assert ui["display_type"] == "CLARIFICATION" and len(ui["clarification"]["options"]) == 4
    assert "voltaje" not in answer.lower()


def test_about_project_count_comes_from_the_database():
    answer, *_ = run("de qué trata este proyecto?")
    assert "64 modelos" in answer


def test_attribute_and_application_answers():
    answer, ui, *_ = run("cuánto pesa el 763B00?")
    assert "no figura" in answer and not ui["actuators"]
    answer, ui, *_ = run("válvula de mariposa de 12 pulgadas")
    assert "Nm" in answer and not ui["actuators"] and ui["clarification"]["options"]


# 7) higiene de estado
def test_filters_age_out_after_idle_turns():
    f = {"voltage_num": 220}
    for i in range(2):
        _a, _u, _d, _p, f, _m = run("gracias", f)
        assert f.get("voltage_num") == 220
        f = dict(f)
    _a, _u, _d, _p, f, _m = run("gracias", f)
    assert f == {}


def test_lookup_expires_recommendation_filters():
    *_, filters, _meta = run("ficha del 763B00-11300000/A", {"voltage_num": 220})
    assert filters == {}


def test_pending_clarification_closes_if_not_answered():
    *_, f1, _m = run("763B00")
    assert f1["_pending"]["topic"] == "supply"
    *_, f2, _m = run("gracias", f1)
    assert "_pending" not in f2
    answer, ui, _d, parts, _f, _m = run("220V trifásico", f1)           # respuesta a la aclaración: ficha del 3F
    assert parts == ["763B00-11330C00/A"]


def test_pronoun_without_referent_asks_which():
    answer, ui, dbg, *_ = run("cuánto tarda ese?")
    assert not ui["actuators"] and not dbg["tool_calls"] and "modelo" in answer


# 8) recomendación sin criterios blandos
def test_recommendation_without_soft_criteria_is_neutral():
    answer, ui, dbg, parts, _f, meta = run("dame opciones de 220V trifásico")
    low = answer.lower()
    assert low.startswith("hay ") and "mejor opci" not in low and "ajuste" not in low
    assert ui["recommendation"]["ranking"] == []
    tq = [min(float(a[k]) for k in ("on_off_torque_nm", "modulating_torque_nm") if a.get(k) is not None) for a in ui["actuators"]]
    assert tq == sorted(tq)
    assert all("Nm" in f["label"] and "220V" in f["query"] for f in ui["suggested_followups"])


def test_recommendation_with_soft_criteria_keeps_ranking():
    ui = run("necesito 500 Nm on/off a 110V weatherproof")[1]
    assert ui["recommendation"]["ranking"]


# 9) título de sesión
def test_title_never_cuts_a_word():
    t = truncate_title("hola necesito saber acerca de este proyecto de que se trata")
    assert len(t) <= 28 and t.endswith("…") and not t[:-1].endswith(("d", "ac")) and t[:-1] in "hola necesito saber acerca de este proyecto"
    assert truncate_title("corto") == "corto"


def test_greeting_does_not_become_the_title():
    from app.main import generate_session_title
    assert generate_session_title("hola", "es") == "Nueva consulta"
    assert generate_session_title("ficha del 763B00-11300000/A", "es").startswith("ficha del")
