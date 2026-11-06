# Konecto Series 76 Assistant — Automated Evaluation Report

- **Model Configured:** `openai/gpt-4o-mini`
- **Provider:** `openrouter`
- **Evaluation Client:** `In-Process TestClient`
- **Total Scenarios:** `11`
- **Execution Timestamp:** `2026-11-06 18:03:58 UTC`

| ID | Category | Scenario | Turns | Latency (ms) | Tools Invoked | Status |
|---|---|---|---|---|---|---|
| `EVAL-01` | Specific Data Retrieval | Exact lookup of 763B00-11300000/A (110V 1-Phase Weatherproof) | 1 | 4736 | `lookup_actuator_by_part_number` | ✅ PASS |
| `EVAL-02` | Multi-Turn Coreference | 3-turn follow-up on 764A00-11320000/A resolving 'it' across turns | 3 | 6913 | `lookup_actuator_by_part_number` | ✅ PASS |
| `EVAL-03` | Specific Data Retrieval | Lookup 763A00-11330C00/A (220V 3-Phase speed 50Hz vs 60Hz) | 1 | 2294 | `lookup_actuator_by_part_number` | ✅ PASS |
| `EVAL-04` | Edge Case: N/A Model | Querying 761A00-11330C00/A which is N/A in 220V 3-Phase table | 1 | 6417 | `lookup_actuator_by_part_number` | ✅ PASS |
| `EVAL-05` | Edge Case: Typo Fuzzy Match | Querying corrupted part number 761800-11300000/A (8 instead of B) | 1 | 3428 | `lookup_actuator_by_part_number` | ✅ PASS |
| `EVAL-06` | Edge Case: Invalid Part Number | Querying non-existent part number 999Z99-00000000/Z | 1 | 2048 | `lookup_actuator_by_part_number` | ✅ PASS |
| `EVAL-07` | Product Recommendation | Recommend Explosionproof actuator with >= 200 Nm Modulating torque on 24V DC | 1 | 2787 | `recommend_actuators` | ✅ PASS |
| `EVAL-08` | Edge Case: CSA Footnote Trap | Requesting 6,000 Nm actuator with mandatory CSA Certification | 1 | 3016 | `recommend_actuators` | ✅ PASS |
| `EVAL-09` | Edge Case: Impossible Requirement | Requesting 1,500 Nm actuator running on 24V DC power supply | 1 | 3064 | `recommend_actuators` | ✅ PASS |
| `EVAL-10` | Edge Case: Ambiguous Service Type | 110V Explosionproof 450 Nm without service type: clarify, then resolve | 2 | 4461 | `recommend_actuators` | ✅ PASS |
| `EVAL-11` | Engineering Rules & Knowledge | Checking allowable voltage tolerance (+/-10%) and hazardous location ratings | 1 | 2764 | `search_engineering_knowledge` | ✅ PASS |

## Summary: **11/11 Scenarios Passed (100.0%)**