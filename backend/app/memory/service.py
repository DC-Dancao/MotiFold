"""
Memory Service for MotiFold.

Provides workspace-level memory storage and retrieval with:
- Vector-based semantic search (pgvector)
- Entity extraction and tracking
- Memory type classification (fact, preference, conclusion)
"""

import logging
from typing import Optional
from uuid import UUID
import asyncio
import numpy as np

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.memory.models import MemoryBank, MemoryUnit, Entity
from app.memory.schemas import (
    MemoryCreate,
    MemoryRecallResult,
    RetainResponse,
    MemoryRecentItem,
)

logger = logging.getLogger(__name__)

# Memory limit per workspace
WORKSPACE_MEMORY_LIMIT = 1000

# Similarity threshold for recall
DEFAULT_SIMILARITY_THRESHOLD = 0.5
# Default number of memories to retrieve
DEFAULT_RECALL_LIMIT = 5


class MemoryLimitExceededError(Exception):
    """Raised when workspace memory limit is exceeded."""
    pass


class MemoryService:
    """
    Memory service for workspace-level memory management.

    Each workspace has its own isolated memory bank. Memories are stored with
    vector embeddings for semantic search.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize MemoryService.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db
        self.embedding = None

    async def ensure_bank(self, workspace_id: int) -> MemoryBank:
        """
        Ensure a memory bank exists for the workspace.

        Creates one if it doesn't exist.

        Args:
            workspace_id: The workspace ID

        Returns:
            The MemoryBank instance
        """
        result = await self.db.execute(
            select(MemoryBank).where(MemoryBank.workspace_id == workspace_id)
        )
        bank = result.scalar_one_or_none()

        if not bank:
            bank = MemoryBank(
                workspace_id=workspace_id,
                name=f"workspace-{workspace_id}-memory",
                config={},
            )
            self.db.add(bank)
            await self.db.commit()
            await self.db.refresh(bank)
            logger.info(f"Created memory bank for workspace {workspace_id}")

        return bank

    async def retain(
        self,
        workspace_id: int,
        content: str,
        memory_type: str = "fact",
        metadata: Optional[dict] = None,
    ) -> RetainResponse:
        """
        Store a memory for the workspace.

        Args:
            workspace_id: The workspace ID
            content: The memory content text
            memory_type: Type of memory (fact, preference, conclusion, context)
            metadata: Additional metadata

        Returns:
            RetainResponse with the created memory ID
        """
        bank = await self.ensure_bank(workspace_id)

        # Check memory count limit before storing
        count_result = await self.db.execute(
            select(func.count(MemoryUnit.id)).where(MemoryUnit.bank_id == bank.id)
        )
        current_count = count_result.scalar() or 0

        if current_count >= WORKSPACE_MEMORY_LIMIT:
            raise MemoryLimitExceededError(
                f"Workspace {workspace_id} has reached memory limit of {WORKSPACE_MEMORY_LIMIT}"
            )

        # Generate embedding
        try:
            if self.embedding is None:
                from app.memory.embedding import get_embedding_service
                self.embedding = get_embedding_service()
            embedding = self.embedding.encode([content])[0]
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            embedding = None

        # Extract and link entities
        entity_ids = []
        if content and len(content) > 10:
            extracted = await self._extract_entities(content)
            for entity_data in extracted:
                entity = await self._get_or_create_entity(bank.id, entity_data)
                entity_ids.append(entity.id)
                # Update mention count via SQL to ensure it's committed
                await self.db.execute(
                    text("""
                        UPDATE entities
                        SET mention_count = mention_count + 1,
                            last_seen = NOW()
                        WHERE id = :id
                    """),
                    {"id": str(entity.id)}
                )

        # Create memory unit
        memory = MemoryUnit(
            bank_id=bank.id,
            content=content,
            embedding=embedding,
            memory_type=memory_type,
            extra_data=metadata or {},
            entity_ids=entity_ids,
        )
        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)
        # Explicitly set mentioned_at = created_at to ensure they're equal at creation
        # This is needed for accurate hit rate calculation (mentioned_at > created_at means recalled)
        await self.db.execute(
            text("UPDATE memory_units SET mentioned_at = created_at WHERE id = :id"),
            {"id": str(memory.id)}
        )
        await self.db.commit()

        logger.debug(f"Stored memory {memory.id} for workspace {workspace_id}")

        return RetainResponse(
            memory_id=str(memory.id),
            workspace_id=workspace_id,
            memory_type=memory_type,
            created_at=memory.created_at,
        )

    async def recall(
        self,
        workspace_id: int,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        max_tokens: int = 4000,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        use_multi_strategy: bool = False,
        use_reranker: bool = False,
    ) -> list[MemoryRecallResult]:
        """
        Recall relevant memories for a query.

        Uses vector similarity search to find relevant memories.
        When use_multi_strategy=True, combines semantic + BM25 keyword search with RRF fusion.
        When use_reranker=True, applies cross-encoder neural reranking after retrieval.

        Args:
            workspace_id: The workspace ID
            query: The search query
            memory_type: Optional filter by memory type
            limit: Maximum number of results
            max_tokens: Maximum total tokens (approximate)
            similarity_threshold: Minimum similarity score (0-1)
            use_multi_strategy: If True, combines semantic + keyword strategies
            use_reranker: If True, applies cross-encoder reranking (requires multi-strategy)

        Returns:
            List of MemoryRecallResult sorted by similarity
        """
        if use_multi_strategy:
            return await self._recall_multi_strategy(
                workspace_id, query, memory_type, limit, max_tokens, similarity_threshold,
                use_reranker=use_reranker
            )
        return await self._recall_single_strategy(
            workspace_id, query, memory_type, limit, max_tokens, similarity_threshold
        )

    async def _recall_single_strategy(
        self,
        workspace_id: int,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        max_tokens: int = 4000,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> list[MemoryRecallResult]:
        """Single-strategy recall using vector similarity."""
        bank = await self.ensure_bank(workspace_id)

        # Generate query embedding
        try:
            if self.embedding is None:
                from app.memory.embedding import get_embedding_service
                self.embedding = get_embedding_service()
            query_embedding = self.embedding.encode([query])[0]
        except Exception as e:
            logger.warning(f"Failed to generate query embedding: {e}")
            return []

        # Build query for vector search
        # Using pgvector's <=> operator for cosine distance
        # Similarity = 1 - cosine_distance
        stmt = (
            select(
                MemoryUnit,
                (1 - func.cosine_distance(MemoryUnit.embedding, query_embedding)).label("similarity"),
            )
            .where(MemoryUnit.bank_id == bank.id)
            .where(MemoryUnit.embedding.isnot(None))
            .order_by(func.cosine_distance(MemoryUnit.embedding, query_embedding))
            .limit(limit * 2)  # Fetch extra for filtering
        )

        if memory_type:
            stmt = stmt.where(MemoryUnit.memory_type == memory_type)

        result = await self.db.execute(stmt)
        rows = result.all()

        # Filter by similarity and token budget
        results = []
        total_tokens = 0
        returned_memory_ids = []

        for memory, similarity in rows:
            if similarity < similarity_threshold:
                continue

            # Rough token estimate (4 chars per token)
            mem_tokens = len(memory.content) // 4
            if total_tokens + mem_tokens > max_tokens:
                continue

            returned_memory_ids.append(memory.id)
            results.append(MemoryRecallResult(
                id=str(memory.id),
                content=memory.content,
                memory_type=memory.memory_type,
                similarity=float(similarity),
                metadata=memory.extra_data or {},
            ))
            total_tokens += mem_tokens

            if len(results) >= limit:
                break

        # Update mentioned_at for returned memories
        if returned_memory_ids:
            await self.db.execute(
                text("""
                    UPDATE memory_units
                    SET mentioned_at = NOW()
                    WHERE id = ANY(:ids)
                """),
                {"ids": [str(id) for id in returned_memory_ids]}
            )
            await self.db.commit()

        return results

    async def _recall_multi_strategy(
        self,
        workspace_id: int,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        max_tokens: int = 4000,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        use_reranker: bool = False,
    ) -> list[MemoryRecallResult]:
        """Multi-strategy recall combining semantic + BM25 + optional reranking."""
        from app.memory.fusion import rrf_fusion

        # Get results from both strategies in parallel
        semantic_task = self._recall_single_strategy(
            workspace_id, query, memory_type, limit, max_tokens, similarity_threshold
        )
        keyword_task = self.keyword_search(
            workspace_id, query, memory_type, limit
        )

        semantic_results, keyword_results = await asyncio.gather(
            semantic_task, keyword_task
        )

        # Convert to dict format for fusion
        semantic_dicts = [
            {"id": r.id, "content": r.content, "memory_type": r.memory_type,
             "similarity": r.similarity, "metadata": r.metadata}
            for r in semantic_results
        ]
        keyword_dicts = [
            {"id": r.id, "content": r.content, "memory_type": r.memory_type,
             "similarity": r.similarity, "metadata": r.metadata}
            for r in keyword_results
        ]

        # Empty lists return empty fusion
        if not semantic_dicts and not keyword_dicts:
            return []

        # Fuse results
        fused = rrf_fusion([semantic_dicts, keyword_dicts])

        # Apply cross-encoder reranking if enabled
        if use_reranker and fused:
            try:
                from app.memory.reranker import get_reranker
                reranker = get_reranker()
                # Use top_k = limit * 2 to get more candidates for reranking
                reranked = await reranker.rerank(
                    query=query,
                    candidates=fused[:limit * 2],
                    top_k=limit,
                )
                fused = reranked
            except Exception as e:
                logger.warning(f"Reranking failed, using fused results: {e}")

        # Update mentioned_at for returned memories
        fused_ids = [r["id"] for r in fused[:limit]]
        if fused_ids:
            await self.db.execute(
                text("""
                    UPDATE memory_units
                    SET mentioned_at = NOW()
                    WHERE id = ANY(:ids)
                """),
                {"ids": fused_ids}
            )
            await self.db.commit()

        # Convert back to MemoryRecallResult
        return [
            MemoryRecallResult(
                id=r["id"],
                content=r["content"],
                memory_type=r["memory_type"],
                similarity=r.get("similarity", r.get("rrf_score", r.get("combined_score", 1.0))),
                metadata=r.get("metadata", {}),
            )
            for r in fused[:limit]
        ]

    async def get_entity_memories(
        self,
        workspace_id: int,
        entity_name: str,
        limit: int = 10,
    ) -> list[MemoryRecallResult]:
        """
        Get all memories containing a specific entity.

        Args:
            workspace_id: The workspace ID
            entity_name: The entity name to search for
            limit: Maximum number of results

        Returns:
            List of MemoryRecallResult
        """
        bank = await self.ensure_bank(workspace_id)

        # Find the entity
        entity_result = await self.db.execute(
            select(Entity).where(
                Entity.bank_id == bank.id,
                func.lower(Entity.name) == entity_name.lower(),
            )
        )
        entity = entity_result.scalar_one_or_none()

        if not entity:
            return []

        # Use SQL array overlap (&&) for filtering - no Python loop needed
        # This is much more efficient than fetching all and filtering in Python
        stmt = (
            select(MemoryUnit)
            .where(MemoryUnit.bank_id == bank.id)
            .where(MemoryUnit.entity_ids.op('&&')([entity.id]))
            .order_by(MemoryUnit.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        memories = result.scalars().all()

        return [
            MemoryRecallResult(
                id=str(memory.id),
                content=memory.content,
                memory_type=memory.memory_type,
                similarity=1.0,  # Direct entity match
                metadata=memory.extra_data or {},
            )
            for memory in memories
        ]

    async def _extract_entities(self, content: str) -> list[dict]:
        """
        Extract entities from content.

        EXPERIMENTAL: This feature requires MEMORY_ENTITY_EXTRACTION_ENABLED=true.

        When enabled, uses LLM for better extraction (see _extract_entities_llm).
        Otherwise falls back to simple capitalization heuristic.

        Args:
            content: The content to extract entities from

        Returns:
            List of entity dicts with 'name' and 'type' keys
        """
        # Check if feature flag is enabled
        from app.core.config import settings
        if settings.MEMORY_ENTITY_EXTRACTION_ENABLED:
            return await self._extract_entities_llm(content)

        # Fall back to simple heuristic
        return self._extract_entities_simple(content)

    def _extract_entities_simple(self, content: str) -> list[dict]:
        """
        Simple entity extraction using capitalization heuristic.

        This is a fallback until LLM extraction is enabled.
        """
        entities = []
        words = content.split()
        current_phrase = []

        for word in words:
            if word and word[0].isupper() and len(word) > 1:
                current_phrase.append(word)
            else:
                if current_phrase and len(current_phrase) >= 2:
                    name = " ".join(current_phrase)
                    entities.append({"name": name, "type": "entity"})
                current_phrase = []

        if current_phrase and len(current_phrase) >= 2:
            name = " ".join(current_phrase)
            entities.append({"name": name, "type": "entity"})

        return entities

    async def _extract_entities_llm(self, content: str) -> list[dict]:
        """
        Extract entities using LLM.

        Uses OpenAI mini model for fast, low-cost extraction.

        Args:
            content: The content to extract entities from

        Returns:
            List of entity dicts with 'name' and 'type' keys
        """
        from app.llm.factory import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage
        import json
        import re

        prompt = f"""Extract significant entities from: "{content[:500]}"

