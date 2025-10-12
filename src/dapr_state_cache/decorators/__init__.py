"""
Cache decorators and configuration.

This module provides the main @cacheable decorator and related utilities
for adding transparent caching capabilities to functions and methods.
"""

from .cacheable import (
    BoundMethodWrapper,
    CacheableWrapper,
    cacheable,
)
from .config import CacheConfig

__all__ = [
    # Main decorator
    "cacheable",
    # Wrapper classes (for advanced use)
    "CacheableWrapper",
    "BoundMethodWrapper",
    # Configuration
    "CacheConfig",
]
