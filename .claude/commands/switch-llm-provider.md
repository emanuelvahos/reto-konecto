# Command: `/switch-llm-provider`

Switches the active LLM provider profile (defined in `backend/config/llm_profiles.json`). No re-ingest or volume change is needed (embeddings were retired).

- **NVIDIA NIM (free, development):** set `LLM_PROVIDER=nim` in `.env` (needs `LLM_API_KEY_NIM`; optional `LLM_BASE_URL_NIM`, `LLM_CHAT_MODEL_NIM`).
- **OpenRouter (final delivery, real balance is tiny):** set `LLM_PROVIDER=openrouter` (needs `LLM_API_KEY`; defaults to `openai/gpt-4o-mini`). Use it for ONE final run only.

Then restart the backend: `docker compose up -d --build backend`. Never print API keys.
