"""Pydantic schemas for Organization API."""
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
import re

SLUG_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]*$')

class OrganizationCreate(BaseModel):
    name: str
    slug: str

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v) or len(v) > 50:
            raise ValueError("Invalid slug format. Use lowercase letters, numbers, underscores, and hyphens.")
        return v

class OrganizationOut(BaseModel):
    id: str  # slug
    name: str
    slug: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class OrganizationMemberCreate(BaseModel):
    user_id: str
    role: str = "member"

class OrganizationMemberOut(BaseModel):
    id: str
    organization_id: str
    user_id: str
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True

class OrgMemberWithUser(OrganizationMemberOut):
    username: str
    email: Optional[str] = None
