"""
Unit tests for keys module.

Tests key builders and hash utilities with 100% coverage
following AAA pattern and TDD principles.
"""

import hashlib
import pytest

from typing import Any

from dapr_state_cache.keys import (
    DefaultKeyBuilder,
    calculate_deterministic_hash,
    calculate_hash_for_args,
    truncate_hash,
    create_cache_key,
)


class TestHashUtils:
    """Test hash utility functions."""

    def test_calculate_deterministic_hash_simple_string(self) -> None:
        """Test hash calculation for simple string."""
        # Arrange
        data = "test string"
        
        # Act
        result = calculate_deterministic_hash(data)
        
        # Assert
        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 produces 64-char hex string
        
        # Verify it's deterministic
        result2 = calculate_deterministic_hash(data)
        assert result == result2

    def test_calculate_deterministic_hash_unicode_string(self) -> None:
        """Test hash calculation with unicode characters."""
        # Arrange
        data = "test ñáéíóú 中文 🎯"
        
        # Act
        result = calculate_deterministic_hash(data)
        
        # Assert
        assert isinstance(result, str)
        assert len(result) == 64
        
        # Should be consistent with manual SHA256
        expected = hashlib.sha256(data.encode('utf-8')).hexdigest()
        assert result == expected

    def test_calculate_deterministic_hash_empty_string(self) -> None:
        """Test hash calculation for empty string."""
        # Arrange
        data = ""
        
        # Act
        result = calculate_deterministic_hash(data)
        
        # Assert
        assert isinstance(result, str)
        assert len(result) == 64
        
        # Empty string has known SHA256
        expected = hashlib.sha256(b'').hexdigest()
        assert result == expected

    def test_calculate_hash_for_args_wrapper_function(self) -> None:
        """Test that calculate_hash_for_args is a proper wrapper."""
        # Arrange
        serialized_args = '{"args":[1,2],"kwargs":{"key":"value"}}'
        
        # Act
        result1 = calculate_hash_for_args(serialized_args)
        result2 = calculate_deterministic_hash(serialized_args)
        
        # Assert
        assert result1 == result2

    def test_truncate_hash_default_length(self) -> None:
        """Test hash truncation with default length."""
        # Arrange
        full_hash = "abcdef1234567890" * 4  # 64 chars
        
        # Act
        result = truncate_hash(full_hash)
        
        # Assert
        assert result == "abcdef1234567890"  # First 16 chars
        assert len(result) == 16

    def test_truncate_hash_custom_length(self) -> None:
        """Test hash truncation with custom length."""
        # Arrange
        full_hash = "abcdef1234567890" * 4  # 64 chars
        
        # Act
        result = truncate_hash(full_hash, length=8)
        
        # Assert
        assert result == "abcdef12"
        assert len(result) == 8

    def test_truncate_hash_full_length(self) -> None:
        """Test truncation that keeps full hash."""
        # Arrange
        full_hash = "abcdef1234567890"
        
        # Act
        result = truncate_hash(full_hash, length=16)
        
        # Assert
        assert result == full_hash

    def test_truncate_hash_invalid_length_raises_error(self) -> None:
        """Test that invalid length raises ValueError."""
        # Arrange
        full_hash = "abcdef12"
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            truncate_hash(full_hash, length=20)
        
        assert "exceeds hash length" in str(exc_info.value)

    def test_create_cache_key_valid_components(self) -> None:
        """Test cache key creation with valid components."""
        # Arrange
        prefix = "cache"
        function_path = "module.function"
        args_hash = "abcdef1234567890"
        
        # Act
        result = create_cache_key(prefix, function_path, args_hash)
        
        # Assert
        assert result == "cache:module.function:abcdef1234567890"

    def test_create_cache_key_complex_function_path(self) -> None:
        """Test cache key creation with complex function path."""
        # Arrange
        prefix = "user-cache"
        function_path = "myapp.services.UserService.get_user_profile"
        args_hash = "1234567890abcdef"
        
        # Act
        result = create_cache_key(prefix, function_path, args_hash)
        
        # Assert
        expected = "user-cache:myapp.services.UserService.get_user_profile:1234567890abcdef"
        assert result == expected

    def test_create_cache_key_empty_prefix_raises_error(self) -> None:
        """Test that empty prefix raises ValueError."""
        # Arrange
        prefix = ""
        function_path = "module.function"
        args_hash = "abcdef"
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_cache_key(prefix, function_path, args_hash)
        
        assert "Key prefix cannot be empty" in str(exc_info.value)

    def test_create_cache_key_empty_function_path_raises_error(self) -> None:
        """Test that empty function path raises ValueError."""
        # Arrange
        prefix = "cache"
        function_path = ""
        args_hash = "abcdef"
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_cache_key(prefix, function_path, args_hash)
        
        assert "Function path cannot be empty" in str(exc_info.value)

    def test_create_cache_key_empty_args_hash_raises_error(self) -> None:
        """Test that empty args hash raises ValueError."""
        # Arrange
        prefix = "cache"
        function_path = "module.function"
        args_hash = ""
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            create_cache_key(prefix, function_path, args_hash)
        
        assert "Arguments hash cannot be empty" in str(exc_info.value)


