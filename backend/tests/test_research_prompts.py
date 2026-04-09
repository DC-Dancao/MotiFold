"""
Tests for app.research.prompts — prompt template formatting.
"""

import pytest

from app.research.prompts import (
    CLARIFY_PROMPT,
    RESEARCH_TOPIC_PROMPT,
    SEARCH_PLAN_PROMPT,
    SYNTHESIZE_PROMPT,
    REPORT_PROMPT,
)


class TestPrompts:
    def test_clarify_prompt_format(self):
        rendered = CLARIFY_PROMPT.format(
            date="Thu Apr 9, 2026",
            messages="User: What is AI?\nAssistant: AI stands for Artificial Intelligence.",
        )
        assert "Thu Apr 9, 2026" in rendered
        assert "What is AI" in rendered

    def test_research_topic_prompt_format(self):
        rendered = RESEARCH_TOPIC_PROMPT.format(
            message="What is the impact of AI on software jobs?",
            date="Thu Apr 9, 2026",
        )
        assert "Thu Apr 9, 2026" in rendered
        assert "AI" in rendered
        assert "software jobs" in rendered.lower()

    def test_search_plan_prompt_format(self):
        rendered = SEARCH_PLAN_PROMPT.format(
            topic="Impact of AI on employment",
            date="Thu Apr 9, 2026",
        )
        assert "Impact of AI on employment" in rendered
        assert "3-8" in rendered  # query count guidance

    def test_synthesize_prompt_format(self):
        rendered = SYNTHESIZE_PROMPT.format(
            topic="AI research",
            date="Thu Apr 9, 2026",
            results="Source: https://example.com\nSummary: AI is growing.",
        )
        assert "AI research" in rendered
        assert "example.com" in rendered

    def test_report_prompt_format(self):
        rendered = REPORT_PROMPT.format(
            topic="AI impact on jobs",
            date="Thu Apr 9, 2026",
            num_notes=3,
            notes="Note 1\n\nNote 2\n\nNote 3",
        )
        assert "AI impact on jobs" in rendered
        assert "3" in rendered  # num_notes
        assert "markdown" in rendered.lower()

    def test_all_prompts_contain_expected_sections(self):
        """Sanity check: all prompts have meaningful content."""
        assert len(CLARIFY_PROMPT) > 100
        assert len(RESEARCH_TOPIC_PROMPT) > 100
        assert len(SEARCH_PLAN_PROMPT) > 50
        assert len(SYNTHESIZE_PROMPT) > 100
        assert len(REPORT_PROMPT) > 100
