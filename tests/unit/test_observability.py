"""
Unit tests for observability module.

Tests hooks implementations and metrics collection with 100% coverage
following AAA pattern and TDD principles.
"""

import logging
from unittest.mock import Mock, patch

import pytest

from dapr_state_cache.observability import (
    CacheMetrics,
    CacheStats,
    CompositeObservabilityHooks,
    DefaultObservabilityHooks,
    MetricsCollectorHooks,
    SilentObservabilityHooks,
    TopKeysResult,
)


class TestCacheStats:
    """Test CacheStats dataclass."""

    def test_cache_stats_initialization_default(self) -> None:
        """Test CacheStats initialization with defaults."""
        # Arrange & Act
        stats = CacheStats()

        # Assert
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.writes == 0
        assert stats.errors == 0
        assert stats.hit_latencies == []
        assert stats.miss_latencies == []
        assert stats.write_sizes == []

    def test_cache_stats_initialization_with_values(self) -> None:
        """Test CacheStats initialization with specific values."""
        # Arrange
        hit_latencies = [0.1, 0.2]
        miss_latencies = [0.5, 0.6]
        write_sizes = [100, 200]

        # Act
        stats = CacheStats(
            hits=10,
            misses=5,
            writes=3,
            errors=1,
            hit_latencies=hit_latencies,
            miss_latencies=miss_latencies,
            write_sizes=write_sizes,
        )

        # Assert
        assert stats.hits == 10
        assert stats.misses == 5
        assert stats.writes == 3
        assert stats.errors == 1
        assert stats.hit_latencies == hit_latencies
        assert stats.miss_latencies == miss_latencies
        assert stats.write_sizes == write_sizes

    def test_total_operations_property(self) -> None:
        """Test total_operations property calculation."""
        # Arrange
        stats = CacheStats(hits=10, misses=5)

        # Act
        result = stats.total_operations

        # Assert
        assert result == 15

    def test_hit_ratio_property_with_operations(self) -> None:
        """Test hit_ratio property with operations."""
        # Arrange
        stats = CacheStats(hits=8, misses=2)

        # Act
        result = stats.hit_ratio

        # Assert
        assert result == 0.8

    def test_hit_ratio_property_no_operations(self) -> None:
        """Test hit_ratio property with no operations."""
        # Arrange
        stats = CacheStats(hits=0, misses=0)

        # Act
        result = stats.hit_ratio

        # Assert
        assert result == 0.0

    def test_miss_ratio_property(self) -> None:
        """Test miss_ratio property calculation."""
        # Arrange
        stats = CacheStats(hits=7, misses=3)

        # Act
        result = stats.miss_ratio

        # Assert
        assert result == pytest.approx(0.3)

    def test_average_hit_latency_ms_with_data(self) -> None:
        """Test average hit latency calculation with data."""
        # Arrange
        stats = CacheStats(hit_latencies=[0.1, 0.2, 0.3])  # 0.2s average

        # Act
        result = stats.average_hit_latency_ms

        # Assert
        assert result == pytest.approx(200.0)  # 0.2s * 1000 = 200ms

    def test_average_hit_latency_ms_no_data(self) -> None:
        """Test average hit latency with no data."""
        # Arrange
        stats = CacheStats(hit_latencies=[])

        # Act
        result = stats.average_hit_latency_ms

        # Assert
        assert result == 0.0

    def test_average_miss_latency_ms_with_data(self) -> None:
        """Test average miss latency calculation with data."""
        # Arrange
        stats = CacheStats(miss_latencies=[0.4, 0.6])  # 0.5s average

        # Act
        result = stats.average_miss_latency_ms

        # Assert
        assert result == 500.0  # 0.5s * 1000 = 500ms

    def test_average_miss_latency_ms_no_data(self) -> None:
        """Test average miss latency with no data."""
        # Arrange
        stats = CacheStats(miss_latencies=[])

        # Act
        result = stats.average_miss_latency_ms

        # Assert
        assert result == 0.0

    def test_average_write_size_bytes_with_data(self) -> None:
        """Test average write size calculation with data."""
        # Arrange
        stats = CacheStats(write_sizes=[100, 200, 300])  # 200 bytes average

        # Act
        result = stats.average_write_size_bytes

        # Assert
        assert result == 200.0

    def test_average_write_size_bytes_no_data(self) -> None:
        """Test average write size with no data."""
        # Arrange
        stats = CacheStats(write_sizes=[])

        # Act
        result = stats.average_write_size_bytes

        # Assert
        assert result == 0.0

    def test_total_write_size_bytes(self) -> None:
        """Test total write size calculation."""
        # Arrange
        stats = CacheStats(write_sizes=[100, 200, 300])

        # Act
        result = stats.total_write_size_bytes

        # Assert
        assert result == 600


