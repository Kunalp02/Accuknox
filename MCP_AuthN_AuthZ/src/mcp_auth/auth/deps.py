from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_auth.auth.context import AuthContext
from mcp_auth.db.models import ApiKey
from mcp_auth.db.session import get_session
from mcp_auth.security import decode_access_token, hash_api_key


async def get_auth_context(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> AuthContext:
    if x_api_key:
        return await _auth_api_key(session, x_api_key)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if token.startswith("mak_"):
            return await _auth_api_key(session, token)
        return _auth_jwt(token)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def _auth_jwt(token: str) -> AuthContext:
    try:
        payload = decode_access_token(token)
        return AuthContext(
            org_id=payload["org_id"],
            user_id=payload["sub"],
            role=payload.get("role"),
        )
    except (JWTError, KeyError) as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e


async def _auth_api_key(session: AsyncSession, key: str) -> AuthContext:
    key_hash = hash_api_key(key)
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return AuthContext(
        org_id=api_key.organization_id,
        api_key_id=api_key.id,
        scopes=api_key.scopes or [],
    )


def require_permission(auth: AuthContext, permission: str) -> None:
    from mcp_auth.rbac import has_permission, has_scope

    if auth.is_api_key:
        if not has_scope(auth.scopes or [], permission):
            raise HTTPException(status_code=403, detail="API key scope denied")
        return
    if not auth.role or not has_permission(auth.role, permission):
        raise HTTPException(status_code=403, detail="Permission denied")
