from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None

class WorkspaceCreate(BaseModel):
    name: str

class WorkspaceOut(BaseModel):
    id: int
    name: str
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

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
