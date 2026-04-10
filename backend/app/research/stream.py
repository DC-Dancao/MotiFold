"""
Redis SSE streaming helpers for Deep Research.
"""

import asyncio
import json
import weakref
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

# Per-event-loop redis client cache — WeakKeyDictionary auto-removes entries
# when the loop is garbage-collected, avoiding connection leaks.
_redis_per_loop: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, aioredis.Redis] = (
    weakref.WeakKeyDictionary()
)


async def get_redis() -> aioredis.Redis:
    """Return a redis client for the current event loop, creating one if needed."""
    loop = asyncio.get_running_loop()
    client = _redis_per_loop.get(loop)
    if client is None:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        _redis_per_loop[loop] = client
    return client


async def close_redis_clients() -> None:
    """Close all cached redis clients. Call on application shutdown."""
    for client in list(_redis_per_loop.values()):
        await client.aclose()
    _redis_per_loop.clear()


async def publish_event(task_id: str, event: dict):
    """Publish a JSON event to the research stream channel."""
    client = await get_redis()
    channel = f"research_stream_{task_id}"
    await client.publish(channel, json.dumps(event))


async def subscribe_stream(task_id: str):
    """Subscribe to the research stream channel."""
    client = await get_redis()
    pubsub = client.pubsub()
    channel = f"research_stream_{task_id}"
    await pubsub.subscribe(channel)
    return pubsub


async def set_processing_flag(task_id: str):
    """Mark a research task as currently processing."""
    client = await get_redis()
    await client.setex(f"research_processing_{task_id}", 3600, "1")


async def clear_processing_flag(task_id: str):
    """Clear the processing flag and publish DONE."""
    client = await get_redis()
    await client.delete(f"research_processing_{task_id}")


async def get_processing_status(task_id: str) -> bool:
    """Check if a research task is currently processing."""
    client = await get_redis()
    val = await client.get(f"research_processing_{task_id}")
    return val is not None


async def save_research_state(task_id: str, state: dict, ttl: int = 86400):
    """Persist full research state to Redis as JSON (24h TTL)."""
    client = await get_redis()
    key = f"research_state_{task_id}"
    await client.setex(key, ttl, json.dumps(state))


async def get_research_state(task_id: str) -> Optional[dict]:
    """Retrieve persisted research state from Redis."""
    client = await get_redis()
    key = f"research_state_{task_id}"
    val = await client.get(key)
    return json.loads(val) if val else None
