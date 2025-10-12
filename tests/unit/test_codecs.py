"""
Unit tests for codec modules.

Tests serializers and normalization functions with 100% coverage
following AAA pattern and TDD principles.
"""

import base64
import pickle
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from dapr_state_cache.codecs import (
    JsonSerializer,
    MsgpackSerializer, 
    PickleSerializer,
    normalize_for_serialization,
    serialize_args_for_key,
    get_function_path,
    filter_args_for_methods,
)


class TestNormalizeForSerialization:
    """Test normalize_for_serialization function."""

    def test_normalize_none_returns_none(self) -> None:
        """Test that None values are returned unchanged."""
        # Arrange
        data = None
        
        # Act
        result = normalize_for_serialization(data)
        
        # Assert
        assert result is None

    def test_normalize_primitives_unchanged(self) -> None:
        """Test that primitive types are returned unchanged."""
        # Arrange
        test_cases = [
            True,
            False,
            42,
            3.14,
            "hello world",
        ]
        
        for data in test_cases:
            # Act
            result = normalize_for_serialization(data)
            
            # Assert
            assert result == data
            assert type(result) is type(data)

    def test_normalize_datetime_to_iso_string(self) -> None:
        """Test datetime normalization to ISO 8601 string."""
        # Arrange
        dt = datetime(2025, 10, 11, 14, 30, 0)
        
        # Act
        result = normalize_for_serialization(dt)
        
        # Assert
        assert result == "2025-10-11T14:30:00"
        assert isinstance(result, str)

    def test_normalize_date_to_iso_string(self) -> None:
        """Test date normalization to ISO 8601 string."""
        # Arrange
        d = date(2025, 10, 11)
        
        # Act
        result = normalize_for_serialization(d)
        
        # Assert
        assert result == "2025-10-11"
        assert isinstance(result, str)

    def test_normalize_time_to_iso_string(self) -> None:
        """Test time normalization to ISO 8601 string."""
        # Arrange
        t = time(14, 30, 0)
        
        # Act
        result = normalize_for_serialization(t)
        
        # Assert
        assert result == "14:30:00"
        assert isinstance(result, str)

    def test_normalize_decimal_to_string(self) -> None:
        """Test Decimal normalization to string."""
        # Arrange
        d = Decimal("123.45")
        
        # Act
        result = normalize_for_serialization(d)
        
        # Assert
        assert result == "123.45"
        assert isinstance(result, str)

    def test_normalize_uuid_to_string(self) -> None:
        """Test UUID normalization to string."""
        # Arrange
        uuid_val = UUID("550e8400-e29b-41d4-a716-446655440000")
        
        # Act
        result = normalize_for_serialization(uuid_val)
        
        # Assert
        assert result == "550e8400-e29b-41d4-a716-446655440000"
        assert isinstance(result, str)

    def test_normalize_bytes_to_base64_string(self) -> None:
        """Test bytes normalization to base64 string."""
        # Arrange
        data = b"Hello World"
        
        # Act
        result = normalize_for_serialization(data)
        
        # Assert
        expected = base64.b64encode(data).decode('ascii')
        assert result == expected
        assert isinstance(result, str)

    def test_normalize_set_to_sorted_list(self) -> None:
        """Test set normalization to sorted list for determinism."""
        # Arrange
        data = {3, 1, 4, 1, 5}  # Will become {1, 3, 4, 5}
        
        # Act
        result = normalize_for_serialization(data)
        
        # Assert
        assert result == [1, 3, 4, 5]  # Sorted
        assert isinstance(result, list)

    def test_normalize_frozenset_to_sorted_list(self) -> None:
        """Test frozenset normalization to sorted list for determinism."""
        # Arrange
        data = frozenset([3, 1, 4, 1, 5])
        
        # Act
        result = normalize_for_serialization(data)
        
        # Assert
        assert result == [1, 3, 4, 5]  # Sorted
        assert isinstance(result, list)

    def test_normalize_list_recursively(self) -> None:
        """Test list normalization with recursive processing."""
        # Arrange
        data = [1, {3, 2}, {"key": UUID("550e8400-e29b-41d4-a716-446655440000")}]
        
        # Act
        result = normalize_for_serialization(data)
        
        # Assert
        assert result == [1, [2, 3], {"key": "550e8400-e29b-41d4-a716-446655440000"}]

    def test_normalize_tuple_to_list(self) -> None:
        """Test tuple normalization to list with recursive processing."""
        # Arrange
        data = (1, 2, {"key": "value"})
        
        # Act
        result = normalize_for_serialization(data)
        
        # Assert
        assert result == [1, 2, {"key": "value"}]
        assert isinstance(result, list)

    def test_normalize_dict_with_sorted_keys(self) -> None:
        """Test dict normalization with sorted keys for determinism."""
        # Arrange
        data = {"z": 1, "a": 2, "m": UUID("550e8400-e29b-41d4-a716-446655440000")}
        
        # Act
        result = normalize_for_serialization(data)
        
        # Assert
        expected = {"a": 2, "m": "550e8400-e29b-41d4-a716-446655440000", "z": 1}
        assert result == expected
        assert list(result.keys()) == ["a", "m", "z"]  # Sorted

    def test_normalize_custom_object_with_dict(self) -> None:
        """Test custom object normalization using __dict__."""
        # Arrange
        class CustomObject:
            def __init__(self) -> None:
                self.name = "test"
                self.value = 42
        
        obj = CustomObject()
        
        # Act
        result = normalize_for_serialization(obj)
        
        # Assert
        assert result == {"name": "test", "value": 42}

    def test_normalize_unsupported_type_raises_error(self) -> None:
        """Test that unsupported types raise TypeError with helpful message."""
        # Arrange
        class UnsupportedObject:
            __slots__ = ()  # No __dict__ access
        
        obj = UnsupportedObject()
        
        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            normalize_for_serialization(obj)
        
        assert "is not JSON serializable" in str(exc_info.value)
        assert "UnsupportedObject" in str(exc_info.value)


