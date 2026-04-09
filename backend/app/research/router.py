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
from app.core.database import get_db
from app.core.security import get_current_user
from app.research.models import ResearchReport
from app.research.schemas import (
    ResearchHistoryItem,
    ResearchResult,
    ResearchStart,
    ResearchStatus,
    SaveResearchRequest,
    ResearchReportSchema,
)
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


@router.post("/save", response_model=ResearchReportSchema)
async def save_research_report(
    req: SaveResearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save or update a research report."""
    notes_json = json.dumps(req.notes)
    queries_json = json.dumps(req.queries)

    if req.id:
        stmt = select(ResearchReport).where(
            ResearchReport.id == req.id,
            ResearchReport.user_id == current_user.id,
        )
        result = await db.execute(stmt)
        report = result.scalars().first()

        if not report:
            raise HTTPException(status_code=404, detail="Research report not found")

        report.query = req.query
        report.research_topic = req.research_topic
        report.report = req.report
        report.notes_json = notes_json
        report.queries_json = queries_json
        report.level = req.level.value
        report.iterations = req.iterations
    else:
        report = ResearchReport(
            user_id=current_user.id,
            query=req.query,
            research_topic=req.research_topic,
            report=req.report,
            notes_json=notes_json,
            queries_json=queries_json,
            level=req.level.value,
            iterations=req.iterations,
        )
        db.add(report)

    await db.commit()
    await db.refresh(report)

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
    )


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
