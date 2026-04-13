"""
Tests for app/core/async_bridge.py
"""
import asyncio
import pytest

from app.core.async_bridge import (
    run_async_from_sync,
    AsyncBridgeError,
    AsyncBridgeTimeoutError,
)


class TestRunAsyncFromSync:
    """Tests for run_async_from_sync function."""

    @pytest.mark.asyncio
    async def test_normal_execution_no_running_loop(self):
        """Without a running loop, should use asyncio.run() directly."""
        async def dummy_coro():
            return 42

        result = run_async_from_sync(dummy_coro())
        assert result == 42

    @pytest.mark.asyncio
    async def test_normal_execution_with_value(self):
        """Async coroutine returns expected value."""
        async def compute():
            await asyncio.sleep(0.01)
            return "hello"

        result = run_async_from_sync(compute())
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_normal_execution_with_timeout_success(self):
        """Timeout does not fire when coroutine completes in time."""
        async def slow_but_under_timeout():
            await asyncio.sleep(0.05)
            return "done"

        result = run_async_from_sync(slow_but_under_timeout(), timeout=1.0)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_raises_async_bridge_timeout_error(self):
        """Exceeding timeout raises AsyncBridgeTimeoutError."""
        async def slow_coro():
            await asyncio.sleep(10.0)
            return "done"

        with pytest.raises(AsyncBridgeTimeoutError) as exc_info:
            run_async_from_sync(slow_coro(), timeout=0.01)

        assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exception_propagates_with_context(self):
        """Exceptions from coroutine are propagated with original context."""
        async def failing_coro():
            raise ValueError("original error message")

        with pytest.raises(AsyncBridgeError) as exc_info:
            run_async_from_sync(failing_coro())

        # Should contain original exception info
        error_message = str(exc_info.value)
        assert "ValueError" in error_message
        assert "original error message" in error_message

    @pytest.mark.asyncio
    async def test_exception_propagates_via_thread_fallback(self):
        """When running inside an existing loop, exceptions still propagate correctly."""
        async def failing_coro():
            raise RuntimeError("thread fallback error")

        # Simulate being inside a running loop
        async def outer():
            # This runs inside an existing loop
            return run_async_from_sync(failing_coro())

        with pytest.raises(AsyncBridgeError) as exc_info:
            asyncio.run(outer())

        error_message = str(exc_info.value)
        assert "RuntimeError" in error_message
        assert "thread fallback error" in error_message

    @pytest.mark.asyncio
    async def test_thread_fallback_with_timeout(self):
        """Timeout works correctly when using thread fallback."""
        async def slow_coro():
            await asyncio.sleep(10.0)
            return "done"

        async def outer():
            return run_async_from_sync(slow_coro(), timeout=0.01)

        with pytest.raises(AsyncBridgeTimeoutError):
            asyncio.run(outer())

    @pytest.mark.asyncio
    async def test_sync_and_async_boundary(self):
        """Verify the bridge correctly handles sync -> async boundary."""
        received_values = []

        async def async_task():
            await asyncio.sleep(0.01)
            received_values.append("async")
            return len(received_values)

        result = run_async_from_sync(async_task())
        assert result == 1
        assert "async" in received_values
