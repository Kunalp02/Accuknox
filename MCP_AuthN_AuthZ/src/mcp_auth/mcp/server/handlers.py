from typing import Any

from mcp_auth.auth.context import AuthContext
from mcp_auth.config import settings
from mcp_auth.mcp.policy.evaluator import PolicyDenied, ToolPolicyEvaluator

INBOUND_TOOLS: list[dict[str, Any]] = [
    {
        "name": "health_check",
        "description": "Returns MCP AuthN/AuthZ service health status",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "whoami",
        "description": "Returns authenticated principal and organization context",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_connections",
        "description": "Lists MCP connections for the authenticated organization",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def protected_resource_metadata() -> dict[str, Any]:
    return {
        "resource": settings.mcp_server_resource_uri,
        "authorization_servers": [settings.mcp_oauth_issuer],
        "bearer_methods_supported": ["header"],
        "scopes_supported": [
            "mcp:server:invoke",
            "mcp:server:read",
            "mcp:invoke",
            "mcp:read",
        ],
    }


def authorization_server_metadata() -> dict[str, Any]:
    base = settings.mcp_oauth_issuer.rstrip("/")
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/v1/oauth/authorize",
        "token_endpoint": f"{base}/v1/oauth/token",
        "registration_endpoint": f"{base}/v1/oauth/register",
        "scopes_supported": [
            "mcp:server:invoke",
            "mcp:server:read",
            "mcp:invoke",
            "mcp:read",
        ],
        "response_types_supported": ["code"],
        "grant_types_supported": [
            "authorization_code",
            "refresh_token",
            "urn:ietf:params:oauth:grant-type:token-exchange",
            "urn:ietf:params:oauth:grant-type:jwt-bearer",
        ],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
    }


async def handle_tools_list() -> dict[str, Any]:
    return {"tools": INBOUND_TOOLS}


async def handle_tools_call(
    auth: AuthContext,
    name: str,
    arguments: dict,
    connections: list[dict] | None = None,
) -> dict[str, Any]:
    evaluator = ToolPolicyEvaluator()
    try:
        evaluator.can_invoke(auth, None, name, direction="inbound")
    except PolicyDenied as e:
        return {
            "content": [{"type": "text", "text": f"Policy denied: {e.reason}"}],
            "isError": True,
        }

    if name == "health_check":
        text = "MCP AuthN/AuthZ server is healthy"
    elif name == "whoami":
        text = (
            f"principal_type={auth.principal_type} principal_id={auth.principal_id} "
            f"org_id={auth.org_id} role={auth.role or 'n/a'}"
        )
    elif name == "list_connections":
        items = connections or []
        text = "\n".join(f"- {c['name']} ({c['id']})" for c in items) or "No connections"
    else:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            "isError": True,
        }

    _ = arguments
    return {"content": [{"type": "text", "text": text}]}
