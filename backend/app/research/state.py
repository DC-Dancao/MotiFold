"""
State definitions and Pydantic models for the Deep Research agent.
"""

from enum import Enum
from typing import Annotated, Optional, Union

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class ResearchLevel(str, Enum):
    STANDARD = "standard"
    EXTENDED = "extended"
    MANUAL = "manual"
    MATRIX = "matrix"  # New level that explores solutions via morphological analysis


LEVEL_DEFAULTS: dict[ResearchLevel, tuple[int, int]] = {
    # (max_iterations, max_results_per_query)
    ResearchLevel.STANDARD: (3, 10),
    ResearchLevel.EXTENDED: (6, 20),
    ResearchLevel.MANUAL: (5, 10),
    ResearchLevel.MATRIX: (3, 10),  # Uses morphological analysis for solution exploration
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

class FollowupDecision(BaseModel):
    needs_followup: bool = Field(
        description="Whether the AI wants to explore more on the topic.",
    )
    question: str = Field(
        description="A question presented to the user about what to explore next.",
    )
    option_1: str = Field(
        description="First follow-up exploration option.",
    )
    option_2: str = Field(
        description="Second follow-up exploration option.",
    )
    option_3: str = Field(
        description="Third follow-up exploration option.",
    )


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
    # Confirmation loop fields
    research_history: list[str]
    user_inputs: list[Union[str, dict]]
    needs_followup: bool
    followup_options: list[str]
    is_complete: bool
