"""
Unit tests for app.research.router — FastAPI endpoints.

Tests verify:
1. POST /research/ — start_research creates task and DB record
2. GET /research/{task_id}/stream — SSE stream endpoint
3. GET /research/{task_id}/state — returns persisted state
4. GET /research/{task_id}/result — returns final result
5. GET /research/history — returns user's research history
6. GET /research/{report_id} — returns specific report
7. DELETE /research/{report_id} — deletes report
8. POST /research/start — confirmation loop start
9. POST /research/resume/{thread_id} — resume after interrupt
10. GET /research/stream/{thread_id} — SSE stream for confirmation loop
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from fastapi import HTTPException

from app.research.router import (
    start_research,
    stream_research,
    get_research_state_endpoint,
    get_result,
    get_research_history,
    get_research_report,
    delete_research_report,
    start_research_v2,
    resume_research,
    stream_research_loop,
)
from app.research.schemas import (
    ResearchStart,
    ResearchStartLoop,
    ResearchStartResponse,
    ResumeRequest,
    ResumeResponse,
)
from app.research.state import ResearchLevel
from app.research.schemas import ResearchRunningState

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


# --------------------------------------------------------------------------
# Mocks & Fixtures
# --------------------------------------------------------------------------

class MockPubsub:
    def __init__(self, messages=None):
        self.messages = messages or []
        self.subscribed_channel = None

    async def subscribe(self, channel):
        self.subscribed_channel = channel

    async def unsubscribe(self, channel):
        pass

    async def close(self):
        pass

    def listen(self):
        return iter(self.messages)


class MockRedis:
    def __init__(self, pubsub=None, get_value=None):
        self._pubsub = pubsub or MockPubsub()
        self._get_value = get_value

    def pubsub(self):
        return self._pubsub

    async def get(self, key):
        return self._get_value


class MockRequest:
    def __init__(self, org_schema=None):
        self.state = MagicMock()
        self.state.org_schema = org_schema


class MockReport:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.user_id = kwargs.get("user_id", 1)
        self.query = kwargs.get("query", "test query")
        self.research_topic = kwargs.get("research_topic", "Test Topic")
        self.report = kwargs.get("report", "# Test Report\n\nFindings.")
        self.notes_json = kwargs.get("notes_json", '[]')
        self.queries_json = kwargs.get("queries_json", '[]')
        self.level = kwargs.get("level", "standard")
        self.iterations = kwargs.get("iterations", 3)
        self.status = kwargs.get("status", "done")
        self.task_id = kwargs.get("task_id", "task-123")
        self.created_at = kwargs.get("created_at", datetime.now(UTC))
        self.updated_at = kwargs.get("updated_at", datetime.now(UTC))


class MockDB:
    def __init__(self, report=None):
        self._report = report
        self._committed = False
        self._deleted = False

    async def execute(self, *args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.first.return_value = self._report
        result.scalars.return_value.all.return_value = [self._report] if self._report else []
        return result

    async def commit(self):
        self._committed = True

    async def delete(self, report):
        self._deleted = True

    async def flush(self):
        pass

    def add(self, report):
        pass


# --------------------------------------------------------------------------
# TestStartResearch
# --------------------------------------------------------------------------

class TestStartResearch:
    """Tests for POST /research/ — start_research endpoint."""

    async def test_creates_task_and_db_record(self):
        """start_research creates DB record and enqueues Celery task."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()
        mock_membership = MagicMock()

        with patch("app.research.router.set_processing_flag", new=AsyncMock()) as mock_set_flag:
            with patch("app.research.tasks.process_research") as mock_task:
                mock_task.delay = MagicMock()

                request = MockRequest(org_schema="public")
                data = ResearchStart(query="AI Agent 研究", level=ResearchLevel.STANDARD)

                result = await start_research(
                    request=request,
                    data=data,
                    current_user=mock_user,
                    db=mock_db,
                    membership=mock_membership,
                )

        assert result.task_id is not None
        assert result.status == "searching"
        assert result.level == ResearchLevel.STANDARD
        mock_set_flag.assert_called_once()
        mock_task.delay.assert_called_once()

        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs["query"] == "AI Agent 研究"
        assert call_kwargs["level"] == "standard"
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["org_schema"] == "public"

    async def test_uses_extended_level_defaults(self):
        """Extended level uses correct max_iterations and max_results."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        with patch("app.research.router.set_processing_flag", new=AsyncMock()):
            with patch("app.research.tasks.process_research") as mock_task:
                mock_task.delay = MagicMock()

                request = MockRequest()
                data = ResearchStart(query="test", level=ResearchLevel.EXTENDED)

                await start_research(
                    request=request,
                    data=data,
                    current_user=mock_user,
                    db=mock_db,
                    membership=MagicMock(),
                )

        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs["max_iterations"] == 6
        assert call_kwargs["max_results"] == 20

    async def test_custom_max_iterations_overrides_default(self):
        """Custom max_iterations overrides level default."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        with patch("app.research.router.set_processing_flag", new=AsyncMock()):
            with patch("app.research.tasks.process_research") as mock_task:
                mock_task.delay = MagicMock()

                request = MockRequest()
                data = ResearchStart(query="test", level=ResearchLevel.STANDARD, max_iterations=5)

                await start_research(
                    request=request,
                    data=data,
                    current_user=mock_user,
                    db=mock_db,
                    membership=MagicMock(),
                )

        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs["max_iterations"] == 5


