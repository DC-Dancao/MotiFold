from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChatCreate(BaseModel):
    workspace_id: Optional[int] = None

class ChatOut(BaseModel):
    id: int
    user_id: int
    workspace_id: Optional[int] = None
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    content: str
    idempotency_key: Optional[str] = None

class MessageOut(BaseModel):
    id: str | int
    chat_id: int
    role: str
    content: str
    created_at: datetime
    idempotency_key: Optional[str] = None

    class Config:
        from_attributes = True
