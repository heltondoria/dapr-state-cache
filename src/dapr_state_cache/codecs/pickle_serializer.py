"""
Pickle serializer implementation.

Python native serializer using pickle module for maximum compatibility
with Python objects. Should be used with caution due to security implications.

⚠️ SECURITY WARNING: This serializer uses pickle which can execute arbitrary code!
Only use in trusted environments with data from trusted sources.
"""

import pickle
import warnings
from typing import Any

from ..backend.exceptions import CacheSerializationError
from ..protocols import Serializer


class PickleSerializer(Serializer):
    """Python-native pickle serializer for complex objects.

    Maximum fidelity serializer using Python's built-in pickle module to
    serialize arbitrary Python objects without any type normalization or
    conversion. This preserves exact object types and references, making
    it ideal for caching complex Python data structures.

    Key Advantages:
        - Perfect type preservation (no normalization needed)
        - Handles complex objects (classes, functions, lambdas)
        - Supports object references and circular references
        - Can serialize most Python objects out-of-the-box
        - Efficient for complex nested data structures

    Features:
        - Uses highest available pickle protocol for performance
        - Compact binary format for most Python objects
        - Automatic handling of custom classes and objects
        - Preserves object identity and references
        - No external dependencies required

    Performance Characteristics:
        - Excellent for complex Python objects
        - Faster than JSON for nested data structures
        - Memory efficient for object graphs
        - Minimal CPU overhead for native Python types

    🚨 SECURITY WARNING:
        Pickle can execute arbitrary code during deserialization!

        - NEVER use with untrusted or user-provided data
        - NEVER deserialize pickle data from external sources
        - Only use in trusted environments (same application/service)
        - Consider JsonSerializer or MsgpackSerializer for external data

        Potential attacks:
        - Code injection during deserialization
        - Remote code execution via malicious pickled data
        - File system access or network connections

    Recommended Use Cases:
        ✅ Internal application caching (trusted environment)
        ✅ Complex Python objects (custom classes, data structures)
        ✅ Object graphs with references and circular dependencies
        ✅ Temporary caching within single application instance
        ✅ Development and testing scenarios

    ❌ Avoid For:
        ❌ External APIs or user-provided data
        ❌ Cross-language compatibility requirements
        ❌ Long-term data storage
        ❌ Network-exposed cache stores
        ❌ Multi-tenant applications

    Example:
        ```python
        # For internal caching of complex objects
        serializer = PickleSerializer()

        # Custom class instance
        class UserPreferences:
            def __init__(self, theme, notifications):
                self.theme = theme
                self.notifications = notifications

        # Complex data with custom objects
        data = {
            "preferences": UserPreferences("dark", True),
            "calculations": lambda x: x ** 2,  # Even functions!
            "nested": {"deep": {"structure": [1, 2, 3]}}
        }

        # Perfect fidelity serialization
        serialized = serializer.serialize(data)
        deserialized = serializer.deserialize(serialized)

        # Types preserved exactly
        assert isinstance(deserialized["preferences"], UserPreferences)
        assert callable(deserialized["calculations"])
        ```

    Protocol Version:
        Uses `pickle.HIGHEST_PROTOCOL` by default for optimal performance
        and compatibility with the current Python version.
    """

    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL) -> None:
        """Initialize Pickle serializer.

        Args:
            protocol: Pickle protocol version to use (default: highest available)
        """
        self._protocol = protocol

    def serialize(self, data: Any) -> bytes:
        """Serialize Python data to pickle bytes.

        Args:
            data: Python object to serialize

        Returns:
            Pickle encoded bytes

        Raises:
            TypeError: If data is not picklable
        """
        try:
            return pickle.dumps(data, protocol=self._protocol)
        except (TypeError, ValueError, pickle.PicklingError) as e:
            raise CacheSerializationError(f"Pickle serialization failed: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        """Deserialize pickle bytes to Python data.

        ⚠️ SECURITY WARNING: pickle.loads() can execute arbitrary code!
        This method should only deserialize data from trusted sources within
        the same application/service boundary. Never use with external or
        user-provided data.

        Args:
            data: Pickle encoded bytes from trusted source

        Returns:
            Deserialized Python object

        Raises:
            ValueError: If data is not valid pickle format
            TypeError: If data is not bytes
        """
        if not isinstance(data, bytes):
            raise CacheSerializationError(f"Expected bytes, got {type(data).__name__}")

        # Issue security warning on first use
        warnings.warn(
            "PickleSerializer.deserialize() uses pickle.loads() which can execute "
            "arbitrary code. Only use with trusted data from same application. "
            "Consider JsonSerializer or MsgpackSerializer for better security.",
            UserWarning,
            stacklevel=2,
        )

        try:
            # Note: Using pickle.loads() here is intentional but requires trusted data
            return pickle.loads(data)  # noqa: S301
        except (pickle.PickleError, EOFError, ValueError) as e:
            raise CacheSerializationError(f"Pickle deserialization failed: {e}") from e
        except Exception as e:
            # Catch any other exceptions that might occur during unpickling
            raise CacheSerializationError(f"Unexpected error during pickle deserialization: {e}") from e
