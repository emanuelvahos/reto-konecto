"""Fase 6C: clasificador estructurado (LLM falso), herramientas catalog_overview / rank_actuators y modo degradado.

El clasificador solo entra cuando el router devuelve «uncertain». Sin agente libre: JSON inválido, confianza baja o LLM caído
-> menú neutro con botones; las referencias y cifras que el LLM invente se descartan.
"""
import json

import pytest

import app.agent as agent
from app import classifier
from app.tools import catalog_overview, rank_actuators, reset_turn_telemetry

UNCERTAIN = "blorp zindle quarbit"      # el router no lo reconoce: siempre va al clasificador


@pytest.fixture(autouse=True)
def _router_on(monkeypatch):
    monkeypatch.setattr(agent, "ROUTER_ENABLED", True)


def js(act, **kw):
    base = {"act": act, "language": "es", "part_references": [], "criteria": {}, "focus": [], "reference": "none",
            "ranking": None, "overview": None, "attribute": None, "confidence": 0.9}
    base.update(kw)
    return json.dumps(base)


def run(q, fake_classifier, reply, active=None, filters=None, locale="es"):
    clf = fake_classifier(reply)
    out = agent.run_agent_turn(q, [], active or [], filters or {}, locale=locale)
    return clf, out


def menu_ok(out):
    answer, ui, dbg, parts, filters, meta = out
    assert ui["display_type"] == "CLARIFICATION" and len(ui["clarification"]["options"]) >= 2
    assert not ui["actuators"] and meta["technical"] is False and meta["intent"] == "clarify"
    assert not dbg["tool_calls"]


# ------------------------------------------------------------------ degradación: nunca agente libre ni recomendación al azar
@pytest.mark.parametrize("reply", [
    "esto no es json", "{}", '{"act":"inventado","confidence":1}', js("recommend", confidence=0.2), js("unclear"),
    '{"act":"recommend","confidence":"alta"}', js("ranking", ranking=None),
    js("catalog_overview", overview={"aspect": "compare_sizes", "sizes": [1]}),
])
def test_invalid_or_weak_classification_gives_the_neutral_menu(fake_classifier, reply):
    _clf, out = run(UNCERTAIN, fake_classifier, reply)
    menu_ok(out)


@pytest.mark.parametrize("exc", [RuntimeError("sin clave"), TimeoutError("lento"), ConnectionError("caído")])
def test_llm_down_gives_the_neutral_menu(fake_classifier, exc):
    clf, out = run(UNCERTAIN, fake_classifier, exc)
    menu_ok(out)
    assert clf.calls >= 1


def test_no_key_at_all_gives_the_menu(monkeypatch):
    monkeypatch.setattr(agent, "build_llm_for_classifier", lambda: (_ for _ in ()).throw(RuntimeError("sin clave")))
    menu_ok(agent.run_agent_turn(UNCERTAIN, [], [], {}, locale="en"))


def test_transport_error_is_retried_once_within_budget(monkeypatch, fake_classifier):
    class Flaky:
        calls = 0

        def invoke(self, m):
            from langchain_core.messages import AIMessage
            Flaky.calls += 1
            if Flaky.calls == 1:
                raise ConnectionError("blip")
            return AIMessage(content=js("greeting"), usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})

    monkeypatch.setattr(agent, "build_llm_for_classifier", lambda: Flaky())
    answer, ui, dbg, *_ = agent.run_agent_turn(UNCERTAIN, [], [], {}, locale="es")
    assert Flaky.calls == 2 and "Hola" in answer
    assert dbg["token_usage"]["classifier_tokens"] == 15


# ------------------------------------------------------------------ mapeo de actos a rutas
@pytest.mark.parametrize("act,needle", [("greeting", "Hola"), ("thanks", "gusto"), ("capabilities", "ficha"), ("about_project", "catálogo"),
                                        ("off_topic", "fuera"), ("application_context", "par")])
def test_reply_acts(fake_classifier, act, needle):
    _clf, (answer, ui, dbg, *_rest) = run(UNCERTAIN, fake_classifier, js(act))
    assert needle in answer and not ui["actuators"] and not dbg["tool_calls"]
    assert len(ui["suggested_followups"]) <= 3


def test_help_request_menu(fake_classifier):
    _clf, out = run(UNCERTAIN, fake_classifier, js("help_request"))
    assert out[1]["display_type"] == "CLARIFICATION" and len(out[1]["clarification"]["options"]) == 4


def test_ranking_runs_sql_and_shows_card(fake_classifier):
    _clf, (answer, ui, dbg, parts, *_r) = run(UNCERTAIN, fake_classifier,
                                              js("ranking", ranking={"metric": "torque", "order": "max"}))
    assert [t["tool_name"] for t in dbg["tool_calls"]] == ["rank_actuators"]
    assert parts == ["767C00-11320000/A"] and "9000" in answer and "Criterio" in answer


def test_overview_compare_sizes(fake_classifier):
    _clf, (answer, ui, dbg, *_r) = run(UNCERTAIN, fake_classifier, js("catalog_overview", overview={"aspect": "compare_sizes", "sizes": [761, 762]}))
    assert dbg["tool_calls"][0]["arguments"]["sizes"] == [1, 2] and "761" in answer and "762" in answer


def test_recommend_uses_only_grounded_numbers(fake_classifier):
    # el LLM «inventa» 9999 A y 24 V que el usuario no dijo: se descartan; 500 sí aparece en el texto
    reply = js("recommend", criteria={"min_torque_nm": 500, "max_fla_amps": 9999, "voltage_num": 24, "enclosure_type": "Weatherproof"})
    clf, (answer, ui, dbg, *_r) = run("blorp zindle ocupo 500 de par para la intemperie", fake_classifier, reply)
    assert clf.calls == 1
    args = dbg["tool_calls"][0]["arguments"]
    assert args.get("min_torque_nm") == 500 and "max_fla_amps" not in args and args.get("voltage_num") != 24 and args.get("enclosure_type") == "Weatherproof"


