"""dapr-state-cache: Cache transparente para aplicações Dapr.

Biblioteca de cache de alta performance usando Dapr State Store,
com suporte a funções síncronas e assíncronas.

Uso básico:
    ```python
    from dapr_state_cache import cacheable

    @cacheable(store_name="cache", ttl_seconds=300)
    def get_user(user_id: int) -> dict:
        return db.query(user_id)

    @cacheable(store_name="cache", ttl_seconds=300)
    async def get_user_async(user_id: int) -> dict:
        return await db.query(user_id)

    # Invalidação
    get_user.invalidate(user_id=123)
    await get_user_async.invalidate_async(user_id=456)
    ```

Com métricas OpenTelemetry:
    ```python
    from dapr_state_cache import cacheable, OpenTelemetryMetrics

    metrics = OpenTelemetryMetrics()

    @cacheable(store_name="cache", metrics=metrics)
    def my_function():
        pass
    ```
"""

__version__ = "0.5.0"

# Decorator principal
# Backend
from .backend import DaprStateBackend
from .decorator import CacheableWrapper, cacheable

# Deduplicação (uso avançado)
from .deduplication import DeduplicationManager

# Exceções
from .exceptions import (
    CacheConnectionError,
    CacheError,
    CacheKeyError,
    CacheSerializationError,
)

# Geração de chaves
from .key_builder import DefaultKeyBuilder

# Métricas
from .metrics import (
    CacheMetrics,
    CacheStats,
    InMemoryMetrics,
    KeyStats,
    NoOpMetrics,
    OpenTelemetryMetrics,
)

# Protocols (para extensibilidade)
from .protocols import CacheMetrics as CacheMetricsProtocol
from .protocols import KeyBuilder
from .protocols import Serializer as SerializerProtocol

# Serialização
from .serializer import MsgPackSerializer, Serializer

__all__ = [
    # Decorator principal
    "cacheable",
    "CacheableWrapper",
    # Backend
    "DaprStateBackend",
    # Serialização
    "MsgPackSerializer",
    "Serializer",
    # Geração de chaves
    "DefaultKeyBuilder",
    "KeyBuilder",
    # Métricas
    "CacheMetrics",
    "CacheStats",
    "KeyStats",
    "NoOpMetrics",
    "InMemoryMetrics",
    "OpenTelemetryMetrics",
    # Exceções
    "CacheError",
    "CacheConnectionError",
    "CacheSerializationError",
    "CacheKeyError",
    # Deduplicação
    "DeduplicationManager",
    # Protocols
    "SerializerProtocol",
    "CacheMetricsProtocol",
]
