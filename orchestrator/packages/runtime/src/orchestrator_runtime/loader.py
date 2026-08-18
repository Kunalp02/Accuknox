"""Build agent configs and MCP clients from DB models."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.models import Agent, McpConnection
from orchestrator_core.security import decrypt_secret
from orchestrator_mcp.client import McpAuth, McpHttpClient
from orchestrator_runtime.agent import AgentConfig, McpToolBinding


async def load_mcp_clients(
    session: AsyncSession,
    org_id: uuid.UUID,
    connection_ids: list[uuid.UUID] | None = None,
) -> dict[str, McpHttpClient]:
    q = select(McpConnection).where(McpConnection.organization_id == org_id)
    if connection_ids:
        q = q.where(McpConnection.id.in_(connection_ids))
    result = await session.execute(q)
    connections = result.scalars().all()
    clients: dict[str, McpHttpClient] = {}
    for conn in connections:
        auth = None
        if conn.auth_type and conn.auth_credentials_encrypted:
            auth = McpAuth(
                auth_type=conn.auth_type,
                credentials=decrypt_secret(conn.auth_credentials_encrypted),
            )
        clients[str(conn.id)] = McpHttpClient(conn.base_url, auth)
    return clients


async def build_agent_config(session: AsyncSession, agent: Agent) -> AgentConfig:
    kb_ids = [uuid.UUID(k) for k in agent.config.get("knowledge_base_ids", [])]
    mcp_bindings: list[McpToolBinding] = []
    mcp_tool_cfg = agent.config.get("mcp_tools", [])

    connection_ids = [
        uuid.UUID(t["connection_id"]) for t in mcp_tool_cfg if t.get("connection_id")
    ]
    if connection_ids:
        result = await session.execute(
            select(McpConnection).where(
                McpConnection.organization_id == agent.organization_id,
                McpConnection.id.in_(connection_ids),
            )
        )
        conn_map = {str(c.id): c for c in result.scalars().all()}

        for entry in mcp_tool_cfg:
            conn_id = entry.get("connection_id", "")
            conn = conn_map.get(conn_id)
            if not conn:
                continue
            tool_names = entry.get("tools", [])
            discovered = {t.get("name"): t for t in conn.discovered_tools or []}
            allowlist = set(conn.tool_allowlist or [])
            for tool_name in tool_names:
                if allowlist and tool_name not in allowlist:
                    continue
                meta = discovered.get(tool_name, {})
                mcp_bindings.append(
                    McpToolBinding(
                        connection_id=conn_id,
                        connection_name=conn.name,
                        tool_name=tool_name,
                        description=meta.get("description", ""),
                        input_schema=meta.get("input_schema", {}),
                    )
                )

    return AgentConfig(
        system_prompt=agent.system_prompt,
        model=agent.model,
        temperature=agent.temperature,
        knowledge_base_ids=kb_ids,
        mcp_tools=mcp_bindings,
    )


async def build_workflow_agent_map(
    session: AsyncSession,
    org_id: uuid.UUID,
    graph: dict,
) -> dict[str, AgentConfig]:
    agent_ids: set[uuid.UUID] = set()
    for node in graph.get("nodes", []):
        if node.get("type") == "agent" and node.get("agent_id"):
            try:
                agent_ids.add(uuid.UUID(node["agent_id"]))
            except ValueError:
                pass

    agents: dict[str, AgentConfig] = {}
    if not agent_ids:
        return agents

    result = await session.execute(
        select(Agent).where(Agent.organization_id == org_id, Agent.id.in_(agent_ids))
    )
    for agent in result.scalars().all():
        agents[str(agent.id)] = await build_agent_config(session, agent)
    return agents
