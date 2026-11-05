"""Motor de recomendación (restricciones duras/blandas, score, why/why_not, aclaración). Sin LLM.

La lógica pura se prueba con las filas del oráculo (golden.json); los casos de herramienta usan la base real.
"""
import json
from pathlib import Path

import pytest

from app import recommend as rec
from app.agent import build_recommendation_payload
from app.i18n import render_clarification, resolve_clarification_answer
from app.tools import (
    current_pending_args,
    current_turn_alerts,
    current_turn_clarification,
    recommend_actuators,
    reset_turn_telemetry,
)

ROWS = json.loads((Path(__file__).parent / "oracle" / "golden.json").read_text(encoding="utf-8"))["records"]
AVAIL = [r for r in ROWS if r["is_available"]]
BY_PN = {r["base_part_number"]: r for r in ROWS}


def ranked(**args):
    a = rec.clean_args(args)
    return rec.rank([r for r in AVAIL if rec.passes_hard(r, a)], a), a


# ------------------------------------------------------------------ restricciones duras
def test_hazardous_area_only_explosionproof_and_never_relaxed():
    items, a = ranked(hazardous_area=True, voltage_num=110, min_torque_nm=100000)  # imposible: igual solo Explosionproof
    assert items and all(i["row"]["enclosure_type"] == "Explosionproof" for i in items)
    assert not any(i["all_met"] for i in items)


def test_voltage_is_hard():
    items, _ = ranked(voltage_num=220, min_torque_nm=10)
    assert items and all(i["row"]["voltage_num"] == 220 for i in items)


def test_24v_exists_only_in_explosionproof_and_without_hz_values():
    assert {r["enclosure_type"] for r in AVAIL if r["voltage_num"] == 24} == {"Explosionproof"}
    assert all(r["speed_60hz_sec"] is None and r["speed_50hz_sec"] is None and r["speed_dc_or_fixed_sec"] is not None
               for r in AVAIL if r["voltage_num"] == 24)
    items, _ = ranked(voltage_num=24, enclosure_type="Weatherproof")
    assert items == []


def test_hard_codes_listed():
    a = rec.clean_args({"voltage_num": 110, "hazardous_area": True, "phase_type": "single phase"})
    assert [h["code"] for h in rec.hard_codes(a)] == ["HC_HAZARDOUS", "HC_VOLTAGE", "HC_PHASE"]


# ------------------------------------------------------------------ score y razones calculados desde las filas
def test_score_formula_matches_documentation():
    a = rec.clean_args({"min_torque_nm": 450, "application_type": "On/Off", "voltage_num": 110, "enclosure_type": "Explosionproof"})
    item = rec.score_candidate(BY_PN["763Y30-11300000/A"], a)
    # un solo criterio cumplido => satisfaccion 1, holgura 0% => economia 1  => score 1.0
    assert item["all_met"] and item["score"] == 1.0
    big = rec.score_candidate(BY_PN["764X30-11300000/A"], a)
    margin = (BY_PN["764X30-11300000/A"]["on_off_torque_nm"] - 450) / 450 * 100
    expected = round(0.9 * 1.0 + 0.1 * (1 / (1 + margin / 100)), 3)
    assert big["score"] == expected and big["score"] < item["score"]


def test_unmet_soft_criterion_scores_proportionally_to_deviation():
    a = rec.clean_args({"min_torque_nm": 1000, "application_type": "On/Off", "voltage_num": 24})
    row = BY_PN["763X30-11380000/A"]  # 240 Nm on/off
    item = rec.score_candidate(row, a)
    dev = (1000 - 240) / 1000
    assert not item["all_met"] and item["score"] == round(0.9 * (1 - dev) + 0.1 * 0.0, 3)


