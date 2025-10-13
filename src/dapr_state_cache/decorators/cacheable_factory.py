"""
Main factory for creating cacheable decorators.

Orchestrates the creation of cache decorators following Clean Code principles
and Factory Pattern, with single responsibility per class.
"""

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from ..protocols import KeyBuilder, ObservabilityHooks, Serializer
from .cacheable import CacheableWrapper
from .component_builder import CacheComponentBuilder
from .configuration_resolver import CacheConfigurationResolver
from .wrapper_builder import CacheableWrapperBuilder

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CacheDecoratorFactory:
    """Main factory for creating cacheable decorators.

    Single responsibility: Orchestrate the creation of cache decorators
    by coordinating configuration resolution, component building, and wrapper creation.
    Follows Clean Code principles with methods ≤20 lines.
    """

    def __init__(
        self,
        configuration_resolver: CacheConfigurationResolver | None = None,
        component_builder: CacheComponentBuilder | None = None,
        wrapper_builder: CacheableWrapperBuilder | None = None,
    ) -> None:
        """Initialize factory with optional dependency injection.

        Args:
            configuration_resolver: Custom configuration resolver (uses default if None)
            component_builder: Custom component builder (uses default if None)
            wrapper_builder: Custom wrapper builder (uses default if None)
        """
        self._configuration_resolver = configuration_resolver or CacheConfigurationResolver()
        self._component_builder = component_builder or CacheComponentBuilder()
        self._wrapper_builder = wrapper_builder or CacheableWrapperBuilder()

    def create_decorator(
        self,
        store_name: str | None = None,
        ttl_seconds: int | None = None,
        key_prefix: str = "cache",
        key_builder: KeyBuilder | None = None,
        serializer: Serializer | None = None,
        use_dapr_crypto: bool = False,
        crypto_component_name: str | None = None,
        condition: Callable[..., bool] | None = None,
        bypass: Callable[..., bool] | None = None,
        hooks: ObservabilityHooks | None = None,
    ) -> Callable[[F], CacheableWrapper]:
        """Create a cacheable decorator with the specified configuration.

        Args:
            store_name: Dapr state store name (default from env or "cache")
            ttl_seconds: TTL in seconds (default 3600, None uses default)
            key_prefix: Prefix for cache keys (default "cache")
            key_builder: Custom key builder (uses DefaultKeyBuilder if None)
            serializer: Custom serializer (uses JsonSerializer if None)
            use_dapr_crypto: Enable Dapr cryptography (default False)
            crypto_component_name: Crypto component name (default from env or "cache-crypto")
            condition: Function to determine if result should be cached
            bypass: Function to determine if cache should be bypassed
            hooks: Observability hooks for metrics/logging

        Returns:
            Decorator function that creates cacheable wrappers

        Raises:
            ValueError: If configuration parameters are invalid
        """

        def decorator(func: F) -> CacheableWrapper:
            return self._create_cacheable_wrapper(
                func=func,
                store_name=store_name,
                ttl_seconds=ttl_seconds,
                key_prefix=key_prefix,
                key_builder=key_builder,
                serializer=serializer,
                use_dapr_crypto=use_dapr_crypto,
                crypto_component_name=crypto_component_name,
                condition=condition,
                bypass=bypass,
                hooks=hooks,
            )

        return decorator

    def _create_cacheable_wrapper(
        self,
        func: F,
        store_name: str | None,
        ttl_seconds: int | None,
        key_prefix: str,
        key_builder: KeyBuilder | None,
        serializer: Serializer | None,
        use_dapr_crypto: bool,
        crypto_component_name: str | None,
        condition: Callable[..., bool] | None,
        bypass: Callable[..., bool] | None,
        hooks: ObservabilityHooks | None,
    ) -> CacheableWrapper:
        """Create cacheable wrapper for a specific function.

        Single responsibility: Coordinate the creation process by delegating
        to specialized builders while handling logging and error management.

        Args:
            func: Function to wrap
            ... (same as create_decorator)

        Returns:
            Configured cacheable wrapper

        Raises:
            ValueError: If configuration is invalid
            Exception: If component creation fails
        """
        logger.debug(f"Creating cacheable wrapper for function {func.__name__}")

        try:
            # Step 1: Resolve configuration
            config = self._resolve_configuration(
                store_name,
                ttl_seconds,
                key_prefix,
                key_builder,
                serializer,
                use_dapr_crypto,
                crypto_component_name,
                condition,
                bypass,
                hooks,
            )

            # Step 2: Build components
            _, orchestrator, bridge = self._component_builder.build_all_components(config)

            # Step 3: Create wrapper
            wrapper = self._wrapper_builder.build_wrapper(func, orchestrator, bridge, config)

            logger.debug(f"Successfully created cacheable wrapper for {func.__name__}")
            return wrapper

        except Exception as e:
            logger.error(f"Failed to create cacheable wrapper for {func.__name__}: {e}")
            raise

    def _resolve_configuration(
        self,
        store_name: str | None,
        ttl_seconds: int | None,
        key_prefix: str,
        key_builder: KeyBuilder | None,
        serializer: Serializer | None,
        use_dapr_crypto: bool,
        crypto_component_name: str | None,
        condition: Callable[..., bool] | None,
        bypass: Callable[..., bool] | None,
        hooks: ObservabilityHooks | None,
    ):
        """Resolve configuration using the configuration resolver.

        Single responsibility: Delegate configuration resolution while
        maintaining clean parameter passing.
        """
        return self._configuration_resolver.resolve_configuration(
            store_name=store_name,
            ttl_seconds=ttl_seconds,
            key_prefix=key_prefix,
            key_builder=key_builder,
            serializer=serializer,
            use_dapr_crypto=use_dapr_crypto,
            crypto_component_name=crypto_component_name,
            condition=condition,
            bypass=bypass,
            hooks=hooks,
        )
