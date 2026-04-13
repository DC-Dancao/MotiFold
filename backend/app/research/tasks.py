"""
Celery tasks for Deep Research.
"""

import asyncio
import json
import logging

import redis
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.async_bridge import run_async_from_sync
from app.llm.checkpointer import SYNC_DB_URL, ensure_checkpointer_ready
from app.research.agent import build_graph, level_defaults_for
from app.research.models import ResearchReport
from app.research.state import ResearchLevel
from app.research.stream import clear_processing_flag, publish_event, set_processing_flag, save_research_state
from app.worker import celery_app
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_postgres_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    await ensure_checkpointer_ready()
    async with AsyncPostgresSaver.from_conn_string(SYNC_DB_URL) as checkpointer:
        yield checkpointer


@celery_app.task(name="process_research")
def process_research(
    task_id: str,
    query: str,
    level: str,
    max_iterations: int | None,
    max_results: int | None,
    user_id: int | None = None,
    org_schema: str | None = None,
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
        await save_research_state(task_id, {
            "status": "running",
            "message": f"Starting {level} research (max_iter={effective_iters})...",
            "progress": 0.0,
            "iteration": None,
            "research_topic": "",
            "notes": [],
            "queries": [],
            "level": level,
            "task_id": task_id,
        })

        async with get_postgres_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)

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
            error_msg = None
            try:
                async for event in graph.astream(initial_state, config):
                    # Track the final state from the last event
                    final_state = event
                    # Persist accumulated state to Redis
                    current_topic = ""
                    current_notes = []
                    current_queries = []
                    if final_state:
                        for node_data in final_state.values():
                            if isinstance(node_data, dict):
                                if node_data.get("research_topic"):
                                    current_topic = node_data["research_topic"]
                                if node_data.get("notes"):
                                    current_notes = node_data["notes"]
                                if node_data.get("search_queries"):
                                    current_queries = node_data["search_queries"]
                    await save_research_state(task_id, {
                        "status": "running",
                        "message": "Research in progress",
                        "progress": 0.5,
                        "iteration": None,
                        "research_topic": current_topic,
                        "notes": current_notes,
                        "queries": current_queries,
                        "level": level,
                        "task_id": task_id,
                    })
            except Exception as e:
                logger.error(f"Research failed for task {task_id}: {e}")
                error_msg = str(e)
                await publish_event(task_id, {
                    "type": "error",
                    "message": str(e),
                })
                await save_research_state(task_id, {
                    "status": "error",
                    "message": str(e),
                    "progress": 0.0,
                    "iteration": None,
                    "research_topic": "",
                    "notes": [],
                    "queries": [],
                    "level": level,
                    "task_id": task_id,
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

        # Update existing DB record on completion
        final_status = "done" if final_report else "error"
        saved_report_id = None
        try:
            async with AsyncSessionLocal() as db:
                if org_schema:
                    from sqlalchemy import text
                    await db.execute(text(f'SET LOCAL search_path TO "{org_schema}", public'))
                from sqlalchemy import update, select
                # Update the existing record (created when task started)
                stmt = (
                    update(ResearchReport)
                    .where(ResearchReport.task_id == task_id)
                    .values(
                        status=final_status,
                        research_topic=research_topic,
                        report=final_report,
                        notes_json=json.dumps(notes),
                        queries_json=json.dumps(queries),
                    )
                )
                await db.execute(stmt)
                await db.commit()
                # Fetch the updated report ID
                select_stmt = select(ResearchReport).where(ResearchReport.task_id == task_id)
                result = await db.execute(select_stmt)
                report = result.scalars().first()
                if report:
                    saved_report_id = report.id
                logger.info(f"Updated research report for task {task_id}, status={final_status}")
        except Exception as e:
            logger.error(f"Failed to update research report: {e}")

        # Always run cleanup and publish done event
        await save_research_state(task_id, {
            "status": final_status,
            "message": "Research complete" if final_report else "Research failed",
            "progress": 1.0,
            "iteration": effective_iters,
            "research_topic": research_topic,
            "notes": notes,
            "queries": queries,
            "level": level,
            "task_id": task_id,
        })
        await clear_processing_flag(task_id)
        await publish_event(task_id, {
            "type": "[DONE]",
            "report_id": saved_report_id,
            "report": final_report,
        })

        # Global notification for cross-tab alerts (only on completion)
        if user_id is not None:
            redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            channel = f"user_notifications_{user_id}"
            notification = {
                "type": "research_report",
                "task_type": "research_complete",
                "resource_type": "research_report",
                "resource_id": saved_report_id,
                "result": "success" if final_report else "error",
                "status": "done" if final_report else "error",
                "title": "研究完成" if final_report else "研究失败",
                "message": f"关于「{research_topic[:20]}...」的研究报告已生成" if final_report else f"研究失败: {error_msg}",
                "link": f"/research?report_id={saved_report_id}" if saved_report_id else None,
            }
            redis_client.publish(channel, json.dumps(notification))
            redis_client.close()

    run_async_from_sync(_run())


@celery_app.task(name="process_research_loop")
def process_research_loop(
    task_id: str,
    thread_id: str,
    query: str,
    level: str,
    max_iterations: int | None,
    max_results: int | None,
    user_id: int | None = None,
    org_schema: str | None = None,
):
    """
    Start the research graph for the confirmation loop.
    Runs until interrupt() is called, then exits.
    State is persisted via MemorySaver checkpointer.
    Publishes events to research_stream_{thread_id} for SSE streaming.
    """
    async def _run():
        await set_processing_flag(task_id)

        research_level = ResearchLevel(level)
        default_iters, default_results = level_defaults_for(research_level)
        effective_iters = max_iterations if max_iterations is not None else default_iters
        effective_res = max_results if max_results is not None else default_results

        # Publish to thread_id channel so SSE endpoint can subscribe using thread_id
        await publish_event(thread_id, {
            "type": "status",
            "event": "start",
            "message": f"Starting {level} research (max_iter={effective_iters})...",
        })

        async with get_postgres_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)

            # Initial state - note: uses thread_id as checkpointer key
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
                # Confirmation loop fields
                "needs_followup": False,
                "followup_options": [],
                "user_inputs": [],
                "research_history": [],
                "is_complete": False,
            }

            # Use thread_id as the checkpointer key
            config = {
                "configurable": {"thread_id": thread_id, "task_id": task_id},
            }

            final_state = None
            try:
                # Use ainvoke instead of astream to properly handle interrupts
                # The graph will run until interrupt() is called, then exit
                final_state = await graph.ainvoke(initial_state, config)
            except Exception as e:
                from langgraph.errors import GraphInterrupt
                if isinstance(e, GraphInterrupt):
                    # This is expected - the graph was interrupted
                    # State is already saved in Postgres checkpointer, will be resumed later
                    logger.info(f"Research interrupted for task {task_id}, thread {thread_id}")
                else:
                    logger.error(f"Research failed for task {task_id}: {e}")
                    await publish_event(thread_id, {
                        "type": "error",
                        "message": str(e),
                    })
                    await save_research_state(task_id, {
                        "status": "error",
                        "message": str(e),
                        "progress": 0.0,
                        "iteration": None,
                        "research_topic": "",
                        "notes": [],
                        "queries": [],
                        "level": level,
                        "task_id": task_id,
                    })
                    await clear_processing_flag(task_id)
                    return

        # If we get here, the graph ran to completion (no interrupt)
        # This happens when needs_followup=False and the graph finishes
        logger.info(f"Research completed for task {task_id}, thread {thread_id}")

        # Extract data from final state and save to DB
        research_topic = ""
        final_report = ""
        research_history = []

        if final_state:
            research_topic = final_state.get("research_topic", "")
            final_report = final_state.get("final_report", "")
            research_history = final_state.get("research_history", [])

        # Update DB record on completion
        try:
            async with AsyncSessionLocal() as db:
                if org_schema:
                    from sqlalchemy import text
                    await db.execute(text(f'SET LOCAL search_path TO "{org_schema}", public'))
                from sqlalchemy import update
                stmt = (
                    update(ResearchReport)
                    .where(ResearchReport.task_id == task_id)
                    .values(
                        status="done",
                        research_topic=research_topic,
                        report=final_report,
                        notes_json=json.dumps(research_history),
                    )
                )
                await db.execute(stmt)
                await db.commit()
                logger.info(f"Updated research report for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to update research report: {e}")

        await publish_event(thread_id, {"type": "done", "final_report": final_report})
        await clear_processing_flag(task_id)

    run_async_from_sync(_run())


