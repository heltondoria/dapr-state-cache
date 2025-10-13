"""
Main cacheable decorator implementation.

Provides the @cacheable decorator with full feature support including:
- 10 configurable parameters
- Sync/async function support
- Sync/async function support
- Descriptor protocol for method support
- Invalidation methods
- Environment variable configuration
"""

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from ..core import CacheOrchestrator, CacheService, SyncAsyncBridge
else:
    from ..core import CacheOrchestrator, CacheService, SyncAsyncBridge
from ..protocols import KeyBuilder, ObservabilityHooks, Serializer

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class InvalidationMethods:
    """Mixin providing cache invalidation methods.

    This mixin provides async and sync invalidation methods for cache entries.
    It requires the implementing class to have _orchestrator, _func, and _bridge attributes.
    """

    if TYPE_CHECKING:
        # Type hints for attributes expected from implementing class
        _orchestrator: "CacheOrchestrator"
        _func: Callable
        _bridge: "SyncAsyncBridge"

    def __init__(self) -> None:
        """Initialize invalidation methods mixin.

        Note: This mixin expects the implementing class to provide:
        - _orchestrator: CacheOrchestrator instance
        - _func: The wrapped function
        - _bridge: SyncAsyncBridge instance
        """
        # Initialize only if not already set by parent class
        if not hasattr(self, "_orchestrator"):
            self._orchestrator = None  # type: ignore
        if not hasattr(self, "_func"):
            self._func = None  # type: ignore
        if not hasattr(self, "_bridge"):
            self._bridge = None  # type: ignore

    async def invalidate(self, *args: Any, **kwargs: Any) -> bool:
        """Invalidate cache entry for specific arguments (async).

        Args:
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            True if invalidation succeeded, False otherwise
        """
        return await self._orchestrator.invalidate_cache(self._func, args, kwargs)

    async def invalidate_prefix(self, prefix: str) -> bool:
        """Invalidate cache entries by prefix (async).

        Args:
            prefix: Cache key prefix to invalidate

        Returns:
            True if invalidation succeeded, False otherwise
        """
        return await self._orchestrator.invalidate_cache_prefix(prefix)

    def invalidate_sync(self, *args: Any, **kwargs: Any) -> bool:
        """Invalidate cache entry for specific arguments (sync).

        Args:
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            True if invalidation succeeded, False otherwise
        """
        return self._bridge.execute_auto_sync(self.invalidate, *args, **kwargs)

    def invalidate_prefix_sync(self, prefix: str) -> bool:
        """Invalidate cache entries by prefix (sync).

        Args:
            prefix: Cache key prefix to invalidate

        Returns:
            True if invalidation succeeded, False otherwise
        """
        return self._bridge.execute_auto_sync(self.invalidate_prefix, prefix)


class DescriptorProtocolMixin:
    """Mixin providing descriptor protocol support."""

    def __init__(self) -> None:
        # Initialize only if not already set by parent class
        if not hasattr(self, "_owner_class"):
            self._owner_class: type | None = None
        if not hasattr(self, "_instance_bound"):
            self._instance_bound = False

    def __set_name__(self, owner: type, name: str) -> None:
        """Set name when used as class attribute (descriptor protocol)."""
        self._owner_class = owner
        self.__name__ = name


