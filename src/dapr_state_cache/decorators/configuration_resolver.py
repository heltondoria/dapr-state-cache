"""
Configuration resolution for cache decorator.

Handles environment variable resolution and parameter validation
with single responsibility principle.
"""

from collections.abc import Callable
from dataclasses import dataclass

from ..protocols import KeyBuilder, ObservabilityHooks, Serializer
from .config import CacheConfig


@dataclass(frozen=True)
class ResolvedCacheConfig:
    """Immutable configuration object for cache decorator."""

    store_name: str
    ttl_seconds: int
    key_prefix: str
    key_builder: KeyBuilder | None
    serializer: Serializer | None
    use_dapr_crypto: bool
    crypto_component_name: str | None
    condition: Callable[..., bool] | None
    bypass: Callable[..., bool] | None
    hooks: ObservabilityHooks | None


class CacheConfigurationResolver:
    """Resolves cache configuration parameters with environment variable support.

    Single responsibility: Transform raw decorator parameters into validated,
    resolved configuration object following Clean Code principles.
    """

    @staticmethod
    def resolve_configuration(
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
    ) -> ResolvedCacheConfig:
        """Resolve all configuration parameters following precedence rules.

        Args:
            store_name: Dapr state store name (resolved from env if None)
            ttl_seconds: TTL in seconds (uses default if None)
            key_prefix: Prefix for cache keys
            key_builder: Custom key builder instance
            serializer: Custom serializer instance
            use_dapr_crypto: Whether to use Dapr cryptography
            crypto_component_name: Crypto component name (resolved from env if None)
            condition: Function to determine if result should be cached
            bypass: Function to determine if cache should be bypassed
            hooks: Observability hooks for metrics/logging

        Returns:
            Validated and resolved configuration object

        Raises:
            ValueError: If any parameter is invalid
        """
        # Resolve environment variables and defaults
        resolved_store_name = CacheConfig.resolve_store_name(store_name)
        resolved_ttl = CacheConfig.resolve_ttl_seconds(ttl_seconds) if ttl_seconds is None else ttl_seconds
        resolved_crypto_name = (
            CacheConfig.resolve_crypto_component_name(crypto_component_name) if use_dapr_crypto else None
        )

        # Validate all parameters
        CacheConfig.validate_parameters(
            store_name=resolved_store_name,
            ttl_seconds=resolved_ttl,
            key_prefix=key_prefix,
            use_dapr_crypto=use_dapr_crypto,
            crypto_component_name=resolved_crypto_name,
        )

        return ResolvedCacheConfig(
            store_name=resolved_store_name,
            ttl_seconds=resolved_ttl,
            key_prefix=key_prefix,
            key_builder=key_builder,
            serializer=serializer,
            use_dapr_crypto=use_dapr_crypto,
            crypto_component_name=resolved_crypto_name,
            condition=condition,
            bypass=bypass,
            hooks=hooks,
        )
