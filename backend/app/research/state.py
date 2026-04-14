"""
State definitions and Pydantic models for the Deep Research agent.
"""

from enum import Enum
from typing import Annotated, Optional

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class ResearchLevel(str, Enum):
    STANDARD = "standard"
    EXTENDED = "extended"
    MANUAL = "manual"


LEVEL_DEFAULTS: dict[ResearchLevel, tuple[int, int]] = {
    # (max_iterations, max_results_per_query)
    ResearchLevel.STANDARD: (3, 10),
    ResearchLevel.EXTENDED: (6, 20),
    ResearchLevel.MANUAL: (5, 10),
}


# =============================================================================
# Structured Output Models
# =============================================================================

class NeedsClarification(BaseModel):
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope.",
    )
    verification: str = Field(
        description="Verification message shown after user provides clarification.",
    )


class ResearchTopic(BaseModel):
    topic: str = Field(
        description="A refined, detailed research question or topic derived from the user's input.",
    )


class SearchPlan(BaseModel):
    queries: list[str] = Field(
        description="A list of search queries to execute. Each query should be self-contained and focused.",
    )


class Summary(BaseModel):
    summary: str = Field(description="A concise summary of the content.")
    key_excerpts: str = Field(
        description="Key excerpts or facts extracted from the content.",
    )


class FinalReport(BaseModel):
    report: str = Field(description="The final markdown research report.")


# =============================================================================
# Graph State
# =============================================================================

class ResearchState(MessagesState):
    research_topic: str
    search_queries: list[str]
    search_results: list[dict]
    notes: list[str]
    final_report: str
    iterations: int
    max_iterations: int
    max_results: int
    research_level: ResearchLevel
