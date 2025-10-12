"""
Serialization and deserialization utilities.

This module provides various serializers for cache data storage:
- JsonSerializer: Default JSON serializer with type normalization
- MsgpackSerializer: Binary MessagePack serializer (requires msgpack)
- PickleSerializer: Python native serializer (security considerations)

Also includes normalization utilities for consistent type handling.
"""

from .json_serializer import JsonSerializer
from .msgpack_serializer import MsgpackSerializer
from .pickle_serializer import PickleSerializer
from .normalizers import (
    normalize_for_serialization,
    serialize_args_for_key,
    get_function_path,
    filter_args_for_methods,
)

__all__ = [
    # Serializers
    "JsonSerializer",
    "MsgpackSerializer", 
    "PickleSerializer",
    
    # Normalization utilities
    "normalize_for_serialization",
    "serialize_args_for_key",
    "get_function_path",
    "filter_args_for_methods",
]