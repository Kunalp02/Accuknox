"""API-as-a-product integration guide endpoint tests."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator_api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    from orchestrator_core.database import engine

    await engine.dispose()


@pytest.fixture
async def auth_headers(client: AsyncClient):
    email = f"product-{uuid.uuid4().hex[:8]}@example.com"
    res = await client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "password123", "org_name": "API Product Org"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_agent_integration_guide(client, auth_headers):
    agent = await client.post(
        "/v1/agents",
        headers=auth_headers,
        json={"name": "Product Agent", "system_prompt": "You are helpful."},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]

    guide = await client.get(f"/v1/agents/{agent_id}/integration", headers=auth_headers)
    assert guide.status_code == 200
    body = guide.json()
    assert body["resource_type"] == "agent"
    assert body["resource_id"] == agent_id
    assert body["invoke"]["path"] == f"/v1/agents/{agent_id}/invoke"
    assert "agent:invoke" in body["required_scopes"]
    assert "invoke" in body["examples"]


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_workflow_integration_guide_includes_resume(client, auth_headers):
    wf = await client.post(
        "/v1/workflows",
        headers=auth_headers,
        json={
            "name": "Product Workflow",
            "graph": {
                "entry": "human_1",
                "nodes": [{"id": "human_1", "type": "human", "prompt": "Approve?"}],
                "edges": [],
            },
        },
    )
    assert wf.status_code == 201
    wf_id = wf.json()["id"]

    guide = await client.get(f"/v1/workflows/{wf_id}/integration", headers=auth_headers)
    assert guide.status_code == 200
    body = guide.json()
    assert body["resource_type"] == "workflow"
    assert body["resume"] is not None
    assert "resume" in body["examples"]
    assert "run.awaiting_input" in body["webhook_events"]
