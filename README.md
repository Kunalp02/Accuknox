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

### Migrations

```bash
uv sync --all-packages
./scripts/migrate.sh
```

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

### External invoke example

```bash
curl -X POST http://localhost:8000/v1/agents/{agent_id}/invoke \
  -H "X-API-Key: oak_..." \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello"}'
```

## Environment

See `.env.example` for all variables. Key settings:

- `LLM_GATEWAY_URL` — OpenAI-compatible base URL (e.g. Bifrost/Ollama)
- `EMBED_MODEL=nomic-embed-text` — same gateway for embeddings
- `QDRANT_URL` — Qdrant HTTP API
