"""
Memory API routes.

Provides REST endpoints for memory operations.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.auth.models import User
from app.core.security import get_current_user
from app.memory.service import MemoryService, MemoryLimitExceededError
from app.memory.schemas import (
    MemoryCreate,
    MemoryRecallResult,
    RecallResponse,
    RetainResponse,
)

router = APIRouter(prefix="/memory", tags=["memory"])


async def _verify_workspace_access(
    workspace_id: int,
    db: AsyncSession,
    current_user: User,
) -> None:
    """Verify user has access to the workspace."""
    from app.workspace.models import Workspace
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == current_user.id,
        )
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.post("/{workspace_id}/retain", response_model=RetainResponse)
async def retain_memory(
    workspace_id: int,
    memory: MemoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Store a memory for a workspace.

    Args:
        workspace_id: The workspace ID
        memory: Memory content and type

    Returns:
        The created memory info
    """
    service = MemoryService(db)
    try:
        result = await service.retain(
            workspace_id=workspace_id,
            content=memory.content,
            memory_type=memory.memory_type,
            metadata=memory.extra_data,
        )
        return result
    except MemoryLimitExceededError as e:
        raise HTTPException(status_code=507, detail=str(e))


@router.post("/{workspace_id}/recall", response_model=RecallResponse)
async def recall_memories(
    workspace_id: int,
    query: str = Query(..., description="Search query"),
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    limit: int = Query(5, ge=1, le=20, description="Max results"),
    max_tokens: int = Query(4000, ge=100, le=10000, description="Max token budget"),
    use_multi_strategy: bool = Query(False, description="Use multi-strategy retrieval (semantic + keyword)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Recall relevant memories for a workspace.

    Uses vector similarity search to find memories related to the query.

    Args:
        workspace_id: The workspace ID
        query: Search query
        memory_type: Optional filter by memory type
        limit: Maximum number of results
        max_tokens: Maximum token budget for results
        use_multi_strategy: If True, combines semantic + keyword search with RRF fusion

    Returns:
        List of relevant memories
    """
    service = MemoryService(db)
    results = await service.recall(
        workspace_id=workspace_id,
        query=query,
        memory_type=memory_type,
        limit=limit,
        max_tokens=max_tokens,
        use_multi_strategy=use_multi_strategy,
    )
    return RecallResponse(
        results=results,
        total=len(results),
        query=query,
    )


@router.get("/{workspace_id}/entities/{entity_name}")
async def get_entity_memories(
    workspace_id: int,
    entity_name: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Get all memories containing a specific entity.

    Args:
        workspace_id: The workspace ID
        entity_name: The entity name to search for
        limit: Maximum number of results

    Returns:
        List of memories containing the entity
    """
    service = MemoryService(db)
    results = await service.get_entity_memories(
        workspace_id=workspace_id,
        entity_name=entity_name,
        limit=limit,
    )
    return {"entity": entity_name, "memories": results}


@router.get("/{workspace_id}/stats")
async def get_memory_stats(
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Get memory statistics for a workspace.

    Args:
        workspace_id: The workspace ID

    Returns:
        Memory counts by type
    """
    service = MemoryService(db)
    stats = await service.get_memory_stats(workspace_id)
    return stats


@router.post("/{workspace_id}/preference")
async def update_preference(
    workspace_id: int,
    preference_key: str = Query(..., description="Preference name"),
    preference_value: str = Query(..., description="Preference value"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace_access(workspace_id, db, current_user)
    """
    Update a user preference.

    Preference memories are stored with type='preference' and overwrite
    previous values with the same key.

    Args:
        workspace_id: The workspace ID
        preference_key: The preference name
        preference_value: The preference value

    Returns:
        The created memory info
    """
    service = MemoryService(db)
    result = await service.update_preference(
        workspace_id=workspace_id,
        preference_key=preference_key,
        preference_value=preference_value,
    )
    return result