# --------------------------------------------------------------------------
# TestStreamResearch
# --------------------------------------------------------------------------

class TestStreamResearch:
    """Tests for GET /research/{task_id}/stream endpoint."""

    async def test_raises_404_when_report_not_found(self):
        """Returns 404 if task_id doesn't belong to user."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB(report=None)
        mock_membership = MagicMock()

        request = MockRequest()

        with pytest.raises(HTTPException) as exc_info:
            await stream_research(
                request=request,
                task_id="nonexistent-task",
                current_user=mock_user,
                db=mock_db,
                membership=mock_membership,
            )

        assert exc_info.value.status_code == 404


# --------------------------------------------------------------------------
# TestGetResearchStateEndpoint
# --------------------------------------------------------------------------

class TestGetResearchStateEndpoint:
    """Tests for GET /research/{task_id}/state endpoint."""

    async def test_returns_redis_state_when_available(self):
        """Returns persisted Redis state if task is running."""
        redis_state = {
            "status": "running",
            "message": "Research in progress",
            "progress": 0.5,
            "iteration": 1,
            "research_topic": "AI Agent 研究",
            "notes": ["note 1"],
            "queries": ["query 1"],
            "level": "standard",
            "task_id": "task-123",
        }

        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        with patch("app.research.router.get_research_state", new=AsyncMock(return_value=redis_state)):
            request = MockRequest()
            result = await get_research_state_endpoint(
                request=request,
                task_id="task-123",
                current_user=mock_user,
                db=mock_db,
                membership=MagicMock(),
            )

        assert result.status == "running"
        assert result.progress == 0.5
        assert result.research_topic == "AI Agent 研究"
        assert result.notes == ["note 1"]

    async def test_falls_back_to_db_when_redis_empty(self):
        """Falls back to DB record when Redis state is None."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_report = MockReport(
            id=1,
            task_id="task-456",
            status="done",
            research_topic="DB Topic",
            notes_json='["note"]',
            queries_json='["q"]',
            level="extended",
            iterations=3,
        )
        mock_db = MockDB(report=mock_report)

        with patch("app.research.router.get_research_state", new=AsyncMock(return_value=None)):
            request = MockRequest()
            result = await get_research_state_endpoint(
                request=request,
                task_id="task-456",
                current_user=mock_user,
                db=mock_db,
                membership=MagicMock(),
            )

        assert result.status == "done"
        assert result.research_topic == "DB Topic"

    async def test_raises_404_when_not_found(self):
        """Returns 404 when task not found in Redis or DB."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB(report=None)

        with patch("app.research.router.get_research_state", new=AsyncMock(return_value=None)):
            request = MockRequest()
            with pytest.raises(HTTPException) as exc_info:
                await get_research_state_endpoint(
                    request=request,
                    task_id="nonexistent",
                    current_user=mock_user,
                    db=mock_db,
                    membership=MagicMock(),
                )

        assert exc_info.value.status_code == 404


# --------------------------------------------------------------------------
# TestGetResult
# --------------------------------------------------------------------------

class TestGetResult:
    """Tests for GET /research/{task_id}/result endpoint."""

    async def test_returns_result_from_redis(self):
        """Returns cached result from Redis."""
        cached_data = {
            "report": "# Final Report\n\nResearch complete.",
            "iterations": 3,
            "level": "standard",
        }

        mock_user = MagicMock()
        mock_user.id = 1
        mock_report = MagicMock()
        mock_report.task_id = "task-123"
        mock_db = MockDB(report=mock_report)

        mock_redis = MockRedis(get_value=json.dumps(cached_data))

        with patch("app.research.router.get_redis", new=AsyncMock(return_value=mock_redis)):
            request = MockRequest()
            result = await get_result(
                request=request,
                task_id="task-123",
                current_user=mock_user,
                db=mock_db,
                membership=MagicMock(),
            )

        assert "Final Report" in result.report
        assert result.iterations == 3

    async def test_raises_404_when_not_cached(self):
        """Returns 404 when result not in Redis."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        mock_redis = MockRedis(get_value=None)

        with patch("app.research.router.get_redis", new=AsyncMock(return_value=mock_redis)):
            request = MockRequest()
            with pytest.raises(HTTPException) as exc_info:
                await get_result(
                    request=request,
                    task_id="task-123",
                    current_user=mock_user,
                    db=mock_db,
                    membership=MagicMock(),
                )

        assert exc_info.value.status_code == 404