Return JSON: {{"entities": ["entity1", "entity2", ...]}}
Only include: people names, organizations, places, significant topics.
Keep entities concise (2-4 words max).
Return empty array if no significant entities found."""

        try:
            llm = get_llm(model_name="mini", streaming=False)

            response = await llm.ainvoke([
                SystemMessage(content="You extract entities from text. Return only valid JSON."),
                HumanMessage(content=prompt)
            ])

            # Extract JSON from response
            json_match = re.search(r'\{"entities":\s*\[[^\]]*\]+\}', response.content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                entities = data.get("entities", [])
                return [{"name": e, "type": "entity"} for e in entities if e]

            return []

        except Exception as e:
            logger.warning(f"LLM entity extraction failed: {e}")
            # Fall back to simple extraction
            return self._extract_entities_simple(content)

    async def _get_or_create_entity(
        self,
        bank_id: UUID,
        entity_data: dict,
    ) -> Entity:
        """
        Get or create an entity using pg_trgm similarity resolution.

        Args:
            bank_id: The memory bank ID
            entity_data: Entity data dict with 'name' and 'type'

        Returns:
            The Entity instance
        """
        from app.memory.entity import EntityResolver

        name = entity_data.get("name", "").strip()
        if not name:
            raise ValueError("Entity name is required")

        # Use EntityResolver for similarity-based resolution
        resolver = EntityResolver(self.db)
        entity_id, was_created = await resolver.resolve(
            bank_id=bank_id,
            entity_name=name,
            entity_type=entity_data.get("type"),
        )

        # Fetch the entity to return
        result = await self.db.execute(
            select(Entity).where(Entity.id == entity_id)
        )
        return result.scalar_one()

    async def update_preference(
        self,
        workspace_id: int,
        preference_key: str,
        preference_value: str,
    ) -> RetainResponse:
        """
        Update a user preference (overwrites previous value).

        Preference memories are stored with type='preference' and use
        the preference_key as part of the content for easy retrieval.

        Args:
            workspace_id: The workspace ID
            preference_key: The preference name (e.g., "preferred_language")
            preference_value: The preference value

        Returns:
            RetainResponse with the updated memory ID
        """
        content = f"Preference: {preference_key} = {preference_value}"
        return await self.retain(
            workspace_id=workspace_id,
            content=content,
            memory_type="preference",
            metadata={"preference_key": preference_key},
        )

    async def get_memory_stats(self, workspace_id: int) -> dict:
        """
        Get memory statistics for a workspace.

        Args:
            workspace_id: The workspace ID

        Returns:
            Dict with memory counts by type
        """
        bank = await self.ensure_bank(workspace_id)

        result = await self.db.execute(
            select(
                MemoryUnit.memory_type,
                func.count(MemoryUnit.id).label("count"),
            )
            .where(MemoryUnit.bank_id == bank.id)
            .group_by(MemoryUnit.memory_type)
        )
        rows = result.all()

        stats = {
            "total": 0,
            "by_type": {},
        }
        for memory_type, count in rows:
            stats["by_type"][memory_type] = count
            stats["total"] += count

        return stats

    async def get_recent_memories(
        self,
        workspace_id: int,
        limit: int = 20,
    ) -> list[MemoryRecentItem]:
        """
        Get recent memories for a workspace.

        Args:
            workspace_id: The workspace ID
            limit: Maximum number of results

        Returns:
            List of MemoryRecentItem sorted by created_at
        """
        bank = await self.ensure_bank(workspace_id)

        stmt = (
            select(MemoryUnit)
            .where(MemoryUnit.bank_id == bank.id)
            .order_by(MemoryUnit.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        memories = result.scalars().all()

        return [
            MemoryRecentItem(
                id=str(memory.id),
                content=memory.content,
                memory_type=memory.memory_type,
                created_at=memory.created_at,
                mentioned_at=memory.mentioned_at,
            )
            for memory in memories
        ]

    async def get_hit_rate(self, workspace_id: int) -> float:
        """
        Calculate hit rate for a workspace.

        Hit rate = memories that have been mentioned at least once / total memories

        Args:
            workspace_id: The workspace ID

        Returns:
            Hit rate as a float between 0 and 1
        """
        bank = await self.ensure_bank(workspace_id)

        # Total count
        total_result = await self.db.execute(
            select(func.count(MemoryUnit.id)).where(MemoryUnit.bank_id == bank.id)
        )
        total = total_result.scalar() or 0

        if total == 0:
            return 0.0

        # Count memories that have been mentioned (mentioned_at != created_at means recalled at least once)
        # Actually, mentioned_at starts same as created_at but gets updated on recall
        # So we need memories where mentioned_at > created_at (has been recalled)
        mentioned_result = await self.db.execute(
            select(func.count(MemoryUnit.id)).where(
                MemoryUnit.bank_id == bank.id,
                MemoryUnit.mentioned_at > MemoryUnit.created_at,
            )
        )
        mentioned = mentioned_result.scalar() or 0

        return mentioned / total

    async def keyword_search(
        self,
        workspace_id: int,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryRecallResult]:
        """Keyword-based search for exact phrase matches."""
        from app.memory.search import MemorySearch

        search = MemorySearch(self.db)
        results = await search.keyword_search(
            workspace_id=workspace_id,
            query=query,
            memory_type=memory_type,
            limit=limit,
        )

        return [MemoryRecallResult(**r) for r in results]
