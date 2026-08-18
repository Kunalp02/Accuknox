from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI
from orchestrator_core.config import settings


@dataclass
class GatewayConfig:
    base_url: str
    api_key: str
    default_model: str
    embed_model: str


def normalize_gateway_base_url(url: str) -> str:
    """OpenAI client expects base_url ending in /v1."""
    normalized = url.strip().rstrip("/")
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


def platform_gateway_config() -> GatewayConfig:
    return GatewayConfig(
        base_url=normalize_gateway_base_url(settings.llm_gateway_url),
        api_key=settings.llm_gateway_key,
        default_model=settings.llm_default_model,
        embed_model=settings.embed_model,
    )


def create_openai_http_client() -> httpx.AsyncClient:
    """
    trust_env=False ignores system HTTP_PROXY (direct connection, like curl without proxy).
    Set LLM_GATEWAY_VERIFY_SSL=false for self-signed certs (like curl -k).
    """
    return httpx.AsyncClient(
        verify=settings.llm_gateway_verify_ssl,
        trust_env=settings.llm_gateway_trust_env,
        timeout=httpx.Timeout(120.0, connect=30.0),
    )


def create_openai_client(config: GatewayConfig) -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=normalize_gateway_base_url(config.base_url),
        api_key=config.api_key or "ollama",
        http_client=create_openai_http_client(),
    )


async def chat_completion(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
) -> tuple[str, dict]:
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    content = response.choices[0].message.content or ""
    usage = {}
    if response.usage:
        usage = {
            "tokens_in": response.usage.prompt_tokens,
            "tokens_out": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    return content, usage


async def embed_texts(
    client: AsyncOpenAI,
    model: str,
    texts: list[str],
) -> list[list[float]]:
    response = await client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]
