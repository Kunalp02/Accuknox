import pytest

from mcp_auth.db.session import init_db


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    await init_db()
