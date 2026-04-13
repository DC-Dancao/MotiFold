"""
Pydantic schemas for the text memory API.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TextMemoryCreate(BaseModel):
    """Schema for creating a text memory."""
    content: str = Field(..., description="Memory content text")


class TextMemoryUpdate(BaseModel):
    """Schema for updating a text memory."""
    content: str = Field(..., description="Updated memory content text")


class TextMemoryResponse(BaseModel):
    """Schema for a text memory response."""
    id: UUID
    workspace_id: int
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TextMemoryListResponse(BaseModel):
    """Schema for listing text memories."""
    memories: list[TextMemoryResponse]
    total: int
