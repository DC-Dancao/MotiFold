"""
FastAPI router for Deep Research endpoints.
"""

import json
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.models import User
from app.core.database import get_db, AsyncSessionLocal
from app.core.security import get_current_user
from app.research.models import ResearchReport
from app.research.schemas import (
    ResearchHistoryItem,
    ResearchResult,
    ResearchStart,
    ResearchRunningState,
    ResearchStatus,
    ResearchReportSchema,
)
from app.research.state import LEVEL_DEFAULTS, ResearchLevel
from app.research.stream import (
    get_processing_status,
    get_redis,
    get_research_state,
    publish_event,
    set_processing_flag,
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

    # Set processing flag BEFORE enqueueing to avoid race condition with SSE stream
    await set_processing_flag(task_id)

    # Immediately create a DB record so task appears in history
    try:
        async with AsyncSessionLocal() as db:
            report = ResearchReport(
                user_id=current_user.id,
                query=data.query,
                level=level.value,
                status="running",
                task_id=task_id,
                notes_json="[]",
                queries_json="[]",
                iterations=max_iters,
            )
            db.add(report)
            await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to create initial research record: {e}")

    # Enqueue Celery task with user_id for proper save
    from app.research.tasks import process_research
    process_research.delay(
        task_id=task_id,
        query=data.query,
        level=level.value,
        max_iterations=max_iters,
        max_results=max_res,
        user_id=current_user.id,
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

        # Emit persisted state first so reconnected clients see full progress
        if is_processing:
            redis_state = await get_research_state(task_id)
            if redis_state:
                yield f"data: {json.dumps({'type': 'rejoin', **redis_state})}\n\n"

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
                    # Check for [DONE] (published as {"type": "[DONE]", "report_id": ..., "report": ...} from tasks)
                    try:
                        parsed = json.loads(data)
                        if parsed.get("type") == "[DONE]":
                            # Include report_id and report in the done event
                            done_event = {"type": "done"}
                            if parsed.get("report_id"):
                                done_event["report_id"] = parsed["report_id"]
                            if parsed.get("report"):
                                done_event["report"] = parsed["report"]
                            yield f"data: {json.dumps(done_event)}\n\n"
                            break
                        # Emit original data for other events
                        yield f"data: {data}\n\n"
                    except json.JSONDecodeError:
                        # Plain string "[DONE]" fallback
                        if data == "[DONE]":
                            yield f"data: {json.dumps({'type': 'done'})}\n\n"
                            break
                        yield f"data: {data}\n\n"
        finally:
            await pubsub.unsubscribe(f"research_stream_{task_id}")
            await pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{task_id}/state", response_model=ResearchRunningState)
async def get_research_state_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get persisted state for a running research task (for rejoin).
    Returns full progress: notes, queries, topic, status, iteration.
    """
    # Try Redis first (running task)
    redis_state = await get_research_state(task_id)
    if redis_state:
        return ResearchRunningState(**redis_state)

    # Fall back to DB record
    stmt = select(ResearchReport).where(
        ResearchReport.task_id == task_id,
        ResearchReport.user_id == current_user.id,
    )
    async with AsyncSessionLocal() as db:
        result = await db.execute(stmt)
        report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Research not found")

    return ResearchRunningState(
        status=report.status,
        message="Research complete" if report.status == "done" else "Research failed",
        progress=1.0,
        iteration=report.iterations,
        level=ResearchLevel(report.level),
        task_id=task_id,
        research_topic=report.research_topic or "",
        notes=json.loads(report.notes_json),
        queries=json.loads(report.queries_json),
    )


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


@router.get("/history", response_model=List[ResearchHistoryItem])
async def get_research_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all saved research reports for the current user."""
    stmt = select(ResearchReport).where(
        ResearchReport.user_id == current_user.id
    ).order_by(ResearchReport.updated_at.desc())

    result = await db.execute(stmt)
    reports = result.scalars().all()

    return [
        ResearchHistoryItem(
            id=r.id,
            query=r.query,
            research_topic=r.research_topic or "",
            level=ResearchLevel(r.level),
            iterations=r.iterations,
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else "",
            status=r.status,
            task_id=r.task_id,
        )
        for r in reports
    ]


@router.get("/{report_id}", response_model=ResearchReportSchema)
async def get_research_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific research report."""
    stmt = select(ResearchReport).where(
        ResearchReport.id == report_id,
        ResearchReport.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Research report not found")

    return ResearchReportSchema(
        id=report.id,
        query=report.query,
        research_topic=report.research_topic or "",
        report=report.report or "",
        notes=json.loads(report.notes_json),
        queries=json.loads(report.queries_json),
        level=ResearchLevel(report.level),
        iterations=report.iterations,
        created_at=report.created_at.isoformat() if report.created_at else "",
        updated_at=report.updated_at.isoformat() if report.updated_at else "",
        status=report.status,
        task_id=report.task_id,
    )


@router.delete("/{report_id}")
async def delete_research_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a research report."""
    stmt = select(ResearchReport).where(
        ResearchReport.id == report_id,
        ResearchReport.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Research report not found")

    await db.delete(report)
    await db.commit()
    return {"status": "success"}
