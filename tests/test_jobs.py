"""Job enqueue tests."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator_api.jobs import enqueue_job


@pytest.mark.asyncio
async def test_enqueue_uses_redis_when_available():
    with patch("orchestrator_api.jobs.create_pool", new_callable=AsyncMock) as pool_factory:
        pool = AsyncMock()
        pool_factory.return_value = pool
        with patch("orchestrator_api.jobs.settings") as mock_settings:
            mock_settings.sync_worker = False
            mock_settings.redis_url = "redis://localhost:6379/0"
            mode = await enqueue_job("execute_agent_run", uuid.uuid4())
    assert mode == "redis"
    pool.enqueue_job.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_falls_back_inline_on_redis_error():
    with patch("orchestrator_api.jobs.create_pool", new_callable=AsyncMock, side_effect=ConnectionError("no redis")):
        with patch("orchestrator_api.jobs._run_inline", new_callable=AsyncMock) as run_inline:
            with patch("orchestrator_api.jobs.asyncio.create_task") as create_task:
                with patch("orchestrator_api.jobs.settings") as mock_settings:
                    mock_settings.sync_worker = False
                    mock_settings.redis_url = "redis://localhost:6379/0"
                    mode = await enqueue_job("execute_agent_run", uuid.uuid4())
    assert mode == "inline"
    create_task.assert_called_once()