class TestTopKeysResult:
    """Test TopKeysResult dataclass."""

    def test_top_keys_result_initialization(self) -> None:
        """Test TopKeysResult initialization."""
        # Arrange & Act
        result = TopKeysResult(key="test:key", count=42, percentage=75.5)

        # Assert
        assert result.key == "test:key"
        assert result.count == 42
        assert result.percentage == 75.5


class TestDefaultObservabilityHooks:
    """Test DefaultObservabilityHooks implementation."""

    def test_default_hooks_initialization_default_level(self) -> None:
        """Test initialization with default log level."""
        # Arrange & Act
        hooks = DefaultObservabilityHooks()

        # Assert
        assert hooks._log_level == logging.DEBUG

    def test_default_hooks_initialization_custom_level(self) -> None:
        """Test initialization with custom log level."""
        # Arrange
        custom_level = logging.INFO

        # Act
        hooks = DefaultObservabilityHooks(log_level=custom_level)

        # Assert
        assert hooks._log_level == custom_level

    @patch("dapr_state_cache.observability.hooks.logger")
    def test_on_cache_hit_logging(self, mock_logger: Mock) -> None:
        """Test cache hit logging."""
        # Arrange
        hooks = DefaultObservabilityHooks()
        key = "test:key"
        latency = 0.025  # 25ms

        # Act
        hooks.on_cache_hit(key, latency)

        # Assert
        mock_logger.log.assert_called_once_with(logging.DEBUG, "Cache HIT for key '%s' (latency: %.3fms)", key, 25.0)

    @patch("dapr_state_cache.observability.hooks.logger")
    def test_on_cache_miss_logging(self, mock_logger: Mock) -> None:
        """Test cache miss logging."""
        # Arrange
        hooks = DefaultObservabilityHooks()
        key = "test:key"
        latency = 0.150  # 150ms

        # Act
        hooks.on_cache_miss(key, latency)

        # Assert
        mock_logger.log.assert_called_once_with(logging.DEBUG, "Cache MISS for key '%s' (latency: %.3fms)", key, 150.0)

    @patch("dapr_state_cache.observability.hooks.logger")
    def test_on_cache_write_logging(self, mock_logger: Mock) -> None:
        """Test cache write logging."""
        # Arrange
        hooks = DefaultObservabilityHooks()
        key = "test:key"
        size = 1024

        # Act
        hooks.on_cache_write(key, size)

        # Assert
        mock_logger.log.assert_called_once_with(logging.DEBUG, "Cache WRITE for key '%s' (size: %d bytes)", key, size)

    @patch("dapr_state_cache.observability.hooks.logger")
    def test_on_cache_error_logging(self, mock_logger: Mock) -> None:
        """Test cache error logging."""
        # Arrange
        hooks = DefaultObservabilityHooks()
        key = "test:key"
        error = ValueError("Test error")

        # Act
        hooks.on_cache_error(key, error)

        # Assert
        mock_logger.error.assert_called_once_with("Cache ERROR for key '%s': %s (%s)", key, "Test error", "ValueError")


