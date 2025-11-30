"""Decorator @cacheable para cache transparente."""

import inspect
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, overload

from .backend import DaprStateBackend
from .deduplication import DeduplicationManager
from .key_builder import DefaultKeyBuilder
from .protocols import KeyBuilder
from .metrics import CacheMetrics, NoOpMetrics
from .serializer import MsgPackSerializer, Serializer

logger = logging.getLogger(__name__)

# Valores padrão
DEFAULT_STORE_NAME = "cache"
DEFAULT_TTL_SECONDS = 3600
DEFAULT_KEY_PREFIX = "cache"


class CacheableWrapper:
    """Wrapper para funções decoradas com @cacheable.

    Detecta automaticamente se a função é sync ou async e usa
    o modo apropriado do backend.

    Implementa o descriptor protocol para suportar métodos de instância.

    Attributes:
        func: Função original
        backend: Backend de storage
        serializer: Serializer de dados
        key_builder: Construtor de chaves
        ttl_seconds: TTL padrão
        metrics: Coletor de métricas
    """

    def __init__(
        self,
        func: Callable[..., Any],
        backend: DaprStateBackend,
        serializer: Serializer,
        key_builder: KeyBuilder,
        ttl_seconds: int,
        metrics: CacheMetrics | NoOpMetrics,
        deduplication: DeduplicationManager | None = None,
    ) -> None:
        self._func = func
        self._backend = backend
        self._serializer = serializer
        self._key_builder = key_builder
        self._ttl_seconds = ttl_seconds
        self._metrics = metrics
        self._deduplication = deduplication or DeduplicationManager()
        self._is_async = inspect.iscoroutinefunction(func)

        # Preserva metadados da função original
        wraps(func)(self)

    def __get__(self, obj: Any, _objtype: type | None = None) -> "CacheableWrapper | BoundCacheableMethod":
        """Descriptor protocol para suporte a métodos."""
        if obj is None:
            return self
        return BoundCacheableMethod(self, obj)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Executa a função com cache."""
        if self._is_async:
            return self._call_async(*args, **kwargs)
        return self._call_sync(*args, **kwargs)

    def _call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Execução síncrona com cache."""
        cache_key = self._key_builder.build_key(self._func, args, kwargs)
        start_time = time.perf_counter()
        cache_error_occurred = False

        # Tenta buscar do cache
        try:
            cached_data = self._backend.get(cache_key)
            if cached_data is not None:
                result = self._serializer.deserialize(cached_data)
                latency = time.perf_counter() - start_time
                self._metrics.record_hit(cache_key, latency)
                logger.debug(f"Cache hit: {cache_key}")
                return result
        except Exception as e:
            logger.warning(f"Erro ao buscar cache: {e}")
            self._metrics.record_error(cache_key, e)
            cache_error_occurred = True

        # Cache miss - executa função (só registra miss se não houve erro)
        latency = time.perf_counter() - start_time
        if not cache_error_occurred:
            self._metrics.record_miss(cache_key, latency)
            logger.debug(f"Cache miss: {cache_key}")

        result = self._func(*args, **kwargs)

        # Armazena no cache
        try:
            serialized = self._serializer.serialize(result)
            self._backend.set(cache_key, serialized, self._ttl_seconds)
            self._metrics.record_write(cache_key, len(serialized))
        except Exception as e:
            logger.warning(f"Erro ao salvar cache: {e}")
            self._metrics.record_error(cache_key, e)

        return result

    async def _call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Execução assíncrona com cache e deduplicação."""
        cache_key = self._key_builder.build_key(self._func, args, kwargs)
        start_time = time.perf_counter()
        cache_error_occurred = False

        # Tenta buscar do cache
        try:
            cached_data = await self._backend.get_async(cache_key)
            if cached_data is not None:
                result = self._serializer.deserialize(cached_data)
                latency = time.perf_counter() - start_time
                self._metrics.record_hit(cache_key, latency)
                logger.debug(f"Cache hit: {cache_key}")
                return result
        except Exception as e:
            logger.warning(f"Erro ao buscar cache: {e}")
            self._metrics.record_error(cache_key, e)
            cache_error_occurred = True

        # Cache miss - executa com deduplicação (só registra miss se não houve erro)
        latency = time.perf_counter() - start_time
        if not cache_error_occurred:
            self._metrics.record_miss(cache_key, latency)
            logger.debug(f"Cache miss: {cache_key}")

        # Captura func localmente para type checker
        func = self._func

        async def compute_and_cache() -> Any:
            result = await func(*args, **kwargs)  # type: ignore[misc]

            # Armazena no cache
            try:
                serialized = self._serializer.serialize(result)
                await self._backend.set_async(cache_key, serialized, self._ttl_seconds)
                self._metrics.record_write(cache_key, len(serialized))
            except Exception as e:
                logger.warning(f"Erro ao salvar cache: {e}")
                self._metrics.record_error(cache_key, e)

            return result

        return await self._deduplication.deduplicate(cache_key, compute_and_cache)

    def invalidate(self, *args: Any, **kwargs: Any) -> bool:
        """Invalida entrada de cache para os argumentos especificados (sync)."""
        cache_key = self._key_builder.build_key(self._func, args, kwargs)
        return self._backend.delete(cache_key)

    async def invalidate_async(self, *args: Any, **kwargs: Any) -> bool:
        """Invalida entrada de cache para os argumentos especificados (async)."""
        cache_key = self._key_builder.build_key(self._func, args, kwargs)
        return await self._backend.delete_async(cache_key)


class BoundCacheableMethod:
    """Wrapper para métodos bound (com self/cls)."""

    def __init__(self, wrapper: CacheableWrapper, instance: Any) -> None:
        self._wrapper = wrapper
        self._instance = instance

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Executa o método com o instance bound."""
        return self._wrapper(self._instance, *args, **kwargs)

    def invalidate(self, *args: Any, **kwargs: Any) -> bool:
        """Invalida cache para este método (sync)."""
        return self._wrapper.invalidate(self._instance, *args, **kwargs)

    async def invalidate_async(self, *args: Any, **kwargs: Any) -> bool:
        """Invalida cache para este método (async)."""
        return await self._wrapper.invalidate_async(self._instance, *args, **kwargs)


