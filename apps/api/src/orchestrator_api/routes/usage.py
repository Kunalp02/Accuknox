from datetime import date, timedelta

from fastapi import APIRouter, Depends
from orchestrator_api.deps import AuthContext, get_auth_context
from orchestrator_core.database import get_session
from orchestrator_core.models import UsageDaily
from orchestrator_core.rbac import has_permission
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/usage", tags=["usage"])


class UsageDay(BaseModel):
    date: date
    runs_total: int
    runs_completed: int
    runs_failed: int
    tokens_in: int
    tokens_out: int


@router.get("", response_model=list[UsageDay])
async def get_usage(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    days: int = 30,
):
    if auth.is_api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not allowed")
    if not auth.role or not has_permission(auth.role, "org:read"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Permission denied")

    since = date.today() - timedelta(days=max(1, min(days, 90)))
    result = await session.execute(
        select(UsageDaily)
        .where(UsageDaily.organization_id == auth.org_id, UsageDaily.usage_date >= since)
        .order_by(UsageDaily.usage_date.desc())
    )
    rows = result.scalars().all()
    return [
        UsageDay(
            date=r.usage_date,
            runs_total=r.runs_total,
            runs_completed=r.runs_completed,
            runs_failed=r.runs_failed,
            tokens_in=r.tokens_in,
            tokens_out=r.tokens_out,
        )
        for r in rows
    ]
