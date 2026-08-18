import json
import uuid
from datetime import datetime, timezone

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.config import settings
from orchestrator_core.database import get_session
from orchestrator_core.models import Agent, Run, Workflow
from orchestrator_core.rbac import has_permission
from orchestrator_core.security import generate_api_key, hash_api_key, encrypt_secret

from orchestrator_api.deps import AuthContext, get_auth_context
from orchestrator_api.guards import check_resource_scope, enforce_rate_limit
from orchestrator_events.publisher import EventPublisher

router = APIRouter(tags=["runs"])
api_keys_router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class InvokeRequest(BaseModel):
    input: str = Field(min_length=1)
    context: dict = Field(default_factory=dict)
    webhook_url: HttpUrl | None = None
    webhook_secret: str | None = Field(default=None, max_length=500)


class ResumeRequest(BaseModel):
    input: str = Field(min_length=1)


class InvokeResponse(BaseModel):
    run_id: str
    status: str


class RunResponse(BaseModel):
    id: str
    status: str
    agent_id: str | None
    workflow_id: str | None
    input: dict
    output: dict | None
    error: str | None
    metrics: dict
    trace: list
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ApiKeyCreate(BaseModel):
    name: str
    scopes: list[str] = ["agent:invoke"]
    resource_ids: list[str] = []
    rate_limit_per_minute: int = 60


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    resource_ids: list[str]
    is_active: bool
    created_at: datetime
    key: str | None = None


def _check(auth: AuthContext, permission: str) -> None:
    if auth.is_api_key:
        if permission == "agent:invoke" and "agent:invoke" in auth.scopes:
            return
        if permission == "workflow:invoke" and "workflow:invoke" in auth.scopes:
            return
        if permission == "run:read":
            return
        raise HTTPException(status_code=403, detail="Insufficient API key scope")
    if auth.role and not has_permission(auth.role, permission):
        raise HTTPException(status_code=403, detail="Permission denied")


async def _enqueue_job(job_name: str, run_id: uuid.UUID) -> None:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    pool = await create_pool(redis_settings)
    await pool.enqueue_job(job_name, str(run_id))
    await pool.aclose()


