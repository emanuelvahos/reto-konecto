"""Pipeline del agente (verificador -> reintento -> plantilla, intent, idioma, steps, costo) con un ejecutor falso.

No usa LLM: las respuestas del "modelo" están guionizadas; las herramientas y la DB son las reales.
"""
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.agent as agent  # noqa: E402
from app.tools import lookup_actuator_by_part_number, recommend_actuators  # noqa: E402

TOOLS = {"lookup": lookup_actuator_by_part_number, "recommend": recommend_actuators}
PN = "763B00-11300000/A"


class FakeExecutor:
    def __init__(self, script):
        self.script, self.calls, self.states = script, 0, []

    def invoke(self, state, config=None):
        self.states.append(state)
        step = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if step.get("tool"):
            name, args = step["tool"]
            TOOLS[name].invoke(args)
        usage = {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110}
        return {"messages": list(state["messages"]) + [AIMessage(content=step["answer"], usage_metadata=usage)]}


@pytest.fixture
def run(monkeypatch):
    monkeypatch.setattr(agent, "build_llm", lambda: None)

    def _run(script, query, locale=None, history=None):
        fake = FakeExecutor(script)
        monkeypatch.setattr(agent, "create_react_agent", lambda llm, tools: fake)
        out = agent.run_agent_turn(query, history or [], [], {}, locale=locale)
        return out, fake

    return _run


LOOKUP = ("lookup", {"part_number": PN})


def test_valid_answer_passes_without_retry(run):
    (answer, ui, dbg, parts, _, meta), fake = run(
        [{"tool": LOOKUP, "answer": f"The {PN} has 500 Nm on/off and 380 Nm modulating, 90 W."}], f"specs of {PN}"
    )
    assert fake.calls == 1 and meta["verification"] == {"status": "verified", "numbers_checked": 4, "ungrounded": []}
    assert meta["intent"] == "lookup" and ui["display_type"] == "SINGLE_SPEC_CARD" and parts == [PN]
    assert dbg["token_usage"]["retries"] == 0 and dbg["provider"] and dbg["language"] == "en"
    assert {"verifier", "ui_payload"} <= {s["name"] for s in dbg["steps"]}


def test_invented_number_triggers_one_retry_listing_offenders_then_passes(run):
    (answer, _, dbg, _, _, meta), fake = run(
        [{"tool": LOOKUP, "answer": f"The {PN} draws 120 W."}, {"answer": f"The {PN} draws 90 W."}], f"power of {PN}"
    )
    assert fake.calls == 2 and dbg["token_usage"]["retries"] == 1
    feedback = fake.states[1]["messages"][-1].content
    assert "120" in feedback and "ONLY numbers returned by the tools" in feedback
    assert answer == f"The {PN} draws 90 W." and meta["verification"]["status"] == "verified"
    assert "verifier_retry" in {s["name"] for s in dbg["steps"]}


@pytest.mark.parametrize("locale,query,header,no_llm_text", [
    ("es", f"¿potencia del {PN}?", "Datos del catálogo", "llm"),
    ("en", f"power of {PN}?", "Catalog data", "llm"),
])
def test_persistent_ungrounded_numbers_use_deterministic_template_in_user_language(run, locale, query, header, no_llm_text):
    (answer, ui, dbg, _, _, meta), fake = run(
        [{"tool": LOOKUP, "answer": "Draws 120 W."}, {"answer": "Draws 130 W."}], query, locale=locale
    )
    assert fake.calls == 2
    assert meta["verification"]["status"] == "fallback_template"
    assert meta["verification"]["ungrounded"] == ["130"] and meta["verification"]["numbers_checked"] == 1
    assert answer.startswith(header) and PN in answer and "90 W" in answer and "130 W" not in answer
    assert meta["intent"] == "lookup" and ui["actuators"][0]["base_part_number"] == PN
    assert "fallback_template" in {s["name"] for s in dbg["steps"]}


def test_no_tool_with_numbers_falls_back_to_generic_message_and_intent_error(run):
    (answer, ui, _, _, _, meta), _ = run([{"answer": "It has 500 Nm."}], "hola, ¿cuánto torque tiene?", locale="es")
    assert meta["verification"]["status"] == "fallback_template" and meta["intent"] == "error"
    assert "No pude verificar" in answer and ui["actuators"] == []


def test_no_tool_without_numbers_is_verified_clarify(run):
    (answer, _, _, _, _, meta), _ = run([{"answer": "Which voltage do you need?"}], "recommend an actuator")
    assert meta["verification"] == {"status": "verified", "numbers_checked": 0, "ungrounded": []}
    assert meta["intent"] == "clarify"


def test_empty_answer_is_treated_as_failure(run):
    (answer, _, _, _, _, meta), fake = run([{"tool": LOOKUP, "answer": ""}, {"answer": ""}], f"specs {PN}", locale="en")
    assert fake.calls == 2 and meta["verification"]["status"] == "fallback_template" and PN in answer


def test_intent_follows_last_tool(run):
    rec = ("recommend", {"min_torque_nm": 200, "enclosure_type": "Explosionproof", "voltage_num": 24})
    (_, ui, _, _, filters, meta), _ = run([{"tool": rec, "answer": "Option found."}], "need 24V explosionproof 200 Nm")
    assert meta["intent"] == "recommend" and filters["voltage_num"] == 24
    assert meta["short_title"] == "Recommendation ≥200 Nm · 24V · Explosionproof"


def test_alerts_are_localized_with_the_turn_language(run):
    na = ("lookup", {"part_number": "761A00-11330C00/A"})
    script = [{"tool": na, "answer": "Listed as N/A."}]
    (_, ui_es, _, _, _, _), _ = run(script, "¿Qué es el 761A00-11330C00/A?")
    (_, ui_en, _, _, _, _), _ = run(script, "What is the 761A00-11330C00/A?")
    es = [a for a in ui_es["alerts"] if a["code"] == "MODEL_LISTED_AS_NA"][0]
    en = [a for a in ui_en["alerts"] if a["code"] == "MODEL_LISTED_AS_NA"][0]
    assert "figura como N/D" in es["message"] and "is listed as N/A" in en["message"]
    assert es["severity"] == en["severity"] == "warning"
    assert ui_es["engineering_warnings"] and ui_es["engineering_warnings"][0] == ui_es["alerts"][0]["message"]


def test_session_cost_is_zero_on_nim_and_priced_on_openrouter(run, monkeypatch):
    (_, _, dbg, _, _, meta), _ = run([{"tool": LOOKUP, "answer": f"{PN}: 90 W."}], f"power {PN}")
    assert dbg["cost_usd_estimate"] == 0.0 or dbg["provider"] != "nim"
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("LLM_CHAT_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    (_, _, dbg2, _, _, meta2), _ = run([{"tool": LOOKUP, "answer": f"{PN}: 90 W."}], f"power {PN}")
    assert dbg2["provider"] == "openrouter" and dbg2["cost_usd_estimate"] == pytest.approx((100 * 0.15 + 10 * 0.60) / 1e6)
    assert meta2["cost_usd"] == dbg2["cost_usd_estimate"]
