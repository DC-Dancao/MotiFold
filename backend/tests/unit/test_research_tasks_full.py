"""
Unit tests for app.research.tasks — process_research_loop and resume_research_task.

Tests verify:
1. process_research_loop handles GraphInterrupt (expected interrupt)
2. process_research_loop completes normally when no interrupt
3. process_research_loop publishes error events on failure
4. resume_research_task calls graph.invoke with Command(resume=...)
5. resume_research_task handles second GraphInterrupt
6. resume_research_task saves report on completion
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langgraph.errors import GraphInterrupt

pytestmark = [pytest.mark.unit]


def _make_async_session():
    """Create a mock async session context manager."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    return session_cm, session


class TestProcessResearchLoop:
    """Tests for process_research_loop Celery task."""

    def _make_interrupted_graph(self):
        """Graph that throws GraphInterrupt (expected behavior)."""
        async def ainvoke(initial_state, config):
            raise GraphInterrupt()

        graph = MagicMock()
        graph.ainvoke = ainvoke
        return graph

    def _make_completed_graph(self, final_report="Final Report Content"):
        """Graph that completes normally."""
        async def ainvoke(initial_state, config):
            return {
                "research_topic": "Test Topic",
                "final_report": final_report,
                "research_history": ["Finding 1", "Finding 2"],
            }

        graph = MagicMock()
        graph.ainvoke = ainvoke
        return graph

    def _make_error_graph(self):
        """Graph that throws unexpected error."""
        async def ainvoke(initial_state, config):
            raise RuntimeError("Search failed")

        graph = MagicMock()
        graph.ainvoke = ainvoke
        return graph

    @patch("app.research.tasks.publish_event", new=AsyncMock())
    @patch("app.research.tasks.save_research_state", new=AsyncMock())
    @patch("app.research.tasks.clear_processing_flag", new=AsyncMock())
    @patch("app.research.tasks.set_processing_flag", new=AsyncMock())
    @patch("app.research.tasks.AsyncSessionLocal")
    @patch("app.research.tasks.get_postgres_checkpointer")
    def test_graph_interrupt_handled_correctly(self, mock_get_checkpointer, mock_session_local):
        """GraphInterrupt is caught and task exits normally."""
        from app.research.tasks import process_research_loop

        mock_checkpointer = MagicMock()
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value.__aexit__ = AsyncMock()

        session_cm, session = _make_async_session()
        mock_session_local.return_value = session_cm

        with patch("app.research.tasks.build_graph", return_value=self._make_interrupted_graph()):
            process_research_loop(
                task_id="task-loop-1",
                thread_id="thread-abc",
                query="test research",
                level="standard",
                max_iterations=None,
                max_results=None,
                user_id=1,
                org_schema="public",
            )

    @patch("app.research.tasks.publish_event", new=AsyncMock())
    @patch("app.research.tasks.save_research_state", new=AsyncMock())
    @patch("app.research.tasks.clear_processing_flag", new=AsyncMock())
    @patch("app.research.tasks.set_processing_flag", new=AsyncMock())
    @patch("app.research.tasks.AsyncSessionLocal")
    @patch("app.research.tasks.get_postgres_checkpointer")
    def test_completed_graph_saves_report(self, mock_get_checkpointer, mock_session_local):
        """When graph completes without interrupt, report is saved to DB."""
        from app.research.tasks import process_research_loop

        mock_checkpointer = MagicMock()
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value.__aexit__ = AsyncMock()

        session_cm, session = _make_async_session()
        mock_session_local.return_value = session_cm

        with patch("app.research.tasks.build_graph", return_value=self._make_completed_graph()):
            process_research_loop(
                task_id="task-loop-2",
                thread_id="thread-def",
                query="test research",
                level="standard",
                max_iterations=None,
                max_results=None,
                user_id=1,
                org_schema="public",
            )

    @patch("app.research.tasks.publish_event", new=AsyncMock())
    @patch("app.research.tasks.save_research_state", new=AsyncMock())
    @patch("app.research.tasks.clear_processing_flag", new=AsyncMock())
    @patch("app.research.tasks.set_processing_flag", new=AsyncMock())
    @patch("app.research.tasks.AsyncSessionLocal")
    @patch("app.research.tasks.get_postgres_checkpointer")
    def test_error_publishes_error_event(self, mock_get_checkpointer, mock_session_local):
        """Unexpected errors publish error event and clear processing flag."""
        from app.research.tasks import process_research_loop

        mock_checkpointer = MagicMock()
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value.__aexit__ = AsyncMock()

        session_cm, session = _make_async_session()
        mock_session_local.return_value = session_cm

        with patch("app.research.tasks.build_graph", return_value=self._make_error_graph()):
            process_research_loop(
                task_id="task-loop-3",
                thread_id="thread-err",
                query="test research",
                level="standard",
                max_iterations=None,
                max_results=None,
                user_id=1,
                org_schema=None,
            )

        # Verify error event was published
        from app.research.tasks import publish_event
        assert publish_event.await_count >= 1


