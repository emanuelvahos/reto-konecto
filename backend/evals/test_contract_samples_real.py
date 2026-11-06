"""Las muestras del contrato son datos REALES: cada actuador coincide con golden.json (0 diferencias) y todo número de parte existe."""
import json
import re
from pathlib import Path

import pytest

from app.i18n import ALERT_TITLES, DEGRADED_ALERT
from app.tools import UI_COLUMNS

HERE = Path(__file__).parent
SAMPLES = json.loads((HERE / "fixtures" / "contract_v2_samples.json").read_text(encoding="utf-8"))
GOLDEN = {g["base_part_number"]: g for g in json.loads((HERE / "oracle" / "golden.json").read_text(encoding="utf-8"))["records"]}
PN_RX = re.compile(r"\b\d{3}[A-Z]\d{2}-\d{8}(?:/[A-Z])?\b|\b\d{3}[A-Z]\d{2}-\d{4}[0-9A-Z]{4}/[A-Z]\b")
EXPECTED = {
    "single_spec_card", "comparison_table", "comparison_table_3", "three_phase_single_torque", "model_listed_as_na",
    "recommendation_with_relaxation", "recommendation_no_match", "clarification", "out_of_scope", "llm_error", "degraded_lookup", "typo_correction",
    # Fase 6
    "greeting", "capabilities", "help_menu", "catalog_overview", "ranking", "attribute_not_included", "size_clarification",
}


def _gold(g, f):
    return g["provenance"]["method"] if f == "source_method" else g["provenance"]["page"] if f == "source_page" else g[f]


def _same(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b


def test_all_expected_samples_exist():
    assert set(SAMPLES) == EXPECTED


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_actuator_matches_golden_with_zero_differences(name):
    for act in SAMPLES[name]["ui_payload"]["actuators"]:
        g = GOLDEN[act["base_part_number"]]                                  # el número de parte existe
        diffs = [f"{act['base_part_number']}.{f}: sample={act.get(f)!r} golden={_gold(g, f)!r}"
                 for f in UI_COLUMNS if f != "id" and not _same(act.get(f), _gold(g, f))]
        assert not diffs, diffs
        assert isinstance(act["source_page"], int) and act["source_method"]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_part_number_mentioned_exists(name):
    s = SAMPLES[name]
    text = json.dumps([s["answer"], s["ui_payload"].get("recommendation"), s["ui_payload"].get("suggested_followups"),
                       s["ui_payload"].get("alerts"), s["debug_trace"].get("active_context_part_numbers")], ensure_ascii=False)
    for pn in re.findall(r"76[1-7][A-Z]\d{2}-11[0-9A-Z]{6}/A", text.upper()):
        assert pn in GOLDEN, f"{name}: {pn} no existe en el catálogo"


def test_scenarios_cover_what_they_claim():
    S = SAMPLES
    assert len(S["single_spec_card"]["ui_payload"]["actuators"]) == 1 and S["single_spec_card"]["ui_payload"]["display_type"] == "SINGLE_SPEC_CARD"
    assert len(S["comparison_table"]["ui_payload"]["actuators"]) == 2 and len(S["comparison_table_3"]["ui_payload"]["actuators"]) == 3
    assert S["three_phase_single_torque"]["ui_payload"]["alerts"][0]["code"] == "SINGLE_TORQUE_RATING"
    assert "MODEL_LISTED_AS_NA" in [a["code"] for a in S["model_listed_as_na"]["ui_payload"]["alerts"]]
    rel = S["recommendation_with_relaxation"]["ui_payload"]["recommendation"]
    assert rel["relaxed_constraints"] and rel["ranking"]
    assert S["recommendation_no_match"]["ui_payload"]["recommendation"]["ranking"] == []
    c = S["clarification"]["ui_payload"]["clarification"]
    assert 2 <= len(c["options"]) <= 4 and S["clarification"]["intent"] == "clarify"
    assert [a["code"] for a in S["out_of_scope"]["ui_payload"]["alerts"]] == ["OUT_OF_SCOPE"] and S["out_of_scope"]["intent"] == "knowledge"
    d = S["degraded_lookup"]   # sin LLM: tarjeta + texto de plantilla + aviso informativo (no error)
    assert d["intent"] == "lookup" and d["ui_payload"]["display_type"] == "SINGLE_SPEC_CARD" and d["verification"]["status"] == "fallback_template"
    assert [(a["code"], a["severity"]) for a in d["ui_payload"]["alerts"]] == [("LLM_UNAVAILABLE", "info")]
    # Fase 6: sin agente libre, un texto ambiguo con el LLM caído da el menú neutro (no un error ni una recomendación al azar)
    e = S["llm_error"]
    assert e["intent"] == "clarify" and e["ui_payload"]["display_type"] == "CLARIFICATION" and not e["ui_payload"]["actuators"] and len(e["ui_payload"]["clarification"]["options"]) == 4
    for k in ("greeting", "capabilities"):
        assert S[k]["ui_payload"]["display_type"] == "TEXT_ONLY" and not S[k]["ui_payload"]["actuators"] and len(S[k]["ui_payload"]["suggested_followups"]) == 3
    assert S["help_menu"]["ui_payload"]["display_type"] == "CLARIFICATION" and len(S["help_menu"]["ui_payload"]["clarification"]["options"]) == 4
    co = S["catalog_overview"]
    assert co["intent"] == "knowledge" and co["ui_payload"]["display_type"] == "TEXT_ONLY" and co["verification"]["numbers_checked"] > 0 and not co["ui_payload"]["actuators"]
    rk = S["ranking"]
    assert rk["intent"] == "lookup" and rk["answer"].startswith("Criterio:") and rk["verification"]["numbers_checked"] > 0 and 1 <= len(rk["ui_payload"]["actuators"]) <= 4
    ab = S["attribute_not_included"]
    assert ab["ui_payload"]["display_type"] == "TEXT_ONLY" and not ab["ui_payload"]["actuators"] and "no figura" in ab["answer"]
    sc = S["size_clarification"]
    assert sc["intent"] == "clarify" and sc["ui_payload"]["display_type"] == "CLARIFICATION" and 2 <= len(sc["ui_payload"]["clarification"]["options"]) <= 4
    assert "TYPO_OR_CLOSEST_MATCH_FOUND" in [a["code"] for a in S["typo_correction"]["ui_payload"]["alerts"]]


def test_alerts_have_titles_and_nothing_invented_remains():
    blob = json.dumps(SAMPLES, ensure_ascii=False).lower()
    for s in SAMPLES.values():
        for a in s["ui_payload"]["alerts"]:
            titles = {v for t in ALERT_TITLES[a["code"]].values() for v in [t]}
            if a["severity"] == "info" and a["code"] == "LLM_UNAVAILABLE":
                titles |= set(DEGRADED_ALERT["title"].values())
            assert a["title"] and a["title"] in titles
    for invented in ("factor de servicio", "service factor", "762b20", "763a20", "(s4 "):
        assert invented not in blob
    assert not re.search(r"\b50[0-9]\b.*(?:openrouter|nvidia)|llm|modelo de lenguaje|language model", json.dumps([s["answer"] for s in SAMPLES.values()]), re.I)
