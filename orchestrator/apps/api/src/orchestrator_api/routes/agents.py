import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.database import get_session
from orchestrator_core.models import Agent
from orchestrator_core.rbac import has_permission

from orchestrator_api.deps import AuthContext, get_auth_context

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str = "You are a helpful assistant."
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    knowledge_base_ids: list[str] = []


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    knowledge_base_ids: list[str] | None = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str | None
    system_prompt: str
    model: str
    temperature: float
    is_published: bool
    version: int
    knowledge_base_ids: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _agent_to_response(agent: Agent) -> AgentResponse:
    kb_ids = agent.config.get("knowledge_base_ids", [])
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model=agent.model,
        temperature=agent.temperature,
        is_published=agent.is_published,
        version=agent.version,
        knowledge_base_ids=kb_ids,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _check_permission(auth: AuthContext, permission: str) -> None:
    if auth.is_api_key:
        if permission not in auth.scopes and "agent:invoke" not in auth.scopes:
            if permission.endswith(":read") and "agent:read" in auth.scopes:
                return
            if permission.endswith(":invoke") and "agent:invoke" in auth.scopes:
                return
            raise HTTPException(status_code=403, detail="Insufficient API key scope")
        return
    if auth.role and not has_permission(auth.role, permission):
        raise HTTPException(status_code=403, detail="Permission denied")


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check_permission(auth, "agent:read")
    result = await session.execute(
        select(Agent).where(Agent.organization_id == auth.org_id).order_by(Agent.created_at.desc())
    )
    agents = result.scalars().all()
    return [_agent_to_response(a) for a in agents]


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check_permission(auth, "agent:write")
    from orchestrator_core.config import settings

    agent = Agent(
        organization_id=auth.org_id,
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        model=body.model or settings.llm_default_model,
        temperature=body.temperature,
        config={"knowledge_base_ids": body.knowledge_base_ids},
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return _agent_to_response(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check_permission(auth, "agent:read")
    result = await session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.organization_id == auth.org_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_response(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check_permission(auth, "agent:write")
    result = await session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.organization_id == auth.org_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if body.name is not None:
        agent.name = body.name
    if body.description is not None:
        agent.description = body.description
    if body.system_prompt is not None:
        agent.system_prompt = body.system_prompt
    if body.model is not None:
        agent.model = body.model
    if body.temperature is not None:
        agent.temperature = body.temperature
    if body.knowledge_base_ids is not None:
        agent.config = {**agent.config, "knowledge_base_ids": body.knowledge_base_ids}
    agent.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(agent)
    return _agent_to_response(agent)


@router.post("/{agent_id}/publish", response_model=AgentResponse)
async def publish_agent(
    agent_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check_permission(auth, "agent:publish")
    result = await session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.organization_id == auth.org_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_published = True
    agent.version += 1
    agent.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(agent)
    return _agent_to_response(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check_permission(auth, "agent:write")
    result = await session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.organization_id == auth.org_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await session.delete(agent)
    await session.commit()
