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


_CLOUD_HOSTS = ("ollama.com", "api.openai.com", "openai.com")


def is_cloud_gateway(base_url: str) -> bool:
    normalized = base_url.lower()
    return any(host in normalized for host in _CLOUD_HOSTS)


def resolve_gateway_api_key(base_url: str, stored_key: str | None, platform_key: str) -> str:
    if stored_key:
        return stored_key
    if is_cloud_gateway(base_url) and platform_key in ("", "ollama"):
        return ""
    return platform_key


def effective_api_key(config: GatewayConfig) -> str:
    """Return the API key to send, or raise if a cloud gateway has no key."""
    if config.api_key:
        return config.api_key
    if is_cloud_gateway(config.base_url):
        raise ValueError(
            "API key required for cloud gateways (e.g. https://ollama.com/v1). "
            "Set OLLAMA_API_KEY or LLM_GATEWAY_KEY in .env, or save a key under Settings."
        )
    return "ollama"


def normalize_model_for_gateway(model: str, base_url: str) -> str:
    """
    Ollama Cloud hosted API uses plain model ids (gpt-oss:120b).
    Local Ollama offloads with a -cloud suffix (gpt-oss:120b-cloud).
    """
    if is_cloud_gateway(base_url) and model.endswith("-cloud"):
        return model[: -len("-cloud")]
    return model


def platform_gateway_config() -> GatewayConfig:
    base_url = normalize_gateway_base_url(settings.llm_gateway_url)
    return GatewayConfig(
        base_url=base_url,
        api_key=resolve_gateway_api_key(base_url, None, settings.effective_llm_gateway_key),
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
        api_key=effective_api_key(config),
        http_client=create_openai_http_client(),
    )


async def chat_completion(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
) -> tuple[str, dict]:
    if settings.llm_mock_mode:
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        content = f"[mock:{model}] {last_user}"
        usage = {"tokens_in": len(str(messages)), "tokens_out": len(content)}
        return content, usage

    response = await client.chat.completions.create(
        model=normalize_model_for_gateway(model, str(client.base_url)),
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
    if settings.llm_mock_mode:
        return [[0.1] * 8 for _ in texts]

    response = await client.embeddings.create(
        model=normalize_model_for_gateway(model, str(client.base_url)),
        input=texts,
    )
    return [item.embedding for item in response.data]


async def list_gateway_models(config: GatewayConfig) -> list[str]:
    """List models from an OpenAI-compatible gateway (e.g. Ollama Cloud /v1/models)."""
    client = create_openai_client(config)
    response = await client.models.list()
    return [item.id for item in response.data]
