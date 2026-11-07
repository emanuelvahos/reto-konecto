"""Fase 6D (tercera ronda): arreglos generales tras el set B. Sin LLM (clasificador y redactor fallan a propósito)."""
import pytest

import app.agent as agent


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setattr(agent, "ROUTER_ENABLED", True)
    monkeypatch.setattr(agent, "build_llm_for_classifier", lambda: (_ for _ in ()).throw(RuntimeError("sin LLM")))
    monkeypatch.setattr(agent, "build_llm", lambda: None)


def turn(q, history=None, active=None, locale=None):
    return agent.run_agent_turn(q, history or [], list(active or []), {}, locale=locale)


# 1) capacidades, no «quién soy»
@pytest.mark.parametrize("q", ["para qué sirve esto", "qué hace esta app", "para qué te uso", "what does this app do"])
def test_what_is_this_for_is_the_capabilities_act(q):
    answer, ui, dbg, *_ = turn(q)
    assert not dbg["tool_calls"] and not ui["actuators"]
    assert any(w in answer.lower() for w in ("ficha", "spec sheet")) and "64 modelos" not in answer


# 2) voltaje sin unidad en cualquier posición
@pytest.mark.parametrize("q", ["necesito algo de 150 Nm monofasico 110", "necesito 150 Nm 110 monofásico", "necesito 150 Nm monofásico a 110"])
def test_bare_voltage_in_any_position(q):
    from app.router import extract_criteria
    assert extract_criteria(q)["voltage_num"] == 110
    out = turn(q)
    assert out[0].startswith("Anotado: 150 Nm, 110 V, monofásico")      # el voltaje se reconoce; sigue la siguiente pregunta (tipo de servicio)


def test_bare_number_after_phase_word_that_is_a_torque_unit_is_not_a_voltage():
    from app.router import extract_criteria
    assert "voltage_num" not in extract_criteria("trifásico 220 Nm")


# 3) voltaje inexistente: lo dice y lista los que sí hay, sin tarjetas
@pytest.mark.parametrize("q,locale,needle", [("hay de 12 voltios?", "es", "No existe ningún modelo de 12 V"), ("is there a 48 V version?", "en", "There is no 48 V model")])
def test_nonexistent_voltage_lists_the_real_ones(q, locale, needle):
    answer, ui, dbg, *_ = turn(q, locale=locale)
    assert needle in answer and not ui["actuators"]
    assert "24 V" in answer and "110 V" in answer and "220 V" in answer and ("Explosionproof" in answer)


# 4) «repítelo en inglés / español»
def test_repeat_in_english_reuses_the_previous_question():
    hist = [{"role": "user", "content": "specs del 763B00-11300000/A"}, {"role": "assistant", "content": "763B00-11300000/A: torque on/off 500 Nm"}]
    answer, ui, dbg, parts, _f, meta = turn("dime lo mismo pero en inglés", history=hist, active=["763B00-11300000/A"])
    assert meta["language"] == "en" and parts == ["763B00-11300000/A"] and "torque" in answer.lower() and "modelo" not in answer.lower()
    assert ui["actuators"][0]["base_part_number"] == "763B00-11300000/A"


def test_repeat_in_spanish_skips_earlier_translation_requests():
    hist = [{"role": "user", "content": "specs of 763B00-11300000/A"}, {"role": "assistant", "content": "x"},
            {"role": "user", "content": "say it in english"}, {"role": "assistant", "content": "y"}]
    answer, ui, dbg, parts, _f, meta = turn("repítelo en español", history=hist, active=["763B00-11300000/A"])
    assert meta["language"] == "es" and ui["actuators"]


def test_repeat_without_previous_answer_asks_what_to_translate():
    answer, ui, dbg, *_rest = turn("repítelo en inglés")
    assert not dbg["tool_calls"] and not ui["actuators"] and "respuesta anterior" in answer


def test_repeat_request_with_numbers_or_part_is_not_a_translation():
    from app import acts
    assert acts.detect_translate("specs del 763B en inglés 50 hz") is None and acts.detect_translate("hola") is None
