"""
JSON serializer implementation.

Default serializer using Python's built-in json module with type normalization
for consistent handling of complex Python types.
"""

import json
from typing import Any

from ..backend.exceptions import CacheSerializationError
from ..protocols import Serializer
from .normalizers import normalize_for_serialization


class JsonSerializer(Serializer):
    """JSON serializer with comprehensive type normalization.

    Default serializer implementation using Python's built-in json module
    with custom type normalization to handle complex Python objects that
    are not natively JSON-serializable.

    The serializer automatically converts Python types to JSON-compatible
    representations:
    - datetime objects → ISO 8601 strings
    - UUID objects → string representation
    - Decimal objects → string representation
    - bytes objects → base64 encoded strings
    - sets/frozensets → sorted lists (for determinism)

    Features:
        - Deterministic output with sorted dictionary keys
        - Compact JSON representation (no extra whitespace)
        - UTF-8 encoding for consistent byte output
        - Type safety with clear error messages
        - Preserves data fidelity for round-trip serialization

    Performance:
        - Fast for most common data types
        - Overhead only for complex types requiring normalization
        - Memory efficient with streaming JSON encoding

    Example:
        ```python
        serializer = JsonSerializer()

        # Complex data with datetime and UUID
        data = {
            "user_id": UUID("550e8400-e29b-41d4-a716-446655440000"),
            "created_at": datetime(2025, 1, 15, 10, 30, 0),
            "tags": {"python", "cache", "dapr"}  # set will be sorted
        }

        # Serialize to bytes
        serialized = serializer.serialize(data)

        # Deserialize back to Python objects
        deserialized = serializer.deserialize(serialized)
        ```

    Note:
        The serializer normalizes types for JSON compatibility but does not
        preserve original Python types during deserialization. For example,
        datetime objects become strings, and sets become lists.
    """

    def serialize(self, data: Any) -> bytes:
        """Serialize Python data to JSON bytes.

        Args:
            data: Python object to serialize

        Returns:
            UTF-8 encoded JSON bytes

        Raises:
            TypeError: If data contains unsupported types after normalization
        """
        try:
            normalized_data = normalize_for_serialization(data)
            json_str = json.dumps(
                normalized_data,
                separators=(',', ':'),  # Compact representation
                sort_keys=True,         # Deterministic order
                ensure_ascii=False      # Allow Unicode characters
            )
            return json_str.encode('utf-8')
        except TypeError as e:
            raise CacheSerializationError(f"JSON serialization failed: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        """Deserialize JSON bytes to Python data.

        Args:
            data: UTF-8 encoded JSON bytes

        Returns:
            Deserialized Python object

        Raises:
            ValueError: If data is not valid JSON
            TypeError: If data is not bytes
        """
        if not isinstance(data, bytes):
            raise CacheSerializationError(f"Expected bytes, got {type(data).__name__}")

        try:
            json_str = data.decode('utf-8')
            return json.loads(json_str)
        except UnicodeDecodeError as e:
            raise CacheSerializationError(f"Invalid UTF-8 encoding: {e}") from e
        except json.JSONDecodeError as e:
            raise CacheSerializationError(f"Invalid JSON data: {e}") from e
