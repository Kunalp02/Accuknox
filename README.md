# Orchestrator

Multi-agent orchestrator platform — SaaS multi-tenant, async API, Qdrant RAG, OpenAI-compatible LLM gateway.

## Stack

- **API**: FastAPI + ARQ worker
- **DB**: PostgreSQL
- **Queue**: Redis
- **Vectors**: Qdrant
- **LLM / Embeddings**: OpenAI-compatible gateway (Ollama Cloud / Bifrost) — model `nomic-embed-text` for embeddings
- **Frontend**: React + Vite

## Quick start

### 1. Infrastructure

```bash
cd infra
docker compose up -d
```

### 2. Python (uv recommended)

```bash
cp .env.example .env
# Edit LLM_GATEWAY_URL and LLM_GATEWAY_KEY for your Ollama/Bifrost endpoint

pip install uv
uv sync --all-packages
```

### 3. Run API + worker

```bash
# Terminal 1 — API
uv run --package orchestrator-api uvicorn orchestrator_api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Worker
uv run --package orchestrator-worker arq orchestrator_worker.tasks.WorkerSettings
```

### 4. Frontend

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:5173

### 5. Production (Docker)

```bash
cp .env.example .env
# Edit LLM_GATEWAY_URL and secrets for production

cd infra
docker compose -f docker-compose.prod.yml up -d --build
```

Open http://localhost (web UI proxies `/v1` to API)

### Testing

```bash
# Unit tests (no Postgres required for most tests)
LLM_MOCK_MODE=true SYNC_WORKER=true uv run pytest tests/ -v

# Full API integration tests (requires Postgres on localhost:5432)
cd infra && docker compose up -d
./scripts/migrate.sh
LLM_MOCK_MODE=true SYNC_WORKER=true ./scripts/test-all-apis.sh
```

**Local dev without a separate worker:** set `SYNC_WORKER=true` in `.env`. Jobs run in-process when Redis is unavailable or sync mode is enabled.

**Test without an LLM gateway:** set `LLM_MOCK_MODE=true` for canned responses.

### Migrations

```bash
uv sync --all-packages
./scripts/migrate.sh
```

### Cursor Cloud Agent

This repo includes `.cursor/environment.json` for [Cursor Cloud Agents](https://cursor.com/docs/cloud-agent/setup). A new agent with this environment will:

1. **Build** — Ubuntu image with Docker, `uv`, and Node.js
2. **Install** — `uv sync` + `npm ci`
3. **Start** — Postgres, Redis, Qdrant, MinIO via Docker Compose + Alembic migrations
4. **Terminals** — API (`8000`), worker, Vite (`5173`)

Add `LLM_GATEWAY_URL` (and optional `LLM_GATEWAY_KEY`) as environment secrets for completed agent runs.

### Phase 2+ (this release)

- **Workflows** — graph editor (React Flow), all node types: agent, supervisor, tool, branch, parallel, human
- **MCP HTTP** — hosted HTTP connections, tool discovery, agent tool binding
- Workflow async invoke + human-in-the-loop resume (`POST /v1/runs/{id}/resume`)

## API overview

| Endpoint | Description |
|----------|-------------|
| `POST /v1/auth/signup` | Create org + user |
| `POST /v1/auth/login` | JWT login |
| `CRUD /v1/workflows` | Multi-agent workflows |
| `POST /v1/workflows/{id}/invoke` | Async workflow invoke |
| `POST /v1/runs/{id}/resume` | Resume human-in-the-loop step |
| `CRUD /v1/mcp-connections` | MCP HTTP server connections |
| `CRUD /v1/agents` | Agent management |
| `POST /v1/agents/{id}/invoke` | Async invoke → `202 { run_id }` |
| `GET /v1/runs/{id}` | Poll run status |
| `GET /v1/runs/{id}/events` | SSE event stream |
| `CRUD /v1/knowledge-bases` | Knowledge bases |
| `POST /v1/api-keys` | Create scoped API keys |

### API-as-a-product

Publish an agent or workflow, create a scoped API key, and share the integration guide:

| Step | Action |
|------|--------|
| 1 | **Publish** agent/workflow in the UI |
| 2 | Open **API product** panel → copy curl examples, or `GET /v1/agents/{id}/integration` |
| 3 | Create API key under **API keys** (scope to specific resources optional) |
| 4 | Consumer invokes → polls `GET /v1/runs/{run_id}` or streams `GET /v1/runs/{run_id}/events` |

### External invoke example

```bash
curl -X POST http://localhost:8000/v1/agents/{agent_id}/invoke \
  -H "X-API-Key: oak_..." \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello"}'
```

Poll for result:

```bash
curl http://localhost:8000/v1/runs/{run_id} -H "X-API-Key: oak_..."
```

## Environment

See `.env.example` for all variables. Key settings:

- `LLM_GATEWAY_URL` — OpenAI-compatible base URL (e.g. Bifrost/Ollama)
- `EMBED_MODEL=nomic-embed-text` — same gateway for embeddings
- `QDRANT_URL` — Qdrant HTTP API

### Ollama Cloud

Set platform defaults in `.env` or configure per-org under **Settings** in the web UI:

```bash
LLM_GATEWAY_URL=https://ollama.com/v1
OLLAMA_API_KEY=your-key-from-ollama.com/settings/keys
LLM_DEFAULT_MODEL=gpt-oss:120b
```

Use plain cloud model names (`gpt-oss:120b`), not the local offload suffix (`gpt-oss:120b-cloud`).
Test with `POST /v1/settings/llm-gateway/test` or the **Test connection** button in Settings.
