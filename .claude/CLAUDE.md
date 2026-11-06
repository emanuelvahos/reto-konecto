## REGLAS DE TRABAJO COMPARTIDO (dos agentes en la misma carpeta y rama)
- Claude Code es dueño de backend/, docker-compose.yml, docs/ y del contrato (backend/app/schemas.py). El agente de la app (Antigravity/Gemini) es dueño de mobile-app/.
- Cada agente edita SOLO sus carpetas. Si necesita un cambio en la del otro, se lo pide al usuario.
- Commits SOLO con rutas explícitas (git add <ruta>), nunca git add -A ni git add . Antes de commitear, git status y verificar que solo van archivos propios.
- Prohibido en esta carpeta compartida: git checkout/switch, stash, reset, clean, cambiar de rama, push y --force.
- Los cambios al contrato son aditivos y los hace Claude Code; Models.kt lo mantiene el agente de la app.
- Nunca claves en archivos rastreados. Las claves viven solo en .env (ignorado por git).

# CLAUDE.md — Konecto Series 76 Neuro-Symbolic Engineering Playbook

This document defines the strict architectural invariants, physical validation laws, domain-specific PDF traps, and budget constraints enforced across the **Konecto Series 76 Heavy-Duty Electric Actuator Assistant** monorepo.

---

## REGLAS VIGENTES (prevalecen sobre lo demás)

1. La fuente de verdad de los datos es el PDF; el archivo de referencia que se creará en la Fase 1 es el oráculo de pruebas.
2. En todas las tablas del PDF el orden de las sub-columnas es 60 Hz | 50 Hz (velocidad, FLA y LRA); no hay excepciones por página.
3. Los números de parte trifásicos terminan en `11330C00/A` (los 4 N/A son `761A00`, `761B00`, `762A00`, `762B00` con ese sufijo). Los de 24V tienen sufijos propios: `11370000/A` (24V DC) y `11380000/A` (24V AC/DC).
4. Ningún número que vea el usuario puede venir del LLM.
5. Ningún diagnóstico puede llevar cifras escritas a mano en el código.

---

## 1. Core Architectural Law: Zero-Hallucination Neuro-Symbolic Execution

0. **Request pipeline (Fase 6: router → classifier → tools → verifier → template; there is NO free agent):**
   1. `router.py` (es/en deterministic rules, before any LLM): injection trimming, out-of-scope replies, conversational acts (greeting, thanks, capabilities, help, off-topic, attribute not in catalog), part-number/selection/knowledge routing, and the catalog/ranking rules that force `catalog_overview` / `rank_actuators`. Output is a `Decision` (`tools` | `reply` | `resolve` | `none`); `none` with rule `uncertain` means "the rules do not understand".
   2. `classifier.py` (only for `uncertain`): ONE structured LLM step (same provider, temperature 0, max_tokens 260, 10 s budget, one transport retry) that returns JSON validated by pydantic (act among 15, language, part references, criteria, focus, reference, ranking, overview, attribute, confidence). The user text is delimited as data. Guards: a number or part reference not present in the user text is discarded; confidence < 0.55, invalid JSON, unresolved references or LLM down → act `unclear` → neutral help menu (`CLARIFICATION`, 4 buttons, no tools, no recommendation). Never a free agent, never a random recommendation.
   3. Tools (SQL, read-only): `lookup_actuator_by_part_number`, `recommend_actuators`, `search_engineering_knowledge` (the only ones the phrasing LLM can call: `LLM_TOOLS`), plus `catalog_overview` and `rank_actuators` (forced by the router/classifier only; whitelisted metrics/aspects, N/A models never win, ties reported). Their texts come from `overview.py` (deterministic es/en, no LLM). Intents reuse existing enum values (`rank_actuators`→`lookup`, `catalog_overview`→`knowledge`).
   4. `agent.py` LLM phrasing (tool-calling with the domain system prompt) only for data turns that need prose; then `verifier.py` (every number in the final text must exist in the tool output of the turn, in the right unit family; config in `config/verifier.json`).
   5. `fallback.py` template (deterministic 1–2 sentence answer from DB rows) when the LLM fails, is too long (≈40 words with cards, ≈80 without) or the verifier rejects it twice.
   Deterministic acts/ranking/catalog/lookup-by-part work with NO LLM at all (degraded mode); ambiguous text without LLM → neutral menu. `ROUTER_ENABLED=False` survives only as a test switch (old LLM-decides-tools path used by pipeline tests). Contract is additive only: no new enum values for `intent`, `verification.status` or `display_type` without checking `Models.kt` and telling the user; `suggested_followups` ≤ 3 (the app shows `take(3)`).