@celery_app.task(name="resume_research_task")
def resume_research_task(
    task_id: str,
    thread_id: str,
    action: str | dict,
    org_schema: str | None = None,
):
    """
    Resume a research graph after user action.
    Calls graph.invoke with Command(resume=action).
    """
    async def _run():
        logger.info(f"Resuming research for task {task_id}, thread {thread_id}, action={action}")

        async with get_postgres_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)

            # Config with thread_id as checkpointer key
            config = {
                "configurable": {"thread_id": thread_id, "task_id": task_id},
            }

            final_state = None
            try:
                # Call invoke with Command(resume=action) to continue from interrupt
                # The checkpointer will restore the saved state
                final_state = await graph.ainvoke(Command(resume=action), config)
                logger.info(f"Resume completed for task {task_id}, thread {thread_id}")
            except Exception as e:
                from langgraph.errors import GraphInterrupt
                if isinstance(e, GraphInterrupt):
                    # This is expected - another interrupt occurred
                    logger.info(f"Research interrupted again for task {task_id}, thread {thread_id}")
                    return

        # If we get here, the graph completed (e.g., confirm_done was selected)
        # Extract and save the final report
        if final_state:
            final_report = final_state.get("final_report", "")
            research_history = final_state.get("research_history", [])
            research_topic = final_state.get("research_topic", "")

            try:
                async with AsyncSessionLocal() as db:
                    if org_schema:
                        from sqlalchemy import text
                        await db.execute(text(f'SET LOCAL search_path TO "{org_schema}", public'))
                    from sqlalchemy import update
                    stmt = (
                        update(ResearchReport)
                        .where(ResearchReport.task_id == task_id)
                        .values(
                            status="done",
                            research_topic=research_topic,
                            report=final_report,
                            notes_json=json.dumps(research_history),
                        )
                    )
                    await db.execute(stmt)
                    await db.commit()
                    logger.info(f"Updated research report for task {task_id} after resume")
            except Exception as e:
                logger.error(f"Failed to update research report after resume: {e}")

            await publish_event(thread_id, {"type": "done", "final_report": final_report})

    run_async_from_sync(_run())
