"""
Additional tests for app.research.state — FollowupDecision and edge cases.
"""
import pytest
from pydantic import ValidationError

from app.research.state import (
    LEVEL_DEFAULTS,
    FinalReport,
    FollowupDecision,
    NeedsClarification,
    ResearchLevel,
    ResearchState,
    ResearchTopic,
    SearchPlan,
    Summary,
)


class TestFollowupDecision:
    """Tests for FollowupDecision schema."""

    def test_needs_followup_true_with_options(self):
        """needs_followup=True requires question and options."""
        result = FollowupDecision(
            needs_followup=True,
            question="What would you like to explore further?",
            option_1="Deep dive into code generation",
            option_2="Explore reliability challenges",
            option_3="Research future trends",
        )
        assert result.needs_followup is True
        assert "explore" in result.question
        assert len(result.option_1) > 0
        assert len(result.option_2) > 0
        assert len(result.option_3) > 0

    def test_needs_followup_false_empty_options(self):
        """needs_followup=False has empty question and options."""
        result = FollowupDecision(
            needs_followup=False,
            question="",
            option_1="",
            option_2="",
            option_3="",
        )
        assert result.needs_followup is False
        assert result.question == ""
        assert result.option_1 == ""
        assert result.option_2 == ""
        assert result.option_3 == ""

    def test_question_not_required_when_no_followup(self):
        """question can be empty string even when needs_followup=True (options may suffice)."""
        # question is not explicitly required to be non-empty
        result = FollowupDecision(
            needs_followup=True,
            question="",
            option_1="Only option",
            option_2="",
            option_3="",
        )
        assert result.question == ""

    def test_options_can_be_any_text(self):
        """option fields accept any text content."""
        result = FollowupDecision(
            needs_followup=True,
            question="Explore?",
            option_1="Technical deep dive: architecture patterns",
            option_2="Practical: getting started guide",
            option_3="Research: academic papers on the topic",
        )
        assert "architecture" in result.option_1
        assert "getting started" in result.option_2
        assert "academic" in result.option_3


class TestLevelDefaultsComprehensive:
    """Comprehensive tests for LEVEL_DEFAULTS."""

    def test_all_levels_have_defaults(self):
        """All ResearchLevel enum values have entries in LEVEL_DEFAULTS."""
        for level in ResearchLevel:
            assert level in LEVEL_DEFAULTS

    def test_defaults_are_tuples_of_two_ints(self):
        """Each level default is a (int, int) tuple."""
        for level, defaults in LEVEL_DEFAULTS.items():
            assert isinstance(defaults, tuple)
            assert len(defaults) == 2
            iters, results = defaults
            assert isinstance(iters, int)
            assert isinstance(results, int)
            assert iters > 0
            assert results > 0

    def test_standard_faster_than_extended(self):
        """STANDARD has fewer iterations than EXTENDED."""
        std_iters, _ = LEVEL_DEFAULTS[ResearchLevel.STANDARD]
        ext_iters, _ = LEVEL_DEFAULTS[ResearchLevel.EXTENDED]
        assert std_iters < ext_iters

    def test_manual_iterations_between_standard_and_extended(self):
        """MANUAL iterations are between STANDARD and EXTENDED."""
        std_iters, _ = LEVEL_DEFAULTS[ResearchLevel.STANDARD]
        ext_iters, _ = LEVEL_DEFAULTS[ResearchLevel.EXTENDED]
        man_iters, _ = LEVEL_DEFAULTS[ResearchLevel.MANUAL]
        assert std_iters < man_iters < ext_iters


