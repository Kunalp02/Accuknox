import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

# Test env defaults before app import
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-integration-tests")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32-bytes!!")

from orchestrator_api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers(client: AsyncClient):
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    res = await client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "password123", "org_name": "Test Org"},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