1. **Deterministic Tool Authority:** The LLM is **strictly forbidden** from computing, interpolating, or recalling actuator specifications (Torque in Nm/in-lbs, Duty Cycle S4%, Operating Speed, FLA, LRA, or Motor Power) from parametric memory. Every numerical metric presented to the user MUST originate from a PostgreSQL tool execution (`lookup_actuator_by_part_number` or `recommend_actuators`).
2. **Why SQL + `pg_trgm` Beats Naive Vector RAG on Tabular PDFs:**
   - Standard chunk-and-embed RAG fails on dense multi-header electrical tables (`series_76_electric_data.pdf`) where 68 part numbers share nearly identical strings and relational inequalities (`modulating_torque_nm >= 200 AND voltage_num = 24`).
   - **Structured Catalog (`actuators` table):** Exact `NUMERIC(10,2)` columns, B-Tree and `pg_trgm` (`gin_trgm_ops`) indexes for OCR/typo recovery.
   - **Knowledge (`backend/data/knowledge.json`):** 4 fragments (text + keyword tags) from `series_76_summary.pdf` and table notes. `search_engineering_knowledge` is deterministic (keyword match, `pg_trgm` for typos, no LLM, no embeddings). pgvector was retired in Phase 2A; on failure the tool returns `KNOWLEDGE_ERROR`, never "all fragments".

---

## 2. The 5 Structural & OCR Traps in `series_76_electric_data.pdf`

Any modification to `backend/scripts/ingest.py` or `backend/app/tools.py` MUST preserve the defenses against these five catalog traps:

### Trap 1: Vertically Merged Cells (`rowspans`) in Motor Power (Watts)
- **Symptom:** In the source PDF tables, the *Motor Power (Watts)* column spans vertically across multiple actuator rows (e.g., `15W`, `40W`, `90W`, `180W`, `700W`). Naive row-by-row parsers leave `NULL` in 75% of the rows.
- **Defense:** `ingest.py` resolves all vertical spans deterministically during catalog construction, ensuring all 64 available actuator models have an explicit integer `motor_power_watts` (`NOT NULL`).

### Trap 2: 50 Hz vs 60 Hz Sub-Columns
- **Fact:** In every table (pages 1, 2 and 4) the order is `60 Hz | 50 Hz` for Operating Speed, FLA and LRA. An earlier hypothesis of per-page column swaps was wrong and was removed.
- **Defense:** `backend/scripts/build_catalog.py` / `ingest.py` map the columns into `speed_60hz_sec`, `speed_50hz_sec`, `fla_60hz_amps`, `fla_50hz_amps`, `lra_60hz_amps`, `lra_50hz_amps`. Verified against the oracle (`backend/evals/oracle/golden.json`) and by `test_spot_check_3phase_frequency_columns` (`763A00-11330C00/A`: 26 s @ 60 Hz, 32 s @ 50 Hz).

### Trap 3: Explicit `N/A` Models in 220V 3-Phase (Sizes 1 & 2)
- **Symptom:** In Page 2 (220V 3-Phase), `761A00-11330C00/A`, `761B00-11330C00/A`, `762A00-11330C00/A` and `762B00-11330C00/A` appear with `N/A` across all metrics. Dropping them would make the assistant claim the part number is a typo or does not exist.
- **Defense:** Stored with `is_available = FALSE` and `service_support = 'N/A (Not Available in 220V 3-Phase)'`. `lookup_actuator_by_part_number` returns `status = "MODEL_LISTED_AS_NA"` plus `available_alternatives_same_size` (110V / 220V single-phase of the same frame size).

### Trap 4: CSA Certification Footnote Exclusion on Frame Sizes 6 & 7
- **Symptom:** The header of Page 1 states *"CSA, CE, & UKCA Certified"*, but Footnote 7 at the bottom of the 220V Single-Phase table states: *"Sizes 6 and 7 are not CSA Certified"*.
- **Defense:** Pydantic validator `verify_physical_laws` in `ingest.py` forces `csa_certified = False` whenever `frame_size in (6, 7)` (`766A`, `766B`, `767A`, `767B`, `767C`). In `recommend_actuators`, if a user requests `require_csa = True` with torque $> 3,000\text{ Nm}$, the Constraint Relaxation Engine detects that Sizes 6 & 7 lack CSA certification and surfaces an explicit engineering warning.

