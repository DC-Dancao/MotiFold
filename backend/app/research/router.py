"""
FastAPI router for Deep Research endpoints.
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth.models import User
from app.core.security import get_current_user
from app.research.schemas import ResearchResult, ResearchStart, ResearchStatus
from app.research.state import LEVEL_DEFAULTS, ResearchLevel
from app.research.stream import (
    get_processing_status,
    get_redis,
    publish_event,
    subscribe_stream,
)

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/", response_model=ResearchStatus)
async def start_research(
    data: ResearchStart,
    current_user: User = Depends(get_current_user),
):
    """
    Start a new deep research task.
    Returns immediately with task_id; results streamed via SSE.
    """
    task_id = str(uuid.uuid4())

    level = data.level or ResearchLevel.STANDARD
    default_iters, default_results = LEVEL_DEFAULTS.get(level, (3, 10))
    max_iters = data.max_iterations if data.max_iterations is not None else default_iters
    max_res = data.max_results if data.max_results is not None else default_results

    # Enqueue Celery task
    from app.research.tasks import process_research
    process_research.delay(
        task_id=task_id,
        query=data.query,
        level=level.value,
        max_iterations=max_iters,
        max_results=max_res,
    )

    return ResearchStatus(
        status="searching",
        message=f"Research started (level={level.value}, max_iter={max_iters})",
        progress=0.0,
        iteration=None,
        level=level,
        task_id=task_id,
    )


@router.get("/{task_id}/stream")
async def stream_research(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    SSE stream of research progress events.
    """
    async def event_generator():
        redis = await get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"research_stream_{task_id}")

        is_processing = await get_processing_status(task_id)

        if not is_processing:
            # Check if already done (maybe Redis flag expired)
            yield f"data: {json.dumps({'type': 'status', 'event': 'not_found', 'message': 'Task not found or already complete'})}\n\n"
            yield "data: [DONE]\n\n"
            await pubsub.unsubscribe(f"research_stream_{task_id}")
            await pubsub.close()
            return

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if data == "[DONE]":
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        break
                    yield f"data: {data}\n\n"
        finally:
            await pubsub.unsubscribe(f"research_stream_{task_id}")
            await pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{task_id}/result", response_model=ResearchResult)
async def get_result(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get the final research result (after completion).
    """
    redis = await get_redis()
    key = f"research_result_{task_id}"
    result_json = await redis.get(key)

    if result_json:
        data = json.loads(result_json)
        return ResearchResult(**data)

    raise HTTPException(status_code=404, detail="Research result not found or still in progress")
