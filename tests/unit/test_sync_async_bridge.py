"""
Unit tests for SyncAsyncBridge.

Tests sync/async bridge with 100% coverage including thread pool management,
event loop detection, and context switching following AAA pattern and TDD.
"""

import asyncio
import concurrent.futures
import threading
import time
from unittest.mock import Mock, patch

import pytest

from dapr_state_cache.core.sync_async_bridge import (
    SyncAsyncBridge,
    execute_auto,
    execute_auto_sync,
    get_default_bridge,
    get_thread_pool,
    is_async_context,
    reset_default_bridge,
    shutdown_thread_pool,
    wrap_for_async_context,
    wrap_for_sync_context,
)


class TestThreadPoolManagement:
    """Test global thread pool management."""

    def test_get_thread_pool_creates_pool(self) -> None:
        """Test that get_thread_pool creates a ThreadPoolExecutor."""
        # Arrange - ensure no existing pool
        shutdown_thread_pool()

        # Act
        pool = get_thread_pool()

        # Assert
        assert isinstance(pool, concurrent.futures.ThreadPoolExecutor)

        # Cleanup
        shutdown_thread_pool()

    def test_get_thread_pool_reuses_existing(self) -> None:
        """Test that get_thread_pool reuses existing pool."""
        # Arrange - ensure no existing pool
        shutdown_thread_pool()

        # Act
        pool1 = get_thread_pool()
        pool2 = get_thread_pool()

        # Assert
        assert pool1 is pool2

        # Cleanup
        shutdown_thread_pool()

    @patch("os.cpu_count")
    def test_get_thread_pool_worker_calculation(self, mock_cpu_count: Mock) -> None:
        """Test thread pool worker count calculation."""
        # Arrange
        shutdown_thread_pool()
        mock_cpu_count.return_value = 8

        # Act
        pool = get_thread_pool()

        # Assert
        # Should be min(32, 8 + 4) = 12 workers
        assert pool._max_workers == 12

        # Cleanup
        shutdown_thread_pool()

    @patch("os.cpu_count")
    def test_get_thread_pool_none_cpu_count(self, mock_cpu_count: Mock) -> None:
        """Test thread pool with None cpu_count."""
        # Arrange
        shutdown_thread_pool()
        mock_cpu_count.return_value = None

        # Act
        pool = get_thread_pool()

        # Assert
        # Should be min(32, 1 + 4) = 5 workers
        assert pool._max_workers == 5

        # Cleanup
        shutdown_thread_pool()

    def test_shutdown_thread_pool(self) -> None:
        """Test thread pool shutdown."""
        # Arrange
        pool = get_thread_pool()

        # Act
        shutdown_thread_pool()

        # Assert
        # Pool should be shutdown (accessing will raise RuntimeError)
        with pytest.raises(RuntimeError):
            pool.submit(lambda: None)


