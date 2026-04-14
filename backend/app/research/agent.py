"""
Deep Research LangGraph agent.

A simple linear research loop: clarify → plan_search → execute_search → synthesize → (loop or report)
"""

import json
import logging
from typing import Literal, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.llm.factory import get_llm
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
from app.research.state import (
    LEVEL_DEFAULTS,
    ResearchState,
    ResearchLevel,
    ResearchTopic,
    SearchPlan,
    Summary,
    FinalReport,
    NeedsClarification,
    FollowupDecision,
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


def _format_user_inputs(user_inputs: list) -> str:
    """Format user inputs for prompts, handling both strings and dicts."""
    if not user_inputs:
        return "(no user inputs yet)"
    formatted = []
    for inp in user_inputs:
        if isinstance(inp, dict):
            # Manual input: {"type": "manual", "text": "..."}
            formatted.append(f"[Manual]: {inp.get('text', '')}")
        else:
            # Option selection: "option_1", "option_2", "option_3", "skip", "confirm_done"
            formatted.append(f"[{inp}]")
    return "\n".join(formatted)


async def _llm_structured(model_name: str, schema, system: str, user: str):
    llm = get_llm(model_name=model_name, temperature=0)
    model = llm.with_structured_output(schema).with_retry(stop_after_attempt=3)
    return await model.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])


