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
    "CacheMetrics",
    "CacheStats",
    "CompositeObservabilityHooks",
    "DefaultObservabilityHooks",
    "MetricsCollectorHooks",
    "SilentObservabilityHooks",
    "TopKeysResult",
]
