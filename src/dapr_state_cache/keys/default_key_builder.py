"""
Default key builder implementation.

Implements the KeyBuilder protocol to generate deterministic cache keys
from function signatures and arguments using SHA256 hashing.
"""

import inspect
from collections.abc import Callable

from ..codecs.normalizers import (
    filter_args_for_methods,
    get_function_path,
    serialize_args_for_key,
)
from .hash_utils import calculate_hash_for_args, create_cache_key


class DefaultKeyBuilder:
    """Cache key builder with deterministic SHA256 hashing.

    Generates stable cache keys using function signatures and arguments.
    Methods exclude 'self'/'cls' parameters for instance sharing.

    Key format: {prefix}:{function_path}:{args_hash}
    Thread-safe and stateless.
    """

    def __init__(self, key_prefix: str = "cache") -> None:
        """Initialize key builder with prefix.

        Args:
            key_prefix: Prefix for all generated keys (default: "cache")

        Raises:
            ValueError: If key_prefix is empty
        """
        if not key_prefix:
            raise ValueError("Key prefix cannot be empty")

        self._key_prefix = key_prefix

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
            filtered_args = self._filter_method_arguments(func, args)
            args_hash = self._calculate_arguments_hash(filtered_args, kwargs)
            return create_cache_key(self._key_prefix, function_path, args_hash)
        except Exception as e:
            raise ValueError(f"Failed to build cache key: {e}") from e

    def _filter_method_arguments(self, func: Callable, args: tuple) -> tuple:
        """Extract method argument filtering logic."""
        is_method = self._is_instance_method(func)
        is_classmethod = self._is_class_method(func)
        return filter_args_for_methods(args, is_method, is_classmethod)

    def _calculate_arguments_hash(self, args: tuple, kwargs: dict) -> str:
        """Extract hash calculation logic."""
        serialized_args = serialize_args_for_key(args, kwargs)
        return calculate_hash_for_args(serialized_args)

    def _is_instance_method(self, func: Callable) -> bool:
        """Check if function is an instance method with type safety.

        Args:
            func: Function to check

        Returns:
            True if function is an instance method
        """
        # Type guard seguro para bound methods
        if hasattr(func, "__self__"):
            self_attr = getattr(func, "__self__", None)
            if self_attr is not None and not inspect.isclass(self_attr):
                return True

        # Verificação de parâmetros sem acesso direto a __self__
        return self._has_self_parameter(func)

    def _is_class_method(self, func: Callable) -> bool:
        """Check if function is a class method with reduced complexity.

        Args:
            func: Function to check

        Returns:
            True if function is a class method
        """
        # Early return para bound methods
        if hasattr(func, "__self__"):
            self_attr = getattr(func, "__self__", None)
            if self_attr is not None and inspect.isclass(self_attr):
                return True

        # Early return para classmethod decorator
        if isinstance(func, classmethod):
            return True

        # Extrair verificação de parâmetros
        return self._has_cls_parameter(func)

    def _has_self_parameter(self, func: Callable) -> bool:
        """Check for self parameter safely."""
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            return len(params) > 0 and params[0] == "self"
        except (ValueError, TypeError):
            return False

    def _has_cls_parameter(self, func: Callable) -> bool:
        """Extract parameter check - método auxiliar."""
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            return len(params) > 0 and params[0] == "cls"
        except (ValueError, TypeError):
            return False

    @property
    def key_prefix(self) -> str:
        """Get the key prefix used by this builder."""
        return self._key_prefix