def test_why_and_why_not_come_from_row_comparisons():
    a = rec.clean_args({"min_torque_nm": 3500, "voltage_num": 220, "application_type": "On/Off", "require_csa_certification": True})
    items = rec.rank([r for r in AVAIL if rec.passes_hard(r, a)], a)
    top = items[0]
    r = rec.reasons(top, is_top_full_match=False)
    row = top["row"]
    codes = {w["code"]: w["params"] for w in r["why"] + r["why_not"]}
    if "N_TORQUE_SHORT" in codes:
        p = codes["N_TORQUE_SHORT"]
        assert p["actual"] == row["on_off_torque_nm"] and p["required"] == 3500
        assert p["shortfall_pct"] == round((3500 - row["on_off_torque_nm"]) / 3500 * 100, 1)
    if "W_TORQUE_MET" in codes:
        p = codes["W_TORQUE_MET"]
        assert p["margin_pct"] == round((p["actual"] - 3500) / 3500 * 100, 1)
    if not row["csa_certified"]:
        assert "N_CSA_NO" in codes and codes["N_CSA_NO"]["frame_size"] == row["frame_size"]


def test_oversized_warning_uses_documented_threshold():
    a = rec.clean_args({"min_torque_nm": 50, "application_type": "On/Off", "voltage_num": 110, "enclosure_type": "Weatherproof"})
    big = rec.score_candidate(BY_PN["766B00-11300000/A"] if "766B00-11300000/A" in BY_PN else max(
        (r for r in AVAIL if r["voltage_num"] == 110 and r["enclosure_type"] == "Weatherproof"), key=lambda r: r["on_off_torque_nm"]), a)
    r = rec.reasons(big, False)
    assert [w["code"] for w in r["why_not"]] == ["N_OVERSIZED"]
    assert r["why_not"][0]["params"]["margin_pct"] >= rec.OVERSIZE_PCT


def test_speed_fla_and_frequency_for_24v_use_fixed_values():
    a = rec.clean_args({"voltage_num": 24, "max_speed_sec": 20, "frequency_hz": 50})
    items = rec.rank([r for r in AVAIL if rec.passes_hard(r, a)], a)
    met = {i["row"]["base_part_number"] for i in items if i["all_met"]}
    assert met == {r["base_part_number"] for r in AVAIL if r["voltage_num"] == 24 and r["speed_dc_or_fixed_sec"] <= 20}
    crit = items[0]["criteria"][0]
    assert crit["key"] == "speed" and crit["hz"] is None  # valor fijo, no "a 50 Hz"


def test_3phase_modulating_uses_single_rating_and_duty_is_unverifiable():
    a = rec.clean_args({"min_torque_nm": 100, "application_type": "Modulating", "phase_type": "3 Phase"})
    items = rec.rank([r for r in AVAIL if rec.passes_hard(r, a)], a)
    assert items and all(i["criteria"][0]["kind"] == "single" for i in items)
    a2 = rec.clean_args({"min_torque_nm": 100, "application_type": "Modulating", "phase_type": "3 Phase", "min_duty_cycle_pct": 10})
    items2 = rec.rank([r for r in AVAIL if rec.passes_hard(r, a2)], a2)
    assert not any(i["all_met"] for i in items2)
    assert any(c.get("no_data") for c in items2[0]["criteria"] if c["key"] == "duty")


# ------------------------------------------------------------------ aclaración
def test_gate_asks_voltage_first_then_service_then_hazard():
    g = rec.gate(AVAIL, rec.clean_args({}))
    assert g["topic"] == "voltage" and [o["args"]["voltage_num"] for o in g["options"]] == [24, 110, 220]
    g = rec.gate(AVAIL, rec.clean_args({"voltage_num": 110, "min_torque_nm": 450}))
    assert g["topic"] == "service" and len(g["options"]) == 2
    g = rec.gate(AVAIL, rec.clean_args({"voltage_num": 110, "min_torque_nm": 450, "application_type": "On/Off"}))
    assert g["topic"] == "hazard"
    assert rec.gate(AVAIL, rec.clean_args({"voltage_num": 110, "min_torque_nm": 450, "application_type": "On/Off", "hazardous_area": False})) is None


def test_gate_does_not_ask_when_the_answer_would_not_change():
    # sin torque no importa el servicio; 24V solo existe en Explosionproof; 6000 Nm no cabe en ningun voltaje
    assert rec.gate(AVAIL, rec.clean_args({"voltage_num": 24})) is None
    assert rec.gate(AVAIL, rec.clean_args({"min_torque_nm": 6000, "require_csa_certification": True})) is None
    assert rec.gate(AVAIL, rec.clean_args({"voltage_num": 110, "hazardous_area": True})) is None


