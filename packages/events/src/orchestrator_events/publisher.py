import json
import uuid
from typing import Any

import redis.asyncio as redis
from orchestrator_core.config import settings


def run_channel(run_id: uuid.UUID) -> str:
    return f"run:{run_id}:events"


class EventPublisher:
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._client: redis.Redis | None = None
        self._disabled = False

    async def connect(self) -> None:
        if self._disabled:
            return
        try:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
            await self._client.ping()
        except Exception:
            self._disabled = True
            self._client = None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def publish(self, run_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> None:
        if self._disabled:
            return
        if not self._client:
            await self.connect()
        if self._disabled or not self._client:
            return
        try:
            payload = json.dumps({"type": event_type, "data": data})
            await self._client.publish(run_channel(run_id), payload)
        except Exception:
            self._disabled = True

    async def subscribe(self, run_id: uuid.UUID):
        client = redis.from_url(self._redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(run_channel(run_id))
        return pubsub, client

