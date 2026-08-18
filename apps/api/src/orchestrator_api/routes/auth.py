import re

from fastapi import APIRouter, Depends, HTTPException
from orchestrator_api.deps import AuthContext, get_auth_context
from orchestrator_core.database import get_session
from orchestrator_core.models import Organization, User
from orchestrator_core.security import create_access_token, hash_password, verify_password
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        org_check = await session.execute(select(Organization).where(Organization.slug == slug))
        if not org_check.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization(name=body.org_name, slug=slug)
    session.add(org)
    await session.flush()

    user = User(
        organization_id=org.id,
        email=body.email,
        password_hash=hash_password(body.password),
        role="owner",
    )
    session.add(user)
    await session.commit()

    token = create_access_token(str(user.id), str(org.id), user.role)
    return TokenResponse(
        access_token=token,
        org_id=str(org.id),
        user_id=str(user.id),
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token(str(user.id), str(user.organization_id), user.role)
    return TokenResponse(
        access_token=token,
        org_id=str(user.organization_id),
        user_id=str(user.id),
        role=user.role,
    )


@router.get("/me")
async def me(auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.id == auth.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role,
        "org_id": str(user.organization_id),
    }