def test_gate_questions_have_two_to_four_options_and_localize():
    for args in ({}, {"voltage_num": 110, "min_torque_nm": 450}, {"voltage_num": 110, "min_torque_nm": 450, "application_type": "On/Off"}):
        g = rec.gate(AVAIL, rec.clean_args(args))
        for lang in ("es", "en"):
            c = render_clarification(g["topic"], g["options"], lang)
            assert c["question"].endswith("?") and 2 <= len(c["options"]) <= 4
            assert all(o["label"] and o["value"] for o in c["options"])


@pytest.mark.parametrize("topic,text,expected", [
    ("voltage", "110V", {"voltage_num": 110}),
    ("voltage", "uno de 220 V por favor", {"voltage_num": 220}),
    ("service", "Servicio modulante", {"application_type": "Modulating"}),
    ("service", "On/Off service", {"application_type": "On/Off"}),
    ("hazard", "Área peligrosa (Explosionproof)", {"hazardous_area": True}),
    ("hazard", "Área no peligrosa", {"hazardous_area": False}),
    ("hazard", "Non-hazardous area", {"hazardous_area": False}),
    ("hazard", "Hazardous area (Explosionproof)", {"hazardous_area": True}),
    ("voltage", "hola", {}),
])
def test_option_values_resolve_back_to_arguments(topic, text, expected):
    assert resolve_clarification_answer(topic, text) == expected


def test_every_option_value_round_trips():
    for args in ({}, {"voltage_num": 110, "min_torque_nm": 450}, {"voltage_num": 110, "min_torque_nm": 450, "application_type": "On/Off"}):
        g = rec.gate(AVAIL, rec.clean_args(args))
        for lang in ("es", "en"):
            c = render_clarification(g["topic"], g["options"], lang)
            for opt, raw in zip(c["options"], g["options"]):
                assert resolve_clarification_answer(g["topic"], opt["value"]) == raw["args"]


# ------------------------------------------------------------------ herramienta (base real)
def test_tool_returns_needs_clarification_and_stores_pending_state():
    reset_turn_telemetry()
    res = recommend_actuators.invoke({"min_torque_nm": 450})
    assert res["status"] == "NEEDS_CLARIFICATION" and res["missing"] == "voltage"
    st = current_turn_clarification.get()
    assert st["topic"] == "voltage" and st["args"] == {"min_torque_nm": 450}


def test_pending_answer_is_resolved_in_the_same_context():
    reset_turn_telemetry()
    current_pending_args.set({"min_torque_nm": 450, "voltage_num": 110})
    res = recommend_actuators.invoke({"application_type": "On/Off"})
    assert res["status"] == "NEEDS_CLARIFICATION" and res["missing"] == "hazard"  # ya no pregunta voltaje ni servicio
    assert current_turn_clarification.get()["args"] == {"min_torque_nm": 450, "voltage_num": 110, "application_type": "On/Off"}
    current_pending_args.set({})


def test_tool_hard_failure_explains_from_database():
    reset_turn_telemetry()
    res = recommend_actuators.invoke({"voltage_num": 24, "enclosure_type": "Weatherproof"})
    assert res["status"] == "NO_MATCH_HARD_CONSTRAINTS"
    assert "only offered as Explosionproof" in res["diagnostics"][0]
    payload, extras = build_recommendation_payload("es")
    assert payload["ranking"] == [] and payload["hard_constraints"] and extras["available_enclosure_voltage"] == 24


def test_tool_recommendation_payload_is_built_from_rows_and_localized():
    reset_turn_telemetry()
    res = recommend_actuators.invoke(
        {"min_torque_nm": 450, "voltage_num": 110, "application_type": "On/Off", "hazardous_area": True}
    )
    assert res["status"] == "MATCHES_FOUND" and res["ranking"][0]["part_number"] == "763Y30-11300000/A"
    es, _ = build_recommendation_payload("es")
    en, _ = build_recommendation_payload("en")
    assert es["hard_constraints"] == ["Área peligrosa: solo Explosionproof", "Voltaje 110 V"]
    assert en["hard_constraints"] == ["Hazardous area: Explosionproof only", "Voltage 110 V"]
    top = es["ranking"][0]
    assert top["score"] == 1.0 and "450 Nm" in top["why"][0] and es["relaxed_constraints"] == []
    assert all(r["part_number"] in BY_PN and BY_PN[r["part_number"]]["enclosure_type"] == "Explosionproof" for r in es["ranking"])


