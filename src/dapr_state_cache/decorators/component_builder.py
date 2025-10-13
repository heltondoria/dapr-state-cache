"""
Component builder for cache services and orchestrators.

Single responsibility: Create and configure cache components
following Factory Pattern and Clean Code principles.
"""

from ..core import CacheOrchestrator, CacheService, SyncAsyncBridge, create_cache_orchestrator, create_cache_service
from .configuration_resolver import ResolvedCacheConfig


class CacheComponentBuilder:
    """Factory for creating cache service and orchestrator components.

    Single responsibility: Build cache components from configuration,
    ensuring proper dependency injection and clean separation.
    """

    @staticmethod
    def build_cache_service(config: ResolvedCacheConfig) -> CacheService:
        """Create cache service from configuration.

        Args:
            config: Resolved cache configuration

        Returns:
            Configured cache service instance
        """
        return create_cache_service(
            store_name=config.store_name,
            key_prefix=config.key_prefix,
            serializer=config.serializer,
            key_builder=config.key_builder,
            use_dapr_crypto=config.use_dapr_crypto,
            crypto_component_name=config.crypto_component_name,
            hooks=config.hooks,
        )

    @staticmethod
    def build_orchestrator(cache_service: CacheService) -> CacheOrchestrator:
        """Create cache orchestrator with deduplication enabled.

        Args:
            cache_service: Configured cache service

        Returns:
            Cache orchestrator with deduplication enabled
        """
        return create_cache_orchestrator(cache_service=cache_service, enable_deduplication=True)

    @staticmethod
    def build_sync_async_bridge() -> SyncAsyncBridge:
        """Create sync/async bridge for execution context handling.

        Returns:
            Configured sync/async bridge instance
        """
        return SyncAsyncBridge()

    @classmethod
    def build_all_components(
        cls, config: ResolvedCacheConfig
    ) -> tuple[CacheService, CacheOrchestrator, SyncAsyncBridge]:
        """Build all required components from configuration.

        Args:
            config: Resolved cache configuration

        Returns:
            Tuple of (cache_service, orchestrator, bridge)
        """
        cache_service = cls.build_cache_service(config)
        orchestrator = cls.build_orchestrator(cache_service)
        bridge = cls.build_sync_async_bridge()
        return cache_service, orchestrator, bridge
