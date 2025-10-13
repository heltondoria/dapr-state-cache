"""
Bridge between synchronous and asynchronous execution contexts.

Provides transparent execution of cache operations in both sync and async
environments using ThreadPoolExecutor and event loop detection.
"""

import asyncio
import atexit
import concurrent.futures
import inspect
import logging
import os
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

from .constants import MAX_THREAD_WORKERS, THREAD_POOL_PREFIX

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Global ThreadPoolExecutor for sync operations in async context
_thread_pool: concurrent.futures.ThreadPoolExecutor | None = None


def get_thread_pool() -> concurrent.futures.ThreadPoolExecutor:
    """Get or create the global thread pool for sync operations.

    Creates a ThreadPoolExecutor with configuration based on CPU count
    following Python's default pattern: min(MAX_WORKERS, (os.cpu_count() or 1) + 4).

    Returns:
        Global ThreadPoolExecutor instance
    """
    global _thread_pool

    if _thread_pool is None:
        max_workers = min(MAX_THREAD_WORKERS, (os.cpu_count() or 1) + 4)
        _thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=THREAD_POOL_PREFIX
        )
        logger.debug(f"Created ThreadPoolExecutor with {max_workers} workers")

    return _thread_pool


def shutdown_thread_pool() -> None:
    """Shutdown the global thread pool.

    This is primarily used for testing and cleanup.
    In normal operation, the thread pool will be cleaned up
    when the process exits.
    """
    global _thread_pool

    if _thread_pool is not None:
        logger.debug("Shutting down ThreadPoolExecutor")
        _thread_pool.shutdown(wait=True)
        _thread_pool = None


# Register cleanup for process exit
atexit.register(shutdown_thread_pool)


