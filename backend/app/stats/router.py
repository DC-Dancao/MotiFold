"""
Stats API routes for dashboard/overview.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc

from app.core.database import get_db_with_schema
from app.auth.models import User
from app.chat.models import Chat
from app.matrix.models import MorphologicalAnalysis
from app.blackboard.models import BlackboardData
from app.research.models import ResearchReport
from app.memory.service import MemoryService
from app.core.security import get_current_user
from app.org.dependencies import get_current_org_membership

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def get_overview_stats(
    request: Request,
    workspace_id: int | None = None,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
    membership = Depends(get_current_org_membership),
):
    """
    Get overview statistics for the current user's workspace.

    Returns counts and recent items across all features:
    - chats, morphological analyses, blackboards, research reports, memories
    """
    # Build base filters
    user_filter = Chat.user_id == current_user.id
    workspace_filter = None
    if workspace_id is not None:
        workspace_filter = Chat.workspace_id == workspace_id

    # Chat stats
    chat_query = select(func.count(Chat.id)).where(user_filter)
    if workspace_filter:
        chat_query = chat_query.where(workspace_filter)
    chat_count_result = await db.execute(chat_query)
    chat_count = chat_count_result.scalar() or 0

    # Recent chats
    recent_chats_query = (
        select(Chat)
        .where(user_filter)
        .order_by(desc(Chat.created_at))
        .limit(5)
    )
    if workspace_filter:
        recent_chats_query = recent_chats_query.where(workspace_filter)
    recent_chats_result = await db.execute(recent_chats_query)
    recent_chats = [
        {"id": c.id, "title": c.title, "model": c.model, "created_at": c.created_at.isoformat()}
        for c in recent_chats_result.scalars().all()
    ]

    # Morphological analysis stats
    ma_query = select(func.count(MorphologicalAnalysis.id)).where(
        MorphologicalAnalysis.user_id == current_user.id
    )
    if workspace_id is not None:
        ma_query = ma_query.where(MorphologicalAnalysis.workspace_id == workspace_id)
    ma_count_result = await db.execute(ma_query)
    ma_count = ma_count_result.scalar() or 0

    # Recent morphological analyses
    recent_ma_query = (
        select(MorphologicalAnalysis)
        .where(MorphologicalAnalysis.user_id == current_user.id)
        .order_by(desc(MorphologicalAnalysis.created_at))
        .limit(5)
    )
    if workspace_id is not None:
        recent_ma_query = recent_ma_query.where(MorphologicalAnalysis.workspace_id == workspace_id)
    recent_ma_result = await db.execute(recent_ma_query)
    recent_ma = [
        {
            "id": m.id,
            "focus_question": m.focus_question,
            "status": m.status,
            "created_at": m.created_at.isoformat()
        }
        for m in recent_ma_result.scalars().all()
    ]

    # Blackboard stats
    bb_query = select(func.count(BlackboardData.id)).where(
        BlackboardData.user_id == current_user.id
    )
    if workspace_id is not None:
        bb_query = bb_query.where(BlackboardData.workspace_id == workspace_id)
    bb_count_result = await db.execute(bb_query)
    bb_count = bb_count_result.scalar() or 0

    # Status breakdown for blackboards
    bb_status_query = (
        select(BlackboardData.status, func.count(BlackboardData.id))
        .where(BlackboardData.user_id == current_user.id)
        .group_by(BlackboardData.status)
    )
    if workspace_id is not None:
        bb_status_query = bb_status_query.where(BlackboardData.workspace_id == workspace_id)
    bb_status_result = await db.execute(bb_status_query)
    bb_status_breakdown = {row[0]: row[1] for row in bb_status_result.all()}

    # Recent blackboards
    recent_bb_query = (
        select(BlackboardData)
        .where(BlackboardData.user_id == current_user.id)
        .order_by(desc(BlackboardData.created_at))
        .limit(5)
    )
    if workspace_id is not None:
        recent_bb_query = recent_bb_query.where(BlackboardData.workspace_id == workspace_id)
    recent_bb_result = await db.execute(recent_bb_query)
    recent_bb = [
        {
            "id": b.id,
            "topic": b.topic,
            "status": b.status,
            "created_at": b.created_at.isoformat()
        }
        for b in recent_bb_result.scalars().all()
    ]

    # Research stats
    research_query = select(func.count(ResearchReport.id)).where(
        ResearchReport.user_id == current_user.id
    )
    research_count_result = await db.execute(research_query)
    research_count = research_count_result.scalar() or 0

    # Status breakdown for research
    research_status_query = (
        select(ResearchReport.status, func.count(ResearchReport.id))
        .where(ResearchReport.user_id == current_user.id)
        .group_by(ResearchReport.status)
    )
    research_status_result = await db.execute(research_status_query)
    research_status_breakdown = {row[0]: row[1] for row in research_status_result.all()}

    # Recent research reports
    recent_research_query = (
        select(ResearchReport)
        .where(ResearchReport.user_id == current_user.id)
        .order_by(desc(ResearchReport.created_at))
        .limit(5)
    )
    recent_research_result = await db.execute(recent_research_query)
    recent_research = [
        {
            "id": r.id,
            "query": r.query,
            "research_topic": r.research_topic or "",
            "status": r.status,
            "level": r.level,
            "created_at": r.created_at.isoformat()
        }
        for r in recent_research_result.scalars().all()
    ]

    # Memory stats (if workspace_id provided)
    memory_stats = None
    if workspace_id is not None:
        try:
            memory_service = MemoryService(db)
            memory_stats = await memory_service.get_memory_stats(workspace_id)
        except Exception:
            memory_stats = {"total": 0, "by_type": {}}

    return {
        "chats": {
            "total": chat_count,
            "recent": recent_chats,
        },
        "morphological_analyses": {
            "total": ma_count,
            "recent": recent_ma,
        },
        "blackboards": {
            "total": bb_count,
            "status_breakdown": bb_status_breakdown,
            "recent": recent_bb,
        },
        "research_reports": {
            "total": research_count,
            "status_breakdown": research_status_breakdown,
            "recent": recent_research,
        },
        "memory": memory_stats,
    }