# --------------------------------------------------------------------------
# TestGetResearchHistory
# --------------------------------------------------------------------------

class TestGetResearchHistory:
    """Tests for GET /research/history endpoint."""

    async def test_returns_user_reports_ordered_by_updated_at(self):
        """Returns all reports for user ordered by updated_at desc."""
        mock_user = MagicMock()
        mock_user.id = 1

        mock_report = MockReport(
            id=1,
            query="AI research",
            research_topic="AI Topic",
            level="standard",
            iterations=3,
            status="done",
            task_id="task-1",
        )
        mock_db = MockDB(report=mock_report)

        request = MockRequest()
        result = await get_research_history(
            request=request,
            current_user=mock_user,
            db=mock_db,
            membership=MagicMock(),
        )

        assert len(result) == 1
        assert result[0].query == "AI research"
        assert result[0].research_topic == "AI Topic"


# --------------------------------------------------------------------------
# TestGetResearchReport
# --------------------------------------------------------------------------

class TestGetResearchReport:
    """Tests for GET /research/{report_id} endpoint."""

    async def test_returns_report_by_id(self):
        """Returns specific report by ID."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_report = MockReport(
            id=5,
            query="Deep research",
            research_topic="Deep Topic",
            report="# Report\n\nContent",
            notes_json='["n1", "n2"]',
            queries_json='["q1"]',
            level="extended",
            iterations=6,
            status="done",
            task_id="task-5",
        )
        mock_db = MockDB(report=mock_report)

        request = MockRequest()
        result = await get_research_report(
            request=request,
            report_id=5,
            current_user=mock_user,
            db=mock_db,
            membership=MagicMock(),
        )

        assert result.id == 5
        assert result.report == "# Report\n\nContent"
        assert result.notes == ["n1", "n2"]
        assert result.queries == ["q1"]

    async def test_raises_404_when_not_found(self):
        """Returns 404 when report doesn't exist."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB(report=None)

        request = MockRequest()
        with pytest.raises(HTTPException) as exc_info:
            await get_research_report(
                request=request,
                report_id=999,
                current_user=mock_user,
                db=mock_db,
                membership=MagicMock(),
            )

        assert exc_info.value.status_code == 404


# --------------------------------------------------------------------------
# TestDeleteResearchReport
# --------------------------------------------------------------------------

class TestDeleteResearchReport:
    """Tests for DELETE /research/{report_id} endpoint."""

    async def test_deletes_report_and_returns_success(self):
        """Deletes report and returns success status."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_report = MockReport(id=7, user_id=1)
        mock_db = MockDB(report=mock_report)

        request = MockRequest()
        result = await delete_research_report(
            request=request,
            report_id=7,
            current_user=mock_user,
            db=mock_db,
            membership=MagicMock(),
        )

        assert result == {"status": "success"}
        assert mock_db._deleted is True
        assert mock_db._committed is True

    async def test_raises_404_when_not_found(self):
        """Returns 404 when trying to delete non-existent report."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB(report=None)

        request = MockRequest()
        with pytest.raises(HTTPException) as exc_info:
            await delete_research_report(
                request=request,
                report_id=999,
                current_user=mock_user,
                db=mock_db,
                membership=MagicMock(),
            )

        assert exc_info.value.status_code == 404


# --------------------------------------------------------------------------
# TestStartResearchV2
# --------------------------------------------------------------------------

