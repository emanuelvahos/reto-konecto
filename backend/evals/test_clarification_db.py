"""Las opciones de aclaración salen de las combinaciones reales de la base (sin anotaciones inventadas)."""
import re

import pytest

from app import recommend as rec
from app.database import get_db_cursor
from app.i18n import render_clarification, resolve_clarification_answer
from app.tools import sanitize_rows


@pytest.fixture(scope="module")
def rows():
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM actuators WHERE is_available = TRUE;")
        return sanitize_rows(cur.fetchall())


def _db_combos(rows, pred=lambda r: True):
    return {(int(r["voltage_num"]), r["phase_type"] if r["phase_type"] in ("Single Phase", "3 Phase") else None) for r in rows if pred(r)}


def test_no_constraints_offers_exactly_the_real_supply_combinations(rows):
    g = rec.gate(rows, rec.clean_args({}))
    offered = {(o["args"]["voltage_num"], o["args"].get("phase_type")) for o in g["options"]}
    assert offered == _db_combos(rows) == {(24, None), (110, "Single Phase"), (220, "Single Phase"), (220, "3 Phase")}


def test_known_constraints_prune_the_options(rows):
    g = rec.gate(rows, rec.clean_args({"hazardous_area": True}))     # Explosionproof: no hay 220V trifásico
    offered = {(o["args"]["voltage_num"], o["args"].get("phase_type")) for o in g["options"]}
    assert offered == _db_combos(rows, lambda r: r["enclosure_type"] == "Explosionproof")
    assert (220, "3 Phase") not in offered
    g = rec.gate(rows, rec.clean_args({"phase_type": "3 Phase"}))     # solo trifásico: una sola combinación -> sin pregunta de voltaje
    assert g is None or g["topic"] != "voltage"


@pytest.mark.parametrize("lang", ["es", "en"])
def test_labels_are_plain_and_round_trip_through_the_resolver(rows, lang):
    g = rec.gate(rows, rec.clean_args({}))
    out = render_clarification("voltage", g["options"], lang)
    for opt, shown in zip(g["options"], out["options"]):
        assert not re.search(r"[()%]|S4|duty|ciclo", shown["label"] + shown["value"], re.I)      # sin anotaciones inventadas
        assert resolve_clarification_answer("voltage", shown["value"]) == opt["args"]
