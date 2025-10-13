"""
Cache orchestration and deduplication utilities.

This module provides orchestration components for managing cache operations
including deduplication to prevent thundering herd scenarios.
"""

from .deduplication import (
    DeduplicationManager,
    DeduplicationStats,
    InstrumentedDeduplicationManager,
)

__all__ = [
    # Deduplication
    "DeduplicationManager",
    "DeduplicationStats",
    "InstrumentedDeduplicationManager",
]
