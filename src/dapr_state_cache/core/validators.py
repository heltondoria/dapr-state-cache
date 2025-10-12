"""
Parameter validation utilities.

Implements validation rules as specified in section 16 of the technical
specification to ensure cache parameters meet requirements and constraints.
"""



class ValidationError(ValueError):
    """Parameter validation error.

    Raised when cache parameters fail validation checks.
    """

    pass


def validate_ttl_seconds(ttl_seconds: int | None) -> None:
    """Validate TTL parameter.

    TTL must be >= 1 second or None (for default 3600s).
    TTL=0 or negative values are invalid per Dapr constraints.

    Args:
        ttl_seconds: TTL value to validate

    Raises:
        ValidationError: If TTL is invalid
    """
    if ttl_seconds is not None:
        # Check for bool first since bool is subclass of int in Python
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
            raise ValidationError(f"ttl_seconds must be int or None, got {type(ttl_seconds).__name__}")

        if ttl_seconds < 1:
            raise ValidationError(f"ttl_seconds must be >= 1 or None (default 3600), got {ttl_seconds}")


def validate_store_name(store_name: str) -> None:
    """Validate Dapr state store name.

    Store name cannot be empty or whitespace-only.

    Args:
        store_name: Dapr state store component name

    Raises:
        ValidationError: If store name is invalid
    """
    if not isinstance(store_name, str):
        raise ValidationError(f"store_name must be str, got {type(store_name).__name__}")

    if not store_name or not store_name.strip():
        raise ValidationError("store_name cannot be empty or whitespace-only")


def validate_key_prefix(key_prefix: str) -> None:
    """Validate cache key prefix.

    Key prefix cannot be empty or whitespace-only.

    Args:
        key_prefix: Prefix for cache keys

    Raises:
        ValidationError: If key prefix is invalid
    """
    if not isinstance(key_prefix, str):
        raise ValidationError(f"key_prefix must be str, got {type(key_prefix).__name__}")

    if not key_prefix or not key_prefix.strip():
        raise ValidationError("key_prefix cannot be empty or whitespace-only")


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
        if not isinstance(crypto_component_name, str):
            raise ValidationError(
                f"crypto_component_name must be str or None, got {type(crypto_component_name).__name__}"
            )

        if not crypto_component_name.strip():
            raise ValidationError("crypto_component_name cannot be empty or whitespace-only")


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
    if key is None and prefix is None:
        raise ValidationError("Either 'key' or 'prefix' must be provided for invalidation")

    if key is not None and prefix is not None:
        raise ValidationError("Cannot specify both 'key' and 'prefix' for invalidation")

    if key is not None:
        if not isinstance(key, str) or not key.strip():
            raise ValidationError("Invalidation key must be non-empty string")

    if prefix is not None:
        if not isinstance(prefix, str) or not prefix.strip():
            raise ValidationError("Invalidation prefix must be non-empty string")
