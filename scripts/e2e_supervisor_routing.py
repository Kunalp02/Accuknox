#!/usr/bin/env python3
"""
Test supervisor routing: 2 specialist agents + supervisor node.
Verifies the supervisor routes to the correct agent based on input.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

import httpx

API = os.environ.get("API_BASE", "http://localhost:8000")
OLLAMA_KEY = os.environ.get("OLLAMA_API_KEY", os.environ.get("LLM_GATEWAY_KEY", ""))
GATEWAY_URL = os.environ.get("LLM_GATEWAY_URL", "https://ollama.com/v1")
CHAT_MODEL = os.environ.get("LLM_DEFAULT_MODEL", "gpt-oss:120b-cloud")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK: {msg}")


async def setup_org(client: httpx.AsyncClient) -> dict:
    email = f"supervisor-{uuid.uuid4().hex[:8]}@example.com"
    signup = await client.post(
        f"{API}/v1/auth/signup",
        json={"email": email, "password": "password123", "org_name": "Supervisor Test"},
    )
    if signup.status_code != 200:
        fail(f"Signup failed: {signup.text}")
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    gw = await client.put(
        f"{API}/v1/settings/llm-gateway",
        headers=headers,
        json={
            "base_url": GATEWAY_URL,
            "default_model": CHAT_MODEL,
            "embed_model": "nomic-embed-text:latest",
            "api_key": OLLAMA_KEY,
        },
    )
    if gw.status_code != 200:
        fail(f"Gateway config failed: {gw.text}")
    ok("Org + gateway configured")
    return headers


async def create_supervisor_workflow(client: httpx.AsyncClient, headers: dict) -> tuple[str, str, str]:
    """Create researcher + writer agents and supervisor workflow. Returns (wf_id, researcher_id, writer_id)."""
    researcher = await client.post(
        f"{API}/v1/agents",
        headers=headers,
        json={
            "name": "Research Agent",
            "system_prompt": (
                "You are a RESEARCH specialist. Always start your reply with exactly: "
                "[RESEARCH_AGENT] then provide 2 bullet points of factual research. "
                "Never write prose paragraphs."
            ),
            "model": CHAT_MODEL,
        },
    )
    writer = await client.post(
        f"{API}/v1/agents",
        headers=headers,
        json={
            "name": "Writing Agent",
            "system_prompt": (
                "You are a WRITING specialist. Always start your reply with exactly: "
                "[WRITER_AGENT] then write one polished paragraph. Never use bullet points."
            ),
            "model": CHAT_MODEL,
        },
    )
    if researcher.status_code != 201 or writer.status_code != 201:
        fail(f"Agent creation failed: {researcher.text} / {writer.text}")

    r_id = researcher.json()["id"]
    w_id = writer.json()["id"]

    graph = {
        "entry": "supervisor_1",
        "nodes": [
            {
                "id": "supervisor_1",
                "type": "supervisor",
                "children": ["researcher_node", "writer_node"],
                "system_prompt": (
                    "You are a routing supervisor. Reply with ONLY the node id to route to.\n"
                    "Children:\n"
                    "- researcher_node: for research, facts, investigation, analysis questions\n"
                    "- writer_node: for writing, summaries, essays, creative text\n\n"
                    "Reply with exactly one of: researcher_node or writer_node"
                ),
                "model": CHAT_MODEL,
            },
            {"id": "researcher_node", "type": "agent", "agent_id": r_id},
            {"id": "writer_node", "type": "agent", "agent_id": w_id},
        ],
        "edges": [
            {"from": "supervisor_1", "to": "researcher_node", "condition": "route == researcher_node"},
            {"from": "supervisor_1", "to": "writer_node", "condition": "route == writer_node"},
        ],
    }

    wf = await client.post(
        f"{API}/v1/workflows",
        headers=headers,
        json={"name": "Supervisor Routing Test", "graph": graph},
    )
    if wf.status_code != 201:
        fail(f"Workflow create failed: {wf.text}")
    wf_id = wf.json()["id"]

    val = await client.post(f"{API}/v1/workflows/{wf_id}/validate", headers=headers)
    if not val.json().get("valid"):
        fail(f"Validation failed: {val.json()}")

    pub = await client.post(f"{API}/v1/workflows/{wf_id}/publish", headers=headers)
    if pub.status_code != 200:
        fail(f"Publish failed: {pub.text}")

    ok("Supervisor workflow created (researcher_node + writer_node)")
    return wf_id, r_id, w_id


async def invoke_and_verify(
    client: httpx.AsyncClient,
    headers: dict,
    wf_id: str,
    test_input: str,
    expected_route: str,
    expected_marker: str,
    not_expected_marker: str,
) -> None:
    print(f"\n--- Test: {test_input[:60]}... ---")
    print(f"Expected route: {expected_route}, expected output marker: {expected_marker}")

    invoke = await client.post(
        f"{API}/v1/workflows/{wf_id}/invoke",
        headers=headers,
        json={"input": test_input},
    )
    if invoke.status_code != 202:
        fail(f"Invoke failed: {invoke.status_code} {invoke.text}")

    run_id = invoke.json()["run_id"]
    deadline = time.time() + 120
    run = None
    while time.time() < deadline:
        res = await client.get(f"{API}/v1/runs/{run_id}", headers=headers)
        run = res.json()
        if run["status"] in ("completed", "failed", "awaiting_input"):
            break
        await asyncio.sleep(1)

    if not run or run["status"] != "completed":
        fail(f"Run failed or timed out: status={run and run['status']} error={run and run.get('error')}")

    node_outputs = run.get("output", {}).get("node_outputs", {})
    trace = run.get("trace", [])

    # Find supervisor routing decision in trace
    supervisor_route = None
    for entry in trace:
        if isinstance(entry, dict) and entry.get("type") == "step.supervisor":
            supervisor_route = entry.get("data", {}).get("route")
        elif isinstance(entry, dict) and entry.get("type") == "step.start":
            pass

    # Also check supervisor node output
    sup_output = node_outputs.get("supervisor_1", {})
    if isinstance(sup_output, dict):
        route_from_output = sup_output.get("route")
        if route_from_output:
            supervisor_route = route_from_output

    print(f"Supervisor routed to: {supervisor_route}")
    print(f"Nodes executed: {list(node_outputs.keys())}")

    if supervisor_route != expected_route:
        fail(
            f"Wrong route! Expected '{expected_route}' but got '{supervisor_route}'. "
            f"Supervisor raw: {sup_output.get('raw', '')[:200] if isinstance(sup_output, dict) else sup_output}"
        )
    ok(f"Supervisor correctly routed to {expected_route}")

    # Verify only the expected agent ran (not both)
    if expected_route not in node_outputs:
        fail(f"Expected agent node '{expected_route}' has no output. Got: {list(node_outputs.keys())}")

    agent_output = str(node_outputs.get(expected_route, ""))
    if expected_marker not in agent_output:
        fail(f"Expected marker '{expected_marker}' not in output: {agent_output[:200]}")

    if not_expected_marker in agent_output:
        fail(f"Wrong agent responded — found '{not_expected_marker}' in output")

    # The other agent should NOT have run
    other_node = "writer_node" if expected_route == "researcher_node" else "researcher_node"
    if other_node in node_outputs and node_outputs[other_node]:
        fail(f"Wrong agent '{other_node}' also ran — supervisor should route to only one")

    ok(f"Agent output correct: {agent_output[:100]}...")
    print(f"Final message: {run['output'].get('message', '')[:150]}...")


async def main() -> None:
    if not OLLAMA_KEY or OLLAMA_KEY == "ollama":
        fail("Set OLLAMA_API_KEY environment variable")

    async with httpx.AsyncClient(timeout=120) as client:
        health = await client.get(f"{API}/health")
        if health.status_code != 200:
            fail("API not healthy")
        ok("API health")

        headers = await setup_org(client)
        wf_id, _, _ = await create_supervisor_workflow(client, headers)

        # Test 1: Research question → should route to researcher_node
        await invoke_and_verify(
            client,
            headers,
            wf_id,
            test_input="Research and list the main scientific facts about quantum computing",
            expected_route="researcher_node",
            expected_marker="[RESEARCH_AGENT]",
            not_expected_marker="[WRITER_AGENT]",
        )

        # Test 2: Writing request → should route to writer_node
        await invoke_and_verify(
            client,
            headers,
            wf_id,
            test_input="Write a polished paragraph explaining why reading books is beneficial",
            expected_route="writer_node",
            expected_marker="[WRITER_AGENT]",
            not_expected_marker="[RESEARCH_AGENT]",
        )

        print("\n=== SUPERVISOR ROUTING TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
