import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from orchestrator_llm.client import (
    GatewayConfig,
    chat_completion,
    create_openai_client,
    embed_texts,
)
from orchestrator_mcp.client import McpHttpClient
from orchestrator_rag.qdrant import QdrantStore


@dataclass
class McpToolBinding:
    connection_id: str
    connection_name: str
    tool_name: str
    description: str
    input_schema: dict


@dataclass
class AgentConfig:
    system_prompt: str
    model: str
    temperature: float
    knowledge_base_ids: list[uuid.UUID]
    mcp_tools: list[McpToolBinding] = field(default_factory=list)


@dataclass
class RunResult:
    output: str
    metrics: dict


async def _run_mcp_tool_loop(
    client: Any,
    model: str,
    messages: list[dict],
    tools: list[McpToolBinding],
    mcp_clients: dict[str, McpHttpClient],
    temperature: float,
    on_token: Callable[[str, dict], Awaitable[None]] | None,
) -> tuple[str, dict]:
    openai_tools = []
    tool_map: dict[str, tuple[str, str]] = {}
    for t in tools:
        fn_name = f"mcp_{t.connection_name}_{t.tool_name}".replace(".", "_").replace("-", "_")
        tool_map[fn_name] = (t.connection_id, t.tool_name)
        openai_tools.append({
            "type": "function",
            "function": {
                "name": fn_name,
                "description": t.description or f"MCP tool {t.tool_name}",
                "parameters": t.input_schema or {"type": "object", "properties": {}},
            },
        })

    usage_total = {"tokens_in": 0, "tokens_out": 0}
    max_rounds = 8

    for _ in range(max_rounds):
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            tools=openai_tools if openai_tools else None,
        )
        choice = response.choices[0]
        if response.usage:
            usage_total["tokens_in"] += response.usage.prompt_tokens
            usage_total["tokens_out"] += response.usage.completion_tokens

        if choice.finish_reason != "tool_calls" and not choice.message.tool_calls:
            content = choice.message.content or ""
            return content, usage_total

        messages.append(choice.message.model_dump(exclude_none=True))

        for tool_call in choice.message.tool_calls or []:
            fn = tool_call.function.name
            import json

            args = json.loads(tool_call.function.arguments or "{}")
            conn_id, tool_name = tool_map.get(fn, ("", ""))
            mcp = mcp_clients.get(conn_id)
            if not mcp:
                result_text = f"Error: MCP connection {conn_id} not found"
            else:
                try:
                    result_text = await mcp.call_tool(tool_name, args)
                except Exception as e:
                    result_text = f"Tool error: {e}"
            if on_token:
                await on_token("tool.call", {"tool": tool_name, "result": result_text[:300]})
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_text,
            })

    return messages[-1].get("content", "") if messages else "", usage_total


async def execute_agent(
    gateway: GatewayConfig,
    agent: AgentConfig,
    user_input: str,
    org_id: uuid.UUID,
    on_token: Callable[[str, dict], Awaitable[None]] | None = None,
    mcp_clients: dict[str, McpHttpClient] | None = None,
) -> RunResult:
    from orchestrator_core.config import settings

    if settings.llm_mock_mode:
        content = f"[mock:{agent.model}] {user_input}"
        if on_token:
            await on_token("message.start", {"role": "assistant"})
            await on_token("message.delta", {"content": content})
            await on_token("message.end", {})
        return RunResult(output=content, metrics={"tokens_in": 10, "tokens_out": 10})

    client = create_openai_client(gateway)
    messages: list[dict] = [{"role": "system", "content": agent.system_prompt}]

    if agent.knowledge_base_ids:
        embed_client = create_openai_client(gateway)
        vectors = await embed_texts(embed_client, gateway.embed_model, [user_input])
        store = QdrantStore()
        hits = await store.search(org_id, agent.knowledge_base_ids, vectors[0], limit=5)
        if hits:
            context = "\n\n".join(f"[{h['score']:.2f}] {h['text']}" for h in hits)
            messages.append({
                "role": "system",
                "content": f"Relevant knowledge base context:\n{context}",
            })

    messages.append({"role": "user", "content": user_input})

    if on_token:
        await on_token("message.start", {"role": "assistant"})

    mcp_map = mcp_clients or {}
    if agent.mcp_tools and mcp_map:
        content, usage = await _run_mcp_tool_loop(
            client,
            agent.model,
            messages,
            agent.mcp_tools,
            mcp_map,
            agent.temperature,
            on_token,
        )
    else:
        content, usage = await chat_completion(
            client, agent.model, messages, temperature=agent.temperature
        )

    if on_token:
        await on_token("message.delta", {"content": content})
        await on_token("message.end", {})

    return RunResult(output=content, metrics=usage)
