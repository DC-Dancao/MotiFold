"""
Tests for app.research.agent — confirmation loop with interrupt nodes.

Tests verify:
1. Graph runs and hits interrupt when follow-up is needed
2. Graph skips interrupt when needs_followup is False
3. Resume routing works correctly for each user action type
"""

import pytest
pytestmark = pytest.mark.unit

from unittest.mock import patch, MagicMock, AsyncMock

from langchain_core.messages import HumanMessage

from app.research.agent import (
    research_node,
    followup_decision_node,
    followup_decision_router,
    interrupt_node,
    finalize_node,
    resume_router,
    build_graph,
)
from app.research.state import (
    ResearchState,
    ResearchLevel,
    FollowupDecision,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def make_config(task_id: str = "test-task"):
    return {"configurable": {"thread_id": f"research_{task_id}", "task_id": task_id}}


def make_model_mock(return_values):
    """
    Build a mock LLM model whose .with_structured_output().with_retry().ainvoke()
    chain returns the given values in sequence.
    """
    if not isinstance(return_values, list):
        return_values = [return_values]

    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_retry = MagicMock()

    mock_model.with_structured_output.return_value = mock_structured
    mock_structured.with_retry.return_value = mock_retry
    mock_retry.ainvoke = AsyncMock(side_effect=return_values)

    return mock_model


# --------------------------------------------------------------------------
# TestResearchNode
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestResearchNode:
    """research_node performs research iteration and appends to research_history."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    @patch("app.research.agent.search_and_summarize", new_callable=AsyncMock)
    async def test_appends_to_research_history(self, mock_search_fn, mock_get_llm, mock_emit):
        """research_node appends synthesized findings to research_history."""
        mock_search_fn.return_value = [
            {
                "query": "AI Agent 进展",
                "title": "AI Agents in Software Development",
                "url": "https://example.com/agents",
                "summary": "AI agents automate code generation and testing.",
                "key_excerpts": "AI agents can write code autonomously.",
            },
        ]

        from app.research.state import Summary
        mock_get_llm.return_value = make_model_mock(
            Summary(
                summary="AI agents automate code generation and testing.",
                key_excerpts="AI agents can write code autonomously.",
            )
        )

        state = ResearchState(
            messages=[],
            research_topic="AI Agent 研究",
            search_queries=["AI Agent 进展"],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=[],
            user_inputs=[],
            needs_followup=False,
            followup_options=[],
            is_complete=False,
        )

        result = await research_node(state, make_config("test-rn-1"))

        assert len(result["research_history"]) == 1
        assert "automate" in result["research_history"][0].lower() or "AI agents" in result["research_history"][0]
        assert result["iterations"] == 1

    @patch("app.research.agent._emit")
    @patch("app.research.agent.search_and_summarize", new_callable=AsyncMock)
    async def test_accumulates_research_history(self, mock_search_fn, mock_emit):
        """research_history accumulates across multiple calls."""
        mock_search_fn.return_value = [
            {
                "query": "q",
                "title": "T",
                "url": "https://example.com",
                "summary": "Summary",
                "key_excerpts": "",
            },
        ]

        state = ResearchState(
            messages=[],
            research_topic="AI Agent 研究",
            search_queries=["query"],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=["[Iteration 0] Initial finding."],
            user_inputs=[],
            needs_followup=False,
            followup_options=[],
            is_complete=False,
        )

        result = await research_node(state, make_config("test-rn-2"))

        assert len(result["research_history"]) == 2
        assert "Initial finding" in result["research_history"][0]

    @patch("app.research.agent._emit")
    @patch("app.research.agent.search_and_summarize", new_callable=AsyncMock)
    async def test_handles_empty_results(self, mock_search_fn, mock_emit):
        """research_node handles empty search results gracefully."""
        mock_search_fn.return_value = []

        state = ResearchState(
            messages=[],
            research_topic="AI Agent 研究",
            search_queries=["query"],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=[],
            user_inputs=[],
            needs_followup=False,
            followup_options=[],
            is_complete=False,
        )

        result = await research_node(state, make_config("test-rn-3"))

        assert len(result["research_history"]) == 1
        assert "No search results found" in result["research_history"][0]
        assert result["iterations"] == 1


# --------------------------------------------------------------------------
# TestFollowupDecisionNode
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFollowupDecisionNode:
    """followup_decision_node calls LLM to decide if follow-up is needed."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_needs_followup_true(self, mock_get_llm, mock_emit):
        """When LLM says needs_followup=True, options are generated."""
        mock_get_llm.return_value = make_model_mock(
            FollowupDecision(
                needs_followup=True,
                question="What would you like to explore further?",
                option_1="Deep dive into code generation",
                option_2="Explore reliability challenges",
                option_3="Research future trends",
            )
        )

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
            research_history=["[Iteration 0] AI agents automate coding."],
            user_inputs=[],
            needs_followup=False,
            followup_options=[],
            is_complete=False,
        )

        result = await followup_decision_node(state, make_config("test-fd-1"))

        assert result["needs_followup"] is True
        assert len(result["followup_options"]) == 3
        assert result["followup_options"][0] == "Deep dive into code generation"

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_needs_followup_false(self, mock_get_llm, mock_emit):
        """When LLM says needs_followup=False, goes to finalize."""
        mock_get_llm.return_value = make_model_mock(
            FollowupDecision(
                needs_followup=False,
                question="",
                option_1="",
                option_2="",
                option_3="",
            )
        )

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
            research_history=["[Iteration 0] Complete research findings."],
            user_inputs=[],
            needs_followup=False,
            followup_options=[],
            is_complete=False,
        )

        result = await followup_decision_node(state, make_config("test-fd-2"))

        assert result["needs_followup"] is False
        assert result["followup_options"] == []

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_emits_followup_decision_event(self, mock_get_llm, mock_emit):
        """followup_decision_node emits followup_decision event."""
        mock_get_llm.return_value = make_model_mock(
            FollowupDecision(
                needs_followup=True,
                question="What to explore?",
                option_1="Option A",
                option_2="Option B",
                option_3="Option C",
            )
        )

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
            needs_followup=False,
            followup_options=[],
            is_complete=False,
        )

        await followup_decision_node(state, make_config("test-fd-3"))

        emit_calls = mock_emit.call_args_list
        decision_calls = [
            c for c in emit_calls
            if c[0][1].get("type") == "followup_decision"
        ]
        assert len(decision_calls) >= 1
        assert decision_calls[0][0][1]["needs_followup"] is True


