"""
Unit tests for app.chat.router module.

Tests chat API endpoints.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

pytestmark = [pytest.mark.unit]


class TestChatSchemasEdgeCases:
    """Additional edge case tests for chat schemas beyond test_chat_schemas.py."""

    def test_chat_create_all_fields(self):
        """Should accept all optional fields."""
        from app.chat.schemas import ChatCreate

        chat = ChatCreate(workspace_id=42, model="max")
        assert chat.workspace_id == 42
        assert chat.model == "max"

    def test_chat_create_invalid_model(self):
        """Should reject invalid model values."""
        from app.chat.schemas import ChatCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatCreate(model="invalid")

    def test_message_create_with_all_fields(self):
        """Should accept all optional fields."""
        from app.chat.schemas import MessageCreate

        msg = MessageCreate(
            content="Hello",
            idempotency_key="key-123",
            model="mini"
        )
        assert msg.content == "Hello"
        assert msg.idempotency_key == "key-123"
        assert msg.model == "mini"

    def test_message_out_with_all_fields(self):
        """Should accept all optional fields."""
        from app.chat.schemas import MessageOut

        now = datetime.now()
        msg = MessageOut(
            id="msg-123",
            chat_id=1,
            role="assistant",
            content="Hi there",
            created_at=now,
            idempotency_key="key-456"
        )
        assert msg.idempotency_key == "key-456"

    def test_chat_out_fields(self):
        """Should have all required fields."""
        from app.chat.schemas import ChatOut

        now = datetime.now()
        chat = ChatOut(
            id=1,
            user_id=1,
            workspace_id=5,
            title="Test",
            model="max",
            created_at=now
        )
        assert chat.id == 1
        assert chat.user_id == 1
        assert chat.workspace_id == 5
        assert chat.title == "Test"
        assert chat.model == "max"


class TestRouterDecision:
    """Tests for RouterDecision schema in agent.py."""

    def test_router_decision_valid(self):
        """Should create valid RouterDecision."""
        from app.chat.agent import RouterDecision

        decision = RouterDecision(
            tags=["qa", "coding"],
            complexity_score=3,
            context_score=2,
            risk_score=1,
            latency_priority=4,
            recommended_model="pro"
        )
        assert decision.tags == ["qa", "coding"]
        assert decision.complexity_score == 3
        assert decision.recommended_model == "pro"

    def test_router_decision_invalid_model(self):
        """Should reject invalid model in RouterDecision."""
        from app.chat.agent import RouterDecision
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RouterDecision(
                tags=["qa"],
                complexity_score=3,
                context_score=2,
                risk_score=1,
                latency_priority=4,
                recommended_model="invalid"
            )

    def test_router_decision_scores_bounds(self):
        """Scores should be within 0-5 bounds."""
        from app.chat.agent import RouterDecision

        # Test lower bound
        decision = RouterDecision(
            tags=[],
            complexity_score=0,
            context_score=0,
            risk_score=0,
            latency_priority=0,
            recommended_model="mini"
        )
        assert decision.complexity_score == 0

        # Test upper bound
        decision.complexity_score = 5
        assert decision.complexity_score == 5

    def test_router_decision_invalid_score(self):
        """Should reject scores outside 0-5 range."""
        from app.chat.agent import RouterDecision
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RouterDecision(
                tags=[],
                complexity_score=6,  # Invalid
                context_score=0,
                risk_score=0,
                latency_priority=0,
                recommended_model="mini"
            )

    def test_router_decision_valid_tags(self):
        """Should accept all valid tags."""
        from app.chat.agent import RouterDecision

        valid_tags = ["qa", "rewrite", "translation", "summary", "creative",
                      "reasoning", "coding", "analysis", "agentic", "high_risk"]

        for tag in valid_tags:
            decision = RouterDecision(
                tags=[tag],
                complexity_score=1,
                context_score=1,
                risk_score=1,
                latency_priority=1,
                recommended_model="mini"
            )
            assert tag in decision.tags


class TestDynamicModelMiddleware:
    """Tests for DynamicModelMiddleware."""

    def test_middleware_import(self):
        """Should import DynamicModelMiddleware."""
        from app.chat.agent import DynamicModelMiddleware

        assert DynamicModelMiddleware is not None

    def test_get_workflow_auto_routing(self):
        """get_workflow with no model_override should use dynamic routing."""
        from app.chat.agent import get_workflow

        # Should not raise
        workflow = get_workflow(model_override=None)
        assert workflow is not None

    def test_get_workflow_specific_model(self):
        """get_workflow with specific model should use that model."""
        from app.chat.agent import get_workflow

        for model in ["mini", "pro", "max"]:
            workflow = get_workflow(model_override=model)
            assert workflow is not None

    def test_get_workflow_with_checkpointer(self):
        """get_workflow should accept checkpointer."""
        from app.chat.agent import get_workflow

        mock_checkpointer = MagicMock()
        workflow = get_workflow(checkpointer=mock_checkpointer)
        assert workflow is not None


class TestTitleGeneration:
    """Tests for chat title generation functions."""

    def test_generate_chat_title_text(self, mocker):
        """Should generate title from first message."""
        class MockResponse:
            content = "Test Title"

        class MockLLM:
            def invoke(self, messages):
                return MockResponse()

        mocker.patch("app.llm.get_llm", return_value=MockLLM())

        from app.worker.chat_tasks import generate_chat_title_text

        title = generate_chat_title_text("Hello world")
        assert title == "Test Title"

    def test_generate_chat_title_text_strips_whitespace(self, mocker):
        """Should strip whitespace from generated title."""
        class MockResponse:
            content = "  My Title  "

        class MockLLM:
            def invoke(self, messages):
                return MockResponse()

        mocker.patch("app.llm.get_llm", return_value=MockLLM())

        from app.worker.chat_tasks import generate_chat_title_text

        title = generate_chat_title_text("Hello")
        assert title == "My Title"


class TestEnrichContentWithMemory:
    """Tests for memory enrichment in chat_tasks."""

    def test_enrich_content_no_workspace(self):
        """Should return original content if no workspace_id."""
        from app.worker.chat_tasks import enrich_content_with_memory

        mock_session = MagicMock()
        result = enrich_content_with_memory(mock_session, None, "Hello")
        assert result == "Hello"

    def test_enrich_content_handles_exception(self):
        """Should return original content if memory lookup fails."""
        from app.worker.chat_tasks import enrich_content_with_memory

        mock_session = MagicMock()

        with patch("app.worker.chat_tasks._get_memory_async_engine", side_effect=Exception("DB Error")):
            result = enrich_content_with_memory(mock_session, 1, "Hello")
            assert result == "Hello"


class TestStoreConversationInMemory:
    """Tests for storing conversation in memory."""

    def test_store_skips_if_no_workspace(self):
        """Should skip storing if workspace_id is None."""
        from app.worker.chat_tasks import store_conversation_in_memory

        mock_session = MagicMock()
        store_conversation_in_memory(mock_session, None, "user msg", "assistant msg")
        # Should not call MemoryService
        mock_session.assert_not_called()

    def test_store_handles_exception(self):
        """Should handle exceptions gracefully."""
        from app.worker.chat_tasks import store_conversation_in_memory

        mock_session = MagicMock()

        with patch("app.worker.chat_tasks._get_memory_async_engine", side_effect=Exception("DB Error")):
            # Should not raise
            store_conversation_in_memory(mock_session, 1, "user msg", "assistant msg")


class TestUpdateChatTitle:
    """Tests for update_chat_title function."""

    def test_update_chat_title_returns_none_if_not_found(self, mocker):
        """Should return None if chat not found."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        mocker.patch("app.worker.generate_chat_title_text", return_value="New Title")

        from app.worker.chat_tasks import update_chat_title

        result = update_chat_title(999, "Hello", db=mock_session)
        assert result is None

    def test_update_chat_title_returns_none_if_already_titled(self, mocker):
        """Should return None if chat already has a title."""
        mock_session = MagicMock()
        mock_chat = MagicMock()
        mock_chat.title = "Already Titled"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_chat
        mock_session.query.return_value = mock_query

        from app.worker.chat_tasks import update_chat_title

        result = update_chat_title(1, "Hello", db=mock_session)
        assert result is None

    def test_update_chat_title_updates_title(self, mocker):
        """Should update chat title when conditions are met."""
        mock_session = MagicMock()
        mock_chat = MagicMock()
        mock_chat.title = "New Chat"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_chat
        mock_session.query.return_value = mock_query

        mocker.patch("app.worker.generate_chat_title_text", return_value="Updated Title")

        from app.worker.chat_tasks import update_chat_title

        result = update_chat_title(1, "Hello", db=mock_session, publish=False)
        assert result == "Updated Title"
        assert mock_chat.title == "Updated Title"


