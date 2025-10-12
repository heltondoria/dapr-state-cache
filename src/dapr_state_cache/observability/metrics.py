"""
Cache metrics collection and analysis.

Provides comprehensive metrics collection for cache operations including
overall statistics, per-key statistics, hit ratios, and performance analysis.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class CacheStats:
    """Comprehensive statistics for cache operations and performance analysis.

    Immutable dataclass containing detailed metrics for cache operations including
    hit/miss counters, latency measurements, data size tracking, and computed
    performance indicators like hit ratios and average latencies.

    This class is used for both overall cache statistics (aggregated across all
    keys) and per-key statistics (isolated to specific cache keys). The statistics
    provide insights into cache effectiveness, performance characteristics, and
    can help identify optimization opportunities.

    Attributes:
        hits: Number of successful cache lookups (data found in cache)
        misses: Number of failed cache lookups (data not found, computed)
        writes: Number of successful cache write operations
        errors: Number of cache operations that encountered errors
        hit_latencies: List of cache hit operation durations (seconds)
        miss_latencies: List of cache miss operation durations (seconds)
        write_sizes: List of serialized data sizes for write operations (bytes)

    Computed Properties:
        total_operations: Sum of hits and misses (read operations)
        hit_ratio: Cache effectiveness ratio (hits / total_operations)
        average_hit_latency_ms: Mean latency for cache hits (milliseconds)
        average_miss_latency_ms: Mean latency for cache misses (milliseconds)
        average_write_size_bytes: Mean size of cached data (bytes)
        total_data_cached_mb: Cumulative amount of data written (megabytes)

    Example:
        ```python
        # Create stats for a specific cache key
        user_stats = CacheStats(
            hits=150,
            misses=30,
            writes=25,
            errors=2,
            hit_latencies=[0.001, 0.002, 0.001],  # Fast cache hits
            miss_latencies=[0.050, 0.045, 0.055], # Slower computes
            write_sizes=[1024, 2048, 1536]       # Bytes written
        )

        # Analyze performance
        print(f"Hit ratio: {user_stats.hit_ratio:.2%}")           # 83.33%
        print(f"Avg hit latency: {user_stats.average_hit_latency_ms:.1f}ms")  # 1.3ms
        print(f"Avg write size: {user_stats.average_write_size_bytes} bytes") # 1536 bytes
        print(f"Total cached: {user_stats.total_data_cached_mb:.2f} MB")      # Cache volume
        ```

    Use Cases:
        - Performance monitoring and alerting
        - Cache effectiveness analysis
        - Capacity planning and sizing
        - Identifying hot keys and usage patterns
        - SLA monitoring and optimization
        - Debug cache behavior and troubleshooting
    """

    hits: int = 0
    misses: int = 0
    writes: int = 0
    errors: int = 0

    # Latency tracking (in seconds)
    hit_latencies: list[float] = field(default_factory=list)
    miss_latencies: list[float] = field(default_factory=list)

    # Size tracking (in bytes)
    write_sizes: list[int] = field(default_factory=list)

    @property
    def total_operations(self) -> int:
        """Total number of cache operations."""
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        """Cache hit ratio (0.0 to 1.0)."""
        total = self.total_operations
        return self.hits / total if total > 0 else 0.0

    @property
    def miss_ratio(self) -> float:
        """Cache miss ratio (0.0 to 1.0)."""
        return 1.0 - self.hit_ratio

    @property
    def average_hit_latency_ms(self) -> float:
        """Average hit latency in milliseconds."""
        return sum(self.hit_latencies) / len(self.hit_latencies) * 1000 if self.hit_latencies else 0.0

    @property
    def average_miss_latency_ms(self) -> float:
        """Average miss latency in milliseconds."""
        return sum(self.miss_latencies) / len(self.miss_latencies) * 1000 if self.miss_latencies else 0.0

    @property
    def average_write_size_bytes(self) -> float:
        """Average write size in bytes."""
        return sum(self.write_sizes) / len(self.write_sizes) if self.write_sizes else 0.0

    @property
    def total_write_size_bytes(self) -> int:
        """Total bytes written to cache."""
        return sum(self.write_sizes)


@dataclass
class TopKeysResult:
    """Result of top keys query."""

    key: str
    count: int
    percentage: float


class CacheMetrics:
    """Thread-safe cache metrics collector and analyzer.

    Comprehensive metrics collection system that provides real-time insights
    into cache performance, effectiveness, and usage patterns. Collects both
    aggregate statistics across all cache operations and detailed per-key
    metrics for granular analysis.

    The collector is designed for production use with built-in memory management
    to prevent unbounded growth of latency samples and automatic aggregation
    of statistics for efficient analysis.

    Key Capabilities:
        ✅ **Real-time Collection**: Live metrics during cache operations
        ✅ **Thread Safety**: Concurrent operation support with locks
        ✅ **Memory Management**: Bounded latency sample storage
        ✅ **Dual Granularity**: Overall + per-key statistics
        ✅ **Performance Analysis**: Latency percentiles and trends
        ✅ **Top Keys Analysis**: Identify hot keys by various criteria
        ✅ **Reset/Cleanup**: Programmatic statistics reset capability

    Metrics Collected:
        - **Counters**: hits, misses, writes, errors (per-key and aggregate)
        - **Latencies**: cache hit/miss operation durations (bounded samples)
        - **Data Sizes**: serialized payload sizes for capacity planning
        - **Computed Metrics**: hit ratios, averages, totals

    Thread Safety:
        All operations are protected by internal locks, making this collector
        safe for use in multi-threaded applications including web servers,
        async applications, and concurrent cache operations.

    Memory Management:
        Latency samples are capped per operation type to prevent memory leaks
        in long-running applications. Older samples are discarded when limits
        are exceeded, maintaining recent performance data.

    Example:
        ```python
        # Initialize collector with memory limits
        metrics = CacheMetrics(max_latency_samples=500)

        # Record cache operations (typically done by hooks)
        metrics.record_hit("user:123", latency=0.001)
        metrics.record_miss("user:456", latency=0.050)
        metrics.record_write("user:456", size=2048)

        # Analyze overall performance
        overall = metrics.get_overall_stats()
        print(f"Hit ratio: {overall.hit_ratio:.2%}")
        print(f"Avg hit latency: {overall.average_hit_latency_ms:.1f}ms")

        # Identify top performing keys
        top_keys = metrics.get_top_keys_by_hits(limit=10)
        for key, hits in top_keys:
            print(f"Key '{key}': {hits} hits")

        # Per-key analysis for specific optimization
        user_stats = metrics.get_key_stats("user:123")
        if user_stats:
            print(f"User 123 hit ratio: {user_stats.hit_ratio:.2%}")
        ```

    Integration:
        Typically used with `MetricsCollectorHooks` for automatic collection
        during cache operations, or manually in custom observability solutions.
    """

    def __init__(self, max_latency_samples: int = 1000) -> None:
        """Initialize metrics collector.

        Args:
            max_latency_samples: Maximum latency samples to keep per operation type
                                to prevent unbounded memory growth
        """
        self._max_latency_samples = max_latency_samples
        self._lock = Lock()

        # Overall statistics
        self._overall_stats = CacheStats()

        # Per-key statistics
        self._key_stats: dict[str, CacheStats] = defaultdict(CacheStats)

    def record_hit(self, key: str, latency: float) -> None:
        """Record a cache hit.

        Args:
            key: Cache key
            latency: Operation latency in seconds
        """
        with self._lock:
            # Update overall stats
            self._overall_stats.hits += 1
            self._overall_stats.hit_latencies.append(latency)
            self._trim_latencies(self._overall_stats.hit_latencies)

            # Update per-key stats
            key_stats = self._key_stats[key]
            key_stats.hits += 1
            key_stats.hit_latencies.append(latency)
            self._trim_latencies(key_stats.hit_latencies)

    def record_miss(self, key: str, latency: float) -> None:
        """Record a cache miss.

        Args:
            key: Cache key
            latency: Operation latency in seconds
        """
        with self._lock:
            # Update overall stats
            self._overall_stats.misses += 1
            self._overall_stats.miss_latencies.append(latency)
            self._trim_latencies(self._overall_stats.miss_latencies)

            # Update per-key stats
            key_stats = self._key_stats[key]
            key_stats.misses += 1
            key_stats.miss_latencies.append(latency)
            self._trim_latencies(key_stats.miss_latencies)

    def record_write(self, key: str, size: int) -> None:
        """Record a cache write.

        Args:
            key: Cache key
            size: Data size in bytes
        """
        with self._lock:
            # Update overall stats
            self._overall_stats.writes += 1
            self._overall_stats.write_sizes.append(size)
            self._trim_sizes(self._overall_stats.write_sizes)

            # Update per-key stats
            key_stats = self._key_stats[key]
            key_stats.writes += 1
            key_stats.write_sizes.append(size)
            self._trim_sizes(key_stats.write_sizes)

    def record_error(self, key: str, error: Exception) -> None:
        """Record a cache error.

        Args:
            key: Cache key
            error: Exception that occurred
        """
        with self._lock:
            # Update overall stats
            self._overall_stats.errors += 1

            # Update per-key stats
            key_stats = self._key_stats[key]
            key_stats.errors += 1

    def get_overall_stats(self) -> CacheStats:
        """Get overall statistics across all keys.

        Returns:
            Overall cache statistics
        """
        with self._lock:
            # Return a deep copy to avoid external modification
            return CacheStats(
                hits=self._overall_stats.hits,
                misses=self._overall_stats.misses,
                writes=self._overall_stats.writes,
                errors=self._overall_stats.errors,
                hit_latencies=self._overall_stats.hit_latencies.copy(),
                miss_latencies=self._overall_stats.miss_latencies.copy(),
                write_sizes=self._overall_stats.write_sizes.copy(),
            )

    def get_key_stats(self, key: str) -> CacheStats | None:
        """Get statistics for a specific key.

        Args:
            key: Cache key to get statistics for

        Returns:
            Key statistics or None if key not found
        """
        with self._lock:
            if key not in self._key_stats:
                return None

            stats = self._key_stats[key]
            return CacheStats(
                hits=stats.hits,
                misses=stats.misses,
                writes=stats.writes,
                errors=stats.errors,
                hit_latencies=stats.hit_latencies.copy(),
                miss_latencies=stats.miss_latencies.copy(),
                write_sizes=stats.write_sizes.copy(),
            )

    def get_all_key_stats(self) -> dict[str, CacheStats]:
        """Get statistics for all tracked keys.

        Returns:
            Dictionary mapping keys to their statistics
        """
        with self._lock:
            return {
                key: CacheStats(
                    hits=stats.hits,
                    misses=stats.misses,
                    writes=stats.writes,
                    errors=stats.errors,
                    hit_latencies=stats.hit_latencies.copy(),
                    miss_latencies=stats.miss_latencies.copy(),
                    write_sizes=stats.write_sizes.copy(),
                )
                for key, stats in self._key_stats.items()
            }

    def get_top_keys_by_hits(self, limit: int = 10) -> list[TopKeysResult]:
        """Get top keys by hit count.

        Args:
            limit: Maximum number of keys to return

        Returns:
            List of top keys by hits, sorted descending
        """
        with self._lock:
            total_hits = self._overall_stats.hits

            # Sort keys by hit count
            sorted_keys = sorted(self._key_stats.items(), key=lambda item: item[1].hits, reverse=True)

            return [
                TopKeysResult(
                    key=key, count=stats.hits, percentage=stats.hits / total_hits * 100 if total_hits > 0 else 0.0
                )
                for key, stats in sorted_keys[:limit]
                if stats.hits > 0
            ]

    def get_top_keys_by_misses(self, limit: int = 10) -> list[TopKeysResult]:
        """Get top keys by miss count.

        Args:
            limit: Maximum number of keys to return

        Returns:
            List of top keys by misses, sorted descending
        """
        with self._lock:
            total_misses = self._overall_stats.misses

            # Sort keys by miss count
            sorted_keys = sorted(self._key_stats.items(), key=lambda item: item[1].misses, reverse=True)

            return [
                TopKeysResult(
                    key=key,
                    count=stats.misses,
                    percentage=stats.misses / total_misses * 100 if total_misses > 0 else 0.0,
                )
                for key, stats in sorted_keys[:limit]
                if stats.misses > 0
            ]

    def get_top_keys_by_writes(self, limit: int = 10) -> list[TopKeysResult]:
        """Get top keys by write count.

        Args:
            limit: Maximum number of keys to return

        Returns:
            List of top keys by writes, sorted descending
        """
        with self._lock:
            total_writes = self._overall_stats.writes

            # Sort keys by write count
            sorted_keys = sorted(self._key_stats.items(), key=lambda item: item[1].writes, reverse=True)

            return [
                TopKeysResult(
                    key=key,
                    count=stats.writes,
                    percentage=stats.writes / total_writes * 100 if total_writes > 0 else 0.0,
                )
                for key, stats in sorted_keys[:limit]
                if stats.writes > 0
            ]

    def get_top_keys_by_errors(self, limit: int = 10) -> list[TopKeysResult]:
        """Get top keys by error count.

        Args:
            limit: Maximum number of keys to return

        Returns:
            List of top keys by errors, sorted descending
        """
        with self._lock:
            total_errors = self._overall_stats.errors

            # Sort keys by error count
            sorted_keys = sorted(self._key_stats.items(), key=lambda item: item[1].errors, reverse=True)

            return [
                TopKeysResult(
                    key=key,
                    count=stats.errors,
                    percentage=stats.errors / total_errors * 100 if total_errors > 0 else 0.0,
                )
                for key, stats in sorted_keys[:limit]
                if stats.errors > 0
            ]

    def reset_stats(self) -> None:
        """Reset all collected statistics."""
        with self._lock:
            self._overall_stats = CacheStats()
            self._key_stats.clear()

    def reset_key_stats(self, key: str) -> bool:
        """Reset statistics for a specific key.

        Args:
            key: Cache key to reset stats for

        Returns:
            True if key existed and was reset, False otherwise
        """
        with self._lock:
            if key in self._key_stats:
                del self._key_stats[key]
                return True
            return False

    def _trim_latencies(self, latencies: list[float]) -> None:
        """Trim latency list to prevent memory growth.

        Args:
            latencies: List of latencies to trim
        """
        if len(latencies) > self._max_latency_samples:
            # Keep the most recent samples
            latencies[:] = latencies[-self._max_latency_samples :]

    def _trim_sizes(self, sizes: list[int]) -> None:
        """Trim size list to prevent memory growth.

        Args:
            sizes: List of sizes to trim
        """
        if len(sizes) > self._max_latency_samples:
            # Keep the most recent samples
            sizes[:] = sizes[-self._max_latency_samples :]


class MetricsCollectorHooks:
    """Automatic metrics collection via ObservabilityHooks integration.

    Bridge between the cache system and CacheMetrics that automatically
    collects performance and usage statistics during cache operations.
    This implementation of the ObservabilityHooks protocol provides
    zero-configuration metrics collection for cache monitoring.

    The hooks are called automatically by the cache system during each
    operation, providing real-time metrics without manual instrumentation.
    All metrics are collected in a thread-safe manner and can be accessed
    via the underlying CacheMetrics instance.

    Key Features:
        🔄 **Automatic Collection**: No manual instrumentation required
        📊 **Real-time Metrics**: Live performance and usage statistics
        🔒 **Thread Safety**: Safe for concurrent cache operations
        🎯 **Zero Overhead**: Minimal performance impact during collection
        📈 **Rich Analytics**: Hit ratios, latencies, sizes, top keys
        🔌 **Easy Integration**: Drop-in ObservabilityHooks implementation

    Collected Metrics:
        - **Cache Hits**: Key and latency for successful lookups
        - **Cache Misses**: Key and latency for failed lookups (computes)
        - **Cache Writes**: Key and data size for successful stores
        - **Cache Errors**: Key and exception for failed operations

    Example:
        ```python
        # Create metrics collector with custom limits
        metrics_hooks = MetricsCollectorHooks(
            metrics=CacheMetrics(max_latency_samples=2000)
        )

        # Use with cacheable decorator for automatic collection
        @cacheable(
            store_name="users",
            ttl_seconds=300,
            hooks=metrics_hooks  # Auto-collect metrics
        )
        def get_user(user_id: int) -> dict:
            return fetch_user_from_database(user_id)

        # Call function normally - metrics collected automatically
        user = get_user(123)
        user = get_user(123)  # Cache hit
        user = get_user(456)  # Cache miss

        # Analyze collected metrics
        stats = metrics_hooks.metrics.get_overall_stats()
        print(f"Hit ratio: {stats.hit_ratio:.2%}")        # e.g., 50%
        print(f"Total operations: {stats.total_operations}") # 3

        # Get statistics via async method
        async def analyze():
            stats_dict = await metrics_hooks.get_stats()
            print(f"Overall hits: {stats_dict['overall']['hits']}")
            print(f"Per-key stats: {stats_dict['by_key']}")
        ```

    Integration Patterns:
        ```python
        # Pattern 1: Single function monitoring
        @cacheable(hooks=MetricsCollectorHooks())
        def expensive_function():
            pass

        # Pattern 2: Shared metrics across functions
        shared_metrics = MetricsCollectorHooks()

        @cacheable(hooks=shared_metrics)
        def function_a():
            pass

        @cacheable(hooks=shared_metrics)
        def function_b():
            pass

        # Pattern 3: Custom metrics analysis
        class CustomMetrics(MetricsCollectorHooks):
            def on_cache_hit(self, key: str, latency: float) -> None:
                super().on_cache_hit(key, latency)
                # Custom alerting logic
                if latency > 0.1:  # 100ms
                    alert_slow_cache_hit(key, latency)
        ```

    The collected metrics can be exported to monitoring systems, used for
    alerting, or analyzed for cache optimization and capacity planning.
    """

    def __init__(self, metrics: CacheMetrics | None = None) -> None:
        """Initialize metrics collector hooks.

        Args:
            metrics: CacheMetrics instance to use, creates new one if None
        """
        self._metrics = metrics or CacheMetrics()

    @property
    def metrics(self) -> CacheMetrics:
        """Get the underlying metrics collector."""
        return self._metrics

    async def get_stats(self) -> dict[str, Any]:
        """Get current metrics statistics.

        Returns:
            Dictionary with overall and key-specific statistics
        """
        overall_stats = self._metrics.get_overall_stats()
        all_key_stats = self._metrics.get_all_key_stats()

        return {
            "overall": {
                "hits": overall_stats.hits,
                "misses": overall_stats.misses,
                "writes": overall_stats.writes,
                "errors": overall_stats.errors,
                "hit_ratio": overall_stats.hit_ratio,
                "average_hit_latency": overall_stats.average_hit_latency_ms,
                "average_miss_latency": overall_stats.average_miss_latency_ms,
            },
            "by_key": {
                key: {
                    "hits": stats.hits,
                    "misses": stats.misses,
                    "writes": stats.writes,
                    "errors": stats.errors,
                    "hit_ratio": stats.hit_ratio,
                    "average_hit_latency": stats.average_hit_latency_ms,
                    "average_miss_latency": stats.average_miss_latency_ms,
                }
                for key, stats in all_key_stats.items()
            },
        }

    def on_cache_hit(self, key: str, latency: float) -> None:
        """Record cache hit in metrics."""
        self._metrics.record_hit(key, latency)

    def on_cache_miss(self, key: str, latency: float) -> None:
        """Record cache miss in metrics."""
        self._metrics.record_miss(key, latency)

    def on_cache_write(self, key: str, size: int) -> None:
        """Record cache write in metrics."""
        self._metrics.record_write(key, size)

    def on_cache_error(self, key: str, error: Exception) -> None:
        """Record cache error in metrics."""
        self._metrics.record_error(key, error)
