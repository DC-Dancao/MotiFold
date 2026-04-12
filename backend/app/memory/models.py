"""
SQLAlchemy models for the memory system.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all memory models."""
    pass


class MemoryBank(Base):
    """
    Memory Bank - one per workspace.

    Each workspace has its own isolated memory bank, providing natural data isolation.
    """
    __tablename__ = "memory_banks"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    workspace_id = Column(Integer, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    config = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    memory_units = relationship(
        "MemoryUnit",
        back_populates="bank",
        cascade="all, delete-orphan",
    )
    entities = relationship(
        "Entity",
        back_populates="bank",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_memory_banks_workspace_id", "workspace_id"),
    )


class MemoryUnit(Base):
    """
    Memory Unit - individual memory entries.

    Stores a single piece of memory with its embedding vector for semantic search.
    """
    __tablename__ = "memory_units"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    bank_id = Column(PGUUID(as_uuid=True), ForeignKey("memory_banks.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(ARRAY(Float), nullable=True)  # standard SQLAlchemy array
    memory_type = Column(String(50), default="fact")  # fact, preference, conclusion, context
    extra_data = Column(JSONB, default={})
    entity_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=[])
    created_at = Column(DateTime, default=datetime.utcnow)
    mentioned_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    bank = relationship("MemoryBank", back_populates="memory_units")

    __table_args__ = (
        Index("idx_memory_units_bank_id", "bank_id"),
        Index("idx_memory_units_created_at", "bank_id", "created_at"),
        Index("idx_memory_units_memory_type", "bank_id", "memory_type"),
    )


# Type alias for pgvector ARRAY column
ARRAY_FLOAT = None  # Will be set after dialect registration


def _init_vector_column():
    """Initialize vector column type after pgvector is loaded."""
    global ARRAY_FLOAT
    try:
        from pgvector.sqlalchemy import Vector
        ARRAY_FLOAT = Vector(1024)  # BGE-M3 dimension
    except ImportError:
        # Fallback to ARRAY(Float) if pgvector not available
        ARRAY_FLOAT = ARRAY


class Entity(Base):
    """
    Entity - extracted entities from memories.

    Stores entities (people, topics, preferences, etc.) extracted from memory content.
    """
    __tablename__ = "entities"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    bank_id = Column(PGUUID(as_uuid=True), ForeignKey("memory_banks.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    entity_type = Column(String(50))  # person, topic, preference, conclusion
    canonical_name = Column(Text)
    extra_data = Column(JSONB, default={})
    mention_count = Column(Integer, default=1)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    # Relationships
    bank = relationship("MemoryBank", back_populates="entities")

    __table_args__ = (
        Index("idx_entities_bank_id", "bank_id"),
        Index("idx_entities_bank_name", "bank_id", "name"),
    )


class EntityMemory(Base):
    """
    Entity-Memory association table.

    Links entities to the memory units they appear in.
    """
    __tablename__ = "entity_memories"

    entity_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    memory_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("memory_units.id", ondelete="CASCADE"),
        primary_key=True,
    )
