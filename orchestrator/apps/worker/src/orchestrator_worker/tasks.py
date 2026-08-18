import uuid
from datetime import datetime, timezone

import httpx

from orchestrator_core.config import settings
from orchestrator_core.database import async_session_factory
from orchestrator_core.models import Agent, Document, Run, Workflow
from orchestrator_events.publisher import EventPublisher
from orchestrator_llm.client import embed_texts, platform_gateway_config, create_openai_client
from orchestrator_rag.chunking import chunk_text
from orchestrator_rag.qdrant import QdrantStore
from orchestrator_runtime.agent import execute_agent
from orchestrator_runtime.loader import build_agent_config, build_workflow_agent_map, load_mcp_clients
from orchestrator_runtime.workflow import (
    execute_workflow,
    next_node_after,
    state_from_dict,
    state_to_dict,
)


async def _send_webhook(run: Run, event: str, payload: dict) -> None:
    if not run.webhook_url:
        return
    body = {"event": event, "run_id": str(run.id), **payload}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(run.webhook_url, json=body)
    except Exception:
        pass


async def execute_agent_run(ctx: dict, run_id: str) -> None:
    run_uuid = uuid.UUID(run_id)
    publisher = EventPublisher()
    await publisher.connect()

    async with async_session_factory() as session:
        run = await session.get(Run, run_uuid)
        if not run:
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await session.commit()
        await publisher.publish(run_uuid, "run.status", {"status": "running"})

        agent = await session.get(Agent, run.agent_id)
        if not agent:
            run.status = "failed"
            run.error = "Agent not found"
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await publisher.publish(run_uuid, "run.failed", {"error": run.error})
            return

        gateway = platform_gateway_config()
        agent_cfg = await build_agent_config(session, agent)
        mcp_clients = await load_mcp_clients(session, run.organization_id)
        user_input = run.input.get("message", "")

        async def on_event(event_type: str, data: dict) -> None:
            await publisher.publish(run_uuid, event_type, data)

        try:
            result = await execute_agent(
                gateway,
                agent_cfg,
                user_input,
                run.organization_id,
                on_token=on_event,
                mcp_clients=mcp_clients,
            )
            run.status = "completed"
            run.output = {"message": result.output}
            run.metrics = result.metrics
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await publisher.publish(run_uuid, "run.completed", run.output)
            await _send_webhook(
                run,
                "run.completed",
                {"status": "completed", "output": run.output, "metrics": run.metrics},
            )
        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await publisher.publish(run_uuid, "run.failed", {"error": str(e)})
            await _send_webhook(run, "run.failed", {"status": "failed", "error": str(e)})

    await publisher.close()


async def execute_workflow_run(ctx: dict, run_id: str) -> None:
    run_uuid = uuid.UUID(run_id)
    publisher = EventPublisher()
    await publisher.connect()

    async with async_session_factory() as session:
        run = await session.get(Run, run_uuid)
        if not run:
            return

        workflow = await session.get(Workflow, run.workflow_id)
        if not workflow:
            run.status = "failed"
            run.error = "Workflow not found"
            await session.commit()
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        await session.commit()
        await publisher.publish(run_uuid, "run.status", {"status": "running"})

        gateway = platform_gateway_config()
        graph = workflow.graph or {}
        agents = await build_workflow_agent_map(session, run.organization_id, graph)
        mcp_clients = await load_mcp_clients(session, run.organization_id)
        user_input = run.input.get("message", "")
        context = run.input.get("context", {})

        async def on_event(event_type: str, data: dict) -> None:
            await publisher.publish(run_uuid, event_type, data)

        try:
            state, metrics = await execute_workflow(
                graph,
                gateway,
                run.organization_id,
                user_input,
                context,
                agents,
                mcp_clients,
                on_event=on_event,
            )
            if state.pending_human_node:
                run.status = "awaiting_input"
                run.checkpoint_data = state_to_dict(state)
                run.metrics = metrics
                await session.commit()
                await publisher.publish(run_uuid, "run.awaiting_input", {
                    "node_id": state.pending_human_node,
                })
                await _send_webhook(run, "run.awaiting_input", {"status": "awaiting_input"})
            else:
                run.status = "completed"
                run.output = {"message": state.last_output, "node_outputs": state.node_outputs}
                run.metrics = metrics
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
                await publisher.publish(run_uuid, "run.completed", run.output)
                await _send_webhook(run, "run.completed", {"status": "completed", "output": run.output})
        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await publisher.publish(run_uuid, "run.failed", {"error": str(e)})

    await publisher.close()


