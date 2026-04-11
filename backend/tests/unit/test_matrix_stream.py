# backend/tests/unit/test_matrix_stream.py
"""
Unit tests for app.matrix.stream — Redis SSE streaming helpers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestPublishEvent:
    """Tests for publish_event."""

    @patch("app.matrix.stream.get_redis")
    async def test_publish_event_sends_to_channel(self, mock_get_redis):
        from app.matrix.stream import publish_event

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await publish_event(42, {"type": "status", "event": "start"})

        mock_client.publish.assert_called_once_with(
            "matrix_stream_42",
            json.dumps({"type": "status", "event": "start"}),
        )


class TestSetProcessingFlag:
    """Tests for set_processing_flag and clear_processing_flag."""

    @patch("app.matrix.stream.get_redis")
    async def test_set_processing_flag_creates_key_with_ttl(self, mock_get_redis):
        from app.matrix.stream import set_processing_flag

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await set_processing_flag(99)

        mock_client.setex.assert_called_once_with("matrix_processing_99", 3600, "1")

    @patch("app.matrix.stream.get_redis")
    async def test_clear_processing_flag_deletes_key(self, mock_get_redis):
        from app.matrix.stream import clear_processing_flag

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await clear_processing_flag(99)

        mock_client.delete.assert_called_once_with("matrix_processing_99")

    @patch("app.matrix.stream.get_redis")
    async def test_get_processing_status_returns_true_when_set(self, mock_get_redis):
        from app.matrix.stream import get_processing_status

        mock_client = AsyncMock()
        mock_client.get.return_value = "1"
        mock_get_redis.return_value = mock_client

        result = await get_processing_status(99)

        assert result is True
        mock_client.get.assert_called_once_with("matrix_processing_99")

    @patch("app.matrix.stream.get_redis")
    async def test_get_processing_status_returns_false_when_missing(self, mock_get_redis):
        from app.matrix.stream import get_processing_status

        mock_client = AsyncMock()
        mock_client.get.return_value = None
        mock_get_redis.return_value = mock_client

        result = await get_processing_status(99)

        assert result is False


class TestMatrixStatePersistence:
    """Tests for save_matrix_state and get_matrix_state."""

    @patch("app.matrix.stream.get_redis")
    async def test_save_matrix_state_stores_json_with_ttl(self, mock_get_redis):
        from app.matrix.stream import save_matrix_state

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        state = {"status": "done", "parameters": [{"name": "Power", "states": ["A", "B"]}]}
        await save_matrix_state(7, state)

        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args
        assert call_args[0][0] == "matrix_state_7"
        assert call_args[0][1] == 86400  # default TTL
        assert json.loads(call_args[0][2]) == state

    @patch("app.matrix.stream.get_redis")
    async def test_save_matrix_state_custom_ttl(self, mock_get_redis):
        from app.matrix.stream import save_matrix_state

        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        await save_matrix_state(7, {"key": "val"}, ttl=3600)

        call_args = mock_client.setex.call_args
        assert call_args[0][1] == 3600

    @patch("app.matrix.stream.get_redis")
    async def test_get_matrix_state_returns_parsed_dict(self, mock_get_redis):
        from app.matrix.stream import get_matrix_state

        mock_client = AsyncMock()
        stored = '{"status": "done", "count": 3}'
        mock_client.get.return_value = stored
        mock_get_redis.return_value = mock_client

        result = await get_matrix_state(7)

        assert result == {"status": "done", "count": 3}
        mock_client.get.assert_called_once_with("matrix_state_7")

    @patch("app.matrix.stream.get_redis")
    async def test_get_matrix_state_returns_none_when_missing(self, mock_get_redis):
        from app.matrix.stream import get_matrix_state

        mock_client = AsyncMock()
        mock_client.get.return_value = None
        mock_get_redis.return_value = mock_client

        result = await get_matrix_state(7)

        assert result is None


class TestSubscribeStream:
    """Tests for subscribe_stream."""

    @patch("app.matrix.stream.get_redis")
    async def test_subscribe_stream_returns_pubsub(self, mock_get_redis):
        from app.matrix.stream import subscribe_stream

        mock_client = AsyncMock()
        # pubsub() is NOT async - it returns a PubSub object directly
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        mock_get_redis.return_value = mock_client

        result = await subscribe_stream(42)

        assert result == mock_pubsub
        mock_pubsub.subscribe.assert_called_once_with("matrix_stream_42")
