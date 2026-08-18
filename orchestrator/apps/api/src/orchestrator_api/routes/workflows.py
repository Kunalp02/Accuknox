import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.database import get_session
from orchestrator_core.models import Workflow
from orchestrator_core.rbac import has_permission

from orchestrator_api.deps import AuthContext, get_auth_context

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowNode(BaseModel):
    id: str
    type: str
    agent_id: str | None = None
    children: list[str] = []
    branches: list[dict] | list[str] = []
    connection_id: str | None = None
    tool_name: str | None = None
    arguments: dict = {}
    prompt: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    default_to: str | None = None


class WorkflowEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    condition: str | None = None

    class Config:
        populate_by_name = True


class WorkflowGraphBody(BaseModel):
    entry: str
    nodes: list[dict]
    edges: list[dict]


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    graph: WorkflowGraphBody | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: WorkflowGraphBody | None = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str | None
    graph: dict
    is_published: bool
    version: int
    created_at: datetime
    updated_at: datetime


def _check(auth: AuthContext, permission: str) -> None:
    if auth.is_api_key:
        if permission == "workflow:invoke" and "workflow:invoke" in auth.scopes:
            return
        if permission == "run:read":
            return
        raise HTTPException(status_code=403, detail="Insufficient API key scope")
    if auth.role and not has_permission(auth.role, permission):
        raise HTTPException(status_code=403, detail="Permission denied")


def _default_graph() -> dict:
    return {
        "entry": "agent_1",
        "nodes": [
            {
                "id": "agent_1",
                "type": "agent",
                "agent_id": "",
            }
        ],
        "edges": [],
    }


def _to_response(w: Workflow) -> WorkflowResponse:
    return WorkflowResponse(
        id=str(w.id),
        name=w.name,
        description=w.description,
        graph=w.graph or _default_graph(),
        is_published=w.is_published,
        version=w.version,
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "workflow:read")
    result = await session.execute(
        select(Workflow).where(Workflow.organization_id == auth.org_id).order_by(Workflow.created_at.desc())
    )
    return [_to_response(w) for w in result.scalars().all()]


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "workflow:write")
    graph = body.graph.model_dump() if body.graph else _default_graph()
    wf = Workflow(
        organization_id=auth.org_id,
        name=body.name,
        description=body.description,
        graph=graph,
    )
    session.add(wf)
    await session.commit()
    await session.refresh(wf)
    return _to_response(wf)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "workflow:read")
    result = await session.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == auth.org_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _to_response(wf)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "workflow:write")
    result = await session.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == auth.org_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if body.name is not None:
        wf.name = body.name
    if body.description is not None:
        wf.description = body.description
    if body.graph is not None:
        wf.graph = body.graph.model_dump()
    wf.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(wf)
    return _to_response(wf)


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish_workflow(
    workflow_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "workflow:publish")
    result = await session.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == auth.org_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf.is_published = True
    wf.version += 1
    wf.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(wf)
    return _to_response(wf)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "workflow:write")
    result = await session.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == auth.org_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await session.delete(wf)
    await session.commit()
