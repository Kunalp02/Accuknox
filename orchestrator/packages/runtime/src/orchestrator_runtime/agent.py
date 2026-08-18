import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from orchestrator_llm.client import (
    GatewayConfig,
    chat_completion,
    create_openai_client,
    embed_texts,
)
from orchestrator_rag.qdrant import QdrantStore


@dataclass
class AgentConfig:
    system_prompt: str
    model: str
    temperature: float
    knowledge_base_ids: list[uuid.UUID]


@dataclass
class RunResult:
    output: str
    metrics: dict


async def execute_agent(
    gateway: GatewayConfig,
    agent: AgentConfig,
    user_input: str,
    org_id: uuid.UUID,
    on_token: Callable[[str, dict], Awaitable[None]] | None = None,
) -> RunResult:
    client = create_openai_client(gateway)
    messages: list[dict] = [{"role": "system", "content": agent.system_prompt}]

    if agent.knowledge_base_ids:
        embed_client = create_openai_client(gateway)
        vectors = await embed_texts(embed_client, gateway.embed_model, [user_input])
        store = QdrantStore()
        hits = await store.search(org_id, agent.knowledge_base_ids, vectors[0], limit=5)
        if hits:
            context = "\n\n".join(f"[{h['score']:.2f}] {h['text']}" for h in hits)
            messages.append(
                {
                    "role": "system",
                    "content": f"Relevant knowledge base context:\n{context}",
                }
            )

    messages.append({"role": "user", "content": user_input})

    if on_token:
        await on_token("message.start", {"role": "assistant"})

    content, usage = await chat_completion(
        client, agent.model, messages, temperature=agent.temperature
    )

    if on_token:
        await on_token("message.delta", {"content": content})
        await on_token("message.end", {})

    return RunResult(output=content, metrics=usage)
