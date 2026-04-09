"""
Deep Research LangGraph agent.

A simple linear research loop: clarify → plan_search → execute_search → synthesize → (loop or report)
"""

import json
import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.llm.factory import get_llm
from app.research.prompts import (
    CLARIFY_PROMPT,
    REPORT_PROMPT,
    RESEARCH_TOPIC_PROMPT,
    SEARCH_PLAN_PROMPT,
    SYNTHESIZE_PROMPT,
)
from app.research.state import (
    LEVEL_DEFAULTS,
    ResearchState,
    ResearchLevel,
    ResearchTopic,
    SearchPlan,
    Summary,
    FinalReport,
    NeedsClarification,
)
from app.research.tools import search_and_summarize

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================

def get_today_str() -> str:
    from datetime import datetime
    now = datetime.now()
    return f"{now:%a} {now:%b} {now.day}, {now:%Y}"


async def _llm_structured(model_name: str, schema, system: str, user: str):
    llm = get_llm(model_name=model_name, temperature=0)
    model = llm.with_structured_output(schema).with_retry(stop_after_attempt=3)
    return await model.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])


async def _emit(task_id: str, event: dict):
    """Emit an event to Redis pub/sub."""
    if not task_id:
        return
    from app.research.stream import publish_event
    try:
        await publish_event(task_id, event)
    except Exception:
        pass  # Non-critical



# =============================================================================
# Graph Nodes
# =============================================================================

async def clarify_topic(
    state: ResearchState, config: RunnableConfig
) -> Command[Literal["plan_search", "__end__"]]:
    """Analyze user input, ask clarifying questions if needed, then derive research topic."""
    logger.info("--- clarify_topic ---")

    task_id = config.get("configurable", {}).get("task_id", "")
    messages = state["messages"]
    date = get_today_str()
    updates: dict = {}

    try:
        result = await _llm_structured(
            "pro",
            NeedsClarification,
            CLARIFY_PROMPT.format(messages=get_buffer_string(messages), date=date),
            "",
        )

        if result.need_clarification:
            await _emit(task_id, {
                "type": "clarify",
                "question": result.question,
            })
            return Command(goto=END)

        if result.verification:
            await _emit(task_id, {
                "type": "status",
                "event": "verified",
                "message": result.verification,
            })

    except Exception as e:
        logger.error(f"clarify_topic failed: {e}")

    # Derive research topic from messages
    try:
        topic_result = await _llm_structured(
            "pro",
            ResearchTopic,
            RESEARCH_TOPIC_PROMPT.format(
                message=get_buffer_string(messages),
                date=date,
            ),
            "",
        )
        updates["research_topic"] = topic_result.topic
    except Exception as e:
        logger.error(f"Failed to derive research topic: {e}")
        updates["research_topic"] = get_buffer_string(messages)

    return Command(goto="plan_search", update=updates)


async def plan_search(
    state: ResearchState, config: RunnableConfig
) -> dict:
    """Generate search queries from the research topic."""
    logger.info("--- plan_search ---")

    task_id = config.get("configurable", {}).get("task_id", "")
    messages = state["messages"]
    date = get_today_str()

    await _emit(task_id, {
        "type": "status",
        "event": "planning",
        "message": "Planning search queries...",
    })

    topic_text = get_buffer_string(messages)

    try:
        result = await _llm_structured(
            "pro",
            SearchPlan,
            RESEARCH_TOPIC_PROMPT.format(message=topic_text, date=date),
            "",
        )

        await _emit(task_id, {
            "type": "status",
            "event": "planning_done",
            "message": f"Generated {len(result.queries)} search queries",
            "queries": result.queries,
        })

        return {
            "search_queries": result.queries,
        }

    except Exception as e:
        logger.error(f"plan_search failed: {e}")
        last_msg = messages[-1].content if messages else "research"
        return {
            "search_queries": [last_msg],
        }


async def execute_search(
    state: ResearchState, config: RunnableConfig
) -> dict:
    """Run web searches and summarize results."""
    logger.info("--- execute_search ---")

    task_id = config.get("configurable", {}).get("task_id", "")
    queries = state["search_queries"]
    max_results = state.get("max_results", 10)
    iterations = state.get("iterations", 0)

    await _emit(task_id, {
        "type": "status",
        "event": "searching",
        "message": f"Searching {len(queries)} queries...",
        "iteration": iterations,
    })

    async def progress_callback(query: str, count: int):
        await _emit(task_id, {
            "type": "search_progress",
            "query": query,
            "result_count": count,
            "iteration": iterations,
        })

    try:
        results = await search_and_summarize(
            queries=queries,
            max_results=max_results,
            progress_callback=progress_callback,
        )

        await _emit(task_id, {
            "type": "status",
            "event": "search_done",
            "message": f"Found {len(results)} results",
            "iteration": iterations,
        })

        return {
            "search_results": results,
        }

    except Exception as e:
        logger.error(f"execute_search failed: {e}")
        return {
            "search_results": [],
        }


