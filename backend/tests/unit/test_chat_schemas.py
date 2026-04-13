"""
Unit tests for app.chat.schemas module.

Tests Chat and Message schemas.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

pytestmark = [pytest.mark.unit]


class TestChatCreate:
    """Tests for ChatCreate schema."""

    def test_default_model_is_pro(self):
        """Should default model to 'pro'."""
        from app.chat.schemas import ChatCreate

        chat = ChatCreate()
        assert chat.model == "pro"
        assert chat.workspace_id is None

    def test_custom_workspace_id(self):
        """Should accept custom workspace_id."""
        from app.chat.schemas import ChatCreate

        chat = ChatCreate(workspace_id=123)
        assert chat.workspace_id == 123

    def test_valid_model_literals(self):
        """Should accept all valid model literals."""
        from app.chat.schemas import ChatCreate

        for model in ["auto", "mini", "pro", "max"]:
            chat = ChatCreate(model=model)
            assert chat.model == model


class TestChatOut:
    """Tests for ChatOut schema."""

    def test_from_attributes_config(self):
        """Should have from_attributes = True for ORM compatibility."""
        from app.chat.schemas import ChatOut

        assert ChatOut.model_config["from_attributes"] is True

    def test_default_model_is_pro(self):
        """Should default model to 'pro'."""
        from app.chat.schemas import ChatOut

        now = datetime.now()
        chat = ChatOut(
            id=1,
            user_id=1,
            title="Test Chat",
            created_at=now
        )
        assert chat.model == "pro"


class TestMessageCreate:
    """Tests for MessageCreate schema."""

    def test_requires_content(self):
        """Should require content field."""
        from app.chat.schemas import MessageCreate

        with pytest.raises(ValidationError):
            MessageCreate()

    def test_valid_message(self):
        """Should create valid MessageCreate."""
        from app.chat.schemas import MessageCreate

        msg = MessageCreate(content="Hello, world!")
        assert msg.content == "Hello, world!"
        assert msg.idempotency_key is None
        assert msg.model is None

    def test_with_idempotency_key(self):
        """Should accept idempotency_key."""
        from app.chat.schemas import MessageCreate

        msg = MessageCreate(
            content="Hello",
            idempotency_key="unique-key-123"
        )
        assert msg.idempotency_key == "unique-key-123"

    def test_with_model_override(self):
        """Should accept model override."""
        from app.chat.schemas import MessageCreate

        msg = MessageCreate(
            content="Hello",
            model="mini"
        )
        assert msg.model == "mini"


class TestMessageOut:
    """Tests for MessageOut schema."""

    def test_from_attributes_config(self):
        """Should have from_attributes = True for ORM compatibility."""
        from app.chat.schemas import MessageOut

        assert MessageOut.model_config["from_attributes"] is True

    def test_valid_message_out(self):
        """Should create valid MessageOut."""
        from app.chat.schemas import MessageOut

        now = datetime.now()
        msg = MessageOut(
            id=1,
            chat_id=1,
            role="user",
            content="Hello",
            created_at=now
        )
        assert msg.role == "user"
        assert msg.idempotency_key is None

    def test_string_id_allowed(self):
        """Should accept string id (for UUIDs etc)."""
        from app.chat.schemas import MessageOut

        now = datetime.now()
        msg = MessageOut(
            id="msg-uuid-123",
            chat_id=1,
            role="assistant",
            content="Hello",
            created_at=now
        )
        assert msg.id == "msg-uuid-123"
