"""
Unit tests for orchestration module.

Tests deduplication manager with 100% coverage including concurrency,
error handling, and statistics tracking following AAA pattern and TDD.
"""

import asyncio

import pytest

from dapr_state_cache.orchestration import (
    DeduplicationManager,
    DeduplicationStats,
    InstrumentedDeduplicationManager,
)


class TestDeduplicationManager:
    """Test DeduplicationManager implementation."""

    def test_deduplication_manager_initialization(self) -> None:
        """Test DeduplicationManager initialization."""
        # Arrange & Act
        manager = DeduplicationManager()

        # Assert
        assert manager._futures == {}
        assert isinstance(manager._lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_deduplicate_first_call_starts_computation(self) -> None:
        """Test that first call starts new computation."""
        # Arrange
        manager = DeduplicationManager()
        key = "test:key"
        expected_result = "computed_value"

        async def mock_compute() -> str:
            return expected_result

        # Act
        result = await manager.deduplicate(key, mock_compute)

        # Assert
        assert result == expected_result
        # Future should be cleaned up after completion
        assert key not in manager._futures

    @pytest.mark.asyncio
    async def test_deduplicate_concurrent_calls_share_computation(self) -> None:
        """Test that concurrent calls for same key share computation."""
        # Arrange
        manager = DeduplicationManager()
        key = "test:key"
        call_count = 0

        async def mock_compute() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate work
            return f"result_{call_count}"

        # Act - start multiple concurrent requests
        tasks = [asyncio.create_task(manager.deduplicate(key, mock_compute)) for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # Assert
        # All requests should get the same result
        assert all(result == "result_1" for result in results)
        # Computation should have been called only once
        assert call_count == 1
        # Future should be cleaned up
        assert key not in manager._futures

    @pytest.mark.asyncio
    async def test_deduplicate_different_keys_separate_computations(self) -> None:
        """Test that different keys trigger separate computations."""
        # Arrange
        manager = DeduplicationManager()
        key1 = "test:key1"
        key2 = "test:key2"

        async def mock_compute1() -> str:
            return "result1"

        async def mock_compute2() -> str:
            return "result2"

        # Act
        result1, result2 = await asyncio.gather(
            manager.deduplicate(key1, mock_compute1), manager.deduplicate(key2, mock_compute2)
        )

        # Assert
        assert result1 == "result1"
        assert result2 == "result2"
        assert key1 not in manager._futures
        assert key2 not in manager._futures

    @pytest.mark.asyncio
    async def test_deduplicate_computation_error_propagated_to_all(self) -> None:
        """Test that computation errors are propagated to all waiting requests."""
        # Arrange
        manager = DeduplicationManager()
        key = "test:key"
        error_message = "Computation failed"

        async def failing_compute() -> str:
            await asyncio.sleep(0.01)
            raise ValueError(error_message)

        # Act & Assert
        tasks = [asyncio.create_task(manager.deduplicate(key, failing_compute)) for _ in range(3)]

        # All tasks should raise the same error
        with pytest.raises(ValueError) as exc_info:
            await asyncio.gather(*tasks)

        assert error_message in str(exc_info.value)
        # Future should be cleaned up after error
        assert key not in manager._futures

    @pytest.mark.asyncio
    async def test_deduplicate_sequential_calls_start_new_computations(self) -> None:
        """Test that sequential calls (not concurrent) start separate computations."""
        # Arrange
        manager = DeduplicationManager()
        key = "test:key"
        call_count = 0

        async def mock_compute() -> str:
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # Act - make sequential calls
        result1 = await manager.deduplicate(key, mock_compute)
        result2 = await manager.deduplicate(key, mock_compute)

        # Assert
        assert result1 == "result_1"
        assert result2 == "result_2"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_is_computation_running_with_active_computation(self) -> None:
        """Test checking if computation is running when it is."""
        # Arrange
        manager = DeduplicationManager()
        key = "test:key"
        computation_started = asyncio.Event()
        computation_continue = asyncio.Event()

        async def slow_compute() -> str:
            computation_started.set()
            await computation_continue.wait()
            return "result"

        # Act - start computation but don't let it finish
        task = asyncio.create_task(manager.deduplicate(key, slow_compute))
        await computation_started.wait()  # Wait for computation to start

        is_running = await manager.is_computation_running(key)

        # Cleanup - let computation finish
        computation_continue.set()
        await task

        # Assert
        assert is_running is True

    @pytest.mark.asyncio
    async def test_is_computation_running_with_no_computation(self) -> None:
        """Test checking if computation is running when it's not."""
        # Arrange
        manager = DeduplicationManager()
        key = "test:key"

        # Act
        is_running = await manager.is_computation_running(key)

        # Assert
        assert is_running is False

    @pytest.mark.asyncio
    async def test_cancel_computation_success(self) -> None:
        """Test successful computation cancellation."""
        # Arrange
        manager = DeduplicationManager()
        key = "test:key"
        computation_started = asyncio.Event()

        async def slow_compute() -> str:
            computation_started.set()
            await asyncio.sleep(10)  # Long computation
            return "result"

        # Act - start computation
        task = asyncio.create_task(manager.deduplicate(key, slow_compute))
        await computation_started.wait()  # Wait for computation to start

        cancelled = await manager.cancel_computation(key)

        # Assert
        assert cancelled is True
        assert key not in manager._futures

        # Task should be cancelled
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_cancel_computation_not_running(self) -> None:
        """Test cancellation when no computation is running."""
        # Arrange
        manager = DeduplicationManager()
        key = "test:key"

        # Act
        cancelled = await manager.cancel_computation(key)

        # Assert
        assert cancelled is False

    @pytest.mark.asyncio
    async def test_get_active_computations(self) -> None:
        """Test getting list of active computations."""
        # Arrange
        manager = DeduplicationManager()
        key1 = "test:key1"
        key2 = "test:key2"
        computation_started = asyncio.Event()
        computation_continue = asyncio.Event()

        async def slow_compute() -> str:
            computation_started.set()
            await computation_continue.wait()
            return "result"

        # Act - start computations
        task1 = asyncio.create_task(manager.deduplicate(key1, slow_compute))
        await computation_started.wait()
        computation_started.clear()

        task2 = asyncio.create_task(manager.deduplicate(key2, slow_compute))
        await computation_started.wait()

        active_computations = await manager.get_active_computations()

        # Cleanup
        computation_continue.set()
        await asyncio.gather(task1, task2)

        # Assert
        assert set(active_computations) == {key1, key2}

    @pytest.mark.asyncio
    async def test_get_computation_count(self) -> None:
        """Test getting count of active computations."""
        # Arrange
        manager = DeduplicationManager()
        key = "test:key"
        computation_started = asyncio.Event()
        computation_continue = asyncio.Event()

        async def slow_compute() -> str:
            computation_started.set()
            await computation_continue.wait()
            return "result"

        # Act
        initial_count = await manager.get_computation_count()

        task = asyncio.create_task(manager.deduplicate(key, slow_compute))
        await computation_started.wait()

        active_count = await manager.get_computation_count()

        # Cleanup
        computation_continue.set()
        await task

        final_count = await manager.get_computation_count()

        # Assert
        assert initial_count == 0
        assert active_count == 1
        assert final_count == 0

    @pytest.mark.asyncio
    async def test_clear_all_computations(self) -> None:
        """Test clearing all active computations."""
        # Arrange
        manager = DeduplicationManager()
        computation_started = asyncio.Event()

        async def slow_compute() -> str:
            computation_started.set()
            await asyncio.sleep(10)  # Long computation
            return "result"

        # Start multiple computations
        task1 = asyncio.create_task(manager.deduplicate("key1", slow_compute))
        await computation_started.wait()
        computation_started.clear()

        task2 = asyncio.create_task(manager.deduplicate("key2", slow_compute))
        await computation_started.wait()

        # Act
        cancelled_count = await manager.clear_all_computations()

        # Assert
        assert cancelled_count == 2
        assert await manager.get_computation_count() == 0

        # Tasks should be cancelled
        with pytest.raises(asyncio.CancelledError):
            await task1
        with pytest.raises(asyncio.CancelledError):
            await task2


class TestDeduplicationStats:
    """Test DeduplicationStats implementation."""

    def test_deduplication_stats_initialization(self) -> None:
        """Test DeduplicationStats initialization."""
        # Arrange & Act
        stats = DeduplicationStats()

        # Assert
        assert stats.total_requests == 0
        assert stats.deduplicated_requests == 0
        assert stats.unique_computations == 0
        assert isinstance(stats._lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_record_request_deduplicated(self) -> None:
        """Test recording a deduplicated request."""
        # Arrange
        stats = DeduplicationStats()

        # Act
        await stats.record_request(was_deduplicated=True)

        # Assert
        assert stats.total_requests == 1
        assert stats.deduplicated_requests == 1
        assert stats.unique_computations == 0

    @pytest.mark.asyncio
    async def test_record_request_unique_computation(self) -> None:
        """Test recording a unique computation request."""
        # Arrange
        stats = DeduplicationStats()

        # Act
        await stats.record_request(was_deduplicated=False)

        # Assert
        assert stats.total_requests == 1
        assert stats.deduplicated_requests == 0
        assert stats.unique_computations == 1

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self) -> None:
        """Test getting statistics with recorded data."""
        # Arrange
        stats = DeduplicationStats()
        await stats.record_request(was_deduplicated=False)  # unique
        await stats.record_request(was_deduplicated=True)  # deduplicated
        await stats.record_request(was_deduplicated=True)  # deduplicated

        # Act
        result = await stats.get_stats()

        # Assert
        expected = {
            "total_requests": 3,
            "deduplicated_requests": 2,
            "unique_computations": 1,
            "deduplication_ratio": 2 / 3,
            "efficiency_percentage": (2 / 3) * 100,
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_stats_no_data(self) -> None:
        """Test getting statistics with no recorded data."""
        # Arrange
        stats = DeduplicationStats()

        # Act
        result = await stats.get_stats()

        # Assert
        expected = {
            "total_requests": 0,
            "deduplicated_requests": 0,
            "unique_computations": 0,
            "deduplication_ratio": 0.0,
            "efficiency_percentage": 0.0,
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_reset_stats(self) -> None:
        """Test resetting statistics."""
        # Arrange
        stats = DeduplicationStats()
        await stats.record_request(was_deduplicated=False)
        await stats.record_request(was_deduplicated=True)

        # Act
        await stats.reset_stats()

        # Assert
        assert stats.total_requests == 0
        assert stats.deduplicated_requests == 0
        assert stats.unique_computations == 0


class TestInstrumentedDeduplicationManager:
    """Test InstrumentedDeduplicationManager implementation."""

    def test_instrumented_manager_initialization(self) -> None:
        """Test InstrumentedDeduplicationManager initialization."""
        # Arrange & Act
        manager = InstrumentedDeduplicationManager()

        # Assert
        assert isinstance(manager.stats, DeduplicationStats)
        assert manager._futures == {}

    @pytest.mark.asyncio
    async def test_deduplicate_records_unique_computation(self) -> None:
        """Test that unique computations are recorded in statistics."""
        # Arrange
        manager = InstrumentedDeduplicationManager()
        key = "test:key"

        async def mock_compute() -> str:
            return "result"

        # Act
        result = await manager.deduplicate(key, mock_compute)
        stats = await manager.get_stats()

        # Assert
        assert result == "result"
        assert stats["total_requests"] == 1
        assert stats["deduplicated_requests"] == 0
        assert stats["unique_computations"] == 1

    @pytest.mark.asyncio
    async def test_deduplicate_records_deduplicated_requests(self) -> None:
        """Test that deduplicated requests are recorded in statistics."""
        # Arrange
        manager = InstrumentedDeduplicationManager()
        key = "test:key"
        computation_started = asyncio.Event()
        computation_continue = asyncio.Event()

        async def slow_compute() -> str:
            computation_started.set()
            await computation_continue.wait()
            return "result"

        # Act - start first computation
        task1 = asyncio.create_task(manager.deduplicate(key, slow_compute))
        await computation_started.wait()

        # Start second computation that should be deduplicated
        task2 = asyncio.create_task(manager.deduplicate(key, slow_compute))

        # Let computations finish
        computation_continue.set()
        results = await asyncio.gather(task1, task2)

        stats = await manager.get_stats()

        # Assert
        assert all(result == "result" for result in results)
        assert stats["total_requests"] == 2
        assert stats["deduplicated_requests"] == 1
        assert stats["unique_computations"] == 1

    @pytest.mark.asyncio
    async def test_stats_property(self) -> None:
        """Test stats property access."""
        # Arrange
        manager = InstrumentedDeduplicationManager()

        # Act
        stats_obj = manager.stats

        # Assert
        assert isinstance(stats_obj, DeduplicationStats)
        assert stats_obj is manager._stats

    @pytest.mark.asyncio
    async def test_reset_stats(self) -> None:
        """Test resetting statistics in instrumented manager."""
        # Arrange
        manager = InstrumentedDeduplicationManager()

        async def mock_compute() -> str:
            return "result"

        # Record some data
        await manager.deduplicate("key1", mock_compute)
        await manager.deduplicate("key2", mock_compute)

        # Act
        await manager.reset_stats()
        stats = await manager.get_stats()

        # Assert
        assert stats["total_requests"] == 0
        assert stats["deduplicated_requests"] == 0
        assert stats["unique_computations"] == 0


class TestDeduplicationIntegration:
    """Integration tests for deduplication components."""

    @pytest.mark.asyncio
    async def test_high_concurrency_deduplication(self) -> None:
        """Test deduplication with high concurrency."""
        # Arrange
        manager = InstrumentedDeduplicationManager()
        key = "test:key"
        computation_count = 0

        async def mock_compute() -> str:
            nonlocal computation_count
            computation_count += 1
            await asyncio.sleep(0.01)  # Simulate work
            return f"result_{computation_count}"

        # Act - create many concurrent requests
        tasks = [asyncio.create_task(manager.deduplicate(key, mock_compute)) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        stats = await manager.get_stats()

        # Assert
        # All requests should get the same result
        assert all(result == "result_1" for result in results)
        # Only one computation should have been executed
        assert computation_count == 1
        # Statistics should reflect deduplication
        assert stats["total_requests"] == 10
        assert stats["unique_computations"] == 1
        assert stats["deduplicated_requests"] == 9

    @pytest.mark.asyncio
    async def test_mixed_keys_concurrent_requests(self) -> None:
        """Test deduplication with mixed keys and concurrent requests."""
        # Arrange
        manager = InstrumentedDeduplicationManager()
        computation_counts: dict[str, int] = {"key1": 0, "key2": 0}

        async def mock_compute_key1() -> str:
            computation_counts["key1"] += 1
            await asyncio.sleep(0.01)
            return f"result_key1_{computation_counts['key1']}"

        async def mock_compute_key2() -> str:
            computation_counts["key2"] += 1
            await asyncio.sleep(0.01)
            return f"result_key2_{computation_counts['key2']}"

        # Act - create concurrent requests for different keys
        tasks = []
        for i in range(5):
            tasks.append(asyncio.create_task(manager.deduplicate("key1", mock_compute_key1)))
            tasks.append(asyncio.create_task(manager.deduplicate("key2", mock_compute_key2)))

        results = await asyncio.gather(*tasks)
        stats = await manager.get_stats()

        # Assert
        # Should have results from both keys
        key1_results = [r for r in results if "key1" in r]
        key2_results = [r for r in results if "key2" in r]

        assert len(key1_results) == 5
        assert len(key2_results) == 5
        assert all(result == "result_key1_1" for result in key1_results)
        assert all(result == "result_key2_1" for result in key2_results)

        # Each key should have been computed only once
        assert computation_counts["key1"] == 1
        assert computation_counts["key2"] == 1

        # Statistics should reflect two unique computations and 8 deduplicated requests
        assert stats["total_requests"] == 10
        assert stats["unique_computations"] == 2
        assert stats["deduplicated_requests"] == 8

    @pytest.mark.asyncio
    async def test_error_handling_with_statistics(self) -> None:
        """Test error handling preserves statistics correctly."""
        # Arrange
        manager = InstrumentedDeduplicationManager()
        key = "test:key"

        async def failing_compute() -> str:
            await asyncio.sleep(0.01)
            raise ValueError("Computation failed")

        # Act - multiple concurrent requests that will fail
        tasks = [asyncio.create_task(manager.deduplicate(key, failing_compute)) for _ in range(3)]

        # All should fail with the same error
        with pytest.raises(ValueError):
            await asyncio.gather(*tasks)

        stats = await manager.get_stats()

        # Assert
        # Statistics should still be recorded even for failed computations
        assert stats["total_requests"] == 3
        assert stats["unique_computations"] == 1
        assert stats["deduplicated_requests"] == 2
