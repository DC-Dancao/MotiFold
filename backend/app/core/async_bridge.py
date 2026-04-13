"""
Async bridge utilities for running async code from synchronous contexts.

This module provides a compatibility layer for calling async code from synchronous
entrypoints, primarily intended for Celery task boundaries.

IMPORTANT: This is NOT the recommended path for normal async usage.
- FastAPI async routes should use 'await' directly
- Service/repo layers should prefer pure async or pure sync
- Only use this bridge at clearly-defined sync/async boundaries

Architecture guidelines:
1. FastAPI routes: use 'await' directly
2. Service layer: keep pure async, no sync bridging
3. Celery tasks: sync entrypoint, bridge to async explicitly here
4. This bridge: only at the boundary, never in deep business logic
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Coroutine, Optional, TypeVar

T = TypeVar("T")


class AsyncBridgeError(RuntimeError):
    """Raised when async bridge execution fails."""


class AsyncBridgeTimeoutError(AsyncBridgeError):
    """Raised when async bridge execution times out."""


async def _run_with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout: Optional[float],
) -> T:
    """Run coroutine with optional timeout."""
    if timeout is None:
        return await coro
    return await asyncio.wait_for(coro, timeout=timeout)


def run_async_from_sync(
    coro_func: Coroutine[Any, Any, T] | Callable[[], Coroutine[Any, Any, T]],
    *,
    timeout: Optional[float] = None,
) -> T:
    """
    Execute async code from a synchronous entrypoint.

    This is a compatibility bridge for running async code from synchronous
    contexts such as Celery tasks. It is NOT intended for:
    - Normal FastAPI async request handlers (use 'await' directly)
    - Deep business logic layers
    - Code that already runs inside an async context

    Behavior:
    - If no running event loop exists in current thread: uses asyncio.run()
    - If a running event loop exists (e.g., eventlet/gevent): runs in a
      dedicated thread with its own event loop

    Args:
        coro_func: Either a coroutine to execute directly OR a callable that
                   returns a coroutine. Passing a callable is preferred when
                   running in a thread to avoid event loop association issues.
        timeout: Optional timeout in seconds. Raises AsyncBridgeTimeoutError if exceeded.

    Returns:
        The result of the coroutine

    Raises:
        AsyncBridgeTimeoutError: If coroutine execution exceeds timeout
        AsyncBridgeError: If coroutine execution fails
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop in this thread - safe to use asyncio.run()
        try:
            coro = coro_func() if callable(coro_func) else coro_func
            return asyncio.run(_run_with_timeout(coro, timeout))
        except asyncio.TimeoutError as exc:
            raise AsyncBridgeTimeoutError(
                f"Coroutine timed out after {timeout} seconds."
            ) from exc
        except BaseException as exc:  # noqa: BLE001
            raise AsyncBridgeError(
                f"Coroutine execution failed: {type(exc).__name__}: {exc}"
            ) from exc

    # A loop is already running (eventlet/gevent scenario)
    # Execute in a separate thread with its own event loop
    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def _thread_runner() -> None:
        try:
            coro = coro_func() if callable(coro_func) else coro_func
            result["value"] = asyncio.run(_run_with_timeout(coro, timeout))
        except BaseException as exc:  # noqa: BLE001
            error["exception"] = exc

    thread = threading.Thread(target=_thread_runner)
    thread.start()
    thread.join()

    if "exception" in error:
        exc = error["exception"]
        if isinstance(exc, asyncio.TimeoutError):
            raise AsyncBridgeTimeoutError(
                f"Coroutine timed out after {timeout} seconds."
            ) from exc
        raise AsyncBridgeError(
            f"Coroutine execution failed: {type(exc).__name__}: {exc}"
        ) from exc

    return result["value"]


# Backwards compatibility alias - DEPRECATED, use run_async_from_sync instead
run_async = run_async_from_sync
