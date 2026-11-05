"""Valida los ejemplos del contrato v2 contra los modelos Pydantic (costo $0, sin red)."""
import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas import ConversationRequest, ConversationResponse  # noqa: E402

SAMPLES = json.loads((Path(__file__).parent / "fixtures" / "contract_v2_samples.json").read_text(encoding="utf-8"))


def test_fixture_has_four_samples():
    assert set(SAMPLES) == {"single_spec_card", "comparison_table", "recommendation_with_relaxation", "clarification"}


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_sample_validates_and_roundtrips(name):
    model = ConversationResponse.model_validate(SAMPLES[name])
    assert model.schema_version == 2
    dumped = model.model_dump(mode="json")
    again = ConversationResponse.model_validate_json(json.dumps(dumped))
    assert again == model
    assert again.model_dump(mode="json") == dumped


def test_defaults_are_backward_compatible():
    minimal = {
        "session_id": "s",
        "answer": "a",
        "ui_payload": {},
        "debug_trace": {"model_used": "m", "total_latency_ms": 1.0},
    }
    r = ConversationResponse.model_validate(minimal)
    assert (r.schema_version, r.intent) == (2, "lookup")
    assert (r.verification.status, r.verification.numbers_checked) == ("unverified", 0)
    assert r.ui_payload.alerts == [] and r.ui_payload.recommendation is None and r.ui_payload.clarification is None
    assert r.debug_trace.steps == [] and r.debug_trace.cost_usd_estimate == 0 and r.debug_trace.provider == ""


def test_request_new_fields_optional_and_validated():
    assert ConversationRequest(query="q").locale is None
    assert ConversationRequest(query="q", locale="es", input_mode="voice").input_mode == "voice"
    with pytest.raises(ValueError):
        ConversationRequest(query="q", locale="fr")


def test_suggested_followups_contract():
    from app.schemas import UIPayload

    assert UIPayload().suggested_followups == []  # aditivo: ausente = lista vacía
    for name in ("single_spec_card", "recommendation_with_relaxation"):
        chips = ConversationResponse.model_validate(SAMPLES[name]).ui_payload.suggested_followups
        assert 1 <= len(chips) <= 3 and all(c.label and c.query for c in chips)
    assert ConversationResponse.model_validate(SAMPLES["clarification"]).ui_payload.suggested_followups == []


def test_clarification_options_are_resendable_values():
    r = ConversationResponse.model_validate(SAMPLES["clarification"])
    assert r.intent == "clarify" and r.ui_payload.display_type == "CLARIFICATION" and r.answer == r.ui_payload.clarification.question
    assert 2 <= len(r.ui_payload.clarification.options) <= 4
    assert all(o.label and o.value for o in r.ui_payload.clarification.options)


def test_recommendation_sample_has_ranking_and_constraints():
    r = ConversationResponse.model_validate(SAMPLES["recommendation_with_relaxation"])
    rec = r.ui_payload.recommendation
    assert r.intent == "recommend" and r.ui_payload.display_type == "RECOMMENDATION_LIST"
    assert rec.ranking[0].score >= rec.ranking[1].score and rec.hard_constraints and rec.relaxed_constraints


def test_out_of_scope_alert_and_step_detail_are_additive():
    from app.i18n import render_alert
    from app.schemas import TraceStep, UIAlert

    for lang in ("es", "en"):
        alert = render_alert({"code": "OUT_OF_SCOPE", "params": {}}, lang)
        assert alert["severity"] == "info" and UIAlert.model_validate(alert).code == "OUT_OF_SCOPE"
    assert TraceStep(name="router", start_ms=0, duration_ms=1).detail is None   # ausente = None (compatible)
    assert TraceStep(name="router", start_ms=0, duration_ms=1, detail="part_number").detail == "part_number"
