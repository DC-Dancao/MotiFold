"""
Text Memory Service for MotiFold.

Provides simple text-based memory storage per workspace without any processing.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.text_memory.models import TextMemory

logger = logging.getLogger(__name__)


class TextMemoryService:
    """
    Simple text memory service for workspace-level storage.

    Stores raw text content without embeddings, entities, or any processing.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize TextMemoryService.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    async def create(
        self,
        workspace_id: int,
        content: str,
    ) -> TextMemory:
        """
        Create a new text memory.

        Args:
            workspace_id: The workspace ID
            content: The plain text content

        Returns:
            The created TextMemory instance
        """
        memory = TextMemory(
            workspace_id=workspace_id,
            content=content,
        )
        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)
        logger.debug(f"Created text memory {memory.id} for workspace {workspace_id}")
        return memory

    async def get(
        self,
        workspace_id: int,
        memory_id: UUID,
    ) -> Optional[TextMemory]:
        """
        Get a text memory by ID.

        Args:
            workspace_id: The workspace ID
            memory_id: The memory UUID

        Returns:
            The TextMemory if found, None otherwise
        """
        result = await self.db.execute(
            select(TextMemory).where(
                TextMemory.id == memory_id,
                TextMemory.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        workspace_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TextMemory]:
        """
        Get all text memories for a workspace.

        Args:
            workspace_id: The workspace ID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of TextMemory instances
        """
        result = await self.db.execute(
            select(TextMemory)
            .where(TextMemory.workspace_id == workspace_id)
            .order_by(TextMemory.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update(
        self,
        workspace_id: int,
        memory_id: UUID,
        content: str,
    ) -> Optional[TextMemory]:
        """
        Update a text memory's content.

        Args:
            workspace_id: The workspace ID
            memory_id: The memory UUID
            content: The new plain text content

        Returns:
            The updated TextMemory if found, None otherwise
        """
        memory = await self.get(workspace_id, memory_id)
        if not memory:
            return None

        memory.content = content
        await self.db.commit()
        await self.db.refresh(memory)
        logger.debug(f"Updated text memory {memory_id}")
        return memory

    async def delete(
        self,
        workspace_id: int,
        memory_id: UUID,
    ) -> bool:
        """
        Delete a text memory.

        Args:
            workspace_id: The workspace ID
            memory_id: The memory UUID

        Returns:
            True if deleted, False if not found
        """
        memory = await self.get(workspace_id, memory_id)
        if not memory:
            return False

        await self.db.delete(memory)
        await self.db.commit()
        logger.debug(f"Deleted text memory {memory_id}")
        return True

    async def count(self, workspace_id: int) -> int:
        """
        Count text memories for a workspace.

        Args:
            workspace_id: The workspace ID

        Returns:
            Number of text memories
        """
        result = await self.db.execute(
            select(func.count(TextMemory.id)).where(TextMemory.workspace_id == workspace_id)
        )
        return result.scalar() or 0
