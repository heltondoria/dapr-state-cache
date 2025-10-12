"""
Unit tests for CacheOrchestrator.

Tests complete cache orchestration with 100% coverage including deduplication,
conditional caching, error handling, and sync/async support following AAA pattern and TDD.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from dapr_state_cache.core import (
    CacheOrchestrationTimeout,
    CacheOrchestrator,
    CacheService,
    NoOpDeduplicationManager,
    OrchestrationError,
    SyncAsyncBridge,
    create_cache_orchestrator,
)
from dapr_state_cache.orchestration import DeduplicationManager


class TestCacheOrchestrator:
    """Test CacheOrchestrator implementation."""

    def test_cache_orchestrator_initialization_defaults(self) -> None:
        """Test CacheOrchestrator initialization with defaults."""
        # Arrange
        mock_cache_service = Mock(spec=CacheService)

        # Act
        orchestrator = CacheOrchestrator(mock_cache_service)

        # Assert
        assert orchestrator.cache_service is mock_cache_service
        assert isinstance(orchestrator.deduplication_manager, DeduplicationManager)
        assert isinstance(orchestrator.sync_async_bridge, SyncAsyncBridge)

    def test_cache_orchestrator_initialization_custom_components(self) -> None:
        """Test CacheOrchestrator initialization with custom components."""
        # Arrange
        mock_cache_service = Mock(spec=CacheService)
        mock_dedup_manager = Mock(spec=DeduplicationManager)
        mock_bridge = Mock(spec=SyncAsyncBridge)

        # Act
        orchestrator = CacheOrchestrator(
            cache_service=mock_cache_service, deduplication_manager=mock_dedup_manager, sync_async_bridge=mock_bridge
        )

        # Assert
        assert orchestrator.cache_service is mock_cache_service
        assert orchestrator.deduplication_manager is mock_dedup_manager
        assert orchestrator.sync_async_bridge is mock_bridge

    @pytest.mark.asyncio
    async def test_execute_with_cache_hit(self) -> None:
        """Test cache orchestration with cache hit."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.get.return_value = "cached_result"

        orchestrator = CacheOrchestrator(mock_cache_service)

        def test_func(x: int) -> str:
            return f"computed_{x}"

        args = (5,)
        kwargs: dict[str, Any] = {}

        # Act
        result = await orchestrator.execute_with_cache(test_func, args, kwargs)

        # Assert
        assert result == "cached_result"
        mock_cache_service.get.assert_called_once_with(test_func, args, kwargs)
        # Should not attempt computation or storage
        assert not hasattr(mock_cache_service, "set") or not mock_cache_service.set.called

    @pytest.mark.asyncio
    async def test_execute_with_cache_miss_and_store(self) -> None:
        """Test cache orchestration with cache miss and successful store."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.get.return_value = None  # Cache miss
        mock_cache_service._build_cache_key.return_value = "test:key:hash123"
        mock_cache_service.set.return_value = True

        mock_dedup_manager = AsyncMock()

        # Mock deduplication to call compute function immediately
        async def mock_deduplicate(key: str, compute_func):
            return await compute_func()

        mock_dedup_manager.deduplicate.side_effect = mock_deduplicate

        orchestrator = CacheOrchestrator(cache_service=mock_cache_service, deduplication_manager=mock_dedup_manager)

        def test_func(x: int) -> str:
            return f"computed_{x}"

        args = (5,)
        kwargs: dict[str, Any] = {}
        ttl_seconds = 3600

        # Act
        result = await orchestrator.execute_with_cache(test_func, args, kwargs, ttl_seconds=ttl_seconds)

        # Assert
        assert result == "computed_5"
        mock_cache_service.get.assert_called_once_with(test_func, args, kwargs)
        mock_cache_service.set.assert_called_once_with(test_func, args, kwargs, "computed_5", ttl_seconds)
        mock_dedup_manager.deduplicate.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_cache_bypass_condition(self) -> None:
        """Test cache orchestration with bypass condition triggered."""
        # Arrange
        mock_cache_service = AsyncMock()

        orchestrator = CacheOrchestrator(mock_cache_service)

        def test_func(x: int) -> str:
            return f"computed_{x}"

        def bypass_condition(x: int) -> bool:
            return x > 10  # Bypass cache for large values

        args = (15,)  # Should trigger bypass
        kwargs: dict[str, Any] = {}

        # Act
        result = await orchestrator.execute_with_cache(test_func, args, kwargs, bypass=bypass_condition)

        # Assert
        assert result == "computed_15"
        # Should not check cache when bypassed
        mock_cache_service.get.assert_not_called()
        mock_cache_service.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_cache_condition_not_met(self) -> None:
        """Test cache orchestration when caching condition is not met."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.get.return_value = None  # Cache miss
        mock_cache_service._build_cache_key.return_value = "test:key:hash123"

        mock_dedup_manager = AsyncMock()

        # Mock deduplication to call compute function immediately
        async def mock_deduplicate(key: str, compute_func):
            return await compute_func()

        mock_dedup_manager.deduplicate.side_effect = mock_deduplicate

        orchestrator = CacheOrchestrator(cache_service=mock_cache_service, deduplication_manager=mock_dedup_manager)

        def test_func(x: int) -> str:
            return f"computed_{x}"

        def cache_condition(x: int) -> bool:
            return x < 10  # Only cache small values

        args = (15,)  # Should not be cached
        kwargs: dict[str, Any] = {}

        # Act
        result = await orchestrator.execute_with_cache(test_func, args, kwargs, condition=cache_condition)

        # Assert
        assert result == "computed_15"
        mock_cache_service.get.assert_called_once()
        # Should not store result when condition not met
        mock_cache_service.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_cache_condition_met(self) -> None:
        """Test cache orchestration when caching condition is met."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.get.return_value = None  # Cache miss
        mock_cache_service._build_cache_key.return_value = "test:key:hash123"
        mock_cache_service.set.return_value = True

        mock_dedup_manager = AsyncMock()

        # Mock deduplication to call compute function immediately
        async def mock_deduplicate(key: str, compute_func):
            return await compute_func()

        mock_dedup_manager.deduplicate.side_effect = mock_deduplicate

        orchestrator = CacheOrchestrator(cache_service=mock_cache_service, deduplication_manager=mock_dedup_manager)

        def test_func(x: int) -> str:
            return f"computed_{x}"

        def cache_condition(x: int) -> bool:
            return x < 10  # Only cache small values

        args = (5,)  # Should be cached
        kwargs: dict[str, Any] = {}

        # Act
        result = await orchestrator.execute_with_cache(test_func, args, kwargs, condition=cache_condition)

        # Assert
        assert result == "computed_5"
        mock_cache_service.get.assert_called_once()
        mock_cache_service.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_cache_async_function(self) -> None:
        """Test cache orchestration with async function."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.get.return_value = None  # Cache miss
        mock_cache_service._build_cache_key.return_value = "test:key:hash123"
        mock_cache_service.set.return_value = True

        mock_dedup_manager = AsyncMock()

        # Mock deduplication to call compute function immediately
        async def mock_deduplicate(key: str, compute_func):
            return await compute_func()

        mock_dedup_manager.deduplicate.side_effect = mock_deduplicate

        orchestrator = CacheOrchestrator(cache_service=mock_cache_service, deduplication_manager=mock_dedup_manager)

        async def test_async_func(x: int) -> str:
            await asyncio.sleep(0.001)  # Simulate async work
            return f"async_computed_{x}"

        args = (5,)
        kwargs: dict[str, Any] = {}

        # Act
        result = await orchestrator.execute_with_cache(test_async_func, args, kwargs)

        # Assert
        assert result == "async_computed_5"
        mock_cache_service.set.assert_called_once_with(test_async_func, args, kwargs, "async_computed_5", None)

    @pytest.mark.asyncio
    async def test_execute_with_cache_deduplication_manager_integration(self) -> None:
        """Test that deduplication manager is properly integrated."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.get.return_value = None  # Cache miss
        mock_cache_service._build_cache_key.return_value = "test:key:hash123"
        mock_cache_service.set.return_value = True

        mock_dedup_manager = AsyncMock()
        mock_dedup_manager.deduplicate.return_value = "deduplicated_result"

        orchestrator = CacheOrchestrator(cache_service=mock_cache_service, deduplication_manager=mock_dedup_manager)

        def test_func(x: int) -> str:
            return f"computed_{x}"

        args = (5,)
        kwargs: dict[str, Any] = {}

        # Act
        result = await orchestrator.execute_with_cache(test_func, args, kwargs)

        # Assert
        assert result == "deduplicated_result"
        mock_dedup_manager.deduplicate.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_cache_error_fallback(self) -> None:
        """Test cache orchestration fallback on error."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.get.side_effect = Exception("Cache service error")

        orchestrator = CacheOrchestrator(mock_cache_service)

        def test_func(x: int) -> str:
            return f"computed_{x}"

        args = (5,)
        kwargs: dict[str, Any] = {}

        # Act
        result = await orchestrator.execute_with_cache(test_func, args, kwargs)

        # Assert
        # Should fallback to direct execution
        assert result == "computed_5"

    @pytest.mark.asyncio
    async def test_execute_with_cache_condition_evaluation_error(self) -> None:
        """Test handling of condition evaluation errors."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.get.return_value = None  # Cache miss
        mock_cache_service._build_cache_key.return_value = "test:key:hash123"

        mock_dedup_manager = AsyncMock()

        # Mock deduplication to call compute function immediately
        async def mock_deduplicate(key: str, compute_func):
            return await compute_func()

        mock_dedup_manager.deduplicate.side_effect = mock_deduplicate

        orchestrator = CacheOrchestrator(cache_service=mock_cache_service, deduplication_manager=mock_dedup_manager)

        def test_func(x: int) -> str:
            return f"computed_{x}"

        def failing_condition(x: int) -> bool:
            raise ValueError("Condition error")

        args = (5,)
        kwargs: dict[str, Any] = {}

        # Act
        result = await orchestrator.execute_with_cache(test_func, args, kwargs, condition=failing_condition)

        # Assert
        assert result == "computed_5"
        # Should not store when condition evaluation fails (defaults to False)
        mock_cache_service.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_cache_success(self) -> None:
        """Test successful cache invalidation."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.invalidate.return_value = True

        orchestrator = CacheOrchestrator(mock_cache_service)

        def test_func(x: int) -> str:
            return f"computed_{x}"

        args = (5,)
        kwargs: dict[str, Any] = {}

        # Act
        result = await orchestrator.invalidate_cache(test_func, args, kwargs)

        # Assert
        assert result is True
        mock_cache_service.invalidate.assert_called_once_with(test_func, args, kwargs)

    @pytest.mark.asyncio
    async def test_invalidate_cache_prefix_success(self) -> None:
        """Test successful cache prefix invalidation."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.invalidate_prefix.return_value = True

        orchestrator = CacheOrchestrator(mock_cache_service)

        prefix = "cache:test"

        # Act
        result = await orchestrator.invalidate_cache_prefix(prefix)

        # Assert
        assert result is True
        mock_cache_service.invalidate_prefix.assert_called_once_with(prefix)

    @pytest.mark.asyncio
    async def test_get_cache_statistics(self) -> None:
        """Test getting cache statistics."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.store_name = "test-store"
        mock_cache_service.key_prefix = "test-prefix"
        mock_cache_service.hooks = None
        mock_cache_service.health_check.return_value = {"service": "healthy"}

        mock_dedup_manager = AsyncMock()
        mock_dedup_manager.get_computation_count.return_value = 2
        mock_dedup_manager.get_active_computations.return_value = ["key1", "key2"]

        orchestrator = CacheOrchestrator(cache_service=mock_cache_service, deduplication_manager=mock_dedup_manager)

        # Act
        stats = await orchestrator.get_cache_statistics()

        # Assert
        assert stats["orchestrator"]["store_name"] == "test-store"
        assert stats["orchestrator"]["key_prefix"] == "test-prefix"
        assert stats["cache_service"]["service"] == "healthy"
        assert stats["deduplication"]["active_computations"] == 2
        assert stats["deduplication"]["computation_keys"] == ["key1", "key2"]

    @pytest.mark.asyncio
    async def test_get_cache_statistics_with_metrics(self) -> None:
        """Test getting cache statistics with metrics hooks."""
        # Arrange
        from dapr_state_cache.observability.metrics import MetricsCollectorHooks

        mock_cache_service = AsyncMock()
        mock_cache_service.store_name = "test-store"
        mock_cache_service.key_prefix = "test-prefix"

        # Create a real MetricsCollectorHooks instance but mock its get_stats method
        real_metrics_hooks = MetricsCollectorHooks()
        real_metrics_hooks.get_stats = AsyncMock(return_value={"hits": 10, "misses": 5})
        mock_cache_service.hooks = real_metrics_hooks

        mock_cache_service.health_check.return_value = {"service": "healthy"}

        mock_dedup_manager = AsyncMock()
        mock_dedup_manager.get_computation_count.return_value = 0
        mock_dedup_manager.get_active_computations.return_value = []

        orchestrator = CacheOrchestrator(cache_service=mock_cache_service, deduplication_manager=mock_dedup_manager)

        # Act
        stats = await orchestrator.get_cache_statistics()

        # Assert
        assert "metrics" in stats
        assert stats["metrics"]["hits"] == 10
        assert stats["metrics"]["misses"] == 5

    @pytest.mark.asyncio
    async def test_clear_cache_computations(self) -> None:
        """Test clearing all cache computations."""
        # Arrange
        mock_dedup_manager = AsyncMock()
        mock_dedup_manager.clear_all_computations.return_value = 3

        orchestrator = CacheOrchestrator(cache_service=Mock(), deduplication_manager=mock_dedup_manager)

        # Act
        cleared_count = await orchestrator.clear_cache_computations()

        # Assert
        assert cleared_count == 3
        mock_dedup_manager.clear_all_computations.assert_called_once()


