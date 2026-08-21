"""Workflow runtime execution tests (mocked LLM)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator_llm.client import GatewayConfig
from orchestrator_runtime.agent import AgentConfig, RunResult
from orchestrator_runtime.workflow import execute_workflow


@pytest.fixture
def gateway():
    return GatewayConfig(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        default_model="llama3.2",
        embed_model="nomic-embed-text",
    )


@pytest.fixture
def agents():
    a1 = AgentConfig(
        system_prompt="Researcher",
        model="llama3.2",
        temperature=0.7,
        knowledge_base_ids=[],
    )
    a2 = AgentConfig(
        system_prompt="Writer",
        model="llama3.2",
        temperature=0.7,
        knowledge_base_ids=[],
    )
    return {
        "agent-1": a1,
        "agent-2": a2,
    }


@pytest.mark.asyncio
async def test_sequential_multi_agent_workflow(gateway, agents):
    graph = {
        "entry": "researcher",
        "nodes": [
            {"id": "researcher", "type": "agent", "agent_id": "agent-1"},
            {"id": "writer", "type": "agent", "agent_id": "agent-2"},
        ],
        "edges": [{"from": "researcher", "to": "writer"}],
    }

    call_count = 0

    async def fake_execute_agent(gw, agent_cfg, user_input, org_id, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return RunResult(output="research facts", metrics={"tokens_in": 5, "tokens_out": 5})
        return RunResult(output=f"summary of: {user_input}", metrics={"tokens_in": 5, "tokens_out": 5})

    events: list[tuple[str, dict]] = []

    async def on_event(event_type: str, data: dict) -> None:
        events.append((event_type, data))

    with patch("orchestrator_runtime.workflow.execute_agent", side_effect=fake_execute_agent):
        state, metrics = await execute_workflow(
            graph,
            gateway,
            uuid.uuid4(),
            "test topic",
            {},
            agents,
            {},
            on_event=on_event,
        )

    assert state.last_output.startswith("summary of:")
    assert "researcher" in state.node_outputs
    assert "writer" in state.node_outputs
    assert metrics["steps"] == 2
    assert any(e[0] == "step.start" for e in events)


@pytest.mark.asyncio
async def test_supervisor_routes_to_child(gateway, agents):
    graph = {
        "entry": "supervisor_1",
        "nodes": [
            {"id": "supervisor_1", "type": "supervisor", "children": ["researcher", "writer"]},
            {"id": "researcher", "type": "agent", "agent_id": "agent-1"},
            {"id": "writer", "type": "agent", "agent_id": "agent-2"},
        ],
        "edges": [
            {"from": "supervisor_1", "to": "researcher", "condition": "route == researcher"},
            {"from": "researcher", "to": "writer"},
        ],
    }

    async def fake_chat(client, model, messages, temperature=0.7):
        return "researcher", {"tokens_in": 3, "tokens_out": 1}

    async def fake_execute_agent(gw, agent_cfg, user_input, org_id, **kwargs):
        return RunResult(output=f"output from {agent_cfg.system_prompt}", metrics={"tokens_in": 1, "tokens_out": 1})

    with (
        patch("orchestrator_runtime.workflow.chat_completion", side_effect=fake_chat),
        patch("orchestrator_runtime.workflow.execute_agent", side_effect=fake_execute_agent),
    ):
        state, metrics = await execute_workflow(
            graph,
            gateway,
            uuid.uuid4(),
            "route me",
            {},
            agents,
            {},
        )

    assert state.variables.get("route") == "researcher"
    assert "researcher" in state.node_outputs
    assert metrics["steps"] >= 2


@pytest.mark.asyncio
async def test_supervisor_honors_route_when_first_edge_unconditional(gateway, agents):
    """Regression: unconditional first edge must not override an explicit writer route."""
    graph = {
        "entry": "supervisor_1",
        "nodes": [
            {
                "id": "supervisor_1",
                "type": "supervisor",
                "children": ["researcher_node", "writer_node"],
            },
            {"id": "researcher_node", "type": "agent", "agent_id": "agent-1"},
            {"id": "writer_node", "type": "agent", "agent_id": "agent-2"},
        ],
        "edges": [
            {"from": "supervisor_1", "to": "researcher_node"},
            {
                "from": "supervisor_1",
                "to": "writer_node",
                "condition": "route == writer_node",
            },
        ],
    }

    async def fake_chat(client, model, messages, temperature=0.7):
        return "writer_node", {"tokens_in": 3, "tokens_out": 1}

    async def fake_execute_agent(gw, agent_cfg, user_input, org_id, **kwargs):
        marker = "[WRITER_AGENT]" if agent_cfg.system_prompt == "Writer" else "[RESEARCH_AGENT]"
        return RunResult(output=marker, metrics={"tokens_in": 1, "tokens_out": 1})

    with (
        patch("orchestrator_runtime.workflow.chat_completion", side_effect=fake_chat),
        patch("orchestrator_runtime.workflow.execute_agent", side_effect=fake_execute_agent),
    ):
        state, metrics = await execute_workflow(
            graph,
            gateway,
            uuid.uuid4(),
            "Call writing agent",
            {},
            agents,
            {},
        )

    assert state.variables.get("route") == "writer_node"
    assert "writer_node" in state.node_outputs
    assert "researcher_node" not in state.node_outputs
    assert state.last_output == "[WRITER_AGENT]"
    assert metrics["steps"] == 2


@pytest.mark.asyncio
async def test_supervisor_routes_without_edges(gateway, agents):
    graph = {
        "entry": "supervisor_1",
        "nodes": [
            {
                "id": "supervisor_1",
                "type": "supervisor",
                "children": ["researcher_node", "writer_node"],
            },
            {"id": "researcher_node", "type": "agent", "agent_id": "agent-1"},
            {"id": "writer_node", "type": "agent", "agent_id": "agent-2"},
        ],
        "edges": [],
    }

    async def fake_chat(client, model, messages, temperature=0.7):
        return "writer_node", {"tokens_in": 3, "tokens_out": 1}

    async def fake_execute_agent(gw, agent_cfg, user_input, org_id, **kwargs):
        return RunResult(output=f"output from {agent_cfg.system_prompt}", metrics={"tokens_in": 1, "tokens_out": 1})

    with (
        patch("orchestrator_runtime.workflow.chat_completion", side_effect=fake_chat),
        patch("orchestrator_runtime.workflow.execute_agent", side_effect=fake_execute_agent),
    ):
        state, _ = await execute_workflow(
            graph,
            gateway,
            uuid.uuid4(),
            "Call writing agent",
            {},
            agents,
            {},
        )

    assert state.variables.get("route") == "writer_node"
    assert "writer_node" in state.node_outputs
    assert "researcher_node" not in state.node_outputs


@pytest.mark.asyncio
async def test_human_node_pauses(gateway, agents):
    graph = {
        "entry": "human_1",
        "nodes": [
            {"id": "human_1", "type": "human", "prompt": "Approve?"},
            {"id": "writer", "type": "agent", "agent_id": "agent-2"},
        ],
        "edges": [{"from": "human_1", "to": "writer"}],
    }

    state, metrics = await execute_workflow(
        graph,
        gateway,
        uuid.uuid4(),
        "hello",
        {},
        agents,
        {},
    )

    assert state.pending_human_node == "human_1"
    assert metrics["steps"] == 1
