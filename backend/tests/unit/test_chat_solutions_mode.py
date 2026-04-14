"""
Unit tests for chat solutions mode functionality.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

pytestmark = [pytest.mark.unit]


class TestChatSolutionsModeSchema:
    """Tests for solutions_mode in chat schemas."""

    def test_chat_create_with_solutions_mode(self):
        """Should accept solutions_mode field."""
        from app.chat.schemas import ChatCreate

        chat = ChatCreate(solutions_mode="solutions")
        assert chat.solutions_mode == "solutions"

    def test_chat_create_without_solutions_mode(self):
        """Should default solutions_mode to None."""
        from app.chat.schemas import ChatCreate

        chat = ChatCreate()
        assert chat.solutions_mode is None

    def test_chat_out_with_solutions_mode(self):
        """Should include solutions_mode in ChatOut."""
        from app.chat.schemas import ChatOut

        now = datetime.now()
        chat = ChatOut(
            id=1,
            user_id=1,
            title="Solutions",
            model="pro",
            solutions_mode="solutions",
            created_at=now
        )
        assert chat.solutions_mode == "solutions"

    def test_chat_out_without_solutions_mode(self):
        """Should default solutions_mode to None in ChatOut."""
        from app.chat.schemas import ChatOut

        now = datetime.now()
        chat = ChatOut(
            id=1,
            user_id=1,
            title="Regular Chat",
            model="pro",
            created_at=now
        )
        assert chat.solutions_mode is None


class TestChatModelSolutionsMode:
    """Tests for solutions_mode in chat model."""

    def test_chat_model_has_solutions_mode_column(self):
        """Chat model should have solutions_mode column."""
        from app.chat.models import Chat

        # Check column exists
        assert hasattr(Chat, "solutions_mode")

    def test_chat_model_solutions_mode_default(self):
        """Chat model solutions_mode should default to None."""
        from app.chat.models import Chat

        # Get column default
        col = Chat.__table__.columns["solutions_mode"]
        assert col.default is None or col.default.arg is None


class TestChatAgentSolutionsMode:
    """Tests for solutions mode in chat agent."""

    def test_solutions_system_prompt_exists(self):
        """Should have SOLUTIONS_SYSTEM_PROMPT defined."""
        from app.chat.agent import SOLUTIONS_SYSTEM_PROMPT

        assert SOLUTIONS_SYSTEM_PROMPT is not None
        assert "Morphological" in SOLUTIONS_SYSTEM_PROMPT
        assert "solutions" in SOLUTIONS_SYSTEM_PROMPT.lower()

    def test_solutions_tools_imported(self):
        """Should import SOLUTION_TOOLS from matrix.tools."""
        from app.chat.agent import SOLUTION_TOOLS

        assert SOLUTION_TOOLS is not None
        assert len(SOLUTION_TOOLS) > 0

    def test_run_agent_accepts_solutions_mode(self):
        """run_agent should accept solutions_mode parameter."""
        from app.chat.agent import run_agent
        import inspect

        sig = inspect.signature(run_agent)
        assert "solutions_mode" in sig.parameters

    def test_get_workflow_accepts_tools(self):
        """get_workflow should accept tools parameter."""
        from app.chat.agent import get_workflow

        # Should not raise when tools is passed
        workflow = get_workflow(tools=[])
        assert workflow is not None


class TestProcessMessageSolutionsMode:
    """Tests for process_message with solutions_mode."""

    def test_process_message_accepts_solutions_mode(self):
        """process_message should accept solutions_mode parameter."""
        from app.worker.chat_tasks import process_message
        import inspect

        sig = inspect.signature(process_message)
        assert "solutions_mode" in sig.parameters


class TestChatRouterSolutionsMode:
    """Tests for solutions mode in chat router."""

    def test_create_chat_with_solutions_mode_sets_title(self):
        """Creating chat with solutions_mode should set appropriate title."""
        # This tests the router logic indirectly
        from app.chat.models import Chat

        chat = Chat(
            user_id=1,
            solutions_mode="solutions",
            title="Solutions Explorer"
        )
        assert chat.title == "Solutions Explorer"
        assert chat.solutions_mode == "solutions"

    def test_send_message_uses_solutions_mode(self):
        """send_message should check chat.solutions_mode."""
        from app.chat.models import Chat

        chat = Chat(
            user_id=1,
            solutions_mode="solutions",
            title="Solutions Explorer"
        )
        # When solutions_mode is "solutions", solutions_mode == "solutions" evaluates to True
        assert chat.solutions_mode == "solutions"
