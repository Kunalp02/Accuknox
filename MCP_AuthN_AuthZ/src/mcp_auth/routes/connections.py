import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_auth.auth.context import AuthContext
from mcp_auth.auth.deps import get_auth_context, require_permission
from mcp_auth.db.models import McpConnection
from mcp_auth.db.session import get_session
from mcp_auth.mcp.client.http import McpHttpClient, auth_from_connection, test_connection
from mcp_auth.mcp.client.obo import OboExchangeRequest, exchange_token_entra_obo, exchange_token_rfc8693
from mcp_auth.mcp.policy.evaluator import PolicyDenied, TimedInvocation, ToolPolicyEvaluator, audit_invocation
from mcp_auth.security import encrypt_secret

router = APIRouter(prefix="/mcp-connections", tags=["connections"])


class ConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=500)
    auth_type: str | None = None
    auth_credentials: str | None = None
    auth_config: dict = Field(default_factory=dict)
    tool_allowlist: list[str] = Field(default_factory=list)


class ConnectionUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    auth_type: str | None = None
    auth_credentials: str | None = None
    auth_config: dict | None = None
    tool_allowlist: list[str] | None = None


class ConnectionResponse(BaseModel):
    id: str
    name: str
    base_url: str
    auth_type: str | None
    auth_config: dict
    tool_allowlist: list[str]
    discovered_tools: list
    health_status: str
    last_error: str | None


class ToolInvokeRequest(BaseModel):
    tool_name: str
    arguments: dict = Field(default_factory=dict)


class OboExchangeBody(BaseModel):
    flow: str = "rfc8693"
    token_endpoint: str
    client_id: str
    client_secret: str | None = None
    subject_token: str
    audience: str
    scopes: list[str] = Field(default_factory=list)


def _to_response(conn: McpConnection) -> ConnectionResponse:
    return ConnectionResponse(
        id=conn.id,
        name=conn.name,
        base_url=conn.base_url,
        auth_type=conn.auth_type,
        auth_config=conn.auth_config or {},
        tool_allowlist=conn.tool_allowlist or [],
        discovered_tools=conn.discovered_tools or [],
        health_status=conn.health_status,
        last_error=conn.last_error,
    )


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    require_permission(auth, "mcp:read")
    result = await session.execute(
        select(McpConnection).where(McpConnection.organization_id == auth.org_id)
    )
    return [_to_response(c) for c in result.scalars().all()]


@router.post("", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    body: ConnectionCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    require_permission(auth, "mcp:write")
    encrypted = encrypt_secret(body.auth_credentials) if body.auth_credentials else None
    conn = McpConnection(
        id=str(uuid.uuid4()),
        organization_id=auth.org_id,
        name=body.name,
        base_url=body.base_url,
        auth_type=body.auth_type,
        auth_config=body.auth_config,
        auth_credentials_encrypted=encrypted,
        tool_allowlist=body.tool_allowlist,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    return _to_response(conn)


@router.patch("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: str,
    body: ConnectionUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    require_permission(auth, "mcp:write")
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
    if body.auth_config is not None:
        conn.auth_config = body.auth_config
    if body.tool_allowlist is not None:
        conn.tool_allowlist = body.tool_allowlist
    conn.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(conn)
    return _to_response(conn)


@router.post("/{connection_id}/test", response_model=ConnectionResponse)
async def test_connection_endpoint(
    connection_id: str,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    require_permission(auth, "mcp:write")
    result = await session.execute(
        select(McpConnection).where(
            McpConnection.id == connection_id,
            McpConnection.organization_id == auth.org_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    mcp_auth = auth_from_connection(
        conn.auth_type, conn.auth_credentials_encrypted, conn.token_encrypted
    )
    ok, tools, msg = await test_connection(conn.base_url, mcp_auth)
    conn.health_status = "healthy" if ok else "unhealthy"
    conn.last_error = None if ok else msg
    if ok:
        conn.discovered_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
    conn.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(conn)
    return _to_response(conn)


@router.post("/{connection_id}/invoke")
async def invoke_tool(
    connection_id: str,
    body: ToolInvokeRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    require_permission(auth, "mcp:invoke")
    result = await session.execute(
        select(McpConnection).where(
            McpConnection.id == connection_id,
            McpConnection.organization_id == auth.org_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    evaluator = ToolPolicyEvaluator()
    timer = TimedInvocation()
    try:
        evaluator.can_invoke(auth, conn, body.tool_name, direction="outbound")
        mcp_auth = auth_from_connection(
            conn.auth_type, conn.auth_credentials_encrypted, conn.token_encrypted
        )
        client = McpHttpClient(conn.base_url, mcp_auth)
        output = await client.call_tool(body.tool_name, body.arguments)
        await audit_invocation(
            session,
            auth,
            tool_name=body.tool_name,
            status="success",
            direction="outbound",
            connection_id=conn.id,
            arguments=body.arguments,
            latency_ms=timer.latency_ms,
        )
        return {"result": output}
    except PolicyDenied as e:
        await audit_invocation(
            session,
            auth,
            tool_name=body.tool_name,
            status="denied",
            direction="outbound",
            connection_id=conn.id,
            arguments=body.arguments,
            error_message=e.reason,
            latency_ms=timer.latency_ms,
        )
        raise HTTPException(status_code=403, detail=e.reason) from e
    except Exception as e:
        await audit_invocation(
            session,
            auth,
            tool_name=body.tool_name,
            status="error",
            direction="outbound",
            connection_id=conn.id,
            arguments=body.arguments,
            error_message=str(e),
            latency_ms=timer.latency_ms,
        )
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/obo/exchange")
async def obo_exchange(
    body: OboExchangeBody,
    auth: AuthContext = Depends(get_auth_context),
):
    require_permission(auth, "mcp:connect")
    if body.flow == "entra":
        token_set = await exchange_token_entra_obo(
            body.token_endpoint,
            body.client_id,
            body.client_secret or "",
            body.subject_token,
            body.scopes,
        )
    else:
        token_set = await exchange_token_rfc8693(
            OboExchangeRequest(
                token_endpoint=body.token_endpoint,
                client_id=body.client_id,
                client_secret=body.client_secret,
                subject_token=body.subject_token,
                audience=body.audience,
                scopes=body.scopes,
            )
        )
    return {
        "access_token": token_set.access_token,
        "token_type": token_set.token_type,
        "expires_in": token_set.expires_in,
    }


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    require_permission(auth, "mcp:write")
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
