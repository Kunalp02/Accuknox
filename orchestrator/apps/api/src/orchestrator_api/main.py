from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orchestrator_core.config import settings
from orchestrator_core.database import init_db

from orchestrator_api.routes.auth import router as auth_router
from orchestrator_api.routes.agents import router as agents_router
from orchestrator_api.routes.runs import router as runs_router, api_keys_router
from orchestrator_api.routes.knowledge import router as knowledge_router
from orchestrator_api.routes.workflows import router as workflows_router
from orchestrator_api.routes.mcp import router as mcp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Orchestrator API",
    description="Multi-agent orchestrator platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/v1")
app.include_router(agents_router, prefix="/v1")
app.include_router(runs_router, prefix="/v1")
app.include_router(api_keys_router, prefix="/v1")
app.include_router(knowledge_router, prefix="/v1")
app.include_router(workflows_router, prefix="/v1")
app.include_router(mcp_router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
