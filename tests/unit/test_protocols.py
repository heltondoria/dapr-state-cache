"""
Unit tests for protocols module.

Tests Protocol definitions and mock implementations to ensure
proper type checking and interface compliance.
"""

from typing import Any
from unittest.mock import Mock

from dapr_state_cache.protocols import KeyBuilder, ObservabilityHooks, Serializer


class TestKeyBuilderProtocol:
    """Test KeyBuilder Protocol compliance and behavior."""

    def test_key_builder_protocol_structure(self) -> None:
        """Test that KeyBuilder protocol has correct method signature."""
        # Arrange
        mock_key_builder = Mock(spec=KeyBuilder)

        # Act & Assert
        # Protocol should have build_key method
        assert hasattr(mock_key_builder, "build_key")

        # Method should be callable
        assert callable(mock_key_builder.build_key)

    def test_key_builder_mock_implementation(self) -> None:
        """Test mock implementation of KeyBuilder protocol."""

        # Arrange
        def sample_func() -> str:
            return "test"

        args = (1, 2)
        kwargs = {"key": "value"}
        expected_key = "test:key:hash"

        mock_key_builder = Mock(spec=KeyBuilder)
        mock_key_builder.build_key.return_value = expected_key

        # Act
        result = mock_key_builder.build_key(sample_func, args, kwargs)

        # Assert
        assert result == expected_key
        mock_key_builder.build_key.assert_called_once_with(sample_func, args, kwargs)

    def test_key_builder_protocol_type_hints(self) -> None:
        """Test that KeyBuilder protocol method has correct type hints."""
        # Arrange
        import inspect

        from dapr_state_cache.protocols import KeyBuilder

        # Act
        signature = inspect.signature(KeyBuilder.build_key)

        # Assert
        assert "func" in signature.parameters
        assert "args" in signature.parameters
        assert "kwargs" in signature.parameters
        assert signature.return_annotation is str


class TestSerializerProtocol:
    """Test Serializer Protocol compliance and behavior."""

    def test_serializer_protocol_structure(self) -> None:
        """Test that Serializer protocol has correct method signatures."""
        # Arrange
        mock_serializer = Mock(spec=Serializer)

        # Act & Assert
        # Protocol should have serialize method
        assert hasattr(mock_serializer, "serialize")
        assert callable(mock_serializer.serialize)

        # Protocol should have deserialize method
        assert hasattr(mock_serializer, "deserialize")
        assert callable(mock_serializer.deserialize)

    def test_serializer_mock_serialize(self) -> None:
        """Test mock implementation of serialize method."""
        # Arrange
        data = {"key": "value", "number": 42}
        expected_bytes = b'{"key":"value","number":42}'

        mock_serializer = Mock(spec=Serializer)
        mock_serializer.serialize.return_value = expected_bytes

        # Act
        result = mock_serializer.serialize(data)

        # Assert
        assert result == expected_bytes
        assert isinstance(result, bytes)
        mock_serializer.serialize.assert_called_once_with(data)

    def test_serializer_mock_deserialize(self) -> None:
        """Test mock implementation of deserialize method."""
        # Arrange
        data_bytes = b'{"key":"value","number":42}'
        expected_data = {"key": "value", "number": 42}

        mock_serializer = Mock(spec=Serializer)
        mock_serializer.deserialize.return_value = expected_data

        # Act
        result = mock_serializer.deserialize(data_bytes)

        # Assert
        assert result == expected_data
        mock_serializer.deserialize.assert_called_once_with(data_bytes)

    def test_serializer_protocol_type_hints(self) -> None:
        """Test that Serializer protocol methods have correct type hints."""
        # Arrange
        import inspect

        from dapr_state_cache.protocols import Serializer

        # Act
        serialize_sig = inspect.signature(Serializer.serialize)
        deserialize_sig = inspect.signature(Serializer.deserialize)

        # Assert
        assert serialize_sig.return_annotation is bytes
        assert deserialize_sig.return_annotation is Any
        assert "data" in serialize_sig.parameters
        assert "data" in deserialize_sig.parameters


