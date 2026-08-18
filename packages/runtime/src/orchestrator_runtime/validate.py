"""Validate workflow graph structure before publish/save."""

from typing import Any

ALLOWED_TYPES = {"agent", "supervisor", "tool", "branch", "parallel", "human"}


def validate_workflow_graph(graph: dict) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    entry = graph.get("entry", "")

    if not nodes:
        errors.append("Workflow has no nodes")
        return {"valid": False, "errors": errors, "warnings": warnings}

    node_ids = {n.get("id") for n in nodes}
    if not entry:
        errors.append("Entry node is required")
    elif entry not in node_ids:
        errors.append(f"Entry node '{entry}' not found in graph")

    seen_ids: set[str] = set()
    for node in nodes:
        nid = node.get("id")
        ntype = node.get("type")
        if not nid:
            errors.append("Node missing id")
            continue
        if nid in seen_ids:
            errors.append(f"Duplicate node id: {nid}")
        seen_ids.add(nid)
        if ntype not in ALLOWED_TYPES:
            errors.append(f"Node {nid}: unknown type '{ntype}'")
            continue

        if ntype == "agent" and not node.get("agent_id"):
            errors.append(f"Node {nid}: agent_id required for agent nodes")
        if ntype == "supervisor":
            children = node.get("children", [])
            if not children:
                warnings.append(f"Node {nid}: supervisor has no children")
            for c in children:
                if c not in node_ids:
                    errors.append(f"Node {nid}: child '{c}' does not exist")
        if ntype == "tool":
            if not node.get("connection_id"):
                errors.append(f"Node {nid}: connection_id required for tool nodes")
            if not node.get("tool_name"):
                errors.append(f"Node {nid}: tool_name required for tool nodes")
        if ntype == "branch":
            branches = node.get("branches", [])
            if not branches and not node.get("default_to"):
                warnings.append(f"Node {nid}: branch node has no branches or default_to")
            for b in branches:
                if isinstance(b, dict):
                    if b.get("to") and b["to"] not in node_ids:
                        errors.append(f"Node {nid}: branch target '{b.get('to')}' not found")
        if ntype == "parallel":
            for b in node.get("branches", []):
                if b not in node_ids:
                    errors.append(f"Node {nid}: parallel branch '{b}' not found")
        if ntype == "human" and not node.get("prompt"):
            warnings.append(f"Node {nid}: human node has no prompt")

    for edge in edges:
        fr = edge.get("from")
        to = edge.get("to")
        if fr not in node_ids:
            errors.append(f"Edge from '{fr}' references missing node")
        if to not in node_ids:
            errors.append(f"Edge to '{to}' references missing node")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
