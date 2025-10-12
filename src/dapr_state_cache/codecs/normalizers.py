"""
Type normalization for consistent serialization.

Converts Python types to JSON-serializable forms with deterministic behavior
to ensure stable cache keys and proper serialization across all serializers.

Supported type conversions (as per specification section 8.1):
- datetime -> ISO 8601 string
- date -> ISO 8601 string
- time -> ISO 8601 string
- Decimal -> string
- UUID -> string
- bytes -> base64 string
- set -> sorted list
- frozenset -> sorted list
"""

import base64
import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..backend.exceptions import CacheSerializationError


def _normalize_primitive_types(obj: Any) -> Any | None:
    """Normalize primitive Python types.

    Args:
        obj: Python object to check and normalize

    Returns:
        Normalized primitive type or None if not primitive
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    return None


def _normalize_datetime_types(obj: Any) -> str | None:
    """Normalize datetime-related types to ISO strings.

    Args:
        obj: Python object to check and normalize

    Returns:
        ISO format string or None if not datetime type
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, time):
        return obj.isoformat()
    return None


def _normalize_numeric_types(obj: Any) -> str | None:
    """Normalize numeric and UUID types to strings.

    Args:
        obj: Python object to check and normalize

    Returns:
        String representation or None if not numeric/UUID type
    """
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    return None


def _normalize_binary_types(obj: Any) -> str | None:
    """Normalize binary data to base64 string.

    Args:
        obj: Python object to check and normalize

    Returns:
        Base64 encoded string or None if not binary type
    """
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    return None


def _normalize_collection_types(obj: Any) -> Any | None:
    """Normalize collection types recursively.

    Args:
        obj: Python object to check and normalize

    Returns:
        Normalized collection or None if not collection type
    """
    if isinstance(obj, (set, frozenset)):
        # Sort for deterministic order
        return sorted([normalize_for_serialization(item) for item in obj])

    if isinstance(obj, (list, tuple)):
        return [normalize_for_serialization(item) for item in obj]

    if isinstance(obj, dict):
        # Sort keys for deterministic order
        return {key: normalize_for_serialization(value) for key, value in sorted(obj.items())}

    return None


def _normalize_custom_object(obj: Any) -> Any | None:
    """Normalize custom objects using __dict__ attribute.

    Args:
        obj: Python object to check and normalize

    Returns:
        Normalized __dict__ or None if no __dict__ available
    """
    if hasattr(obj, "__dict__"):
        return normalize_for_serialization(obj.__dict__)
    return None


def _raise_unsupported_type_error(obj: Any) -> None:
    """Raise descriptive error for unsupported types.

    Args:
        obj: The unsupported object

    Raises:
        TypeError: With comprehensive error message
    """
    raise CacheSerializationError(
        f"Object of type '{type(obj).__name__}' is not JSON serializable. "
        f"Supported types: str, int, float, bool, None, datetime, date, time, "
        f"Decimal, UUID, bytes, set, frozenset, list, tuple, dict. "
        f"For custom objects, provide a custom serializer."
    )


def normalize_for_serialization(obj: Any) -> Any:
    """Normalize Python objects to JSON-serializable types.

    Recursively processes nested structures (dict, list, tuple) and converts
    special Python types to their JSON-serializable equivalents.

    Args:
        obj: Python object to normalize

    Returns:
        JSON-serializable equivalent of the object

    Raises:
        CacheSerializationError: If object contains unsupported types
    """
    # Try each normalization strategy in order
    result = _normalize_primitive_types(obj)
    if result is not None or obj is None:
        return result

    result = _normalize_datetime_types(obj)
    if result is not None:
        return result

    result = _normalize_numeric_types(obj)
    if result is not None:
        return result

    result = _normalize_binary_types(obj)
    if result is not None:
        return result

    result = _normalize_collection_types(obj)
    if result is not None:
        return result

    result = _normalize_custom_object(obj)
    if result is not None:
        return result

    # If no normalization worked, raise error
    _raise_unsupported_type_error(obj)


def serialize_args_for_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Serialize function arguments for cache key generation.

    Creates a deterministic string representation of function arguments
    suitable for hashing. Ensures same arguments always produce same string.

    Args:
        args: Positional arguments tuple
        kwargs: Keyword arguments dictionary

    Returns:
        JSON string representation of normalized arguments

    Raises:
        CacheSerializationError: If arguments contain unsupported types
    """
    normalized_data = {"args": normalize_for_serialization(args), "kwargs": normalize_for_serialization(kwargs)}

    # Use separators for compact representation and sort_keys for determinism
    return json.dumps(normalized_data, separators=(",", ":"), sort_keys=True)


def get_function_path(func: Any) -> str:
    """Get normalized path for a function.

    Creates consistent path regardless of how function is accessed.
    Format: module.class.function or module.function for standalone functions.

    Args:
        func: Function object

    Returns:
        Dot-separated path string
    """
    module_name = getattr(func, "__module__", None)
    if module_name is None:
        module_name = "unknown"

    # Check if function is a method (has __qualname__ with class info)
    if hasattr(func, "__qualname__") and "." in func.__qualname__:
        return f"{module_name}.{func.__qualname__}"

    # Standalone function
    return f"{module_name}.{func.__name__}"


def filter_args_for_methods(args: tuple[Any, ...], is_method: bool, is_classmethod: bool) -> tuple[Any, ...]:
    """Filter out self/cls from method arguments for cache key generation.

    Removes the implicit first argument (self or cls) from methods to ensure
    cache keys are shared across instances as specified in section 11.3.1.

    Args:
        args: Original arguments tuple
        is_method: True if this is an instance method
        is_classmethod: True if this is a class method

    Returns:
        Filtered arguments tuple without self/cls
    """
    if (is_method or is_classmethod) and args:
        # Remove first argument (self or cls)
        return args[1:]

    return args
