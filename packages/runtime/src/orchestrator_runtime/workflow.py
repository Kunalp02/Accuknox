"""Workflow graph execution."""

import asyncio
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from orchestrator_llm.client import GatewayConfig, chat_completion, create_openai_client
from orchestrator_mcp.client import McpHttpClient

from orchestrator_runtime.agent import AgentConfig, execute_agent


@dataclass
class WorkflowState:
    messages: list[dict] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    node_outputs: dict[str, Any] = field(default_factory=dict)
    last_output: str = ""
    pending_human_node: str | None = None
    current_node_id: str | None = None


@dataclass
class WorkflowGraph:
    entry: str
    nodes: list[dict]
    edges: list[dict]


EventCallback = Callable[[str, dict], Awaitable[None]]


def parse_graph(graph: dict) -> WorkflowGraph:
    return WorkflowGraph(
        entry=graph.get("entry", ""),
        nodes=graph.get("nodes", []),
        edges=graph.get("edges", []),
    )


def _node_by_id(graph: WorkflowGraph, node_id: str) -> dict | None:
    for n in graph.nodes:
        if n.get("id") == node_id:
            return n
    return None


def _outgoing_edges(graph: WorkflowGraph, node_id: str) -> list[dict]:
    return [e for e in graph.edges if e.get("from") == node_id]


def _eval_condition(condition: str, state: WorkflowState) -> bool:
    if not condition:
        return True
    # Simple expressions: route == value, variables.key == value
    m = re.match(r"variables\.(\w+)\s*==\s*['\"]?(\w+)['\"]?", condition.strip())
    if m:
        return str(state.variables.get(m.group(1))) == m.group(2)
    m = re.match(r"route\s*==\s*['\"]?(\w+)['\"]?", condition.strip())
    if m:
        return str(state.variables.get("route")) == m.group(1)
    if condition.strip().lower() == "true":
        return True
    return bool(state.variables.get(condition))


