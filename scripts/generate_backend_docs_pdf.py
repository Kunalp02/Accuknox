#!/usr/bin/env python3
"""Generate Orchestrator backend documentation PDF."""

from datetime import date
from pathlib import Path

from fpdf import FPDF


class DocPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Orchestrator Backend Documentation", align="R")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def title_page(self):
        self.add_page()
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(30, 30, 30)
        self.ln(40)
        self.cell(0, 14, "Orchestrator Platform", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 18)
        self.set_text_color(60, 60, 60)
        self.cell(0, 10, "Backend Architecture & Working Flow", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(8)
        self.set_font("Helvetica", "", 12)
        self.cell(0, 8, f"Updated: {date.today().isoformat()}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 8, "Repository: Accuknox / Orchestrator", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(20)
        self.set_font("Helvetica", "", 11)
        self.set_x(self.l_margin)
        self.multi_cell(
            self._content_width(),
            6,
            "Multi-tenant SaaS orchestrator: FastAPI API, ARQ worker, PostgreSQL, Redis, "
            "Qdrant RAG, OpenAI-compatible LLM gateway, agents, workflows, MCP HTTP, "
            "knowledge bases, API keys, runs/trace, and webhooks.",
        )

    def _content_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def h1(self, text: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(25, 55, 95)
        self.set_x(self.l_margin)
        self.multi_cell(self._content_width(), 10, text)
        self.ln(2)

    def h2(self, text: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(40, 70, 110)
        self.set_x(self.l_margin)
        self.multi_cell(self._content_width(), 8, text)
        self.ln(1)

    def h3(self, text: str):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(50, 50, 50)
        self.set_x(self.l_margin)
        self.multi_cell(self._content_width(), 7, text)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5, text)
        self.ln(2)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5, f"- {text}")

    def code_block(self, text: str):
        self.set_font("Courier", "", 9)
        self.set_fill_color(245, 245, 245)
        self.set_text_color(20, 20, 20)
        for line in text.split("\n"):
            self.cell(0, 5, "  " + line, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(3)

    def table(self, headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None):
        total = int(self._content_width())
        if col_widths is None:
            w = int(total / len(headers))
            col_widths = [w] * len(headers)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(230, 235, 240)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        for row in rows:
            max_lines = 1
            cell_lines = []
            for i, cell in enumerate(row):
                lines = self.multi_cell(col_widths[i], 5, cell, dry_run=True, output="LINES")
                cell_lines.append(lines)
                max_lines = max(max_lines, len(lines))
            y_start = self.get_y()
            x_start = self.get_x()
            for i, lines in enumerate(cell_lines):
                self.set_xy(x_start + sum(col_widths[:i]), y_start)
                for j, line in enumerate(lines):
                    self.set_xy(x_start + sum(col_widths[:i]), y_start + j * 5)
                    self.cell(col_widths[i], 5, line, border=0)
            self.set_xy(x_start, y_start + max_lines * 5)
            # draw row border
            self.set_draw_color(200, 200, 200)
            self.line(x_start, self.get_y(), x_start + sum(col_widths), self.get_y())
        self.ln(4)


def build_pdf(output: Path) -> None:
    pdf = DocPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.title_page()

    # 1. Overview
    pdf.add_page()
    pdf.h1("1. Overview")
    pdf.body(
        "Orchestrator is a multi-agent orchestration platform designed as multi-tenant SaaS. "
        "The backend exposes a REST API (FastAPI) for configuration and invocation. Long-running "
        "work (agent runs, workflow runs, document indexing) is delegated to an ARQ worker via Redis. "
        "All tenant data is scoped by organization_id."
    )
    pdf.h2("Core capabilities")
    pdf.bullet("JWT login and scoped API keys (oak_...) for external invoke")
    pdf.bullet("Agents with system prompts, models, RAG knowledge bases, and MCP tools")
    pdf.bullet("Workflow graphs: agent, supervisor, tool, branch, parallel, human-in-the-loop nodes")
    pdf.bullet("Async invoke returns 202 + run_id; poll GET /runs/{id} or SSE /runs/{id}/events")
    pdf.bullet("Per-org LLM gateway config (OpenAI-compatible) with SSL/proxy controls")
    pdf.bullet("Usage tracking, webhooks on run completion, RBAC roles")

    # 2. Architecture
    pdf.h1("2. System Architecture")
    pdf.body(
        "Three runtime processes plus infrastructure services. The API is stateless; the worker "
        "owns execution. Redis carries job queue and real-time run events."
    )
    pdf.code_block(
        "  [Client / UI / External API]\n"
        "           |\n"
        "           v\n"
        "  +------------------+     enqueue      +------------------+\n"
        "  |  FastAPI (API)   | ----------------> |  Redis (ARQ)     |\n"
        "  |  port 8000       |                   |  + pub/sub SSE   |\n"
        "  +------------------+                   +------------------+\n"
        "           |                                      |\n"
        "           v                                      v\n"
        "  +------------------+                   +------------------+\n"
        "  |  PostgreSQL      |                   |  ARQ Worker      |\n"
        "  |  (all entities)  | <---------------- |  execute_* jobs  |\n"
        "  +------------------+                   +------------------+\n"
        "                                                  |\n"
        "                    +-----------------------------+\n"
        "                    v\n"
        "  +----------+  +----------+  +------------------------+\n"
        "  | Qdrant   |  | MinIO    |  | LLM Gateway (OpenAI)   |\n"
        "  | vectors  |  | docs/S3  |  | chat + embeddings      |\n"
        "  +----------+  +----------+  +------------------------+"
    )

    pdf.h2("Technology stack")
    pdf.table(
        ["Layer", "Technology"],
        [
            ["API", "FastAPI, Uvicorn, Pydantic v2"],
            ["Worker", "ARQ (async Redis queue)"],
            ["Database", "PostgreSQL 16, SQLAlchemy 2 async, Alembic"],
            ["Queue / Events", "Redis 7 (jobs + pub/sub for SSE)"],
            ["Vectors", "Qdrant (per-org collections)"],
            ["LLM", "OpenAI-compatible HTTP (Ollama, Bifrost, corporate gateway)"],
            ["Auth", "JWT (users) + hashed API keys"],
            ["Monorepo", "uv workspace: packages + apps"],
        ],
        [50, 140],
    )

    # 3. Project structure
    pdf.add_page()
    pdf.h1("3. Project Structure")
    pdf.code_block(
        "Accuknox/\n"
        "  apps/\n"
        "    api/          orchestrator_api - FastAPI routes, deps, guards\n"
        "    worker/       orchestrator_worker - ARQ task functions\n"
        "    web/          React frontend (not covered here)\n"
        "  packages/\n"
        "    core/         models, config, DB, security, RBAC, usage\n"
        "    llm/          OpenAI client, gateway resolution, embeddings\n"
        "    rag/          chunking, Qdrant store\n"
        "    mcp/          MCP HTTP client, tool discovery\n"
        "    runtime/      agent + workflow execution engine\n"
        "    events/       Redis EventPublisher for run SSE\n"
        "  infra/          docker-compose (postgres, redis, qdrant, minio)\n"
        "  scripts/        migrate.sh, cloud-agent scripts\n"
        "  tests/          integration tests (pytest)"
    )

  # 4. Authentication
    pdf.h1("4. Authentication & Authorization")
    pdf.h2("Auth modes")
    pdf.bullet("Bearer JWT: from POST /v1/auth/login or /signup; contains sub, org_id, role")
    pdf.bullet("X-API-Key or Bearer oak_...: scoped API key with scopes and optional resource_ids")
    pdf.body(
        "AuthContext (deps.py) resolves org_id for every request. API keys cannot access "
        "settings, knowledge upload, or MCP management unless scope allows invoke/read."
    )
    pdf.h2("RBAC roles (rbac.py)")
    pdf.table(
        ["Role", "Summary"],
        [
            ["owner", "Full org control including org:write, api keys, all resources"],
            ["admin", "Like owner minus org:write"],
            ["builder", "Create/edit agents, workflows, KB, MCP; invoke runs"],
            ["viewer", "Read-only across agents, workflows, KB, MCP, runs"],
        ],
        [45, 145],
    )
    pdf.h2("API key scopes")
    pdf.bullet("agent:invoke, workflow:invoke, run:read (typical external integration)")
    pdf.bullet("resource_ids limits key to specific agent/workflow UUIDs")
    pdf.bullet("rate_limit_per_minute per key; org-level limit via ORG_RATE_LIMIT_PER_MINUTE")

    # 5. API routes
    pdf.add_page()
    pdf.h1("5. API Routes Summary")
    pdf.body("All business routes are under /v1. Health check: GET /health")
    pdf.table(
        ["Prefix / Route", "Description"],
        [
            ["POST /v1/auth/signup", "Create org + owner user, return JWT"],
            ["POST /v1/auth/login", "Email/password login"],
            ["GET /v1/auth/me", "Current user profile"],
            ["CRUD /v1/agents", "Agent management; POST /{id}/publish"],
            ["POST /v1/agents/{id}/invoke", "Async agent run (202, run_id)"],
            ["CRUD /v1/workflows", "Graph workflows; validate + publish"],
            ["POST /v1/workflows/{id}/invoke", "Async workflow run"],
            ["POST /v1/runs/{id}/resume", "Resume human-in-the-loop step"],
            ["GET /v1/runs, /runs/{id}", "List and poll run status"],
            ["GET /v1/runs/{id}/events", "SSE stream of run events"],
            ["CRUD /v1/knowledge-bases", "KB + document upload/index"],
            ["CRUD /v1/mcp-connections", "MCP HTTP servers + discover tools"],
            ["CRUD /v1/api-keys", "Create/list/revoke API keys"],
            ["GET /v1/usage", "Daily usage aggregates"],
            ["GET/PUT/DELETE /v1/settings/llm-gateway", "Per-org gateway config"],
            ["POST /v1/settings/llm-gateway/test", "Ping gateway via chat completion"],
        ],
        [70, 120],
    )

    # 6. Agent invoke flow
    pdf.h1("6. Agent Invoke Flow")
    pdf.body("End-to-end path when a client calls POST /v1/agents/{agent_id}/invoke:")
    pdf.code_block(
        "1. API: authenticate, rate limit, check agent exists + published (if API key)\n"
        "2. API: create Run row (status=pending, input={message, context})\n"
        "3. API: enqueue ARQ job execute_agent_run(run_id) on Redis\n"
        "4. API: return 202 { run_id, status: pending }\n"
        "5. Worker: load Run, set status=running, publish run.status event\n"
        "6. Worker: load Agent, get_gateway_for_org(), build_agent_config()\n"
        "7. Worker: load_mcp_clients() for org\n"
        "8. Worker: execute_agent() - RAG retrieval, MCP tool loop, LLM chat\n"
        "9. Worker: on each token/event -> Redis pub/sub + append run.trace\n"
        "10. Worker: set status=completed/failed, record usage, webhook POST\n"
        "11. Client: poll GET /runs/{id} or SSE GET /runs/{id}/events"
    )
    pdf.h2("execute_agent (runtime/agent.py)")
    pdf.bullet("Embeds user query; searches Qdrant for bound knowledge_base_ids")
    pdf.bullet("Injects retrieved chunks into system context")
    pdf.bullet("If MCP tools bound: OpenAI function-calling loop (max 8 rounds)")
    pdf.bullet("Returns output text + metrics (tokens_in, tokens_out)")

    # 7. Workflow flow
    pdf.add_page()
    pdf.h1("7. Workflow Execution Flow")
    pdf.body(
        "Workflows store a JSON graph: entry node id, nodes array, edges array. "
        "Invoke enqueues execute_workflow_run. Node types supported in runtime:"
    )
    pdf.table(
        ["Node type", "Behavior"],
        [
            ["agent", "Run linked agent or inline prompt/model config"],
            ["supervisor", "LLM routes to child agents (children list)"],
            ["tool", "Call MCP tool on connection_id + tool_name"],
            ["branch", "Conditional edges (route == value, variables.key)"],
            ["parallel", "Run children concurrently (asyncio.gather)"],
            ["human", "Pause run; status=awaiting_input; checkpoint saved"],
        ],
        [55, 135],
    )
    pdf.h2("Human-in-the-loop resume")
    pdf.body(
        "When a human node is hit, run.status becomes awaiting_input and checkpoint_data "
        "stores WorkflowState. Client calls POST /v1/runs/{id}/resume with human_response. "
        "Worker job resume_workflow_run restores state, appends human input, continues from next node."
    )

    # 8. Knowledge / RAG
    pdf.h1("8. Knowledge Base & RAG Flow")
    pdf.body("Document upload path:")
    pdf.code_block(
        "1. POST /v1/knowledge-bases/{kb_id}/documents (multipart file)\n"
        "2. File saved to storage path (org_id/kb_id/filename; dev uses local /tmp)\n"
        "3. Document row created (status=pending)\n"
        "4. ARQ job index_document(document_id) enqueued\n"
        "5. Worker: read file, chunk_text(), embed via gateway embed_model\n"
        "6. Worker: QdrantStore.upsert_chunks(org, kb, doc, vectors)\n"
        "7. Document status -> indexed (or failed)"
    )
    pdf.body(
        "At agent runtime, execute_agent queries Qdrant with the user message embedding "
        "and injects top chunks into the LLM context for agents with knowledge_base_ids in config."
    )

    # 9. MCP
    pdf.h1("9. MCP HTTP Connections")
    pdf.bullet("CRUD /v1/mcp-connections stores base_url, auth (encrypted), tool_allowlist")
    pdf.bullet("POST /{id}/discover fetches tools from remote MCP HTTP server")
    pdf.bullet("POST /{id}/test verifies connectivity")
    pdf.bullet("Agents bind tools via config.mcp_tools: [{connection_id, tools: [...]}]")
    pdf.bullet("Worker loads clients per org; runtime maps tools to OpenAI function schemas")

    # 10. LLM Gateway
    pdf.add_page()
    pdf.h1("10. LLM Gateway Configuration")
    pdf.body(
        "Platform default from env: LLM_GATEWAY_URL, LLM_GATEWAY_KEY, LLM_DEFAULT_MODEL, EMBED_MODEL. "
        "Per-org override stored in llm_gateway_configs table (one row per org)."
    )
    pdf.h2("Key modules")
    pdf.bullet("orchestrator_llm.client: normalize_gateway_base_url(), create_openai_client()")
    pdf.bullet("httpx verify=LLM_GATEWAY_VERIFY_SSL, trust_env=LLM_GATEWAY_TRUST_ENV")
    pdf.bullet("orchestrator_llm.gateway: get_gateway_for_org(), upsert_gateway_config()")
    pdf.h2("Corporate / self-signed gateway (.env)")
    pdf.code_block(
        "LLM_GATEWAY_URL=https://aigw.example.net/v1\n"
        "LLM_GATEWAY_VERIFY_SSL=false    # like curl -k\n"
        "LLM_GATEWAY_TRUST_ENV=false     # bypass HTTP_PROXY on Windows"
    )
    pdf.body(
        "Settings UI: PUT /v1/settings/llm-gateway saves normalized base URL. "
        "POST /v1/settings/llm-gateway/test sends a ping chat completion and returns ok/error + hint."
    )

    # 11. Worker tasks
    pdf.h1("11. ARQ Worker Tasks")
    pdf.table(
        ["Job function", "Trigger", "Purpose"],
        [
            ["execute_agent_run", "Agent invoke", "Run single agent LLM + RAG + MCP"],
            ["execute_workflow_run", "Workflow invoke", "Execute graph from entry node"],
            ["resume_workflow_run", "Run resume", "Continue after human node"],
            ["index_document", "Document upload", "Chunk, embed, upsert to Qdrant"],
        ],
        [55, 45, 90],
    )
    pdf.body("Start worker: arq orchestrator_worker.tasks.WorkerSettings")

    # 12. Events & webhooks
    pdf.h1("12. Real-time Events & Webhooks")
    pdf.h2("SSE (Server-Sent Events)")
    pdf.body(
        "EventPublisher publishes to Redis channel run:{run_id}:events. "
        "GET /runs/{id}/events subscribes and streams JSON: run.status, run.completed, "
        "run.failed, run.awaiting_input, token events during execution."
    )
    pdf.h2("Webhooks")
    pdf.body(
        "Invoke body may include webhook_url and webhook_secret. On completion/failure/awaiting_input, "
        "worker POSTs signed payload (X-Orchestrator-Signature) to the callback URL."
    )

    # 13. Database
    pdf.h1("13. Database Entities (PostgreSQL)")
    pdf.table(
        ["Table", "Purpose"],
        [
            ["organizations", "Tenant root (name, slug)"],
            ["users", "Email login, role, org FK"],
            ["agents", "Agent config, model, system_prompt, JSONB config"],
            ["workflows", "Graph JSONB, publish version"],
            ["runs", "Execution record, trace, checkpoint, webhook"],
            ["api_keys", "Hashed keys, scopes, rate limits"],
            ["knowledge_bases", "KB metadata, embed_model"],
            ["documents", "Uploaded files, indexing status"],
            ["mcp_connections", "MCP HTTP endpoints, discovered_tools"],
            ["llm_gateway_configs", "Per-org gateway override"],
            ["usage_daily", "Aggregated tokens and run counts per day"],
        ],
        [55, 135],
    )
    pdf.body("Migrations: Alembic in packages/core/alembic. Run: ./scripts/migrate.sh")

    # 14. Environment
    pdf.add_page()
    pdf.h1("14. Environment Variables")
    pdf.table(
        ["Variable", "Default / notes"],
        [
            ["DATABASE_URL", "postgresql+asyncpg://...localhost:5432/orchestrator"],
            ["REDIS_URL", "redis://localhost:6379/0"],
            ["LLM_GATEWAY_URL", "OpenAI-compatible base URL (/v1)"],
            ["LLM_GATEWAY_KEY", "API key for gateway"],
            ["LLM_DEFAULT_MODEL", "Platform default chat model"],
            ["EMBED_MODEL", "nomic-embed-text typical"],
            ["QDRANT_URL", "http://localhost:6333"],
            ["S3_*", "MinIO endpoint and bucket"],
            ["JWT_SECRET", "Change in production"],
            ["ENCRYPTION_KEY", "Secrets encryption (API keys, MCP, webhooks)"],
            ["LLM_GATEWAY_VERIFY_SSL", "true; set false for self-signed"],
            ["LLM_GATEWAY_TRUST_ENV", "false; ignores system proxy"],
            ["ORG_RATE_LIMIT_PER_MINUTE", "120"],
            ["CORS_ORIGINS", "http://localhost:5173"],
        ],
        [70, 120],
    )

    # 15. Local dev & deploy
    pdf.h1("15. Local Development")
    pdf.code_block(
        "cd infra && docker compose up -d          # postgres, redis, qdrant, minio\n"
        "cp .env.example .env && edit secrets\n"
        "uv sync --all-packages && ./scripts/migrate.sh\n"
        "# Terminal 1: API\n"
        "uv run --package orchestrator-api uvicorn orchestrator_api.main:app --reload --port 8000\n"
        "# Terminal 2: Worker\n"
        "uv run --package orchestrator-worker arq orchestrator_worker.tasks.WorkerSettings"
    )
    pdf.h2("Production Docker")
    pdf.body("infra/docker-compose.prod.yml builds API, worker, web images. Web proxies /v1 to API.")

    # 16. Run statuses
    pdf.h1("16. Run Status Lifecycle")
    pdf.table(
        ["Status", "Meaning"],
        [
            ["pending", "Created; job queued"],
            ["running", "Worker executing"],
            ["completed", "Success; output available"],
            ["failed", "Error in run.error"],
            ["awaiting_input", "Workflow paused at human node"],
            ["cancelled", "Reserved for future use"],
        ],
        [55, 135],
    )

    pdf.h1("17. External Invoke Example")
    pdf.code_block(
        "curl -X POST http://localhost:8000/v1/agents/{agent_id}/invoke \\\n"
        "  -H 'X-API-Key: oak_...' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\"input\": \"Hello\", \"context\": {}}'\n"
        "# Response: 202 {\"run_id\": \"...\", \"status\": \"pending\"}\n"
        "curl http://localhost:8000/v1/runs/{run_id} -H 'X-API-Key: oak_...'"
    )

    pdf.output(str(output))


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "docs" / "Orchestrator-Backend-Documentation.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    build_pdf(out)
    print(f"Generated: {out}")
