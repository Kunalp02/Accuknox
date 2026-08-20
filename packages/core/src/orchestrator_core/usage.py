"""Record daily usage metrics per organization."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.models import UsageDaily


async def record_run_usage(
    session: AsyncSession,
    org_id: uuid.UUID,
    metrics: dict,
    status: str,
) -> None:
    today = datetime.now(UTC).date()
    result = await session.execute(
        select(UsageDaily).where(
            UsageDaily.organization_id == org_id,
            UsageDaily.usage_date == today,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        row = UsageDaily(
            organization_id=org_id,
            usage_date=today,
            runs_total=0,
            runs_completed=0,
            runs_failed=0,
            tokens_in=0,
            tokens_out=0,
        )
        session.add(row)

    row.runs_total = (row.runs_total or 0) + 1
    if status == "completed":
        row.runs_completed = (row.runs_completed or 0) + 1
    elif status == "failed":
        row.runs_failed = (row.runs_failed or 0) + 1
    row.tokens_in = (row.tokens_in or 0) + int(metrics.get("tokens_in", 0))
    row.tokens_out = (row.tokens_out or 0) + int(metrics.get("tokens_out", 0))
    row.updated_at = datetime.now(UTC)
