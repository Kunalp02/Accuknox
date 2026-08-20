#!/usr/bin/env python3
"""
Full end-to-end test against a live Ollama Cloud gateway and multi-agent workflow.

Usage:
  export OLLAMA_API_KEY="your-key-here"
  export LLM_GATEWAY_URL="https://ollama.com/v1"
  export LLM_DEFAULT_MODEL="gpt-oss:120b"
  python3 scripts/e2e_ollama_workflow.py

Requires: API running on localhost:8000, Postgres on :5432, SYNC_WORKER=true
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
CHAT_MODEL = os.environ.get("LLM_DEFAULT_MODEL", "gpt-oss:120b")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK: {msg}")


async def wait_run(client: httpx.AsyncClient, headers: dict, run_id: str, timeout: float = 120) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = await client.get(f"{API}/v1/runs/{run_id}", headers=headers)
        res.raise_for_status()
        body = res.json()
        if body["status"] in ("completed", "failed", "awaiting_input"):
            return body
        await asyncio.sleep(1)
    fail(f"Run {run_id} timed out after {timeout}s")


async def main() -> None:
    if not OLLAMA_KEY or OLLAMA_KEY == "ollama":
        fail("Set OLLAMA_API_KEY to your real Ollama Cloud API key")

    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Health
        health = await client.get(f"{API}/health")
        if health.status_code != 200:
            fail(f"Health check: {health.status_code}")
        ok("API health")

        # 2. Signup
        email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
        signup = await client.post(
            f"{API}/v1/auth/signup",
            json={"email": email, "password": "password123", "org_name": "E2E Org"},
        )
        if signup.status_code != 200:
            fail(f"Signup: {signup.status_code} {signup.text}")
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        ok(f"Signup ({email})")

        # 3. Configure gateway
        gw = await client.put(
            f"{API}/v1/settings/llm-gateway",
            headers=headers,
            json={
                "base_url": GATEWAY_URL,
                "default_model": CHAT_MODEL,
                "embed_model": EMBED_MODEL,
                "api_key": OLLAMA_KEY,
            },
        )
        if gw.status_code != 200:
            fail(f"Gateway config: {gw.status_code} {gw.text}")
        ok(f"Gateway configured ({GATEWAY_URL})")

        # 4. Test gateway
        test = await client.post(f"{API}/v1/settings/llm-gateway/test", headers=headers)
        if test.status_code != 200:
            fail(f"Gateway test HTTP: {test.status_code}")
        test_body = test.json()
        if not test_body.get("ok"):
            fail(f"Gateway test failed: {test_body}")
        ok(f"Gateway test: {test_body.get('response_preview', '')[:80]}")

        # 5. Create agents
        researcher = await client.post(
            f"{API}/v1/agents",
            headers=headers,
            json={
                "name": "E2E Researcher",
                "system_prompt": "You research topics in 2-3 bullet points. Be concise.",
                "model": CHAT_MODEL,
            },
        )
        writer = await client.post(
            f"{API}/v1/agents",
            headers=headers,
            json={
                "name": "E2E Writer",
                "system_prompt": "You write a one-paragraph summary based on the research provided.",
                "model": CHAT_MODEL,
            },
        )
        if researcher.status_code != 201 or writer.status_code != 201:
            fail(f"Agent create: {researcher.text} / {writer.text}")
        r_id = researcher.json()["id"]
        w_id = writer.json()["id"]
        ok("Created Researcher + Writer agents")

        # 6. Create multi-agent workflow
        wf = await client.post(
            f"{API}/v1/workflows",
            headers=headers,
            json={
                "name": "E2E Multi-agent",
                "graph": {
                    "entry": "researcher",
                    "nodes": [
                        {"id": "researcher", "type": "agent", "agent_id": r_id},
                        {"id": "writer", "type": "agent", "agent_id": w_id},
                    ],
                    "edges": [{"from": "researcher", "to": "writer"}],
                },
            },
        )
        if wf.status_code != 201:
            fail(f"Workflow create: {wf.status_code} {wf.text}")
        wf_id = wf.json()["id"]
        ok("Created workflow")

        # 7. Validate + publish
        val = await client.post(f"{API}/v1/workflows/{wf_id}/validate", headers=headers)
        if not val.json().get("valid"):
            fail(f"Validation: {val.json()}")
        ok("Workflow validated")

        pub = await client.post(f"{API}/v1/workflows/{wf_id}/publish", headers=headers)
        if pub.status_code != 200:
            fail(f"Publish: {pub.status_code} {pub.text}")
        ok("Workflow published")

        # 8. Invoke workflow
        invoke = await client.post(
            f"{API}/v1/workflows/{wf_id}/invoke",
            headers=headers,
            json={"input": "What are the main benefits of solar energy?"},
        )
        if invoke.status_code != 202:
            fail(f"Invoke: {invoke.status_code} {invoke.text}")
        run_id = invoke.json()["run_id"]
        ok(f"Workflow invoked (run {run_id})")

        # 9. Wait for completion
        run = await wait_run(client, headers, run_id, timeout=180)
        if run["status"] != "completed":
            fail(f"Run status={run['status']} error={run.get('error')}")
        outputs = run.get("output", {}).get("node_outputs", {})
        if "researcher" not in outputs or "writer" not in outputs:
            fail(f"Missing node outputs: {list(outputs.keys())}")
        ok(f"Workflow completed — researcher: {str(outputs['researcher'])[:60]}...")
        ok(f"Workflow completed — writer: {str(outputs['writer'])[:60]}...")

        # 10. Single agent invoke
        await client.post(f"{API}/v1/agents/{r_id}/publish", headers=headers)
        ainvoke = await client.post(
            f"{API}/v1/agents/{r_id}/invoke",
            headers=headers,
            json={"input": "Say hello in one sentence."},
        )
        if ainvoke.status_code != 202:
            fail(f"Agent invoke: {ainvoke.status_code}")
        arun = await wait_run(client, headers, ainvoke.json()["run_id"], timeout=120)
        if arun["status"] != "completed":
            fail(f"Agent run failed: {arun.get('error')}")
        ok(f"Agent invoke: {arun['output']['message'][:80]}")

        print("\n=== ALL E2E TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
