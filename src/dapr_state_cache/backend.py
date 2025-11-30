"""Backend para comunicação com Dapr State Store via API HTTP do sidecar."""

import asyncio
import base64
import logging
import os
from threading import Lock
from typing import Any

import httpx

from .exceptions import CacheConnectionError, CacheKeyError

logger = logging.getLogger(__name__)

# Configuração do sidecar Dapr
DEFAULT_DAPR_HTTP_PORT = 3500
DEFAULT_TIMEOUT_SECONDS = 5.0


def _get_dapr_url() -> str:
    """Obtém a URL base do sidecar Dapr."""
    host = os.getenv("DAPR_HTTP_HOST", "127.0.0.1")
    port = os.getenv("DAPR_HTTP_PORT", str(DEFAULT_DAPR_HTTP_PORT))
    return f"http://{host}:{port}"


class DaprStateBackend:
    """Backend para Dapr State Store usando API HTTP direta.

    Usa httpx para comunicação HTTP com o sidecar Dapr, oferecendo
    métodos sync e async com a mesma interface.

    A API REST do Dapr State é simples:
    - GET /v1.0/state/{storename}/{key} - buscar valor
    - POST /v1.0/state/{storename} - salvar valor(es)
    - DELETE /v1.0/state/{storename}/{key} - deletar valor

    Attributes:
        store_name: Nome do state store configurado no Dapr
        timeout: Timeout para operações HTTP em segundos
    """

    def __init__(
        self,
        store_name: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        dapr_url: str | None = None,
    ) -> None:
        """Inicializa o backend.

        Args:
            store_name: Nome do state store Dapr
            timeout: Timeout para operações HTTP
            dapr_url: URL do sidecar (usa env vars se não fornecido)

        Raises:
            CacheKeyError: Se store_name for vazio
        """
        if not store_name:
            raise CacheKeyError("store_name não pode ser vazio")

        self._store_name = store_name
        self._timeout = timeout
        self._base_url = dapr_url or _get_dapr_url()

        # Clientes são criados sob demanda para melhor gerenciamento de recursos
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

        # Locks para thread-safety na criação de clientes
        self._sync_client_lock = Lock()
        # asyncio.Lock é criado lazy para evitar "no current event loop" em Python 3.10+
        # quando a classe é instanciada antes de um event loop existir (ex: tempo de decorator)
        self._async_client_lock: asyncio.Lock | None = None

    @property
    def store_name(self) -> str:
        """Nome do state store."""
        return self._store_name

    def _get_sync_client(self) -> httpx.Client:
        """Obtém ou cria cliente HTTP síncrono (thread-safe).

        Usa double-checked locking para evitar race conditions.
        """
        if self._sync_client is None:
            with self._sync_client_lock:
                if self._sync_client is None:
                    self._sync_client = httpx.Client(
                        base_url=self._base_url,
                        timeout=self._timeout,
                    )
        return self._sync_client

    def _get_async_lock(self) -> asyncio.Lock:
        """Obtém ou cria lock assíncrono (lazy init).

        Cria o asyncio.Lock na primeira chamada async, quando já existe
        um event loop ativo. Evita RuntimeError em Python 3.10+ quando
        a classe é instanciada antes de um event loop existir.
        """
        if self._async_client_lock is None:
            self._async_client_lock = asyncio.Lock()
        return self._async_client_lock

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Obtém ou cria cliente HTTP assíncrono (async-safe).

        Usa double-checked locking com asyncio.Lock para não bloquear o event loop.
        """
        if self._async_client is None:
            async with self._get_async_lock():
                if self._async_client is None:
                    self._async_client = httpx.AsyncClient(
                        base_url=self._base_url,
                        timeout=self._timeout,
                    )
        return self._async_client

    def _state_url(self, key: str | None = None) -> str:
        """Constrói URL para operações de state."""
        if key:
            return f"/v1.0/state/{self._store_name}/{key}"
        return f"/v1.0/state/{self._store_name}"

    def _encode_value(self, value: bytes) -> str:
        """Codifica valor em base64 para envio via JSON."""
        return base64.b64encode(value).decode("ascii")

    def _decode_value(self, data: Any) -> bytes | None:
        """Decodifica valor recebido do Dapr."""
        if data is None:
            return None
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            try:
                return base64.b64decode(data)
            except Exception:
                return data.encode("utf-8")
        return None

    # ========== Métodos Síncronos ==========

    def get(self, key: str) -> bytes | None:
        """Busca valor do cache (síncrono).

        Args:
            key: Chave do cache

        Returns:
            Valor em bytes ou None se não encontrado

        Raises:
            CacheConnectionError: Se não conseguir conectar ao sidecar
        """
        if not key:
            raise CacheKeyError("Chave não pode ser vazia", key=key)

        try:
            client = self._get_sync_client()
            response = client.get(self._state_url(key))

            if response.status_code == 204 or not response.content:
                logger.debug(f"Cache miss para chave: {key}")
                return None

            if response.status_code == 200:
                logger.debug(f"Cache hit para chave: {key}")
                # Dapr retorna o valor como string (base64 encoded)
                try:
                    value_str = response.content.decode("utf-8")
                    return self._decode_value(value_str)
                except UnicodeDecodeError as e:
                    logger.warning(f"Erro ao decodificar resposta para chave {key}: {e}")
                    return None

            logger.warning(f"Resposta inesperada do Dapr: {response.status_code}")
            return None

        except httpx.ConnectError as e:
            raise CacheConnectionError(f"Não foi possível conectar ao sidecar Dapr: {e}", key=key) from e
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout ao buscar chave {key}: {e}")
            return None

    def set(self, key: str, value: bytes, ttl_seconds: int) -> bool:
        """Armazena valor no cache (síncrono).

        Args:
            key: Chave do cache
            value: Valor em bytes
            ttl_seconds: Tempo de vida em segundos

        Returns:
            True se armazenado com sucesso

        Raises:
            CacheConnectionError: Se não conseguir conectar ao sidecar
        """
        if not key:
            raise CacheKeyError("Chave não pode ser vazia", key=key)

        try:
            client = self._get_sync_client()
            payload = [
                {
                    "key": key,
                    "value": self._encode_value(value),
                    "metadata": {"ttlInSeconds": str(ttl_seconds)},
                }
            ]
            response = client.post(self._state_url(), json=payload)

            if response.status_code in (200, 201, 204):
                logger.debug(f"Cache set para chave: {key}, TTL: {ttl_seconds}s")
                return True

            logger.warning(f"Falha ao salvar cache: {response.status_code}")
            return False

        except httpx.ConnectError as e:
            raise CacheConnectionError(f"Não foi possível conectar ao sidecar Dapr: {e}", key=key) from e
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout ao salvar chave {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Remove valor do cache (síncrono).

        Args:
            key: Chave do cache

        Returns:
            True se removido com sucesso
        """
        if not key:
            return False

        try:
            client = self._get_sync_client()
            response = client.delete(self._state_url(key))
            success = response.status_code in (200, 204)
            if success:
                logger.debug(f"Cache delete para chave: {key}")
            return success

        except httpx.HTTPError as e:
            logger.warning(f"Erro ao deletar chave {key}: {e}")
            return False

    # ========== Métodos Assíncronos ==========

    async def get_async(self, key: str) -> bytes | None:
        """Busca valor do cache (assíncrono).

        Args:
            key: Chave do cache

        Returns:
            Valor em bytes ou None se não encontrado

        Raises:
            CacheConnectionError: Se não conseguir conectar ao sidecar
        """
        if not key:
            raise CacheKeyError("Chave não pode ser vazia", key=key)

        try:
            client = await self._get_async_client()
            response = await client.get(self._state_url(key))

            if response.status_code == 204 or not response.content:
                logger.debug(f"Cache miss para chave: {key}")
                return None

            if response.status_code == 200:
                logger.debug(f"Cache hit para chave: {key}")
                # Dapr retorna o valor como string (base64 encoded)
                try:
                    value_str = response.content.decode("utf-8")
                    return self._decode_value(value_str)
                except UnicodeDecodeError as e:
                    logger.warning(f"Erro ao decodificar resposta para chave {key}: {e}")
                    return None

            logger.warning(f"Resposta inesperada do Dapr: {response.status_code}")
            return None

        except httpx.ConnectError as e:
            raise CacheConnectionError(f"Não foi possível conectar ao sidecar Dapr: {e}", key=key) from e
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout ao buscar chave {key}: {e}")
            return None

    async def set_async(self, key: str, value: bytes, ttl_seconds: int) -> bool:
        """Armazena valor no cache (assíncrono).

        Args:
            key: Chave do cache
            value: Valor em bytes
            ttl_seconds: Tempo de vida em segundos

        Returns:
            True se armazenado com sucesso

        Raises:
            CacheConnectionError: Se não conseguir conectar ao sidecar
        """
        if not key:
            raise CacheKeyError("Chave não pode ser vazia", key=key)

        try:
            client = await self._get_async_client()
            payload = [
                {
                    "key": key,
                    "value": self._encode_value(value),
                    "metadata": {"ttlInSeconds": str(ttl_seconds)},
                }
            ]
            response = await client.post(self._state_url(), json=payload)

            if response.status_code in (200, 201, 204):
                logger.debug(f"Cache set para chave: {key}, TTL: {ttl_seconds}s")
                return True

            logger.warning(f"Falha ao salvar cache: {response.status_code}")
            return False

        except httpx.ConnectError as e:
            raise CacheConnectionError(f"Não foi possível conectar ao sidecar Dapr: {e}", key=key) from e
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout ao salvar chave {key}: {e}")
            return False

    async def delete_async(self, key: str) -> bool:
        """Remove valor do cache (assíncrono).

        Args:
            key: Chave do cache

        Returns:
            True se removido com sucesso
        """
        if not key:
            return False

        try:
            client = await self._get_async_client()
            response = await client.delete(self._state_url(key))
            success = response.status_code in (200, 204)
            if success:
                logger.debug(f"Cache delete para chave: {key}")
            return success

        except httpx.HTTPError as e:
            logger.warning(f"Erro ao deletar chave {key}: {e}")
            return False

    # ========== Gerenciamento de Recursos ==========

    def close(self) -> None:
        """Fecha clientes HTTP síncronos."""
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        """Fecha clientes HTTP assíncronos."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def __enter__(self) -> "DaprStateBackend":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    async def __aenter__(self) -> "DaprStateBackend":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
