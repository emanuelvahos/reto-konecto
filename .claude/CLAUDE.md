# CLAUDE.md — Konecto Series 76 Neuro-Symbolic Engineering Playbook

This document defines the strict architectural invariants, physical validation laws, domain-specific PDF traps, and budget constraints enforced across the **Konecto Series 76 Heavy-Duty Electric Actuator Assistant** monorepo.

---

## REGLAS VIGENTES (prevalecen sobre lo demás)

1. La fuente de verdad de los datos es el PDF; el archivo de referencia que se creará en la Fase 1 es el oráculo de pruebas.
2. Las afirmaciones sobre columnas 50/60 Hz "invertidas" en las páginas 2 y 4 son FALSAS: en todas las tablas el orden es 60 Hz | 50 Hz; no las preserves.
3. Los números de parte trifásicos reales terminan en `11330C00` (no `11330000`).
4. Ningún número que vea el usuario puede venir del LLM.
5. Ningún diagnóstico puede llevar cifras escritas a mano en el código.

---

## 1. Core Architectural Law: Zero-Hallucination Neuro-Symbolic Execution

1. **Deterministic Tool Authority:** The LLM is **strictly forbidden** from computing, interpolating, or recalling actuator specifications (Torque in Nm/in-lbs, Duty Cycle S4%, Operating Speed, FLA, LRA, or Motor Power) from parametric memory. Every numerical metric presented to the user MUST originate from a PostgreSQL tool execution (`lookup_actuator_by_part_number` or `recommend_actuators`).
2. **Why Hybrid SQL + `pg_trgm` + `pgvector` Beats Naive Vector RAG on Tabular PDFs:**
   - Standard chunk-and-embed RAG fails catastrophically on dense multi-header electrical tables (`series_76_electric_data.pdf`) where 68 part numbers share nearly identical strings (`761A00-11300000/A` vs `761A00-11320000/A` vs `761A00-11330000/A`) and relational inequalities (`modulating_torque_nm >= 200 AND voltage_num = 24`).
   - **Structured Catalog (`actuators` table):** Exact `NUMERIC(10,2)` columns for all 68 catalog rows, indexed with B-Tree and `pg_trgm` (`gin_trgm_ops`) for OCR/typo recovery.
   - **Semantic Knowledge Base (`knowledge_chunks` table):** `pgvector` cosine similarity search exclusively for conceptual definitions (`series_76_summary.pdf`), operating tolerances ($\pm 10\%$ voltage, $\pm 5\%$ frequency), and hazardous location ratings (`Class I, Div 1, Groups C, D, T4 | Ex d IIB T4 Gb`).

---

## 2. The 5 Structural & OCR Traps in `series_76_electric_data.pdf`

Any modification to `backend/scripts/ingest.py` or `backend/app/tools.py` MUST preserve the defenses against these five catalog traps:

### Trap 1: Vertically Merged Cells (`rowspans`) in Motor Power (Watts)
- **Symptom:** In the source PDF tables, the *Motor Power (Watts)* column spans vertically across multiple actuator rows (e.g., `15W`, `40W`, `90W`, `180W`, `700W`). Naive row-by-row parsers leave `NULL` in 75% of the rows.
- **Defense:** `ingest.py` resolves all vertical spans deterministically during catalog construction, ensuring all 64 available actuator models have an explicit integer `motor_power_watts` (`NOT NULL`).

### Trap 2: Inverted `50 Hz` vs `60 Hz` Sub-Column Headers Across Pages — EN REVISIÓN, ver REGLAS VIGENTES
- **Symptom:**
  - **Page 1 (Weatherproof 110V & 220V 1-Phase):** Speed, FLA, and LRA sub-columns are ordered `60 Hz (left) | 50 Hz (right)`.
  - **Page 2 (Weatherproof 220V 3-Phase):** Operating Speed and LRA invert the order to `50 Hz (left) | 60 Hz (right)`, while FLA remains `60 Hz (left) | 50 Hz (right)`.
  - **Page 4 (Explosionproof 110V 1-Phase):** LRA is inverted to `50 Hz (left) | 60 Hz (right)`.
  - **Page 4 (Explosionproof 220V 1-Phase):** FLA is inverted to `50 Hz (left) | 60 Hz (right)`.
- **Defense:** `build_verified_catalog()` in `backend/scripts/ingest.py` explicitly maps each table's exact column header permutation into canonical database columns (`speed_60hz_sec`, `speed_50hz_sec`, `fla_60hz_amps`, `fla_50hz_amps`, `lra_60hz_amps`, `lra_50hz_amps`). Verified by `EVAL-03` (`763A00-11330000/A`: 32s @ 50Hz vs 26s @ 60Hz).

### Trap 3: Explicit `N/A` Models in 220V 3-Phase (Sizes 1 & 2) — EN REVISIÓN, ver REGLAS VIGENTES
- **Symptom:** In Page 2 (220V 3-Phase), frame sizes 1 and 2 (`761A00-11330000/A`, `761B00-11330000/A`, `762A00-11330000/A`, `762B00-11330000/A`) appear in the table with `N/A` across all metrics. Dropping them during ingestion would cause the assistant to falsely claim the part number is a typo or does not exist.
- **Defense:** Stored in PostgreSQL with `is_available = FALSE` and `service_support = 'N/A (Not Available in 220V 3-Phase)'`. When queried via `lookup_actuator_by_part_number`, the tool returns `status = "MODEL_LISTED_AS_NA"` and automatically queries available 110V/220V Single-Phase equivalents of the same frame size (`available_alternatives_same_size`).