class TestStartResearchV2:
    """Tests for POST /research/start — confirmation loop start."""

    async def test_creates_thread_and_enqueues_task(self):
        """Creates thread_id, stores mapping, enqueues process_research_loop."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        mock_redis = MagicMock()
        mock_redis.set = AsyncMock()

        with patch("app.research.router.set_processing_flag", new=AsyncMock()):
            with patch("app.research.router.get_redis", new=AsyncMock(return_value=mock_redis)):
                with patch("app.research.tasks.process_research_loop") as mock_task:
                    mock_task.delay = MagicMock()

                    request = MockRequest()
                    data = ResearchStartLoop(topic="AI Agent 研究", level=ResearchLevel.STANDARD)

                    result = await start_research_v2(
                        request=request,
                        data=data,
                        current_user=mock_user,
                        db=mock_db,
                        membership=MagicMock(),
                    )

        assert result.thread_id is not None
        mock_redis.set.assert_called_once()
        mock_task.delay.assert_called_once()

        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs["query"] == "AI Agent 研究"
        assert call_kwargs["level"] == "standard"
        assert call_kwargs["thread_id"] == result.thread_id

    async def test_stores_thread_task_mapping_with_24h_expiry(self):
        """Stores thread_id -> task_id mapping with 86400s expiry."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        mock_redis = MagicMock()
        mock_redis.set = AsyncMock()

        with patch("app.research.router.set_processing_flag", new=AsyncMock()):
            with patch("app.research.router.get_redis", new=AsyncMock(return_value=mock_redis)):
                with patch("app.research.tasks.process_research_loop") as mock_task:
                    mock_task.delay = MagicMock()

                    request = MockRequest()
                    data = ResearchStartLoop(topic="test")

                    await start_research_v2(
                        request=request,
                        data=data,
                        current_user=mock_user,
                        db=mock_db,
                        membership=MagicMock(),
                    )

        call_args = mock_redis.set.call_args
        assert call_args[0][1] is not None  # task_id value
        # Check expiry is set
        assert call_args[1]["ex"] == 86400


# --------------------------------------------------------------------------
# TestResumeResearch
# --------------------------------------------------------------------------

class TestResumeResearch:
    """Tests for POST /research/resume/{thread_id} endpoint."""

    async def test_resumes_with_thread_id(self):
        """Looks up task_id and enqueues resume_research_task."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=b"task-abc-123")

        with patch("app.research.router.get_redis", new=AsyncMock(return_value=mock_redis)):
            with patch("app.research.tasks.resume_research_task") as mock_task:
                mock_task.delay = MagicMock()

                request = MockRequest()
                data = ResumeRequest(action="confirm_done")

                result = await resume_research(
                    request=request,
                    thread_id="thread-xyz",
                    data=data,
                    current_user=mock_user,
                    db=mock_db,
                    membership=MagicMock(),
                )

        assert result.status == "resumed"
        mock_task.delay.assert_called_once()
        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs["task_id"] == "task-abc-123"
        assert call_kwargs["action"] == "confirm_done"

    async def test_raises_404_when_thread_not_found(self):
        """Returns 404 when thread_id mapping not found."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.research.router.get_redis", new=AsyncMock(return_value=mock_redis)):
            request = MockRequest()
            data = ResumeRequest(action="option_1")

            with pytest.raises(HTTPException) as exc_info:
                await resume_research(
                    request=request,
                    thread_id="nonexistent-thread",
                    data=data,
                    current_user=mock_user,
                    db=mock_db,
                    membership=MagicMock(),
                )

        assert exc_info.value.status_code == 404

    async def test_handles_string_task_id_from_redis(self):
        """Handles task_id returned as string (not bytes)."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value="task-str-123")  # str not bytes

        with patch("app.research.router.get_redis", new=AsyncMock(return_value=mock_redis)):
            with patch("app.research.tasks.resume_research_task") as mock_task:
                mock_task.delay = MagicMock()

                request = MockRequest()
                data = ResumeRequest(action={"type": "manual", "text": "more about X"})

                result = await resume_research(
                    request=request,
                    thread_id="thread-xyz",
                    data=data,
                    current_user=mock_user,
                    db=mock_db,
                    membership=MagicMock(),
                )

        assert result.status == "resumed"
        call_kwargs = mock_task.delay.call_args.kwargs
        assert call_kwargs["task_id"] == "task-str-123"


# --------------------------------------------------------------------------
# TestStreamResearchLoop
# --------------------------------------------------------------------------

class TestStreamResearchLoop:
    """Tests for GET /research/stream/{thread_id} SSE endpoint."""

    async def test_returns_streaming_response(self):
        """Returns StreamingResponse with correct headers."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_db = MockDB()

        mock_pubsub = MockPubsub(messages=[])
        mock_redis = MockRedis(pubsub=mock_pubsub)

        with patch("app.research.router.get_redis", new=AsyncMock(return_value=mock_redis)):
            request = MockRequest()
            result = await stream_research_loop(
                request=request,
                thread_id="thread-abc",
                current_user=mock_user,
                db=mock_db,
                membership=MagicMock(),
            )

        assert result.media_type == "text/event-stream"
        assert "Cache-Control" in result.headers
        assert "X-Accel-Buffering" in result.headers
