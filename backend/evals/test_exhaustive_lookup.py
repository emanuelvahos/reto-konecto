"""Exhaustivo SIN LLM: 68 filas del oráculo x todos los campos, leídos a través de la herramienta de lookup (0 diferencias).

Se comprueban las dos salidas de la herramienta:
  - la compacta que ve el LLM (grupos torque/duty/speed/current/power, con single_torque_* en trifásico), y
  - las filas de la tarjeta móvil (UI_COLUMNS, leídas de PostgreSQL por id) para TODOS los demás campos.
"""
import json
from pathlib import Path

import pytest

from app.tools import (
    FOCUS_GROUPS,
    UI_COLUMNS,
    current_turn_actuators,
    fetch_ui_actuators,
    lookup_actuator_by_part_number,
    reset_turn_telemetry,
)

GOLDEN = json.loads((Path(__file__).parent / "oracle" / "golden.json").read_text(encoding="utf-8"))["records"]
METRIC_COLS = [c for cols in FOCUS_GROUPS.values() for c in cols]
UI_FIELDS = [c for c in UI_COLUMNS if c != "id"]


def _same(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b


def _single(g):
    return g["phase_type"] == "3 Phase" and g["modulating_torque_nm"] is None and g["on_off_torque_nm"] is not None


def _compact_diffs(g, row):
    diffs = []
    for f in ("base_part_number", "power_supply", "enclosure_type"):
        if row[f] != g[f]:
            diffs.append(f"{g['base_part_number']}.{f}: tool={row[f]!r} golden={g[f]!r}")
    for col in METRIC_COLS:
        key = col.replace("on_off_torque", "single_torque") if _single(g) and col in ("on_off_torque_nm", "on_off_torque_in_lbs") else col
        if g[col] is None:
            if key in row:
                diffs.append(f"{g['base_part_number']}.{col}: tool devolvió {row[key]!r}, golden es NULL")
        elif not _same(row.get(key), g[col]):
            diffs.append(f"{g['base_part_number']}.{col}: tool={row.get(key)!r} golden={g[col]!r}")
    if _same(row.get("csa_certified", True), g["csa_certified"]) is False:
        diffs.append(f"{g['base_part_number']}.csa_certified: tool={row.get('csa_certified', True)!r} golden={g['csa_certified']!r}")
    if _single(g) != (row.get("alert") == "SINGLE_TORQUE_RATING"):
        diffs.append(f"{g['base_part_number']}: alerta SINGLE_TORQUE_RATING inconsistente")
    return diffs


def _ui_diffs(g, ui):
    return [
        f"{g['base_part_number']}.{f}: ui={ui.get(f)!r} golden={g[f]!r}"
        for f in UI_FIELDS if not _same(ui.get(f), g[f])
    ]


def test_ui_columns_cover_every_oracle_field_except_provenance_and_notes():
    covered = set(UI_FIELDS)
    expected = {k for k in GOLDEN[0] if k not in ("provenance", "table_notes", "source_page")}
    assert expected <= covered, f"campos del oráculo sin salida en la tarjeta: {sorted(expected - covered)}"


def test_every_oracle_row_through_the_lookup_tool_has_zero_differences():
    diffs, checked, na_rows = [], 0, 0
    for g in GOLDEN:
        reset_turn_telemetry()
        res = lookup_actuator_by_part_number.invoke({"part_number": g["base_part_number"]})
        if g["is_available"]:
            assert res["status"] == "EXACT_MATCH" and res["count"] == 1, g["base_part_number"]
            diffs += _compact_diffs(g, res["actuators"][0])
            ui_rows = fetch_ui_actuators(list(current_turn_actuators.get().values()))
            assert [r["base_part_number"] for r in ui_rows] == [g["base_part_number"]]
            diffs += _ui_diffs(g, ui_rows[0])
            checked += len(METRIC_COLS) + len(UI_FIELDS) + 3
        else:
            na_rows += 1
            assert res["status"] == "MODEL_LISTED_AS_NA" and res["na_part_number"] == g["base_part_number"]
            assert res["na_power_supply"] == g["power_supply"]
            assert all(g[c] is None for c in METRIC_COLS) and g["service_support"].startswith("N/A")
            by_pn = {x["base_part_number"]: x for x in GOLDEN}
            alts = res["available_alternatives_same_size"]
            assert alts, g["base_part_number"]
            for alt in alts:
                ga = by_pn[alt["base_part_number"]]
                assert ga["size_code"] == g["size_code"] and ga["is_available"]
                diffs += _compact_diffs(ga, alt)
                checked += len(METRIC_COLS) + 3
    print(f"\n{len(GOLDEN)} filas ({na_rows} N/A) via lookup: {checked} comparaciones, {len(diffs)} diferencias")
    assert not diffs, "\n".join(diffs[:40])


@pytest.mark.parametrize("variant", ["lower", "no_slash", "spaces"])
def test_part_number_normalization_variants_return_the_same_row(variant):
    for g in GOLDEN[::9]:
        pn = g["base_part_number"]
        q = {"lower": pn.lower(), "no_slash": pn.replace("/A", ""), "spaces": pn.replace("-", " - ")}[variant]
        reset_turn_telemetry()
        res = lookup_actuator_by_part_number.invoke({"part_number": q})
        got = res.get("actuators") or res.get("available_alternatives_same_size") or []
        assert res["status"] in ("EXACT_MATCH", "MODEL_LISTED_AS_NA"), (q, res["status"])
        if g["is_available"]:
            assert got[0]["base_part_number"] == pn
