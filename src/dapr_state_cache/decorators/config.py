"""
Configuration management for cache decorator.

Handles environment variables, default values, and parameter validation
for cache configuration according to specification section 3.1.
"""

import os


class CacheConfig:
    """Configuration manager for cache decorator.


    Handles environment variable resolution and default value management
    following the precedence rules defined in the specification:

    1. Explicit decorator parameter (highest precedence)

    1. Explicit decorator parameter (highest precedence)
    2. Environment variable
    3. Default value (lowest precedence)
    """

    # Environment variable names
    ENV_DEFAULT_STORE_NAME = "DAPR_CACHE_DEFAULT_STORE_NAME"
    ENV_DEFAULT_CRYPTO_NAME = "DAPR_CACHE_DEFAULT_CRYPTO_NAME"

    # Default values
    DEFAULT_STORE_NAME = "cache"
    DEFAULT_TTL_SECONDS = 3600
    DEFAULT_KEY_PREFIX = "cache"
    DEFAULT_CRYPTO_COMPONENT_NAME = "cache-crypto"

    @classmethod
    def resolve_store_name(cls, explicit_value: str | None = None) -> str:
        """Resolve store name following precedence rules.


        Args:
            explicit_value: Explicit store name from decorator parameter


        Returns:
            Resolved store name
        """
        if explicit_value is not None:
            return explicit_value

        env_value = os.getenv(cls.ENV_DEFAULT_STORE_NAME)
        if env_value:
            return env_value

        return cls.DEFAULT_STORE_NAME

    @classmethod
    def resolve_crypto_component_name(cls, explicit_value: str | None = None) -> str:
        """Resolve crypto component name following precedence rules.


        Args:
            explicit_value: Explicit component name from decorator parameter


        Returns:
            Resolved crypto component name
        """
        if explicit_value is not None:
            return explicit_value

        env_value = os.getenv(cls.ENV_DEFAULT_CRYPTO_NAME)
        if env_value:
            return env_value

        return cls.DEFAULT_CRYPTO_COMPONENT_NAME

    @classmethod
    def resolve_ttl_seconds(cls, explicit_value: int | None = None) -> int:
        """Resolve TTL seconds with default fallback.


        Args:
            explicit_value: Explicit TTL from decorator parameter


        Returns:
            Resolved TTL in seconds
        """
        if explicit_value is not None:
            return explicit_value

        return cls.DEFAULT_TTL_SECONDS

    @classmethod
    def validate_parameters(
        cls,
        store_name: str,
        ttl_seconds: int | None,
        key_prefix: str,
        use_dapr_crypto: bool,
        crypto_component_name: str | None,
    ) -> None:
        """Validate cache configuration parameters.


        Args:
            store_name: Dapr state store name
            ttl_seconds: TTL in seconds (None for default)
            key_prefix: Cache key prefix
            use_dapr_crypto: Whether to use Dapr cryptography
            crypto_component_name: Crypto component name


        Raises:
            ValueError: If any parameter is invalid
        """
        cls._validate_store_name(store_name)
        cls._validate_ttl_seconds(ttl_seconds)
        cls._validate_key_prefix(key_prefix)
        cls._validate_crypto_config(use_dapr_crypto, crypto_component_name)

    @classmethod
    def _validate_store_name(cls, store_name: str) -> None:
        """Validate store name parameter.

        Args:
            store_name: Dapr state store name

        Raises:
            ValueError: If store_name is invalid
        """
        if not store_name or not store_name.strip():
            raise ValueError("store_name cannot be empty")

    @classmethod
    def _validate_ttl_seconds(cls, ttl_seconds: int | None) -> None:
        """Validate TTL seconds parameter.

        Args:
            ttl_seconds: TTL in seconds (None for default)

        Raises:
            ValueError: If ttl_seconds is invalid
        """
        if ttl_seconds is not None and ttl_seconds < 1:
            raise ValueError(f"ttl_seconds must be >= 1 or None, got {ttl_seconds}")

    @classmethod
    def _validate_key_prefix(cls, key_prefix: str) -> None:
        """Validate key prefix parameter.

        Args:
            key_prefix: Cache key prefix

        Raises:
            ValueError: If key_prefix is invalid
        """
        if not key_prefix or not key_prefix.strip():
            raise ValueError("key_prefix cannot be empty")

    @classmethod
    def _validate_crypto_config(cls, use_dapr_crypto: bool, crypto_component_name: str | None) -> None:
        """Validate crypto configuration parameters.

        Args:
            use_dapr_crypto: Whether to use Dapr cryptography
            crypto_component_name: Crypto component name

        Raises:
            ValueError: If crypto configuration is invalid
        """
        if use_dapr_crypto and not crypto_component_name:
            raise ValueError("crypto_component_name is required when use_dapr_crypto=True")
            raise ValueError("crypto_component_name is required when use_dapr_crypto=True")
