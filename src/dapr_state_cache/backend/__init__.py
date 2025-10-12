"""
Backend storage implementations.

This module provides cache backend implementations using Dapr State Store
with comprehensive error handling and observability.
"""

from .constants import (
    DAPR_NOT_CONFIGURED_INDICATORS,
    DAPR_TIMEOUT_INDICATORS,
    DEFAULT_STORE_NAME,
    DEFAULT_TIMEOUT_SECONDS,
    MIN_TTL_SECONDS,
)
from .dapr_state_backend import DaprStateBackend
from .exceptions import (
    CacheAuthenticationError,
    CacheBackendError,
    CacheCryptographyError,
    CacheKeyEmptyError,
    CacheSerializationError,
    CacheTimeoutError,
    CacheValueEmptyError,
    DaprUnavailableError,
    InvalidTTLValueError,
    IrrecoverableCacheError,
    RecoverableCacheError,
    StateStoreNotConfiguredError,
)

__all__ = [
    "CacheAuthenticationError",
    "CacheBackendError",
    "CacheCryptographyError",
    "CacheKeyEmptyError",
    "CacheSerializationError",
    "CacheTimeoutError",
    "CacheValueEmptyError",
    "DAPR_NOT_CONFIGURED_INDICATORS",
    "DAPR_TIMEOUT_INDICATORS",
    "DEFAULT_STORE_NAME",
    "DEFAULT_TIMEOUT_SECONDS",
    "DaprStateBackend",
    "DaprUnavailableError",
    "InvalidTTLValueError",
    "IrrecoverableCacheError",
    "MIN_TTL_SECONDS",
    "RecoverableCacheError",
    "StateStoreNotConfiguredError",
]
