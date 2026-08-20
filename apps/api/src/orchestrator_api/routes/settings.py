from fastapi import APIRouter, Depends, HTTPException
from orchestrator_api.deps import AuthContext, get_auth_context
from orchestrator_core.config import settings
from orchestrator_core.database import get_session
from orchestrator_core.models import LlmGatewayConfig
from orchestrator_core.rbac import has_permission
from orchestrator_llm.client import (
    chat_completion,
    create_openai_client,
    is_cloud_gateway,
    normalize_gateway_base_url,
)
from orchestrator_llm.gateway import (
    delete_gateway_config,
    get_gateway_for_org,
    upsert_gateway_config,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    base_url = normalize_gateway_base_url(body.base_url)
    if is_cloud_gateway(base_url):
        result = await session.execute(
            select(LlmGatewayConfig).where(LlmGatewayConfig.organization_id == auth.org_id)
        )
        existing = result.scalar_one_or_none()
        has_key = bool(body.api_key) or bool(existing and existing.api_key_encrypted)
        if not has_key:
            raise HTTPException(
                status_code=400,
                detail="API key required for cloud gateways. Paste your key from ollama.com/settings/keys.",
            )

    await upsert_gateway_config(
        session,
        auth.org_id,
        normalize_gateway_base_url(body.base_url),
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
    base_url = normalize_gateway_base_url(gateway.base_url)

    if is_cloud_gateway(base_url) and not gateway.api_key:
        return {
            "ok": False,
            "error": "API key required for cloud gateways (e.g. ollama.com)",
            "base_url": base_url,
            "hint": "Create a key at https://ollama.com/settings/keys and paste it in the API key field before Save. "
            "Use model gpt-oss:120b (not gpt-oss:120b-cloud) for direct ollama.com/v1 calls.",
        }

    if settings.llm_mock_mode:
        preview, _ = await chat_completion(
            create_openai_client(gateway),
            gateway.default_model,
            [{"role": "user", "content": "ping"}],
        )
        return {
            "ok": True,
            "base_url": base_url,
            "default_model": gateway.default_model,
            "response_preview": preview,
            "mock_mode": True,
        }

    client = create_openai_client(gateway)
    try:
        preview, _ = await chat_completion(
            client,
            gateway.default_model,
            [{"role": "user", "content": "ping"}],
        )
        return {
            "ok": True,
            "base_url": base_url,
            "default_model": gateway.default_model,
            "response_preview": preview.strip(),
            "verify_ssl": settings.llm_gateway_verify_ssl,
            "trust_env": settings.llm_gateway_trust_env,
        }
    except Exception as e:
        hint = (
            "Cloud gateway: set a real API key (not 'ollama'). "
            "Corporate gateway: try https://aigw.ccilindia.net/v1. "
            "Self-signed cert: LLM_GATEWAY_VERIFY_SSL=false. "
            "Bypass proxy: LLM_GATEWAY_TRUST_ENV=false."
        )
        return {
            "ok": False,
            "error": str(e),
            "base_url": base_url,
            "hint": hint,
        }
