"""
SQLAlchemy models for the text memory system.
"""

from datetime import datetime
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all text memory models."""
    pass


class TextMemory(Base):
    """
    Text Memory - simple plain text memory per workspace.

    Stores raw text content without any processing, embeddings, or analysis.
    """
    __tablename__ = "text_memories"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Integer, nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_text_memories_workspace_id", "workspace_id"),
    )
