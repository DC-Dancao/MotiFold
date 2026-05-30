import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis

from app.core.config import settings
from app.auth.models import User
from app.core.security import get_current_user

router = APIRouter(tags=["notifications"])

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

@router.get("/stream")
async def stream_notifications(current_user: User = Depends(get_current_user)):
    """SSE stream of notifications for the authenticated user.

    Channel topology is **user-scoped**, not org-scoped: a single user
    that belongs to multiple orgs subscribes to one channel
    (``user_notifications_{user.id}``) and receives notifications from
    every org they are a member of. This is intentional — the recipient
    is the authoritative subject — but means consumers should include
    enough context in the payload (e.g. ``link`` to the relevant
    resource) to disambiguate when the same user has more than one
    active workspace. Current publishers (research, matrix, blackboard
    workers) emit ``type``/``resource_id``/``link``-style envelopes;
    new publishers should follow the same shape.

    Because the stream is user-scoped, the endpoint sits in
    ``_TENANT_FREE_SEGMENT_PREFIXES`` in ``app.tenant.middleware``: no
    ``X-Org-ID`` is needed and ``request.state.org_schema`` is None.
    """
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