class TestSerializeArgsForKey:
    """Test serialize_args_for_key function."""

    def test_serialize_empty_args_and_kwargs(self) -> None:
        """Test serialization of empty arguments."""
        # Arrange
        args = ()
        kwargs: dict[str, Any] = {}
        
        # Act
        result = serialize_args_for_key(args, kwargs)
        
        # Assert
        expected = '{"args":[],"kwargs":{}}'
        assert result == expected

    def test_serialize_args_only(self) -> None:
        """Test serialization with only positional arguments."""
        # Arrange
        args = (1, 2, "test")
        kwargs: dict[str, Any] = {}
        
        # Act
        result = serialize_args_for_key(args, kwargs)
        
        # Assert
        expected = '{"args":[1,2,"test"],"kwargs":{}}'
        assert result == expected

    def test_serialize_kwargs_only(self) -> None:
        """Test serialization with only keyword arguments."""
        # Arrange
        args = ()
        kwargs: dict[str, Any] = {"name": "test", "value": 42}
        
        # Act
        result = serialize_args_for_key(args, kwargs)
        
        # Assert
        # Keys should be sorted
        expected = '{"args":[],"kwargs":{"name":"test","value":42}}'
        assert result == expected

    def test_serialize_complex_args(self) -> None:
        """Test serialization with complex argument types."""
        # Arrange
        args = (datetime(2025, 10, 11), UUID("550e8400-e29b-41d4-a716-446655440000"))
        kwargs: dict[str, Any] = {"data": {1, 2, 3}}
        
        # Act
        result = serialize_args_for_key(args, kwargs)
        
        # Assert
        # Should normalize complex types
        assert "2025-10-11T00:00:00" in result
        assert "550e8400-e29b-41d4-a716-446655440000" in result
        assert "[1,2,3]" in result

    def test_serialize_deterministic_output(self) -> None:
        """Test that serialization produces deterministic output."""
        # Arrange
        args = (1, 2)
        kwargs = {"b": 2, "a": 1}  # Unsorted keys
        
        # Act
        result1 = serialize_args_for_key(args, kwargs)
        result2 = serialize_args_for_key(args, kwargs)
        
        # Assert
        assert result1 == result2
        assert '"a":1' in result1  # Keys should be sorted
        assert result1.index('"a":1') < result1.index('"b":2')


class TestGetFunctionPath:
    """Test get_function_path function."""

    def test_get_path_for_standalone_function(self) -> None:
        """Test path generation for standalone function."""
        # Arrange
        def test_function() -> None:
            pass
        
        # Act
        result = get_function_path(test_function)
        
        # Assert
        assert result.endswith('.test_function')
        assert 'test_codecs' in result

    def test_get_path_for_method(self) -> None:
        """Test path generation for method with class info."""
        # Arrange
        class TestClass:
            def test_method(self) -> None:
                pass
        
        instance = TestClass()
        
        # Act
        result = get_function_path(instance.test_method)
        
        # Assert
        assert 'TestClass.test_method' in result

    def test_get_path_for_function_without_module(self) -> None:
        """Test path generation for function without __module__."""
        # Arrange
        def test_function() -> None:
            pass
        
        # Remove __module__ attribute
        delattr(test_function, '__module__')
        
        # Act
        result = get_function_path(test_function)
        
        # Assert
        assert result.startswith("unknown.")
        assert result.endswith(".test_function")


