"""
Configuration management for cache decorator.

Handles environment variables, default values, and parameter validation
for cache configuration according to specification section 3.1.
"""

import os
from typing import Optional


class CacheConfig:
    """Configuration manager for cache decorator.
    
    Handles environment variable resolution and default value management
    following the precedence rules defined in the specification:
    
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
    def resolve_store_name(cls, explicit_value: Optional[str] = None) -> str:
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
    def resolve_crypto_component_name(
        cls, 
        explicit_value: Optional[str] = None
    ) -> str:
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
    def resolve_ttl_seconds(cls, explicit_value: Optional[int] = None) -> int:
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
        self,
        store_name: str,
        ttl_seconds: Optional[int],
        key_prefix: str,
        use_dapr_crypto: bool,
        crypto_component_name: Optional[str]
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
        # Validate store_name
        if not store_name or not store_name.strip():
            raise ValueError("store_name cannot be empty")
        
        # Validate TTL
        if ttl_seconds is not None and ttl_seconds < 1:
            raise ValueError(f"ttl_seconds must be >= 1 or None, got {ttl_seconds}")
        
        # Validate key_prefix
        if not key_prefix or not key_prefix.strip():
            raise ValueError("key_prefix cannot be empty")
        
        # Validate crypto configuration
        if use_dapr_crypto and not crypto_component_name:
            raise ValueError(
                "crypto_component_name is required when use_dapr_crypto=True"
            )
