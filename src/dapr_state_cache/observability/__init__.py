"""
Observability hooks and metrics.

This module provides comprehensive observability features including:
- Hook implementations for cache events
- Metrics collection and analysis
- Performance monitoring
- Top keys analysis
"""

from .hooks import (
    CompositeObservabilityHooks,
    DefaultObservabilityHooks,
    SilentObservabilityHooks,
)
from .metrics import (
    CacheMetrics,
    CacheStats,
    MetricsCollectorHooks,
    TopKeysResult,
)

__all__ = [
    # Hook implementations
    "DefaultObservabilityHooks",
    "SilentObservabilityHooks",
    "CompositeObservabilityHooks",
    # Metrics
    "CacheStats",
    "TopKeysResult",
    "CacheMetrics",
    "MetricsCollectorHooks",
]
