# Command: `/run-e2e-harness`

Runs the complete 4-tier verification harness across Data Integrity, Deterministic SQL/Vector Tools, FastAPI Multi-Turn Persistence, and the 11-Scenario End-to-End Evaluation Suite.

## Execution Steps

```bash
# Tier 1: Physical & Catalog Integrity (9 checks, $0.00 LLM cost)
python -m pytest backend/evals/test_data_integrity.py -v

# Tier 2: Deterministic Tool & pgvector Retrieval Verification (5 checks)
python -m pytest backend/evals/test_tools.py -v

# Tier 3: JWT Auth, Multi-Turn Coreference & PostgreSQL Persistence (2 E2E checks)
python -m pytest backend/evals/test_api_e2e.py -v

# Tier 4: Full 11-Scenario Automated Benchmark & Markdown Report Generation
python backend/evals/run_evals.py -v
```

## Targeted Single-Scenario Debugging (Budget-Saving Mode)

When iterating on a specific prompt or edge case, run a single scenario instead of all 11 to preserve API budget:

```bash
# Run only EVAL-02 (3-turn coreference resolution) against in-process TestClient
python backend/evals/run_evals.py --scenario EVAL-02 -v

# Run against live Docker container on port 8001 with JWT authentication
python backend/evals/run_evals.py --live --auth --scenario EVAL-08 -v
```

## Expected Output Artifacts

- All `pytest` suites exit with status code `0` (`16/16` unit & integration checks green).
- `backend/evals/EVALUATION_REPORT.md` is updated with per-scenario latency (ms), invoked tools, and pass rate (`11/11 Scenarios Passed - 100.0%`).

