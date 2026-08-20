from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_auth.auth.context import AuthContext
from mcp_auth.auth.deps import get_auth_context, require_permission
from mcp_auth.config import settings
from mcp_auth.db.models import McpConnection
from mcp_auth.db.session import get_session
from mcp_auth.mcp.policy.evaluator import PolicyDenied, TimedInvocation, audit_invocation
from mcp_auth.mcp.server.handlers import (
    authorization_server_metadata,
    handle_tools_call,
    handle_tools_list,
    protected_resource_metadata,
)
from mcp_auth.security import create_access_token

router = APIRouter(tags=["mcp-server"])
well_known_router = APIRouter(tags=["well-known"])


@well_known_router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource():
    return protected_resource_metadata()


@well_known_router.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource_mcp():
    return protected_resource_metadata()


@well_known_router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server():
    return authorization_server_metadata()


@router.post("/mcp")
async def mcp_jsonrpc(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    body = await request.json()
    method = body.get("method")
    params = body.get("params") or {}
    req_id = body.get("id")

    timer = TimedInvocation()

    try:
        if method == "tools/list":
            require_permission(auth, "mcp:server:read")
            result = await handle_tools_list()
            await audit_invocation(
                session,
                auth,
                tool_name="tools/list",
                status="success",
                direction="inbound",
                latency_ms=timer.latency_ms,
            )
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments") or {}
            require_permission(auth, "mcp:server:invoke")

            conn_result = await session.execute(
                select(McpConnection).where(McpConnection.organization_id == auth.org_id)
            )
            connections = [
                {"id": c.id, "name": c.name, "base_url": c.base_url}
                for c in conn_result.scalars().all()
            ]
            result = await handle_tools_call(auth, tool_name, arguments, connections)
            is_error = result.get("isError", False)
            await audit_invocation(
                session,
                auth,
                tool_name=tool_name,
                status="error" if is_error else "success",
                direction="inbound",
                arguments=arguments,
                latency_ms=timer.latency_ms,
            )
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mcp-authn-authz", "version": "0.1.0"},
                },
            }

        raise HTTPException(status_code=400, detail=f"Unsupported MCP method: {method}")
    except HTTPException:
        raise
    except PolicyDenied as e:
        await audit_invocation(
            session,
            auth,
            tool_name=str(method),
            status="denied",
            direction="inbound",
            error_message=e.reason,
            latency_ms=timer.latency_ms,
        )
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32000, "message": e.reason},
        }


oauth_router = APIRouter(prefix="/oauth", tags=["oauth"])


@oauth_router.post("/token")
async def oauth_token(request: Request):
    """Minimal token endpoint supporting client_credentials and token introspection-style JWT issue."""
    form = dict(await request.form())
    grant_type = form.get("grant_type")

    if grant_type == "client_credentials":
        return {
            "access_token": create_access_token("service", "system", "admin"),
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    if grant_type == "urn:ietf:params:oauth:grant-type:token-exchange":
        return {
            "access_token": create_access_token(
                form.get("subject_token", "delegated-user")[:36],
                "system",
                "builder",
            ),
            "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")


@oauth_router.get("/authorize")
async def oauth_authorize():
    return {
        "message": "Use POST /v1/auth/login for user tokens in this reference implementation",
        "issuer": settings.mcp_oauth_issuer,
    }
