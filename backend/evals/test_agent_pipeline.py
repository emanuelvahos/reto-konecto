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

    def _run(script, query, locale=None, history=None, filters=None):
        fake = FakeExecutor(script)
        monkeypatch.setattr(agent, "create_react_agent", lambda llm, tools: fake)
        out = agent.run_agent_turn(query, history or [], [], dict(filters or {}), locale=locale)
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
    assert "120" in feedback and "ONLY figures returned by the tools" in feedback
    assert answer == f"The {PN} draws 90 W." and meta["verification"]["status"] == "verified"
    assert "verifier_retry" in {s["name"] for s in dbg["steps"]}


@pytest.mark.parametrize("locale,query,header,no_llm_text", [
    ("es", f"¿potencia del {PN}?", "763B00-11300000/A: ", "llm"),
    ("en", f"power of {PN}?", "763B00-11300000/A: ", "llm"),
])
def test_persistent_ungrounded_numbers_use_deterministic_template_in_user_language(run, locale, query, header, no_llm_text):
    (answer, ui, dbg, _, _, meta), fake = run(
        [{"tool": LOOKUP, "answer": "Draws 120 W."}, {"answer": "Draws 130 W."}], query, locale=locale
    )
    assert fake.calls == 2
    assert meta["verification"]["status"] == "fallback_template"
    assert meta["verification"]["ungrounded"] == ["130"] and meta["verification"]["numbers_checked"] == 1
    assert answer.startswith(header) and "90 W" in answer and "130 W" not in answer
    assert ("potencia del motor 90 W" if locale == "es" else "motor power 90 W") in answer and len(answer.split()) <= 40
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


def test_empty_answer_with_tool_results_uses_template(run):
    (answer, ui, dbg, _, _, meta), fake = run([{"tool": LOOKUP, "answer": ""}, {"answer": ""}], f"specs {PN}", locale="en")
    assert fake.calls == 3 and dbg["token_usage"]["llm_retries"] == 2  # 1 llamada + 2 reintentos, luego plantilla con la tarjeta ya obtenida
    assert meta["intent"] == "lookup" and meta["verification"]["status"] == "fallback_template"
    assert ui["actuators"][0]["base_part_number"] == PN and answer.startswith(PN)


def test_empty_answer_without_tool_results_is_reported_as_error(run):
    (answer, ui, dbg, _, _, meta), fake = run([{"answer": ""}], "hello", locale="en")
    assert dbg["token_usage"]["llm_retries"] == 2
    assert meta["intent"] == "error" and ui["alerts"][0]["code"] == "LLM_UNAVAILABLE"
    assert "temporarily unavailable" in answer


def test_intent_follows_last_tool(run):
    rec = ("recommend", {"min_torque_nm": 200, "enclosure_type": "Explosionproof", "voltage_num": 24, "application_type": "Modulating"})
    (_, ui, _, _, filters, meta), _ = run([{"tool": rec, "answer": "Option found."}], "need 24V explosionproof 200 Nm modulating")
    assert meta["intent"] == "recommend" and filters["voltage_num"] == 24
    assert meta["short_title"] == "Recommendation ≥200 Nm · 24V · Explosionproof · Modulating"
    assert ui["display_type"] == "RECOMMENDATION_LIST" and ui["recommendation"]["ranking"][0]["part_number"] == "763X30-11370000/A"


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


# ------------------------------------------------------------------ aclaración real (bloque E)
def test_missing_decisive_data_returns_clarification_with_one_question_and_options(run):
    rec = ("recommend", {"min_torque_nm": 450})
    (answer, ui, dbg, _, filters, meta), _ = run([{"tool": rec, "answer": "I will ask."}], "necesito un actuador de 450 Nm", locale="es")
    assert meta["intent"] == "clarify" and ui["display_type"] == "CLARIFICATION" and ui["actuators"] == []
    c = ui["clarification"]
    assert answer == c["question"] == "¿Qué voltaje de alimentación necesita el actuador?"
    assert [o["value"] for o in c["options"]] == ["110V", "220V"]  # 24V no llega a 450 Nm: no se ofrece
    assert meta["verification"]["status"] == "verified" and ui["suggested_followups"] == []
    assert filters["_pending"] == {"topic": "voltage", "args": {"min_torque_nm": 450}}


