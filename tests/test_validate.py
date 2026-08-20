"""Workflow graph validation tests."""

from orchestrator_runtime.validate import validate_workflow_graph


def test_valid_sequential_agents():
    graph = {
        "entry": "a1",
        "nodes": [
            {"id": "a1", "type": "agent", "agent_id": "00000000-0000-0000-0000-000000000001"},
            {"id": "a2", "type": "agent", "agent_id": "00000000-0000-0000-0000-000000000002"},
        ],
        "edges": [{"from": "a1", "to": "a2"}],
    }
    result = validate_workflow_graph(graph)
    assert result["valid"] is True
    assert result["errors"] == []


def test_missing_agent_id():
    graph = {
        "entry": "a1",
        "nodes": [{"id": "a1", "type": "agent"}],
        "edges": [],
    }
    result = validate_workflow_graph(graph)
    assert result["valid"] is False
    assert any("agent_id required" in e for e in result["errors"])


def test_supervisor_missing_children_warning():
    graph = {
        "entry": "s1",
        "nodes": [
            {"id": "s1", "type": "supervisor", "children": []},
            {"id": "a1", "type": "agent", "agent_id": "00000000-0000-0000-0000-000000000001"},
        ],
        "edges": [],
    }
    result = validate_workflow_graph(graph)
    assert any("supervisor has no children" in w for w in result["warnings"])


def test_invalid_entry_node():
    graph = {
        "entry": "missing",
        "nodes": [{"id": "a1", "type": "agent", "agent_id": "x"}],
        "edges": [],
    }
    result = validate_workflow_graph(graph)
    assert result["valid"] is False
    assert any("Entry node" in e for e in result["errors"])
