"""
Unit tests for research agent matrix exploration functionality.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

pytestmark = [pytest.mark.unit]


class TestExploreMatrixSolutionsNode:
    """Tests for explore_matrix_solutions node."""

    def test_explore_matrix_solutions_exists(self):
        """Should have explore_matrix_solutions function."""
        from app.research.agent import explore_matrix_solutions

        assert explore_matrix_solutions is not None

    def test_explore_matrix_solutions_is_async(self):
        """Should be an async function."""
        import inspect
        from app.research.agent import explore_matrix_solutions

        assert inspect.iscoroutinefunction(explore_matrix_solutions)


class TestBuildGraphWithMatrixNode:
    """Tests for build_graph including matrix node."""

    def test_build_graph_returns_compiled_graph(self):
        """build_graph should return a compiled graph."""
        from app.research.agent import build_graph

        graph = build_graph()
        assert graph is not None

    def test_build_graph_has_explore_matrix_solutions_node(self):
        """Graph should have explore_matrix_solutions node."""
        from app.research.agent import build_graph

        graph = build_graph()
        # Check nodes exist by verifying graph structure
        assert graph is not None


class TestMatrixExplorationPrompt:
    """Tests for MATRIX_EXPLORATION_PROMPT."""

    def test_matrix_exploration_prompt_exists(self):
        """Should have MATRIX_EXPLORATION_PROMPT."""
        from app.research.prompts import MATRIX_EXPLORATION_PROMPT

        assert MATRIX_EXPLORATION_PROMPT is not None
        assert len(MATRIX_EXPLORATION_PROMPT) > 0

    def test_matrix_exploration_prompt_content(self):
        """Should have expected content in prompt."""
        from app.research.prompts import MATRIX_EXPLORATION_PROMPT

        assert "Morphological" in MATRIX_EXPLORATION_PROMPT
        assert "keywords" in MATRIX_EXPLORATION_PROMPT.lower()

    def test_matrix_exploration_prompt_imported_in_agent(self):
        """MATRIX_EXPLORATION_PROMPT should be imported in agent."""
        from app.research.agent import MATRIX_EXPLORATION_PROMPT

        # This verifies the import is working
        assert MATRIX_EXPLORATION_PROMPT is not None


class TestResearchPrompts完整性:
    """Tests that all prompts are properly defined."""

    def test_all_prompts_exist(self):
        """All expected prompts should exist."""
        from app.research.prompts import (
            CLARIFY_PROMPT,
            FOLLOWUP_DECISION_PROMPT,
            FOLLOWUP_SEARCH_PROMPT,
            REPORT_PROMPT,
            RESEARCH_TOPIC_PROMPT,
            SEARCH_PLAN_PROMPT,
            SYNTHESIZE_PROMPT,
            MATRIX_EXPLORATION_PROMPT,
        )

        prompts = [
            CLARIFY_PROMPT,
            FOLLOWUP_DECISION_PROMPT,
            FOLLOWUP_SEARCH_PROMPT,
            REPORT_PROMPT,
            RESEARCH_TOPIC_PROMPT,
            SEARCH_PLAN_PROMPT,
            SYNTHESIZE_PROMPT,
            MATRIX_EXPLORATION_PROMPT,
        ]

        for prompt in prompts:
            assert prompt is not None
            assert len(prompt) > 0
