"""Build API-as-a-product integration guides for published agents and workflows."""

from pydantic import BaseModel


class EndpointGuide(BaseModel):
    method: str
    path: str
    description: str


class IntegrationGuideResponse(BaseModel):
    resource_type: str
    resource_id: str
    name: str
    version: int
    is_published: bool
    base_url: str
    invoke: EndpointGuide
    poll_run: EndpointGuide
    stream_events: EndpointGuide
    resume: EndpointGuide | None = None
    required_scopes: list[str]
    auth_headers: list[str]
    request_body: dict
    webhook_events: list[str]
    examples: dict[str, str]


def _agent_scopes() -> list[str]:
    return ["agent:invoke", "run:read"]


def _workflow_scopes() -> list[str]:
    return ["workflow:invoke", "run:read"]


def build_agent_integration(base_url: str, agent_id: str, name: str, version: int, is_published: bool) -> IntegrationGuideResponse:
    invoke_path = f"/v1/agents/{agent_id}/invoke"
    return IntegrationGuideResponse(
        resource_type="agent",
        resource_id=agent_id,
        name=name,
        version=version,
        is_published=is_published,
        base_url=base_url,
        invoke=EndpointGuide(
            method="POST",
            path=invoke_path,
            description="Start an async agent run. Returns 202 with run_id.",
        ),
        poll_run=EndpointGuide(
            method="GET",
            path="/v1/runs/{run_id}",
            description="Poll run status until completed, failed, or awaiting_input.",
        ),
        stream_events=EndpointGuide(
            method="GET",
            path="/v1/runs/{run_id}/events",
            description="Server-Sent Events stream for live run progress.",
        ),
        required_scopes=_agent_scopes(),
        auth_headers=["X-API-Key: oak_...", "Authorization: Bearer oak_..."],
        request_body={
            "input": "string (required)",
            "context": "object (optional)",
            "webhook_url": "string URL (optional)",
            "webhook_secret": "string (optional, HMAC signing)",
        },
        webhook_events=["run.completed", "run.failed"],
        examples={
            "invoke": f"""curl -X POST {base_url}{invoke_path} \\
  -H "X-API-Key: oak_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{"input": "Hello, what can you do?"}}'""",
            "poll": f"""curl {base_url}/v1/runs/RUN_ID \\
  -H "X-API-Key: oak_YOUR_KEY" """,
            "stream": f"""curl -N {base_url}/v1/runs/RUN_ID/events \\
  -H "X-API-Key: oak_YOUR_KEY" """,
            "webhook_invoke": f"""curl -X POST {base_url}{invoke_path} \\
  -H "X-API-Key: oak_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "input": "Summarize our Q3 metrics",
    "webhook_url": "https://hooks.example.com/orchestrator",
    "webhook_secret": "whsec_your_secret"
  }}'""",
        },
    )


def build_workflow_integration(
    base_url: str, workflow_id: str, name: str, version: int, is_published: bool
) -> IntegrationGuideResponse:
    invoke_path = f"/v1/workflows/{workflow_id}/invoke"
    guide = build_agent_integration(base_url, workflow_id, name, version, is_published)
    return guide.model_copy(
        update={
            "resource_type": "workflow",
            "resource_id": workflow_id,
            "invoke": EndpointGuide(
                method="POST",
                path=invoke_path,
                description="Start an async workflow run. Returns 202 with run_id.",
            ),
            "resume": EndpointGuide(
                method="POST",
                path="/v1/runs/{run_id}/resume",
                description="Resume a workflow paused at a human-in-the-loop node.",
            ),
            "required_scopes": _workflow_scopes(),
            "webhook_events": ["run.completed", "run.failed", "run.awaiting_input"],
            "examples": {
                **guide.examples,
                "invoke": f"""curl -X POST {base_url}{invoke_path} \\
  -H "X-API-Key: oak_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{"input": "Research solar energy benefits"}}'""",
                "resume": f"""curl -X POST {base_url}/v1/runs/RUN_ID/resume \\
  -H "X-API-Key: oak_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{"input": "Approved — proceed"}}'""",
            },
        }
    )