class CacheableWrapper(InvalidationMethods, DescriptorProtocolMixin):
    """Wrapper for cached functions with full feature support.


    This class wraps functions decorated with @cacheable and provides transparent
    caching functionality. It implements the descriptor protocol to support
    caching functionality. It implements the descriptor protocol to support
    instance methods, class methods, and static methods while preserving proper
    binding semantics.


    Key Features:
        - Transparent caching for sync/async functions
        - Cache invalidation methods (invalidate, invalidate_sync, invalidate_prefix)
        - Descriptor protocol support for method decoration
        - Conditional caching and bypass functionality
        - Shared cache between instances (self/cls excluded from keys)
        - Preserved function metadata and annotations
        - Integration with CacheOrchestrator for orchestration


    The wrapper automatically detects function types (sync/async) and handles
    execution context appropriately using SyncAsyncBridge. Cache keys are
    generated deterministically, excluding 'self' and 'cls' parameters to
    enable cache sharing between instances of the same class.


    Example:
        ```python
        @cacheable(store_name="users", ttl_seconds=300)
        def get_user(user_id: int) -> dict:
            return fetch_user_from_database(user_id)


        # Cache can be invalidated
        get_user.invalidate_sync(123)
        ```


    Attributes:
        _func: The original wrapped function
        _orchestrator: Cache orchestrator for cache operations
        _orchestrator: Cache orchestrator for cache operations
        _bridge: Sync/async bridge for context handling
        _ttl_seconds: Default TTL for cache entries (None uses backend default)
        _condition: Optional condition function for caching
        _bypass: Optional bypass function to skip cache
        _owner_class: Class that owns this method (set by __set_name__)
    """

    def __init__(
        self,
        func: Callable,
        orchestrator: CacheOrchestrator,
        bridge: SyncAsyncBridge,
        ttl_seconds: int | None,
        condition: Callable[..., bool] | None,
        bypass: Callable[..., bool] | None,
    ) -> None:
        """Initialize cacheable wrapper following Clean Code principles.

        Args:
            func: Original function to wrap
            orchestrator: Cache orchestrator for operations
            bridge: Sync/async bridge for execution
            ttl_seconds: TTL for cached results
            condition: Condition for caching
            bypass: Condition for bypassing cache
        """
        self._initialize_core_attributes(func, orchestrator, bridge, ttl_seconds, condition, bypass)
        self._copy_function_metadata(func)
        self._setup_mixins()

    def _initialize_core_attributes(
        self,
        func: Callable,
        orchestrator: CacheOrchestrator,
        bridge: SyncAsyncBridge,
        ttl_seconds: int | None,
        condition: Callable[..., bool] | None,
        bypass: Callable[..., bool] | None,
    ) -> None:
        """Initialize core wrapper attributes.

        Single responsibility: Set primary instance attributes
        following dependency injection principles.
        """
        self._func = func
        self._orchestrator = orchestrator
        self._bridge = bridge
        self._ttl_seconds = ttl_seconds
        self._condition = condition
        self._bypass = bypass

    def _setup_mixins(self) -> None:
        """Initialize mixin classes after core attributes are set.

        Single responsibility: Proper mixin initialization order
        ensuring attributes are available for mixin constructors.
        """
        InvalidationMethods.__init__(self)
        DescriptorProtocolMixin.__init__(self)

    def _copy_function_metadata(self, func: Callable) -> None:
        """Copy metadata from original function to wrapper.

        Args:
            func: Original function to copy metadata from
        """
        self.__name__ = getattr(func, "__name__", "wrapped_function")
        self.__doc__ = getattr(func, "__doc__", None)
        self.__module__ = getattr(func, "__module__", "<unknown>")
        self.__qualname__ = getattr(func, "__qualname__", "wrapped_function")
        self.__annotations__ = getattr(func, "__annotations__", {})

    def __get__(self, instance: Any, owner: type | None = None) -> "CacheableWrapper | BoundMethodWrapper":
        """Descriptor protocol: return bound method or unbound function."""
        if instance is None:
            # Accessed on class - return unbound wrapper
            return self

        # Accessed on instance - return bound method wrapper
        return BoundMethodWrapper(instance=instance, cacheable_wrapper=self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the cached function with automatic sync/async detection."""
        # Detect if we're in async context
        try:
            asyncio.get_running_loop()
            is_async_context = True
        except RuntimeError:
            is_async_context = False

        if is_async_context:
            # In async context - return coroutine
            return self._async_call(*args, **kwargs)
        else:
            # In sync context - execute synchronously
            return self.__call_sync__(*args, **kwargs)

    async def _async_call(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the cached function (async version)."""
        return await self._orchestrator.execute_with_cache(
            func=self._func,
            args=args,
            kwargs=kwargs,
            ttl_seconds=self._ttl_seconds,
            condition=self._condition,
            bypass=self._bypass,
        )

    def __call_sync__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the cached function (sync version)."""
        if inspect.iscoroutinefunction(self._func):
            # Async function called from sync context
            return self._bridge.run_async_in_sync(self._async_call, *args, **kwargs)
        else:
            # Sync function - execute through orchestrator using bridge
            return self._bridge.run_async_in_sync(self._async_call, *args, **kwargs)

    @property
    def cache_service(self) -> CacheService:
        """Get the underlying cache service."""
        return self._orchestrator.cache_service

    @property
    def orchestrator(self) -> CacheOrchestrator:
        """Get the cache orchestrator."""
        return self._orchestrator


class BoundMethodWrapper:
    """Wrapper for bound methods that handles instance context.


    This wrapper is created when a decorated method is accessed on an instance.
    It automatically filters out 'self' or 'cls' from cache key generation
    to enable cache sharing between instances.
    """

    def __init__(self, instance: Any, cacheable_wrapper: CacheableWrapper) -> None:
        """Initialize bound method wrapper.


        Args:
            instance: Instance the method is bound to
            cacheable_wrapper: Original cacheable wrapper
        """
        self._instance = instance
        self._wrapper = cacheable_wrapper

        # Copy attributes for transparent access
        self.__name__ = cacheable_wrapper.__name__
        self.__doc__ = cacheable_wrapper.__doc__

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the bound method with automatic sync/async handling."""
        # Determine if we're in async context
        try:
            asyncio.get_running_loop()
            is_async_context = True
        except RuntimeError:
            is_async_context = False

        # Include instance in args for function execution
        full_args = (self._instance, *args)

        if is_async_context:
            # In async context - return coroutine
            return self._wrapper._async_call(*full_args, **kwargs)
        else:
            # In sync context - execute synchronously
            return self._wrapper.__call_sync__(*full_args, **kwargs)

    # Delegate invalidation methods
    async def invalidate(self, *args: Any, **kwargs: Any) -> bool:
        """Invalidate cache for this method with instance context."""
        full_args = (self._instance, *args)
        return await self._wrapper.invalidate(*full_args, **kwargs)

    def invalidate_sync(self, *args: Any, **kwargs: Any) -> bool:
        """Invalidate cache for this method with instance context (sync)."""
        full_args = (self._instance, *args)
        return self._wrapper.invalidate_sync(*full_args, **kwargs)

    async def invalidate_prefix(self, prefix: str) -> bool:
        """Invalidate cache entries by prefix."""
        return await self._wrapper.invalidate_prefix(prefix)

    def invalidate_prefix_sync(self, prefix: str) -> bool:
        """Invalidate cache entries by prefix (sync)."""
        return self._wrapper.invalidate_prefix_sync(prefix)

    @property
    def cache_service(self) -> CacheService:
        """Get the underlying cache service."""
        return self._wrapper.cache_service

    @property
    def orchestrator(self) -> CacheOrchestrator:
        """Get the cache orchestrator."""
        return self._wrapper.orchestrator


def cacheable(
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
) -> Callable[[Any], CacheableWrapper]:
    """Decorator for adding transparent caching to functions and methods.


    This decorator provides comprehensive caching functionality with support for:
    - Sync and async functions, configurable TTL and conditions, multiple serialization formats
    - Optional Dapr cryptography, observability hooks, and cache invalidation methods

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
        Decorated function with caching capabilities

    Example:
        >>> @cacheable(store_name="users", ttl_seconds=300)
        ... def get_user(user_id: int) -> dict:
        ...     return fetch_user_from_db(user_id)
    """
    from .cacheable_factory import CacheDecoratorFactory

    factory = CacheDecoratorFactory()
    return factory.create_decorator(
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
