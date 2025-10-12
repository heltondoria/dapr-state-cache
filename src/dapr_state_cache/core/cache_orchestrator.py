"""
Cache orchestrator coordinating the complete cache flow.

Orchestrates cache operations by coordinating lookup, compute, store operations
with deduplication to prevent thundering herd scenarios and ensure optimal
cache performance.
"""

import logging
from typing import Any, Callable, Optional, cast

from .cache_service import CacheService
from .sync_async_bridge import SyncAsyncBridge, execute_auto
from ..orchestration.deduplication import DeduplicationManager

logger = logging.getLogger(__name__)


class CacheOrchestrator:
    """Orchestrates complete cache operations with deduplication.
    
    The CacheOrchestrator is responsible for coordinating the entire cache
    workflow including:
    
    1. Cache lookup via CacheService
    2. Deduplication management for cache misses
    3. Function execution for cache misses
    4. Cache storage for computed results
    5. Condition evaluation for caching decisions
    6. Error handling and fallback mechanisms
    
    Features:
    - Thundering herd protection via DeduplicationManager
    - Sync/async function support via SyncAsyncBridge
    - Conditional caching support
    - Cache bypass functionality
    - Comprehensive error handling
    - Observability integration
    
    The orchestrator ensures that:
    - Only one computation happens per cache key at a time
    - Results are shared among concurrent requests
    - Errors don't break the application flow (best-effort)
    - All operations are properly instrumented
    """

    def __init__(
        self,
        cache_service: CacheService,
        deduplication_manager: Optional[DeduplicationManager] = None,
        sync_async_bridge: Optional[SyncAsyncBridge] = None
    ) -> None:
        """Initialize cache orchestrator.
        
        Args:
            cache_service: Cache service for storage operations
            deduplication_manager: Manager for deduplication (creates default if None)
            sync_async_bridge: Bridge for sync/async execution (creates default if None)
        """
        self._cache_service = cache_service
        self._deduplication_manager = deduplication_manager or DeduplicationManager()
        self._sync_async_bridge = sync_async_bridge or SyncAsyncBridge()
        
        logger.debug("Initialized CacheOrchestrator")

    async def execute_with_cache(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        ttl_seconds: Optional[int] = None,
        condition: Optional[Callable[..., bool]] = None,
        bypass: Optional[Callable[..., bool]] = None
    ) -> Any:
        """Execute function with caching orchestration.
        
        This is the main orchestration method that handles the complete
        cache workflow including deduplication, conditional caching,
        and error handling.
        
        Args:
            func: Function to execute and cache
            args: Function arguments
            kwargs: Function keyword arguments
            ttl_seconds: TTL for cached result
            condition: Condition function for whether to cache (True = cache)
            bypass: Bypass function for whether to skip cache (True = skip)
            
        Returns:
            Function result (from cache or computation)
        """
        logger.debug(f"Starting cache orchestration for function {func.__name__}")
        
        try:
            # Check bypass condition first
            if bypass and self._evaluate_condition(bypass, args, kwargs):
                logger.debug(f"Cache bypass triggered for {func.__name__}")
                return await self._execute_function_directly(func, args, kwargs)
            
            # Try cache lookup first
            cached_result = await self._cache_service.get(func, args, kwargs)
            if cached_result is not None:
                logger.debug(f"Cache hit for function {func.__name__}")
                return cached_result
            
            # Cache miss - use deduplication for computation
            logger.debug(f"Cache miss for function {func.__name__}, starting computation")
            cache_key = self._cache_service._build_cache_key(func, args, kwargs)
            
            async def compute_and_store() -> Any:
                # Execute the function
                result = await self._execute_function_directly(func, args, kwargs)
                
                # Check if we should cache the result
                should_cache = True
                if condition:
                    should_cache = self._evaluate_condition(condition, args, kwargs)
                
                if should_cache:
                    # Store result in cache (best-effort)
                    await self._store_result_in_cache(
                        func, args, kwargs, result, ttl_seconds
                    )
                else:
                    logger.debug(f"Caching condition not met for {func.__name__}")
                
                return result
            
            # Use deduplication to prevent thundering herd
            return await self._deduplication_manager.deduplicate(
                cache_key, compute_and_store
            )
            
        except Exception as e:
            logger.error(f"Cache orchestration failed for {func.__name__}: {e}")
            # Fallback to direct execution on any orchestration error
            return await self._execute_function_directly(func, args, kwargs)

    async def invalidate_cache(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict
    ) -> bool:
        """Invalidate cache entry for specific function call.
        
        Args:
            func: Function whose cache entry to invalidate
            args: Function arguments
            kwargs: Function keyword arguments
            
        Returns:
            True if invalidation succeeded, False otherwise
        """
        logger.debug(f"Invalidating cache for function {func.__name__}")
        return await self._cache_service.invalidate(func, args, kwargs)

    async def invalidate_cache_prefix(self, prefix: str) -> bool:
        """Invalidate cache entries by prefix.
        
        Args:
            prefix: Cache key prefix to invalidate
            
        Returns:
            True if invalidation succeeded, False otherwise
        """
        logger.debug(f"Invalidating cache prefix '{prefix}'")
        return await self._cache_service.invalidate_prefix(prefix)

    async def _execute_function_directly(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict
    ) -> Any:
        """Execute function directly without caching.
        
        Handles both sync and async functions appropriately.
        
        Args:
            func: Function to execute
            args: Function arguments  
            kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        logger.debug(f"Executing function {func.__name__} directly")
        return await execute_auto(func, *args, **kwargs)

    async def _store_result_in_cache(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        result: Any,
        ttl_seconds: Optional[int]
    ) -> None:
        """Store result in cache (best-effort).
        
        Errors in caching don't affect the function result.
        
        Args:
            func: Function that produced the result
            args: Function arguments
            kwargs: Function keyword arguments
            result: Result to cache
            ttl_seconds: TTL for cached result
        """
        try:
            logger.debug(f"Storing result in cache for function {func.__name__}")
            success = await self._cache_service.set(func, args, kwargs, result, ttl_seconds)
            if not success:
                logger.warning(f"Failed to cache result for function {func.__name__}")
        except Exception as e:
            logger.error(f"Error storing result in cache for {func.__name__}: {e}")
            # Don't propagate caching errors

    def _evaluate_condition(
        self,
        condition: Callable[..., bool],
        args: tuple,
        kwargs: dict
    ) -> bool:
        """Evaluate a condition function safely.
        
        Args:
            condition: Condition function to evaluate
            args: Arguments to pass to condition
            kwargs: Keyword arguments to pass to condition
            
        Returns:
            True if condition is met, False on error or condition not met
        """
        try:
            logger.debug("Evaluating cache condition")
            return condition(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error evaluating cache condition: {e}")
            # Default to False on condition evaluation error
            return False

    @property
    def cache_service(self) -> CacheService:
        """Get the cache service instance."""
        return self._cache_service

    @property
    def deduplication_manager(self) -> DeduplicationManager:
        """Get the deduplication manager instance."""
        return self._deduplication_manager

    @property
    def sync_async_bridge(self) -> SyncAsyncBridge:
        """Get the sync/async bridge instance."""
        return self._sync_async_bridge

    async def get_cache_statistics(self) -> dict[str, Any]:
        """Get comprehensive cache statistics.
        
        Returns:
            Dictionary with cache and deduplication statistics
        """
        stats = {
            "orchestrator": {
                "store_name": self._cache_service.store_name,
                "key_prefix": self._cache_service.key_prefix,
            },
            "cache_service": await self._cache_service.health_check(),
            "deduplication": {
                "active_computations": await self._deduplication_manager.get_computation_count(),
                "computation_keys": await self._deduplication_manager.get_active_computations(),
            }
        }
        
        # Add observability statistics if hooks are available
        if self._cache_service.hooks:
            from ..observability.metrics import MetricsCollectorHooks
            if isinstance(self._cache_service.hooks, MetricsCollectorHooks):
                stats["metrics"] = await self._cache_service.hooks.get_stats()
        
        return stats

    async def clear_cache_computations(self) -> int:
        """Clear all active cache computations.
        
        This cancels any ongoing computations and clears the deduplication
        manager. Useful for testing or emergency cleanup.
        
        Returns:
            Number of computations that were cancelled
        """
        logger.warning("Clearing all active cache computations")
        return await self._deduplication_manager.clear_all_computations()


class OrchestrationError(Exception):
    """Base exception for orchestration errors."""
    pass


class CacheOrchestrationTimeout(OrchestrationError):
    """Cache orchestration operation timed out."""
    pass


def create_cache_orchestrator(
    cache_service: CacheService,
    enable_deduplication: bool = True,
    deduplication_manager: Optional[DeduplicationManager] = None,
    sync_async_bridge: Optional[SyncAsyncBridge] = None
) -> CacheOrchestrator:
    """Create a CacheOrchestrator with specified configuration.
    
    Args:
        cache_service: Cache service for storage operations
        enable_deduplication: Whether to enable deduplication (default True)
        deduplication_manager: Custom deduplication manager (creates default if None)
        sync_async_bridge: Custom sync/async bridge (creates default if None)
        
    Returns:
        Configured CacheOrchestrator instance
    """
    if not enable_deduplication:
        # Use a no-op deduplication manager
        deduplication_manager = cast(DeduplicationManager, NoOpDeduplicationManager())
    elif deduplication_manager is None:
        deduplication_manager = DeduplicationManager()
    
    return CacheOrchestrator(
        cache_service=cache_service,
        deduplication_manager=deduplication_manager,
        sync_async_bridge=sync_async_bridge
    )


class NoOpDeduplicationManager:
    """No-operation deduplication manager that doesn't deduplicate.
    
    Used when deduplication is disabled. Simply executes functions
    directly without any deduplication logic.
    """

    async def deduplicate(self, key: str, compute_func: Callable) -> Any:
        """Execute computation without deduplication.
        
        Args:
            key: Cache key (ignored)
            compute_func: Function to execute
            
        Returns:
            Result of compute_func
        """
        return await compute_func()

    async def is_computation_running(self, key: str) -> bool:
        """Always returns False (no computations tracked).
        
        Args:
            key: Cache key to check
            
        Returns:
            False (no-op implementation)
        """
        return False

    async def cancel_computation(self, key: str) -> bool:
        """Always returns False (no computations to cancel).
        
        Args:
            key: Cache key to cancel computation for
            
        Returns:
            False (no-op implementation)
        """
        return False

    async def get_active_computations(self) -> list[str]:
        """Returns empty list (no computations tracked).
        
        Returns:
            Empty list
        """
        return []

    async def get_computation_count(self) -> int:
        """Returns 0 (no computations tracked).
        
        Returns:
            0 (no-op implementation)
        """
        return 0

    async def clear_all_computations(self) -> int:
        """Returns 0 (no computations to clear).
        
        Returns:
            0 (no-op implementation)
        """
        return 0
