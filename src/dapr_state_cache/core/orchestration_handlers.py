"""
Orchestration operation handlers for CacheOrchestrator.

Provides specialized handlers for cache orchestration operations following
Single Responsibility Principle and Clean Code practices.
"""

import logging
from collections.abc import Callable
from typing import Any

from .cache_service import CacheService
from .sync_async_bridge import execute_auto

logger = logging.getLogger(__name__)


class CacheBypassHandler:
    """Handles cache bypass logic and condition evaluation."""

    def should_bypass_cache(self, bypass: Callable[..., bool] | None, args: tuple, kwargs: dict) -> bool:
        """Evaluate if cache should be bypassed.

        Args:
            bypass: Bypass condition function
            args: Function arguments
            kwargs: Function keyword arguments

        Returns:
            True if cache should be bypassed, False otherwise
        """
        if not bypass:
            return False

        try:
            return bypass(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error evaluating bypass condition: {e}")
            return False


class CacheLookupHandler:
    """Handles cache lookup operations."""

    def __init__(self, cache_service: CacheService) -> None:
        """Initialize cache lookup handler.

        Args:
            cache_service: Cache service for lookup operations
        """
        self._cache_service = cache_service

    async def try_cache_lookup(self, func: Callable, args: tuple, kwargs: dict) -> tuple[Any | None, bool]:
        """Try to get value from cache.

        Args:
            func: Function for key generation
            args: Function arguments
            kwargs: Function keyword arguments

        Returns:
            Tuple of (cached_result, cache_hit_flag)
        """
        try:
            cached_result = await self._cache_service.get(func, args, kwargs)
            return cached_result, cached_result is not None
        except Exception as e:
            logger.error(f"Cache lookup failed for {func.__name__}: {e}")
            return None, False


class CacheComputationHandler:
    """Handles function computation and result caching."""

    def __init__(self, cache_service: CacheService) -> None:
        """Initialize computation handler.

        Args:
            cache_service: Cache service for storage operations
        """
        self._cache_service = cache_service

    async def compute_and_cache_result(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        ttl_seconds: int | None,
        condition: Callable[..., bool] | None,
    ) -> Any:
        """Compute function result and cache it if conditions are met.

        Args:
            func: Function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            ttl_seconds: TTL for cached result
            condition: Condition function for caching

        Returns:
            Computed function result
        """
        # Execute the function
        result = await self._execute_function(func, args, kwargs)

        # Check if we should cache the result
        if self._should_cache_result(condition, args, kwargs):
            await self._store_result_in_cache(func, args, kwargs, result, ttl_seconds)
        else:
            logger.debug(f"Caching condition not met for {func.__name__}")

        return result

    async def _execute_function(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """Execute function directly."""
        logger.debug(f"Executing function {func.__name__} directly")
        return await execute_auto(func, *args, **kwargs)

    def _should_cache_result(self, condition: Callable[..., bool] | None, args: tuple, kwargs: dict) -> bool:
        """Evaluate if result should be cached."""
        if not condition:
            return True

        try:
            return condition(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error evaluating cache condition: {e}")
            return False

    async def _store_result_in_cache(
        self, func: Callable, args: tuple, kwargs: dict, result: Any, ttl_seconds: int | None
    ) -> None:
        """Store result in cache (best-effort)."""
        try:
            logger.debug(f"Storing result in cache for function {func.__name__}")
            success = await self._cache_service.set(func, args, kwargs, result, ttl_seconds)
            if not success:
                logger.warning(f"Failed to cache result for function {func.__name__}")
        except Exception as e:
            logger.error(f"Error storing result in cache for {func.__name__}: {e}")
            # Don't propagate caching errors


class CacheOrchestrationCoordinator:
    """Coordinates the complete cache orchestration flow."""

    def __init__(
        self,
        cache_service: CacheService,
        bypass_handler: CacheBypassHandler,
        lookup_handler: CacheLookupHandler,
        computation_handler: CacheComputationHandler,
    ) -> None:
        """Initialize orchestration coordinator.

        Args:
            cache_service: Cache service for key generation
            bypass_handler: Handler for bypass logic
            lookup_handler: Handler for cache lookups
            computation_handler: Handler for computations
        """
        self._cache_service = cache_service
        self._bypass_handler = bypass_handler
        self._lookup_handler = lookup_handler
        self._computation_handler = computation_handler

    async def orchestrate_cache_operation(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        ttl_seconds: int | None,
        condition: Callable[..., bool] | None,
        bypass: Callable[..., bool] | None,
    ) -> tuple[bool, Any | None]:
        """Orchestrate cache bypass and lookup flow.

        Args:
            func: Function to execute and cache
            args: Function arguments
            kwargs: Function keyword arguments
            ttl_seconds: TTL for cached result
            condition: Condition function for caching
            bypass: Bypass function for cache skipping

        Returns:
            Tuple of (operation_completed, result). When operation_completed is
            True, result contains either the bypassed execution or cached value.
            When False, the caller must handle computation and storage.
        """
        logger.debug(f"Starting cache orchestration for function {func.__name__}")

        # Check bypass condition first
        if self._bypass_handler.should_bypass_cache(bypass, args, kwargs):
            logger.debug(f"Cache bypass triggered for {func.__name__}")
            return True, await self._execute_function_directly(func, args, kwargs)

        # Try cache lookup
        cached_result, cache_hit = await self._lookup_handler.try_cache_lookup(func, args, kwargs)
        if cache_hit:
            logger.debug(f"Cache hit for function {func.__name__}")
            return True, cached_result

        # Cache miss - compute and cache result
        logger.debug(f"Cache miss for function {func.__name__}, starting computation")
        return False, None

    async def _execute_function_directly(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """Execute function directly without caching."""
        logger.debug(f"Executing function {func.__name__} directly")
        return await execute_auto(func, *args, **kwargs)
