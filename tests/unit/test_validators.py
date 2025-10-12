"""
Unit tests for parameter validators.

Tests validation logic for cache configuration parameters following AAA pattern
and TDD principles with comprehensive coverage of validation rules.
"""

import pytest

from dapr_state_cache.core.validators import (
    ValidationError,
    validate_ttl_seconds,
    validate_store_name,
    validate_key_prefix,
    validate_crypto_component_name,
    validate_cache_parameters,
    validate_invalidation_parameters,
)


class TestTTLValidation:
    """Test TTL parameter validation."""

    def test_validate_ttl_seconds_none_valid(self) -> None:
        """Test TTL validation with None (uses default)."""
        # Act & Assert - should not raise
        validate_ttl_seconds(None)

    def test_validate_ttl_seconds_positive_valid(self) -> None:
        """Test TTL validation with positive values."""
        # Arrange
        valid_ttls = [1, 60, 3600, 86400, 604800]
        
        # Act & Assert - should not raise
        for ttl in valid_ttls:
            validate_ttl_seconds(ttl)

    def test_validate_ttl_seconds_zero_invalid(self) -> None:
        """Test TTL validation rejects zero."""
        # Act & Assert
        with pytest.raises(ValidationError, match="ttl_seconds must be >= 1"):
            validate_ttl_seconds(0)

    def test_validate_ttl_seconds_negative_invalid(self) -> None:
        """Test TTL validation rejects negative values."""
        # Arrange
        invalid_ttls = [-1, -10, -3600]
        
        # Act & Assert
        for ttl in invalid_ttls:
            with pytest.raises(ValidationError, match="ttl_seconds must be >= 1"):
                validate_ttl_seconds(ttl)

    def test_validate_ttl_seconds_wrong_type_invalid(self) -> None:
        """Test TTL validation rejects non-integer types."""
        # Arrange
        invalid_types = ["60", 60.0, True, [60], {"ttl": 60}]
        
        # Act & Assert
        for invalid_ttl in invalid_types:
            with pytest.raises(ValidationError, match="ttl_seconds must be int or None"):
                validate_ttl_seconds(invalid_ttl)


class TestStoreNameValidation:
    """Test store name parameter validation."""

    def test_validate_store_name_valid(self) -> None:
        """Test store name validation with valid names."""
        # Arrange
        valid_names = ["redis-cache", "mongodb-store", "cache", "my_store_123"]
        
        # Act & Assert - should not raise
        for name in valid_names:
            validate_store_name(name)

    def test_validate_store_name_empty_invalid(self) -> None:
        """Test store name validation rejects empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="store_name cannot be empty"):
            validate_store_name("")

    def test_validate_store_name_whitespace_invalid(self) -> None:
        """Test store name validation rejects whitespace-only."""
        # Arrange
        whitespace_names = [" ", "\t", "\n", "   ", "\t\n "]
        
        # Act & Assert
        for name in whitespace_names:
            with pytest.raises(ValidationError, match="store_name cannot be empty"):
                validate_store_name(name)

    def test_validate_store_name_wrong_type_invalid(self) -> None:
        """Test store name validation rejects non-string types."""
        # Arrange
        invalid_types = [123, True, ["redis"], {"name": "redis"}, None]
        
        # Act & Assert
        for invalid_name in invalid_types:
            with pytest.raises(ValidationError, match="store_name must be str"):
                validate_store_name(invalid_name)


class TestKeyPrefixValidation:
    """Test key prefix parameter validation."""

    def test_validate_key_prefix_valid(self) -> None:
        """Test key prefix validation with valid prefixes."""
        # Arrange
        valid_prefixes = ["cache", "myapp", "user-cache", "api_v1"]
        
        # Act & Assert - should not raise
        for prefix in valid_prefixes:
            validate_key_prefix(prefix)

    def test_validate_key_prefix_empty_invalid(self) -> None:
        """Test key prefix validation rejects empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="key_prefix cannot be empty"):
            validate_key_prefix("")

    def test_validate_key_prefix_whitespace_invalid(self) -> None:
        """Test key prefix validation rejects whitespace-only."""
        # Arrange
        whitespace_prefixes = [" ", "\t", "\n", "   "]
        
        # Act & Assert
        for prefix in whitespace_prefixes:
            with pytest.raises(ValidationError, match="key_prefix cannot be empty"):
                validate_key_prefix(prefix)

    def test_validate_key_prefix_wrong_type_invalid(self) -> None:
        """Test key prefix validation rejects non-string types."""
        # Arrange
        invalid_types = [123, True, ["cache"], None]
        
        # Act & Assert
        for invalid_prefix in invalid_types:
            with pytest.raises(ValidationError, match="key_prefix must be str"):
                validate_key_prefix(invalid_prefix)