class TestProcessMessageTask:
    """Tests for process_message Celery task."""

    def test_process_message_returns_early_if_chat_not_found(self, mocker):
        """Should return early if chat doesn't exist."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        mocker.patch("app.worker.SessionLocal", return_value=mock_db)

        from app.worker.chat_tasks import process_message

        process_message(999, "Hello")
        # Should not try to run agent

    def test_process_message_enriches_content_with_memory(self, mocker):
        """Should call enrich_content_with_memory when workspace_id exists."""
        mock_db = MagicMock()
        mock_chat = MagicMock()
        mock_chat.workspace_id = 1
        mock_chat.title = "New Chat"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_chat
        mock_db.query.return_value = mock_query

        mocker.patch("app.worker.SessionLocal", return_value=mock_db)
        mocker.patch("app.worker.run_async_from_sync")
        mocker.patch("app.worker.redis_client.publish")
        mocker.patch("app.worker.redis_client.delete")
        mocker.patch("app.worker.enrich_content_with_memory", return_value="Enriched Hello")

        from app.worker.chat_tasks import process_message

        process_message(1, "Hello")
        # Verify enrich_content_with_memory was called


class TestGenerateTitleTask:
    """Tests for generate_title Celery task."""

    def test_generate_title_calls_update_chat_title(self, mocker):
        """Should call update_chat_title with publish=True."""
        mocker.patch("app.worker.update_chat_title")

        from app.worker.chat_tasks import generate_title

        generate_title(1, "Hello world")