async def execute_workflow(
    graph: dict,
    gateway: GatewayConfig,
    org_id: uuid.UUID,
    user_input: str,
    context: dict,
    agents: dict[str, AgentConfig],
    mcp_clients: dict[str, McpHttpClient],
    on_event: EventCallback | None = None,
    initial_state: WorkflowState | None = None,
    start_node_id: str | None = None,
) -> tuple[WorkflowState, dict]:
    wf = parse_graph(graph)
    state = initial_state or WorkflowState(
        messages=[{"role": "user", "content": user_input}],
        variables={"input": user_input, **context},
    )
    metrics: dict[str, int] = {"tokens_in": 0, "tokens_out": 0, "steps": 0}

    node_id = start_node_id or wf.entry
    if not node_id:
        raise ValueError("Workflow has no entry node")

    async def emit(event_type: str, data: dict) -> None:
        if on_event:
            await on_event(event_type, data)

    while node_id:
        node = _node_by_id(wf, node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        node_type = node.get("type", "agent")
        state.current_node_id = node_id
        await emit("step.start", {"node_id": node_id, "type": node_type})

        if node_type == "agent":
            agent_id = node.get("agent_id", "")
            agent_cfg = agents.get(agent_id)
            if not agent_cfg:
                raise ValueError(f"Agent {agent_id} not configured for workflow")
            last_msg = state.messages[-1]["content"] if state.messages else user_input
            result = await execute_agent(
                gateway, agent_cfg, last_msg, org_id, on_token=on_event
            )
            state.last_output = result.output
            state.node_outputs[node_id] = result.output
            state.messages.append({"role": "assistant", "content": result.output})
            for k, v in result.metrics.items():
                if k in metrics and isinstance(v, int):
                    metrics[k] += v
            metrics["steps"] += 1

        elif node_type == "supervisor":
            children = node.get("children", [])
            child_descriptions = "\n".join(
                f"- {c}: {_node_by_id(wf, c).get('type', 'agent')}" for c in children
            )
            client = create_openai_client(gateway)
            supervisor_model = node.get("model") or gateway.default_model
            prompt = node.get(
                "system_prompt",
                f"You are a supervisor. Route to one child node id. Children:\n{child_descriptions}",
            )
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": state.messages[-1]["content"]},
            ]
            content, usage = await chat_completion(client, supervisor_model, messages, 0.3)
            route = children[0] if children else ""
            for child in children:
                if child in content:
                    route = child
                    break
            state.variables["route"] = route
            state.node_outputs[node_id] = {"route": route, "raw": content}
            metrics["tokens_in"] += usage.get("tokens_in", 0)
            metrics["tokens_out"] += usage.get("tokens_out", 0)
            metrics["steps"] += 1
            await emit("step.supervisor", {"route": route})

            edges = _outgoing_edges(wf, node_id)
            next_id = None
            for edge in edges:
                if edge.get("to") == route or _eval_condition(edge.get("condition", ""), state):
                    next_id = edge.get("to")
                    break
            if next_id:
                node_id = next_id
                await emit("step.end", {"node_id": node_id})
                continue
            node_id = route if route in children else None
            await emit("step.end", {"node_id": node_id})
            continue

        elif node_type == "tool":
            conn_id = node.get("connection_id", "")
            tool_name = node.get("tool_name", "")
            args = node.get("arguments", {})
            # Substitute variables in args
            resolved_args = {}
            for k, v in args.items():
                if isinstance(v, str) and v.startswith("$"):
                    key = v[1:]
                    resolved_args[k] = state.variables.get(key, state.last_output)
                else:
                    resolved_args[k] = v
            client = mcp_clients.get(conn_id)
            if not client:
                raise ValueError(f"MCP connection {conn_id} not available")
            tool_result = await client.call_tool(tool_name, resolved_args)
            state.last_output = tool_result
            state.node_outputs[node_id] = tool_result
            state.messages.append({"role": "assistant", "content": tool_result})
            metrics["steps"] += 1
            await emit("step.tool", {"tool": tool_name, "result": tool_result[:500]})

        elif node_type == "branch":
            branches = node.get("branches", [])
            chosen = None
            for branch in branches:
                cond = branch.get("condition", "true")
                if _eval_condition(cond, state):
                    chosen = branch.get("to")
                    break
            if not chosen:
                chosen = node.get("default_to")
            state.node_outputs[node_id] = {"chosen": chosen}
            metrics["steps"] += 1
            node_id = chosen
            await emit("step.end", {"node_id": node_id})
            continue

        elif node_type == "parallel":
            branch_ids = node.get("branches", [])
            async def run_branch(branch_start: str) -> tuple[str, Any]:
                branch_state, branch_metrics = await execute_workflow(
                    graph,
                    gateway,
                    org_id,
                    user_input,
                    context,
                    agents,
                    mcp_clients,
                    on_event=on_event,
                    initial_state=WorkflowState(
                        messages=list(state.messages),
                        variables=dict(state.variables),
                        node_outputs=dict(state.node_outputs),
                    ),
                    start_node_id=branch_start,
                )
                return branch_start, branch_state.last_output

            results = await asyncio.gather(*[run_branch(b) for b in branch_ids])
            merged = {bid: out for bid, out in results}
            state.node_outputs[node_id] = merged
            state.last_output = "\n---\n".join(
                f"{k}: {v}" for k, v in merged.items()
            )
            state.messages.append({"role": "assistant", "content": state.last_output})
            metrics["steps"] += 1

        elif node_type == "human":
            state.pending_human_node = node_id
            state.node_outputs[node_id] = {
                "prompt": node.get("prompt", "Approval required"),
                "status": "awaiting_input",
            }
            metrics["steps"] += 1
            await emit("run.awaiting_input", {
                "node_id": node_id,
                "prompt": node.get("prompt", "Approval required"),
            })
            return state, metrics

        else:
            raise ValueError(f"Unknown node type: {node_type}")

        await emit("step.end", {"node_id": node_id})

        edges = _outgoing_edges(wf, node_id)
        if not edges:
            break
        next_id = None
        for edge in edges:
            cond = edge.get("condition", "")
            if not cond or _eval_condition(cond, state):
                next_id = edge.get("to")
                break
        if not next_id and edges:
            next_id = edges[0].get("to")
        node_id = next_id

    return state, metrics


def state_to_dict(state: WorkflowState) -> dict:
    return {
        "messages": state.messages,
        "variables": state.variables,
        "node_outputs": state.node_outputs,
        "last_output": state.last_output,
        "pending_human_node": state.pending_human_node,
        "current_node_id": state.current_node_id,
    }


def state_from_dict(data: dict) -> WorkflowState:
    return WorkflowState(
        messages=data.get("messages", []),
        variables=data.get("variables", {}),
        node_outputs=data.get("node_outputs", {}),
        last_output=data.get("last_output", ""),
        pending_human_node=data.get("pending_human_node"),
        current_node_id=data.get("current_node_id"),
    )


def next_node_after(graph: dict, node_id: str, state: WorkflowState) -> str | None:
    wf = parse_graph(graph)
    edges = _outgoing_edges(wf, node_id)
    for edge in edges:
        cond = edge.get("condition", "")
        if not cond or _eval_condition(cond, state):
            return edge.get("to")
    return edges[0].get("to") if edges else None
