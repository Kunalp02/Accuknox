from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mcp_auth.config import settings
from mcp_auth.db.session import init_db
from mcp_auth.routes.audit import router as audit_router
from mcp_auth.routes.auth import router as auth_router
from mcp_auth.routes.connections import router as connections_router
from mcp_auth.routes.mcp_server import oauth_router, router as mcp_router, well_known_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
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

app.include_router(well_known_router)
app.include_router(auth_router, prefix="/v1")
app.include_router(connections_router, prefix="/v1")
app.include_router(audit_router, prefix="/v1")
app.include_router(mcp_router)
app.include_router(oauth_router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp-authn-authz"}


def run() -> None:
    uvicorn.run(
        "mcp_auth.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
