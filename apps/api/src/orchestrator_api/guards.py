"""Shared invoke guards: rate limits and API key resource scoping."""

import uuid

from fastapi import HTTPException

from orchestrator_core.config import settings
from orchestrator_core.rate_limit import check_rate_limit

from orchestrator_api.deps import AuthContext


def check_resource_scope(auth: AuthContext, resource_id: uuid.UUID) -> None:
    if not auth.is_api_key or not auth.resource_ids:
        return
    if str(resource_id) not in auth.resource_ids:
        raise HTTPException(status_code=403, detail="API key not authorized for this resource")


async def enforce_rate_limit(auth: AuthContext) -> None:
    if auth.is_api_key and auth.api_key_id:
        limit = auth.rate_limit_per_minute or 60
        prefix = f"oak:{auth.api_key_id}"
    else:
        limit = settings.org_rate_limit_per_minute
        prefix = f"org:{auth.org_id}"
    try:
        await check_rate_limit(prefix, limit)
    except ValueError:
        raise HTTPException(status_code=429, detail="Rate limit exceeded") from None
