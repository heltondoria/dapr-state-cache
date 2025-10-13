"""
Default key builder implementation.

Implements the KeyBuilder protocol to generate deterministic cache keys
from function signatures and arguments using SHA256 hashing.
"""

from collections.abc import Callable

from ..codecs.normalizers import (
    get_function_path,
    serialize_args_for_key,
)
from .argument_filter import ArgumentFilter
from .hash_utils import calculate_hash_for_args, create_cache_key


class DefaultKeyBuilder:
    """Cache key builder with deterministic SHA256 hashing.

    Generates stable cache keys using function signatures and arguments.
    Methods exclude 'self'/'cls' parameters for instance sharing.

    Key format: {prefix}:{function_path}:{args_hash}
    Thread-safe and stateless.
    """

    def __init__(self, key_prefix: str = "cache", argument_filter: ArgumentFilter | None = None) -> None:
        """Initialize key builder with prefix.

        Args:
            key_prefix: Prefix for all generated keys (default: "cache")
            argument_filter: Filter for method arguments (optional)

        Raises:
            ValueError: If key_prefix is empty
        """
        if not key_prefix:
            raise ValueError("Key prefix cannot be empty")

        self._key_prefix = key_prefix
        self._argument_filter = argument_filter or ArgumentFilter()

    def build_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """Build cache key from function and arguments.

        Args:
            func: Function being cached
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Cache key string in format: prefix:function_path:args_hash

        Raises:
            ValueError: If key generation fails
        """
        try:
            function_path = get_function_path(func)
            filtered_args = self._argument_filter.filter_method_arguments(func, args)
            args_hash = self._calculate_arguments_hash(filtered_args, kwargs)
            return create_cache_key(self._key_prefix, function_path, args_hash)
        except Exception as e:
            raise ValueError(f"Failed to build cache key: {e}") from e

    def _calculate_arguments_hash(self, args: tuple, kwargs: dict) -> str:
        """Calculate hash for function arguments."""
        serialized_args = serialize_args_for_key(args, kwargs)
        return calculate_hash_for_args(serialized_args)

    @property
    def key_prefix(self) -> str:
        """Get the key prefix used by this builder."""
        return self._key_prefix
