"""Record daily usage metrics per organization."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.models import UsageDaily


async def record_run_usage(
    session: AsyncSession,
    org_id: uuid.UUID,
    metrics: dict,
    status: str,
) -> None:
    today = datetime.now(timezone.utc).date()
    result = await session.execute(
        select(UsageDaily).where(
            UsageDaily.organization_id == org_id,
            UsageDaily.usage_date == today,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        row = UsageDaily(organization_id=org_id, usage_date=today)
        session.add(row)

    row.runs_total += 1
    if status == "completed":
        row.runs_completed += 1
    elif status == "failed":
        row.runs_failed += 1
    row.tokens_in += int(metrics.get("tokens_in", 0))
    row.tokens_out += int(metrics.get("tokens_out", 0))
    row.updated_at = datetime.now(timezone.utc)
