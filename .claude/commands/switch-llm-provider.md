# Command: `/switch-llm-provider`

Switches the active LLM provider profile (defined in `backend/config/llm_profiles.json`). No re-ingest or volume change is needed (embeddings were retired).

- **NVIDIA NIM (free, development):** set `LLM_PROVIDER=nim` in `.env` (needs `LLM_API_KEY_NIM`; optional `LLM_BASE_URL_NIM`, `LLM_CHAT_MODEL_NIM`).
- **OpenRouter (default):** set `LLM_PROVIDER=openrouter` (needs `LLM_API_KEY`; defaults to `openai/gpt-4o-mini`). Paste the key into `LLM_API_KEY`; check `/health` shows `llm_configured: true`.

Then restart the backend: `docker compose up -d --build backend`. Never print API keys.