class TestOrchestrationErrors:
    """Test orchestration error classes."""

    def test_orchestration_error_inheritance(self) -> None:
        """Test OrchestrationError inheritance."""
        # Arrange
        error = OrchestrationError("Test error")

        # Assert
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_cache_orchestration_timeout_inheritance(self) -> None:
        """Test CacheOrchestrationTimeout inheritance."""
        # Arrange
        error = CacheOrchestrationTimeout("Timeout error")

        # Assert
        assert isinstance(error, OrchestrationError)
        assert isinstance(error, Exception)
        assert str(error) == "Timeout error"


class TestNoOpDeduplicationManager:
    """Test NoOpDeduplicationManager implementation."""

    @pytest.mark.asyncio
    async def test_noop_deduplicate_executes_function(self) -> None:
        """Test that no-op deduplication executes function directly."""
        # Arrange
        manager = NoOpDeduplicationManager()

        async def test_compute():
            return "result"

        # Act
        result = await manager.deduplicate("key", test_compute)

        # Assert
        assert result == "result"

    @pytest.mark.asyncio
    async def test_noop_is_computation_running_always_false(self) -> None:
        """Test that no-op manager always reports no computations running."""
        # Arrange
        manager = NoOpDeduplicationManager()

        # Act
        result = await manager.is_computation_running("key")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_noop_cancel_computation_always_false(self) -> None:
        """Test that no-op manager always reports no computations to cancel."""
        # Arrange
        manager = NoOpDeduplicationManager()

        # Act
        result = await manager.cancel_computation("key")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_noop_get_active_computations_empty(self) -> None:
        """Test that no-op manager reports no active computations."""
        # Arrange
        manager = NoOpDeduplicationManager()

        # Act
        result = await manager.get_active_computations()

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_noop_get_computation_count_zero(self) -> None:
        """Test that no-op manager reports zero computations."""
        # Arrange
        manager = NoOpDeduplicationManager()

        # Act
        result = await manager.get_computation_count()

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_noop_clear_all_computations_zero(self) -> None:
        """Test that no-op manager reports zero computations cleared."""
        # Arrange
        manager = NoOpDeduplicationManager()

        # Act
        result = await manager.clear_all_computations()

        # Assert
        assert result == 0


