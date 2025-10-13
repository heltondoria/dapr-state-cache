"""
Cache operation handlers for CacheService.

Provides specialized handlers for cache operations following Single Responsibility
Principle and Clean Code practices. Each handler focuses on a specific aspect
of cache operations.
"""

import logging
import time
from typing import Any

from ..protocols import ObservabilityHooks, Serializer
from .crypto_integration import CryptoIntegration, DaprCryptoError, NoOpCryptoIntegration

logger = logging.getLogger(__name__)


class CacheGetOperationHandler:
    """Handles cache get operations with proper separation of concerns."""

    def __init__(
        self,
        serializer: Serializer,
        crypto: CryptoIntegration | NoOpCryptoIntegration,
        hooks: ObservabilityHooks | None = None,
    ) -> None:
        """Initialize get operation handler.

        Args:
            serializer: Data serializer for deserialization
            crypto: Crypto integration for decryption
            hooks: Optional observability hooks
        """
        self._serializer = serializer
        self._crypto = crypto
        self._hooks = hooks

    async def handle_get_operation(self, cache_key: str, serialized_data: bytes) -> Any | None:
        """Handle complete cache get operation flow.

        Args:
            cache_key: Cache key for observability
            serialized_data: Raw serialized data from backend

        Returns:
            Deserialized value or None if operation fails
        """
        start_time = time.time()

        try:
            # Decrypt data
            decrypted_data = await self._decrypt_data(cache_key, serialized_data)
            if decrypted_data is None:
                self._record_cache_miss(cache_key, start_time)
                return None

            # Deserialize data
            value = await self._deserialize_data(cache_key, decrypted_data)
            if value is None:
                self._record_cache_miss(cache_key, start_time)
                return None

            self._record_cache_hit(cache_key, start_time)
            return value

        except Exception as e:
            logger.error(f"Cache get operation failed for key '{cache_key}': {e}")
            self._record_cache_error(cache_key, e)
            self._record_cache_miss(cache_key, start_time)
            return None

    async def _decrypt_data(self, cache_key: str, serialized_data: bytes) -> bytes | None:
        """Decrypt serialized data."""
        try:
            return await self._crypto.decrypt(serialized_data)
        except DaprCryptoError as e:
            logger.error(f"Decryption failed for key '{cache_key}': {e}")
            self._record_cache_error(cache_key, e)
            return None

    async def _deserialize_data(self, cache_key: str, decrypted_data: bytes) -> Any | None:
        """Deserialize decrypted data."""
        try:
            return self._serializer.deserialize(decrypted_data)
        except Exception as e:
            logger.error(f"Deserialization failed for key '{cache_key}': {e}")
            self._record_cache_error(cache_key, e)
            return None

    def _record_cache_hit(self, cache_key: str, start_time: float) -> None:
        """Record cache hit metrics."""
        if self._hooks:
            latency = time.time() - start_time
            self._hooks.on_cache_hit(cache_key, latency)

    def _record_cache_miss(self, cache_key: str, start_time: float) -> None:
        """Record cache miss metrics."""
        if self._hooks:
            latency = time.time() - start_time
            self._hooks.on_cache_miss(cache_key, latency)

    def _record_cache_error(self, cache_key: str, error: Exception) -> None:
        """Record cache error metrics."""
        if self._hooks:
            self._hooks.on_cache_error(cache_key, error)


