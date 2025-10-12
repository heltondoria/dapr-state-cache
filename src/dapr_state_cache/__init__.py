"""
dapr-state-cache: Enterprise-grade caching library for Dapr applications.

A production-ready, high-performance caching solution built on Dapr State Store
that provides transparent caching for Python applications with comprehensive
observability, security, and extensibility features.

🚀 **Key Features:**
    • **Zero-Configuration**: Works out-of-the-box with sensible defaults
    • **Transparent Caching**: Simple @cacheable decorator for functions/methods
    • **Multi-Backend Support**: Any Dapr-supported state store (Redis, MongoDB, etc.)
    • **High Performance**: Optimized for throughput with minimal overhead
    • **Production Ready**: Comprehensive error handling and observability
    • **Extensible Design**: Pluggable serializers, key builders, and hooks
    • **Security First**: Built-in encryption via Dapr Cryptography
    • **Thread Safe**: Safe for concurrent operations and async applications

🏗️ **Architecture:**
    The library follows a layered architecture with clear separation of concerns:
    
    ```
    @cacheable Decorator          ← Public API
    ├── CacheOrchestrator        ← Orchestration & Flow Control
    ├── CacheService             ← Component Integration Facade
    ├── DaprStateBackend         ← Storage Backend
    ├── Serializers              ← Data Encoding (JSON/MessagePack/Pickle)
    ├── KeyBuilders              ← Cache Key Generation
    ├── ObservabilityHooks       ← Metrics & Monitoring
    └── CryptoIntegration        ← Security & Encryption
    ```

📊 **Observability & Monitoring:**
    Built-in support for comprehensive cache monitoring:
    • Real-time hit/miss ratios and performance metrics
    • Per-key statistics for detailed analysis
    • Integration with monitoring systems (Prometheus, etc.)
    • Distributed tracing via Dapr's observability features
    • Custom hooks for advanced monitoring scenarios

🔐 **Security Features:**
    • Optional encryption via Dapr Cryptography building block
    • Support for Azure Key Vault, AWS KMS, GCP KMS
    • Secure by default with best-effort fallbacks
    • No sensitive data exposure in logs or metrics

⚡ **Quick Start:**
    ```python
    from dapr_state_cache import cacheable
    
    # Basic caching with default settings
    @cacheable(store_name="redis-cache")
    def get_user_profile(user_id: int) -> dict:
        return expensive_database_query(user_id)
    
    # Advanced configuration with encryption and monitoring
    from dapr_state_cache import (
        cacheable, 
        MsgpackSerializer, 
        MetricsCollectorHooks
    )
    
    @cacheable(
        store_name="sensitive-cache",
        ttl_seconds=1800,                    # 30 minutes
        serializer=MsgpackSerializer(),      # Fast binary serialization
        use_dapr_crypto=True,               # Encrypt sensitive data
        crypto_component_name="vault-kms",   # Azure Key Vault
        hooks=MetricsCollectorHooks()        # Auto-collect metrics
    )
    async def get_sensitive_data(user_id: int) -> dict:
        return await fetch_sensitive_user_data(user_id)
    
    # Cache invalidation
    await get_sensitive_data.invalidate(user_id=123)
    get_sensitive_data.invalidate_sync(user_id=456)  # Sync version
    ```

📈 **Performance Characteristics:**
    • **Cache Hits**: Sub-millisecond response times
    • **Cache Misses**: Backend-dependent (typically 1-20ms)
    • **Throughput**: Scales with Dapr state store capacity
    • **Memory**: Minimal overhead, stateless operation
    • **CPU**: Dominated by serialization (~1-5ms typical)

🔧 **Supported State Stores:**
    Works with any Dapr state store that supports TTL:
    • **Redis** (recommended for production)
    • **MongoDB** (document storage)
    • **PostgreSQL** (relational database)
    • **Azure Cosmos DB** (globally distributed)
    • **Memory** (development/testing)
    • **And many more**: https://docs.dapr.io/reference/components-reference/supported-state-stores/

🎯 **Use Cases:**
    • **API Response Caching**: Cache expensive API calls
    • **Database Query Caching**: Reduce database load
    • **Computation Caching**: Cache expensive calculations
    • **Cross-Service Caching**: Share cache between microservices
    • **Session Storage**: Distributed session management
    • **Configuration Caching**: Cache application settings

📚 **Main Components:**
    • `cacheable`: Primary decorator for transparent caching
    • `JsonSerializer`, `MsgpackSerializer`, `PickleSerializer`: Data serializers
    • `CacheStats`, `CacheMetrics`: Performance monitoring
    • `MetricsCollectorHooks`: Automatic metrics collection
    • `DefaultKeyBuilder`: Deterministic cache key generation
    • `DaprStateBackend`: Dapr integration backend

For detailed documentation, examples, and best practices, visit:
https://github.com/your-repo/dapr-state-cache
"""

__version__ = "0.3.2"

# Main interface
from .decorators import cacheable

# Protocols for extensibility
from .protocols import KeyBuilder, Serializer, ObservabilityHooks

# Serializers
from .codecs import (
    JsonSerializer,
    MsgpackSerializer,
    PickleSerializer,
)

# Observability
from .observability import (
    CacheStats,
    CacheMetrics,
    MetricsCollectorHooks,
    DefaultObservabilityHooks,
    SilentObservabilityHooks,
    CompositeObservabilityHooks,
)

# Core components (for advanced usage)
from .core import (
    CacheService,
    CacheOrchestrator,
    create_cache_service,
    create_cache_orchestrator,
)

# Backend and exceptions (for error handling)
from .backend import (
    DaprStateBackend,
    CacheBackendError,
    RecoverableCacheError,
    IrrecoverableCacheError,
    DaprUnavailableError,
    StateStoreNotConfiguredError,
    CacheKeyEmptyError,
    CacheValueEmptyError,
    InvalidTTLValueError,
)

# Key builders
from .keys import DefaultKeyBuilder

# Deduplication (for advanced usage)
from .orchestration import DeduplicationManager

__all__: list[str] = [
    # Main interface
    "cacheable",

    # Protocols for extensibility
    "KeyBuilder",
    "Serializer", 
    "ObservabilityHooks",

    # Serializers
    "JsonSerializer",
    "MsgpackSerializer",
    "PickleSerializer",

    # Observability
    "CacheStats",
    "CacheMetrics",
    "MetricsCollectorHooks",
    "DefaultObservabilityHooks",
    "SilentObservabilityHooks",
    "CompositeObservabilityHooks",

    # Core components (advanced usage)
    "CacheService",
    "CacheOrchestrator", 
    "create_cache_service",
    "create_cache_orchestrator",

    # Backend and exceptions
    "DaprStateBackend",
    "CacheBackendError",
    "RecoverableCacheError",
    "IrrecoverableCacheError",
    "DaprUnavailableError",
    "StateStoreNotConfiguredError",
    "CacheKeyEmptyError",
    "CacheValueEmptyError",
    "InvalidTTLValueError",

    # Key builders
    "DefaultKeyBuilder",

    # Deduplication (advanced usage)
    "DeduplicationManager",
]