class TestCreateCacheOrchestrator:
    """Test create_cache_orchestrator factory function."""

    def test_create_cache_orchestrator_with_deduplication(self) -> None:
        """Test creating orchestrator with deduplication enabled."""
        # Arrange
        mock_cache_service = Mock(spec=CacheService)

        # Act
        orchestrator = create_cache_orchestrator(mock_cache_service, enable_deduplication=True)

        # Assert
        assert isinstance(orchestrator, CacheOrchestrator)
        assert isinstance(orchestrator.deduplication_manager, DeduplicationManager)

    def test_create_cache_orchestrator_without_deduplication(self) -> None:
        """Test creating orchestrator with deduplication disabled."""
        # Arrange
        mock_cache_service = Mock(spec=CacheService)

        # Act
        orchestrator = create_cache_orchestrator(mock_cache_service, enable_deduplication=False)

        # Assert
        assert isinstance(orchestrator, CacheOrchestrator)
        assert isinstance(orchestrator.deduplication_manager, NoOpDeduplicationManager)

    def test_create_cache_orchestrator_custom_components(self) -> None:
        """Test creating orchestrator with custom components."""
        # Arrange
        mock_cache_service = Mock(spec=CacheService)
        mock_dedup_manager = Mock(spec=DeduplicationManager)
        mock_bridge = Mock(spec=SyncAsyncBridge)

        # Act
        orchestrator = create_cache_orchestrator(
            cache_service=mock_cache_service,
            enable_deduplication=True,
            deduplication_manager=mock_dedup_manager,
            sync_async_bridge=mock_bridge,
        )

        # Assert
        assert orchestrator.cache_service is mock_cache_service
        assert orchestrator.deduplication_manager is mock_dedup_manager
        assert orchestrator.sync_async_bridge is mock_bridge


