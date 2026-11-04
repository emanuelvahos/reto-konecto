# Command: `/switch-llm-provider`

Switches the active LLM and Embedding provider between **NVIDIA NIM (Free Development Tier, 2048 dims)** and **OpenRouter (Production Evaluation Delivery, 1536 dims)** without dropping PostgreSQL volumes or losing conversation history.

## Option A: Switch to OpenRouter (Production Delivery — `< $0.25 USD` Total Budget)

1. Update `.env` with the OpenRouter configuration:
   ```dotenv
   LLM_BASE_URL=https://openrouter.ai/api/v1
   LLM_API_KEY=<YOUR_OPENROUTER_API_KEY>
   LLM_CHAT_MODEL=openai/gpt-4o-mini
   LLM_VISION_MODEL=google/gemini-2.5-flash
   EMBEDDING_MODEL=openai/text-embedding-3-small
   EMBEDDING_DIMENSIONS=1536
   ```
2. Re-run ingestion to dynamically alter `knowledge_chunks.embedding` to `vector(1536)` and generate the 4 OpenRouter embeddings (costs ~$0.00002 USD):
   ```bash
   python backend/scripts/ingest.py --mode auto
   ```
3. Rebuild/restart the backend container so FastAPI picks up the updated `.env`:
   ```bash
   docker compose up -d --build backend
   ```
4. Verify vector similarity mode (`retrieval_mode == "vector_similarity"`):
   ```bash
   python -m pytest backend/evals/test_tools.py -k test_tool_semantic_knowledge_search -v
   ```

---

## Option B: Switch to NVIDIA NIM (Zero-Cost Development & Stress Testing)

1. Update `.env` with the NVIDIA NIM configuration:
   ```dotenv
   LLM_BASE_URL=https://integrate.api.nvidia.com/v1
   LLM_API_KEY=<YOUR_NVIDIA_NIM_KEY>
   LLM_CHAT_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b
   LLM_VISION_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b
   EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b
   EMBEDDING_DIMENSIONS=2048
   ```
2. Re-run ingestion to dynamically alter `knowledge_chunks.embedding` to `vector(2048)`:
   ```bash
   python backend/scripts/ingest.py --mode auto
   ```
3. Restart backend container:
   ```bash
   docker compose up -d --build backend
   ```

