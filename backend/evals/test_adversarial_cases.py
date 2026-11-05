"""Sin LLM: el archivo de casos adversarios está bien formado y el validador contra el oráculo discrimina."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oracle_check import BY_PN, oracle_verify, oracle_value, states_value, ui_matches_oracle  # noqa: E402

CASES = json.loads((Path(__file__).parent / "adversarial.json").read_text(encoding="utf-8"))["cases"]
EXPECT_KEYS = {
    "intent", "display_type", "tools_include", "tool_status_any", "alerts_any", "ui_parts_include", "ui_all_enclosure",
    "no_ui_actuators", "options_between", "answer_any", "answer_none", "must_state", "max_words",
}
REQUIRED_CATEGORIES = {
    "typo", "na_3phase", "invented_pn", "ambiguity", "impossible", "24v_weatherproof", "24v_no_hz", "cycles_vs_starts",
    "csa_warning", "prompt_injection", "out_of_catalog", "followup_no_pn", "compare", "3phase_modulating",
}


def test_at_least_twenty_cases_in_both_languages_covering_all_categories():
    assert len(CASES) >= 20 and len({c["id"] for c in CASES}) == len(CASES)
    assert {c["lang"] for c in CASES} == {"es", "en"}
    assert REQUIRED_CATEGORIES <= {c["category"] for c in CASES}
    for cat in REQUIRED_CATEGORIES:
        assert {c["lang"] for c in CASES if c["category"] == cat} == {"es", "en"}, f"{cat} sin ambos idiomas"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_is_well_formed(case):
    assert case["turns"] and set(case["expect"]) <= EXPECT_KEYS
    for pat in case["expect"].get("answer_any", []) + case["expect"].get("answer_none", []):
        re.compile(pat)
    for ms in case["expect"].get("must_state", []):
        assert ms["pn"] in BY_PN and ms["field"] in BY_PN[ms["pn"]] and oracle_value(ms["pn"], ms["field"]) is not None
    for pn in case["expect"].get("ui_parts_include", []):
        assert pn in BY_PN
    for t in case["turns"]:
        assert isinstance(t, str) or (isinstance(t, dict) and "pick_option" in t)
    if any(isinstance(t, dict) for t in case["turns"]):
        assert isinstance(case["turns"][0], str)


def resp(answer, pns, alerts=None, actuators=None):
    return {
        "answer": answer,
        "ui_payload": {"actuators": actuators or [], "alerts": alerts or []},
        "debug_trace": {"tool_calls": [{"raw_output": {"actuators": [{"base_part_number": p} for p in pns]}}]},
    }


def test_oracle_verify_accepts_correct_and_rejects_wrong_row_or_unit():
    pn = "764A00-11320000/A"
    assert oracle_verify(resp(f"{pn} draws 180 W and turns in 33 s at 50 Hz.", [pn]), "x").ok
    assert oracle_verify(resp(f"{pn} draws 90 W.", [pn]), "x").ungrounded == ["90"]               # 90 W es de 763B: no está en esta fila
    assert oracle_verify(resp(f"{pn} turns in 180 s.", [pn]), "x").ungrounded == ["180 s"]       # unidad equivocada
    assert oracle_verify(resp(f"{pn} has 3.0 A at 50 Hz.", [pn]), "x").ok
    assert oracle_verify(resp(f"{pn} has 3.2 A at 50 Hz.", [pn]), "x").ok  # 3.2 A existe en la fila (60 Hz): familia A, no atribuye Hz


def test_states_value_handles_separators_and_decimals():
    assert states_value("Starts: 1,200 per hour", 1200) and states_value("Consume 3,0 A", 3.0) and states_value("33 s", 33)
    assert not states_value("Consume 13 s", 3) and not states_value("3.5 A", 3)


def test_ui_matches_oracle_detects_a_changed_field():
    g = dict(BY_PN["763B00-11300000/A"])
    ok = resp("x", [], actuators=[{k: g[k] for k in ("base_part_number", "on_off_torque_nm", "fla_60hz_amps", "csa_certified")}])
    assert ui_matches_oracle(ok) == []
    ok["ui_payload"]["actuators"][0]["on_off_torque_nm"] = 501
    assert len(ui_matches_oracle(ok)) == 1
