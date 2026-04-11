# backend/tests/unit/test_research_tasks.py
"""
Unit tests for app.research.tasks — Celery task behavior around notifications.
"""
import json
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit]


def _make_async_session(report_id):
    update_result = MagicMock()
    select_result = MagicMock()
    report = MagicMock(id=report_id) if report_id is not None else None
    select_result.scalars.return_value.first.return_value = report

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[update_result, select_result])
    session.commit = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    return session_cm, session


def _success_graph(topic="AI Agent 研究", report="Research report content.", notes=None, queries=None):
    async def astream(initial_state, config):
        yield {
            "generate_report": {
                "research_topic": topic,
                "final_report": report,
                "notes": notes or ["note-1"],
                "search_queries": queries or ["query-1"],
            }
        }

    graph = MagicMock()
    graph.astream = astream
    return graph


def _failing_graph(error_message="Search failed"):
    async def astream(initial_state, config):
        raise RuntimeError(error_message)
        yield  # pragma: no cover

    graph = MagicMock()
    graph.astream = astream
    return graph


class TestProcessResearchNotification:
    def test_process_research_publishes_success_notification(self):
        from app.research.tasks import process_research

        mock_redis = MagicMock()
        mock_redis.publish = MagicMock()
        mock_redis.close = MagicMock()
        session_cm, session = _make_async_session(report_id=99)

        with (
            patch("app.research.tasks.build_graph", return_value=_success_graph()),
            patch("app.research.tasks.AsyncSessionLocal", return_value=session_cm),
            patch("app.research.tasks.set_processing_flag", new=AsyncMock()),
            patch("app.research.tasks.publish_event", new=AsyncMock()) as mock_publish_event,
            patch("app.research.tasks.save_research_state", new=AsyncMock()) as mock_save_state,
            patch("app.research.tasks.clear_processing_flag", new=AsyncMock()) as mock_clear_flag,
            patch("app.research.tasks.redis.Redis.from_url", return_value=mock_redis),
        ):
            process_research(
                task_id="task-123",
                query="Test query",
                level="standard",
                max_iterations=None,
                max_results=None,
                user_id=42,
            )

        mock_redis.publish.assert_called_once()
        channel, raw_message = mock_redis.publish.call_args.args
        message = json.loads(raw_message)

        assert channel == "user_notifications_42"
        assert message["type"] == "research_report"
        assert message["task_type"] == "research_complete"
        assert message["resource_type"] == "research_report"
        assert message["resource_id"] == 99
        assert message["result"] == "success"
        assert message["status"] == "done"
        assert message["title"] == "研究完成"
        assert "AI Agent" in message["message"]
        assert message["link"] == "/research?report_id=99"

        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()
        mock_clear_flag.assert_awaited_once_with("task-123")
        assert mock_publish_event.await_count >= 2
        assert mock_save_state.await_count >= 3

    def test_process_research_publishes_error_notification(self):
        from app.research.tasks import process_research

        mock_redis = MagicMock()
        mock_redis.publish = MagicMock()
        mock_redis.close = MagicMock()
        session_cm, session = _make_async_session(report_id=None)

        with (
            patch("app.research.tasks.build_graph", return_value=_failing_graph("Search failed")),
            patch("app.research.tasks.AsyncSessionLocal", return_value=session_cm),
            patch("app.research.tasks.set_processing_flag", new=AsyncMock()),
            patch("app.research.tasks.publish_event", new=AsyncMock()) as mock_publish_event,
            patch("app.research.tasks.save_research_state", new=AsyncMock()) as mock_save_state,
            patch("app.research.tasks.clear_processing_flag", new=AsyncMock()) as mock_clear_flag,
            patch("app.research.tasks.redis.Redis.from_url", return_value=mock_redis),
        ):
            process_research(
                task_id="task-456",
                query="Test query",
                level="standard",
                max_iterations=None,
                max_results=None,
                user_id=42,
            )

        mock_redis.publish.assert_called_once()
        channel, raw_message = mock_redis.publish.call_args.args
        message = json.loads(raw_message)

        assert channel == "user_notifications_42"
        assert message["result"] == "error"
        assert message["status"] == "error"
        assert message["title"] == "研究失败"
        assert message["resource_id"] is None
        assert message["link"] is None
        assert "Search failed" in message["message"]

        session.execute.assert_awaited()
        session.commit.assert_awaited_once()
        mock_clear_flag.assert_awaited_once_with("task-456")
        assert mock_publish_event.await_count >= 2
        assert mock_save_state.await_count >= 3

    def test_process_research_skips_notification_without_user_id(self):
        from app.research.tasks import process_research

        session_cm, session = _make_async_session(report_id=77)

        with (
            patch("app.research.tasks.build_graph", return_value=_success_graph(topic="Long topic for truncation test")),
            patch("app.research.tasks.AsyncSessionLocal", return_value=session_cm),
            patch("app.research.tasks.set_processing_flag", new=AsyncMock()),
            patch("app.research.tasks.publish_event", new=AsyncMock()),
            patch("app.research.tasks.save_research_state", new=AsyncMock()),
            patch("app.research.tasks.clear_processing_flag", new=AsyncMock()),
            patch("app.research.tasks.redis.Redis.from_url") as mock_from_url,
        ):
            process_research(
                task_id="task-789",
                query="Test query",
                level="standard",
                max_iterations=None,
                max_results=None,
                user_id=None,
            )

        mock_from_url.assert_not_called()
        session.execute.assert_awaited()

    def test_process_research_truncates_topic_in_notification_message(self):
        from app.research.tasks import process_research

        long_topic = "这是一个非常长的研究主题关于AI Agent的最新发展"
        mock_redis = MagicMock()
        mock_redis.publish = MagicMock()
        mock_redis.close = MagicMock()
        session_cm, _ = _make_async_session(report_id=88)

        with (
            patch("app.research.tasks.build_graph", return_value=_success_graph(topic=long_topic)),
            patch("app.research.tasks.AsyncSessionLocal", return_value=session_cm),
            patch("app.research.tasks.set_processing_flag", new=AsyncMock()),
            patch("app.research.tasks.publish_event", new=AsyncMock()),
            patch("app.research.tasks.save_research_state", new=AsyncMock()),
            patch("app.research.tasks.clear_processing_flag", new=AsyncMock()),
            patch("app.research.tasks.redis.Redis.from_url", return_value=mock_redis),
        ):
            process_research(
                task_id="task-999",
                query="Test query",
                level="standard",
                max_iterations=None,
                max_results=None,
                user_id=7,
            )

        _, raw_message = mock_redis.publish.call_args.args
        message = json.loads(raw_message)
        assert long_topic[:20] in message["message"]
        assert "...」的研究报告已生成" in message["message"]