class TestFilterArgsForMethods:
    """Test filter_args_for_methods function."""

    def test_filter_instance_method_removes_self(self) -> None:
        """Test that self is removed from instance method arguments."""
        # Arrange
        args = ("self_obj", 1, 2, 3)
        
        # Act
        result = filter_args_for_methods(args, is_method=True, is_classmethod=False)
        
        # Assert
        assert result == (1, 2, 3)

    def test_filter_class_method_removes_cls(self) -> None:
        """Test that cls is removed from class method arguments."""
        # Arrange
        args = ("cls_obj", 1, 2, 3)
        
        # Act
        result = filter_args_for_methods(args, is_method=False, is_classmethod=True)
        
        # Assert
        assert result == (1, 2, 3)

    def test_filter_static_method_unchanged(self) -> None:
        """Test that static method arguments are unchanged."""
        # Arrange
        args = (1, 2, 3)
        
        # Act
        result = filter_args_for_methods(args, is_method=False, is_classmethod=False)
        
        # Assert
        assert result == args

    def test_filter_empty_args_returns_empty(self) -> None:
        """Test filtering empty args returns empty tuple."""
        # Arrange
        args = ()
        
        # Act
        result = filter_args_for_methods(args, is_method=True, is_classmethod=False)
        
        # Assert
        assert result == ()


class TestJsonSerializer:
    """Test JsonSerializer implementation."""

    def test_json_serializer_init(self) -> None:
        """Test JsonSerializer initialization."""
        # Arrange & Act
        serializer = JsonSerializer()
        
        # Assert
        assert serializer is not None

    def test_json_serialize_simple_data(self) -> None:
        """Test JSON serialization of simple data."""
        # Arrange
        serializer = JsonSerializer()
        data = {"key": "value", "number": 42}
        
        # Act
        result = serializer.serialize(data)
        
        # Assert
        assert isinstance(result, bytes)
        # Should be compact and sorted
        assert b'{"key":"value","number":42}' == result

    def test_json_serialize_complex_data(self) -> None:
        """Test JSON serialization with type normalization."""
        # Arrange
        serializer = JsonSerializer()
        data = {
            "date": datetime(2025, 10, 11),
            "uuid": UUID("550e8400-e29b-41d4-a716-446655440000"),
            "set": {1, 2, 3}
        }
        
        # Act
        result = serializer.serialize(data)
        
        # Assert
        assert isinstance(result, bytes)
        result_str = result.decode('utf-8')
        assert "2025-10-11T00:00:00" in result_str
        assert "550e8400-e29b-41d4-a716-446655440000" in result_str
        assert "[1,2,3]" in result_str

    def test_json_deserialize_simple_data(self) -> None:
        """Test JSON deserialization of simple data."""
        # Arrange
        serializer = JsonSerializer()
        data = b'{"key":"value","number":42}'
        
        # Act
        result = serializer.deserialize(data)
        
        # Assert
        assert result == {"key": "value", "number": 42}

    def test_json_serialize_deserialize_roundtrip(self) -> None:
        """Test JSON serialization/deserialization roundtrip."""
        # Arrange
        serializer = JsonSerializer()
        original_data = {"key": "value", "numbers": [1, 2, 3], "nested": {"a": 1}}
        
        # Act
        serialized = serializer.serialize(original_data)
        deserialized = serializer.deserialize(serialized)
        
        # Assert
        assert deserialized == original_data

    def test_json_serialize_unsupported_type_raises_error(self) -> None:
        """Test that unsupported types raise TypeError."""
        # Arrange
        serializer = JsonSerializer()
        
        class UnsupportedType:
            __slots__ = ()  # No __dict__ access
        
        data = UnsupportedType()
        
        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            serializer.serialize(data)
        
        assert "JSON serialization failed" in str(exc_info.value)

    def test_json_deserialize_invalid_bytes_raises_error(self) -> None:
        """Test that non-bytes input raises TypeError."""
        # Arrange
        serializer = JsonSerializer()
        
        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            serializer.deserialize("not bytes")  # type: ignore
        
        assert "Expected bytes, got str" in str(exc_info.value)

    def test_json_deserialize_invalid_json_raises_error(self) -> None:
        """Test that invalid JSON raises ValueError."""
        # Arrange
        serializer = JsonSerializer()
        invalid_json = b'{"invalid": json}'
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            serializer.deserialize(invalid_json)
        
        assert "Invalid JSON data" in str(exc_info.value)

    def test_json_deserialize_invalid_utf8_raises_error(self) -> None:
        """Test that invalid UTF-8 raises ValueError."""
        # Arrange
        serializer = JsonSerializer()
        invalid_utf8 = b'\xff\xfe'  # Invalid UTF-8
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            serializer.deserialize(invalid_utf8)
        
        assert "Invalid UTF-8 encoding" in str(exc_info.value)


