"""Resolve LLM gateway config per organization."""

from uuid import UUID

from orchestrator_core.config import settings
from orchestrator_core.models import LlmGatewayConfig
from orchestrator_core.security import decrypt_secret, encrypt_secret
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_llm.client import (
    GatewayConfig,
    normalize_gateway_base_url,
    platform_gateway_config,
)


async def get_gateway_for_org(session: AsyncSession, org_id: UUID) -> GatewayConfig:
    result = await session.execute(
        select(LlmGatewayConfig).where(LlmGatewayConfig.organization_id == org_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return platform_gateway_config()

    api_key = settings.llm_gateway_key
    if row.api_key_encrypted:
        api_key = decrypt_secret(row.api_key_encrypted)

    return GatewayConfig(
        base_url=normalize_gateway_base_url(row.base_url),
        api_key=api_key,
        default_model=row.default_model,
        embed_model=row.embed_model,
    )


async def upsert_gateway_config(
    session: AsyncSession,
    org_id: UUID,
    base_url: str,
    default_model: str,
    embed_model: str,
    api_key: str | None,
    allowed_models: list[str],
) -> LlmGatewayConfig:
    result = await session.execute(
        select(LlmGatewayConfig).where(LlmGatewayConfig.organization_id == org_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        row = LlmGatewayConfig(
            organization_id=org_id,
            base_url=normalize_gateway_base_url(base_url),
            default_model=default_model,
            embed_model=embed_model,
            allowed_models=allowed_models,
        )
        session.add(row)
    else:
        row.base_url = normalize_gateway_base_url(base_url)
        row.default_model = default_model
        row.embed_model = embed_model
        row.allowed_models = allowed_models

    if api_key:
        row.api_key_encrypted = encrypt_secret(api_key)
    await session.flush()
    return row


async def delete_gateway_config(session: AsyncSession, org_id: UUID) -> bool:
    result = await session.execute(
        select(LlmGatewayConfig).where(LlmGatewayConfig.organization_id == org_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return False
    await session.delete(row)
    return True
