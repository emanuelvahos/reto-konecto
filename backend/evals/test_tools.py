from app.tools import (
    lookup_actuator_by_part_number,
    recommend_actuators,
    search_engineering_knowledge,
    reset_turn_telemetry,
    current_turn_tool_traces,
    current_turn_actuators,
    current_turn_alerts,
    fetch_ui_actuators,
)


def _codes(res):
    return [a["code"] for a in res.get("alerts", [])]


def test_tool_exact_lookup():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "763B00-11300000/A"})
    assert res["status"] == "EXACT_MATCH"
    row = res["actuators"][0]
    assert row["on_off_torque_nm"] == 500 and row["modulating_torque_nm"] == 380
    assert row["motor_power_watts"] == 90
    assert row["speed_60hz_sec"] == 26 and row["speed_50hz_sec"] == 32
    assert row["fla_60hz_amps"] == 4.8 and isinstance(row["fla_60hz_amps"], float)
    assert len(current_turn_tool_traces.get()) == 1


def test_lookup_focus_returns_only_requested_groups():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "763B00-11300000/A", "focus": ["current"]})
    row = res["actuators"][0]
    assert row["motor_power_watts"] == 90  # la potencia va siempre
    assert row["fla_60hz_amps"] == 4.8
    assert "on_off_torque_nm" not in row and "speed_60hz_sec" not in row and "table_notes" not in row


def test_tool_output_has_no_long_notes():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "763B00-11300000/A"})
    assert not ({"table_notes", "normalized_part_number", "source_page", "id"} & set(res["actuators"][0]))


def test_tool_na_3phase_lookup_returns_alternatives():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "761A00-11330C00/A"})
    assert res["status"] == "MODEL_LISTED_AS_NA"
    assert res["na_part_number"] == "761A00-11330C00/A"
    assert len(res["available_alternatives_same_size"]) >= 2
    assert "MODEL_LISTED_AS_NA" in _codes(res)
    assert len(current_turn_actuators.get()) >= 2  # alternativas registradas para la UI


def test_tool_typo_fuzzy_lookup():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "761800-11300000/A"})
    assert res["status"] == "TYPO_OR_CLOSEST_MATCH_FOUND"
    suggested_codes = [a["base_part_number"] for a in res["suggested_actuators"]]
    assert "761B00-11300000/A" in suggested_codes or "761A00-11300000/A" in suggested_codes


def test_tool_invalid_part_number():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "ZZZZZZ"})
    assert res["status"] == "INVALID_PART_NUMBER"


def test_lookup_3phase_single_torque_not_labeled_onoff_or_modulating():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "763B00-11330C00/A"})
    row = res["actuators"][0]
    assert row["single_torque_nm"] == 500
    assert not ({"on_off_torque_nm", "modulating_torque_nm", "on_off_torque_in_lbs"} & set(row))
    assert row["alert"] == "SINGLE_TORQUE_RATING"
    assert "SINGLE_TORQUE_RATING" in _codes(res)


def test_recommend_modulating_includes_3phase_with_single_torque_alert():
    reset_turn_telemetry()
    res = recommend_actuators.invoke(
        {"min_torque_nm": 2500, "application_type": "Modulating", "phase_type": "3 Phase"}
    )
    assert res["status"] == "MATCHES_FOUND"
    parts = [a["base_part_number"] for a in res["recommended_actuators"]]
    assert parts == ["765B00-11330C00/A"]  # unico 3F con torque >= 2500
    row = res["recommended_actuators"][0]
    assert "modulating_torque_nm" not in row and row["single_torque_nm"] == 3000
    assert "SINGLE_TORQUE_RATING" in _codes(res)
    alert = [a for a in current_turn_alerts.get() if a["code"] == "SINGLE_TORQUE_RATING"]
    assert alert and "único torque de salida" in alert[0]["message"]  # visible en el contexto padre


