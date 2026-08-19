import pytest
from httpx import ASGITransport, AsyncClient

from mcp_auth.main import app
from mcp_auth.rbac import has_permission
from mcp_auth.mcp.policy.evaluator import PolicyDenied, ToolPolicyEvaluator
from mcp_auth.auth.context import AuthContext
from mcp_auth.db.models import McpConnection


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_signup_login_and_me(client):
    signup = await client.post(
        "/v1/auth/signup",
        json={"email": "builder@example.com", "password": "password123", "org_name": "Acme"},
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]

    me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_well_known_metadata(client):
    response = await client.get("/.well-known/oauth-protected-resource")
    assert response.status_code == 200
    body = response.json()
    assert "resource" in body
    assert "authorization_servers" in body


@pytest.mark.asyncio
async def test_mcp_tools_list_requires_auth(client):
    response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mcp_inbound_tools_flow(client):
    signup = await client.post(
        "/v1/auth/signup",
        json={"email": "mcp@example.com", "password": "password123", "org_name": "MCP Org"},
    )
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    tools = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers=headers,
    )
    assert tools.status_code == 200
    assert "tools" in tools.json()["result"]

    call = await client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "whoami", "arguments": {}},
        },
        headers=headers,
    )
    assert call.status_code == 200
    assert "principal_type=user" in call.json()["result"]["content"][0]["text"]


def test_rbac_permissions():
    assert has_permission("owner", "mcp:invoke")
    assert has_permission("viewer", "mcp:read")
    assert not has_permission("viewer", "mcp:write")


def test_tool_allowlist_policy():
    evaluator = ToolPolicyEvaluator()
    auth = AuthContext(org_id="org-1", user_id="user-1", role="builder")
    conn = McpConnection(
        id="c1",
        organization_id="org-1",
        name="test",
        base_url="http://example.com/mcp",
        tool_allowlist=["allowed_tool"],
    )
    evaluator.can_invoke(auth, conn, "allowed_tool")
    with pytest.raises(PolicyDenied):
        evaluator.can_invoke(auth, conn, "blocked_tool")
