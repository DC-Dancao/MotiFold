"""
Multi-strategy retrieval for memory search using PostgreSQL full-text search (BM25-like).
"""
import re
import logging
from typing import List, Optional
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.models import MemoryUnit, MemoryBank

logger = logging.getLogger(__name__)


class MemorySearch:
    """Multi-strategy memory search with BM25 full-text search."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _tokenize_query(self, query: str) -> str:
        """
        Normalize query text for PostgreSQL full-text search.

        Converts query to a format suitable for tsquery.
        """
        # Lowercase and remove special characters, split into tokens
        tokens = re.sub(r"[^\w\s]", " ", query.lower()).split()
        # Join tokens with | for OR behavior (BM25-like)
        if not tokens:
            return ""
        return " | ".join(tokens)

    async def keyword_search(
        self,
        workspace_id: int,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """
        Search memories using PostgreSQL full-text search (ts_rank).

        This provides BM25-like ranking based on term frequency and document length.

        Args:
            workspace_id: The workspace ID
            query: Search query
            memory_type: Optional filter by memory type
            limit: Maximum results

        Returns:
            List of memory dicts with id, content, score (BM25-like rank)
        """
        bank_result = await self.db.execute(
            select(MemoryBank).where(MemoryBank.workspace_id == workspace_id)
        )
        bank = bank_result.scalar_one_or_none()
        if not bank:
            return []

        # Tokenize query for tsquery
        tsquery_tokens = self._tokenize_query(query)
        if not tsquery_tokens:
            return []

        # Use PostgreSQL's ts_rank_cd for BM25-like ranking
        # ts_rank_cd uses coverage density ranking (similar to BM25)
        tsquery_expr = func.to_tsquery('english', tsquery_tokens)
        rank_expr = func.ts_rank_cd(
            func.to_tsvector('english', MemoryUnit.content),
            tsquery_expr
        )

        stmt = (
            select(
                MemoryUnit,
                rank_expr.label('rank')
            )
            .where(MemoryUnit.bank_id == bank.id)
            .where(
                func.to_tsvector('english', MemoryUnit.content).op('@@')(tsquery_expr)
            )
            .order_by(rank_expr.desc())
            .limit(limit)
        )

        if memory_type:
            stmt = stmt.where(MemoryUnit.memory_type == memory_type)

        result = await self.db.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        # Normalize scores to 0-1 range
        max_rank = max(rank for _, rank in rows) if rows else 1.0
        if max_rank == 0:
            max_rank = 1.0

        return [
            {
                "id": str(m.id),
                "content": m.content,
                "memory_type": m.memory_type,
                "similarity": float(rank) / float(max_rank) if max_rank > 0 else 0.0,
                "metadata": m.extra_data or {},
            }
            for m, rank in rows
        ]