class TestSilentObservabilityHooks:
    """Test SilentObservabilityHooks implementation."""

    def test_silent_hooks_on_cache_hit_no_operation(self) -> None:
        """Test that silent hooks perform no operation on cache hit."""
        # Arrange
        hooks = SilentObservabilityHooks()

        # Act & Assert - should not raise exception
        hooks.on_cache_hit("key", 0.1)

    def test_silent_hooks_on_cache_miss_no_operation(self) -> None:
        """Test that silent hooks perform no operation on cache miss."""
        # Arrange
        hooks = SilentObservabilityHooks()

        # Act & Assert - should not raise exception
        hooks.on_cache_miss("key", 0.1)

    def test_silent_hooks_on_cache_write_no_operation(self) -> None:
        """Test that silent hooks perform no operation on cache write."""
        # Arrange
        hooks = SilentObservabilityHooks()

        # Act & Assert - should not raise exception
        hooks.on_cache_write("key", 100)

    def test_silent_hooks_on_cache_error_no_operation(self) -> None:
        """Test that silent hooks perform no operation on cache error."""
        # Arrange
        hooks = SilentObservabilityHooks()
        error = Exception("test")

        # Act & Assert - should not raise exception
        hooks.on_cache_error("key", error)


class TestCompositeObservabilityHooks:
    """Test CompositeObservabilityHooks implementation."""

    def test_composite_hooks_initialization(self) -> None:
        """Test composite hooks initialization."""
        # Arrange
        from dapr_state_cache.protocols import ObservabilityHooks

        hook1 = Mock(spec=ObservabilityHooks)
        hook2 = Mock(spec=ObservabilityHooks)
        hooks_list = [hook1, hook2]

        # Act
        composite = CompositeObservabilityHooks(hooks_list)

        # Assert
        assert composite._hooks == hooks_list

    def test_composite_on_cache_hit_delegates_to_all(self) -> None:
        """Test that cache hit is delegated to all hooks."""
        # Arrange
        from dapr_state_cache.protocols import ObservabilityHooks

        hook1 = Mock(spec=ObservabilityHooks)
        hook2 = Mock(spec=ObservabilityHooks)
        composite = CompositeObservabilityHooks([hook1, hook2])

        key = "test:key"
        latency = 0.1

        # Act
        composite.on_cache_hit(key, latency)

        # Assert
        hook1.on_cache_hit.assert_called_once_with(key, latency)
        hook2.on_cache_hit.assert_called_once_with(key, latency)

    @patch("dapr_state_cache.observability.hooks.logger")
    def test_composite_on_cache_hit_handles_hook_errors(self, mock_logger: Mock) -> None:
        """Test that hook errors are handled gracefully."""
        # Arrange
        from dapr_state_cache.protocols import ObservabilityHooks

        hook1 = Mock(spec=ObservabilityHooks)
        hook1.on_cache_hit.side_effect = Exception("Hook error")
        hook2 = Mock(spec=ObservabilityHooks)

        composite = CompositeObservabilityHooks([hook1, hook2])
        key = "test:key"
        latency = 0.1

        # Act
        composite.on_cache_hit(key, latency)

        # Assert
        hook1.on_cache_hit.assert_called_once_with(key, latency)
        hook2.on_cache_hit.assert_called_once_with(key, latency)  # Should still be called
        mock_logger.warning.assert_called_once()

    def test_composite_on_cache_miss_delegates_to_all(self) -> None:
        """Test that cache miss is delegated to all hooks."""
        # Arrange
        from dapr_state_cache.protocols import ObservabilityHooks

        hook1 = Mock(spec=ObservabilityHooks)
        hook2 = Mock(spec=ObservabilityHooks)
        composite = CompositeObservabilityHooks([hook1, hook2])

        key = "test:key"
        latency = 0.2

        # Act
        composite.on_cache_miss(key, latency)

        # Assert
        hook1.on_cache_miss.assert_called_once_with(key, latency)
        hook2.on_cache_miss.assert_called_once_with(key, latency)

    def test_composite_on_cache_write_delegates_to_all(self) -> None:
        """Test that cache write is delegated to all hooks."""
        # Arrange
        from dapr_state_cache.protocols import ObservabilityHooks

        hook1 = Mock(spec=ObservabilityHooks)
        hook2 = Mock(spec=ObservabilityHooks)
        composite = CompositeObservabilityHooks([hook1, hook2])

        key = "test:key"
        size = 500

        # Act
        composite.on_cache_write(key, size)

        # Assert
        hook1.on_cache_write.assert_called_once_with(key, size)
        hook2.on_cache_write.assert_called_once_with(key, size)

    def test_composite_on_cache_error_delegates_to_all(self) -> None:
        """Test that cache error is delegated to all hooks."""
        # Arrange
        from dapr_state_cache.protocols import ObservabilityHooks

        hook1 = Mock(spec=ObservabilityHooks)
        hook2 = Mock(spec=ObservabilityHooks)
        composite = CompositeObservabilityHooks([hook1, hook2])

        key = "test:key"
        error = ValueError("test")

        # Act
        composite.on_cache_error(key, error)

        # Assert
        hook1.on_cache_error.assert_called_once_with(key, error)
        hook2.on_cache_error.assert_called_once_with(key, error)

    def test_add_hook(self) -> None:
        """Test adding hook to composite."""
        # Arrange
        from dapr_state_cache.protocols import ObservabilityHooks

        hook1 = Mock(spec=ObservabilityHooks)
        hook2 = Mock(spec=ObservabilityHooks)
        composite = CompositeObservabilityHooks([hook1])

        # Act
        composite.add_hook(hook2)

        # Assert
        assert hook2 in composite._hooks
        assert len(composite._hooks) == 2

    def test_remove_hook_success(self) -> None:
        """Test successful hook removal."""
        # Arrange
        from dapr_state_cache.protocols import ObservabilityHooks

        hook1 = Mock(spec=ObservabilityHooks)
        hook2 = Mock(spec=ObservabilityHooks)
        composite = CompositeObservabilityHooks([hook1, hook2])

        # Act
        result = composite.remove_hook(hook1)

        # Assert
        assert result is True
        assert hook1 not in composite._hooks
        assert len(composite._hooks) == 1

    def test_remove_hook_not_found(self) -> None:
        """Test hook removal when hook not found."""
        # Arrange
        from dapr_state_cache.protocols import ObservabilityHooks

        hook1 = Mock(spec=ObservabilityHooks)
        hook2 = Mock(spec=ObservabilityHooks)
        composite = CompositeObservabilityHooks([hook1])

        # Act
        result = composite.remove_hook(hook2)

        # Assert
        assert result is False
        assert len(composite._hooks) == 1


