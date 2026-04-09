"""
Redis SSE streaming helpers for Deep Research.
"""

import json

import redis.asyncio as aioredis

from app.core.config import settings

redis_client: aioredis.Redis = None


async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return redis_client


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
