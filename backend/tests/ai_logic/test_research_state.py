"""
Tests for app.research.state — models, enums, and LEVEL_DEFAULTS.
"""

import pytest
from pydantic import ValidationError

from app.research.state import (
    LEVEL_DEFAULTS,
    FinalReport,
    NeedsClarification,
    ResearchLevel,
    ResearchState,
    ResearchTopic,
    SearchPlan,
    Summary,
)


class TestResearchLevel:
    def test_enum_values(self):
        assert ResearchLevel.STANDARD.value == "standard"
        assert ResearchLevel.EXTENDED.value == "extended"
        assert ResearchLevel.MANUAL.value == "manual"

    def test_level_defaults_standard(self):
        iters, results = LEVEL_DEFAULTS[ResearchLevel.STANDARD]
        assert iters == 3
        assert results == 10

    def test_level_defaults_extended(self):
        iters, results = LEVEL_DEFAULTS[ResearchLevel.EXTENDED]
        assert iters == 6
        assert results == 20

    def test_level_defaults_manual(self):
        iters, results = LEVEL_DEFAULTS[ResearchLevel.MANUAL]
        assert iters == 5
        assert results == 10


class TestNeedsClarification:
    def test_needs_clarification_true(self):
        result = NeedsClarification(
            need_clarification=True,
            question="Which region are you interested in?",
            verification="",
        )
        assert result.need_clarification is True
        assert result.question == "Which region are you interested in?"
        assert result.verification == ""

    def test_needs_clarification_false(self):
        result = NeedsClarification(
            need_clarification=False,
            question="",
            verification="Understood. Starting research now.",
        )
        assert result.need_clarification is False
        assert result.question == ""
        assert result.verification == "Understood. Starting research now."


class TestResearchTopic:
    def test_valid_topic(self):
        result = ResearchTopic(topic="Impact of AI on software development jobs")
        assert result.topic == "Impact of AI on software development jobs"


class TestSearchPlan:
    def test_valid_queries(self):
        result = SearchPlan(queries=["query 1", "query 2", "query 3"])
        assert len(result.queries) == 3
        assert result.queries[0] == "query 1"

    def test_empty_queries_allowed(self):
        result = SearchPlan(queries=[])
        assert result.queries == []


class TestSummary:
    def test_valid_summary(self):
        result = Summary(
            summary="AI is affecting jobs in multiple ways.",
            key_excerpts="Source: https://example.com\nAnother fact.",
        )
        assert "AI" in result.summary
        assert "example.com" in result.key_excerpts


class TestFinalReport:
    def test_valid_report(self):
        result = FinalReport(report="# Research Report\n\nFindings...")
        assert result.report.startswith("# Research Report")


class TestResearchState:
    def test_state_fields(self):
        state = ResearchState(
            messages=[],
            research_topic="test topic",
            search_queries=["q1", "q2"],
            search_results=[],
            notes=["note1"],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )
        # ResearchState extends MessagesState (TypedDict), so construction returns a dict
        assert state["research_topic"] == "test topic"
        assert len(state["search_queries"]) == 2
        assert state["iterations"] == 0
        assert state["research_level"] == ResearchLevel.STANDARD

    def test_research_state_with_messages(self):
        from langchain_core.messages import HumanMessage
        state = ResearchState(
            messages=[HumanMessage(content="I want to research X")],
            research_topic="",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.EXTENDED,
        )
        assert len(state["messages"]) == 1
        assert state["research_level"] == ResearchLevel.EXTENDED

    def test_research_state_defaults(self):
        # Only required fields — others get defaults from TypedDict
        state = ResearchState(
            messages=[],
        )
        assert state["messages"] == []
        # TypedDict doesn't enforce types at construction like Pydantic,
        # but fields are accessible via dict access
        assert state.get("research_level") is None