async def synthesize(
    state: ResearchState, config: RunnableConfig
) -> dict:
    """Compress search results into notes."""
    logger.info("--- synthesize ---")

    task_id = config.get("configurable", {}).get("task_id", "")
    search_results = state.get("search_results", [])
    research_topic = state.get("research_topic", "")
    notes: list = state.get("notes", [])
    iterations = state.get("iterations", 0)
    date = get_today_str()

    await _emit(task_id, {
        "type": "status",
        "event": "synthesizing",
        "message": "Synthesizing findings...",
        "iteration": iterations,
    })

    if not search_results:
        empty_note = f"[Iteration {iterations}] No search results found."
        notes = notes + [empty_note]
        return {"notes": notes, "iterations": iterations + 1}

    results_text = ""
    for r in search_results:
        results_text += f"\n--- Source: {r['title']} ({r['url']}) ---\n"
        results_text += f"Summary: {r.get('summary', '')}\n"
        results_text += f"Key Excerpts: {r.get('key_excerpts', '')}\n"

    try:
        result = await _llm_structured(
            "pro",
            Summary,
            SYNTHESIZE_PROMPT.format(
                topic=research_topic,
                date=date,
                results=results_text[:6000],
            ),
            "",
        )

        note = f"[Iteration {iterations}] {result.summary}"
        if result.key_excerpts:
            note += f"\n\nKey excerpts:\n{result.key_excerpts}"

        notes = notes + [note]

        await _emit(task_id, {
            "type": "note",
            "content": result.summary,
            "iteration": iterations,
        })

        return {
            "notes": notes,
            "iterations": iterations + 1,
        }

    except Exception as e:
        logger.error(f"synthesize failed: {e}")
        fallback = f"[Iteration {iterations}] [Error synthesizing: {e}]"
        return {
            "notes": notes + [fallback],
            "iterations": iterations + 1,
        }


def should_continue(state: ResearchState) -> Literal["execute_search", "generate_report"]:
    """Route: loop back to search or exit to report."""
    iterations = state.get("iterations", 0)
    max_iterations = state.get("max_iterations", 3)

    if iterations < max_iterations:
        return "execute_search"
    return "generate_report"


async def generate_report(
    state: ResearchState, config: RunnableConfig
) -> dict:
    """Produce the final markdown report."""
    logger.info("--- generate_report ---")

    task_id = config.get("configurable", {}).get("task_id", "")
    research_topic = state.get("research_topic", "")
    notes = state.get("notes", [])
    date = get_today_str()

    await _emit(task_id, {
        "type": "status",
        "event": "reporting",
        "message": "Generating final report...",
    })

    notes_text = "\n\n".join(f"- {note}" for note in notes)

    try:
        result = await _llm_structured(
            "pro",
            FinalReport,
            REPORT_PROMPT.format(
                topic=research_topic,
                date=date,
                num_notes=len(notes),
                notes=notes_text[:8000],
            ),
            "",
        )

        await _emit(task_id, {
            "type": "done",
            "report": result.report,
        })

        return {
            "final_report": result.report,
        }

    except Exception as e:
        logger.error(f"generate_report failed: {e}")
        fallback = f"# Research Report\n\n[Error generating report: {e}]\n\n## Notes\n\n{notes_text}"
        await _emit(task_id, {
            "type": "done",
            "report": fallback,
        })
        return {
            "final_report": fallback,
        }


# =============================================================================
# Graph Builder
# =============================================================================

def build_graph():
    builder = StateGraph(ResearchState)

    builder.add_node("clarify_topic", clarify_topic)
    builder.add_node("plan_search", plan_search)
    builder.add_node("execute_search", execute_search)
    builder.add_node("synthesize", synthesize)
    builder.add_node("generate_report", generate_report)

    builder.add_edge(START, "clarify_topic")
    builder.add_edge("plan_search", "execute_search")
    builder.add_edge("execute_search", "synthesize")
    builder.add_conditional_edges(
        "synthesize",
        should_continue,
        {
            "execute_search": "execute_search",
            "generate_report": "generate_report",
        },
    )
    builder.add_edge("generate_report", END)

    return builder.compile()


def level_defaults_for(level: ResearchLevel) -> tuple[int, int]:
    return LEVEL_DEFAULTS.get(level, (3, 10))
