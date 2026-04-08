from pydantic import BaseModel
from typing import Optional

class BlackboardCreate(BaseModel):
    topic: str
    workspace_id: Optional[int] = None

class BlackboardResponse(BaseModel):
    id: int
    topic: str
    status: str
    content_json: str
    created_at: str
