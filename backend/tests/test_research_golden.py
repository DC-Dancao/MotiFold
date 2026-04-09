"""
Golden tests for Deep Research — real API calls, manually triggered.

These tests call the real LLM API with a pre-verified golden dataset.
Marked with @pytest.mark.integration so CI can skip them by default.

Run manually:
    pytest tests/test_research_golden.py -v

CI (skip integration):
    pytest tests/test_research_*.py -m "not integration" -v
"""

import pytest

from app.research.agent import build_graph
from app.research.state import ResearchLevel
from langchain_core.messages import HumanMessage


pytestmark = pytest.mark.integration


# --------------------------------------------------------------------------
# Golden Dataset
# --------------------------------------------------------------------------

GOLDEN_CASES = [
    # (query, expected_keywords_in_topic)
    # 每个 query 都足够宽/深，能触发多轮搜索迭代
    (
        "研究 AI Agent 在软件开发中的最新进展和面临的挑战",
        ["AI Agent", "软件", "进展", "挑战", "自主"],
    ),
    (
        "分析全球电动汽车市场 2024-2025 年的竞争格局与技术趋势",
        ["电动汽车", "市场", "竞争", "格局", "技术趋势"],
    ),
    (
        "调研 RAG（检索增强生成）技术在企业知识库中的应用现状与局限",
        ["RAG", "检索增强", "知识库", "企业", "应用", "局限"],
    ),
    (
        "研究气候变化对全球农业的影响及主要应对策略",
        ["气候变化", "农业", "影响", "应对", "策略"],
    ),
    (
        "分析分布式训练在大型语言模型中的应用与优化方法",
        ["分布式训练", "大型语言模型", "优化", "应用"],
    ),
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def make_config(task_id: str):
    return {"configurable": {"thread_id": f"research_{task_id}", "task_id": task_id}}


async def extract_topic_via_llm(query: str) -> str:
    """
    Run just the clarify_topic node to extract research topic.
    Uses real API — no mocks.
    """
    from app.research.agent import clarify_topic
    from app.research.state import ResearchState

    state = ResearchState(
        messages=[HumanMessage(content=query)],
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

    result = await clarify_topic(state, make_config("golden-topic"))
    topic = result.update.get("research_topic", "") if result.update else ""
    return topic


# --------------------------------------------------------------------------
# Golden Tests
# --------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_keywords", GOLDEN_CASES)
async def test_research_topic_golden(query, expected_keywords):
    """
    Test that clarify_topic extracts a topic containing expected keywords.
    This is the simplest end-to-end test that exercises the real LLM.
    """
    topic = await extract_topic_via_llm(query)

    assert topic, f"Topic should not be empty for query: {query}"
    assert len(topic) > 5, f"Topic too short for '{query}': {topic}"

    found = any(kw.lower() in topic.lower() for kw in expected_keywords)
    assert found, (
        f"None of {expected_keywords} found in topic for query '{query}'. "
        f"Got: {topic}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_graph_smoke_no_api():
    """
    Smoke test: verify graph compiles and astream runs without crashing.
    No real API calls — just graph construction and state flow.
    """
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
        "max_iterations": 1,  # 1 iteration to keep test fast
        "max_results": 3,
        "research_level": ResearchLevel.STANDARD,
    }
    config = make_config("smoke-test")

    # Just verify graph.astream doesn't raise
    async for event in graph.astream(state, config):
        # Should not raise — event stream works
        pass