class TestSyncAsyncBridge:
    """Test SyncAsyncBridge implementation."""

    def test_sync_async_bridge_initialization_default(self) -> None:
        """Test SyncAsyncBridge initialization with defaults."""
        # Arrange & Act
        bridge = SyncAsyncBridge()

        # Assert
        assert bridge._thread_pool is None
        assert isinstance(bridge.thread_pool, concurrent.futures.ThreadPoolExecutor)

    def test_sync_async_bridge_initialization_custom_pool(self) -> None:
        """Test SyncAsyncBridge initialization with custom thread pool."""
        # Arrange
        custom_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # Act
        bridge = SyncAsyncBridge(custom_pool)

        # Assert
        assert bridge._thread_pool is custom_pool
        assert bridge.thread_pool is custom_pool

        # Cleanup
        custom_pool.shutdown()

    @pytest.mark.asyncio
    async def test_run_async_direct_execution(self) -> None:
        """Test direct async function execution."""
        # Arrange
        bridge = SyncAsyncBridge()

        async def test_async_func(x: int) -> int:
            return x * 2

        # Act
        result = await bridge.run_async(test_async_func, 5)

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_run_sync_in_async_thread_pool(self) -> None:
        """Test sync function execution in async context via thread pool."""
        # Arrange
        bridge = SyncAsyncBridge()

        def test_sync_func(x: int) -> int:
            # Verify we're running in a different thread
            return x * 2

        # Act
        result = await bridge.run_sync_in_async(test_sync_func, 5)

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_run_sync_in_async_with_thread_info(self) -> None:
        """Test that sync function runs in different thread."""
        # Arrange
        bridge = SyncAsyncBridge()
        main_thread_id = threading.get_ident()

        def get_thread_id() -> int:
            return threading.get_ident()

        # Act
        worker_thread_id = await bridge.run_sync_in_async(get_thread_id)

        # Assert
        assert worker_thread_id != main_thread_id

    def test_run_async_in_sync_no_loop(self) -> None:
        """Test async function execution in sync context with no event loop."""
        # Arrange
        bridge = SyncAsyncBridge()

        async def test_async_func(x: int) -> int:
            return x * 2

        # Act
        result = bridge.run_async_in_sync(test_async_func, 5)

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_run_async_in_sync_with_existing_loop(self) -> None:
        """Test async function execution when event loop already exists."""
        # Arrange
        bridge = SyncAsyncBridge()

        async def test_async_func(x: int) -> int:
            return x * 2

        def sync_caller() -> int:
            # This will be called from async context, so there's already a loop
            return bridge.run_async_in_sync(test_async_func, 5)

        # Act - run sync function in thread pool, which will detect existing loop
        result = await bridge.run_sync_in_async(sync_caller)

        # Assert
        assert result == 10

    def test_run_sync_direct_execution(self) -> None:
        """Test direct sync function execution."""
        # Arrange
        bridge = SyncAsyncBridge()

        def test_sync_func(x: int) -> int:
            return x * 2

        # Act
        result = bridge.run_sync(test_sync_func, 5)

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_execute_auto_async_function(self) -> None:
        """Test automatic execution of async function."""
        # Arrange
        bridge = SyncAsyncBridge()

        async def test_async_func(x: int) -> int:
            return x * 2

        # Act
        result = await bridge.execute_auto(test_async_func, 5)

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_execute_auto_sync_function(self) -> None:
        """Test automatic execution of sync function in async context."""
        # Arrange
        bridge = SyncAsyncBridge()

        def test_sync_func(x: int) -> int:
            return x * 2

        # Act
        result = await bridge.execute_auto(test_sync_func, 5)

        # Assert
        assert result == 10

    def test_execute_auto_sync_async_function(self) -> None:
        """Test automatic execution of async function in sync context."""
        # Arrange
        bridge = SyncAsyncBridge()

        async def test_async_func(x: int) -> int:
            return x * 2

        # Act
        result = bridge.execute_auto_sync(test_async_func, 5)

        # Assert
        assert result == 10

    def test_execute_auto_sync_sync_function(self) -> None:
        """Test automatic execution of sync function in sync context."""
        # Arrange
        bridge = SyncAsyncBridge()

        def test_sync_func(x: int) -> int:
            return x * 2

        # Act
        result = bridge.execute_auto_sync(test_sync_func, 5)

        # Assert
        assert result == 10

    def test_is_async_context_false_no_loop(self) -> None:
        """Test is_async_context returns False when no loop is running."""
        # Arrange & Act
        result = SyncAsyncBridge.is_async_context()

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_is_async_context_true_with_loop(self) -> None:
        """Test is_async_context returns True when loop is running."""
        # Arrange & Act
        result = SyncAsyncBridge.is_async_context()

        # Assert
        assert result is True

    def test_wrap_for_sync_context(self) -> None:
        """Test wrapping async function for sync context."""

        # Arrange
        async def test_async_func(x: int) -> int:
            return x * 2

        # Act
        wrapped_func = SyncAsyncBridge.wrap_for_sync_context(test_async_func)
        result = wrapped_func(5)

        # Assert
        assert result == 10
        # Verify the wrapper preserves function metadata
        assert wrapped_func.__name__ == test_async_func.__name__

    @pytest.mark.asyncio
    async def test_wrap_for_async_context(self) -> None:
        """Test wrapping sync function for async context."""

        # Arrange
        def test_sync_func(x: int) -> int:
            return x * 2

        # Act
        wrapped_func = SyncAsyncBridge.wrap_for_async_context(test_sync_func)
        result = await wrapped_func(5)

        # Assert
        assert result == 10
        # Verify the wrapper preserves function metadata
        assert wrapped_func.__name__ == test_sync_func.__name__