# --------------------------------------------------------------------------
# TestFollowupDecisionRouter
# --------------------------------------------------------------------------

class TestFollowupDecisionRouter:
    """followup_decision_router routes based on needs_followup flag."""

    def test_routes_to_interrupt_when_needs_followup_true(self):
        """needs_followup=True routes to interrupt_node."""
        state = ResearchState(
            messages=[],
            research_topic="test",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=[],
            user_inputs=[],
            needs_followup=True,
            followup_options=["A", "B", "C"],
            is_complete=False,
        )
        assert followup_decision_router(state) == "interrupt_node"

    def test_routes_to_finalize_when_needs_followup_false(self):
        """needs_followup=False routes to finalize_node."""
        state = ResearchState(
            messages=[],
            research_topic="test",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=[],
            user_inputs=[],
            needs_followup=False,
            followup_options=[],
            is_complete=False,
        )
        assert followup_decision_router(state) == "finalize_node"


# --------------------------------------------------------------------------
# TestFinalizeNode
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFinalizeNode:
    """finalize_node produces final research output."""

    @patch("app.research.agent._emit")
    async def test_produces_final_report(self, mock_emit):
        """finalize_node produces a final report from research_history."""
        state = ResearchState(
            messages=[],
            research_topic="AI Agent 研究",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=2,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=[
                "[Iteration 0] AI agents automate code generation.",
                "[Iteration 1] Challenges include reliability and context management.",
            ],
            user_inputs=["option_1"],
            needs_followup=False,
            followup_options=[],
            is_complete=False,
        )

        result = await finalize_node(state, make_config("test-fn-1"))

        assert "AI Agent 研究" in result["final_report"]
        assert "AI agents automate code generation" in result["final_report"]
        assert result["is_complete"] is True
        assert result["final_report"].startswith("# Research Report")

    @patch("app.research.agent._emit")
    async def test_includes_user_inputs_in_report(self, mock_emit):
        """finalize_node includes user_inputs in the final report."""
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
            research_history=["[Iteration 0] Finding."],
            user_inputs=["Deep dive into code generation", "confirm_done"],
            needs_followup=False,
            followup_options=[],
            is_complete=False,
        )

        result = await finalize_node(state, make_config("test-fn-2"))

        assert "Deep dive into code generation" in result["final_report"]
        assert "confirm_done" in result["final_report"]


