"""
MessagePack serializer implementation.

Binary serializer using msgpack for compact data representation.
Requires msgpack dependency to be installed.
"""

from typing import Any

from ..backend.exceptions import CacheSerializationError
from ..protocols import Serializer
from .normalizers import normalize_for_serialization


class MsgpackSerializer(Serializer):
    """High-performance MessagePack serializer with type normalization.

    Efficient binary serializer using the MessagePack format, which provides
    faster serialization and smaller payload sizes compared to JSON while
    maintaining cross-language compatibility.

    MessagePack is particularly well-suited for caching scenarios where:
    - Performance is critical (CPU and memory efficiency)
    - Network bandwidth is limited (smaller payloads)
    - Data contains many numeric values or binary data

    Features:
        - Compact binary format (typically 20-50% smaller than JSON)
        - Fast serialization/deserialization (2-5x faster than JSON)
        - Type normalization for complex Python objects
        - Deterministic output with sorted dictionary keys
        - Cross-language compatibility
        - Native support for bytes without base64 encoding

    Performance Characteristics:
        - Excellent for numeric data and mixed data types
        - Minimal memory overhead during serialization
        - Efficient handling of binary data (bytes, bytearrays)
        - Faster than JSON for most data structures

    Dependencies:
        Requires the msgpack package to be installed:
        ```bash
        pip install msgpack
        ```

    Example:
        ```python
        # Install dependency first: pip install msgpack
        serializer = MsgpackSerializer()

        # Efficient for numeric and mixed data
        data = {
            "metrics": [1.5, 2.7, 3.1, 4.9],  # Fast numeric serialization
            "binary_data": b"raw bytes here",   # No base64 overhead
            "metadata": {"version": 1, "type": "cache"}
        }

        # Serialize to compact binary format
        serialized = serializer.serialize(data)
        print(f"Size: {len(serialized)} bytes")  # Typically smaller than JSON

        # Fast deserialization
        deserialized = serializer.deserialize(serialized)
        ```

    Use Cases:
        - High-throughput caching scenarios
        - Large numeric datasets
        - Binary data caching (images, files)
        - Microservices with bandwidth constraints
        - Mobile applications requiring efficient serialization

    Note:
        Like JsonSerializer, this normalizes Python types for compatibility
        but doesn't preserve original types during deserialization.
    """

    def __init__(self, msgpack_module: Any = None) -> None:
        """Initialize MessagePack serializer.

        Args:
            msgpack_module: Optional msgpack module to use. If None, will import automatically.
                           This parameter enables dependency injection for testing.

        Raises:
            ImportError: If msgpack package is not installed and no module provided
        """
        if msgpack_module is not None:
            self._msgpack = msgpack_module
        else:
            try:
                import msgpack  # type: ignore[import-untyped]
                self._msgpack = msgpack
            except ImportError as e:
                raise ImportError(
                    "MsgpackSerializer requires msgpack package. "
                    "Install with: pip install msgpack"
                ) from e

    def serialize(self, data: Any) -> bytes:
        """Serialize Python data to MessagePack bytes.

        Args:
            data: Python object to serialize

        Returns:
            MessagePack encoded bytes

        Raises:
            TypeError: If data contains unsupported types after normalization
        """
        try:
            normalized_data = normalize_for_serialization(data)
            packed_data: bytes = self._msgpack.packb(normalized_data, use_bin_type=True)
            return packed_data
        except (TypeError, ValueError) as e:
            raise CacheSerializationError(f"MessagePack serialization failed: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        """Deserialize MessagePack bytes to Python data.

        Args:
            data: MessagePack encoded bytes

        Returns:
            Deserialized Python object

        Raises:
            ValueError: If data is not valid MessagePack
            TypeError: If data is not bytes
        """
        if not isinstance(data, bytes):
            raise CacheSerializationError(f"Expected bytes, got {type(data).__name__}")

        try:
            return self._msgpack.unpackb(data, raw=False, strict_map_key=False)
        except (ValueError, self._msgpack.exceptions.ExtraData) as e:
            raise CacheSerializationError(f"Invalid MessagePack data: {e}") from e
        except Exception as e:
            raise CacheSerializationError(f"MessagePack deserialization failed: {e}") from e
