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


def normalize_for_serialization(obj: Any) -> Any:
    """Normalize Python objects to JSON-serializable types.
    
    Recursively processes nested structures (dict, list, tuple) and converts
    special Python types to their JSON-serializable equivalents.
    
    Args:
        obj: Python object to normalize
        
    Returns:
        JSON-serializable equivalent of the object
        
    Raises:
        TypeError: If object contains unsupported types
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    if isinstance(obj, date):
        return obj.isoformat()
    
    if isinstance(obj, time):
        return obj.isoformat()
    
    if isinstance(obj, Decimal):
        return str(obj)
    
    if isinstance(obj, UUID):
        return str(obj)
    
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode('ascii')
    
    if isinstance(obj, (set, frozenset)):
        # Sort for deterministic order
        return sorted([normalize_for_serialization(item) for item in obj])
    
    if isinstance(obj, (list, tuple)):
        return [normalize_for_serialization(item) for item in obj]
    
    if isinstance(obj, dict):
        # Sort keys for deterministic order
        return {
            key: normalize_for_serialization(value)
            for key, value in sorted(obj.items())
        }
    
    # Attempt to use object's __dict__ if it's a custom object
    if hasattr(obj, '__dict__'):
        return normalize_for_serialization(obj.__dict__)
    
    # If we can't normalize, raise TypeError with helpful message
    raise TypeError(
        f"Object of type '{type(obj).__name__}' is not JSON serializable. "
        f"Supported types: str, int, float, bool, None, datetime, date, time, "
        f"Decimal, UUID, bytes, set, frozenset, list, tuple, dict. "
        f"For custom objects, provide a custom serializer."
    )


def serialize_args_for_key(args: tuple, kwargs: dict) -> str:
    """Serialize function arguments for cache key generation.
    
    Creates a deterministic string representation of function arguments
    suitable for hashing. Ensures same arguments always produce same string.
    
    Args:
        args: Positional arguments tuple
        kwargs: Keyword arguments dictionary
        
    Returns:
        JSON string representation of normalized arguments
        
    Raises:
        TypeError: If arguments contain unsupported types
    """
    normalized_data = {
        'args': normalize_for_serialization(args),
        'kwargs': normalize_for_serialization(kwargs)
    }
    
    # Use separators for compact representation and sort_keys for determinism
    return json.dumps(normalized_data, separators=(',', ':'), sort_keys=True)


def get_function_path(func: Any) -> str:
    """Get normalized path for a function.
    
    Creates consistent path regardless of how function is accessed.
    Format: module.class.function or module.function for standalone functions.
    
    Args:
        func: Function object
        
    Returns:
        Dot-separated path string
    """
    module_name = getattr(func, '__module__', None)
    if module_name is None:
        module_name = 'unknown'
    
    # Check if function is a method (has __qualname__ with class info)
    if hasattr(func, '__qualname__') and '.' in func.__qualname__:
        return f"{module_name}.{func.__qualname__}"
    
    # Standalone function
    return f"{module_name}.{func.__name__}"


def filter_args_for_methods(args: tuple, is_method: bool, is_classmethod: bool) -> tuple:
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
