"""
Entity resolution using pg_trgm similarity.
"""
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Similarity threshold (0-1)
SIMILARITY_THRESHOLD = 0.6


class EntityResolver:
    """Resolves entity names to canonical forms using pg_trgm similarity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_similar(
        self,
        bank_id: UUID,
        entity_name: str,
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> Optional[dict]:
        """
        Find a similar existing entity using trigram similarity.

        Args:
            bank_id: The memory bank ID
            entity_name: The entity name to match
            threshold: Minimum similarity score (0-1)

        Returns:
            Dict with entity data if match found, None otherwise
        """
        # Use pg_trgm similarity function
        query = text("""
            SELECT id, name, entity_type, mention_count,
                   similarity(:name, name) as sim_score
            FROM entities
            WHERE bank_id = :bank_id
              AND similarity(:name, name) >= :threshold
            ORDER BY sim_score DESC
            LIMIT 1
        """)

        result = await self.db.execute(
            query,
            {
                "name": entity_name,
                "bank_id": str(bank_id),
                "threshold": threshold,
            }
        )
        row = result.fetchone()

        if row:
            return {
                "id": row.id,
                "name": row.name,
                "entity_type": row.entity_type,
                "mention_count": row.mention_count,
                "similarity": row.sim_score,
            }
        return None

    async def resolve(
        self,
        bank_id: UUID,
        entity_name: str,
        entity_type: str = None,
    ) -> tuple[UUID, bool]:
        """
        Resolve an entity name to canonical form.

        Args:
            bank_id: The memory bank ID
            entity_name: The entity name
            entity_type: Optional entity type hint

        Returns:
            Tuple of (entity_id, was_created) - new entity created or existing matched
        """
        # First try exact match (case insensitive)
        exact_match = await self._find_exact(bank_id, entity_name)
        if exact_match:
            return exact_match, False

        # Try similarity match
        similar = await self.find_similar(bank_id, entity_name)
        if similar:
            # Update mention count (flush to persist in same transaction)
            await self.db.execute(
                text("""
                    UPDATE entities
                    SET mention_count = mention_count + 1,
                        last_seen = NOW()
                    WHERE id = :id
                """),
                {"id": str(similar["id"])}
            )
            await self.db.flush()
            return similar["id"], False

        # No match - create new entity
        new_id = await self._create_entity(bank_id, entity_name, entity_type)
        return new_id, True

    async def _find_exact(self, bank_id: UUID, name: str) -> Optional[UUID]:
        """Find entity by exact name (case insensitive)."""
        from app.memory.models import Entity
        result = await self.db.execute(
            select(Entity).where(
                Entity.bank_id == bank_id,
                func.lower(Entity.name) == name.lower(),
            )
        )
        entity = result.scalar_one_or_none()
        return entity.id if entity else None

    async def _create_entity(
        self,
        bank_id: UUID,
        name: str,
        entity_type: str = None,
    ) -> UUID:
        """Create a new entity."""
        from app.memory.models import Entity
        entity = Entity(
            bank_id=bank_id,
            name=name,
            entity_type=entity_type,
        )
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity.id