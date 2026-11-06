"""heldout.json (casos ciegos escritos por un subagente sin acceso al router ni a adversarial.json): bien formado y verificable contra golden.json."""
import json
import re
from pathlib import Path

import pytest

from oracle_check import BY_PN, oracle_value
from test_adversarial_cases import EXPECT_KEYS

DOC = json.loads((Path(__file__).parent / "heldout.json").read_text(encoding="utf-8"))
CASES = DOC["cases"]


def test_forty_unique_cases_covering_the_requested_categories():
    assert len(CASES) == 40 and len({c["id"] for c in CASES}) == 40
    cats = {c["category"] for c in CASES}
    assert len(cats) >= 12 and {c["lang"] for c in CASES} >= {"es", "en", "mixed"}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_is_well_formed(case):
    assert case["turns"] and set(case["expect"]) <= EXPECT_KEYS
    for pat in case["expect"].get("answer_any", []) + case["expect"].get("answer_none", []):
        re.compile(pat)
    for ms in case["expect"].get("must_state", []):
        assert ms["pn"] in BY_PN and oracle_value(ms["pn"], ms["field"]) is not None
    for pn in case["expect"].get("ui_parts_include", []):
        assert pn in BY_PN