class TestCryptoComponentNameValidation:
    """Test crypto component name parameter validation."""

    def test_validate_crypto_component_name_none_valid(self) -> None:
        """Test crypto component validation with None."""
        # Act & Assert - should not raise
        validate_crypto_component_name(True, None)
        validate_crypto_component_name(False, None)

    def test_validate_crypto_component_name_valid_string(self) -> None:
        """Test crypto component validation with valid names."""
        # Arrange
        valid_names = ["vault-kms", "azure-keyvault", "aws-kms", "crypto-component"]
        
        # Act & Assert - should not raise
        for name in valid_names:
            validate_crypto_component_name(True, name)

    def test_validate_crypto_component_name_empty_invalid(self) -> None:
        """Test crypto component validation rejects empty string."""
        # Act & Assert
        with pytest.raises(ValidationError, match="crypto_component_name cannot be empty"):
            validate_crypto_component_name(True, "")

    def test_validate_crypto_component_name_whitespace_invalid(self) -> None:
        """Test crypto component validation rejects whitespace-only."""
        # Arrange
        whitespace_names = [" ", "\t", "   "]
        
        # Act & Assert
        for name in whitespace_names:
            with pytest.raises(ValidationError, match="crypto_component_name cannot be empty"):
                validate_crypto_component_name(True, name)

    def test_validate_crypto_component_name_wrong_type_invalid(self) -> None:
        """Test crypto component validation rejects non-string types."""
        # Arrange
        invalid_types = [123, True, ["vault"], {"name": "vault"}]
        
        # Act & Assert
        for invalid_name in invalid_types:
            with pytest.raises(ValidationError, match="crypto_component_name must be str or None"):
                validate_crypto_component_name(True, invalid_name)


class TestCacheParametersValidation:
    """Test comprehensive cache parameters validation."""

    def test_validate_cache_parameters_all_valid(self) -> None:
        """Test cache parameters validation with all valid parameters."""
        # Act & Assert - should not raise
        validate_cache_parameters(
            store_name="redis-cache",
            ttl_seconds=3600,
            key_prefix="myapp",
            use_dapr_crypto=True,
            crypto_component_name="vault-kms"
        )

    def test_validate_cache_parameters_minimal_valid(self) -> None:
        """Test cache parameters validation with minimal valid parameters."""
        # Act & Assert - should not raise
        validate_cache_parameters(store_name="redis-cache")

    def test_validate_cache_parameters_defaults_valid(self) -> None:
        """Test cache parameters validation with default values."""
        # Act & Assert - should not raise
        validate_cache_parameters(
            store_name="redis-cache",
            ttl_seconds=None,
            key_prefix="cache",
            use_dapr_crypto=False,
            crypto_component_name=None
        )

    def test_validate_cache_parameters_invalid_store_name(self) -> None:
        """Test cache parameters validation propagates store name errors."""
        # Act & Assert
        with pytest.raises(ValidationError, match="store_name cannot be empty"):
            validate_cache_parameters(store_name="")

    def test_validate_cache_parameters_invalid_ttl(self) -> None:
        """Test cache parameters validation propagates TTL errors."""
        # Act & Assert
        with pytest.raises(ValidationError, match="ttl_seconds must be >= 1"):
            validate_cache_parameters(
                store_name="redis-cache",
                ttl_seconds=0
            )

    def test_validate_cache_parameters_invalid_key_prefix(self) -> None:
        """Test cache parameters validation propagates key prefix errors."""
        # Act & Assert
        with pytest.raises(ValidationError, match="key_prefix cannot be empty"):
            validate_cache_parameters(
                store_name="redis-cache",
                key_prefix=""
            )

    def test_validate_cache_parameters_invalid_crypto_component(self) -> None:
        """Test cache parameters validation propagates crypto component errors."""
        # Act & Assert
        with pytest.raises(ValidationError, match="crypto_component_name cannot be empty"):
            validate_cache_parameters(
                store_name="redis-cache",
                use_dapr_crypto=True,
                crypto_component_name=""
            )


class TestInvalidationParametersValidation:
    """Test invalidation parameters validation."""

    def test_validate_invalidation_parameters_key_valid(self) -> None:
        """Test invalidation validation with valid key."""
        # Act & Assert - should not raise
        validate_invalidation_parameters(key="user:123")

    def test_validate_invalidation_parameters_prefix_valid(self) -> None:
        """Test invalidation validation with valid prefix."""
        # Act & Assert - should not raise
        validate_invalidation_parameters(prefix="user:")

    def test_validate_invalidation_parameters_both_none_invalid(self) -> None:
        """Test invalidation validation rejects both None."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Either 'key' or 'prefix' must be provided"):
            validate_invalidation_parameters(key=None, prefix=None)

    def test_validate_invalidation_parameters_both_provided_invalid(self) -> None:
        """Test invalidation validation rejects both key and prefix."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Cannot specify both 'key' and 'prefix'"):
            validate_invalidation_parameters(key="user:123", prefix="user:")

    def test_validate_invalidation_parameters_empty_key_invalid(self) -> None:
        """Test invalidation validation rejects empty key."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Invalidation key must be non-empty"):
            validate_invalidation_parameters(key="")

    def test_validate_invalidation_parameters_whitespace_key_invalid(self) -> None:
        """Test invalidation validation rejects whitespace-only key."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Invalidation key must be non-empty"):
            validate_invalidation_parameters(key="   ")

    def test_validate_invalidation_parameters_empty_prefix_invalid(self) -> None:
        """Test invalidation validation rejects empty prefix."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Invalidation prefix must be non-empty"):
            validate_invalidation_parameters(prefix="")

    def test_validate_invalidation_parameters_whitespace_prefix_invalid(self) -> None:
        """Test invalidation validation rejects whitespace-only prefix."""
        # Act & Assert
        with pytest.raises(ValidationError, match="Invalidation prefix must be non-empty"):
            validate_invalidation_parameters(prefix="   ")


class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_inherits_value_error(self) -> None:
        """Test ValidationError inherits from ValueError."""
        # Arrange
        error = ValidationError("test error")
        
        # Assert
        assert isinstance(error, ValueError)
        assert isinstance(error, ValidationError)

    def test_validation_error_message(self) -> None:
        """Test ValidationError preserves message."""
        # Arrange
        message = "Invalid parameter value"
        error = ValidationError(message)
        
        # Assert
        assert str(error) == message
