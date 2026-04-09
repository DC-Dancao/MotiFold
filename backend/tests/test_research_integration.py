"""
Integration tests for app.research.agent — tests LLM prompt quality with mocks.

These tests patch get_llm() to return controlled responses, avoiding real API calls
and network I/O while verifying the agent's node logic and state transitions.

Scope:
- clarify_topic, plan_search, synthesize nodes
- should_continue routing function
- Full graph compilation and end-to-end state flow
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from langchain_core.messages import HumanMessage

from app.research.agent import (
    clarify_topic,
    plan_search,
    synthesize,
    should_continue,
    build_graph,
)
from langgraph.graph import END

from app.research.state import (
    ResearchState,
    NeedsClarification,
    ResearchTopic,
    SearchPlan,
    Summary,
    ResearchLevel,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def make_config(task_id: str = "test-task"):
    return {"configurable": {"thread_id": f"research_{task_id}", "task_id": task_id}}


def mock_llm_model(return_values):
    """
    Build a mock LLM model that returns sequenced values from ainvoke.

    Args:
        return_values: single value or list of values to return in order
    """
    if not isinstance(return_values, list):
        return_values = [return_values]

    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_astream = AsyncMock(side_effect=return_values)
    mock_structured.ainvoke = mock_astream
    mock_model.with_structured_output.return_value.with_retry.return_value = mock_structured
    return mock_model


# --------------------------------------------------------------------------
# clarify_topic tests
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestClarifyTopicIntegration:
    """Tests for clarify_topic node with mocked LLM."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_needs_clarification_true(self, mock_get_llm, mock_emit):
        """When LLM says clarification needed, node goes to END."""
        mock_get_llm.return_value = mock_llm_model(
            NeedsClarification(
                need_clarification=True,
                question="您关注的是哪个地区？",
                verification="",
            )
        )

        state = ResearchState(
            messages=[HumanMessage(content="AI 的影响")],
            research_topic="",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await clarify_topic(state, make_config("test-clarify-1"))

        assert result.goto == END
        assert result.update is None

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_research_topic_extracted(self, mock_get_llm, mock_emit):
        """When no clarification needed, node extracts topic and goes to plan_search."""
        mock_get_llm.return_value = mock_llm_model([
            NeedsClarification(
                need_clarification=False,
                question="",
                verification="好的，开始研究。",
            ),
            ResearchTopic(topic="AI 对软件就业市场的影响"),
        ])

        state = ResearchState(
            messages=[HumanMessage(content="AI 对程序员影响大吗")],
            research_topic="",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await clarify_topic(state, make_config("test-clarify-2"))

        assert result.goto == "plan_search"
        assert "AI" in result.update["research_topic"]
        assert "软件" in result.update["research_topic"]

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_verification_message_emitted(self, mock_get_llm, mock_emit):
        """When LLM returns verification text, it is emitted as a status event."""
        mock_get_llm.return_value = mock_llm_model([
            NeedsClarification(
                need_clarification=False,
                question="",
                verification="了解，开始调研。",
            ),
            ResearchTopic(topic="研究主题"),
        ])

        state = ResearchState(
            messages=[HumanMessage(content="test")],
            research_topic="",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        await clarify_topic(state, make_config("test-clarify-3"))

        # Verify _emit was called with verification event
        emit_calls = mock_emit.call_args_list
        status_calls = [c for c in emit_calls if c[0][1].get("type") == "status"]
        verified_calls = [c for c in status_calls if c[0][1].get("event") == "verified"]
        assert len(verified_calls) >= 1


# --------------------------------------------------------------------------
# plan_search tests
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPlanSearchIntegration:
    """Tests for plan_search node with mocked LLM."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_returns_search_queries(self, mock_get_llm, mock_emit):
        """plan_search extracts queries from research topic."""
        mock_get_llm.return_value = mock_llm_model(
            SearchPlan(queries=["AI impact jobs 2024", "AI automation software developers"])
        )

        state = ResearchState(
            messages=[HumanMessage(content="AI 对工作的影响")],
            research_topic="AI 对软件工程师就业的影响",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await plan_search(state, make_config("test-plan-1"))

        assert len(result["search_queries"]) == 2
        assert "AI" in result["search_queries"][0] or "AI" in result["search_queries"][1]

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_emits_planning_done_event(self, mock_get_llm, mock_emit):
        """plan_search emits planning_done event with query count."""
        mock_get_llm.return_value = mock_llm_model(
            SearchPlan(queries=["q1", "q2", "q3"])
        )

        state = ResearchState(
            messages=[],
            research_topic="AI 研究",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        await plan_search(state, make_config("test-plan-2"))

        emit_calls = mock_emit.call_args_list
        done_calls = [c for c in emit_calls if c[0][1].get("event") == "planning_done"]
        assert len(done_calls) >= 1
        assert done_calls[0][0][1]["queries"] == ["q1", "q2", "q3"]

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_llm_failure_fallback_to_last_message(self, mock_get_llm, mock_emit):
        """LLM failure falls back to using last message as query."""
        mock_model = MagicMock()
        mock_model.with_structured_output.return_value.with_retry.return_value.ainvoke = AsyncMock(
            side_effect=Exception("LLM down")
        )
        mock_get_llm.return_value = mock_model

        state = ResearchState(
            messages=[HumanMessage(content="fallback query content")],
            research_topic="",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await plan_search(state, make_config("test-plan-3"))

        assert result["search_queries"] == ["fallback query content"]


# --------------------------------------------------------------------------
# synthesize tests
# --------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSynthesizeIntegration:
    """Tests for synthesize node with mocked LLM."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_produces_note(self, mock_get_llm, mock_emit):
        """synthesize converts search results into a note."""
        mock_get_llm.return_value = mock_llm_model(
            Summary(
                summary="研究发现 AI 正在自动化某些编程任务。",
                key_excerpts="source: https://example.com",
            )
        )

        state = ResearchState(
            messages=[],
            research_topic="AI 对软件工作的影响",
            search_results=[
                {
                    "query": "AI jobs",
                    "title": "AI and Software Jobs",
                    "url": "https://example.com",
                    "summary": "AI 自动化工件...",
                    "key_excerpts": "",
                }
            ],
            notes=[],
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await synthesize(state, make_config("test-synth-1"))

        assert len(result["notes"]) == 1
        assert "AI" in result["notes"][0]
        assert result["iterations"] == 1

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_empty_results_produces_empty_note(self, mock_get_llm, mock_emit):
        """No search results produces a placeholder note."""
        state = ResearchState(
            messages=[],
            research_topic="AI 研究",
            search_results=[],
            notes=[],
            iterations=2,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await synthesize(state, make_config("test-synth-2"))

        assert len(result["notes"]) == 1
        assert "[Error synthesizing" in result["notes"][0] or "No search results" in result["notes"][0]
        assert result["iterations"] == 3

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_note_appends_not_replaces(self, mock_get_llm, mock_emit):
        """New notes are appended, not replacing existing ones."""
        mock_get_llm.return_value = mock_llm_model(
            Summary(summary="Second iteration note.", key_excerpts="")
        )

        state = ResearchState(
            messages=[],
            research_topic="AI 研究",
            search_results=[{"title": "T", "url": "U", "summary": "S", "key_excerpts": ""}],
            notes=["[Iteration 0] First note."],
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await synthesize(state, make_config("test-synth-3"))

        assert len(result["notes"]) == 2
        assert result["notes"][0] == "[Iteration 0] First note."
        assert "Second iteration" in result["notes"][1]


# --------------------------------------------------------------------------
# should_continue routing tests
# --------------------------------------------------------------------------

class TestShouldContinueRouting:
    """Tests for should_continue routing function."""

    def test_continues_under_max_iterations(self):
        state = ResearchState(
            messages=[],
            iterations=0,
            max_iterations=3,
            research_topic="",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )
        assert should_continue(state) == "execute_search"

    def test_continues_at_last_allowed(self):
        state = ResearchState(
            messages=[],
            iterations=2,
            max_iterations=3,
            research_topic="",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )
        assert should_continue(state) == "execute_search"

    def test_stops_at_max_iterations(self):
        state = ResearchState(
            messages=[],
            iterations=3,
            max_iterations=3,
            research_topic="",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )
        assert should_continue(state) == "generate_report"

    def test_stops_beyond_max_iterations(self):
        state = ResearchState(
            messages=[],
            iterations=10,
            max_iterations=3,
            research_topic="",
            search_queries=[],
            search_results=[],
            notes=[],
            final_report="",
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )
        assert should_continue(state) == "generate_report"


# --------------------------------------------------------------------------
# Graph structure tests
# --------------------------------------------------------------------------

class TestGraphStructure:
    """Tests for graph compilation and structure."""

    def test_graph_has_all_nodes(self):
        graph = build_graph()
        nodes = set(graph.nodes.keys())
        expected = {"__start__", "clarify_topic", "plan_search", "execute_search", "synthesize", "generate_report"}
        assert expected.issubset(nodes)

    def test_graph_compiles(self):
        """build_graph() produces a compilable StateGraph."""
        graph = build_graph()
        assert graph is not None
        # Check it has the expected entry point
        assert "__start__" in graph.nodes
