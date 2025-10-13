"""
Deduplication manager for cache miss operations.

Implements thundering herd protection by ensuring only one computation
happens per cache key at a time, with other concurrent requests waiting
for the same result.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DeduplicationManager:
    """Manages deduplication of cache miss computations.

    Prevents thundering herd problem by ensuring that multiple concurrent
    requests for the same cache key only trigger one computation, with
    all requests sharing the result.

    Features:
    - Thread-safe operation using asyncio.Lock
    - Automatic cleanup of completed futures
    - Exception propagation to all waiting requests
    - Memory-efficient (futures removed after completion)

    Thread Safety:
    - Safe for concurrent use within the same event loop
    - Uses asyncio.Lock for atomic operations
    - All operations are async-only
    """

    def __init__(self) -> None:
        """Initialize deduplication manager."""
        self._futures: dict[str, asyncio.Future[Any]] = {}
        self._lock = asyncio.Lock()

    async def deduplicate(self, key: str, compute_func: Callable[[], Awaitable[T]]) -> T:
        """Execute computation with deduplication for the given key.

        If another computation is already running for the same key,
        waits for that computation to complete instead of starting a new one.

        Args:
            key: Cache key to deduplicate on
            compute_func: Async function to call if no computation is running

        Returns:
            Result of the computation (either new or from existing future)

        Raises:
            Any exception raised by compute_func, propagated to all waiters
        """
        async with self._lock:
            # Check if a computation is already running for this key
            if key in self._futures:
                logger.debug(f"Deduplication: waiting for existing computation for key '{key}'")
                future = self._futures[key]
            else:
                logger.debug(f"Deduplication: starting new computation for key '{key}'")
                # Create new future and start computation
                future = asyncio.create_task(self._execute_computation(key, compute_func))
                self._futures[key] = future

        try:
            # Wait for computation to complete (either new or existing)
            result = await future
            logger.debug(f"Deduplication: computation completed for key '{key}'")
            return result
        except Exception as e:
            logger.debug(f"Deduplication: computation failed for key '{key}': {e}")
            raise
        finally:
            # Clean up the future after completion (success or failure)
            # Note: We don't need to acquire the lock here since we're only
            # removing our own future, and multiple tasks can safely attempt
            # to remove the same key
            await self._cleanup_future(key)

    async def _execute_computation(self, key: str, compute_func: Callable[[], Awaitable[T]]) -> T:
        """Execute the computation function.

        Args:
            key: Cache key (for logging)
            compute_func: Function to execute

        Returns:
            Result of computation
        """
        try:
            logger.debug(f"Executing computation for key '{key}'")
            return await compute_func()
        except Exception as e:
            logger.debug(f"Computation failed for key '{key}': {e}")
            raise

    async def _cleanup_future(self, key: str) -> None:
        """Clean up completed future from registry.

        Args:
            key: Cache key to clean up
        """
        async with self._lock:
            # Remove future if it exists and is done
            if key in self._futures and self._futures[key].done():
                logger.debug(f"Cleaning up future for key '{key}'")
                del self._futures[key]

    async def is_computation_running(self, key: str) -> bool:
        """Check if a computation is currently running for the given key.

        Args:
            key: Cache key to check

        Returns:
            True if computation is running, False otherwise
        """
        async with self._lock:
            return key in self._futures and not self._futures[key].done()

    async def cancel_computation(self, key: str) -> bool:
        """Cancel any running computation for the given key.

        Args:
            key: Cache key to cancel computation for

        Returns:
            True if computation was cancelled, False if no computation was running
        """
        async with self._lock:
            if key in self._futures and not self._futures[key].done():
                logger.debug(f"Cancelling computation for key '{key}'")
                future = self._futures[key]
                future.cancel()
                del self._futures[key]
                return True
            return False

    async def get_active_computations(self) -> list[str]:
        """Get list of keys with active computations.

        Returns:
            List of cache keys that have computations running
        """
        async with self._lock:
            return [key for key, future in self._futures.items() if not future.done()]

    async def get_computation_count(self) -> int:
        """Get count of active computations.

        Returns:
            Number of computations currently running
        """
        async with self._lock:
            return len([future for future in self._futures.values() if not future.done()])

    async def clear_all_computations(self) -> int:
        """Cancel all running computations and clear the registry.

        Returns:
            Number of computations that were cancelled
        """
        async with self._lock:
            cancelled_count = 0

            for key, future in list(self._futures.items()):
                if not future.done():
                    logger.debug(f"Cancelling computation for key '{key}' during clear")
                    future.cancel()
                    cancelled_count += 1
                del self._futures[key]

            return cancelled_count


class DeduplicationStats:
    """Statistics for deduplication operations.

    Tracks metrics about deduplication effectiveness and performance.
    """

    def __init__(self) -> None:
        """Initialize deduplication statistics."""
        self.total_requests = 0
        self.deduplicated_requests = 0
        self.unique_computations = 0
        self._lock = asyncio.Lock()

    async def record_request(self, was_deduplicated: bool) -> None:
        """Record a deduplication request.

        Args:
            was_deduplicated: True if request was deduplicated (waited for existing),
                            False if it started a new computation
        """
        async with self._lock:
            self.total_requests += 1
            if was_deduplicated:
                self.deduplicated_requests += 1
            else:
                self.unique_computations += 1

    async def get_stats(self) -> dict[str, Any]:
        """Get current deduplication statistics.

        Returns:
            Dictionary with deduplication metrics
        """
        async with self._lock:
            deduplication_ratio = self.deduplicated_requests / self.total_requests if self.total_requests > 0 else 0.0

            return {
                "total_requests": self.total_requests,
                "deduplicated_requests": self.deduplicated_requests,
                "unique_computations": self.unique_computations,
                "deduplication_ratio": deduplication_ratio,
                "efficiency_percentage": deduplication_ratio * 100,
            }

    async def reset_stats(self) -> None:
        """Reset all statistics to zero."""
        async with self._lock:
            self.total_requests = 0
            self.deduplicated_requests = 0
            self.unique_computations = 0


class InstrumentedDeduplicationManager(DeduplicationManager):
    """DeduplicationManager with built-in statistics collection.

    Extends the basic DeduplicationManager to automatically track
    deduplication effectiveness metrics.
    """

    def __init__(self) -> None:
        """Initialize instrumented deduplication manager."""
        super().__init__()
        self._stats = DeduplicationStats()

    async def deduplicate(self, key: str, compute_func: Callable[[], Awaitable[T]]) -> T:
        """Execute computation with deduplication and statistics tracking.

        Args:
            key: Cache key to deduplicate on
            compute_func: Async function to call if no computation is running

        Returns:
            Result of the computation
        """
        # Check if this will be deduplicated
        async with self._lock:
            was_deduplicated = key in self._futures

        # Record the request
        await self._stats.record_request(was_deduplicated)

        # Execute with deduplication
        return await super().deduplicate(key, compute_func)

    @property
    def stats(self) -> DeduplicationStats:
        """Get access to deduplication statistics."""
        return self._stats

    async def get_stats(self) -> dict[str, Any]:
        """Get current deduplication statistics.

        Returns:
            Dictionary with deduplication metrics
        """
        return await self._stats.get_stats()

    async def reset_stats(self) -> None:
        """Reset deduplication statistics."""
        await self._stats.reset_stats()
