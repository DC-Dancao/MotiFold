# backend/tests/ai_quality/test_research_golden.py
"""
Golden dataset tests for deep research.
Real API calls with semantic keyword validation.
"""
import pytest
from langchain_core.messages import HumanMessage
from app.research.agent import build_graph, clarify_topic
from app.research.state import ResearchState, ResearchLevel
from tests.fixtures.golden_loader import load_golden_cases

pytestmark = [pytest.mark.ai_quality, pytest.mark.asyncio]


def make_config(task_id: str):
    return {"configurable": {"thread_id": f"research_{task_id}", "task_id": task_id}}


@pytest.mark.parametrize("case", load_golden_cases("research", "clarify_topic"))
async def test_clarify_topic_golden(case):
    """
    Test that clarify_topic extracts a topic containing expected keywords.
    Uses golden dataset from JSON for semantic validation.
    """
    state = ResearchState(
        messages=[HumanMessage(content=case["query"])],
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

    result = await clarify_topic(state, make_config(f"golden-{case['id']}"))
    topic = result.update.get("research_topic", "") if result.update else ""

    assert topic, f"Topic should not be empty for query: {case['query']}"
    assert len(topic) >= case.get("expected_min_length", 5), \
        f"Topic too short for '{case['query']}': {topic}"
    assert len(topic) <= case.get("expected_max_length", 500), \
        f"Topic too long for '{case['query']}': {topic}"

    found = any(kw.lower() in topic.lower() for kw in case["expected_keywords"])
    assert found, (
        f"None of {case['expected_keywords']} found in topic for query '{case['query']}'. "
        f"Got: {topic}"
    )


async def test_graph_smoke_no_api():
    """Smoke test: verify graph compiles without API calls."""
    graph = build_graph()
    assert graph is not None

    state = {
        "messages": [HumanMessage(content="test")],
        "research_topic": "",
        "search_queries": [],
        "search_results": [],
        "notes": [],
        "final_report": "",
        "iterations": 0,
        "max_iterations": 1,
        "max_results": 3,
        "research_level": ResearchLevel.STANDARD,
    }
    config = make_config("smoke-test")

    async for event in graph.astream(state, config):
        pass
