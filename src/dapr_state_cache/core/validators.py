"""
Parameter validation utilities.

Implements validation rules as specified in section 16 of the technical
specification to ensure cache parameters meet requirements and constraints.
"""

from .constants import (
    ERROR_CRYPTO_COMPONENT_EMPTY,
    ERROR_INVALIDATION_KEY_INVALID,
    ERROR_INVALIDATION_PARAMS_BOTH,
    ERROR_INVALIDATION_PARAMS_MISSING,
    ERROR_INVALIDATION_PREFIX_INVALID,
    ERROR_KEY_PREFIX_EMPTY,
    ERROR_STORE_NAME_EMPTY,
    ERROR_TTL_INVALID,
    ERROR_TTL_TYPE_INVALID,
    MIN_TTL_SECONDS,
)


class ValidationError(ValueError):
    """Parameter validation error.

    Raised when cache parameters fail validation checks.
    """

    pass


def validate_ttl_seconds(ttl_seconds: int | None) -> None:
    """Validate TTL parameter.

    TTL must be >= 1 second or None (for default).
    TTL=0 or negative values are invalid per Dapr constraints.

    Args:
        ttl_seconds: TTL value to validate

    Raises:
        ValidationError: If TTL is invalid
    """
    if ttl_seconds is not None:
        _validate_ttl_type(ttl_seconds)
        _validate_ttl_range(ttl_seconds)


def _validate_ttl_type(ttl_seconds: int | None) -> None:
    """Validate TTL parameter type."""
    # Check for bool first since bool is subclass of int in Python
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
        raise ValidationError(ERROR_TTL_TYPE_INVALID.format(type_name=type(ttl_seconds).__name__))


def _validate_ttl_range(ttl_seconds: int) -> None:
    """Validate TTL parameter range."""
    if ttl_seconds < MIN_TTL_SECONDS:
        raise ValidationError(ERROR_TTL_INVALID.format(value=ttl_seconds))


def validate_store_name(store_name: str) -> None:
    """Validate Dapr state store name.

    Store name cannot be empty or whitespace-only.

    Args:
        store_name: Dapr state store component name

    Raises:
        ValidationError: If store name is invalid
    """
    _validate_string_type("store_name", store_name)
    _validate_non_empty_string(store_name, ERROR_STORE_NAME_EMPTY)


def validate_key_prefix(key_prefix: str) -> None:
    """Validate cache key prefix.

    Key prefix cannot be empty or whitespace-only.

    Args:
        key_prefix: Prefix for cache keys

    Raises:
        ValidationError: If key prefix is invalid
    """
    _validate_string_type("key_prefix", key_prefix)
    _validate_non_empty_string(key_prefix, ERROR_KEY_PREFIX_EMPTY)


def validate_crypto_component_name(use_dapr_crypto: bool, crypto_component_name: str | None) -> None:
    """Validate Dapr cryptography component name.

    When use_dapr_crypto=True, component name is validated if provided.

    Args:
        use_dapr_crypto: Whether cryptography is enabled
        crypto_component_name: Name of crypto component

    Raises:
        ValidationError: If crypto component name is invalid
    """
    if crypto_component_name is not None:
        _validate_optional_string_type("crypto_component_name", crypto_component_name)
        _validate_non_empty_string(crypto_component_name, ERROR_CRYPTO_COMPONENT_EMPTY)


def validate_cache_parameters(
    store_name: str,
    ttl_seconds: int | None = None,
    key_prefix: str = "cache",
    use_dapr_crypto: bool = False,
    crypto_component_name: str | None = None,
) -> None:
    """Validate all cache parameters comprehensively.

    Performs validation of all cache configuration parameters according
    to the constraints specified in section 16 of the specification.

    Args:
        store_name: Dapr state store component name
        ttl_seconds: TTL in seconds (>= 1 or None for default)
        key_prefix: Prefix for cache keys
        use_dapr_crypto: Whether to enable Dapr cryptography
        crypto_component_name: Name of crypto component

    Raises:
        ValidationError: If any parameter is invalid

    Example:
        ```python
        # Valid parameters
        validate_cache_parameters(
            store_name="redis-cache",
            ttl_seconds=3600,
            key_prefix="myapp",
            use_dapr_crypto=True,
            crypto_component_name="vault-kms"
        )

        # Invalid TTL
        validate_cache_parameters(
            store_name="redis-cache",
            ttl_seconds=0  # Raises ValidationError
        )
        ```
    """
    # Validate individual parameters
    validate_store_name(store_name)
    validate_ttl_seconds(ttl_seconds)
    validate_key_prefix(key_prefix)
    validate_crypto_component_name(use_dapr_crypto, crypto_component_name)

    # Additional cross-parameter validations can be added here
    # For example, checking for incompatible combinations per section 16.5


def validate_invalidation_parameters(key: str | None = None, prefix: str | None = None) -> None:
    """Validate cache invalidation parameters.

    Either key or prefix must be provided for invalidation operations.

    Args:
        key: Specific cache key to invalidate
        prefix: Key prefix for bulk invalidation

    Raises:
        ValidationError: If parameters are invalid
    """
    _validate_invalidation_params_presence(key, prefix)
    _validate_invalidation_params_exclusivity(key, prefix)
    _validate_invalidation_key_if_provided(key)
    _validate_invalidation_prefix_if_provided(prefix)


def _validate_string_type(param_name: str, value: str) -> None:
    """Validate that a parameter is a string type."""
    if not isinstance(value, str):
        raise ValidationError(f"{param_name} must be str, got {type(value).__name__}")


def _validate_optional_string_type(param_name: str, value: str | None) -> None:
    """Validate that a parameter is a string or None type."""
    if not isinstance(value, str):
        raise ValidationError(f"{param_name} must be str or None, got {type(value).__name__}")


def _validate_non_empty_string(value: str, error_message: str) -> None:
    """Validate that a string is not empty or whitespace-only."""
    if not value or not value.strip():
        raise ValidationError(error_message)


def _validate_invalidation_params_presence(key: str | None, prefix: str | None) -> None:
    """Validate that at least one invalidation parameter is provided."""
    if key is None and prefix is None:
        raise ValidationError(ERROR_INVALIDATION_PARAMS_MISSING)


def _validate_invalidation_params_exclusivity(key: str | None, prefix: str | None) -> None:
    """Validate that only one invalidation parameter is provided."""
    if key is not None and prefix is not None:
        raise ValidationError(ERROR_INVALIDATION_PARAMS_BOTH)


def _validate_invalidation_key_if_provided(key: str | None) -> None:
    """Validate invalidation key if provided."""
    if key is not None:
        if not isinstance(key, str) or not key.strip():
            raise ValidationError(ERROR_INVALIDATION_KEY_INVALID)


def _validate_invalidation_prefix_if_provided(prefix: str | None) -> None:
    """Validate invalidation prefix if provided."""
    if prefix is not None:
        if not isinstance(prefix, str) or not prefix.strip():
            raise ValidationError(ERROR_INVALIDATION_PREFIX_INVALID)