class TestObservabilityHooksProtocol:
    """Test ObservabilityHooks Protocol compliance and behavior."""

    def test_observability_hooks_protocol_structure(self) -> None:
        """Test that ObservabilityHooks protocol has all required methods."""
        # Arrange
        mock_hooks = Mock(spec=ObservabilityHooks)

        # Act & Assert
        # Protocol should have all hook methods
        assert hasattr(mock_hooks, "on_cache_hit")
        assert callable(mock_hooks.on_cache_hit)

        assert hasattr(mock_hooks, "on_cache_miss")
        assert callable(mock_hooks.on_cache_miss)

        assert hasattr(mock_hooks, "on_cache_write")
        assert callable(mock_hooks.on_cache_write)

        assert hasattr(mock_hooks, "on_cache_error")
        assert callable(mock_hooks.on_cache_error)

    def test_on_cache_hit_mock(self) -> None:
        """Test mock implementation of on_cache_hit hook."""
        # Arrange
        key = "test:key:123"
        latency = 0.025

        mock_hooks = Mock(spec=ObservabilityHooks)

        # Act
        mock_hooks.on_cache_hit(key, latency)

        # Assert
        mock_hooks.on_cache_hit.assert_called_once_with(key, latency)

    def test_on_cache_miss_mock(self) -> None:
        """Test mock implementation of on_cache_miss hook."""
        # Arrange
        key = "test:key:456"
        latency = 0.150

        mock_hooks = Mock(spec=ObservabilityHooks)

        # Act
        mock_hooks.on_cache_miss(key, latency)

        # Assert
        mock_hooks.on_cache_miss.assert_called_once_with(key, latency)

    def test_on_cache_write_mock(self) -> None:
        """Test mock implementation of on_cache_write hook."""
        # Arrange
        key = "test:key:789"
        size = 1024

        mock_hooks = Mock(spec=ObservabilityHooks)

        # Act
        mock_hooks.on_cache_write(key, size)

        # Assert
        mock_hooks.on_cache_write.assert_called_once_with(key, size)

    def test_on_cache_error_mock(self) -> None:
        """Test mock implementation of on_cache_error hook."""
        # Arrange
        key = "test:key:error"
        error = ValueError("Test error")

        mock_hooks = Mock(spec=ObservabilityHooks)

        # Act
        mock_hooks.on_cache_error(key, error)

        # Assert
        mock_hooks.on_cache_error.assert_called_once_with(key, error)

    def test_observability_hooks_protocol_type_hints(self) -> None:
        """Test that ObservabilityHooks protocol methods have correct type hints."""
        # Arrange
        import inspect

        from dapr_state_cache.protocols import ObservabilityHooks

        # Act
        hit_sig = inspect.signature(ObservabilityHooks.on_cache_hit)
        miss_sig = inspect.signature(ObservabilityHooks.on_cache_miss)
        write_sig = inspect.signature(ObservabilityHooks.on_cache_write)
        error_sig = inspect.signature(ObservabilityHooks.on_cache_error)

        # Assert
        # All methods should return None
        assert hit_sig.return_annotation is None
        assert miss_sig.return_annotation is None
        assert write_sig.return_annotation is None
        assert error_sig.return_annotation is None

        # Check parameter names exist
        assert "key" in hit_sig.parameters
        assert "latency" in hit_sig.parameters
        assert "key" in miss_sig.parameters
        assert "latency" in miss_sig.parameters
        assert "key" in write_sig.parameters
        assert "size" in write_sig.parameters
        assert "key" in error_sig.parameters
        assert "error" in error_sig.parameters


class TestProtocolIntegration:
    """Integration tests for protocol usage patterns."""

    def test_all_protocols_can_be_mocked(self) -> None:
        """Test that all protocols can be properly mocked for testing."""
        # Arrange
        mock_key_builder = Mock(spec=KeyBuilder)
        mock_serializer = Mock(spec=Serializer)
        mock_hooks = Mock(spec=ObservabilityHooks)

        # Act & Assert
        # All mocks should be created successfully
        assert mock_key_builder is not None
        assert mock_serializer is not None
        assert mock_hooks is not None

        # All should have expected methods
        assert hasattr(mock_key_builder, "build_key")
        assert hasattr(mock_serializer, "serialize")
        assert hasattr(mock_serializer, "deserialize")
        assert hasattr(mock_hooks, "on_cache_hit")
        assert hasattr(mock_hooks, "on_cache_miss")
        assert hasattr(mock_hooks, "on_cache_write")
        assert hasattr(mock_hooks, "on_cache_error")

    def test_protocols_import_correctly(self) -> None:
        """Test that all protocols can be imported from module."""
        # Arrange & Act
        from dapr_state_cache.protocols import KeyBuilder, ObservabilityHooks, Serializer

        # Assert
        # All protocols should be imported successfully
        assert KeyBuilder is not None
        assert Serializer is not None
        assert ObservabilityHooks is not None

        # Should be protocol types
        assert hasattr(KeyBuilder, "__protocol__") or hasattr(KeyBuilder, "__annotations__")
        assert hasattr(Serializer, "__protocol__") or hasattr(Serializer, "__annotations__")
        assert hasattr(ObservabilityHooks, "__protocol__") or hasattr(ObservabilityHooks, "__annotations__")