def _run_response(run: Run) -> RunResponse:
    return RunResponse(
        id=str(run.id),
        status=run.status,
        agent_id=str(run.agent_id) if run.agent_id else None,
        workflow_id=str(run.workflow_id) if run.workflow_id else None,
        input=run.input,
        output=run.output,
        error=run.error,
        metrics=run.metrics,
        trace=run.trace or [],
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.post("/agents/{agent_id}/invoke", response_model=InvokeResponse, status_code=202)
async def invoke_agent(
    agent_id: uuid.UUID,
    body: InvokeRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "agent:invoke")
    await enforce_rate_limit(auth)
    check_resource_scope(auth, agent_id)
    result = await session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.organization_id == auth.org_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if auth.is_api_key and not agent.is_published:
        raise HTTPException(status_code=403, detail="Agent is not published")

    run = Run(
        organization_id=auth.org_id,
        agent_id=agent.id,
        status="pending",
        input={"message": body.input, "context": body.context},
        webhook_url=str(body.webhook_url) if body.webhook_url else None,
        webhook_secret_encrypted=encrypt_secret(body.webhook_secret) if body.webhook_secret else None,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    await _enqueue_job("execute_agent_run", run.id)

    return InvokeResponse(run_id=str(run.id), status=run.status)


@router.post("/workflows/{workflow_id}/invoke", response_model=InvokeResponse, status_code=202)
async def invoke_workflow(
    workflow_id: uuid.UUID,
    body: InvokeRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "workflow:invoke")
    await enforce_rate_limit(auth)
    check_resource_scope(auth, workflow_id)
    result = await session.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == auth.org_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if auth.is_api_key and not workflow.is_published:
        raise HTTPException(status_code=403, detail="Workflow is not published")

    run = Run(
        organization_id=auth.org_id,
        workflow_id=workflow.id,
        status="pending",
        input={"message": body.input, "context": body.context},
        webhook_url=str(body.webhook_url) if body.webhook_url else None,
        webhook_secret_encrypted=encrypt_secret(body.webhook_secret) if body.webhook_secret else None,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    await _enqueue_job("execute_workflow_run", run.id)
    return InvokeResponse(run_id=str(run.id), status=run.status)


@router.post("/runs/{run_id}/resume", response_model=InvokeResponse, status_code=202)
async def resume_run(
    run_id: uuid.UUID,
    body: ResumeRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "workflow:invoke")
    await enforce_rate_limit(auth)
    result = await session.execute(
        select(Run).where(Run.id == run_id, Run.organization_id == auth.org_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "awaiting_input":
        raise HTTPException(status_code=400, detail="Run is not awaiting input")

    run.input = {**run.input, "human_response": body.input}
    run.status = "pending"
    await session.commit()
    await _enqueue_job("resume_workflow_run", run.id)
    return InvokeResponse(run_id=str(run.id), status=run.status)


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "run:read")
    result = await session.execute(
        select(Run).where(Run.id == run_id, Run.organization_id == auth.org_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_response(run)


@router.get("/runs")
async def list_runs(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
):
    _check(auth, "run:read")
    result = await session.execute(
        select(Run)
        .where(Run.organization_id == auth.org_id)
        .order_by(Run.created_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return [_run_response(r) for r in runs]


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "run:read")
    result = await session.execute(
        select(Run).where(Run.id == run_id, Run.organization_id == auth.org_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        pubsub, client = await EventPublisher().subscribe(run_id)
        try:
            if run.status in ("completed", "failed", "cancelled", "awaiting_input"):
                yield f"data: {json.dumps({'type': 'run.status', 'data': {'status': run.status}})}\n\n"
                if run.output:
                    yield f"data: {json.dumps({'type': 'run.completed', 'data': run.output})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'run.status', 'data': {'status': run.status}})}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                    data = json.loads(message["data"])
                    if data.get("type") in ("run.completed", "run.failed"):
                        break
                await session.refresh(run)
                refreshed = await session.get(Run, run_id)
                if refreshed and refreshed.status in ("completed", "failed", "cancelled", "awaiting_input"):
                    if refreshed.status == "completed":
                        yield f"data: {json.dumps({'type': 'run.completed', 'data': refreshed.output})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'run.failed', 'data': {'error': refreshed.error}})}\n\n"
                    break
        finally:
            await pubsub.unsubscribe()
            await client.aclose()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@api_keys_router.post("", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    if auth.is_api_key:
        raise HTTPException(status_code=403, detail="API keys cannot create API keys")
    if not auth.role or not has_permission(auth.role, "api_key:write"):
        raise HTTPException(status_code=403, detail="Permission denied")

    from orchestrator_core.models import ApiKey

    full_key, prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        organization_id=auth.org_id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes,
        resource_ids=body.resource_ids,
        rate_limit_per_minute=body.rate_limit_per_minute,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return ApiKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        resource_ids=api_key.resource_ids,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        key=full_key,
    )


@api_keys_router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    if auth.is_api_key:
        raise HTTPException(status_code=403, detail="Not allowed")
    if not auth.role or not has_permission(auth.role, "api_key:read"):
        raise HTTPException(status_code=403, detail="Permission denied")

    from orchestrator_core.models import ApiKey

    result = await session.execute(
        select(ApiKey).where(ApiKey.organization_id == auth.org_id).order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        ApiKeyResponse(
            id=str(k.id),
            name=k.name,
            key_prefix=k.key_prefix,
            scopes=k.scopes,
            resource_ids=k.resource_ids,
            is_active=k.is_active,
            created_at=k.created_at,
        )
        for k in keys
    ]


@api_keys_router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    if auth.is_api_key:
        raise HTTPException(status_code=403, detail="Not allowed")
    if not auth.role or not has_permission(auth.role, "api_key:write"):
        raise HTTPException(status_code=403, detail="Permission denied")

    from orchestrator_core.models import ApiKey

    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == auth.org_id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.is_active = False
    await session.commit()