class TestCacheMetrics:
    """Test CacheMetrics implementation."""

    def test_cache_metrics_initialization_default(self) -> None:
        """Test CacheMetrics initialization with defaults."""
        # Arrange & Act
        metrics = CacheMetrics()

        # Assert
        assert metrics._max_latency_samples == 1000
        assert metrics._overall_stats.hits == 0
        assert len(metrics._key_stats) == 0

    def test_cache_metrics_initialization_custom_samples(self) -> None:
        """Test CacheMetrics initialization with custom sample limit."""
        # Arrange
        max_samples = 500

        # Act
        metrics = CacheMetrics(max_latency_samples=max_samples)

        # Assert
        assert metrics._max_latency_samples == max_samples

    def test_record_hit_updates_overall_and_key_stats(self) -> None:
        """Test that recording hit updates both overall and key statistics."""
        # Arrange
        metrics = CacheMetrics()
        key = "test:key"
        latency = 0.1

        # Act
        metrics.record_hit(key, latency)

        # Assert
        assert metrics._overall_stats.hits == 1
        assert metrics._overall_stats.hit_latencies == [latency]

        assert metrics._key_stats[key].hits == 1
        assert metrics._key_stats[key].hit_latencies == [latency]

    def test_record_miss_updates_overall_and_key_stats(self) -> None:
        """Test that recording miss updates both overall and key statistics."""
        # Arrange
        metrics = CacheMetrics()
        key = "test:key"
        latency = 0.2

        # Act
        metrics.record_miss(key, latency)

        # Assert
        assert metrics._overall_stats.misses == 1
        assert metrics._overall_stats.miss_latencies == [latency]

        assert metrics._key_stats[key].misses == 1
        assert metrics._key_stats[key].miss_latencies == [latency]

    def test_record_write_updates_overall_and_key_stats(self) -> None:
        """Test that recording write updates both overall and key statistics."""
        # Arrange
        metrics = CacheMetrics()
        key = "test:key"
        size = 1024

        # Act
        metrics.record_write(key, size)

        # Assert
        assert metrics._overall_stats.writes == 1
        assert metrics._overall_stats.write_sizes == [size]

        assert metrics._key_stats[key].writes == 1
        assert metrics._key_stats[key].write_sizes == [size]

    def test_record_error_updates_overall_and_key_stats(self) -> None:
        """Test that recording error updates both overall and key statistics."""
        # Arrange
        metrics = CacheMetrics()
        key = "test:key"
        error = ValueError("test")

        # Act
        metrics.record_error(key, error)

        # Assert
        assert metrics._overall_stats.errors == 1
        assert metrics._key_stats[key].errors == 1

    def test_get_overall_stats_returns_copy(self) -> None:
        """Test that get_overall_stats returns a copy of statistics."""
        # Arrange
        metrics = CacheMetrics()
        metrics.record_hit("key1", 0.1)
        metrics.record_miss("key2", 0.2)

        # Act
        stats = metrics.get_overall_stats()

        # Assert
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_latencies == [0.1]
        assert stats.miss_latencies == [0.2]

        # Modifying returned stats should not affect internal stats
        stats.hits = 999
        assert metrics._overall_stats.hits == 1

    def test_get_key_stats_existing_key(self) -> None:
        """Test getting statistics for existing key."""
        # Arrange
        metrics = CacheMetrics()
        key = "test:key"
        metrics.record_hit(key, 0.1)
        metrics.record_write(key, 500)

        # Act
        stats = metrics.get_key_stats(key)

        # Assert
        assert stats is not None
        assert stats.hits == 1
        assert stats.writes == 1
        assert stats.hit_latencies == [0.1]
        assert stats.write_sizes == [500]

    def test_get_key_stats_nonexistent_key(self) -> None:
        """Test getting statistics for non-existent key."""
        # Arrange
        metrics = CacheMetrics()

        # Act
        stats = metrics.get_key_stats("nonexistent")

        # Assert
        assert stats is None

    def test_get_all_key_stats(self) -> None:
        """Test getting all key statistics."""
        # Arrange
        metrics = CacheMetrics()
        metrics.record_hit("key1", 0.1)
        metrics.record_miss("key2", 0.2)

        # Act
        all_stats = metrics.get_all_key_stats()

        # Assert
        assert len(all_stats) == 2
        assert "key1" in all_stats
        assert "key2" in all_stats
        assert all_stats["key1"].hits == 1
        assert all_stats["key2"].misses == 1

    def test_get_top_keys_by_hits(self) -> None:
        """Test getting top keys by hit count."""
        # Arrange
        metrics = CacheMetrics()
        metrics.record_hit("key1", 0.1)
        metrics.record_hit("key1", 0.1)  # 2 hits
        metrics.record_hit("key2", 0.1)  # 1 hit
        metrics.record_hit("key3", 0.1)
        metrics.record_hit("key3", 0.1)
        metrics.record_hit("key3", 0.1)  # 3 hits

        # Act
        top_keys = metrics.get_top_keys_by_hits(limit=2)

        # Assert
        assert len(top_keys) == 2
        assert top_keys[0].key == "key3"
        assert top_keys[0].count == 3
        assert top_keys[0].percentage == 50.0  # 3/6 * 100
        assert top_keys[1].key == "key1"
        assert top_keys[1].count == 2
        assert top_keys[1].percentage == pytest.approx(33.33, abs=0.01)

    def test_get_top_keys_by_misses(self) -> None:
        """Test getting top keys by miss count."""
        # Arrange
        metrics = CacheMetrics()
        metrics.record_miss("key1", 0.1)  # 1 miss
        metrics.record_miss("key2", 0.1)
        metrics.record_miss("key2", 0.1)  # 2 misses

        # Act
        top_keys = metrics.get_top_keys_by_misses()

        # Assert
        assert len(top_keys) == 2
        assert top_keys[0].key == "key2"
        assert top_keys[0].count == 2
        assert top_keys[0].percentage == pytest.approx(66.67, abs=0.01)

    def test_get_top_keys_by_writes(self) -> None:
        """Test getting top keys by write count."""
        # Arrange
        metrics = CacheMetrics()
        metrics.record_write("key1", 100)
        metrics.record_write("key1", 200)  # 2 writes
        metrics.record_write("key2", 300)  # 1 write

        # Act
        top_keys = metrics.get_top_keys_by_writes()

        # Assert
        assert len(top_keys) == 2
        assert top_keys[0].key == "key1"
        assert top_keys[0].count == 2
        assert top_keys[0].percentage == pytest.approx(66.67, abs=0.01)

    def test_get_top_keys_by_errors(self) -> None:
        """Test getting top keys by error count."""
        # Arrange
        metrics = CacheMetrics()
        error1 = ValueError("error1")
        error2 = ValueError("error2")

        metrics.record_error("key1", error1)
        metrics.record_error("key1", error1)  # 2 errors
        metrics.record_error("key2", error2)  # 1 error

        # Act
        top_keys = metrics.get_top_keys_by_errors()

        # Assert
        assert len(top_keys) == 2
        assert top_keys[0].key == "key1"
        assert top_keys[0].count == 2
        assert top_keys[0].percentage == pytest.approx(66.67, abs=0.01)

    def test_reset_stats_clears_all_data(self) -> None:
        """Test that reset_stats clears all collected data."""
        # Arrange
        metrics = CacheMetrics()
        metrics.record_hit("key1", 0.1)
        metrics.record_miss("key2", 0.2)

        # Act
        metrics.reset_stats()

        # Assert
        stats = metrics.get_overall_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert len(metrics._key_stats) == 0

    def test_reset_key_stats_existing_key(self) -> None:
        """Test resetting stats for existing key."""
        # Arrange
        metrics = CacheMetrics()
        metrics.record_hit("key1", 0.1)
        metrics.record_hit("key2", 0.1)

        # Act
        result = metrics.reset_key_stats("key1")

        # Assert
        assert result is True
        assert "key1" not in metrics._key_stats
        assert "key2" in metrics._key_stats

    def test_reset_key_stats_nonexistent_key(self) -> None:
        """Test resetting stats for non-existent key."""
        # Arrange
        metrics = CacheMetrics()

        # Act
        result = metrics.reset_key_stats("nonexistent")

        # Assert
        assert result is False

    def test_trim_latencies_when_exceeding_limit(self) -> None:
        """Test that latencies are trimmed when exceeding limit."""
        # Arrange
        metrics = CacheMetrics(max_latency_samples=3)
        key = "test:key"

        # Record more samples than limit
        metrics.record_hit(key, 0.1)
        metrics.record_hit(key, 0.2)
        metrics.record_hit(key, 0.3)
        metrics.record_hit(key, 0.4)
        metrics.record_hit(key, 0.5)

        # Act
        key_stats = metrics.get_key_stats(key)

        # Assert
        assert key_stats is not None
        assert len(key_stats.hit_latencies) == 3
        # Should keep the most recent samples
        assert key_stats.hit_latencies == [0.3, 0.4, 0.5]

    def test_trim_sizes_when_exceeding_limit(self) -> None:
        """Test that sizes are trimmed when exceeding limit."""
        # Arrange
        metrics = CacheMetrics(max_latency_samples=2)
        key = "test:key"

        # Record more samples than limit
        metrics.record_write(key, 100)
        metrics.record_write(key, 200)
        metrics.record_write(key, 300)

        # Act
        key_stats = metrics.get_key_stats(key)

        # Assert
        assert key_stats is not None
        assert len(key_stats.write_sizes) == 2
        # Should keep the most recent samples
        assert key_stats.write_sizes == [200, 300]


