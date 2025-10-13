"""
Default observability hooks implementation.

Provides basic implementations of ObservabilityHooks protocol for
common observability patterns and logging integration.
"""

import logging

from ..protocols import ObservabilityHooks

logger = logging.getLogger(__name__)


class DefaultObservabilityHooks:
    """Default implementation of ObservabilityHooks protocol.

    Provides basic logging for all cache events. Can be used as-is
    or as a base class for custom hook implementations.

    Features:
    - Structured logging for all events
    - Configurable log levels
    - Performance metrics logging
    - Error details logging
    """

    def __init__(self, log_level: int = logging.DEBUG) -> None:
        """Initialize hooks with configurable log level.

        Args:
            log_level: Log level for cache events (default: DEBUG)
        """
        self._log_level = log_level

    def on_cache_hit(self, key: str, latency: float) -> None:
        """Log cache hit event.

        Args:
            key: Cache key that was found
            latency: Time taken for cache lookup in seconds
        """
        logger.log(self._log_level, "Cache HIT for key '%s' (latency: %.3fms)", key, latency * 1000)

    def on_cache_miss(self, key: str, latency: float) -> None:
        """Log cache miss event.

        Args:
            key: Cache key that was not found
            latency: Time taken for cache lookup in seconds
        """
        logger.log(self._log_level, "Cache MISS for key '%s' (latency: %.3fms)", key, latency * 1000)

    def on_cache_write(self, key: str, size: int) -> None:
        """Log cache write event.

        Args:
            key: Cache key being written
            size: Size of serialized data in bytes
        """
        logger.log(self._log_level, "Cache WRITE for key '%s' (size: %d bytes)", key, size)

    def on_cache_error(self, key: str, error: Exception) -> None:
        """Log cache error event.

        Args:
            key: Cache key involved in the failed operation
            error: Exception that occurred during cache operation
        """
        logger.error("Cache ERROR for key '%s': %s (%s)", key, str(error), type(error).__name__)


class SilentObservabilityHooks:
    """Silent implementation that performs no operations.

    Useful for production environments where observability overhead
    should be minimized or when using external monitoring systems.
    """

    def on_cache_hit(self, key: str, latency: float) -> None:
        """Silent cache hit handler."""
        pass

    def on_cache_miss(self, key: str, latency: float) -> None:
        """Silent cache miss handler."""
        pass

    def on_cache_write(self, key: str, size: int) -> None:
        """Silent cache write handler."""
        pass

    def on_cache_error(self, key: str, error: Exception) -> None:
        """Silent cache error handler."""
        pass


class CompositeObservabilityHooks:
    """Composite hooks that delegate to multiple hook implementations.

    Allows combining multiple observability systems (e.g., logging + metrics).

    Example:
        hooks = CompositeObservabilityHooks([
            DefaultObservabilityHooks(),
            MetricsCollectorHooks(),
            TracingHooks()
        ])
    """

    def __init__(self, hooks: list[ObservabilityHooks]) -> None:
        """Initialize composite hooks.

        Args:
            hooks: List of hook implementations to delegate to
        """
        self._hooks = hooks

    def on_cache_hit(self, key: str, latency: float) -> None:
        """Delegate cache hit to all hooks."""
        for hook in self._hooks:
            try:
                hook.on_cache_hit(key, latency)
            except Exception as e:
                # Don't let hook errors break cache operations
                logger.warning("Hook error in on_cache_hit for key '%s': %s", key, e)

    def on_cache_miss(self, key: str, latency: float) -> None:
        """Delegate cache miss to all hooks."""
        for hook in self._hooks:
            try:
                hook.on_cache_miss(key, latency)
            except Exception as e:
                logger.warning("Hook error in on_cache_miss for key '%s': %s", key, e)

    def on_cache_write(self, key: str, size: int) -> None:
        """Delegate cache write to all hooks."""
        for hook in self._hooks:
            try:
                hook.on_cache_write(key, size)
            except Exception as e:
                logger.warning("Hook error in on_cache_write for key '%s': %s", key, e)

    def on_cache_error(self, key: str, error: Exception) -> None:
        """Delegate cache error to all hooks."""
        for hook in self._hooks:
            try:
                hook.on_cache_error(key, error)
            except Exception as e:
                logger.warning("Hook error in on_cache_error for key '%s': %s", key, e)

    def add_hook(self, hook: ObservabilityHooks) -> None:
        """Add a new hook to the composite.

        Args:
            hook: Hook implementation to add
        """
        self._hooks.append(hook)

    def remove_hook(self, hook: ObservabilityHooks) -> bool:
        """Remove a hook from the composite.

        Args:
            hook: Hook implementation to remove

        Returns:
            True if hook was found and removed, False otherwise
        """
        try:
            self._hooks.remove(hook)
            return True
        except ValueError:
            return False