# Cache de backends por store_name para reutilização (thread-safe via setdefault)
_backends: dict[str, DaprStateBackend] = {}


def _get_backend(store_name: str) -> DaprStateBackend:
    """Obtém ou cria backend para o store (thread-safe).

    Usa setdefault() que é atômico em CPython para evitar race conditions.
    """
    backend = _backends.get(store_name)
    if backend is None:
        backend = _backends.setdefault(store_name, DaprStateBackend(store_name))
    return backend


@overload
def cacheable(func: Callable[..., Any]) -> CacheableWrapper: ...


@overload
def cacheable(
    *,
    store_name: str = DEFAULT_STORE_NAME,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    key_prefix: str = DEFAULT_KEY_PREFIX,
    key_builder: KeyBuilder | None = None,
    serializer: Serializer | None = None,
    metrics: CacheMetrics | NoOpMetrics | None = None,
) -> Callable[[Callable[..., Any]], CacheableWrapper]: ...


def cacheable(
    func: Callable[..., Any] | None = None,
    *,
    store_name: str = DEFAULT_STORE_NAME,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    key_prefix: str = DEFAULT_KEY_PREFIX,
    key_builder: KeyBuilder | None = None,
    serializer: Serializer | None = None,
    metrics: CacheMetrics | NoOpMetrics | None = None,
) -> CacheableWrapper | Callable[[Callable[..., Any]], CacheableWrapper]:
    """Decorator para adicionar cache transparente a funções.

    Funciona com funções síncronas e assíncronas, detectando
    automaticamente o tipo e usando o modo apropriado.

    Args:
        func: Função a decorar (quando usado sem parênteses)
        store_name: Nome do state store Dapr (default: "cache")
        ttl_seconds: Tempo de vida do cache em segundos (default: 3600)
        key_prefix: Prefixo para chaves de cache (default: "cache")
        key_builder: Construtor de chaves customizado
        serializer: Serializer customizado (default: MsgPackSerializer)
        metrics: Coletor de métricas (default: NoOpMetrics)

    Returns:
        Função decorada com cache

    Example:
        ```python
        # Uso simples
        @cacheable
        def get_user(user_id: int) -> dict:
            return db.query(user_id)

        # Com configuração
        @cacheable(store_name="users", ttl_seconds=300)
        async def get_user_async(user_id: int) -> dict:
            return await db.query(user_id)

        # Invalidação
        get_user.invalidate(user_id=123)
        await get_user_async.invalidate_async(user_id=456)
        ```
    """

    def decorator(fn: Callable[..., Any]) -> CacheableWrapper:
        backend = _get_backend(store_name)
        actual_serializer = serializer or MsgPackSerializer()
        actual_key_builder = key_builder or DefaultKeyBuilder(prefix=key_prefix)
        actual_metrics = metrics or NoOpMetrics()

        return CacheableWrapper(
            func=fn,
            backend=backend,
            serializer=actual_serializer,
            key_builder=actual_key_builder,
            ttl_seconds=ttl_seconds,
            metrics=actual_metrics,
        )

    if func is not None:
        # Usado sem parênteses: @cacheable
        return decorator(func)

    # Usado com parênteses: @cacheable(...)
    return decorator
