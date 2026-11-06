# Command: `/verify-physics-ingestion`

Executes the deterministic Series 76 ingestion pipeline (`backend/scripts/ingest.py`) and runs the 9-check physical & domain integrity suite (`backend/evals/test_data_integrity.py`) against PostgreSQL.

## Execution Steps

```bash
# 1. Ensure PostgreSQL container is running and healthy
docker compose up -d db

# 2. Run the ingestion & physics validation pipeline
python backend/scripts/ingest.py --mode auto

# 3. Execute the 9 data & physical integrity assertions
python -m pytest backend/evals/test_data_integrity.py -v
```

## Physical & Domain Invariants Verified

1. **Exact Row Count (`test_total_catalog_row_count`):**
   - `COUNT(*) FROM actuators == 68` (64 available models + 4 explicit `N/A` rows in 220V 3-Phase).
2. **Mechanical Unit Conversion Law (`test_physical_torque_ratio_in_lbs_to_nm`):**
   - Every available actuator satisfies:
     $$\frac{\text{Torque (in-lbs)}}{\text{Torque (Nm)}} \in [8.2, 9.5]$$
   - Prevents column swaps between `in-lbs` and `Nm` or OCR corruptions (`BOO` vs `800`).
3. **Electrical Induction Motor Law (`test_electrical_law_lra_greater_or_equal_fla`):**
   - Locked Rotor Current ($\text{LRA}$) is strictly greater than or equal to Full Load Current ($\text{FLA}$) across all frequencies ($50\text{ Hz}$, $60\text{ Hz}$, and $\text{DC}$):
     $$\text{LRA}_{f} \ge \text{FLA}_{f}$$
4. **Rowspan Propagation Completeness (`test_motor_power_rowspans_resolved`):**
   - Zero available models have `motor_power_watts IS NULL`; all values belong to $\{15, 40, 90, 180, 700\}\text{ W}$.
5. **Frequency Columns & N/A Rows (`test_spot_check_3phase_frequency_columns`):**
   - Column order is `60 Hz | 50 Hz` in every table. Confirms `763A00-11330C00/A` has `speed_60hz_sec = 26.0` and `speed_50hz_sec = 32.0`. The 4 `N/A` models (`761A`, `761B`, `762A`, `762B`, suffix `11330C00/A`) are counted in the per-table totals (`test_total_catalog_counts_per_table`).
6. **CSA Footnote Exclusion (`test_sizes_6_and_7_not_csa_certified`):**
   - Confirms all 5 models in Frame Sizes 6 and 7 (`766A`, `766B`, `767A`, `767B`, `767C`) have `csa_certified = FALSE` and `ce_ukca_certified = TRUE`.
7. **No pgvector (`test_pgvector_retired`):**
   - Confirms the `vector` extension and `knowledge_chunks` table no longer exist; knowledge lives in `backend/data/knowledge.json`.

