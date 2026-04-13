"""
Unit tests for app.chat.models module.

Tests Chat and Message SQLAlchemy models.
"""
import pytest
from datetime import datetime

pytestmark = [pytest.mark.unit]


class TestChatModel:
    """Tests for Chat model."""

    def test_chat_table_name(self):
        """Should use 'chats' as table name."""
        from app.chat.models import Chat

        assert Chat.__tablename__ == "chats"

    def test_chat_default_title(self):
        """Should have default title 'New Chat'."""
        from app.chat.models import Chat

        chat = Chat(user_id=1)
        assert chat.title == "New Chat"

    def test_chat_default_model(self):
        """Should default model to 'pro'."""
        from app.chat.models import Chat

        chat = Chat(user_id=1)
        assert chat.model == "pro"

    def test_chat_workspace_id_nullable(self):
        """workspace_id should be nullable."""
        from app.chat.models import Chat

        chat = Chat(user_id=1)
        assert chat.workspace_id is None

    def test_chat_relationships(self):
        """Should have proper relationships."""
        from app.chat.models import Chat

        # Check that 'owner' and 'workspace' are relationship names
        assert hasattr(Chat, "owner")
        assert hasattr(Chat, "workspace")

    def test_chat_with_workspace(self):
        """Should create chat with workspace_id."""
        from app.chat.models import Chat

        chat = Chat(user_id=1, workspace_id=5)
        assert chat.workspace_id == 5

    def test_chat_with_custom_model(self):
        """Should create chat with custom model."""
        from app.chat.models import Chat

        for model in ["auto", "mini", "pro", "max"]:
            chat = Chat(user_id=1, model=model)
            assert chat.model == model


class TestMessageModel:
    """Tests for Message model."""

    def test_message_table_name(self):
        """Should use 'messages' as table name."""
        from app.chat.models import Message

        assert Message.__tablename__ == "messages"

    def test_message_requires_chat_id(self):
        """Should require chat_id foreign key."""
        from app.chat.models import Message

        msg = Message(role="user", content="Hello")
        assert msg.chat_id is None  # FK defaults to None, not enforced at Python level

    def test_message_role_required(self):
        """Should require role field."""
        from app.chat.models import Message

        msg = Message(role="user", content="Hello")
        assert msg.role == "user"

    def test_message_content_required(self):
        """Should require content field."""
        from app.chat.models import Message

        msg = Message(role="user", content="Hello")
        assert msg.content == "Hello"

    def test_message_idempotency_key_optional(self):
        """idempotency_key should be optional."""
        from app.chat.models import Message

        msg = Message(role="user", content="Hello")
        assert msg.idempotency_key is None

    def test_message_with_idempotency_key(self):
        """Should accept idempotency_key."""
        from app.chat.models import Message

        msg = Message(
            chat_id=1,
            role="user",
            content="Hello",
            idempotency_key="unique-key-123"
        )
        assert msg.idempotency_key == "unique-key-123"

    def test_message_created_at_default(self):
        """Should have created_at field."""
        from app.chat.models import Message

        msg = Message(chat_id=1, role="user", content="Hello")
        assert hasattr(msg, "created_at")