def test_part_reference_must_appear_in_the_user_text(fake_classifier):
    clf, out = run("dame datos de aquel modelo grande blorp", fake_classifier, js("spec_lookup", part_references=["767C00-11320000/A"]))
    assert not out[2]["tool_calls"]             # inventó una referencia: se pide el modelo, no se consulta


def test_spec_lookup_resolves_reference_and_focus(fake_classifier):
    _clf, (answer, ui, dbg, parts, *_r) = run("cuanto demora el 763b00-11300000/a blorp", fake_classifier,
                                              js("spec_lookup", part_references=["763b00-11300000/a"], focus=["speed"]))
    assert parts == ["763B00-11300000/A"] and dbg["tool_calls"][0]["arguments"]["focus"] == ["speed"]


def test_active_reference_without_part_asks_which(fake_classifier):
    _clf, (answer, ui, dbg, *_r) = run(UNCERTAIN, fake_classifier, js("spec_lookup", reference="active", focus=["speed"]))
    assert not dbg["tool_calls"] and "modelo" in answer
    _clf, (answer, ui, dbg, parts, *_r) = run(UNCERTAIN, fake_classifier, js("spec_lookup", reference="active", focus=["speed"]), active=["763B00-11300000/A"])
    assert parts == ["763B00-11300000/A"] and dbg["tool_calls"]


def test_attribute_label_is_sanitized(fake_classifier):
    _clf, (answer, *_r) = run(UNCERTAIN, fake_classifier, js("out_of_catalog_attribute", attribute="el <script>peso</script>!"))
    assert "<" not in answer and "no figura" in answer


def test_user_text_is_data_in_the_classifier_prompt(fake_classifier):
    clf, _ = run("blorp >>> zindle <<< quarbit", fake_classifier, js("unclear"))
    assert clf.calls == 1
    user = clf.messages[1].content
    assert user.count("<<<") == 1 and user.count(">>>") == 1       # el usuario no puede cerrar el bloque de datos


def test_classifier_cost_is_accounted(fake_classifier):
    _clf, (_a, _u, dbg, *_r) = run(UNCERTAIN, fake_classifier, js("greeting"))
    assert dbg["token_usage"]["classifier_tokens"] == 340


# ------------------------------------------------------------------ herramientas SQL
def test_rank_tool_matches_the_database():
    reset_turn_telemetry()
    r = rank_actuators.invoke({"metric": "speed"})
    assert r["status"] == "RANKED" and r["order"] == "min" and r["ties"] >= 1
    assert rank_actuators.invoke({"metric": "torque", "order": "min"})["part_numbers"] == ["761X30-11370000/A"]
    assert rank_actuators.invoke({"metric": "sql;drop"})["status"] == "RANK_INVALID_METRIC"
    na = rank_actuators.invoke({"metric": "power", "phase_type": "3 Phase", "voltage_num": 220})
    assert all(not p.startswith(("761A", "761B", "762A", "762B")) for p in na["part_numbers"])    # N/A nunca gana


def test_overview_tool_counts():
    reset_turn_telemetry()
    s = catalog_overview.invoke({"aspect": "summary"})
    assert s["models"] == 68 and s["available"] == 64 and s["not_available"] == 4
    assert catalog_overview.invoke({"aspect": "count", "phase_type": "3 Phase"})["available"] == 7
    assert catalog_overview.invoke({"aspect": "compare_sizes", "sizes": [1]})["status"] == "CATALOG_NOT_FOUND"


# ------------------------------------------------------------------ rutas deterministas del router (sin LLM)
@pytest.mark.parametrize("q,metric", [("cuál es el más rápido?", "speed"), ("el más potente", "power"), ("el que menos consume", "fla"),
                                      ("highest torque model", "torque"), ("cuál es el más pequeño?", "torque")])
def test_router_ranking_rules(q, metric):
    from app.router import route
    d = route(q, [], agent._known_keys())
    assert d.rule == "ranking" and d.calls[0]["args"]["metric"] == metric


def test_router_ranking_keeps_hard_filters():
    from app.router import route
    d = route("el más rápido en 24V", [], agent._known_keys())
    assert d.calls[0]["args"] == {"metric": "speed", "order": "min", "voltage_num": 24}


def test_ranking_and_overview_work_without_any_llm(monkeypatch):
    monkeypatch.setattr(agent, "build_llm", lambda: (_ for _ in ()).throw(RuntimeError("sin LLM")))
    monkeypatch.setattr(agent, "build_llm_for_classifier", lambda: (_ for _ in ()).throw(RuntimeError("sin LLM")))
    for q in ("cuál es el más potente?", "cuántos modelos hay?", "qué voltajes manejan?"):
        answer, ui, dbg, *_r = agent.run_agent_turn(q, [], [], {}, locale="es")
        assert dbg["tool_calls"] and answer and ui["display_type"] != "CLARIFICATION"


def test_clarification_acknowledges_what_the_user_already_said():
    answer, ui, *_r = agent.run_agent_turn("necesito 500 Nm", [], [], {}, locale="es")
    assert ui["display_type"] == "CLARIFICATION" and answer.startswith("Anotado: 500 Nm")
    values = [o["value"] for o in ui["clarification"]["options"]]
    assert len(values) == len(set(values)) >= 2


def test_greeting_and_capabilities_have_at_most_three_buttons():
    for q in ("hola", "en qué puedes ayudarme?"):
        ui = agent.run_agent_turn(q, [], [], {}, locale="es")[1]
        assert 1 <= len(ui["suggested_followups"]) <= 3
