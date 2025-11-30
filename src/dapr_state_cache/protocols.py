"""Protocols para extensibilidade da biblioteca.

Define interfaces que permitem implementações customizadas de:
- KeyBuilder: Geração de chaves de cache
- Serializer: Serialização/deserialização de dados
- CacheMetrics: Coleta de métricas
"""

from collections.abc import Callable
from typing import Any, Protocol


class KeyBuilder(Protocol):
    """Protocol para construtores de chaves de cache.

    Implemente este protocol para customizar como as chaves
    de cache são geradas a partir de funções e argumentos.

    Example:
        ```python
        class MyKeyBuilder:
            def build_key(self, func, args, kwargs) -> str:
                return f"my-prefix:{func.__name__}:{hash(args)}"
        ```
    """

    def build_key(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str:
        """Constrói chave de cache.

        Args:
            func: Função decorada
            args: Argumentos posicionais
            kwargs: Argumentos nomeados

        Returns:
            Chave de cache como string
        """
        ...


class Serializer(Protocol):
    """Protocol para serialização de dados.

    Implemente este protocol para usar formatos de serialização
    customizados (JSON, Protocol Buffers, etc.).

    Example:
        ```python
        import json

        class JsonSerializer:
            def serialize(self, data: Any) -> bytes:
                return json.dumps(data).encode()

            def deserialize(self, data: bytes) -> Any:
                return json.loads(data.decode())
        ```
    """

    def serialize(self, data: Any) -> bytes:
        """Serializa dados Python para bytes.

        Args:
            data: Dados a serializar

        Returns:
            Dados serializados em bytes

        Raises:
            Exception: Se falhar ao serializar
        """
        ...

    def deserialize(self, data: bytes) -> Any:
        """Deserializa bytes para dados Python.

        Args:
            data: Bytes a deserializar

        Returns:
            Dados Python deserializados

        Raises:
            Exception: Se falhar ao deserializar
        """
        ...


class CacheMetrics(Protocol):
    """Protocol para coleta de métricas de cache.

    Implemente este protocol para integrar com sistemas
    de monitoramento customizados.

    Example:
        ```python
        class PrometheusMetrics:
            def record_hit(self, key: str, latency: float) -> None:
                cache_hits_total.labels(key=key).inc()
                cache_latency.labels(operation="hit").observe(latency)
        ```
    """

    def record_hit(self, key: str, latency: float) -> None:
        """Registra cache hit.

        Args:
            key: Chave do cache
            latency: Latência da operação em segundos
        """
        ...

    def record_miss(self, key: str, latency: float) -> None:
        """Registra cache miss.

        Args:
            key: Chave do cache
            latency: Latência da operação em segundos
        """
        ...

    def record_write(self, key: str, size: int) -> None:
        """Registra escrita no cache.

        Args:
            key: Chave do cache
            size: Tamanho dos dados em bytes
        """
        ...

    def record_error(self, key: str, error: Exception) -> None:
        """Registra erro de cache.

        Args:
            key: Chave do cache
            error: Exceção que ocorreu
        """
        ...