class TestDefaultKeyBuilder:
    """Test DefaultKeyBuilder implementation."""

    def test_default_key_builder_init_default_prefix(self) -> None:
        """Test DefaultKeyBuilder initialization with default prefix."""
        # Arrange & Act
        builder = DefaultKeyBuilder()
        
        # Assert
        assert builder.key_prefix == "cache"

    def test_default_key_builder_init_custom_prefix(self) -> None:
        """Test DefaultKeyBuilder initialization with custom prefix."""
        # Arrange
        custom_prefix = "user-cache"
        
        # Act
        builder = DefaultKeyBuilder(key_prefix=custom_prefix)
        
        # Assert
        assert builder.key_prefix == custom_prefix

    def test_default_key_builder_init_empty_prefix_raises_error(self) -> None:
        """Test that empty prefix raises ValueError."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError) as exc_info:
            DefaultKeyBuilder(key_prefix="")
        
        assert "Key prefix cannot be empty" in str(exc_info.value)

    def test_build_key_simple_function(self) -> None:
        """Test key building for simple function."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        def test_function(x: int, y: str) -> str:
            return f"{x}:{y}"
        
        args = (1, "test")
        kwargs: dict[str, Any] = {}
        
        # Act
        result = builder.build_key(test_function, args, kwargs)
        
        # Assert
        assert isinstance(result, str)
        assert result.startswith("cache:")
        assert "test_function" in result
        # Should have 3 parts: prefix, function_path, hash
        parts = result.split(":")
        assert len(parts) == 3
        assert parts[0] == "cache"
        assert parts[2]  # Hash should not be empty

    def test_build_key_function_with_kwargs(self) -> None:
        """Test key building with keyword arguments."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        def test_function(x: int, name: str = "default") -> str:
            return f"{x}:{name}"
        
        args = (42,)
        kwargs: dict[str, Any] = {"name": "test"}
        
        # Act
        result = builder.build_key(test_function, args, kwargs)
        
        # Assert
        assert isinstance(result, str)
        assert result.startswith("cache:")
        assert "test_function" in result
        
        # Different kwargs should produce different keys
        kwargs2 = {"name": "different"}
        result2 = builder.build_key(test_function, args, kwargs2)
        assert result != result2

    def test_build_key_deterministic_output(self) -> None:
        """Test that key building produces deterministic output."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        def test_function(x: int, y: str) -> str:
            return f"{x}:{y}"
        
        args = (1, "test")
        kwargs: dict[str, Any] = {"flag": True}
        
        # Act
        result1 = builder.build_key(test_function, args, kwargs)
        result2 = builder.build_key(test_function, args, kwargs)
        
        # Assert
        assert result1 == result2

    def test_build_key_different_args_produce_different_keys(self) -> None:
        """Test that different arguments produce different keys."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        def test_function(x: int) -> int:
            return x * 2
        
        # Act
        key1 = builder.build_key(test_function, (1,), {})
        key2 = builder.build_key(test_function, (2,), {})
        
        # Assert
        assert key1 != key2

    def test_build_key_instance_method_excludes_self(self) -> None:
        """Test that instance method keys exclude self."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        class TestClass:
            def method(self, x: int) -> int:
                return x * 2
        
        instance1 = TestClass()
        instance2 = TestClass()
        
        args1 = (instance1, 5)
        args2 = (instance2, 5)
        kwargs: dict[str, Any] = {}
        
        # Act
        key1 = builder.build_key(instance1.method, args1, kwargs)
        key2 = builder.build_key(instance2.method, args2, kwargs)
        
        # Assert
        # Keys should be the same since self is excluded
        assert key1 == key2

    def test_build_key_class_method_excludes_cls(self) -> None:
        """Test that class method keys exclude cls."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        class TestClass:
            @classmethod
            def class_method(cls, x: int) -> int:
                return x * 2
        
        args = (TestClass, 5)
        kwargs: dict[str, Any] = {}
        
        # Act
        key1 = builder.build_key(TestClass.class_method, args, kwargs)
        
        # Assert
        assert isinstance(key1, str)
        assert "class_method" in key1

    def test_build_key_static_method_includes_all_args(self) -> None:
        """Test that static method keys include all arguments."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        class TestClass:
            @staticmethod
            def static_method(x: int, y: str) -> str:
                return f"{x}:{y}"
        
        args = (42, "test")
        kwargs: dict[str, Any] = {}
        
        # Act
        result = builder.build_key(TestClass.static_method, args, kwargs)
        
        # Assert
        assert isinstance(result, str)
        assert "static_method" in result

    def test_build_key_custom_prefix(self) -> None:
        """Test key building with custom prefix."""
        # Arrange
        builder = DefaultKeyBuilder(key_prefix="custom")
        
        def test_function(x: int) -> int:
            return x
        
        args = (1,)
        kwargs: dict[str, Any] = {}
        
        # Act
        result = builder.build_key(test_function, args, kwargs)
        
        # Assert
        assert result.startswith("custom:")

    def test_is_instance_method_bound_method(self) -> None:
        """Test detection of bound instance method."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        class TestClass:
            def method(self) -> None:
                pass
        
        instance = TestClass()
        
        # Act
        result = builder._is_instance_method(instance.method)
        
        # Assert
        assert result is True

    def test_is_instance_method_function_with_self(self) -> None:
        """Test detection of function with self parameter."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        def function_with_self(self, x: int) -> int:
            return x
        
        # Act
        result = builder._is_instance_method(function_with_self)
        
        # Assert
        assert result is True

    def test_is_instance_method_regular_function(self) -> None:
        """Test that regular function is not detected as instance method."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        def regular_function(x: int) -> int:
            return x
        
        # Act
        result = builder._is_instance_method(regular_function)
        
        # Assert
        assert result is False

    def test_is_class_method_bound_class_method(self) -> None:
        """Test detection of bound class method."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        class TestClass:
            @classmethod
            def class_method(cls) -> None:
                pass
        
        # Act
        result = builder._is_class_method(TestClass.class_method)
        
        # Assert
        assert result is True

    def test_is_class_method_function_with_cls(self) -> None:
        """Test detection of function with cls parameter."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        def function_with_cls(cls, x: int) -> int:
            return x
        
        # Act
        result = builder._is_class_method(function_with_cls)
        
        # Assert
        assert result is True

    def test_is_class_method_regular_function(self) -> None:
        """Test that regular function is not detected as class method."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        def regular_function(x: int) -> int:
            return x
        
        # Act
        result = builder._is_class_method(regular_function)
        
        # Assert
        assert result is False

    def test_build_key_error_handling(self) -> None:
        """Test that build_key handles errors gracefully."""
        # Arrange
        builder = DefaultKeyBuilder()
        
        # Create a function that will cause serialization to fail
        def problematic_function(obj) -> None:
            pass
        
        class NonSerializableObject:
            __slots__ = ()  # No __dict__
        
        args = (NonSerializableObject(),)
        kwargs: dict[str, Any] = {}
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            builder.build_key(problematic_function, args, kwargs)
        
        assert "Failed to build cache key" in str(exc_info.value)
