"""
Redis SSE streaming helpers for Morphological Analysis.
"""

import asyncio
import json
import weakref
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

# Per-event-loop redis client cache
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


async def publish_event(analysis_id: int, event: dict):
    """Publish a JSON event to the matrix stream channel."""
    client = await get_redis()
    channel = f"matrix_stream_{analysis_id}"
    await client.publish(channel, json.dumps(event))


async def subscribe_stream(analysis_id: int):
    """Subscribe to the matrix stream channel."""
    client = await get_redis()
    pubsub = client.pubsub()
    channel = f"matrix_stream_{analysis_id}"
    await pubsub.subscribe(channel)
    return pubsub


async def set_processing_flag(analysis_id: int):
    """Mark a morphological analysis as currently processing."""
    client = await get_redis()
    await client.setex(f"matrix_processing_{analysis_id}", 3600, "1")


async def clear_processing_flag(analysis_id: int):
    """Clear the processing flag."""
    client = await get_redis()
    await client.delete(f"matrix_processing_{analysis_id}")


async def get_processing_status(analysis_id: int) -> bool:
    """Check if a morphological analysis is currently processing."""
    client = await get_redis()
    val = await client.get(f"matrix_processing_{analysis_id}")
    return val is not None


async def save_matrix_state(analysis_id: int, state: dict, ttl: int = 86400):
    """Persist full matrix state to Redis as JSON (24h TTL)."""
    client = await get_redis()
    key = f"matrix_state_{analysis_id}"
    await client.setex(key, ttl, json.dumps(state))


async def get_matrix_state(analysis_id: int) -> Optional[dict]:
    """Retrieve persisted matrix state from Redis."""
    client = await get_redis()
    key = f"matrix_state_{analysis_id}"
    val = await client.get(key)
    return json.loads(val) if val else None
