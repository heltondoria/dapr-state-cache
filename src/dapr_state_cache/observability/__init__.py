"""
Observability hooks and metrics.

This module provides comprehensive observability features including:
- Hook implementations for cache events
- Metrics collection and analysis
- Performance monitoring
- Top keys analysis
"""

from .hooks import (
    DefaultObservabilityHooks,
    SilentObservabilityHooks,
    CompositeObservabilityHooks,
)
from .metrics import (
    CacheStats,
    TopKeysResult,
    CacheMetrics,
    MetricsCollectorHooks,
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