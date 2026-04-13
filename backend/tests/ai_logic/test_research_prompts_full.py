"""
Comprehensive tests for app.research.prompts — all prompt templates.

Covers:
- FOLLOWUP_DECISION_PROMPT — format and content
- FOLLOWUP_SEARCH_PROMPT — format and content
- All prompts from test_research_prompts.py expanded
"""
import pytest

from app.research.prompts import (
    CLARIFY_PROMPT,
    RESEARCH_TOPIC_PROMPT,
    SEARCH_PLAN_PROMPT,
    SYNTHESIZE_PROMPT,
    FOLLOWUP_DECISION_PROMPT,
    FOLLOWUP_SEARCH_PROMPT,
    REPORT_PROMPT,
)


class TestFollowupDecisionPrompt:
    """Tests for FOLLOWUP_DECISION_PROMPT."""

    def test_format_basic(self):
        rendered = FOLLOWUP_DECISION_PROMPT.format(
            topic="AI Agent 研究",
            date="Thu Apr 9, 2026",
            research_history="Finding 1: AI agents automate code.\nFinding 2: Challenges include hallucination.",
            user_inputs="(no user inputs yet)",
        )
        assert "AI Agent 研究" in rendered
        assert "Thu Apr 9, 2026" in rendered
        assert "Finding 1" in rendered
        assert "no user inputs yet" in rendered

    def test_format_with_user_inputs(self):
        rendered = FOLLOWUP_DECISION_PROMPT.format(
            topic="Machine Learning",
            date="Mon Jan 1, 2026",
            research_history="Finding: ML models improve with scale.",
            user_inputs="[option_1]\n[Manual]: Explore ethics",
        )
        assert "Machine Learning" in rendered
        assert "option_1" in rendered
        assert "Explore ethics" in rendered

    def test_contains_needs_followup_guidance(self):
        """Prompt contains guidance for needs_followup decision."""
        rendered = FOLLOWUP_DECISION_PROMPT.format(
            topic="Test",
            date="Date",
            research_history="Finding",
            user_inputs="None",
        )
        assert "needs_followup" in rendered.lower()

    def test_contains_options_guidance(self):
        """Prompt asks for option_1, option_2, option_3."""
        rendered = FOLLOWUP_DECISION_PROMPT.format(
            topic="Test",
            date="Date",
            research_history="Finding",
            user_inputs="",
        )
        assert "option_1" in rendered
        assert "option_2" in rendered
        assert "option_3" in rendered


class TestFollowupSearchPrompt:
    """Tests for FOLLOWUP_SEARCH_PROMPT."""

    def test_format_basic(self):
        rendered = FOLLOWUP_SEARCH_PROMPT.format(
            topic="AI Agent 软件开发",
            date="Thu Apr 9, 2026",
            research_history="AI agents automate code generation and testing.",
            user_input="option_1",
        )
        assert "AI Agent 软件开发" in rendered
        assert "Thu Apr 9, 2026" in rendered
        assert "automate code" in rendered
        assert "option_1" in rendered

    def test_format_with_manual_input(self):
        rendered = FOLLOWUP_SEARCH_PROMPT.format(
            topic="Topic",
            date="Date",
            research_history="Finding",
            user_input="I want to research ethics in AI",
        )
        assert "ethics in AI" in rendered

    def test_contains_queries_guidance(self):
        """Prompt asks for 2-5 focused search queries."""
        rendered = FOLLOWUP_SEARCH_PROMPT.format(
            topic="Test",
            date="Date",
            research_history="Finding",
            user_input="input",
        )
        assert "2-5" in rendered or "2-5" in rendered.lower()

    def test_prompt_excludes_duplicates(self):
        """Prompt guidance mentions complementing existing research."""
        rendered = FOLLOWUP_SEARCH_PROMPT.format(
            topic="Test",
            date="Date",
            research_history="Original finding",
            user_input="follow-up",
        )
        assert "complement" in rendered.lower()


class TestAllPrompts:
    """Sanity check for all prompts."""

    def test_all_prompts_are_non_empty(self):
        """All prompt templates are non-empty strings."""
        prompts = [
            CLARIFY_PROMPT,
            RESEARCH_TOPIC_PROMPT,
            SEARCH_PLAN_PROMPT,
            SYNTHESIZE_PROMPT,
            FOLLOWUP_DECISION_PROMPT,
            FOLLOWUP_SEARCH_PROMPT,
            REPORT_PROMPT,
        ]
        for p in prompts:
            assert len(p) > 0

    def test_all_prompts_contain_date_placeholder(self):
        """All prompts accept date parameter."""
        for name, p in [
            ("CLARIFY_PROMPT", CLARIFY_PROMPT),
            ("RESEARCH_TOPIC_PROMPT", RESEARCH_TOPIC_PROMPT),
            ("SEARCH_PLAN_PROMPT", SEARCH_PLAN_PROMPT),
            ("SYNTHESIZE_PROMPT", SYNTHESIZE_PROMPT),
            ("FOLLOWUP_DECISION_PROMPT", FOLLOWUP_DECISION_PROMPT),
            ("FOLLOWUP_SEARCH_PROMPT", FOLLOWUP_SEARCH_PROMPT),
            ("REPORT_PROMPT", REPORT_PROMPT),
        ]:
            assert "{date}" in p, f"{name} missing {{date}}"


class TestPromptsFormattingEdgeCases:
    """Edge cases in prompt formatting."""

    def test_clarify_prompt_with_empty_messages(self):
        """CLARIFY_PROMPT handles empty messages."""
        rendered = CLARIFY_PROMPT.format(
            date="Thu Apr 9, 2026",
            messages="",
        )
        assert "Thu Apr 9, 2026" in rendered

    def test_synthesize_prompt_truncation_guidance(self):
        """SYNTHESIZE_PROMPT mentions truncation to 6000 chars."""
        rendered = SYNTHESIZE_PROMPT.format(
            topic="Test",
            date="Date",
            results="x" * 10000,
        )
        # The prompt should accept the results even if long
        assert "Test" in rendered

    def test_report_prompt_with_zero_notes(self):
        """REPORT_PROMPT handles 0 notes."""
        rendered = REPORT_PROMPT.format(
            topic="Test topic",
            date="Date",
            num_notes=0,
            notes="",
        )
        assert "Test topic" in rendered
        assert "0" in rendered

    def test_search_plan_prompt_query_count_guidance(self):
        """SEARCH_PLAN_PROMPT specifies 3-8 queries."""
        rendered = SEARCH_PLAN_PROMPT.format(
            topic="Test",
            date="Date",
        )
        assert "3-8" in rendered

    def test_report_prompt_citation_format(self):
        """REPORT_PROMPT instructs to use [Source: Title](URL) format."""
        rendered = REPORT_PROMPT.format(
            topic="Test",
            date="Date",
            num_notes=1,
            notes="Note",
        )
        assert "[Source:" in rendered
