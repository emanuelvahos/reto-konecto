from app.tools import (
    lookup_actuator_by_part_number,
    recommend_actuators,
    search_engineering_knowledge,
    reset_turn_telemetry,
    current_turn_tool_traces,
)


def test_tool_exact_lookup():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "763B00-11300000/A"})
    assert res["status"] == "EXACT_MATCH"
    assert res["actuators"][0]["on_off_torque_nm"] == 500.0
    assert res["actuators"][0]["motor_power_watts"] == 90
    assert len(current_turn_tool_traces.get()) == 1


def test_tool_na_3phase_lookup_returns_alternatives():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "761A00-11330000/A"})
    assert res["status"] == "MODEL_LISTED_AS_NA"
    assert len(res["available_alternatives_same_size"]) >= 2


def test_tool_typo_fuzzy_lookup():
    reset_turn_telemetry()
    res = lookup_actuator_by_part_number.invoke({"part_number": "761800-11300000/A"})
    assert res["status"] == "TYPO_OR_CLOSEST_MATCH_FOUND"
    suggested_codes = [a["base_part_number"] for a in res["suggested_actuators"]]
    assert "761B00-11300000/A" in suggested_codes or "761A00-11300000/A" in suggested_codes


def test_tool_recommend_valid_and_impossible_relaxation():
    reset_turn_telemetry()
    # 1. Búsqueda con resultado válido
    ok = recommend_actuators.invoke(
        {
            "min_torque_nm": 200,
            "enclosure_type": "Explosionproof",
            "voltage_num": 24,
            "application_type": "Modulating",
        }
    )
    assert ok["status"] == "MATCHES_FOUND"
    assert ok["recommended_actuators"][0]["base_part_number"] == "763X30-11370000/A"

    # 2. Búsqueda imposible (1000 Nm en 24V DC) -> Debe activar Constraint Relaxation
    impossible = recommend_actuators.invoke(
        {"min_torque_nm": 1000, "voltage_num": 24}
    )
    assert impossible["status"] == "NO_EXACT_MATCH_CONSTRAINT_RELAXATION"
    assert len(impossible["diagnostics"]) > 0
    assert len(impossible["closest_alternative_actuators"]) > 0


def test_tool_search_knowledge_vector():
    reset_turn_telemetry()
    res = search_engineering_knowledge.invoke(
        {"query": "What is the allowable voltage tolerance and are sizes 6 and 7 CSA certified?"}
    )
    assert res["status"] == "KNOWLEDGE_RETRIEVED"
    assert res["retrieval_mode"] == "vector_similarity"
    assert len(res["chunks"]) >= 1