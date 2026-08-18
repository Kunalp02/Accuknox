import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.database import get_session
from orchestrator_core.models import McpConnection
from orchestrator_core.rbac import has_permission
from orchestrator_core.security import encrypt_secret
from orchestrator_mcp.client import auth_from_encrypted, test_connection

from orchestrator_api.deps import AuthContext, get_auth_context

router = APIRouter(prefix="/mcp-connections", tags=["mcp"])


class McpConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=500)
    auth_type: str | None = None  # bearer | api_key_header
    auth_credentials: str | None = None
    tool_allowlist: list[str] = []


class McpConnectionUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    auth_type: str | None = None
    auth_credentials: str | None = None
    tool_allowlist: list[str] | None = None


class McpConnectionResponse(BaseModel):
    id: str
    name: str
    base_url: str
    auth_type: str | None
    tool_allowlist: list[str]
    discovered_tools: list
    health_status: str
    last_error: str | None


def _check(auth: AuthContext, permission: str) -> None:
    if auth.is_api_key:
        raise HTTPException(status_code=403, detail="Not allowed for API keys")
    if not auth.role or not has_permission(auth.role, permission):
        raise HTTPException(status_code=403, detail="Permission denied")


def _to_response(c: McpConnection) -> McpConnectionResponse:
    return McpConnectionResponse(
        id=str(c.id),
        name=c.name,
        base_url=c.base_url,
        auth_type=c.auth_type,
        tool_allowlist=c.tool_allowlist or [],
        discovered_tools=c.discovered_tools or [],
        health_status=c.health_status,
        last_error=c.last_error,
    )


@router.get("", response_model=list[McpConnectionResponse])
async def list_connections(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "mcp:read")
    result = await session.execute(
        select(McpConnection).where(McpConnection.organization_id == auth.org_id)
    )
    return [_to_response(c) for c in result.scalars().all()]


@router.post("", response_model=McpConnectionResponse, status_code=201)
async def create_connection(
    body: McpConnectionCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "mcp:write")
    encrypted = None
    if body.auth_credentials and body.auth_type:
        encrypted = encrypt_secret(body.auth_credentials)

    conn = McpConnection(
        organization_id=auth.org_id,
        name=body.name,
        base_url=body.base_url,
        auth_type=body.auth_type,
        auth_credentials_encrypted=encrypted,
        tool_allowlist=body.tool_allowlist,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    return _to_response(conn)


@router.patch("/{connection_id}", response_model=McpConnectionResponse)
async def update_connection(
    connection_id: uuid.UUID,
    body: McpConnectionUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "mcp:write")
    result = await session.execute(
        select(McpConnection).where(
            McpConnection.id == connection_id,
            McpConnection.organization_id == auth.org_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    if body.name is not None:
        conn.name = body.name
    if body.base_url is not None:
        conn.base_url = body.base_url
    if body.auth_type is not None:
        conn.auth_type = body.auth_type
    if body.auth_credentials is not None:
        conn.auth_credentials_encrypted = encrypt_secret(body.auth_credentials) if body.auth_credentials else None
    if body.tool_allowlist is not None:
        conn.tool_allowlist = body.tool_allowlist
    conn.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(conn)
    return _to_response(conn)


@router.post("/{connection_id}/test", response_model=McpConnectionResponse)
async def test_mcp_connection(
    connection_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "mcp:write")
    result = await session.execute(
        select(McpConnection).where(
            McpConnection.id == connection_id,
            McpConnection.organization_id == auth.org_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    mcp_auth = auth_from_encrypted(conn.auth_type or "", conn.auth_credentials_encrypted)
    ok, tools, msg = await test_connection(conn.base_url, mcp_auth)
    conn.health_status = "healthy" if ok else "unhealthy"
    conn.last_error = None if ok else msg
    if ok:
        conn.discovered_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]
    conn.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(conn)
    return _to_response(conn)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "mcp:write")
    result = await session.execute(
        select(McpConnection).where(
            McpConnection.id == connection_id,
            McpConnection.organization_id == auth.org_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    await session.delete(conn)
    await session.commit()
