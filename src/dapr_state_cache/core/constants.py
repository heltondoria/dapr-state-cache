"""
Constants for cache core components.

Defines configuration constants and default values used throughout
the cache system to eliminate magic numbers and improve maintainability.
"""

# Default TTL configuration
DEFAULT_TTL_SECONDS = 3600  # 1 hour default TTL
MIN_TTL_SECONDS = 1  # Minimum valid TTL per Dapr constraints

# Thread pool configuration
MAX_THREAD_WORKERS = 32  # Maximum threads in executor pool
THREAD_POOL_PREFIX = "dapr-cache-sync"  # Thread name prefix

# Backend timeout configuration
DEFAULT_BACKEND_TIMEOUT_SECONDS = 5.0  # Default backend operation timeout

# Cryptography defaults
DEFAULT_CRYPTO_KEY_NAME = "cache-encryption-key"  # Default encryption key name
DEFAULT_CRYPTO_ALGORITHM = "AES-GCM-256"  # Default encryption algorithm

# Health check constants
HEALTH_STATUS_HEALTHY = "healthy"
HEALTH_STATUS_DEGRADED = "degraded"
HEALTH_STATUS_DISABLED = "disabled"

# Cache key defaults
DEFAULT_KEY_PREFIX = "cache"  # Default cache key prefix

# Error message templates
ERROR_TTL_INVALID = "ttl_seconds must be >= 1 or None (default 3600), got {value}"
ERROR_TTL_TYPE_INVALID = "ttl_seconds must be int or None, got {type_name}"
ERROR_STORE_NAME_EMPTY = "store_name cannot be empty or whitespace-only"
ERROR_KEY_PREFIX_EMPTY = "key_prefix cannot be empty or whitespace-only"
ERROR_CRYPTO_COMPONENT_EMPTY = "crypto_component_name cannot be empty or whitespace-only"
ERROR_CACHE_KEY_EMPTY = "Generated cache key is empty"
ERROR_CRYPTO_COMPONENT_REQUIRED = "crypto_component_name is required when use_dapr_crypto=True"
ERROR_INVALIDATION_PARAMS_MISSING = "Either 'key' or 'prefix' must be provided for invalidation"
ERROR_INVALIDATION_PARAMS_BOTH = "Cannot specify both 'key' and 'prefix' for invalidation"
ERROR_INVALIDATION_KEY_INVALID = "Invalidation key must be non-empty string"
ERROR_INVALIDATION_PREFIX_INVALID = "Invalidation prefix must be non-empty string"

# Test data for health checks
HEALTH_CHECK_TEST_DATA = {"test": "health_check"}