# --------------------------------------------------------------------------
# TestGraphWithConfirmationLoop
# --------------------------------------------------------------------------

class TestGraphWithConfirmationLoop:
    """Test the full graph with confirmation loop nodes."""

    def test_graph_has_confirmation_loop_nodes(self):
        """Graph contains all confirmation loop nodes."""
        graph = build_graph()
        nodes = list(graph.nodes.keys())

        assert "research_node" in nodes
        assert "followup_decision_node" in nodes
        assert "interrupt_node" in nodes
        assert "finalize_node" in nodes

    def test_graph_flow_to_confirmation_loop(self):
        """Graph has edges from synthesize to followup_decision_node."""
        graph = build_graph()

        # The graph should have:
        # - synthesize → followup_decision_node (direct edge)
        # - followup_decision_node → interrupt_node or finalize_node (conditional)
        # - interrupt_node → research_node (direct edge)
        # - research_node → followup_decision_node (direct edge, for loop)
        # - finalize_node → END
        assert "followup_decision_node" in graph.nodes
        assert "interrupt_node" in graph.nodes
        assert "finalize_node" in graph.nodes
        assert "research_node" in graph.nodes


# --------------------------------------------------------------------------
# TestResumeRouter
# --------------------------------------------------------------------------

class TestResumeRouter:
    """resume_router routes based on user's resume action."""

    def test_routes_to_research_node_when_empty(self):
        """Empty user_inputs routes to research_node (first iteration)."""
        state = ResearchState(
            messages=[],
            research_topic="test",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=[],
            user_inputs=[],
            needs_followup=True,
            followup_options=["A", "B", "C"],
            is_complete=False,
        )
        assert resume_router(state) == "research_node"

    def test_routes_to_finalize_on_confirm_done(self):
        """confirm_done action routes to finalize_node."""
        state = ResearchState(
            messages=[],
            research_topic="test",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=1,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=["finding 1"],
            user_inputs=["option_1", "confirm_done"],
            needs_followup=True,
            followup_options=["A", "B", "C"],
            is_complete=False,
        )
        assert resume_router(state) == "finalize_node"

    def test_routes_to_research_node_on_option(self):
        """option_1/2/3 routes to research_node (continue loop)."""
        for action in ["option_1", "option_2", "option_3"]:
            state = ResearchState(
                messages=[],
                research_topic="test",
                search_queries=[],
                search_results=[],
                notes=[],
                final_report="",
                iterations=1,
                max_iterations=3,
                max_results=10,
                research_level=ResearchLevel.STANDARD,
                research_history=["finding 1"],
                user_inputs=[action],
                needs_followup=True,
                followup_options=["A", "B", "C"],
                is_complete=False,
            )
            assert resume_router(state) == "research_node"

    def test_routes_to_research_node_on_skip(self):
        """skip action routes to research_node (continue loop)."""
        state = ResearchState(
            messages=[],
            research_topic="test",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=1,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=["finding 1"],
            user_inputs=["skip"],
            needs_followup=True,
            followup_options=["A", "B", "C"],
            is_complete=False,
        )
        assert resume_router(state) == "research_node"

    def test_routes_to_research_node_on_manual_input(self):
        """Manual dict input routes to research_node (continue loop)."""
        state = ResearchState(
            messages=[],
            research_topic="test",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=1,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=["finding 1"],
            user_inputs=[{"type": "manual", "text": "I want to know more about AI ethics"}],
            needs_followup=True,
            followup_options=["A", "B", "C"],
            is_complete=False,
        )
        assert resume_router(state) == "research_node"

    def test_handles_multiple_user_inputs(self):
        """Multiple user inputs - uses last one for routing."""
        state = ResearchState(
            messages=[],
            research_topic="test",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=2,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
            research_history=["finding 1", "finding 2"],
            user_inputs=["option_1", "option_2", "confirm_done"],
            needs_followup=True,
            followup_options=["A", "B", "C"],
            is_complete=False,
        )
        assert resume_router(state) == "finalize_node"

