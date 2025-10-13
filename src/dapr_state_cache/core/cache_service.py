"""
Cache service facade integrating all cache components.

Provides a unified interface for cache operations by coordinating
backend storage, serialization, key generation, and cryptography.
"""

import logging
from collections.abc import Callable
from typing import Any

from ..backend.dapr_state_backend import DaprStateBackend
from ..backend.exceptions import CacheKeyEmptyError, InvalidTTLValueError
from ..codecs.json_serializer import JsonSerializer
from ..keys.default_key_builder import DefaultKeyBuilder
from ..protocols import KeyBuilder, ObservabilityHooks, Serializer
from .cache_operations import CacheGetOperationHandler, CacheHealthChecker, CacheSetOperationHandler
from .constants import DEFAULT_KEY_PREFIX, DEFAULT_TTL_SECONDS
from .crypto_integration import CryptoIntegration, NoOpCryptoIntegration, create_crypto_integration

logger = logging.getLogger(__name__)


class CacheService:
    """Enterprise-grade cache service facade with comprehensive integration.

    High-level cache service that orchestrates all caching components into
    a unified, production-ready system. This facade implements the Service
    Layer pattern, providing a clean abstraction over complex cache operations
    while maintaining extensibility and configurability.

    The service acts as the central coordination point for all cache operations,
    handling the intricate details of serialization, key generation, encryption,
    error handling, and observability while presenting a simple, consistent
    interface to higher-level components.

    Architecture Integration:
        ```
        CacheService (Facade)
        ├── DaprStateBackend (Storage)
        ├── Serializer (Data encoding)
        ├── KeyBuilder (Key generation)
        ├── CryptoIntegration (Encryption)
        └── ObservabilityHooks (Monitoring)
        ```

    Core Capabilities:
        🔄 **Unified Operations**: Single interface for get/set/invalidate
        🔧 **Component Integration**: Seamless coordination of all subsystems
        🛡️ **Error Resilience**: Graceful fallbacks with comprehensive logging
        🔐 **Encryption Support**: Optional Dapr cryptography integration
        📊 **Observability**: Built-in hooks for metrics and monitoring
        🎯 **Type Safety**: Full type hints and runtime validation
        ⚡ **Performance**: Optimized operation flow with minimal overhead

    Error Handling Philosophy:
        The service implements a "best-effort" approach where cache operations
        never break application flow:

        - **Recoverable Errors**: Logged and gracefully handled (serialization,
          encryption, temporary network issues)
        - **Irrecoverable Errors**: Logged and propagated (Dapr unavailable,
          misconfiguration)
        - **Fallback Strategy**: Operations continue without caching when possible

    Component Pluggability:
        All major components are pluggable through dependency injection:

        ```python
        # Custom serializer for specific data types
        custom_serializer = MyProtocolBufferSerializer()

        # Custom key builder for specific naming strategy
        custom_keys = MyHierarchicalKeyBuilder()

        # Custom observability integration
        custom_hooks = MyPrometheusHooks()

        service = CacheService(
            store_name="myapp-cache",
            serializer=custom_serializer,
            key_builder=custom_keys,
            hooks=custom_hooks
        )
        ```

    Performance Characteristics:
        - **Memory**: Minimal overhead, stateless operation
        - **CPU**: Dominated by serialization and hashing (typically <1ms)
        - **Network**: Single round-trip per cache operation
        - **Latency**: Sub-millisecond for cache hits, backend-dependent for misses

    Thread Safety:
        The service is thread-safe and can be safely shared across multiple
        threads, coroutines, and concurrent operations. Internal operations
        are stateless and atomic.

    Example Usage:
        ```python
        # Basic service setup
        service = CacheService(
            store_name="user-cache",
            key_prefix="users",
            serializer=MsgpackSerializer(),  # Fast binary serialization
            use_dapr_crypto=True,           # Encrypt sensitive data
            hooks=MetricsCollectorHooks()   # Automatic metrics
        )

        # Cache operations
        async def example_operations():
            # Cache a user profile (with encryption)
            user_data = {"id": 123, "name": "John", "email": "john@example.com"}
            success = await service.set(
                func=get_user,
                args=(123,),
                kwargs={},
                value=user_data,
                ttl_seconds=3600
            )

            # Retrieve from cache
            cached_user = await service.get(get_user, (123,), {})
            if cached_user:
                print("Cache hit! User data retrieved instantly")
            else:
                print("Cache miss - need to fetch from database")

            # Invalidate when user updates
            await service.invalidate(get_user, (123,), {})

            # Bulk invalidation by prefix
            await service.invalidate_prefix("users:profile:")

        # Health monitoring
        health = await service.health_check()
        if health["service"] == "healthy":
            print("Cache service operational")
        ```

    Integration Patterns:
        ```python
        # Pattern 1: Service Layer Integration
        class UserService:
            def __init__(self):
                self.cache = CacheService("users")

            async def get_user_profile(self, user_id: int):
                # Try cache first
                cached = await self.cache.get(self._fetch_profile, (user_id,), {})
                if cached:
                    return cached

                # Cache miss - fetch and cache
                profile = await self._fetch_profile(user_id)
                await self.cache.set(self._fetch_profile, (user_id,), {}, profile)
                return profile

        # Pattern 2: Decorator Integration (via CacheOrchestrator)
        cache_service = CacheService("api-cache")

        @cacheable(cache_service=cache_service)
        async def expensive_api_call(endpoint: str, params: dict):
            return await make_api_request(endpoint, params)
        ```

    This service is typically used through higher-level abstractions like
    CacheOrchestrator or the @cacheable decorator, but can be used directly
    for custom caching implementations or advanced cache management scenarios.
    """

    def __init__(
        self,
        store_name: str,
        backend: DaprStateBackend | None = None,
        serializer: Serializer | None = None,
        key_builder: KeyBuilder | None = None,
        crypto_integration: CryptoIntegration | NoOpCryptoIntegration | None = None,
        hooks: ObservabilityHooks | None = None,
        key_prefix: str = DEFAULT_KEY_PREFIX,
    ) -> None:
        """Initialize cache service.

        Args:
            store_name: Dapr state store name
            backend: Backend storage implementation (creates default if None)
            serializer: Data serializer (uses JsonSerializer if None)
            key_builder: Key builder (uses DefaultKeyBuilder if None)
            crypto_integration: Crypto integration (no crypto if None)
            hooks: Observability hooks (no hooks if None)
            key_prefix: Prefix for cache keys
        """
        self._store_name = store_name
        self._key_prefix = key_prefix

        # Initialize components with defaults
        self._backend = backend or DaprStateBackend(store_name)
        self._serializer = serializer or JsonSerializer()
        self._key_builder = key_builder or DefaultKeyBuilder()
        self._crypto = crypto_integration or NoOpCryptoIntegration()
        self._hooks = hooks

        # Initialize operation handlers
        self._get_handler = CacheGetOperationHandler(self._serializer, self._crypto, self._hooks)
        self._set_handler = CacheSetOperationHandler(self._serializer, self._crypto, self._hooks)
        self._health_checker = CacheHealthChecker(self._store_name, self._key_prefix, self._serializer, self._crypto)

        logger.debug(f"Initialized CacheService for store '{store_name}' with prefix '{key_prefix}'")

    async def get(self, func: Callable, args: tuple, kwargs: dict) -> Any | None:
        """Get value from cache.

        Args:
            func: Function for key generation
            args: Function arguments
            kwargs: Function keyword arguments

        Returns:
            Cached value if found, None if cache miss or error
        """
        import time

        start_time = time.time()

        try:
            cache_key = self._build_cache_key(func, args, kwargs)
            serialized_data = await self._backend.get(cache_key)

            if serialized_data is None:
                # Cache miss - record metrics
                latency = time.time() - start_time
                if self._hooks:
                    self._hooks.on_cache_miss(cache_key, latency)
                return None

            return await self._get_handler.handle_get_operation(cache_key, serialized_data)

        except Exception as e:
            logger.error(f"Cache get operation failed: {e}")
            # Record cache miss for any error
            try:
                cache_key = self._build_cache_key(func, args, kwargs)
                latency = time.time() - start_time
                if self._hooks:
                    self._hooks.on_cache_miss(cache_key, latency)
            except Exception as hook_error:
                # Log hook failures but don't propagate to preserve cache semantics
                logger.warning(f"Failed to record cache miss metrics: {hook_error}")
            return None

    async def set(self, func: Callable, args: tuple, kwargs: dict, value: Any, ttl_seconds: int | None = None) -> bool:
        """Set value in cache.

        Args:
            func: Function for key generation
            args: Function arguments
            kwargs: Function keyword arguments
            value: Value to cache
            ttl_seconds: TTL in seconds (``None`` falls back to
                :data:`DEFAULT_TTL_SECONDS`)

        Returns:
            True if successfully cached, False if error occurred
        """
        try:
            cache_key = self._build_cache_key(func, args, kwargs)
            prepared_data = await self._set_handler.prepare_data_for_storage(cache_key, value)

            if prepared_data is None:
                return False

            # Apply default TTL when not provided to maintain backward compatibility
            effective_ttl = ttl_seconds if ttl_seconds is not None else DEFAULT_TTL_SECONDS
            self.validate_ttl(effective_ttl)

            await self._backend.set(cache_key, prepared_data, effective_ttl)

            self._set_handler.record_cache_write(cache_key, len(prepared_data))
            return True

        except Exception as e:
            logger.error(f"Cache set operation failed: {e}")
            return False

    async def invalidate(self, func: Callable, args: tuple, kwargs: dict) -> bool:
        """Invalidate specific cache entry.

        Args:
            func: Function for key generation
            args: Function arguments
            kwargs: Function keyword arguments

        Returns:
            True if successfully invalidated, False if error occurred
        """
        try:
            cache_key = self._build_cache_key(func, args, kwargs)
            await self._backend.invalidate(cache_key)
            logger.debug(f"Invalidated cache key '{cache_key}'")
            return True
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            try:
                cache_key = self._build_cache_key(func, args, kwargs)
                if self._hooks:
                    self._hooks.on_cache_error(cache_key, e)
            except Exception as hook_error:
                # Log hook failures but don't propagate to preserve cache semantics
                logger.warning(f"Failed to record cache error metrics for invalidation: {hook_error}")
            return False

    async def invalidate_prefix(self, prefix: str) -> bool:
        """Invalidate cache entries by prefix.

        Args:
            prefix: Key prefix to invalidate

        Returns:
            True if successfully invalidated, False if error occurred
        """
        try:
            await self._backend.invalidate_prefix(prefix)
            logger.debug(f"Invalidated cache keys with prefix '{prefix}'")
            return True
        except Exception as e:
            logger.error(f"Cache prefix invalidation failed for '{prefix}': {e}")
            if self._hooks:
                self._hooks.on_cache_error(prefix, e)
            return False

    def _build_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """Build cache key using configured key builder.

        Args:
            func: Function for key generation
            args: Function arguments
            kwargs: Function keyword arguments

        Returns:
            Generated cache key

        Raises:
            CacheKeyEmptyError: If generated key is empty
        """
        from .constants import ERROR_CACHE_KEY_EMPTY

        try:
            key = self._key_builder.build_key(func, args, kwargs)
            if not key or not key.strip():
                raise CacheKeyEmptyError(ERROR_CACHE_KEY_EMPTY)
            return key
        except Exception as e:
            logger.error(f"Key generation failed: {e}")
            raise

    def validate_ttl(self, ttl_seconds: int | None) -> None:
        """Validate TTL parameter.

        Args:
            ttl_seconds: TTL value to validate

        Raises:
            InvalidTTLValueError: If TTL is invalid
        """
        from .constants import MIN_TTL_SECONDS

        if ttl_seconds is not None and ttl_seconds < MIN_TTL_SECONDS:
            raise InvalidTTLValueError(f"TTL must be >= {MIN_TTL_SECONDS} second, got {ttl_seconds}")

    @property
    def store_name(self) -> str:
        """Get the store name."""
        return self._store_name

    @property
    def key_prefix(self) -> str:
        """Get the key prefix."""
        return self._key_prefix

    @property
    def backend(self) -> DaprStateBackend:
        """Get the backend instance."""
        return self._backend

    @property
    def serializer(self) -> Serializer:
        """Get the serializer instance."""
        return self._serializer

    @property
    def key_builder(self) -> KeyBuilder:
        """Get the key builder instance."""
        return self._key_builder

    @property
    def crypto_integration(self) -> CryptoIntegration | NoOpCryptoIntegration:
        """Get the crypto integration instance."""
        return self._crypto

    @property
    def hooks(self) -> ObservabilityHooks | None:
        """Get the observability hooks instance."""
        return self._hooks

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on cache service components.

        Returns:
            Dictionary with component health status
        """
        return await self._health_checker.check_component_health()


def create_cache_service(
    store_name: str,
    key_prefix: str = DEFAULT_KEY_PREFIX,
    serializer: Serializer | None = None,
    key_builder: KeyBuilder | None = None,
    use_dapr_crypto: bool = False,
    crypto_component_name: str | None = None,
    hooks: ObservabilityHooks | None = None,
    dapr_client: Any | None = None,
) -> CacheService:
    """Create CacheService with specified configuration.

    Args:
        store_name: Dapr state store name
        key_prefix: Prefix for cache keys
        serializer: Custom serializer (uses JsonSerializer if None)
        key_builder: Custom key builder (uses DefaultKeyBuilder if None)
        use_dapr_crypto: Whether to enable Dapr cryptography
        crypto_component_name: Name of crypto component (required if use_dapr_crypto=True)
        hooks: Observability hooks
        dapr_client: Optional DaprClient instance for backend and crypto

    Returns:
        Configured CacheService instance

    Raises:
        ValueError: If configuration is invalid
    """
    from .validators import validate_key_prefix, validate_store_name

    # Validate required parameters
    validate_store_name(store_name)
    validate_key_prefix(key_prefix)

    # Create backend
    backend = DaprStateBackend(store_name)

    # Create crypto integration
    crypto_integration = create_crypto_integration(
        use_dapr_crypto=use_dapr_crypto, crypto_component_name=crypto_component_name, dapr_client=dapr_client
    )

    return CacheService(
        store_name=store_name,
        backend=backend,
        serializer=serializer,
        key_builder=key_builder,
        crypto_integration=crypto_integration,
        hooks=hooks,
        key_prefix=key_prefix,
    )