def test_recommend_modulating_with_duty_excludes_unverifiable_3phase():
    reset_turn_telemetry()
    res = recommend_actuators.invoke(
        {"min_torque_nm": 100, "application_type": "Modulating", "phase_type": "3 Phase", "min_duty_cycle_pct": 10}
    )
    assert res["status"] == "NO_EXACT_MATCH_CONSTRAINT_RELAXATION"


def test_tool_recommend_valid_and_impossible_relaxation():
    reset_turn_telemetry()
    ok = recommend_actuators.invoke(
        {"min_torque_nm": 200, "enclosure_type": "Explosionproof", "voltage_num": 24, "application_type": "Modulating"}
    )
    assert ok["status"] == "MATCHES_FOUND"
    assert ok["recommended_actuators"][0]["base_part_number"] == "763X30-11370000/A"

    impossible = recommend_actuators.invoke({"min_torque_nm": 1000, "voltage_num": 24})
    assert impossible["status"] == "NO_EXACT_MATCH_CONSTRAINT_RELAXATION"
    assert len(impossible["closest_alternative_actuators"]) > 0
    assert any("24V" in d for d in impossible["diagnostics"])


def test_relaxation_figures_come_from_db():
    reset_turn_telemetry()
    from app.database import get_db_cursor

    with get_db_cursor() as cur:
        cur.execute("SELECT MAX(GREATEST(COALESCE(on_off_torque_nm,0), COALESCE(modulating_torque_nm,0))) AS m "
                    "FROM actuators WHERE is_available AND voltage_num = 24;")
        db_max = int(cur.fetchone()["m"])
    res = recommend_actuators.invoke({"min_torque_nm": 1000, "voltage_num": 24})
    assert any(f"{db_max} Nm" in d for d in res["diagnostics"])


def test_csa_diagnostic_mentions_non_certified_sizes():
    reset_turn_telemetry()
    res = recommend_actuators.invoke({"min_torque_nm": 5000, "require_csa_certification": True})
    assert res["status"] == "NO_EXACT_MATCH_CONSTRAINT_RELAXATION"
    assert any("not CSA certified" in d for d in res["diagnostics"])


def test_ui_rows_come_from_db_in_tool_order():
    reset_turn_telemetry()
    recommend_actuators.invoke({"min_torque_nm": 200, "enclosure_type": "Explosionproof", "voltage_num": 24})
    ids = list(current_turn_actuators.get().values())
    rows = fetch_ui_actuators(ids)
    assert [r["id"] for r in rows] == ids
    assert "table_notes" not in rows[0] and "on_off_torque_nm" in rows[0]


def test_tool_search_knowledge_keyword():
    reset_turn_telemetry()
    res = search_engineering_knowledge.invoke(
        {"query": "What is the allowable voltage tolerance and are sizes 6 and 7 CSA certified?"}
    )
    assert res["status"] == "KNOWLEDGE_RETRIEVED"
    assert res["retrieval_mode"] == "keyword"
    assert res["chunks"][0]["chunk_key"] == "notes_tolerances_and_certifications"


def test_knowledge_typo_recovered_with_pg_trgm():
    reset_turn_telemetry()
    res = search_engineering_knowledge.invoke({"query": "torqe duti cicle"})
    assert res["status"] == "KNOWLEDGE_RETRIEVED" and res["retrieval_mode"] == "pg_trgm"
    assert res["chunks"][0]["chunk_key"] == "summary_electrical_metrics"


def test_knowledge_no_match_returns_no_chunks():
    reset_turn_telemetry()
    res = search_engineering_knowledge.invoke({"query": "recipe for pasta"})
    assert res["status"] == "NO_KNOWLEDGE_MATCH" and "chunks" not in res


def test_knowledge_failure_is_explicit_error_not_all_chunks(monkeypatch):
    import app.tools as t

    def boom():
        raise OSError("knowledge.json missing")

    monkeypatch.setattr(t, "_load_knowledge", boom)
    reset_turn_telemetry()
    res = search_engineering_knowledge.invoke({"query": "voltage tolerance"})
    assert res["status"] == "KNOWLEDGE_ERROR" and "chunks" not in res
