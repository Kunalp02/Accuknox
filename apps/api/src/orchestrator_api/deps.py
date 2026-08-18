import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.database import get_session
from orchestrator_core.models import ApiKey, User
from orchestrator_core.security import decode_access_token, hash_api_key


class AuthContext:
    def __init__(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        role: str | None = None,
        api_key_id: uuid.UUID | None = None,
        scopes: list[str] | None = None,
        resource_ids: list[str] | None = None,
        rate_limit_per_minute: int | None = None,
    ):
        self.org_id = org_id
        self.user_id = user_id
        self.role = role
        self.api_key_id = api_key_id
        self.scopes = scopes or []
        self.resource_ids = resource_ids or []
        self.rate_limit_per_minute = rate_limit_per_minute
        self.is_api_key = api_key_id is not None


async def get_auth_context(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> AuthContext:
    if x_api_key:
        return await _auth_api_key(session, x_api_key)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if token.startswith("oak_"):
            return await _auth_api_key(session, token)
        return await _auth_jwt(token)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


async def _auth_jwt(token: str) -> AuthContext:
    try:
        payload = decode_access_token(token)
        return AuthContext(
            org_id=uuid.UUID(payload["org_id"]),
            user_id=uuid.UUID(payload["sub"]),
            role=payload.get("role"),
        )
    except (JWTError, KeyError, ValueError) as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e


async def _auth_api_key(session: AsyncSession, key: str) -> AuthContext:
    key_hash = hash_api_key(key)
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API key expired")
    return AuthContext(
        org_id=api_key.organization_id,
        api_key_id=api_key.id,
        scopes=api_key.scopes or [],
        resource_ids=api_key.resource_ids or [],
        rate_limit_per_minute=api_key.rate_limit_per_minute,
    )