def test_tool_relaxation_reports_relaxed_constraints():
    reset_turn_telemetry()
    res = recommend_actuators.invoke({"min_torque_nm": 1500, "voltage_num": 24, "application_type": "On/Off"})
    assert res["status"] == "NO_EXACT_MATCH_CONSTRAINT_RELAXATION" and res["unmet_constraints"] == ["torque"]
    es, _ = build_recommendation_payload("es")
    assert es["relaxed_constraints"] == ["Torque mínimo 1500 Nm"] and es["hard_constraints"] == ["Voltaje 24 V"]
    assert all(BY_PN[r["part_number"]]["voltage_num"] == 24 for r in es["ranking"])  # la dura nunca se relaja


def test_dc_has_no_frequency_alert_on_recommend_and_lookup():
    from app.tools import lookup_actuator_by_part_number

    reset_turn_telemetry()
    recommend_actuators.invoke({"voltage_num": 24, "frequency_hz": 50, "max_speed_sec": 30})
    assert "DC_NO_FREQUENCY" in [a["code"] for a in current_turn_alerts.get()]
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "763X30-11370000/A", "frequency_hz": 50})
    assert "DC_NO_FREQUENCY" in [a["code"] for a in res["alerts"]]
    assert "speed_50hz_sec" not in res["actuators"][0]


# ------------------------------------------------------------------ argumentos con respaldo del usuario
def test_ground_args_drops_what_the_user_never_said():
    given = {"application_type": "On/Off", "voltage_num": 110, "min_torque_nm": 450, "hazardous_area": True,
             "require_csa_certification": True, "enclosure_type": "Weatherproof"}
    kept, dropped = rec.ground_args(given, "Necesito un actuador de 450 Nm a 110V")
    assert kept == {"voltage_num": 110, "min_torque_nm": 450} and set(dropped) == {"application_type", "hazardous_area", "require_csa_certification", "enclosure_type"}


@pytest.mark.parametrize("text,arg,value", [
    ("servicio on/off", "application_type", "On/Off"), ("modulating valve", "application_type", "Modulating"),
    ("área peligrosa", "hazardous_area", True), ("Hazardous area (Explosionproof)", "hazardous_area", True),
    ("Área no peligrosa", "hazardous_area", False), ("non-hazardous area", "hazardous_area", False),
    ("must be CSA", "require_csa_certification", True), ("a 50 Hz", "frequency_hz", 50),
    ("1,500 Nm", "min_torque_nm", 1500), ("1.5 s", "max_speed_sec", 1.5), ("220 V", "voltage_num", 220),
    ("trifásico", "phase_type", "3 Phase"),
])
def test_ground_args_keeps_what_the_user_said(text, arg, value):
    kept, dropped = rec.ground_args({arg: value}, text)
    assert kept == {arg: value} and dropped == []


def test_hazard_true_is_not_grounded_by_a_negated_sentence():
    assert rec.ground_args({"hazardous_area": True}, "no es un área peligrosa")[1] == ["hazardous_area"]
    assert rec.ground_args({"hazardous_area": False}, "es un área peligrosa")[1] == ["hazardous_area"]


def test_tool_ignores_invented_arguments_and_reports_them():
    from app.tools import current_user_text

    reset_turn_telemetry()
    current_user_text.set("Recomiéndame un actuador")
    res = recommend_actuators.invoke({"application_type": "On/Off", "min_torque_nm": 800})
    assert res["status"] == "NEEDS_CLARIFICATION" and res["missing"] == "voltage"
    assert sorted(res["ignored_arguments"]) == ["application_type", "min_torque_nm"]
    assert current_turn_clarification.get()["args"] == {}
    reset_turn_telemetry()
