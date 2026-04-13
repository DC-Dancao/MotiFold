"""
Text Memory API routes.

Provides REST endpoints for simple text-based memory operations.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_with_schema
from app.auth.models import User
from app.core.security import get_current_user
from app.text_memory.service import TextMemoryService
from app.text_memory.schemas import (
    TextMemoryCreate,
    TextMemoryUpdate,
    TextMemoryResponse,
    TextMemoryListResponse,
)

router = APIRouter(prefix="/text-memory", tags=["text-memory"])


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


@router.post("/{workspace_id}", response_model=TextMemoryResponse)
async def create_text_memory(
    workspace_id: int,
    memory: TextMemoryCreate,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new text memory for a workspace.

    Args:
        workspace_id: The workspace ID
        memory: Memory content

    Returns:
        The created memory
    """
    await _verify_workspace_access(workspace_id, db, current_user)
    service = TextMemoryService(db)
    result = await service.create(workspace_id=workspace_id, content=memory.content)
    return result


@router.get("/{workspace_id}", response_model=TextMemoryListResponse)
async def list_text_memories(
    workspace_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    """
    List all text memories for a workspace.

    Args:
        workspace_id: The workspace ID
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of text memories
    """
    await _verify_workspace_access(workspace_id, db, current_user)
    service = TextMemoryService(db)
    memories = await service.get_all(workspace_id=workspace_id, limit=limit, offset=offset)
    total = await service.count(workspace_id)
    return TextMemoryListResponse(memories=memories, total=total)


@router.get("/{workspace_id}/{memory_id}", response_model=TextMemoryResponse)
async def get_text_memory(
    workspace_id: int,
    memory_id: UUID,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific text memory by ID.

    Args:
        workspace_id: The workspace ID
        memory_id: The memory UUID

    Returns:
        The text memory
    """
    await _verify_workspace_access(workspace_id, db, current_user)
    service = TextMemoryService(db)
    memory = await service.get(workspace_id=workspace_id, memory_id=memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@router.put("/{workspace_id}/{memory_id}", response_model=TextMemoryResponse)
async def update_text_memory(
    workspace_id: int,
    memory_id: UUID,
    memory: TextMemoryUpdate,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    """
    Update a text memory's content.

    Args:
        workspace_id: The workspace ID
        memory_id: The memory UUID
        memory: Updated content

    Returns:
        The updated memory
    """
    await _verify_workspace_access(workspace_id, db, current_user)
    service = TextMemoryService(db)
    result = await service.update(
        workspace_id=workspace_id,
        memory_id=memory_id,
        content=memory.content,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Memory not found")
    return result


@router.delete("/{workspace_id}/{memory_id}")
async def delete_text_memory(
    workspace_id: int,
    memory_id: UUID,
    db: AsyncSession = Depends(get_db_with_schema),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a text memory.

    Args:
        workspace_id: The workspace ID
        memory_id: The memory UUID

    Returns:
        Success message
    """
    await _verify_workspace_access(workspace_id, db, current_user)
    service = TextMemoryService(db)
    deleted = await service.delete(workspace_id=workspace_id, memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"message": "Memory deleted successfully"}
