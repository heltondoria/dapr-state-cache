"""
Wrapper builder for cacheable functions.

Single responsibility: Build CacheableWrapper instances with proper configuration,
following Clean Code and Builder Pattern principles.
"""

from collections.abc import Callable
from typing import Any

from ..core import CacheOrchestrator, SyncAsyncBridge
from .cacheable import CacheableWrapper
from .configuration_resolver import ResolvedCacheConfig


class CacheableWrapperBuilder:
    """Builder for creating CacheableWrapper instances.

    Single responsibility: Construct cacheable wrappers from configuration
    and components, ensuring proper initialization and metadata copying.
    """

    @staticmethod
    def build_wrapper(
        func: Callable[..., Any],
        orchestrator: CacheOrchestrator,
        bridge: SyncAsyncBridge,
        config: ResolvedCacheConfig,
    ) -> CacheableWrapper:
        """Build a CacheableWrapper instance from function and components.

        Args:
            func: Original function to wrap
            orchestrator: Cache orchestrator for operations
            bridge: Sync/async bridge for execution
            config: Resolved configuration object

        Returns:
            Configured cacheable wrapper instance
        """
        return CacheableWrapper(
            func=func,
            orchestrator=orchestrator,
            bridge=bridge,
            ttl_seconds=config.ttl_seconds,
            condition=config.condition,
            bypass=config.bypass,
        )
