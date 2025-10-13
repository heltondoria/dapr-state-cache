"""
Method type detection utilities for cache key generation.

Provides detection of instance methods, class methods and static methods
following Clean Code principles with single responsibility.
"""

import inspect
from collections.abc import Callable


class MethodTypeDetector:
    """Detects method types for proper argument filtering.

    Identifies instance methods, class methods, and static methods
    to enable proper cache key generation.

    Stateless and thread-safe utility class.
    """

    def is_instance_method(self, func: Callable) -> bool:
        """Check if function is an instance method.

        Args:
            func: Function to check

        Returns:
            True if function is an instance method
        """
        if self._is_bound_instance_method(func):
            return True

        return self._has_self_parameter(func)

    def is_class_method(self, func: Callable) -> bool:
        """Check if function is a class method.

        Args:
            func: Function to check

        Returns:
            True if function is a class method
        """
        if self._is_bound_class_method(func):
            return True

        if self._is_classmethod_decorator(func):
            return True

        return self._has_cls_parameter(func)

    def _is_bound_instance_method(self, func: Callable) -> bool:
        """Check for bound instance method."""
        if not hasattr(func, "__self__"):
            return False

        self_attr = getattr(func, "__self__", None)
        return self_attr is not None and not inspect.isclass(self_attr)

    def _is_bound_class_method(self, func: Callable) -> bool:
        """Check for bound class method."""
        if not hasattr(func, "__self__"):
            return False

        self_attr = getattr(func, "__self__", None)
        return self_attr is not None and inspect.isclass(self_attr)

    def _is_classmethod_decorator(self, func: Callable) -> bool:
        """Check for classmethod decorator."""
        return isinstance(func, classmethod)

    def _has_self_parameter(self, func: Callable) -> bool:
        """Check for self parameter safely."""
        return self._has_first_parameter(func, "self")

    def _has_cls_parameter(self, func: Callable) -> bool:
        """Check for cls parameter safely."""
        return self._has_first_parameter(func, "cls")

    def _has_first_parameter(self, func: Callable, param_name: str) -> bool:
        """Check if function has specific first parameter."""
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            return len(params) > 0 and params[0] == param_name
        except (ValueError, TypeError):
            return False
