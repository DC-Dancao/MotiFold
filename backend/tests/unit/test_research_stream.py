# backend/tests/unit/test_research_stream.py
"""
Unit tests for app.research.stream — Redis SSE streaming helpers for Deep Research.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestPublishEvent:
    """Tests for publish_event."""

    @patch("app.research.stream.get_redis")
    async def test_publish_event_sends_to_research_channel(self, mock_get_redis):
        from app.research.stream import publish_event

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await publish_event("task-abc", {"type": "status", "event": "start"})

        mock_client.publish.assert_called_once_with(
            "research_stream_task-abc",
            json.dumps({"type": "status", "event": "start"}),
        )


class TestProcessingFlag:
    """Tests for set_processing_flag, clear_processing_flag, get_processing_status."""

    @patch("app.research.stream.get_redis")
    async def test_set_processing_flag_sets_key_with_ttl(self, mock_get_redis):
        from app.research.stream import set_processing_flag

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await set_processing_flag("task-xyz")

        mock_client.setex.assert_called_once_with("research_processing_task-xyz", 3600, "1")

    @patch("app.research.stream.get_redis")
    async def test_clear_processing_flag_deletes_key(self, mock_get_redis):
        from app.research.stream import clear_processing_flag

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await clear_processing_flag("task-xyz")

        mock_client.delete.assert_called_once_with("research_processing_task-xyz")

    @patch("app.research.stream.get_redis")
    async def test_get_processing_status_returns_true_when_set(self, mock_get_redis):
        from app.research.stream import get_processing_status

        mock_client = AsyncMock()
        mock_client.get.return_value = "1"
        mock_get_redis.return_value = mock_client

        result = await get_processing_status("task-xyz")

        assert result is True

    @patch("app.research.stream.get_redis")
    async def test_get_processing_status_returns_false_when_missing(self, mock_get_redis):
        from app.research.stream import get_processing_status

        mock_client = AsyncMock()
        mock_client.get.return_value = None
        mock_get_redis.return_value = mock_client

        result = await get_processing_status("task-xyz")

        assert result is False


class TestResearchStatePersistence:
    """Tests for save_research_state and get_research_state."""

    @patch("app.research.stream.get_redis")
    async def test_save_research_state_stores_json_with_ttl(self, mock_get_redis):
        from app.research.stream import save_research_state

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        state = {"status": "running", "progress": 0.5, "notes": ["note1"]}
        await save_research_state("task-abc", state)

        call_args = mock_client.setex.call_args
        assert call_args[0][0] == "research_state_task-abc"
        assert call_args[0][1] == 86400  # default TTL
        assert json.loads(call_args[0][2]) == state

    @patch("app.research.stream.get_redis")
    async def test_save_research_state_custom_ttl(self, mock_get_redis):
        from app.research.stream import save_research_state

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await save_research_state("task-abc", {"key": "val"}, ttl=3600)

        call_args = mock_client.setex.call_args
        assert call_args[0][1] == 3600

    @patch("app.research.stream.get_redis")
    async def test_get_research_state_returns_parsed_dict(self, mock_get_redis):
        from app.research.stream import get_research_state

        mock_client = AsyncMock()
        stored = '{"status": "done", "progress": 1.0}'
        mock_client.get.return_value = stored
        mock_get_redis.return_value = mock_client

        result = await get_research_state("task-abc")

        assert result == {"status": "done", "progress": 1.0}

    @patch("app.research.stream.get_redis")
    async def test_get_research_state_returns_none_when_missing(self, mock_get_redis):
        from app.research.stream import get_research_state

        mock_client = AsyncMock()
        mock_client.get.return_value = None
        mock_get_redis.return_value = mock_client

        result = await get_research_state("task-abc")

        assert result is None


class TestSubscribeStream:
    """Tests for subscribe_stream."""

    @patch("app.research.stream.get_redis")
    async def test_subscribe_stream_returns_pubsub(self, mock_get_redis):
        from app.research.stream import subscribe_stream

        mock_client = AsyncMock()
        # pubsub() is NOT async - it returns a PubSub object directly
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        mock_get_redis.return_value = mock_client

        result = await subscribe_stream("task-abc")

        assert result == mock_pubsub
        mock_pubsub.subscribe.assert_called_once_with("research_stream_task-abc")