class TestMetricsCollectorHooks:
    """Test MetricsCollectorHooks implementation."""

    def test_metrics_collector_hooks_initialization_default(self) -> None:
        """Test initialization with default CacheMetrics."""
        # Arrange & Act
        hooks = MetricsCollectorHooks()

        # Assert
        assert isinstance(hooks.metrics, CacheMetrics)

    def test_metrics_collector_hooks_initialization_custom(self) -> None:
        """Test initialization with custom CacheMetrics."""
        # Arrange
        custom_metrics = CacheMetrics(max_latency_samples=100)

        # Act
        hooks = MetricsCollectorHooks(custom_metrics)

        # Assert
        assert hooks.metrics is custom_metrics

    def test_on_cache_hit_records_metric(self) -> None:
        """Test that cache hit is recorded in metrics."""
        # Arrange
        metrics = CacheMetrics()
        hooks = MetricsCollectorHooks(metrics)
        key = "test:key"
        latency = 0.1

        # Act
        hooks.on_cache_hit(key, latency)

        # Assert
        assert metrics.get_overall_stats().hits == 1

    def test_on_cache_miss_records_metric(self) -> None:
        """Test that cache miss is recorded in metrics."""
        # Arrange
        metrics = CacheMetrics()
        hooks = MetricsCollectorHooks(metrics)
        key = "test:key"
        latency = 0.2

        # Act
        hooks.on_cache_miss(key, latency)

        # Assert
        assert metrics.get_overall_stats().misses == 1

    def test_on_cache_write_records_metric(self) -> None:
        """Test that cache write is recorded in metrics."""
        # Arrange
        metrics = CacheMetrics()
        hooks = MetricsCollectorHooks(metrics)
        key = "test:key"
        size = 1024

        # Act
        hooks.on_cache_write(key, size)

        # Assert
        assert metrics.get_overall_stats().writes == 1

    def test_on_cache_error_records_metric(self) -> None:
        """Test that cache error is recorded in metrics."""
        # Arrange
        metrics = CacheMetrics()
        hooks = MetricsCollectorHooks(metrics)
        key = "test:key"
        error = ValueError("test")

        # Act
        hooks.on_cache_error(key, error)

        # Assert
        assert metrics.get_overall_stats().errors == 1

    def test_metrics_property(self) -> None:
        """Test metrics property getter."""
        # Arrange
        custom_metrics = CacheMetrics()
        hooks = MetricsCollectorHooks(custom_metrics)

        # Act
        result = hooks.metrics

        # Assert
        assert result is custom_metrics


