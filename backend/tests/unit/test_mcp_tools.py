# backend/tests/unit/test_mcp_tools.py
"""
Unit tests for app.mcp.operations and app.mcp.server.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

pytestmark = [pytest.mark.unit]


# --------------------------------------------------------------------------
# OperationStatus dataclass tests
# --------------------------------------------------------------------------

class TestOperationStatus:
    """Tests for OperationStatus dataclass."""

    def test_to_json_serializes_all_fields(self):
        from app.mcp.operations import OperationStatus

        status = OperationStatus(
            id="task-123",
            type="research",
            status="done",
            message="Research complete",
            progress=1.0,
            created_at="2026-04-12T10:00:00Z",
        )
        result = json.loads(status.to_json())

        assert result["id"] == "task-123"
        assert result["type"] == "research"
        assert result["status"] == "done"
        assert result["message"] == "Research complete"
        assert result["progress"] == 1.0

    def test_error_static_creates_failed_status(self):
        from app.mcp.operations import OperationStatus

        status = OperationStatus.error("task-456", "Something went wrong")

        assert status.id == "task-456"
        assert status.type == "research"
        assert status.status == "failed"
        assert status.message == "Something went wrong"
        assert status.progress == 0.0
        assert status.created_at.endswith("Z")

    def test_not_found_static_creates_not_found_status(self):
        from app.mcp.operations import OperationStatus

        status = OperationStatus.not_found("task-789")

        assert status.id == "task-789"
        assert status.status == "failed"
        assert "not found" in status.message


# --------------------------------------------------------------------------
# Status mapping function tests
# --------------------------------------------------------------------------

class TestResearchStatusMapping:
    """Tests for _map_research_status."""

    def test_map_running_to_processing(self):
        from app.mcp.operations import _map_research_status
        assert _map_research_status("running") == "processing"

    def test_map_done(self):
        from app.mcp.operations import _map_research_status
        assert _map_research_status("done") == "done"

    def test_map_error_to_failed(self):
        from app.mcp.operations import _map_research_status
        assert _map_research_status("error") == "failed"

    def test_map_start_to_started(self):
        from app.mcp.operations import _map_research_status
        assert _map_research_status("start") == "started"

    def test_map_unknown_defaults_to_processing(self):
        from app.mcp.operations import _map_research_status
        assert _map_research_status("unknown") == "processing"


class TestBlackboardStatusMapping:
    """Tests for blackboard status helpers."""

    def test_map_generating_to_processing(self):
        from app.mcp.operations import _map_blackboard_status
        assert _map_blackboard_status("generating") == "processing"

    def test_map_completed_to_done(self):
        from app.mcp.operations import _map_blackboard_status
        assert _map_blackboard_status("completed") == "done"

    def test_blackboard_progress_generating(self):
        from app.mcp.operations import _blackboard_progress
        assert _blackboard_progress("generating") == 0.5

    def test_blackboard_progress_completed(self):
        from app.mcp.operations import _blackboard_progress
        assert _blackboard_progress("completed") == 1.0

    def test_blackboard_status_message(self):
        from app.mcp.operations import _blackboard_status_message
        assert "in progress" in _blackboard_status_message("generating")
        assert "complete" in _blackboard_status_message("completed")


class TestMatrixStatusMapping:
    """Tests for matrix status helpers."""

    def test_map_generating_parameters_to_processing(self):
        from app.mcp.operations import _map_matrix_status
        assert _map_matrix_status("generating_parameters") == "processing"

    def test_map_parameters_ready_to_done(self):
        from app.mcp.operations import _map_matrix_status
        assert _map_matrix_status("parameters_ready") == "done"

    def test_map_generate_failed_to_failed(self):
        from app.mcp.operations import _map_matrix_status
        assert _map_matrix_status("generate_failed") == "failed"

    def test_matrix_progress_generating_parameters(self):
        from app.mcp.operations import _matrix_progress
        assert _matrix_progress("generating_parameters") == 0.25

    def test_matrix_progress_matrix_ready(self):
        from app.mcp.operations import _matrix_progress
        assert _matrix_progress("matrix_ready") == 1.0

    def test_matrix_status_message(self):
        from app.mcp.operations import _matrix_status_message
        assert "Generating" in _matrix_status_message("generating_parameters")
        assert "complete" in _matrix_status_message("matrix_ready")


# --------------------------------------------------------------------------
# get_operation_status tests
# --------------------------------------------------------------------------

class TestGetOperationStatus:
    """Tests for get_operation_status."""

    @patch("app.research.stream.get_research_state")
    @patch("app.research.stream.get_processing_status")
    async def test_returns_redis_state_for_research(self, mock_get_proc, mock_get_state):
        from app.mcp.operations import get_operation_status

        mock_get_proc.return_value = True
        mock_get_state.return_value = {
            "status": "done",
            "message": "Research complete",
            "progress": 1.0,
        }

        result = await get_operation_status("research-task-123")

        assert result.id == "research-task-123"
        assert result.type == "research"
        assert result.status == "done"
        assert result.progress == 1.0

    @patch("app.research.stream.get_research_state")
    @patch("app.research.stream.get_processing_status")
    async def test_returns_blackboard_status_from_db_fallback(self, mock_get_proc, mock_get_state):
        from app.mcp.operations import get_operation_status

        mock_get_proc.return_value = False
        mock_get_state.return_value = None

        blackboard = MagicMock()
        blackboard.status = "completed"
        blackboard.created_at = datetime(2026, 4, 12, tzinfo=UTC)

        bb_result = MagicMock()
        bb_result.scalars.return_value.first.return_value = blackboard
        matrix_result = MagicMock()
        matrix_result.scalars.return_value.first.return_value = None

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[bb_result])
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("app.core.database.AsyncSessionLocal", return_value=session_cm):
            result = await get_operation_status("123")

        assert result.id == "123"
        assert result.type == "blackboard"
        assert result.status == "done"
        assert result.message == "Blackboard generation complete"
        assert result.progress == 1.0

    @patch("app.research.stream.get_research_state")
    @patch("app.research.stream.get_processing_status")
    async def test_returns_matrix_status_from_db_fallback(self, mock_get_proc, mock_get_state):
        from app.mcp.operations import get_operation_status

        mock_get_proc.return_value = False
        mock_get_state.return_value = None

        bb_result = MagicMock()
        bb_result.scalars.return_value.first.return_value = None

        matrix = MagicMock()
        matrix.status = "evaluating_matrix"
        matrix.created_at = datetime(2026, 4, 12, tzinfo=UTC)
        matrix_result = MagicMock()
        matrix_result.scalars.return_value.first.return_value = matrix

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[bb_result, matrix_result])
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("app.core.database.AsyncSessionLocal", return_value=session_cm):
            result = await get_operation_status("456")

        assert result.id == "456"
        assert result.type == "matrix"
        assert result.status == "processing"
        assert result.message == "Evaluating matrix consistency"
        assert result.progress == 0.75

    @patch("app.research.stream.get_research_state")
    @patch("app.research.stream.get_processing_status")
    async def test_returns_not_found_when_missing(self, mock_get_proc, mock_get_state):
        from app.mcp.operations import get_operation_status

        mock_get_proc.return_value = False
        mock_get_state.return_value = None

        bb_result = MagicMock()
        bb_result.scalars.return_value.first.return_value = None
        matrix_result = MagicMock()
        matrix_result.scalars.return_value.first.return_value = None

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[bb_result, matrix_result])
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("app.core.database.AsyncSessionLocal", return_value=session_cm):
            result = await get_operation_status("999")

        assert result.status == "failed"
        assert "not found" in result.message


# --------------------------------------------------------------------------
# MCP server creation smoke test
# --------------------------------------------------------------------------

def test_mcp_server_creation():
    """Smoke test: verify MCP server can be created with all default tools."""
    from app.mcp.server import create_mcp_server

    mcp = create_mcp_server()
    assert mcp is not None

    components = mcp._local_provider._components
    tool_names = {k.split(":")[1][:-1] for k in components if k.startswith("tool:")}
    expected = {
        "workspace_list", "workspace_get", "workspace_create", "workspace_delete",
        "chat_list", "chat_get", "chat_create", "chat_send_message", "chat_get_history",
        "matrix_list_analyses", "matrix_get_analysis", "matrix_start_analysis",
        "matrix_evaluate_consistency", "matrix_save_analysis", "matrix_delete_analysis",
        "blackboard_list", "blackboard_get", "blackboard_generate", "blackboard_delete",
        "research_list_reports", "research_get_report", "research_start",
        "research_get_result", "research_get_state", "research_delete_report",
        "operation_list", "operation_get_status",
    }
    assert expected.issubset(tool_names), f"Missing: {expected - tool_names}"
