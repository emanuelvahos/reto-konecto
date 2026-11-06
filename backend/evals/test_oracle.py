"""Oráculo: DB vs backend/evals/oracle/golden.json, 68 filas x todos los campos, tolerancia 0."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from test_data_integrity import db_conn  # noqa: F401  (fixture)

GOLDEN = json.loads((Path(__file__).parent / "oracle" / "golden.json").read_text(encoding="utf-8"))["records"]
# Todo campo del golden salvo la procedencia (no se persiste en la tabla).
FIELDS = [k for k in GOLDEN[0] if k != "provenance"]


def _norm(v):
    if isinstance(v, Decimal):
        return float(v) if v != v.to_integral_value() else int(v)
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


def test_golden_has_68_unique_rows():
    assert len(GOLDEN) == 68
    assert len({r["base_part_number"] for r in GOLDEN}) == 68


def test_golden_provenance_is_recorded():
    for r in GOLDEN:
        assert r["provenance"]["method"] in ("A=B", "A+B+humano")
        assert r["provenance"]["page"] == r["source_page"]


def test_db_matches_golden_all_fields_zero_tolerance(db_conn):  # noqa: F811
    with db_conn.cursor() as cur:
        cur.execute("SELECT * FROM actuators;")
        db = {r["base_part_number"]: r for r in cur.fetchall()}
    assert set(db) == {g["base_part_number"] for g in GOLDEN}, "El conjunto de números de parte difiere del oráculo"
    mismatches = []
    checked = 0
    for g in GOLDEN:
        row = db[g["base_part_number"]]
        for f in FIELDS:
            checked += 1
            if _norm(row[f]) != _norm(g[f]):
                mismatches.append(f"{g['base_part_number']}.{f}: db={row[f]!r} golden={g[f]!r}")
    print(f"\n{len(GOLDEN)} filas x {len(FIELDS)} campos = {checked} comparaciones, {len(mismatches)} diferencias")
    assert not mismatches, "\n".join(mismatches[:40])
