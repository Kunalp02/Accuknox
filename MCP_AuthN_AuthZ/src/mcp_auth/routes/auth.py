import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_auth.auth.context import AuthContext
from mcp_auth.auth.deps import get_auth_context, require_permission
from mcp_auth.db.models import ApiKey, Organization, User
from mcp_auth.db.session import get_session
from mcp_auth.security import create_access_token, generate_api_key, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    org_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    org_id: str
    user_id: str
    role: str


class ApiKeyCreate(BaseModel):
    name: str
    scopes: list[str] = ["mcp:read", "mcp:invoke"]


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    full_key: str | None = None


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


@router.post("/signup", response_model=TokenResponse)
async def signup(body: SignupRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    base_slug = _slugify(body.org_name)
    slug = base_slug
    counter = 1
    while True:
        check = await session.execute(select(Organization).where(Organization.slug == slug))
        if not check.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization(id=str(uuid.uuid4()), name=body.org_name, slug=slug)
    session.add(org)
    await session.flush()

    user = User(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        email=body.email,
        password_hash=hash_password(body.password),
        role="owner",
    )
    session.add(user)
    await session.commit()

    token = create_access_token(user.id, org.id, user.role)
    return TokenResponse(
        access_token=token,
        org_id=org.id,
        user_id=user.id,
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")

    token = create_access_token(user.id, user.organization_id, user.role)
    return TokenResponse(
        access_token=token,
        org_id=user.organization_id,
        user_id=user.id,
        role=user.role,
    )


@router.get("/me")
async def me(auth: AuthContext = Depends(get_auth_context)):
    return {
        "org_id": auth.org_id,
        "user_id": auth.user_id,
        "role": auth.role,
        "api_key_id": auth.api_key_id,
        "scopes": auth.scopes,
    }


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    require_permission(auth, "api_key:write")
    full_key, prefix, key_hash = generate_api_key()
    record = ApiKey(
        id=str(uuid.uuid4()),
        organization_id=auth.org_id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes,
    )
    session.add(record)
    await session.commit()
    return ApiKeyResponse(
        id=record.id,
        name=record.name,
        key_prefix=record.key_prefix,
        scopes=record.scopes,
        full_key=full_key,
    )
