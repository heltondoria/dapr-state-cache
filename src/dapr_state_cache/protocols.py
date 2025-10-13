"""
Protocols for extensibility and type safety.

This module defines the contracts that allow users to extend the library
with custom implementations while maintaining type safety and clear interfaces.

Protocols defined:
- KeyBuilder: For custom cache key generation
- Serializer: For custom data serialization/deserialization
- ObservabilityHooks: For custom observability and monitoring integration
"""

from collections.abc import Callable
from typing import Any, Protocol


class KeyBuilder(Protocol):
    """Protocol for custom cache key builders.

    Allows users to customize how cache keys are generated from function
    signatures and arguments, enabling specialized caching strategies.
    """

    def build_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """Build a cache key from function and its arguments.

        Args:
            func: The decorated function
            args: Positional arguments passed to the function
            kwargs: Keyword arguments passed to the function

        Returns:
            Cache key as string, must be unique for different input combinations

        Raises:
            ValueError: If key cannot be generated (e.g., non-serializable args)
        """
        ...


class Serializer(Protocol):
    """Protocol for custom data serialization.

    Enables pluggable serialization strategies for different data types
    and performance requirements (JSON, MessagePack, Pickle, etc.).
    """

    def serialize(self, data: Any) -> bytes:
        """Serialize Python data to bytes for storage.

        Args:
            data: Python object to serialize

        Returns:
            Serialized data as bytes

        Raises:
            TypeError: If data type is not serializable by this serializer
            ValueError: If data contains invalid values for this format
        """
        ...

    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes back to Python data.

        Args:
            data: Serialized bytes from storage

        Returns:
            Deserialized Python object

        Raises:
            ValueError: If data is corrupted or invalid for this format
            TypeError: If data format is incompatible with this deserializer
        """
        ...


class ObservabilityHooks(Protocol):
    """Protocol for custom observability and monitoring hooks.

    Allows integration with monitoring systems, metrics collection,
    distributed tracing, and custom logging strategies.
    """

    def on_cache_hit(self, key: str, latency: float) -> None:
        """Called when cache lookup results in a hit.

        Args:
            key: Cache key that was found
            latency: Time taken for cache lookup in seconds
        """
        ...

    def on_cache_miss(self, key: str, latency: float) -> None:
        """Called when cache lookup results in a miss.

        Args:
            key: Cache key that was not found
            latency: Time taken for cache lookup in seconds
        """
        ...

    def on_cache_write(self, key: str, size: int) -> None:
        """Called when data is written to cache.

        Args:
            key: Cache key being written
            size: Size of serialized data in bytes
        """
        ...

    def on_cache_error(self, key: str, error: Exception) -> None:
        """Called when cache operation encounters an error.

        Args:
            key: Cache key involved in the failed operation
            error: Exception that occurred during cache operation
        """
        ...
