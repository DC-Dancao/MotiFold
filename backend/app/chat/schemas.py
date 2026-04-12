from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

ModelLiteral = Literal["auto", "mini", "pro", "max"]

class ChatCreate(BaseModel):
    workspace_id: Optional[int] = None
    model: Optional[ModelLiteral] = "pro"

class ChatOut(BaseModel):
    id: int
    user_id: int
    workspace_id: Optional[int] = None
    title: str
    model: ModelLiteral = "pro"
    created_at: datetime

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    content: str
    idempotency_key: Optional[str] = None
    model: Optional[ModelLiteral] = None  # overrides chat model if provided

class MessageOut(BaseModel):
    id: str | int
    chat_id: int
    role: str
    content: str
    created_at: datetime
    idempotency_key: Optional[str] = None

    class Config:
        from_attributes = True
