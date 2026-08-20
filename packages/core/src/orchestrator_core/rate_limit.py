"""Redis-backed rate limiting."""

import logging
import time

import redis.asyncio as redis

from orchestrator_core.config import settings

logger = logging.getLogger(__name__)


async def check_rate_limit(
    key_prefix: str,
    limit_per_minute: int,
    redis_url: str | None = None,
) -> None:
    """Raise ValueError with message if limit exceeded (caller maps to 429)."""
    if limit_per_minute <= 0:
        return
    bucket = int(time.time() // 60)
    key = f"rate:{key_prefix}:{bucket}"
    client = redis.from_url(redis_url or settings.redis_url, decode_responses=True)
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, 120)
        if count > limit_per_minute:
            raise ValueError("Rate limit exceeded")
    except (redis.ConnectionError, OSError) as exc:
        logger.warning("Rate limit skipped (Redis unavailable): %s", exc)
    finally:
        await client.aclose()
