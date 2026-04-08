from pydantic import BaseModel
from datetime import datetime

class WorkspaceCreate(BaseModel):
    name: str

class WorkspaceOut(BaseModel):
    id: int
    name: str
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True
