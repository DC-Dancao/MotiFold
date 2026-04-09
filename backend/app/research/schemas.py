"""
Pydantic schemas for the Deep Research API.
"""

from typing import Literal, Optional

from pydantic import BaseModel

from app.research.state import ResearchLevel


class ResearchStart(BaseModel):
    query: str
    level: ResearchLevel = ResearchLevel.STANDARD
    max_iterations: Optional[int] = None
    max_results: Optional[int] = None


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