class TestObservabilityIntegration:
    """Integration tests for observability components."""

    def test_metrics_and_hooks_integration(self) -> None:
        """Test integration between metrics and hooks."""
        # Arrange
        metrics = CacheMetrics()
        hooks = MetricsCollectorHooks(metrics)

        # Act - simulate cache operations
        hooks.on_cache_miss("key1", 0.1)
        hooks.on_cache_hit("key1", 0.05)
        hooks.on_cache_write("key1", 500)
        hooks.on_cache_error("key2", ValueError("error"))

        # Assert
        overall_stats = metrics.get_overall_stats()
        assert overall_stats.hits == 1
        assert overall_stats.misses == 1
        assert overall_stats.writes == 1
        assert overall_stats.errors == 1

        key1_stats = metrics.get_key_stats("key1")
        assert key1_stats is not None
        assert key1_stats.hits == 1
        assert key1_stats.misses == 1
        assert key1_stats.writes == 1
        assert key1_stats.errors == 0  # Error was for key2

        key2_stats = metrics.get_key_stats("key2")
        assert key2_stats is not None
        assert key2_stats.errors == 1

    def test_composite_with_metrics_and_logging(self) -> None:
        """Test composite hooks with both metrics and logging."""
        # Arrange
        metrics = CacheMetrics()
        metrics_hooks = MetricsCollectorHooks(metrics)
        logging_hooks = DefaultObservabilityHooks()

        composite = CompositeObservabilityHooks([metrics_hooks, logging_hooks])

        # Act
        composite.on_cache_hit("key1", 0.1)

        # Assert
        # Metrics should be recorded
        assert metrics.get_overall_stats().hits == 1

        # Both hooks should be in composite
        assert len(composite._hooks) == 2