class TestDefaultBridge:
    """Test default bridge management."""

    def test_get_default_bridge_creates_instance(self) -> None:
        """Test that get_default_bridge creates a SyncAsyncBridge."""
        # Arrange
        reset_default_bridge()

        # Act
        bridge = get_default_bridge()

        # Assert
        assert isinstance(bridge, SyncAsyncBridge)

    def test_get_default_bridge_reuses_instance(self) -> None:
        """Test that get_default_bridge reuses existing instance."""
        # Arrange
        reset_default_bridge()

        # Act
        bridge1 = get_default_bridge()
        bridge2 = get_default_bridge()

        # Assert
        assert bridge1 is bridge2

    def test_reset_default_bridge(self) -> None:
        """Test resetting the default bridge."""
        # Arrange
        bridge1 = get_default_bridge()

        # Act
        reset_default_bridge()
        bridge2 = get_default_bridge()

        # Assert
        assert bridge1 is not bridge2


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_execute_auto_async_function(self) -> None:
        """Test execute_auto convenience function with async function."""

        # Arrange
        async def test_async_func(x: int) -> int:
            return x * 2

        # Act
        result = await execute_auto(test_async_func, 5)

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_execute_auto_sync_function(self) -> None:
        """Test execute_auto convenience function with sync function."""

        # Arrange
        def test_sync_func(x: int) -> int:
            return x * 2

        # Act
        result = await execute_auto(test_sync_func, 5)

        # Assert
        assert result == 10

    def test_execute_auto_sync_async_function(self) -> None:
        """Test execute_auto_sync convenience function with async function."""

        # Arrange
        async def test_async_func(x: int) -> int:
            return x * 2

        # Act
        result = execute_auto_sync(test_async_func, 5)

        # Assert
        assert result == 10

    def test_execute_auto_sync_sync_function(self) -> None:
        """Test execute_auto_sync convenience function with sync function."""

        # Arrange
        def test_sync_func(x: int) -> int:
            return x * 2

        # Act
        result = execute_auto_sync(test_sync_func, 5)

        # Assert
        assert result == 10

    def test_is_async_context_convenience(self) -> None:
        """Test is_async_context convenience function."""
        # Arrange & Act
        result = is_async_context()

        # Assert
        assert result is False

    def test_wrap_for_sync_context_convenience(self) -> None:
        """Test wrap_for_sync_context convenience function."""

        # Arrange
        async def test_async_func(x: int) -> int:
            return x * 2

        # Act
        wrapped_func = wrap_for_sync_context(test_async_func)
        result = wrapped_func(5)

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_wrap_for_async_context_convenience(self) -> None:
        """Test wrap_for_async_context convenience function."""

        # Arrange
        def test_sync_func(x: int) -> int:
            return x * 2

        # Act
        wrapped_func = wrap_for_async_context(test_sync_func)
        result = await wrapped_func(5)

        # Assert
        assert result == 10


class TestErrorHandling:
    """Test error handling in bridge operations."""

    @pytest.mark.asyncio
    async def test_async_function_exception_propagation(self) -> None:
        """Test that exceptions in async functions are properly propagated."""
        # Arrange
        bridge = SyncAsyncBridge()

        async def failing_async_func() -> None:
            raise ValueError("Async error")

        # Act & Assert
        with pytest.raises(ValueError, match="Async error"):
            await bridge.run_async(failing_async_func)

    @pytest.mark.asyncio
    async def test_sync_function_exception_propagation(self) -> None:
        """Test that exceptions in sync functions are properly propagated."""
        # Arrange
        bridge = SyncAsyncBridge()

        def failing_sync_func() -> None:
            raise ValueError("Sync error")

        # Act & Assert
        with pytest.raises(ValueError, match="Sync error"):
            await bridge.run_sync_in_async(failing_sync_func)

    def test_async_function_exception_in_sync_context(self) -> None:
        """Test exception propagation for async function in sync context."""
        # Arrange
        bridge = SyncAsyncBridge()

        async def failing_async_func() -> None:
            raise ValueError("Async error in sync context")

        # Act & Assert
        with pytest.raises(ValueError, match="Async error in sync context"):
            bridge.run_async_in_sync(failing_async_func)

    def test_wrapped_function_exception_propagation(self) -> None:
        """Test exception propagation in wrapped functions."""

        # Arrange
        async def failing_async_func() -> None:
            raise ValueError("Wrapped async error")

        wrapped_func = wrap_for_sync_context(failing_async_func)

        # Act & Assert
        with pytest.raises(ValueError, match="Wrapped async error"):
            wrapped_func()


