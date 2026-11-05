"""Auditoría 2D: el PDF no define factor de seguridad. El filtro usa exactamente lo pedido; el margen solo se informa;
un factor se aplica únicamente si el usuario lo pide, y se declara."""
import json
from pathlib import Path

from app import recommend as rec
from app.tools import current_user_text, recommend_actuators, reset_turn_telemetry

GOLDEN = json.loads((Path(__file__).parent / "oracle" / "golden.json").read_text(encoding="utf-8"))["records"]
ROW = next(g for g in GOLDEN if g["base_part_number"] == "763B00-11300000/A")   # 500 Nm on/off
TQ = float(ROW["on_off_torque_nm"])


def _run(user_text, **args):
    reset_turn_telemetry()
    current_user_text.set(user_text)
    return recommend_actuators.invoke({"application_type": "On/Off", "voltage_num": 110, "enclosure_type": "Weatherproof",
                                       "phase_type": "Single Phase", **args})


def _pns(res):
    return [x["part_number"] for x in res.get("ranking", [])]


def test_filter_uses_exactly_the_requested_torque_no_hidden_margin():
    # pedir exactamente el torque de la fila: la fila cumple (no se exige torque * algún factor)
    row = {"phase_type": "Single Phase", "on_off_torque_nm": TQ, "modulating_torque_nm": 400.0}
    c = rec.evaluate(row, {"min_torque_nm": TQ, "application_type": "On/Off"})[0]
    assert c["met"] and c["required"] == TQ and c["margin_pct"] == 0.0
    c = rec.evaluate(row, {"min_torque_nm": TQ + 0.01, "application_type": "On/Off"})[0]
    assert not c["met"]


def test_margin_is_reported_as_slack_in_why():
    res = _run(f"need {TQ - 50:g} Nm on/off 110V weatherproof single phase", min_torque_nm=TQ - 50)
    assert res["status"] == "MATCHES_FOUND"
    from app.tools import current_turn_recommendation
    whys = [w for i in current_turn_recommendation.get()["items"] for w in i["why"] if w["code"] == "W_TORQUE_MET"]
    assert whys and all(w["params"]["required"] == TQ - 50 and w["params"]["margin_pct"] >= 0 for w in whys)


def test_factor_is_ignored_when_the_user_never_asked_for_it():
    res = _run(f"need {TQ:g} Nm on/off 110V weatherproof single phase", min_torque_nm=TQ, safety_factor=2.0)
    assert "safety_factor" in res.get("ignored_arguments", []) and ROW["base_part_number"] in _pns(res)
    assert not any(a["code"] == "SAFETY_FACTOR_APPLIED" for a in res.get("alerts", []))


def test_factor_requested_by_the_user_is_applied_and_declared():
    res = _run(f"need {TQ:g} Nm on/off 110V weatherproof single phase with a safety factor of 1.5", min_torque_nm=TQ, safety_factor=1.5)
    assert ROW["base_part_number"] not in _pns(res) or res["status"] != "MATCHES_FOUND"
    alert = next(a for a in res["alerts"] if a["code"] == "SAFETY_FACTOR_APPLIED")
    assert f"{TQ * 1.5:g}" in alert["message"] and "1.5" in alert["message"]
