"""
Pydantic schemas for the Deep Research API.
"""

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

from app.research.state import ResearchLevel


class ResearchStart(BaseModel):
    query: str
    level: ResearchLevel = ResearchLevel.STANDARD
    max_iterations: Optional[int] = Field(default=None, ge=1, le=100)
    max_results: Optional[int] = Field(default=None, ge=1, le=1000)


class ResearchStartLoop(BaseModel):
    """Request schema for POST /api/research/start (confirmation loop)"""
    topic: str
    level: ResearchLevel = ResearchLevel.STANDARD
    max_iterations: Optional[int] = Field(default=None, ge=1, le=100)
    max_results: Optional[int] = Field(default=None, ge=1, le=1000)


class ResearchStatus(BaseModel):
    status: Literal[
        "clarifying", "planning", "searching", "synthesizing", "reporting", "done", "error"
    ]
    message: str
    progress: float
    iteration: Optional[int] = None
    level: ResearchLevel
    task_id: str


class ResearchResult(BaseModel):
    report: str
    iterations: int
    level: ResearchLevel


class ResearchReportSchema(BaseModel):
    id: int
    query: str
    research_topic: str
    report: str
    notes: list[str]
    queries: list[str]
    level: ResearchLevel
    iterations: int
    created_at: str
    updated_at: str
    status: str = "running"           # NEW
    task_id: Optional[str] = None     # NEW


class ResearchHistoryItem(BaseModel):
    id: int
    query: str
    research_topic: str
    level: ResearchLevel
    iterations: int
    created_at: str
    updated_at: str
    status: str = "running"           # NEW: "running" | "done" | "error"
    task_id: Optional[str] = None     # NEW: Celery task UUID


class ResearchRunningState(BaseModel):
    """Full state returned for rejoin — persisted in Redis during run."""
    status: str
    message: str
    progress: float
    iteration: Optional[int] = None
    level: ResearchLevel
    task_id: str
    research_topic: str
    notes: list[str] = []
    queries: list[str] = []


class ResearchStartResponse(BaseModel):
    """Response from POST /api/research/start"""
    thread_id: str


class ResumeRequest(BaseModel):
    """Request for POST /api/research/resume/{thread_id}"""
    action: Union[str, dict]  # "option_1", "option_2", "option_3", "skip", "confirm_done", or {"type": "manual", "text": "..."}


class ResumeResponse(BaseModel):
    """Response from POST /api/research/resume/{thread_id}"""
    status: Literal["resumed", "error"]
    message: Optional[str] = None