### Trap 4: CSA Certification Footnote Exclusion on Frame Sizes 6 & 7
- **Symptom:** The header of Page 1 states *"CSA, CE, & UKCA Certified"*, but Footnote 7 at the bottom of the 220V Single-Phase table states: *"Sizes 6 and 7 are not CSA Certified"*.
- **Defense:** Pydantic validator `verify_physical_laws` in `ingest.py` forces `csa_certified = False` whenever `frame_size in (6, 7)` (`766A`, `766B`, `767A`, `767B`, `767C`). In `recommend_actuators`, if a user requests `require_csa = True` with torque $> 3,000\text{ Nm}$, the Constraint Relaxation Engine detects that Sizes 6 & 7 lack CSA certification and surfaces an explicit engineering warning.

### Trap 5: Optical / Typographical Corruption (`BOO` vs `800`, `8` vs `B`, `0` vs `C`)
- **Symptom:** Scanned industrial datasheets and field engineers frequently confuse `B` with `8` (`761800-11300000/A` instead of `761B00-11300000/A`, or `BOO` instead of `800` Nm).
- **Defense:**
  - **Ingestion Gate (`ActuatorRecord.verify_physical_laws`):** Enforces physical unit conversion invariants:
    $$\frac{\text{Torque (in-lbs)}}{\text{Torque (Nm)}} \in [8.2, 9.5] \quad (\text{theoretical } 1\text{ Nm} \approx 8.8507\text{ in-lbs})$$
    $$\text{LRA (Amps)} \ge \text{FLA (Amps)} \quad \forall f \in \{50\text{Hz}, 60\text{Hz}, \text{DC}\}$$
  - **Runtime Fuzzy Recovery (`lookup_actuator_by_part_number`):** Combines `pg_trgm` (`similarity() >= 0.45`) with custom Levenshtein distance ranking to recover corrupted part numbers in a single tool call (`status = "FUZZY_SUGGESTIONS"`).

---

## 3. Telemetry & `ContextVar` In-Place Mutation Convention (`backend/app/tools.py`)

- **Critical Implementation Rule:** LangChain's `AgentExecutor` / LangGraph executes synchronous `@tool` functions inside isolated child `contextvars.Context` copies (`copy_context().run(...)`).
- If a tool calls `current_turn_tool_traces.set(new_list)` inside its body, that rebinding only mutates the child context and is **invisible** to the parent FastAPI request coroutine.
- **Required Pattern:**
  1. At the start of each turn (`reset_turn_telemetry()`), bind a fresh mutable container (`list` / `dict`) in the parent context.
  2. Inside tools (`record_tool_trace`, `register_ui_actuators`), **always mutate the container in-place**:
     ```python
     current_turn_tool_traces.get().append({...})
     current_turn_actuators.get()[row["id"]] = row
     ```
  3. Never replace `.get().append()` with `.set()` inside a tool function.

---

## 4. Two-Stage LLM & Embedding Budget Strategy ($10.00 USD Cap Protection)

To respect the evaluation API key's **$10.00 USD limit** while running hundreds of automated unit, integration, and multi-turn E2E tests:

| Stage | Provider & Base URL | Chat Model | Embedding Model (Dims) | Cost on Evaluation Key |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 1: Development & Stress Testing** | **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`) | `nvidia/nemotron-3.5-lightning-30b-a3b` | `nvidia/nemotron-3-embed-1b` (`2048` dims) | **$0.00 USD** (Free Developer Tier) |
| **Stage 2: Production & Final Delivery** | **OpenRouter** (`https://openrouter.ai/api/v1`) | `openai/gpt-4o-mini` ($0.15/1M in, $0.60/1M out) | `openai/text-embedding-3-small` (`1536` dims, $0.02/1M) | **< $0.05 USD** per full 11-scenario eval suite |

- **Zero-Friction Provider Switching:** `backend/scripts/ingest.py` reads `EMBEDDING_DIMENSIONS` from `.env` (`1536` for OpenRouter, `2048` for NVIDIA NIM) and automatically executes:
  ```sql
  TRUNCATE TABLE knowledge_chunks RESTART IDENTITY;
  ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(<EMBEDDING_DIMENSIONS>);
  ```
  before generating and inserting the 4 knowledge chunk embeddings. No volume deletion or manual SQL editing is ever required.

---

## 5. Mobile-First UI & Developer X-Ray Standards (`mobile-app/`)

- **Single Package Architecture:** All Kotlin sources reside under `io.konecto.series76` (`data/`, `ui/`, `util/`) for immediate navigation in Android Studio.
- **Interactive Product Cards (`ChatComponents.kt`):**
  - Never display actuator specifications as a wall of raw text.
  - Render `SingleActuatorSpecCard` (for 1 model) or `ActuatorComparisonTable` (for 2+ models) with an interactive **60 Hz / 50 Hz** frequency selector chip.
  - Auto-initialize `selectedHz = 50` whenever the user query or assistant response explicitly mentions `"50Hz"` or `"50 Hz"`.
  - Strip raw Markdown bold asterisks (`**`) in `ChatBubbleItem` via `formatMarkdownBold(text): AnnotatedString`.
- **Zero-Cost On-Device Voice Normalization (`VoiceNormalizer.kt`):**
  - Transforms spoken phonetic strings in English or Spanish (*"seven six three B zero zero dash one one three zero zero zero zero zero slash A"*) into canonical part numbers (`763B00-11300000/A`) on-device at **$0.00 USD** LLM cost.
- **Hidden Developer X-Ray Debug Screen (`Screens.kt`):**
  - Unlocked by **Long-Pressing (2 seconds)** the top navigation bar title, exposing full tool traces, SQL queries, latency metrics, and active session entities.

