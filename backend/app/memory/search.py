"""
Multi-strategy retrieval for memory search.
"""
import logging
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.models import MemoryUnit, MemoryBank

logger = logging.getLogger(__name__)


class MemorySearch:
    """Multi-strategy memory search."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def keyword_search(
        self,
        workspace_id: int,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """
        Search memories using PostgreSQL full-text search.

        Args:
            workspace_id: The workspace ID
            query: Search query
            memory_type: Optional filter by memory type
            limit: Maximum results

        Returns:
            List of memory dicts with id, content, score
        """
        bank_result = await self.db.execute(
            select(MemoryBank).where(MemoryBank.workspace_id == workspace_id)
        )
        bank = bank_result.scalar_one_or_none()
        if not bank:
            return []

        # Use ILIKE for simple keyword matching
        # For production, could use PostgreSQL tsvector/tsquery
        search_pattern = f"%{query}%"

        # Compute relevance as: shorter content with matches = more relevant
        # We use the difference as a proxy - smaller difference = shorter content after removing query = more relevant
        relevance_expr = func.length(MemoryUnit.content) - func.length(
            func.replace(func.lower(MemoryUnit.content), func.lower(query), '')
        )

        stmt = (
            select(
                MemoryUnit,
                relevance_expr.label('relevance')
            )
            .where(MemoryUnit.bank_id == bank.id)
            .where(MemoryUnit.content.ilike(search_pattern))
            .order_by(relevance_expr)
            .limit(limit)
        )

        if memory_type:
            stmt = stmt.where(MemoryUnit.memory_type == memory_type)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(m.id),
                "content": m.content,
                "memory_type": m.memory_type,
                "similarity": 1.0,  # Keyword matches are binary here
                "metadata": m.extra_data or {},
            }
            for m, _ in rows
        ]