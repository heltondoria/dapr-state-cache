"""
Cache backend specific exceptions.

Defines exception hierarchy for backend operations to distinguish between
recoverable and irrecoverable errors as per specification section 7.3.
"""


class CacheBackendError(Exception):
    """Base exception for all cache backend errors."""

    def __init__(self, message: str, key: str | None = None) -> None:
        """Initialize cache backend error.

        Args:
            message: Error message
            key: Cache key involved in the operation (if applicable)
        """
        super().__init__(message)
        self.key = key


class RecoverableCacheError(CacheBackendError):
    """Recoverable cache error that should not break application flow.

    These errors are logged but operations continue gracefully.
    Examples: serialization failures, timeouts, temporary network issues.
    """

    pass


class IrrecoverableCacheError(CacheBackendError):
    """Irrecoverable cache error indicating critical infrastructure problems.

    These errors are propagated to the application for handling.
    Examples: Dapr not available, store not configured, authentication errors.
    """

    pass


class CacheTimeoutError(RecoverableCacheError):
    """Cache operation timed out."""

    pass


class CacheSerializationError(RecoverableCacheError):
    """Cache data serialization/deserialization failed."""

    pass


class CacheCryptographyError(RecoverableCacheError):
    """Cache cryptography operation failed."""

    pass


class DaprUnavailableError(IrrecoverableCacheError):
    """Dapr sidecar is not available or accessible."""

    pass


class StateStoreNotConfiguredError(IrrecoverableCacheError):
    """State store is not properly configured in Dapr."""

    pass


class CacheAuthenticationError(IrrecoverableCacheError):
    """Authentication failed with the underlying state store."""

    pass


class CacheKeyEmptyError(CacheBackendError):
    """Cache key is empty or invalid.

    This indicates a configuration or programming error in key generation.
    """

    pass


class CacheValueEmptyError(CacheBackendError):
    """Cache value is empty or invalid when not expected."""

    pass


class InvalidTTLValueError(CacheBackendError):
    """TTL value is invalid (e.g., negative or zero when positive required)."""

    pass
