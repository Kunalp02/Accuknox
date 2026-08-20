"""Enqueue ARQ jobs with optional in-process fallback when Redis/worker unavailable."""

import asyncio
import logging
import uuid

from arq import create_pool
from arq.connections import RedisSettings
from orchestrator_core.config import settings

logger = logging.getLogger(__name__)

_JOB_FUNCTIONS = {
    "execute_agent_run": "orchestrator_worker.tasks.execute_agent_run",
    "execute_workflow_run": "orchestrator_worker.tasks.execute_workflow_run",
    "resume_workflow_run": "orchestrator_worker.tasks.resume_workflow_run",
    "index_document": "orchestrator_worker.tasks.index_document",
}


def _import_job(job_name: str):
    module_path, func_name = _JOB_FUNCTIONS[job_name].rsplit(".", 1)
    module = __import__(module_path, fromlist=[func_name])
    return getattr(module, func_name)


async def _run_inline(job_name: str, run_id: uuid.UUID) -> None:
    func = _import_job(job_name)
    await func({}, str(run_id))


async def enqueue_job(job_name: str, run_id: uuid.UUID) -> str:
    """
    Enqueue a background job. Falls back to in-process execution when:
    - SYNC_WORKER=true, or
    - Redis is unreachable (dev/single-process mode).
    Returns 'redis' or 'inline'.
    """
    if settings.sync_worker:
        asyncio.create_task(_run_inline(job_name, run_id))
        return "inline"

    try:
        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        pool = await create_pool(redis_settings)
        await pool.enqueue_job(job_name, str(run_id))
        await pool.aclose()
        return "redis"
    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s); running %s inline for run %s",
            exc,
            job_name,
            run_id,
        )
        asyncio.create_task(_run_inline(job_name, run_id))
        return "inline"
