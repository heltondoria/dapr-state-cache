"""
Argument filtering utilities for cache key generation.

Filters method arguments (self/cls) to ensure cache key consistency
across different instances of the same class.
"""

from collections.abc import Callable

from ..codecs.normalizers import filter_args_for_methods
from .method_type_detector import MethodTypeDetector


class ArgumentFilter:
    """Filters method arguments for cache key generation.

    Removes self/cls parameters from method arguments to ensure
    consistent cache keys across different instances.

    Stateless and thread-safe utility class.
    """

    def __init__(self, method_detector: MethodTypeDetector | None = None) -> None:
        """Initialize argument filter.

        Args:
            method_detector: Method type detector instance
        """
        self._method_detector = method_detector or MethodTypeDetector()

    def filter_method_arguments(self, func: Callable, args: tuple) -> tuple:
        """Filter method arguments removing self/cls parameters.

        Args:
            func: Function being cached
            args: Positional arguments

        Returns:
            Filtered arguments tuple without self/cls
        """
        is_method = self._method_detector.is_instance_method(func)
        is_classmethod = self._method_detector.is_class_method(func)

        return filter_args_for_methods(args, is_method, is_classmethod)
