"""
Core cache service components.

This module provides the main cache service facade and related components
including cryptography integration and service creation utilities.
"""

from . import constants
from .cache_operations import (
    CacheGetOperationHandler,
    CacheHealthChecker,
    CacheSetOperationHandler,
)
from .cache_orchestrator import (
    CacheOrchestrationTimeout,
    CacheOrchestrator,
    NoOpDeduplicationManager,
    OrchestrationError,
    create_cache_orchestrator,
)
from .cache_service import (
    CacheService,
    create_cache_service,
)
from .crypto_integration import (
    CryptoIntegration,
    DaprCryptoError,
    NoOpCryptoIntegration,
    create_crypto_integration,
)
from .sync_async_bridge import (
    SyncAsyncBridge,
    execute_auto,
    execute_auto_sync,
    get_default_bridge,
    get_thread_pool,
    is_async_context,
    shutdown_thread_pool,
    wrap_for_async_context,
    wrap_for_sync_context,
)
from .validators import (
    ValidationError,
    validate_cache_parameters,
    validate_crypto_component_name,
    validate_invalidation_parameters,
    validate_key_prefix,
    validate_store_name,
    validate_ttl_seconds,
)

__all__ = [
    # Cache service
    "CacheService",
    "create_cache_service",
    # Crypto integration
    "CryptoIntegration",
    "NoOpCryptoIntegration",
    "DaprCryptoError",
    "create_crypto_integration",
    # Sync/Async bridge
    "SyncAsyncBridge",
    "get_thread_pool",
    "shutdown_thread_pool",
    "get_default_bridge",
    "execute_auto",
    "execute_auto_sync",
    "is_async_context",
    "wrap_for_sync_context",
    "wrap_for_async_context",
    # Cache orchestrator
    "CacheOrchestrator",
    "OrchestrationError",
    "CacheOrchestrationTimeout",
    "create_cache_orchestrator",
    "NoOpDeduplicationManager",
    # Parameter validators
    "ValidationError",
    "validate_ttl_seconds",
    "validate_store_name",
    "validate_key_prefix",
    "validate_crypto_component_name",
    "validate_cache_parameters",
    "validate_invalidation_parameters",
    # Cache operation handlers
    "CacheGetOperationHandler",
    "CacheSetOperationHandler",
    "CacheHealthChecker",
    # Constants module
    "constants",
]