### Trap 5: Optical / Typographical Corruption (`BOO` vs `800`, `8` vs `B`, `0` vs `C`)
- **Symptom:** Scanned industrial datasheets and field engineers frequently confuse `B` with `8` (`761800-11300000/A` instead of `761B00-11300000/A`, or `BOO` instead of `800` Nm).
- **Defense:**
  - **Ingestion Gate (`ActuatorRecord.verify_physical_laws`):** Enforces physical unit conversion invariants:
    $$\frac{\text{Torque (in-lbs)}}{\text{Torque (Nm)}} \in [8.2, 9.5] \quad (\text{theoretical } 1\text{ Nm} \approx 8.8507\text{ in-lbs})$$
    $$\text{LRA (Amps)} \ge \text{FLA (Amps)} \quad \forall f \in \{50\text{Hz}, 60\text{Hz}, \text{DC}\}$$
  - **Runtime Fuzzy Recovery (`lookup_actuator_by_part_number`):** Combines `pg_trgm` (`similarity() >= 0.42`) with custom Levenshtein distance ranking to recover corrupted part numbers in a single tool call (`status = "TYPO_OR_CLOSEST_MATCH_FOUND"`).

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

## 4. Two-Stage LLM Budget Strategy ($10.00 USD Cap Protection)

Provider profiles live in `backend/config/llm_profiles.json`, selected with `LLM_PROVIDER` (`openrouter` | `nim`); no model or URL is hardcoded in Python (`app/config.py`).

| Stage | `LLM_PROVIDER` | Env vars | Cost |
| :--- | :--- | :--- | :--- |
| **Development & Stress Testing (alternative)** | `nim` | `LLM_BASE_URL_NIM`, `LLM_CHAT_MODEL_NIM`, `LLM_API_KEY_NIM` | $0.00 (free tier) |
| **Default / Final Delivery** | `openrouter` (default when `LLM_PROVIDER` is unset) | `LLM_BASE_URL`, `LLM_CHAT_MODEL` (`openai/gpt-4o-mini`), `LLM_API_KEY` | list price $0.15 / $0.60 per 1M tokens (in/out) |

There are no embeddings (pgvector was retired in Phase 2A), so provider switching needs no re-ingest or volume change.

---

## 5. Mobile-First UI & Developer X-Ray Standards (`mobile-app/`)

- **Single Package Architecture:** All Kotlin sources reside under `io.konecto.series76` (`data/`, `ui/`, `util/`). Final `ui/` layout (confirmed by the app agent): `ui/login/LoginScreen.kt`, `ui/sessions/SessionsScreen.kt`, `ui/chat/ChatScreen.kt`, `ui/debug/DebugScreen.kt`, `ui/components/`, `ui/theme/` and `ui/ChatComponents.kt` (cards, comparison table, alerts).
- **Interactive Product Cards (`ChatComponents.kt`):**
  - Never display actuator specifications as a wall of raw text.
  - Render `SingleActuatorSpecCard` (for 1 model) or `ActuatorComparisonTable` (for 2+ models) with an interactive **60 Hz / 50 Hz** frequency selector chip.
  - Auto-initialize `selectedHz = 50` whenever the user query or assistant response explicitly mentions `"50Hz"` or `"50 Hz"`.
  - Strip raw Markdown bold asterisks (`**`) in `ChatBubbleItem` via `formatMarkdownBold(text): AnnotatedString`.
- **Zero-Cost On-Device Voice Normalization (`VoiceNormalizer.kt`):**
  - Transforms spoken phonetic strings in English or Spanish (*"seven six three B zero zero dash one one three zero zero zero zero zero slash A"*) into canonical part numbers (`763B00-11300000/A`) on-device at **$0.00 USD** LLM cost.
- **Hidden Developer X-Ray Debug Screen (`ui/debug/DebugScreen.kt`):**
  - Opened by **Long-Pressing (2 seconds)** the top bar title, with haptic feedback and a toast; exposes full tool traces, SQL queries, latency metrics, and active session entities.
- **Mock data is debug-only:** the mock provider and `contract_v2_samples.json` live in the `debug` sourceSet and are isolated from the release build.