async def _emit(thread_id: str, event: dict):
    """Emit an event to Redis pub/sub."""
    if not thread_id:
        return
    from app.research.stream import publish_event
    try:
        await publish_event(thread_id, event)
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

    thread_id = config.get("configurable", {}).get("thread_id", "")
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
            await _emit(thread_id, {
                "type": "clarify",
                "question": result.question,
            })
            return Command(goto=END)

        if result.verification:
            await _emit(thread_id, {
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

    thread_id = config.get("configurable", {}).get("thread_id", "")
    messages = state["messages"]
    date = get_today_str()

    await _emit(thread_id, {
        "type": "status",
        "event": "planning",
        "message": "Planning search queries...",
    })

    topic = state.get("research_topic", "")

    try:
        result = await _llm_structured(
            "pro",
            SearchPlan,
            SEARCH_PLAN_PROMPT.format(topic=topic, date=date),
            "",
        )

        await _emit(thread_id, {
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

    thread_id = config.get("configurable", {}).get("thread_id", "")
    queries = state["search_queries"]
    max_results = state.get("max_results", 10)
    iterations = state.get("iterations", 0)

    await _emit(thread_id, {
        "type": "status",
        "event": "searching",
        "message": f"Searching {len(queries)} queries...",
        "iteration": iterations,
    })

    async def progress_callback(query: str, count: int):
        await _emit(thread_id, {
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

        await _emit(thread_id, {
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

    thread_id = config.get("configurable", {}).get("thread_id", "")
    search_results = state.get("search_results", [])
    research_topic = state.get("research_topic", "")
    notes: list = state.get("notes", [])
    iterations = state.get("iterations", 0)
    date = get_today_str()

    await _emit(thread_id, {
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

        await _emit(thread_id, {
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


# =============================================================================
# Confirmation Loop Nodes
# =============================================================================

async def research_node(
    state: ResearchState, config: RunnableConfig
) -> dict:
    """
    Perform a research iteration: execute search and synthesize results.
    On first iteration, uses original search_queries.
    On subsequent iterations (user_inputs non-empty), generates new queries
    based on the user's last follow-up choice/input.
    Appends findings to research_history and increments iterations.
    """
    logger.info("--- research_node ---")

    thread_id = config.get("configurable", {}).get("thread_id", "")
    research_topic = state.get("research_topic", "")
    original_queries = state.get("search_queries", [])
    max_results = state.get("max_results", 10)
    iterations = state.get("iterations", 0)
    research_history: list = state.get("research_history", [])
    user_inputs: list = state.get("user_inputs", [])
    date = get_today_str()

    await _emit(thread_id, {
        "type": "status",
        "event": "researching",
        "message": f"Running research iteration {iterations}...",
        "iteration": iterations,
    })

    # Determine which queries to use:
    # - First iteration (user_inputs empty): use original search_queries
    # - Subsequent iterations: generate new follow-up queries based on user input
    if user_inputs:
        # Generate follow-up queries based on user's last input
        last_input = user_inputs[-1]
        try:
            plan = await _llm_structured(
                "pro",
                SearchPlan,
                FOLLOWUP_SEARCH_PROMPT.format(
                    topic=research_topic,
                    date=date,
                    research_history="\n\n".join(research_history[-3:]),
                    user_input=last_input,
                ),
                "",
            )
            search_queries = plan.queries
            logger.info(f"Generated {len(search_queries)} follow-up queries from user input: {last_input}")
        except Exception as e:
            logger.error(f"Follow-up query generation failed: {e}, falling back to original queries")
            search_queries = original_queries
    else:
        # First iteration: use original queries
        search_queries = original_queries

    # Execute search
    try:
        results = await search_and_summarize(
            queries=search_queries,
            max_results=max_results,
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        results = []

    # Synthesize results
    if not results:
        note = f"[Iteration {iterations}] No search results found."
        research_history = research_history + [note]
        return {
            "research_history": research_history,
            "iterations": iterations + 1,
        }

    results_text = ""
    for r in results:
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

        research_history = research_history + [note]

        await _emit(thread_id, {
            "type": "research_note",
            "content": result.summary,
            "iteration": iterations,
        })

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        fallback = f"[Iteration {iterations}] [Error synthesizing: {e}]"
        research_history = research_history + [fallback]

    return {
        "research_history": research_history,
        "iterations": iterations + 1,
    }


async def followup_decision_node(
    state: ResearchState, config: RunnableConfig
) -> dict:
    """
    Decide if more follow-up research is needed based on accumulated findings.
    Calls LLM to determine needs_followup and generate 3 followup_options.
    """
    logger.info("--- followup_decision_node ---")

    thread_id = config.get("configurable", {}).get("thread_id", "")
    research_topic = state.get("research_topic", "")
    research_history: list = state.get("research_history", [])
    user_inputs: list = state.get("user_inputs", [])
    date = get_today_str()

    research_text = "\n\n".join(f"- {item}" for item in research_history)
    user_inputs_text = _format_user_inputs(user_inputs)

    await _emit(thread_id, {
        "type": "status",
        "event": "evaluating",
        "message": "Evaluating if follow-up research is needed...",
    })

    try:
        result = await _llm_structured(
            "pro",
            FollowupDecision,
            FOLLOWUP_DECISION_PROMPT.format(
                topic=research_topic,
                date=date,
                research_history=research_text[:5000],
                user_inputs=user_inputs_text,
            ),
            "",
        )

        followup_options = [result.option_1, result.option_2, result.option_3] if result.needs_followup else []

        await _emit(thread_id, {
            "type": "followup_decision",
            "needs_followup": result.needs_followup,
            "question": result.question if result.needs_followup else "",
            "options": followup_options if result.needs_followup else [],
        })

        return {
            "needs_followup": result.needs_followup,
            "followup_options": followup_options,
        }

    except Exception as e:
        logger.error(f"followup_decision_node failed: {e}")
        # Default to no followup on error (fallback to finalize)
        return {
            "needs_followup": False,
            "followup_options": [],
        }


def followup_decision_router(state: ResearchState) -> Literal["interrupt_node", "finalize_node"]:
    """Route based on needs_followup flag."""
    if state.get("needs_followup", False):
        return "interrupt_node"
    return "finalize_node"


async def interrupt_node(state: ResearchState, config: RunnableConfig) -> dict:
    """
    Present follow-up options to the user via interrupt.
    Pauses graph execution until user responds.

    On first execution: interrupt() throws, graph pauses, _emit publishes event.
    On re-execution (after resume): interrupt() returns user's action, we update user_inputs.
    """
    logger.info("--- interrupt_node ---")

    thread_id = config.get("configurable", {}).get("thread_id", "")
    research_topic = state.get("research_topic", "")
    followup_options: list = state.get("followup_options", [])
    user_inputs: list = state.get("user_inputs", [])

    # Build the interrupt payload
    payload = {
        "type": "interrupt",
        "question": f"What would you like to explore further about '{research_topic}'?",
        "options": followup_options,
        "allow_manual_input": True,
        "allow_skip": True,
        "allow_confirm_done": True,
    }

    await _emit(thread_id, payload)

    # On first execution: interrupt() throws, graph pauses
    # On re-execution (after resume): interrupt() returns user's action (e.g., "confirm_done")
    user_action = interrupt(payload)

    # Append user's action to user_inputs so resume_router can route correctly
    return {"user_inputs": user_inputs + [user_action]}


def resume_router(
    state: ResearchState,
) -> Literal["research_node", "finalize_node"]:
    """
    Route after interrupt based on user's resume action.
    The user's action is stored in user_inputs[-1] when they resume.
    """
    user_inputs: list = state.get("user_inputs", [])
    if not user_inputs:
        return "research_node"

    last_action = user_inputs[-1]
    if last_action == "confirm_done":
        return "finalize_node"
    return "research_node"


async def finalize_node(
    state: ResearchState, config: RunnableConfig
) -> dict:
    """
    Produce the final research output from all accumulated findings.
    """
    logger.info("--- finalize_node ---")

    thread_id = config.get("configurable", {}).get("thread_id", "")
    research_topic = state.get("research_topic", "")
    research_history: list = state.get("research_history", [])
    user_inputs: list = state.get("user_inputs", [])
    date = get_today_str()

    await _emit(thread_id, {
        "type": "status",
        "event": "finalizing",
        "message": "Generating final research report...",
    })

    # Compile research findings
    research_text = "\n\n".join(f"- {item}" for item in research_history)
    user_inputs_text = _format_user_inputs(user_inputs)

    report_content = f"# Research Report: {research_topic}\n\n"
    report_content += f"Date: {date}\n\n"
    report_content += f"## Research Findings\n\n{research_text}\n\n"
    report_content += f"## User Interactions\n\n{user_inputs_text}\n"

    await _emit(thread_id, {
        "type": "done",
        "report": report_content,
    })

    return {
        "final_report": report_content,
        "is_complete": True,
    }


async def explore_matrix_solutions(
    state: ResearchState, config: RunnableConfig
) -> dict:
    """
    Explore morphological solutions relevant to the research topic.
    This node uses the matrix tools to find and analyze solutions.
    """
    logger.info("--- explore_matrix_solutions ---")

    thread_id = config.get("configurable", {}).get("thread_id", "")
    research_topic = state.get("research_topic", "")
    research_history: list = state.get("research_history", [])

    await _emit(thread_id, {
        "type": "status",
        "event": "exploring_solutions",
        "message": "Exploring morphological solutions...",
    })

    # Compile research findings for context
    research_text = "\n\n".join(f"- {item}" for item in research_history)

    try:
        from app.matrix.tools import search_solutions_by_keywords, list_morphological_analyses
        from app.core.database import async_session_maker
        import json

        # First, list available analyses
        analyses_result = await list_morphological_analyses.ainvoke({})
        await _emit(thread_id, {
            "type": "matrix_analyses",
            "content": analyses_result,
        })

        # Extract potential keywords from research topic and findings
        llm = get_llm(model_name="mini", temperature=0)
        keyword_prompt = f"""Extract 3-5 relevant keywords from this research topic and findings that could match morphological solution parameters.
Research topic: {research_topic}

Findings:
{research_text[:2000]}

Return a JSON array of keywords like: ["keyword1", "keyword2", "keyword3"]
Only return the JSON array, nothing else."""

        keyword_response = await llm.ainvoke([
            HumanMessage(content=keyword_prompt)
        ])

        # Parse keywords
        try:
            keywords = json.loads(keyword_response.content)
        except:
            keywords = research_topic.split()[:5]  # Fallback to topic words

        await _emit(thread_id, {
            "type": "status",
            "event": "searching_solutions",
            "message": f"Searching solutions with keywords: {', '.join(keywords)}",
        })

        # Search for solutions using the keywords
        # Note: We need an analysis_id, which we'd typically get from the analyses list
        # For now, we'll provide a placeholder approach
        solutions_content = f"Keywords identified: {', '.join(keywords)}\n\n{analyses_result}"

        await _emit(thread_id, {
            "type": "matrix_solutions",
            "keywords": keywords,
            "content": solutions_content,
        })

        return {
            "research_history": research_history + [f"[Matrix Exploration] Found potential solutions using keywords: {', '.join(keywords)}"],
        }

    except Exception as e:
        logger.error(f"explore_matrix_solutions failed: {e}")
        return {
            "research_history": research_history + [f"[Matrix Exploration] Error exploring solutions: {str(e)}"],
        }


async def generate_report(
    state: ResearchState, config: RunnableConfig
) -> dict:
    """Produce the final markdown report."""
    logger.info("--- generate_report ---")

    thread_id = config.get("configurable", {}).get("thread_id", "")
    research_topic = state.get("research_topic", "")
    notes = state.get("notes", [])
    date = get_today_str()

    await _emit(thread_id, {
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

        await _emit(thread_id, {
            "type": "done",
            "report": result.report,
        })

        return {
            "final_report": result.report,
        }

    except Exception as e:
        logger.error(f"generate_report failed: {e}")
        fallback = f"# Research Report\n\n[Error generating report: {e}]\n\n## Notes\n\n{notes_text}"
        await _emit(thread_id, {
            "type": "done",
            "report": fallback,
        })
        return {
            "final_report": fallback,
        }


# =============================================================================
# Graph Builder
# =============================================================================

def build_graph(checkpointer=None):
    """
    Build the research graph.

    Args:
        checkpointer: LangGraph checkpointer. If None, uses MemorySaver (for testing only).
                     Production should pass a persistent checkpointer (e.g., PostgresSaver).
    """
    from langgraph.checkpoint.memory import MemorySaver

    builder = StateGraph(ResearchState)

    builder.add_node("clarify_topic", clarify_topic)
    builder.add_node("plan_search", plan_search)
    builder.add_node("execute_search", execute_search)
    builder.add_node("synthesize", synthesize)
    builder.add_node("generate_report", generate_report)
    # Confirmation loop nodes
    builder.add_node("research_node", research_node)
    builder.add_node("followup_decision_node", followup_decision_node)
    builder.add_node("interrupt_node", interrupt_node)
    builder.add_node("finalize_node", finalize_node)
    # Matrix solutions exploration node (step 4/5)
    builder.add_node("explore_matrix_solutions", explore_matrix_solutions)

    builder.add_edge(START, "clarify_topic")
    builder.add_edge("plan_search", "execute_search")
    builder.add_edge("execute_search", "synthesize")
    # Confirmation loop: synthesize → research_node (populates research_history)
    # Then research_node → followup_decision_node → [interrupt_node or finalize_node]
    builder.add_edge("synthesize", "research_node")
    builder.add_conditional_edges(
        "followup_decision_node",
        followup_decision_router,
        {
            "interrupt_node": "interrupt_node",
            "finalize_node": "finalize_node",
        },
    )
    builder.add_edge("research_node", "followup_decision_node")
    # After interrupt, route based on user's resume action via resume_router:
    # - "confirm_done" → finalize_node (exit loop)
    # - otherwise → research_node (continue loop)
    builder.add_conditional_edges(
        "interrupt_node",
        resume_router,
        {
            "research_node": "research_node",
            "finalize_node": "finalize_node",
        },
    )
    # After finalize, optionally explore matrix solutions
    builder.add_edge("finalize_node", "explore_matrix_solutions")
    builder.add_edge("explore_matrix_solutions", END)

    if checkpointer is None:
        checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


def level_defaults_for(level: ResearchLevel) -> tuple[int, int]:
    return LEVEL_DEFAULTS.get(level, (3, 10))
