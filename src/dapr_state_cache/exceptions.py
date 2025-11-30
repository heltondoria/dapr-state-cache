"""Exceções simplificadas para dapr-state-cache."""


class CacheError(Exception):
    """Erro base para operações de cache."""

    def __init__(self, message: str, key: str | None = None) -> None:
        self.key = key
        super().__init__(message)


class CacheConnectionError(CacheError):
    """Erro de conexão com o sidecar Dapr."""

    pass


class CacheSerializationError(CacheError):
    """Erro de serialização/deserialização de dados."""

    pass


class CacheKeyError(CacheError):
    """Erro relacionado à chave de cache (vazia, inválida, etc.)."""

    pass