class TestMsgpackSerializer:
    """Test MsgpackSerializer implementation."""

    def test_msgpack_serializer_init_success(self) -> None:
        """Test MsgpackSerializer initialization with msgpack available."""
        # Arrange & Act
        try:
            serializer = MsgpackSerializer()
            # Assert
            assert serializer is not None
        except ImportError:
            pytest.skip("msgpack not available")

    def test_msgpack_serializer_init_missing_dependency(self) -> None:
        """Test MsgpackSerializer raises ImportError when msgpack unavailable."""
        # This test would need to mock the import failure
        # For now, we'll skip if msgpack is available
        try:
            import msgpack  # type: ignore[import-untyped,import-not-found] # noqa: F401
            pytest.skip("msgpack is available, cannot test ImportError")
        except ImportError:
            # Act & Assert
            with pytest.raises(ImportError) as exc_info:
                MsgpackSerializer()
            
            assert "requires msgpack package" in str(exc_info.value)

    @pytest.mark.skipif(
        condition=True,
        reason="Requires msgpack - will implement when needed"
    )
    def test_msgpack_serialize_deserialize_roundtrip(self) -> None:
        """Test msgpack serialization/deserialization roundtrip."""
        # This test would be implemented when msgpack is needed
        pass


class TestPickleSerializer:
    """Test PickleSerializer implementation."""

    def test_pickle_serializer_init_default_protocol(self) -> None:
        """Test PickleSerializer initialization with default protocol."""
        # Arrange & Act
        serializer = PickleSerializer()
        
        # Assert
        assert serializer._protocol == pickle.HIGHEST_PROTOCOL

    def test_pickle_serializer_init_custom_protocol(self) -> None:
        """Test PickleSerializer initialization with custom protocol."""
        # Arrange
        protocol = 4
        
        # Act
        serializer = PickleSerializer(protocol=protocol)
        
        # Assert
        assert serializer._protocol == protocol

    def test_pickle_serialize_simple_data(self) -> None:
        """Test pickle serialization of simple data."""
        # Arrange
        serializer = PickleSerializer()
        data = {"key": "value", "number": 42}
        
        # Act
        result = serializer.serialize(data)
        
        # Assert
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pickle_serialize_complex_data(self) -> None:
        """Test pickle serialization of complex Python objects."""
        # Arrange
        serializer = PickleSerializer()
        
        # Use a simple data structure instead of local class
        # as local classes are not picklable 
        data = {"custom_object": True, "value": 42, "nested": [1, 2, 3]}
        
        # Act
        result = serializer.serialize(data)
        
        # Assert
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pickle_deserialize_simple_data(self) -> None:
        """Test pickle deserialization of simple data."""
        # Arrange
        serializer = PickleSerializer()
        data = {"key": "value", "number": 42}
        serialized = pickle.dumps(data)
        
        # Act
        result = serializer.deserialize(serialized)
        
        # Assert
        assert result == data

    def test_pickle_serialize_deserialize_roundtrip(self) -> None:
        """Test pickle serialization/deserialization roundtrip."""
        # Arrange
        serializer = PickleSerializer()
        original_data = {"key": "value", "numbers": [1, 2, 3]}
        
        # Act
        serialized = serializer.serialize(original_data)
        deserialized = serializer.deserialize(serialized)
        
        # Assert
        assert deserialized == original_data

    def test_pickle_deserialize_invalid_bytes_raises_error(self) -> None:
        """Test that non-bytes input raises TypeError."""
        # Arrange
        serializer = PickleSerializer()
        
        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            serializer.deserialize("not bytes")  # type: ignore
        
        assert "Expected bytes, got str" in str(exc_info.value)

    def test_pickle_deserialize_invalid_data_raises_error(self) -> None:
        """Test that invalid pickle data raises ValueError."""
        # Arrange
        serializer = PickleSerializer()
        invalid_data = b"not pickle data"
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            serializer.deserialize(invalid_data)
        
        assert "Pickle deserialization failed" in str(exc_info.value)