class TestConcurrency:
    """Test concurrent execution scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_sync_functions_in_async(self) -> None:
        """Test concurrent execution of sync functions in async context."""
        # Arrange
        bridge = SyncAsyncBridge()

        def slow_sync_func(delay: float, value: int) -> int:
            time.sleep(delay)
            return value * 2

        # Act - run multiple sync functions concurrently
        tasks = [bridge.run_sync_in_async(slow_sync_func, 0.1, i) for i in range(3)]
        results = await asyncio.gather(*tasks)

        # Assert
        assert results == [0, 2, 4]

    def test_concurrent_async_functions_in_sync_thread_pool(self) -> None:
        """Test concurrent async functions from sync context using thread pool."""
        # Arrange
        bridge = SyncAsyncBridge()

        async def slow_async_func(delay: float, value: int) -> int:
            await asyncio.sleep(delay)
            return value * 2

        def run_concurrent_async() -> list[int]:
            # This simulates running from sync context where we need thread pool
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(bridge.run_async_in_sync, slow_async_func, 0.1, i) for i in range(3)]
                for future in concurrent.futures.as_completed(futures):
                    results.append(future.result())
            return sorted(results)

        # Act
        results = run_concurrent_async()

        # Assert
        assert results == [0, 2, 4]


class TestIntegration:
    """Integration tests for bridge functionality."""

    @pytest.mark.asyncio
    async def test_mixed_sync_async_chain(self) -> None:
        """Test chaining sync and async functions through bridge."""
        # Arrange
        bridge = SyncAsyncBridge()

        def sync_step1(x: int) -> int:
            return x + 1

        async def async_step2(x: int) -> int:
            await asyncio.sleep(0.01)  # Simulate async work
            return x * 2

        def sync_step3(x: int) -> int:
            return x - 1

        # Act - chain operations
        result1 = await bridge.run_sync_in_async(sync_step1, 5)  # 6
        result2 = await bridge.run_async(async_step2, result1)  # 12
        result3 = await bridge.run_sync_in_async(sync_step3, result2)  # 11

        # Assert
        assert result3 == 11

    def test_bridge_in_different_thread_contexts(self) -> None:
        """Test bridge behavior when used from different threads."""
        # Arrange
        bridge = SyncAsyncBridge()
        results = []

        async def async_worker(thread_id: int) -> int:
            await asyncio.sleep(0.01)
            return thread_id * 10

        def thread_worker(thread_id: int) -> None:
            # Each thread runs its own async function
            result = bridge.run_async_in_sync(async_worker, thread_id)
            results.append(result)

        # Act - run from multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Assert
        assert sorted(results) == [0, 10, 20]

    @pytest.mark.asyncio
    async def test_nested_bridge_calls(self) -> None:
        """Test nested bridge calls (async -> sync -> async)."""
        # Arrange
        bridge = SyncAsyncBridge()

        async def outer_async(x: int) -> int:
            return x + 1

        def middle_sync(x: int) -> int:
            # This sync function calls an async function
            inner_result = bridge.run_async_in_sync(outer_async, x)
            return inner_result * 2

        # Act
        result = await bridge.run_sync_in_async(middle_sync, 5)

        # Assert
        assert result == 12  # (5 + 1) * 2


class TestCleanup:
    """Test cleanup and resource management."""

    def test_thread_pool_cleanup(self) -> None:
        """Test proper cleanup of thread pool resources."""
        # Arrange
        bridge = SyncAsyncBridge()

        # Use the bridge to ensure thread pool is created
        result = bridge.execute_auto_sync(lambda x: x * 2, 5)
        assert result == 10

        # Act - shutdown should work cleanly
        shutdown_thread_pool()

        # Assert - new bridge should get new thread pool
        new_bridge = SyncAsyncBridge()
        result2 = new_bridge.execute_auto_sync(lambda x: x * 3, 5)
        assert result2 == 15

        # Cleanup
        shutdown_thread_pool()

    def test_custom_thread_pool_not_affected_by_global_shutdown(self) -> None:
        """Test that custom thread pools are not affected by global shutdown."""
        # Arrange
        custom_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        bridge = SyncAsyncBridge(custom_pool)

        # Act - shutdown global pool
        shutdown_thread_pool()

        # Assert - bridge with custom pool should still work
        result = bridge.execute_auto_sync(lambda x: x * 2, 5)
        assert result == 10

        # Cleanup
        custom_pool.shutdown()
