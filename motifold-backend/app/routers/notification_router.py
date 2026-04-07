import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis

from app.config import settings
from app.models import User
from app.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

@router.get("/stream")
async def stream_notifications(current_user: User = Depends(get_current_user)):
    async def event_generator():
        pubsub = redis_client.pubsub()
        channel = f"user_notifications_{current_user.id}"
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
