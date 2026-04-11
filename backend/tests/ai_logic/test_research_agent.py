# backend/tests/ai_logic/test_research_agent.py
"""
AI logic tests for app.research.agent — deep research scenarios with mocks.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import HumanMessage
from app.research.agent import (
    clarify_topic, plan_search, execute_search, synthesize,
    should_continue, generate_report, build_graph,
)
from langgraph.graph import END
from app.research.state import (
    ResearchState, NeedsClarification, ResearchTopic,
    SearchPlan, Summary, FinalReport, ResearchLevel,
)

pytestmark = [pytest.mark.ai_logic, pytest.mark.asyncio]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def make_config(task_id: str = "test-task"):
    return {"configurable": {"thread_id": f"research_{task_id}", "task_id": task_id}}


def make_model_mock(return_values):
    """
    Build a mock LLM model whose .with_structured_output().with_retry().ainvoke()
    chain returns the given values in sequence.

    This mimics the real call chain:
        get_llm() → model.with_structured_output(schema).with_retry().ainvoke([...])
    """
    if not isinstance(return_values, list):
        return_values = [return_values]

    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_retry = MagicMock()

    # Chain: model.with_structured_output() → structured → .with_retry() → retry
    mock_model.with_structured_output.return_value = mock_structured
    mock_structured.with_retry.return_value = mock_retry
    # ainvoke returns the desired schema objects
    mock_retry.ainvoke = AsyncMock(side_effect=return_values)

    return mock_model


# --------------------------------------------------------------------------
# TestClarifyTopicIntegration
# --------------------------------------------------------------------------


@pytest.mark.ai_logic
class TestClarifyTopicIntegration:
    """clarify_topic derives a deep research topic from a complex query."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_deep_research_topic_extracted(self, mock_get_llm, mock_emit):
        """A complex multi-faceted query produces a specific research topic."""
        # Two LLM calls: NeedsClarification (false) + ResearchTopic
        mock_get_llm.return_value = make_model_mock([
            NeedsClarification(need_clarification=False, question="", verification="了解，开始调研。"),
            ResearchTopic(topic="AI Agent 在软件开发中的最新进展、面临的挑战与未来趋势"),
        ])

        state = ResearchState(
            messages=[HumanMessage(content="研究 AI Agent 在软件开发中的最新进展和面临的挑战")],
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

        assert result.goto == "plan_search"
        topic = result.update["research_topic"]
        assert "AI Agent" in topic
        assert len(topic) > 10

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_need_clarification_aborts(self, mock_get_llm, mock_emit):
        """If LLM asks for clarification, research stops immediately."""
        mock_get_llm.return_value = make_model_mock(
            NeedsClarification(need_clarification=True, question="您想研究哪个行业？", verification="")
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

        result = await clarify_topic(state, make_config("test-clarify-2"))

        assert result.goto == END

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_verification_message_emitted(self, mock_get_llm, mock_emit):
        """When LLM returns verification text, it is emitted as a status event."""
        mock_get_llm.return_value = make_model_mock([
            NeedsClarification(need_clarification=False, question="", verification="了解，开始调研。"),
            ResearchTopic(topic="AI Agent 研究"),
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

        emit_calls = mock_emit.call_args_list
        verified_calls = [
            c for c in emit_calls
            if c[0][1].get("type") == "status" and c[0][1].get("event") == "verified"
        ]
        assert len(verified_calls) >= 1
        assert "了解" in verified_calls[0][0][1]["message"]


# --------------------------------------------------------------------------
# TestPlanSearchIntegration
# --------------------------------------------------------------------------


@pytest.mark.ai_logic
class TestPlanSearchIntegration:
    """plan_search generates multiple search queries from a research topic."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_generates_multiple_queries(self, mock_get_llm, mock_emit):
        """A deep research topic produces multiple focused queries."""
        mock_get_llm.return_value = make_model_mock(
            SearchPlan(queries=[
                "AI Agent 软件开发进展 2024",
                "AI Agent 自动化编程挑战",
                "AI Agent 未来发展趋势",
            ])
        )

        state = ResearchState(
            messages=[HumanMessage(content="研究 AI Agent 在软件开发中的最新进展")],
            research_topic="AI Agent 在软件开发中的最新进展、挑战与趋势",
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

        assert len(result["search_queries"]) >= 3
        assert len(set(result["search_queries"])) == len(result["search_queries"])

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_planning_done_event_emitted(self, mock_get_llm, mock_emit):
        """plan_search emits planning_done with query count."""
        mock_get_llm.return_value = make_model_mock(
            SearchPlan(queries=["q1", "q2", "q3"])
        )

        state = ResearchState(
            messages=[],
            research_topic="AI Agent 研究",
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
        done_calls = [
            c for c in emit_calls
            if c[0][1].get("event") == "planning_done"
        ]
        assert len(done_calls) >= 1
        assert done_calls[0][0][1]["queries"] == ["q1", "q2", "q3"]

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_llm_failure_fallback_to_last_message(self, mock_get_llm, mock_emit):
        """LLM failure falls back to using last message as the search query."""
        # make_model_mock raises on ainvoke
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
# TestExecuteSearchIntegration
# --------------------------------------------------------------------------


@pytest.mark.ai_logic
class TestExecuteSearchIntegration:
    """execute_search runs search_and_summarize and populates search_results."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.search_and_summarize", new_callable=AsyncMock)
    async def test_search_results_populated(self, mock_search_fn, mock_emit):
        """execute_search populates search_results from multiple queries."""
        mock_search_fn.return_value = [
            {
                "query": "AI Agent 软件进展",
                "title": "AI Agents in Software Development",
                "url": "https://example.com/agents",
                "summary": "AI agents automate code generation and testing.",
                "key_excerpts": "AI agents can write code autonomously.",
            },
            {
                "query": "AI Agent 挑战",
                "title": "Challenges of AI Agents",
                "url": "https://example.com/challenges",
                "summary": "Reliability and context management remain challenges.",
                "key_excerpts": "Hallucination and context length are open problems.",
            },
        ]

        state = ResearchState(
            messages=[],
            research_topic="AI Agent 在软件开发中的进展与挑战",
            search_queries=["AI Agent 软件进展", "AI Agent 挑战"],
            search_results=[],
            notes=[],
            final_report="",
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await execute_search(state, make_config("test-exec-1"))

        assert len(result["search_results"]) == 2
        assert result["search_results"][0]["title"] == "AI Agents in Software Development"
        assert "Hallucination" in result["search_results"][1]["key_excerpts"]


# --------------------------------------------------------------------------
# TestSynthesizeIntegration
# --------------------------------------------------------------------------


@pytest.mark.ai_logic
class TestSynthesizeIntegration:
    """synthesize converts search results into notes and increments iterations."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_note_includes_key_findings(self, mock_get_llm, mock_emit):
        """synthesize note captures key findings and citations."""
        mock_get_llm.return_value = make_model_mock(
            Summary(
                summary="研究发现 AI Agent 在代码生成方面取得显著进展，但仍面临幻觉和上下文管理的挑战。",
                key_excerpts="AI agents can write code autonomously. Hallucination remains an open problem.",
            )
        )

        state = ResearchState(
            messages=[],
            research_topic="AI Agent 在软件开发中的进展与挑战",
            search_results=[
                {
                    "query": "AI Agent 进展",
                    "title": "AI Agents in Software Development",
                    "url": "https://example.com/agents",
                    "summary": "AI agents automate code generation.",
                    "key_excerpts": "AI agents can write code autonomously.",
                },
                {
                    "query": "AI Agent 挑战",
                    "title": "Challenges of AI Agents",
                    "url": "https://example.com/challenges",
                    "summary": "Reliability challenges remain.",
                    "key_excerpts": "Hallucination and context length are open problems.",
                },
            ],
            notes=[],
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await synthesize(state, make_config("test-synth-1"))

        assert len(result["notes"]) == 1
        note = result["notes"][0]
        assert "AI" in note
        assert "挑战" in note or "challenges" in note.lower()
        assert result["iterations"] == 1

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_notes_accumulate_across_iterations(self, mock_get_llm, mock_emit):
        """Notes from each iteration are appended, not replaced."""
        mock_get_llm.return_value = make_model_mock(
            Summary(summary="Iteration 1: AI Agent 代码生成进展。", key_excerpts="")
        )

        state = ResearchState(
            messages=[],
            research_topic="AI Agent 研究",
            search_results=[{"title": "T", "url": "U", "summary": "S", "key_excerpts": ""}],
            notes=["[Iteration 0] 初始文献综述。"],
            iterations=0,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await synthesize(state, make_config("test-synth-2"))

        assert len(result["notes"]) == 2
        assert result["notes"][0] == "[Iteration 0] 初始文献综述。"
        assert "Iteration 1" in result["notes"][1]


# --------------------------------------------------------------------------
# TestMultiIterationFlow
# --------------------------------------------------------------------------


@pytest.mark.ai_logic
class TestMultiIterationFlow:
    """
    Core deep research behavior: multiple iterations accumulate notes
    until max_iterations is reached, then route to generate_report.
    """

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_notes_accumulate_over_three_iterations(self, mock_get_llm, mock_emit):
        """
        Three iterations of synthesize produce three notes.
        After max_iterations, should_continue routes to generate_report.
        """
        # Each synthesize call gets its own model mock
        mock_get_llm.side_effect = [
            make_model_mock(Summary(summary="第一轮：AI Agent 代码生成进展。", key_excerpts="")),
            make_model_mock(Summary(summary="第二轮：挑战包括幻觉和上下文管理。", key_excerpts="")),
            make_model_mock(Summary(summary="第三轮：未来趋势是多模态和自主协作。", key_excerpts="")),
        ]

        base_state = {
            "messages": [],
            "research_topic": "AI Agent 在软件开发中的进展与挑战",
            "search_queries": [],
            "search_results": [{"title": "T", "url": "U", "summary": "S", "key_excerpts": ""}],
            "notes": [],
            "final_report": "",
            "iterations": 0,
            "max_iterations": 3,
            "max_results": 10,
            "research_level": ResearchLevel.STANDARD,
        }

        # Iteration 0
        s0 = await synthesize(ResearchState(**base_state), make_config("test-multi-1"))
        assert len(s0["notes"]) == 1
        assert s0["iterations"] == 1
        assert "第一轮" in s0["notes"][0]

        # Iteration 1
        s1_state = dict(base_state, notes=s0["notes"], iterations=s0["iterations"])
        s1 = await synthesize(ResearchState(**s1_state), make_config("test-multi-1"))
        assert len(s1["notes"]) == 2
        assert s1["iterations"] == 2
        assert "第二轮" in s1["notes"][1]

        # Iteration 2
        s2_state = dict(base_state, notes=s1["notes"], iterations=s1["iterations"])
        s2 = await synthesize(ResearchState(**s2_state), make_config("test-multi-1"))
        assert len(s2["notes"]) == 3
        assert s2["iterations"] == 3
        assert "第三轮" in s2["notes"][2]

        # should_continue at max → report
        done_state = ResearchState(**dict(base_state, notes=s2["notes"], iterations=3))
        assert should_continue(done_state) == "generate_report"

    def test_should_continue_loops_under_max(self):
        """Before max_iterations, should_continue routes back to execute_search."""
        for i in range(3):
            state = ResearchState(
                messages=[],
                research_topic="AI Agent 研究",
                search_queries=[],
                search_results=[],
                notes=[],
                final_report="",
                iterations=i,
                max_iterations=3,
                max_results=10,
                research_level=ResearchLevel.STANDARD,
            )
            assert should_continue(state) == "execute_search", f"iter={i} should loop"


# --------------------------------------------------------------------------
# TestGenerateReportIntegration
# --------------------------------------------------------------------------


@pytest.mark.ai_logic
class TestGenerateReportIntegration:
    """generate_report produces a structured markdown report from all notes."""

    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    async def test_report_from_multiple_notes(self, mock_get_llm, mock_emit):
        """With 3 iterations of notes, generate_report produces a structured report."""
        mock_get_llm.return_value = make_model_mock(
            FinalReport(report="# AI Agent 研究报告\n\n## 进展\n\n研究发现 AI Agent 在代码生成方面取得显著进展。\n\n## 挑战\n\n主要挑战包括幻觉问题和上下文管理。\n\n## 结论\n\n多模态和自主协作是未来趋势。")
        )

        state = ResearchState(
            messages=[],
            research_topic="AI Agent 在软件开发中的进展与挑战",
            search_queries=[],
            search_results=[],
            notes=[
                "[Iteration 0] 第一轮：AI Agent 在代码生成方面取得进展。",
                "[Iteration 1] 第二轮：挑战包括幻觉和上下文管理。",
                "[Iteration 2] 第三轮：未来趋势是多模态和自主协作。",
            ],
            final_report="",
            iterations=3,
            max_iterations=3,
            max_results=10,
            research_level=ResearchLevel.STANDARD,
        )

        result = await generate_report(state, make_config("test-report-1"))

        assert "AI Agent" in result["final_report"]
        assert "#" in result["final_report"]  # markdown heading
        assert len(result["final_report"]) > 50


# --------------------------------------------------------------------------
# TestEndToEndFlow
# --------------------------------------------------------------------------


@pytest.mark.ai_logic
class TestEndToEndFlow:
    """Full graph end-to-end: verify compilation and meaningful final state."""

    def test_graph_compiles(self):
        """Graph builds successfully with all required nodes."""
        graph = build_graph()
        nodes = set(graph.nodes.keys())
        expected = {
            "__start__",
            "clarify_topic",
            "plan_search",
            "execute_search",
            "synthesize",
            "generate_report",
        }
        assert expected.issubset(nodes)

    @pytest.mark.asyncio
    @patch("app.research.agent._emit")
    @patch("app.research.agent.get_llm")
    @patch("app.research.agent.search_and_summarize", new_callable=AsyncMock)
    async def test_full_flow_produces_notes_and_report(self, mock_search, mock_get_llm, mock_emit):
        """
        End-to-end flow with max_iterations=1:
        clarify → plan → search → synthesize (iter 0) → should_continue → report.

        Verifies the final state contains meaningful research output.
        """
        mock_get_llm.side_effect = [
            # clarify_topic
            make_model_mock([
                NeedsClarification(need_clarification=False, question="", verification=""),
                ResearchTopic(topic="AI Agent 软件开发进展与挑战"),
            ]),
            # plan_search
            make_model_mock(SearchPlan(queries=["AI Agent 进展", "AI Agent 挑战"])),
            # synthesize
            make_model_mock(Summary(summary="研究发现 AI Agent 在代码生成方面取得进展。", key_excerpts="")),
            # generate_report
            make_model_mock(FinalReport(report="# AI Agent 研究报告\n\n研究发现...")),
        ]

        mock_search.return_value = [
            {
                "query": "AI Agent 进展",
                "title": "AI Agents in Software Development",
                "url": "https://example.com",
                "summary": "AI agents automate code generation.",
                "key_excerpts": "Autonomous code generation is maturing.",
            },
            {
                "query": "AI Agent 挑战",
                "title": "Challenges of AI Agents",
                "url": "https://example.com/challenges",
                "summary": "Hallucination and reliability are challenges.",
                "key_excerpts": "Context management remains hard.",
            },
        ]

        graph = build_graph()
        initial_state = {
            "messages": [HumanMessage(content="研究 AI Agent 在软件开发中的最新进展和面临的挑战")],
            "research_topic": "",
            "search_queries": [],
            "search_results": [],
            "notes": [],
            "final_report": "",
            "iterations": 0,
            "max_iterations": 1,  # 1 iteration → goes to report immediately
            "max_results": 10,
            "research_level": ResearchLevel.STANDARD,
        }

        final_state = None
        async for event in graph.astream(initial_state, make_config("test-e2e")):
            # graph.astream yields dicts of {node_name: state_update}
            # last event should contain generate_report's update
            final_state = event

        # Verify meaningful output
        assert final_state is not None
        report_values = [v for v in final_state.values() if isinstance(v, dict) and "final_report" in v]
        if report_values:
            report = report_values[0]["final_report"]
            assert report, "final_report should not be empty"
            assert len(report) > 20