def test_clarification_chain_resolves_each_answer_in_the_same_context(run):
    """El valor elegido se reenvía como mensaje; el LLM puede llamar a la tool SOLO con lo nuevo: el contexto lo completa."""
    (_, ui, _, _, filters, _), _ = run([{"tool": ("recommend", {"min_torque_nm": 450}), "answer": "q"}], "need 450 Nm", locale="en")
    assert ui["clarification"]["options"][0]["value"] == "110V"
    (_, ui, _, _, filters, _), _ = run(
        [{"tool": ("recommend", {"voltage_num": 110}), "answer": "q"}], "110V", locale="en", filters=filters
    )
    assert ui["clarification"]["question"] == "Which type of service will it run?"
    (_, ui, _, _, filters, _), _ = run(
        [{"tool": ("recommend", {}), "answer": "q"}], ui["clarification"]["options"][0]["value"], locale="en", filters=filters
    )
    assert ui["clarification"]["question"].startswith("Will it be installed in a hazardous")
    assert [o["value"] for o in ui["clarification"]["options"]] == ["Hazardous area (Explosionproof)", "Non-hazardous area"]
    (answer, ui, _, _, filters, meta), _ = run(
        [{"tool": ("recommend", {}), "answer": "Best is 763Y30-11300000/A at 450 Nm."}],
        ui["clarification"]["options"][0]["value"], locale="en", filters=filters,
    )
    assert meta["intent"] == "recommend" and ui["display_type"] == "RECOMMENDATION_LIST"
    assert ui["recommendation"]["hard_constraints"] == ["Hazardous area: Explosionproof only", "Voltage 110 V"]
    assert ui["recommendation"]["ranking"][0]["part_number"] == "763Y30-11300000/A"
    assert "_pending" not in filters and filters["application_type"] == "On/Off" and filters["voltage_num"] == 110


def test_unrecognized_reply_drops_the_pending_question(run):
    pending = {"_pending": {"topic": "voltage", "args": {"min_torque_nm": 450}}}
    (_, ui, _, _, filters, meta), _ = run([{"tool": LOOKUP, "answer": f"{PN}: 90 W."}], f"power of {PN}", filters=pending)
    assert meta["intent"] == "lookup" and "_pending" not in filters and "min_torque_nm" not in filters


# ------------------------------------------------------------------ sugerencias (bloque F) y recomendación en el payload
def test_lookup_followups_are_deterministic_localized_and_capped(run):
    (_, ui_en, _, _, _, _), _ = run([{"tool": LOOKUP, "answer": f"{PN}: 90 W."}], f"power of {PN}", locale="en")
    (_, ui_es, _, _, _, _), _ = run([{"tool": LOOKUP, "answer": f"{PN}: 90 W."}], f"potencia del {PN}", locale="es")
    en, es = ui_en["suggested_followups"], ui_es["suggested_followups"]
    assert 1 <= len(en) <= 3 and len(en) == len(es)
    assert [f["label"] for f in es] == ["Compara con el tamaño siguiente", "Ver valores a 50 Hz", "Alternativas del mismo voltaje"]
    assert [f["label"] for f in en] == ["Compare with the next size", "Show 50 Hz values", "Alternatives with the same voltage"]
    assert all(PN in f["query"] for f in en + es) and en[0]["query"].startswith(f"Compare {PN} with 7")
    assert en[1]["query"] == f"What are the 50 Hz values of {PN}?"


def test_followup_after_50hz_question_offers_60hz_and_24v_has_no_hz_chip(run):
    (_, ui, _, _, _, _), _ = run([{"tool": LOOKUP, "answer": f"{PN}: 90 W."}], f"power of {PN} at 50 Hz", locale="en")
    assert "Show 60 Hz values" in [f["label"] for f in ui["suggested_followups"]]
    dc = ("lookup", {"part_number": "763X30-11370000/A"})
    (_, ui, _, _, _, _), _ = run([{"tool": dc, "answer": "ok"}], "specs of 763X30-11370000/A", locale="en")
    assert not any("Hz" in f["label"] for f in ui["suggested_followups"])


def test_recommend_followups_offer_to_relax_unmet_constraints(run):
    rec = ("recommend", {"min_torque_nm": 1500, "voltage_num": 24, "application_type": "On/Off"})
    (_, ui, _, _, _, meta), _ = run([{"tool": rec, "answer": "None reaches it."}], "24V 1500 Nm on/off", locale="es")
    assert meta["intent"] == "recommend" and ui["recommendation"]["relaxed_constraints"] == ["Torque mínimo 1500 Nm"]
    labels = [f["label"] for f in ui["suggested_followups"]]
    assert labels[0] == "Relajar: Torque mínimo 1500 Nm" and len(labels) <= 3
    assert ui["suggested_followups"][0]["query"] == 'Relaja el requisito "Torque mínimo 1500 Nm" y recomienda de nuevo'


def test_impossible_hard_constraints_have_no_cards_and_an_explanatory_alert(run):
    rec = ("recommend", {"voltage_num": 24, "enclosure_type": "Weatherproof"})
    (_, ui, _, _, _, meta), _ = run([{"tool": rec, "answer": "There are none."}], "24V weatherproof actuator", locale="en")
    assert meta["intent"] == "recommend" and ui["display_type"] == "EDGE_CASE_ALERT" and ui["actuators"] == []
    assert ui["alerts"][0]["code"] == "VOLTAGE_ENCLOSURE_UNAVAILABLE" and ui["recommendation"]["ranking"] == []
    assert ui["suggested_followups"][0]["label"] == "Explosionproof models"