class SyncAsyncBridge:
    """Bridge for transparent sync/async execution.

    Handles the execution of cache operations in both synchronous and
    asynchronous contexts by:

    1. Detecting the current execution context (sync vs async)
    2. Using appropriate execution strategy:
       - Async context: direct await for async functions
       - Sync context: asyncio.run() for async functions
       - Mixed context: ThreadPoolExecutor for sync functions in async

    Features:
    - Automatic context detection
    - Event loop management
    - Thread pool execution for blocking operations
    - Proper exception handling and propagation
    - Support for both callable and awaitable operations

    Thread Safety:
    - Safe for concurrent use
    - Uses separate threads for sync operations in async context
    - Proper isolation of event loops
    """

    def __init__(self, thread_pool: concurrent.futures.ThreadPoolExecutor | None = None) -> None:
        """Initialize sync/async bridge.

        Args:
            thread_pool: Optional custom thread pool (uses global if None)
        """
        self._thread_pool = thread_pool

    @property
    def thread_pool(self) -> concurrent.futures.ThreadPoolExecutor:
        """Get the thread pool for this bridge."""
        return self._thread_pool or get_thread_pool()

    async def run_async(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """Run an async function in async context.

        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the async function
        """
        logger.debug(f"Running async function {func.__name__} in async context")
        return await func(*args, **kwargs)

    async def run_sync_in_async(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a sync function in async context using thread pool.

        Args:
            func: Sync function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the sync function
        """
        logger.debug(f"Running sync function {func.__name__} in async context via thread pool")

        # Get the current event loop
        loop = asyncio.get_running_loop()

        # Execute sync function in thread pool
        return await loop.run_in_executor(self.thread_pool, lambda: func(*args, **kwargs))

    def run_async_in_sync(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """Run an async function in sync context.

        Uses different strategies based on whether an event loop is running:
        1. If no loop is running: Use asyncio.run()
        2. If loop is running: Execute in thread pool with new event loop

        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the async function
        """
        logger.debug(f"Running async function {func.__name__} in sync context")

        try:
            # Check if event loop is already running
            asyncio.get_running_loop()

            # Event loop is running, we need to execute in thread pool
            logger.debug("Event loop detected, using thread pool for async function")
            return self._run_async_in_thread(func, *args, **kwargs)

        except RuntimeError:
            # No event loop running, we can use asyncio.run()
            logger.debug("No event loop detected, using asyncio.run()")
            coro = func(*args, **kwargs)
            return asyncio.run(coro)  # type: ignore[arg-type]

    def _run_async_in_thread(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """Run async function in thread pool with new event loop.

        This is used when we need to run an async function from sync context
        but there's already an event loop running in the current thread.

        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the async function
        """

        def run_in_new_loop() -> T:
            # Create new event loop for this thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)

            try:
                return new_loop.run_until_complete(func(*args, **kwargs))
            finally:
                new_loop.close()
                asyncio.set_event_loop(None)

        # Submit to thread pool and wait for result
        future = self.thread_pool.submit(run_in_new_loop)
        return future.result()

    def run_sync(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a sync function in sync context.

        Args:
            func: Sync function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the sync function
        """
        logger.debug(f"Running sync function {func.__name__} in sync context")
        return func(*args, **kwargs)

    async def execute_auto(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Automatically execute function based on its type and current context.

        Determines the appropriate execution strategy:
        - Async function in async context: direct await
        - Sync function in async context: thread pool execution
        - Preserves original function behavior and exceptions

        Args:
            func: Function to execute (sync or async)
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function execution
        """
        if inspect.iscoroutinefunction(func):
            # Async function - await it directly
            return await self.run_async(func, *args, **kwargs)
        else:
            # Sync function - run in thread pool
            return await self.run_sync_in_async(func, *args, **kwargs)

    def execute_auto_sync(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Automatically execute function in sync context.

        Determines the appropriate execution strategy:
        - Sync function: direct execution
        - Async function: run with event loop handling

        Args:
            func: Function to execute (sync or async)
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function execution
        """
        if inspect.iscoroutinefunction(func):
            # Async function - handle event loop
            return self.run_async_in_sync(func, *args, **kwargs)
        else:
            # Sync function - execute directly
            return self.run_sync(func, *args, **kwargs)

    @staticmethod
    def is_async_context() -> bool:
        """Check if currently running in async context.

        Returns:
            True if in async context (event loop running), False otherwise
        """
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    @staticmethod
    def wrap_for_sync_context(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
        """Wrap an async function to be callable from sync context.

        Args:
            func: Async function to wrap

        Returns:
            Sync function that runs the async function appropriately
        """
        bridge = SyncAsyncBridge()

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return bridge.run_async_in_sync(func, *args, **kwargs)

        return wrapper

    @staticmethod
    def wrap_for_async_context(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
        """Wrap a sync function to be awaitable in async context.

        Args:
            func: Sync function to wrap

        Returns:
            Async function that runs the sync function in thread pool
        """
        bridge = SyncAsyncBridge()

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await bridge.run_sync_in_async(func, *args, **kwargs)

        return wrapper


# Global bridge instance for convenience
_default_bridge: SyncAsyncBridge | None = None


def get_default_bridge() -> SyncAsyncBridge:
    """Get the default SyncAsyncBridge instance.

    Returns:
        Default SyncAsyncBridge instance
    """
    global _default_bridge

    if _default_bridge is None:
        _default_bridge = SyncAsyncBridge()
        logger.debug("Created default SyncAsyncBridge instance")

    return _default_bridge


def reset_default_bridge() -> None:
    """Reset the default bridge (primarily for testing).

    Forces creation of a new default bridge on next access.
    """
    global _default_bridge
    _default_bridge = None


# Convenience functions using default bridge
async def execute_auto(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute function automatically in async context using default bridge.

    Args:
        func: Function to execute (sync or async)
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Result of function execution
    """
    return await get_default_bridge().execute_auto(func, *args, **kwargs)


def execute_auto_sync(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Execute function automatically in sync context using default bridge.

    Args:
        func: Function to execute (sync or async)
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Result of function execution
    """
    return get_default_bridge().execute_auto_sync(func, *args, **kwargs)


def is_async_context() -> bool:
    """Check if currently in async context.

    Returns:
        True if in async context, False otherwise
    """
    return SyncAsyncBridge.is_async_context()


def wrap_for_sync_context(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """Wrap async function for sync context.

    Args:
        func: Async function to wrap

    Returns:
        Sync-callable version of the function
    """
    return SyncAsyncBridge.wrap_for_sync_context(func)


def wrap_for_async_context(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    """Wrap sync function for async context.

    Args:
        func: Sync function to wrap

    Returns:
        Async-awaitable version of the function
    """
    return SyncAsyncBridge.wrap_for_async_context(func)


def _reset_default_bridge() -> None:
    """Reset the default bridge instance.

    This is primarily used for testing to ensure clean state
    between test runs.
    """
    global _default_bridge
    _default_bridge = None
    logger.debug("Reset default SyncAsyncBridge instance")
