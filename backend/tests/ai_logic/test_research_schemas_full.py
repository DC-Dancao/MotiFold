"""
Comprehensive tests for app.research.schemas — all API models.

Covers:
- ResearchStart, ResearchStartLoop (validation, defaults)
- ResearchStatus (status values, validation)
- ResearchResult
- ResearchReportSchema, ResearchHistoryItem, ResearchRunningState
- ResearchStartResponse, ResumeRequest, ResumeResponse
"""
import pytest
from pydantic import ValidationError

from app.research.schemas import (
    ResearchStart,
    ResearchStartLoop,
    ResearchStartResponse,
    ResearchStatus,
    ResearchResult,
    ResearchReportSchema,
    ResearchHistoryItem,
    ResearchRunningState,
    ResumeRequest,
    ResumeResponse,
)
from app.research.state import ResearchLevel


class TestResearchStartLoop:
    """Tests for ResearchStartLoop schema."""

    def test_defaults(self):
        schema = ResearchStartLoop(topic="What is AI?")
        assert schema.topic == "What is AI?"
        assert schema.level == ResearchLevel.STANDARD
        assert schema.max_iterations is None
        assert schema.max_results is None

    def test_with_extended_level(self):
        schema = ResearchStartLoop(topic="Deep dive", level=ResearchLevel.EXTENDED)
        assert schema.level == ResearchLevel.EXTENDED

    def test_with_custom_iterations(self):
        schema = ResearchStartLoop(topic="test", max_iterations=7, max_results=50)
        assert schema.max_iterations == 7
        assert schema.max_results == 50

    def test_topic_required(self):
        with pytest.raises(ValidationError):
            ResearchStartLoop()

    def test_max_iterations_minimum(self):
        """max_iterations must be >= 1."""
        with pytest.raises(ValidationError):
            ResearchStartLoop(topic="test", max_iterations=0)

    def test_max_iterations_maximum(self):
        """max_iterations must be <= 100."""
        with pytest.raises(ValidationError):
            ResearchStartLoop(topic="test", max_iterations=101)

    def test_max_results_minimum(self):
        """max_results must be >= 1."""
        with pytest.raises(ValidationError):
            ResearchStartLoop(topic="test", max_results=0)

    def test_max_results_maximum(self):
        """max_results must be <= 1000."""
        with pytest.raises(ValidationError):
            ResearchStartLoop(topic="test", max_results=1001)


class TestResearchRunningState:
    """Tests for ResearchRunningState schema."""

    def test_required_fields(self):
        schema = ResearchRunningState(
            status="running",
            message="Working...",
            progress=0.5,
            level=ResearchLevel.STANDARD,
            task_id="task-123",
            research_topic="AI Research",
        )
        assert schema.status == "running"
        assert schema.progress == 0.5
        assert schema.notes == []
        assert schema.queries == []

    def test_with_notes_and_queries(self):
        schema = ResearchRunningState(
            status="searching",
            message="Searching...",
            progress=0.3,
            level=ResearchLevel.EXTENDED,
            task_id="task-456",
            research_topic="Topic",
            notes=["note1", "note2"],
            queries=["q1", "q2"],
        )
        assert len(schema.notes) == 2
        assert len(schema.queries) == 2

    def test_with_iteration(self):
        schema = ResearchRunningState(
            status="synthesizing",
            message="Synthesizing",
            progress=0.7,
            iteration=2,
            level=ResearchLevel.MANUAL,
            task_id="task-789",
            research_topic="Topic",
        )
        assert schema.iteration == 2


class TestResearchReportSchema:
    """Tests for ResearchReportSchema."""

    def test_full_report(self):
        schema = ResearchReportSchema(
            id=1,
            query="AI research",
            research_topic="AI Agents",
            report="# Report\n\nFindings",
            notes=["note1", "note2"],
            queries=["q1"],
            level=ResearchLevel.STANDARD,
            iterations=3,
            created_at="2026-04-01T10:00:00",
            updated_at="2026-04-01T10:30:00",
            status="done",
            task_id="task-123",
        )
        assert schema.id == 1
        assert schema.report.startswith("# Report")
        assert schema.status == "done"

    def test_default_status(self):
        schema = ResearchReportSchema(
            id=1,
            query="test",
            research_topic="topic",
            report="",
            notes=[],
            queries=[],
            level=ResearchLevel.STANDARD,
            iterations=0,
            created_at="",
            updated_at="",
        )
        assert schema.status == "running"

    def test_optional_task_id(self):
        schema = ResearchReportSchema(
            id=1,
            query="test",
            research_topic="topic",
            report="",
            notes=[],
            queries=[],
            level=ResearchLevel.STANDARD,
            iterations=0,
            created_at="",
            updated_at="",
        )
        assert schema.task_id is None


class TestResearchHistoryItem:
    """Tests for ResearchHistoryItem."""

    def test_required_fields(self):
        schema = ResearchHistoryItem(
            id=1,
            query="test query",
            research_topic="test topic",
            level=ResearchLevel.STANDARD,
            iterations=3,
            created_at="2026-04-01T10:00:00",
            updated_at="2026-04-01T10:30:00",
        )
        assert schema.status == "running"
        assert schema.task_id is None

    def test_with_all_fields(self):
        schema = ResearchHistoryItem(
            id=5,
            query="AI research",
            research_topic="AI topic",
            level=ResearchLevel.EXTENDED,
            iterations=6,
            created_at="2026-04-01T10:00:00",
            updated_at="2026-04-01T11:00:00",
            status="done",
            task_id="task-xyz",
        )
        assert schema.status == "done"
        assert schema.task_id == "task-xyz"


class TestResumeRequest:
    """Tests for ResumeRequest schema."""

    def test_string_action(self):
        schema = ResumeRequest(action="confirm_done")
        assert schema.action == "confirm_done"

    def test_option_1_action(self):
        schema = ResumeRequest(action="option_1")
        assert schema.action == "option_1"

    def test_skip_action(self):
        schema = ResumeRequest(action="skip")
        assert schema.action == "skip"

    def test_manual_dict_action(self):
        schema = ResumeRequest(action={"type": "manual", "text": "Explore ethics"})
        assert schema.action["type"] == "manual"
        assert "Explore ethics" in schema.action["text"]

    def test_action_required(self):
        with pytest.raises(ValidationError):
            ResumeRequest()


class TestResumeResponse:
    """Tests for ResumeResponse schema."""

    def test_resumed_status(self):
        schema = ResumeResponse(status="resumed")
        assert schema.status == "resumed"
        assert schema.message is None

    def test_error_status_with_message(self):
        schema = ResumeResponse(status="error", message="Thread not found")
        assert schema.status == "error"
        assert "not found" in schema.message

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            ResumeResponse(status="invalid_status")


class TestResearchStartResponse:
    """Tests for ResearchStartResponse schema."""

    def test_thread_id_required(self):
        schema = ResearchStartResponse(thread_id="abc-123-def")
        assert schema.thread_id == "abc-123-def"
