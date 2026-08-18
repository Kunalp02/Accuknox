from dataclasses import dataclass

from openai import AsyncOpenAI

from orchestrator_core.config import settings


@dataclass
class GatewayConfig:
    base_url: str
    api_key: str
    default_model: str
    embed_model: str


def platform_gateway_config() -> GatewayConfig:
    return GatewayConfig(
        base_url=settings.llm_gateway_url,
        api_key=settings.llm_gateway_key,
        default_model=settings.llm_default_model,
        embed_model=settings.embed_model,
    )


def create_openai_client(config: GatewayConfig) -> AsyncOpenAI:
    return AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)


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
