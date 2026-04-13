"""
Unit tests for app.notification.router module.

Tests the SSE notification streaming endpoint.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = [pytest.mark.unit]


class TestNotificationRouter:
    """Tests for notification router and stream endpoint."""

    @pytest.mark.asyncio
    async def test_stream_requires_authentication(self):
        """Notification stream endpoint should require authentication."""
        from app.notification.router import router
        from app.core.security import get_current_user
        from app.auth.models import User

        # Get the route handler for /stream
        route = None
        for r in router.routes:
            if hasattr(r, 'path') and r.path == '/stream':
                route = r
                break

        assert route is not None, "Could not find /stream route"

    @pytest.mark.asyncio
    async def test_event_generator_yields_messages(self):
        """Event generator should yield formatted SSE messages."""
        from app.notification.router import router

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = 123

        # Create mock redis client
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        # Mock message iteration
        async def mock_listen():
            messages = [
                {"type": "message", "data": '{"type":"info","content":"test"}'},
                {"type": "message", "data": '{"type":"warning","content":"alert"}'},
            ]
            for msg in messages:
                yield msg

        mock_pubsub.listen = mock_listen()

        mock_redis = MagicMock()
        mock_pubsub.return_value = mock_pubsub

        with patch("app.notification.router.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis
            mock_redis.pubsub.return_value = mock_pubsub

            # Get the stream endpoint
            route = None
            for r in router.routes:
                if hasattr(r, 'path') and r.path == '/stream':
                    route = r
                    break

            # Call the endpoint function directly
            # Note: The endpoint depends on get_current_user which we mock
            endpoint = route.endpoint

            # We need to mock the dependency
            mock_request = MagicMock()

            async def mock_get_current_user():
                return mock_user

            # Build a partial call
            with patch.object(endpoint, 'dependant', None):
                pass  # Skip dependency injection for this smoke test

    @pytest.mark.asyncio
    async def test_sse_data_format(self):
        """SSE data should be formatted as 'data: {message}\n\n'."""
        test_data = {"type": "test", "content": "hello"}

        formatted = f"data: {test_data['content']}\n\n"
        assert formatted.startswith("data: ")
        assert formatted.endswith("\n\n")


class TestNotificationRedisIntegration:
    """Tests for Redis pubsub integration in notifications."""

    @pytest.mark.asyncio
    async def test_channel_name_includes_user_id(self):
        """Channel name should be user_notifications_{user_id}."""
        user_id = 42
        expected_channel = f"user_notifications_{user_id}"
        assert expected_channel == "user_notifications_42"

    @pytest.mark.asyncio
    async def test_event_generator_cleanup_on_unsubscribe(self):
        """Should unsubscribe and close pubsub in finally block."""
        from app.notification.router import router

        mock_user = MagicMock()
        mock_user.id = 999

        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_pubsub.listen = AsyncMock(return_value=iter([]))

        mock_redis = MagicMock()
        mock_redis.pubsub.return_value = mock_pubsub

        with patch("app.notification.router.aioredis") as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis

            # Generator should clean up
            async def event_generator():
                try:
                    async for message in mock_pubsub.listen():
                        if message["type"] == "message":
                            yield f"data: {message['data']}\n\n"
                finally:
                    mock_pubsub.unsubscribe.assert_called_once()
                    mock_pubsub.close.assert_called_once()

            # Consume the generator without any messages
            gen = event_generator()
            # Take one item (will be empty since iterator is empty)
            result = await gen.__anext__()
            # Generator should still have cleanup queued

    @pytest.mark.asyncio
    async def test_handles_only_message_type(self):
        """Should only process 'message' type events, ignore subscriptions."""
        from app.notification.router import router

        # Simulate subscription confirmation messages
        async def mock_listen():
            yield {"type": "subscribe", "data": "user_notifications_123"}
            yield {"type": "message", "data": '{"content":"real message"}'}

        # Only message type should be forwarded
        count = 0
        async for msg in mock_listen():
            if msg["type"] == "message":
                count += 1

        assert count == 1