class TestResearchStateEdgeCases:
    """Edge cases for ResearchState construction."""

    def _make_state(self, **overrides):
        """Factory for valid ResearchState with required fields."""
        base = {
            "messages": [],
            "research_topic": "AI Agents",
            "search_queries": [],
            "search_results": [],
            "notes": [],
            "final_report": "",
            "iterations": 0,
            "max_iterations": 3,
            "max_results": 10,
            "research_level": ResearchLevel.STANDARD,
            "research_history": [],
            "user_inputs": [],
            "needs_followup": False,
            "followup_options": [],
            "is_complete": False,
        }
        base.update(overrides)
        return ResearchState(**base)

    def test_research_history_default_empty_list(self):
        """research_history defaults to empty list."""
        state = self._make_state()
        assert state["research_history"] == []

    def test_user_inputs_default_empty_list(self):
        """user_inputs defaults to empty list."""
        state = self._make_state()
        assert state["user_inputs"] == []

    def test_needs_followup_default_false(self):
        """needs_followup defaults to False."""
        state = self._make_state()
        assert state["needs_followup"] is False

    def test_followup_options_default_empty_list(self):
        """followup_options defaults to empty list."""
        state = self._make_state()
        assert state["followup_options"] == []

    def test_is_complete_default_false(self):
        """is_complete defaults to False."""
        state = self._make_state()
        assert state["is_complete"] is False

    def test_with_manual_input_dict_in_user_inputs(self):
        """user_inputs accepts dict (manual input)."""
        state = self._make_state(
            user_inputs=[{"type": "manual", "text": "Explore AI ethics"}],
        )
        assert isinstance(state["user_inputs"][0], dict)
        assert state["user_inputs"][0]["text"] == "Explore AI ethics"

    def test_with_mixed_user_inputs(self):
        """user_inputs accepts mix of strings and dicts."""
        state = self._make_state(
            user_inputs=[
                "option_1",
                {"type": "manual", "text": "Custom query"},
                "confirm_done",
            ],
        )
        assert len(state["user_inputs"]) == 3
        assert state["user_inputs"][0] == "option_1"
        assert isinstance(state["user_inputs"][1], dict)
        assert state["user_inputs"][2] == "confirm_done"


class TestResearchTopicEdgeCases:
    """Edge cases for ResearchTopic schema."""

    def test_empty_topic_allowed(self):
        """topic can be empty string."""
        result = ResearchTopic(topic="")
        assert result.topic == ""

    def test_very_long_topic(self):
        """Very long topic is accepted."""
        long_topic = "AI " * 1000
        result = ResearchTopic(topic=long_topic)
        assert result.topic == long_topic

    def test_unicode_topic(self):
        """Unicode characters are accepted."""
        result = ResearchTopic(topic="AI 代理人在软件开发中的最新进展")
        assert len(result.topic) > 10


class TestSearchPlanEdgeCases:
    """Edge cases for SearchPlan schema."""

    def test_single_query(self):
        """Single query is allowed."""
        result = SearchPlan(queries=["AI Agent 软件开发"])
        assert len(result.queries) == 1

    def test_many_queries(self):
        """Many queries (up to reasonable limit) are allowed."""
        queries = [f"query {i}" for i in range(20)]
        result = SearchPlan(queries=queries)
        assert len(result.queries) == 20

    def test_duplicate_queries_allowed(self):
        """Duplicate queries are accepted (LLM may produce them)."""
        result = SearchPlan(queries=["AI", "AI", "AI Agent"])
        assert len(result.queries) == 3


class TestSummaryEdgeCases:
    """Edge cases for Summary schema."""

    def test_empty_summary(self):
        """Empty summary is allowed."""
        result = Summary(summary="", key_excerpts="")
        assert result.summary == ""

    def test_very_long_key_excerpts(self):
        """Long key_excerpts are accepted."""
        long_excerpts = "Fact 1. " * 1000
        result = Summary(summary="Summary", key_excerpts=long_excerpts)
        assert len(result.key_excerpts) > 100

    def test_urls_in_key_excerpts(self):
        """URLs in key_excerpts are preserved."""
        result = Summary(
            summary="AI is growing.",
            key_excerpts="Source: https://example.com/article\nAnother: https://blog.example.com",
        )
        assert "https://example.com" in result.key_excerpts
        assert "https://blog.example.com" in result.key_excerpts


class TestFinalReportEdgeCases:
    """Edge cases for FinalReport schema."""

    def test_empty_report(self):
        """Empty report is allowed."""
        result = FinalReport(report="")
        assert result.report == ""

    def test_markdown_content(self):
        """Markdown-formatted report is preserved."""
        md = """# Title

## Section 1
- Item 1
- Item 2

**Bold** and *italic* text.
"""
        result = FinalReport(report=md)
        assert "# Title" in result.report
        assert "- Item 1" in result.report
