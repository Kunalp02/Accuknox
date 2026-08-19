from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_auth.auth.context import AuthContext
from mcp_auth.auth.deps import get_auth_context, require_permission
from mcp_auth.db.models import McpToolInvocation
from mcp_auth.db.session import get_session

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/invocations")
async def list_invocations(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
):
    require_permission(auth, "audit:read")
    result = await session.execute(
        select(McpToolInvocation)
        .where(McpToolInvocation.organization_id == auth.org_id)
        .order_by(McpToolInvocation.created_at.desc())
        .limit(min(limit, 200))
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "tool_name": r.tool_name,
            "direction": r.direction,
            "status": r.status,
            "principal_type": r.principal_type,
            "principal_id": r.principal_id,
            "connection_id": r.connection_id,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
