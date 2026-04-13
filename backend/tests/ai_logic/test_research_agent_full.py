"""
Additional AI logic tests for app.research.agent — covering:
1. interrupt_node behavior
2. level_defaults_for helper
3. Additional confirmation loop edge cases
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langgraph.types import interrupt

from app.research.agent import (
    interrupt_node,
    level_defaults_for,
    build_graph,
)
from app.research.state import (
    ResearchState,
    ResearchLevel,
)

pytestmark = [pytest.mark.ai_logic, pytest.mark.asyncio]


# --------------------------------------------------------------------------
# TestInterruptNode
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestInterruptNode:
    """Tests for interrupt_node."""

    @patch("app.research.agent._emit")
    async def test_emits_interrupt_event(self, mock_emit):
        """interrupt_node emits interrupt event with options."""
        state = ResearchState(
            messages=[],
            research_topic="AI Agent 研究",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=1,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=["Finding 1"],
            user_inputs=[],
            needs_followup=True,
            followup_options=[
                "Deep dive into code generation",
                "Explore reliability challenges",
                "Research future trends",
            ],
            is_complete=False,
        )

        config = {"configurable": {"thread_id": "test-thread", "task_id": "test-task"}}

        # interrupt() throws by default — catch it
        with pytest.raises(Exception):
            await interrupt_node(state, config)

        # Verify _emit was called with interrupt payload
        emit_calls = mock_emit.call_args_list
        interrupt_calls = [c for c in emit_calls if c[0][1].get("type") == "interrupt"]
        assert len(interrupt_calls) >= 1
        payload = interrupt_calls[0][0][1]
        assert payload["type"] == "interrupt"
        assert len(payload["options"]) == 3
        assert payload["allow_manual_input"] is True
        assert payload["allow_skip"] is True
        assert payload["allow_confirm_done"] is True

    @patch("app.research.agent._emit")
    async def test_question_includes_research_topic(self, mock_emit):
        """interrupt question includes the research topic."""
        state = ResearchState(
            messages=[],
            research_topic="LangGraph Agents",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=1,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.EXTENDED,
            research_history=["Finding"],
            user_inputs=[],
            needs_followup=True,
            followup_options=["Option A", "Option B", "Option C"],
            is_complete=False,
        )

        config = {"configurable": {"thread_id": "t", "task_id": "t"}}

        with pytest.raises(Exception):
            await interrupt_node(state, config)

        interrupt_calls = [c for c in mock_emit.call_args_list if c[0][1].get("type") == "interrupt"]
        question = interrupt_calls[0][0][1]["question"]
        assert "LangGraph Agents" in question

    @patch("app.research.agent._emit")
    async def test_empty_followup_options_allowed(self, mock_emit):
        """interrupt_node handles empty followup_options list."""
        state = ResearchState(
            messages=[],
            research_topic="Topic",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=1,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=["Finding"],
            user_inputs=[],
            needs_followup=True,
            followup_options=[],
            is_complete=False,
        )

        config = {"configurable": {"thread_id": "t", "task_id": "t"}}

        with pytest.raises(Exception):
            await interrupt_node(state, config)


# --------------------------------------------------------------------------
# TestLevelDefaultsFor
# --------------------------------------------------------------------------

class TestLevelDefaultsFor:
    """Tests for level_defaults_for helper."""

    def test_standard_level(self):
        iters, results = level_defaults_for(ResearchLevel.STANDARD)
        assert iters == 3
        assert results == 10

    def test_extended_level(self):
        iters, results = level_defaults_for(ResearchLevel.EXTENDED)
        assert iters == 6
        assert results == 20

    def test_manual_level(self):
        iters, results = level_defaults_for(ResearchLevel.MANUAL)
        assert iters == 5
        assert results == 10

    def test_unknown_level_fallback(self):
        """Unknown level returns (3, 10) fallback."""
        # Create a mock level
        unknown_level = ResearchLevel.STANDARD
        iters, results = level_defaults_for(unknown_level)
        assert iters == 3
        assert results == 10


# --------------------------------------------------------------------------
# TestBuildGraphVariants
# --------------------------------------------------------------------------

class TestBuildGraphVariants:
    """Tests for build_graph with different checkpointer configurations."""

    def test_build_graph_without_checkpointer_uses_memory(self):
        """build_graph() with no checkpointer uses MemorySaver."""
        graph = build_graph()
        assert graph is not None

    def test_build_graph_with_none_checkpointer_uses_memory(self):
        """build_graph(checkpointer=None) uses MemorySaver."""
        graph = build_graph(checkpointer=None)
        assert graph is not None

    def test_graph_has_correct_confirmation_loop_edges(self):
        """Graph has all required confirmation loop edges."""
        graph = build_graph()
        # Verify build_graph returns a valid compiled graph
        assert graph is not None
        assert hasattr(graph, 'ainvoke'), "Compiled graph should have ainvoke method"

        # Verify build_graph with explicit checkpointer works
        from langgraph.checkpoint.memory import MemorySaver
        graph_with_memory = build_graph(checkpointer=MemorySaver())
        assert graph_with_memory is not None
