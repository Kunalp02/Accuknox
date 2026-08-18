import uuid
from datetime import datetime, timezone

import httpx

from orchestrator_core.config import settings
from orchestrator_core.database import async_session_factory
from orchestrator_core.models import Agent, Document, KnowledgeBase, Run
from orchestrator_events.publisher import EventPublisher
from orchestrator_llm.client import embed_texts, platform_gateway_config, create_openai_client
from orchestrator_rag.chunking import chunk_text
from orchestrator_rag.qdrant import QdrantStore
from orchestrator_runtime.agent import AgentConfig, execute_agent


async def _send_webhook(run: Run, event: str, payload: dict) -> None:
    if not run.webhook_url:
        return
    body = {"event": event, "run_id": str(run.id), **payload}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(run.webhook_url, json=body)
    except Exception:
        pass  # webhook failures should not fail the run


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
        kb_ids = [
            uuid.UUID(k) for k in agent.config.get("knowledge_base_ids", [])
        ]
        agent_cfg = AgentConfig(
            system_prompt=agent.system_prompt,
            model=agent.model,
            temperature=agent.temperature,
            knowledge_base_ids=kb_ids,
        )
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
    functions = [execute_agent_run, index_document]
    redis_settings = __import__("arq.connections").connections.RedisSettings.from_dsn(
        settings.redis_url
    )
