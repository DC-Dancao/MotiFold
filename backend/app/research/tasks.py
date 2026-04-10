"""
Celery tasks for Deep Research.
"""

import asyncio
import json
import logging

from langchain_core.messages import HumanMessage

from app.core.database import AsyncSessionLocal
from app.research.agent import build_graph, level_defaults_for
from app.research.models import ResearchReport
from app.research.state import ResearchLevel
from app.research.stream import clear_processing_flag, publish_event, set_processing_flag
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="process_research")
def process_research(
    task_id: str,
    query: str,
    level: str,
    max_iterations: int | None,
    max_results: int | None,
    user_id: int | None = None,
):
    """
    Run the deep research agent for a given query.
    Publishes progress events to Redis pub/sub.
    Saves result to database on completion.
    """
    async def _run():
        await set_processing_flag(task_id)

        # Determine parameters
        research_level = ResearchLevel(level)
        default_iters, default_results = level_defaults_for(research_level)
        effective_iters = max_iterations if max_iterations is not None else default_iters
        effective_res = max_results if max_results is not None else default_results

        await publish_event(task_id, {
            "type": "status",
            "event": "start",
            "message": f"Starting {level} research (max_iter={effective_iters})...",
        })

        # Build graph
        graph = build_graph()

        # Initial state
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "research_topic": "",
            "search_queries": [],
            "search_results": [],
            "notes": [],
            "final_report": "",
            "iterations": 0,
            "max_iterations": effective_iters,
            "max_results": effective_res,
            "research_level": research_level,
        }

        # Pass task_id through config so nodes can emit SSE events
        config = {
            "configurable": {"thread_id": f"research_{task_id}", "task_id": task_id},
        }

        final_state = None
        try:
            async for event in graph.astream(initial_state, config):
                # Track the final state from the last event
                final_state = event
        except Exception as e:
            logger.error(f"Research failed for task {task_id}: {e}")
            await publish_event(task_id, {
                "type": "error",
                "message": str(e),
            })

        # Extract data from final state
        research_topic = ""
        final_report = ""
        notes = []
        queries = []

        if final_state:
            for node_data in final_state.values():
                if isinstance(node_data, dict):
                    if node_data.get("research_topic"):
                        research_topic = node_data["research_topic"]
                    if node_data.get("final_report"):
                        final_report = node_data["final_report"]
                    if node_data.get("notes"):
                        notes = node_data["notes"]
                    if node_data.get("search_queries"):
                        queries = node_data["search_queries"]

        # Save to database on completion
        saved_report_id = None
        if final_report:
            try:
                async with AsyncSessionLocal() as db:
                    report = ResearchReport(
                        user_id=user_id,
                        query=query,
                        research_topic=research_topic,
                        report=final_report,
                        notes_json=json.dumps(notes),
                        queries_json=json.dumps(queries),
                        level=level,
                        iterations=effective_iters,
                    )
                    db.add(report)
                    await db.commit()
                    await db.refresh(report)
                    saved_report_id = report.id
                    logger.info(f"Saved research report for task {task_id}, report_id={report.id}")
            except Exception as e:
                logger.error(f"Failed to save research report: {e}")

        # Always run cleanup and publish done event
        await clear_processing_flag(task_id)
        await publish_event(task_id, {
            "type": "[DONE]",
            "report_id": saved_report_id,
            "report": final_report,
        })

    asyncio.run(_run())
