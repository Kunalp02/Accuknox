import asyncio
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_signup_and_me(client: AsyncClient):
    email = f"signup-{uuid.uuid4().hex[:8]}@example.com"
    res = await client.post(
        "/v1/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "org_name": "Signup Org",
        },
    )
    assert res.status_code == 200
    token = res.json()["access_token"]

    me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_agent_crud_and_invoke(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/v1/agents",
        headers=auth_headers,
        json={
            "name": "Test Agent",
            "system_prompt": "You are a test bot.",
            "model": "llama3.2",
        },
    )
    assert create.status_code == 201, create.text
    agent_id = create.json()["id"]

    publish = await client.post(f"/v1/agents/{agent_id}/publish", headers=auth_headers)
    assert publish.status_code == 200
    assert publish.json()["is_published"] is True

    invoke = await client.post(
        f"/v1/agents/{agent_id}/invoke",
        headers=auth_headers,
        json={"input": "Hello from integration test"},
    )
    assert invoke.status_code == 202
    run_id = invoke.json()["run_id"]

    for _ in range(20):
        run = await client.get(f"/v1/runs/{run_id}", headers=auth_headers)
        assert run.status_code == 200
        status = run.json()["status"]
        if status in ("completed", "failed"):
            assert status == "completed", run.json().get("error")
            assert run.json()["output"]["message"]
            break
        await asyncio.sleep(0.25)
    else:
        pytest.fail("Run did not complete in time")


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_workflow_multi_agent_invoke(client: AsyncClient, auth_headers: dict):
    a1 = await client.post(
        "/v1/agents",
        headers=auth_headers,
        json={"name": "Researcher", "system_prompt": "Research", "model": "llama3.2"},
    )
    a2 = await client.post(
        "/v1/agents",
        headers=auth_headers,
        json={"name": "Writer", "system_prompt": "Write", "model": "llama3.2"},
    )
    assert a1.status_code == 201 and a2.status_code == 201
    agent1_id = a1.json()["id"]
    agent2_id = a2.json()["id"]

    wf = await client.post(
        "/v1/workflows",
        headers=auth_headers,
        json={
            "name": "Multi-agent test",
            "graph": {
                "entry": "researcher",
                "nodes": [
                    {"id": "researcher", "type": "agent", "agent_id": agent1_id},
                    {"id": "writer", "type": "agent", "agent_id": agent2_id},
                ],
                "edges": [{"from": "researcher", "to": "writer"}],
            },
        },
    )
    assert wf.status_code == 201, wf.text
    workflow_id = wf.json()["id"]

    validate = await client.post(f"/v1/workflows/{workflow_id}/validate", headers=auth_headers)
    assert validate.status_code == 200
    assert validate.json()["valid"] is True

    publish = await client.post(f"/v1/workflows/{workflow_id}/publish", headers=auth_headers)
    assert publish.status_code == 200

    invoke = await client.post(
        f"/v1/workflows/{workflow_id}/invoke",
        headers=auth_headers,
        json={"input": "Test multi-agent workflow"},
    )
    assert invoke.status_code == 202
    run_id = invoke.json()["run_id"]

    for _ in range(30):
        run = await client.get(f"/v1/runs/{run_id}", headers=auth_headers)
        assert run.status_code == 200
        status = run.json()["status"]
        if status in ("completed", "failed"):
            assert status == "completed", run.json().get("error")
            assert "node_outputs" in run.json()["output"]
            assert "researcher" in run.json()["output"]["node_outputs"]
            assert "writer" in run.json()["output"]["node_outputs"]
            break
        await asyncio.sleep(0.25)
    else:
        pytest.fail("Workflow run did not complete in time")


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_gateway_settings_and_test(client: AsyncClient, auth_headers: dict):
    res = await client.get("/v1/settings/llm-gateway", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["uses_platform_default"] is True

    test = await client.post("/v1/settings/llm-gateway/test", headers=auth_headers)
    assert test.status_code == 200
    body = test.json()
    assert body["ok"] is True
    assert "response_preview" in body


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_agent_delete(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/v1/agents",
        headers=auth_headers,
        json={"name": "Delete Agent", "system_prompt": "test", "model": "llama3.2"},
    )
    assert create.status_code == 201
    agent_id = create.json()["id"]

    delete = await client.delete(f"/v1/agents/{agent_id}", headers=auth_headers)
    assert delete.status_code == 204


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_api_key_revoke(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/v1/api-keys",
        headers=auth_headers,
        json={"name": "Revoke Test", "scopes": ["agent:invoke"]},
    )
    assert create.status_code == 201
    key_id = create.json()["id"]

    revoke = await client.delete(f"/v1/api-keys/{key_id}", headers=auth_headers)
    assert revoke.status_code == 204

    keys = await client.get("/v1/api-keys", headers=auth_headers)
    revoked = next(k for k in keys.json() if k["id"] == key_id)
    assert revoked["is_active"] is False


@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_knowledge_base_documents(client: AsyncClient, auth_headers: dict):
    kb = await client.post(
        "/v1/knowledge-bases",
        headers=auth_headers,
        json={"name": "Test KB"},
    )
    assert kb.status_code == 201
    kb_id = kb.json()["id"]

    docs = await client.get(f"/v1/knowledge-bases/{kb_id}/documents", headers=auth_headers)
    assert docs.status_code == 200
    assert docs.json() == []