class CacheSetOperationHandler:
    """Handles cache set operations with proper separation of concerns."""

    def __init__(
        self,
        serializer: Serializer,
        crypto: CryptoIntegration | NoOpCryptoIntegration,
        hooks: ObservabilityHooks | None = None,
    ) -> None:
        """Initialize set operation handler.

        Args:
            serializer: Data serializer for serialization
            crypto: Crypto integration for encryption
            hooks: Optional observability hooks
        """
        self._serializer = serializer
        self._crypto = crypto
        self._hooks = hooks

    async def prepare_data_for_storage(self, cache_key: str, value: Any) -> bytes | None:
        """Prepare data for storage (serialize + encrypt).

        Args:
            cache_key: Cache key for error reporting
            value: Value to prepare for storage

        Returns:
            Prepared data bytes or None if preparation fails
        """
        try:
            # Serialize value
            serialized_data = await self._serialize_data(cache_key, value)
            if serialized_data is None:
                return None

            # Encrypt data
            encrypted_data = await self._encrypt_data(cache_key, serialized_data)
            return encrypted_data

        except Exception as e:
            logger.error(f"Data preparation failed for key '{cache_key}': {e}")
            self._record_cache_error(cache_key, e)
            return None

    async def _serialize_data(self, cache_key: str, value: Any) -> bytes | None:
        """Serialize value to bytes."""
        try:
            return self._serializer.serialize(value)
        except Exception as e:
            logger.error(f"Serialization failed for key '{cache_key}': {e}")
            self._record_cache_error(cache_key, e)
            return None

    async def _encrypt_data(self, cache_key: str, serialized_data: bytes) -> bytes:
        """Encrypt serialized data."""
        try:
            return await self._crypto.encrypt(serialized_data)
        except DaprCryptoError as e:
            logger.warning(f"Encryption failed for key '{cache_key}': {e}. Storing data in plaintext.")
            self._record_cache_error(cache_key, e)
            # Continue with plaintext data
            return serialized_data

    def record_cache_write(self, cache_key: str, data_size: int) -> None:
        """Record cache write metrics."""
        if self._hooks:
            self._hooks.on_cache_write(cache_key, data_size)

    def _record_cache_error(self, cache_key: str, error: Exception) -> None:
        """Record cache error metrics."""
        if self._hooks:
            self._hooks.on_cache_error(cache_key, error)


class CacheHealthChecker:
    """Handles cache service health checking operations."""

    def __init__(
        self,
        store_name: str,
        key_prefix: str,
        serializer: Serializer,
        crypto: CryptoIntegration | NoOpCryptoIntegration,
    ) -> None:
        """Initialize health checker.

        Args:
            store_name: Dapr store name for reporting
            key_prefix: Cache key prefix for reporting
            serializer: Serializer to test
            crypto: Crypto integration to test
        """
        self._store_name = store_name
        self._key_prefix = key_prefix
        self._serializer = serializer
        self._crypto = crypto

    async def check_component_health(self) -> dict[str, Any]:
        """Check health of all cache components.

        Returns:
            Health status dictionary with component details
        """
        from .constants import HEALTH_STATUS_HEALTHY

        health_status = {
            "service": HEALTH_STATUS_HEALTHY,
            "store_name": self._store_name,
            "key_prefix": self._key_prefix,
            "components": {},
        }

        # Check individual components
        self._check_backend_health(health_status)
        await self._check_crypto_health(health_status)
        self._check_serializer_health(health_status)

        return health_status

    def _check_backend_health(self, health_status: dict[str, Any]) -> None:
        """Check backend component health."""
        from .constants import HEALTH_STATUS_HEALTHY

        try:
            health_status["components"]["backend"] = HEALTH_STATUS_HEALTHY
        except Exception as e:
            health_status["components"]["backend"] = f"unhealthy: {e}"
            health_status["service"] = "degraded"

    async def _check_crypto_health(self, health_status: dict[str, Any]) -> None:
        """Check crypto component health."""
        from .constants import HEALTH_STATUS_DISABLED, HEALTH_STATUS_HEALTHY

        try:
            crypto_available = await self._crypto.is_available()
            health_status["components"]["crypto"] = (
                HEALTH_STATUS_HEALTHY if crypto_available else HEALTH_STATUS_DISABLED
            )
        except Exception as e:
            health_status["components"]["crypto"] = f"unhealthy: {e}"

    def _check_serializer_health(self, health_status: dict[str, Any]) -> None:
        """Check serializer component health."""
        from .constants import HEALTH_CHECK_TEST_DATA, HEALTH_STATUS_DEGRADED, HEALTH_STATUS_HEALTHY

        try:
            serialized = self._serializer.serialize(HEALTH_CHECK_TEST_DATA)
            deserialized = self._serializer.deserialize(serialized)

            if deserialized == HEALTH_CHECK_TEST_DATA:
                health_status["components"]["serializer"] = HEALTH_STATUS_HEALTHY
            else:
                health_status["components"]["serializer"] = "unhealthy: data mismatch"
                health_status["service"] = HEALTH_STATUS_DEGRADED

        except Exception as e:
            health_status["components"]["serializer"] = f"unhealthy: {e}"
            health_status["service"] = HEALTH_STATUS_DEGRADED