class TestIntegrationScenarios:
    """Integration tests for complex orchestration scenarios."""

    @pytest.mark.asyncio
    async def test_complex_caching_scenario(self) -> None:
        """Test complex scenario with conditions, bypass, and deduplication."""
        # Arrange
        mock_cache_service = AsyncMock()
        mock_cache_service.get.return_value = None  # Always cache miss for this test
        mock_cache_service._build_cache_key.return_value = "test:key:hash123"
        mock_cache_service.set.return_value = True

        # Use real deduplication manager
        dedup_manager = DeduplicationManager()

        orchestrator = CacheOrchestrator(cache_service=mock_cache_service, deduplication_manager=dedup_manager)

        call_count = 0

        def complex_func(x: int, operation: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"{operation}_{x}_{call_count}"

        def cache_condition(x: int, operation: str) -> bool:
            return operation == "cache"  # Only cache "cache" operations

        def bypass_condition(x: int, operation: str) -> bool:
            return operation == "bypass"  # Bypass "bypass" operations

        # Act - Test various scenarios

        # 1. Bypass scenario - should not use cache at all
        result1 = await orchestrator.execute_with_cache(
            complex_func, (10,), {"operation": "bypass"}, condition=cache_condition, bypass=bypass_condition
        )

        # 2. Cache scenario - should use cache
        result2 = await orchestrator.execute_with_cache(
            complex_func, (20,), {"operation": "cache"}, condition=cache_condition, bypass=bypass_condition
        )

        # 3. No-cache scenario - should execute but not cache
        result3 = await orchestrator.execute_with_cache(
            complex_func, (30,), {"operation": "compute"}, condition=cache_condition, bypass=bypass_condition
        )

        # Assert
        assert result1 == "bypass_10_1"  # Direct execution, bypassed cache
        assert result2 == "cache_20_2"  # Computed and cached
        assert result3 == "compute_30_3"  # Computed but not cached

        # Verify caching behavior
        assert call_count == 3  # All three should execute (no hits)

        # Verify cache service calls
        # Bypass should not call get or set
        # Cache should call both get and set
        # Compute should call get but not set

        # Should have called get for cache and compute scenarios only
        assert mock_cache_service.get.call_count == 2

        # Should have called set for cache scenario only
        assert mock_cache_service.set.call_count == 1

    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self) -> None:
        """Test error recovery in various parts of orchestration."""
        # Arrange
        mock_cache_service = AsyncMock()

        # Simulate intermittent errors
        get_call_count = 0

        def get_side_effect(*args):
            nonlocal get_call_count
            get_call_count += 1
            if get_call_count == 1:
                raise Exception("First get fails")
            return None  # Cache miss on subsequent calls

        mock_cache_service.get.side_effect = get_side_effect
        mock_cache_service._build_cache_key.return_value = "test:key:hash123"
        mock_cache_service.set.return_value = True

        orchestrator = CacheOrchestrator(mock_cache_service)

        def resilient_func(x: int) -> str:
            return f"resilient_{x}"

        # Act - First call should recover from cache error
        result1 = await orchestrator.execute_with_cache(resilient_func, (1,), {})

        # Second call should work normally (no cache error)
        result2 = await orchestrator.execute_with_cache(resilient_func, (2,), {})

        # Assert
        assert result1 == "resilient_1"  # Should fallback to direct execution
        assert result2 == "resilient_2"  # Should work with cache miss flow

        # Both calls should result in function execution
        assert get_call_count == 2
