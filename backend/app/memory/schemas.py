"""
Pydantic schemas for the memory API.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    """Schema for creating a memory."""
    content: str = Field(..., description="Memory content text")
    memory_type: str = Field(default="fact", description="Type: fact, preference, conclusion, context")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class MemoryRecallResult(BaseModel):
    """Schema for a recalled memory result."""
    id: str
    content: str
    memory_type: str
    similarity: float
    metadata: dict = Field(default_factory=dict)


class EntityInfo(BaseModel):
    """Schema for entity information."""
    id: str
    name: str
    entity_type: Optional[str] = None
    mention_count: int


class BankConfig(BaseModel):
    """Schema for memory bank configuration."""
    retain_mission: Optional[str] = None
    reflect_mission: Optional[str] = None
    disposition_skepticism: int = 3
    disposition_literalism: int = 3
    disposition_empathy: int = 3


class MemoryBankInfo(BaseModel):
    """Schema for memory bank information."""
    id: str
    workspace_id: int
    name: str
    config: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecallResponse(BaseModel):
    """Schema for recall response."""
    results: list[MemoryRecallResult]
    total: int
    query: str


class RetainResponse(BaseModel):
    """Schema for retain response."""
    memory_id: str
    workspace_id: int
    memory_type: str
    created_at: datetime


class MemoryRecentItem(BaseModel):
    """Schema for a recent memory item."""
    id: str
    content: str
    memory_type: str
    created_at: datetime
    mentioned_at: Optional[datetime] = None


class RecentMemoriesResponse(BaseModel):
    """Schema for recent memories response."""
    memories: list[MemoryRecentItem]
    total: int