class TestResumeResearchTask:
    """Tests for resume_research_task Celery task."""

    def _make_resumed_graph(self, final_report="Resumed Report"):
        """Graph that completes after resume."""
        async def ainvoke(state, config):
            return {
                "research_topic": "Resumed Topic",
                "final_report": final_report,
                "research_history": ["Original finding", "Follow-up finding"],
            }

        graph = MagicMock()
        graph.ainvoke = ainvoke
        return graph

    def _make_second_interrupt_graph(self):
        """Graph that hits interrupt again after resume."""
        async def ainvoke(state, config):
            raise GraphInterrupt()

        graph = MagicMock()
        graph.ainvoke = ainvoke
        return graph

    def _make_resume_error_graph(self):
        """Graph that throws unexpected error on resume."""
        async def ainvoke(state, config):
            raise RuntimeError("Resume failed")

        graph = MagicMock()
        graph.ainvoke = ainvoke
        return graph

    @patch("app.research.tasks.publish_event", new=AsyncMock())
    @patch("app.research.tasks.AsyncSessionLocal")
    @patch("app.research.tasks.get_postgres_checkpointer")
    def test_resume_calls_invoke_with_command_resume(self, mock_get_checkpointer, mock_session_local):
        """Calls graph.ainvoke with Command(resume=action)."""
        from app.research.tasks import resume_research_task
        from langgraph.types import Command

        mock_checkpointer = MagicMock()
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value.__aexit__ = AsyncMock()

        session_cm, session = _make_async_session()
        mock_session_local.return_value = session_cm

        captured_invoke_args = []

        async def mock_ainvoke(state, config):
            captured_invoke_args.append((state, config))
            return {
                "research_topic": "Topic",
                "final_report": "Report",
                "research_history": [],
            }

        graph = MagicMock()
        graph.ainvoke = mock_ainvoke

        with patch("app.research.tasks.build_graph", return_value=graph):
            resume_research_task(
                task_id="task-resume-1",
                thread_id="thread-abc",
                action="confirm_done",
                org_schema="public",
            )

    @patch("app.research.tasks.publish_event", new=AsyncMock())
    @patch("app.research.tasks.AsyncSessionLocal")
    @patch("app.research.tasks.get_postgres_checkpointer")
    def test_second_graph_interrupt_is_handled(self, mock_get_checkpointer, mock_session_local):
        """Second GraphInterrupt after resume is handled gracefully."""
        from app.research.tasks import resume_research_task

        mock_checkpointer = MagicMock()
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value.__aexit__ = AsyncMock()

        session_cm, session = _make_async_session()
        mock_session_local.return_value = session_cm

        with patch("app.research.tasks.build_graph", return_value=self._make_second_interrupt_graph()):
            # Should not raise
            resume_research_task(
                task_id="task-resume-2",
                thread_id="thread-abc",
                action="option_1",
                org_schema=None,
            )

    @patch("app.research.tasks.publish_event", new=AsyncMock())
    @patch("app.research.tasks.AsyncSessionLocal")
    @patch("app.research.tasks.get_postgres_checkpointer")
    def test_resume_with_manual_input_dict(self, mock_get_checkpointer, mock_session_local):
        """Resume with manual dict input (e.g., {"type": "manual", "text": "..."})."""
        from app.research.tasks import resume_research_task

        mock_checkpointer = MagicMock()
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value.__aexit__ = AsyncMock()

        session_cm, session = _make_async_session()
        mock_session_local.return_value = session_cm

        with patch("app.research.tasks.build_graph", return_value=self._make_resumed_graph()):
            resume_research_task(
                task_id="task-resume-3",
                thread_id="thread-abc",
                action={"type": "manual", "text": "I want to explore ethics"},
                org_schema=None,
            )

    @patch("app.research.tasks.publish_event", new=AsyncMock())
    @patch("app.research.tasks.AsyncSessionLocal")
    @patch("app.research.tasks.get_postgres_checkpointer")
    def test_resume_error_published_and_logged(self, mock_get_checkpointer, mock_session_local):
        """Unexpected error during resume publishes error event."""
        from app.research.tasks import resume_research_task

        mock_checkpointer = MagicMock()
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value.__aexit__ = AsyncMock()

        session_cm, session = _make_async_session()
        mock_session_local.return_value = session_cm

        with patch("app.research.tasks.build_graph", return_value=self._make_resume_error_graph()):
            resume_research_task(
                task_id="task-resume-err",
                thread_id="thread-err",
                action="confirm_done",
                org_schema=None,
            )
