import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


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

    run = await client.get(f"/v1/runs/{run_id}", headers=auth_headers)
    assert run.status_code == 200
    assert run.json()["id"] == run_id
    assert run.json()["status"] in ("pending", "running", "completed", "failed")


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
