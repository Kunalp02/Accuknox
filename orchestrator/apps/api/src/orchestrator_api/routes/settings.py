import uuid

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.config import settings
from orchestrator_core.database import get_session
from orchestrator_core.models import LlmGatewayConfig
from orchestrator_core.rbac import has_permission
from sqlalchemy import select

from orchestrator_api.deps import AuthContext, get_auth_context
from orchestrator_llm.gateway import (
    delete_gateway_config,
    get_gateway_for_org,
    upsert_gateway_config,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class GatewaySettingsResponse(BaseModel):
    uses_platform_default: bool
    base_url: str | None = None
    default_model: str | None = None
    embed_model: str | None = None
    allowed_models: list[str] = []
    has_api_key: bool = False
    platform_default_model: str
    platform_embed_model: str


class GatewaySettingsUpdate(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    default_model: str = Field(min_length=1, max_length=100)
    embed_model: str = Field(default="nomic-embed-text", max_length=100)
    api_key: str | None = None
    allowed_models: list[str] = []


def _check(auth: AuthContext, permission: str) -> None:
    if auth.is_api_key:
        raise HTTPException(status_code=403, detail="Not allowed")
    if not auth.role or not has_permission(auth.role, permission):
        raise HTTPException(status_code=403, detail="Permission denied")


@router.get("/llm-gateway", response_model=GatewaySettingsResponse)
async def get_llm_gateway_settings(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "org:read")
    result = await session.execute(
        select(LlmGatewayConfig).where(LlmGatewayConfig.organization_id == auth.org_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return GatewaySettingsResponse(
            uses_platform_default=True,
            platform_default_model=settings.llm_default_model,
            platform_embed_model=settings.embed_model,
        )
    return GatewaySettingsResponse(
        uses_platform_default=False,
        base_url=row.base_url,
        default_model=row.default_model,
        embed_model=row.embed_model,
        allowed_models=row.allowed_models or [],
        has_api_key=bool(row.api_key_encrypted),
        platform_default_model=settings.llm_default_model,
        platform_embed_model=settings.embed_model,
    )


@router.put("/llm-gateway", response_model=GatewaySettingsResponse)
async def update_llm_gateway_settings(
    body: GatewaySettingsUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "org:write")
    await upsert_gateway_config(
        session,
        auth.org_id,
        body.base_url.rstrip("/"),
        body.default_model,
        body.embed_model,
        body.api_key,
        body.allowed_models,
    )
    await session.commit()
    return await get_llm_gateway_settings(auth, session)


@router.delete("/llm-gateway", status_code=204)
async def clear_llm_gateway_settings(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "org:write")
    await delete_gateway_config(session, auth.org_id)
    await session.commit()


@router.post("/llm-gateway/test")
async def test_llm_gateway(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "org:read")
    gateway = await get_gateway_for_org(session, auth.org_id)
    client = AsyncOpenAI(base_url=gateway.base_url, api_key=gateway.api_key)
    try:
        models = await client.models.list()
        model_ids = [m.id for m in models.data[:20]]
        return {
            "ok": True,
            "base_url": gateway.base_url,
            "models_sample": model_ids,
            "default_model": gateway.default_model,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "base_url": gateway.base_url}