async def resume_workflow_run(ctx: dict, run_id: str) -> None:
    run_uuid = uuid.UUID(run_id)
    publisher = EventPublisher()
    await publisher.connect()

    async with async_session_factory() as session:
        run = await session.get(Run, run_uuid)
        if not run or not run.checkpoint_data:
            return

        workflow = await session.get(Workflow, run.workflow_id)
        if not workflow:
            return

        run.status = "running"
        await session.commit()
        await publisher.publish(run_uuid, "run.status", {"status": "running"})

        state = state_from_dict(run.checkpoint_data)
        human_node = state.pending_human_node
        human_response = run.input.get("human_response", "")
        if human_node:
            state.messages.append({"role": "user", "content": human_response})
            state.variables["human_response"] = human_response
            state.pending_human_node = None
            next_id = next_node_after(workflow.graph, human_node, state)
        else:
            next_id = None

        gateway = platform_gateway_config()
        graph = workflow.graph or {}
        agents = await build_workflow_agent_map(session, run.organization_id, graph)
        mcp_clients = await load_mcp_clients(session, run.organization_id)
        context = run.input.get("context", {})

        async def on_event(event_type: str, data: dict) -> None:
            await publisher.publish(run_uuid, event_type, data)

        try:
            state, metrics = await execute_workflow(
                graph,
                gateway,
                run.organization_id,
                run.input.get("message", ""),
                context,
                agents,
                mcp_clients,
                on_event=on_event,
                initial_state=state,
                start_node_id=next_id,
            )
            if state.pending_human_node:
                run.status = "awaiting_input"
                run.checkpoint_data = state_to_dict(state)
                run.metrics = {**run.metrics, **metrics}
                await session.commit()
                await publisher.publish(run_uuid, "run.awaiting_input", {"node_id": state.pending_human_node})
            else:
                run.status = "completed"
                run.output = {"message": state.last_output, "node_outputs": state.node_outputs}
                run.metrics = {**run.metrics, **metrics}
                run.completed_at = datetime.now(timezone.utc)
                run.checkpoint_data = None
                await session.commit()
                await publisher.publish(run_uuid, "run.completed", run.output)
        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await publisher.publish(run_uuid, "run.failed", {"error": str(e)})

    await publisher.close()


async def index_document(ctx: dict, document_id: str) -> None:
    doc_uuid = uuid.UUID(document_id)
    gateway = platform_gateway_config()
    client = create_openai_client(gateway)

    async with async_session_factory() as session:
        doc = await session.get(Document, doc_uuid)
        if not doc:
            return

        doc.status = "indexing"
        await session.commit()

        try:
            with open(doc.storage_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            chunks = chunk_text(text)
            if not chunks:
                doc.status = "indexed"
                doc.chunk_count = 0
                await session.commit()
                return

            vectors = await embed_texts(client, gateway.embed_model, chunks)
            store = QdrantStore()
            chunk_tuples = [(i, c, v) for i, (c, v) in enumerate(zip(chunks, vectors))]
            await store.upsert_chunks(
                doc.organization_id,
                doc.knowledge_base_id,
                doc.id,
                chunk_tuples,
            )
            doc.status = "indexed"
            doc.chunk_count = len(chunks)
            await session.commit()
        except Exception:
            doc.status = "failed"
            await session.commit()


class WorkerSettings:
    functions = [execute_agent_run, execute_workflow_run, resume_workflow_run, index_document]
    redis_settings = __import__("arq.connections").connections.RedisSettings.from_dsn(
        settings.redis_url
    )
