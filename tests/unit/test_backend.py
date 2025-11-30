"""Testes para o backend Dapr State."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from dapr_state_cache.backend import DaprStateBackend, _get_dapr_url
from dapr_state_cache.exceptions import CacheConnectionError, CacheKeyError


class TestGetDaprUrl:
    """Testes para _get_dapr_url."""

    def test_default_url(self) -> None:
        """Deve retornar URL padrão."""
        with patch.dict("os.environ", {}, clear=True):
            url = _get_dapr_url()
            assert url == "http://127.0.0.1:3500"

    def test_custom_host_and_port(self) -> None:
        """Deve usar variáveis de ambiente."""
        with patch.dict("os.environ", {"DAPR_HTTP_HOST": "custom", "DAPR_HTTP_PORT": "3501"}):
            url = _get_dapr_url()
            assert url == "http://custom:3501"


class TestDaprStateBackend:
    """Testes para DaprStateBackend."""

    def test_init_with_store_name(self) -> None:
        """Deve inicializar com nome do store."""
        backend = DaprStateBackend("my-store")
        assert backend.store_name == "my-store"

    def test_init_empty_store_name_raises_error(self) -> None:
        """Deve lançar erro com store_name vazio."""
        with pytest.raises(CacheKeyError):
            DaprStateBackend("")

    def test_init_with_custom_timeout(self) -> None:
        """Deve aceitar timeout customizado."""
        backend = DaprStateBackend("store", timeout=10.0)
        assert backend._timeout == 10.0

    def test_init_with_custom_url(self) -> None:
        """Deve aceitar URL customizada."""
        backend = DaprStateBackend("store", dapr_url="http://custom:3501")
        assert backend._base_url == "http://custom:3501"

    def test_state_url_without_key(self) -> None:
        """Deve construir URL sem chave."""
        backend = DaprStateBackend("mystore")
        url = backend._state_url()
        assert url == "/v1.0/state/mystore"

    def test_state_url_with_key(self) -> None:
        """Deve construir URL com chave."""
        backend = DaprStateBackend("mystore")
        url = backend._state_url("mykey")
        assert url == "/v1.0/state/mystore/mykey"

    def test_encode_value(self) -> None:
        """Deve codificar valor em base64."""
        backend = DaprStateBackend("store")
        encoded = backend._encode_value(b"hello")
        assert encoded == "aGVsbG8="

    def test_decode_value_from_bytes(self) -> None:
        """Deve decodificar bytes diretamente."""
        backend = DaprStateBackend("store")
        result = backend._decode_value(b"hello")
        assert result == b"hello"

    def test_decode_value_from_base64_string(self) -> None:
        """Deve decodificar string base64."""
        backend = DaprStateBackend("store")
        result = backend._decode_value("aGVsbG8=")
        assert result == b"hello"

    def test_decode_value_none(self) -> None:
        """Deve retornar None para valor None."""
        backend = DaprStateBackend("store")
        result = backend._decode_value(None)
        assert result is None

    def test_get_empty_key_raises_error(self) -> None:
        """Deve lançar erro para chave vazia no get."""
        backend = DaprStateBackend("store")
        with pytest.raises(CacheKeyError):
            backend.get("")

    def test_set_empty_key_raises_error(self) -> None:
        """Deve lançar erro para chave vazia no set."""
        backend = DaprStateBackend("store")
        with pytest.raises(CacheKeyError):
            backend.set("", b"value", 3600)

    def test_delete_empty_key_returns_false(self) -> None:
        """Deve retornar False para chave vazia no delete."""
        backend = DaprStateBackend("store")
        result = backend.delete("")
        assert result is False

    def test_context_manager_sync(self) -> None:
        """Deve funcionar como context manager síncrono."""
        with DaprStateBackend("store") as backend:
            assert backend.store_name == "store"

    @pytest.mark.asyncio
    async def test_context_manager_async(self) -> None:
        """Deve funcionar como context manager assíncrono."""
        async with DaprStateBackend("store") as backend:
            assert backend.store_name == "store"

    @pytest.mark.asyncio
    async def test_get_async_empty_key_raises_error(self) -> None:
        """Deve lançar erro para chave vazia no get_async."""
        backend = DaprStateBackend("store")
        with pytest.raises(CacheKeyError):
            await backend.get_async("")

    @pytest.mark.asyncio
    async def test_set_async_empty_key_raises_error(self) -> None:
        """Deve lançar erro para chave vazia no set_async."""
        backend = DaprStateBackend("store")
        with pytest.raises(CacheKeyError):
            await backend.set_async("", b"value", 3600)

    @pytest.mark.asyncio
    async def test_delete_async_empty_key_returns_false(self) -> None:
        """Deve retornar False para chave vazia no delete_async."""
        backend = DaprStateBackend("store")
        result = await backend.delete_async("")
        assert result is False

    def test_decode_value_invalid_base64_returns_utf8(self) -> None:
        """Deve retornar string como UTF-8 se não for base64 válido."""
        backend = DaprStateBackend("store")
        result = backend._decode_value("not-base64!")
        assert result == b"not-base64!"

    def test_decode_value_non_string_non_bytes_returns_none(self) -> None:
        """Deve retornar None para tipos não suportados."""
        backend = DaprStateBackend("store")
        result = backend._decode_value(12345)
        assert result is None


class TestDaprStateBackendHttpSync:
    """Testes para operações HTTP síncronas."""

    def test_get_cache_miss_204(self) -> None:
        """Deve retornar None para status 204."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""

        with patch.object(httpx.Client, "get", return_value=mock_response):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.get("mykey")
            assert result is None

    def test_get_cache_miss_empty_content(self) -> None:
        """Deve retornar None para conteúdo vazio."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b""

        with patch.object(httpx.Client, "get", return_value=mock_response):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.get("mykey")
            assert result is None

    def test_get_cache_hit(self) -> None:
        """Deve retornar valor decodificado para hit."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"aGVsbG8="  # "hello" em base64

        with patch.object(httpx.Client, "get", return_value=mock_response):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.get("mykey")
            assert result == b"hello"

    def test_get_unexpected_status(self) -> None:
        """Deve retornar None para status inesperado."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b"error"

        with patch.object(httpx.Client, "get", return_value=mock_response):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.get("mykey")
            assert result is None

    def test_get_connect_error(self) -> None:
        """Deve lançar CacheConnectionError em erro de conexão."""
        with patch.object(httpx.Client, "get", side_effect=httpx.ConnectError("Connection refused")):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            with pytest.raises(CacheConnectionError):
                backend.get("mykey")

    def test_get_timeout(self) -> None:
        """Deve retornar None em timeout."""
        with patch.object(httpx.Client, "get", side_effect=httpx.TimeoutException("Timeout")):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.get("mykey")
            assert result is None

    def test_get_unicode_decode_error(self) -> None:
        """Deve retornar None em erro de decodificação UTF-8."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\xff\xfe"  # Bytes inválidos UTF-8

        with patch.object(httpx.Client, "get", return_value=mock_response):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.get("mykey")
            assert result is None

    def test_set_success(self) -> None:
        """Deve retornar True para set bem sucedido."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(httpx.Client, "post", return_value=mock_response):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.set("mykey", b"value", 3600)
            assert result is True

    def test_set_failure(self) -> None:
        """Deve retornar False para set falho."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(httpx.Client, "post", return_value=mock_response):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.set("mykey", b"value", 3600)
            assert result is False

    def test_set_connect_error(self) -> None:
        """Deve lançar CacheConnectionError em erro de conexão."""
        with patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("Connection refused")):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            with pytest.raises(CacheConnectionError):
                backend.set("mykey", b"value", 3600)

    def test_set_timeout(self) -> None:
        """Deve retornar False em timeout."""
        with patch.object(httpx.Client, "post", side_effect=httpx.TimeoutException("Timeout")):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.set("mykey", b"value", 3600)
            assert result is False

    def test_delete_success(self) -> None:
        """Deve retornar True para delete bem sucedido."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(httpx.Client, "delete", return_value=mock_response):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.delete("mykey")
            assert result is True

    def test_delete_http_error(self) -> None:
        """Deve retornar False em erro HTTP."""
        with patch.object(httpx.Client, "delete", side_effect=httpx.HTTPError("Error")):
            backend = DaprStateBackend("store", dapr_url="http://test:3500")
            backend._sync_client = httpx.Client(base_url="http://test:3500")
            result = backend.delete("mykey")
            assert result is False

    def test_close_with_client(self) -> None:
        """Deve fechar cliente sync."""
        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = MagicMock()
        backend._sync_client = mock_client
        backend.close()
        mock_client.close.assert_called_once()
        assert backend._sync_client is None

    def test_close_without_client(self) -> None:
        """Deve funcionar mesmo sem cliente."""
        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        backend.close()  # Não deve lançar exceção


class TestDaprStateBackendHttpAsync:
    """Testes para operações HTTP assíncronas."""

    @pytest.mark.asyncio
    async def test_get_async_cache_miss_204(self) -> None:
        """Deve retornar None para status 204."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""

        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        backend._async_client = mock_client

        result = await backend.get_async("mykey")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_async_cache_hit(self) -> None:
        """Deve retornar valor decodificado para hit."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"aGVsbG8="  # "hello" em base64

        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        backend._async_client = mock_client

        result = await backend.get_async("mykey")
        assert result == b"hello"

    @pytest.mark.asyncio
    async def test_get_async_unexpected_status(self) -> None:
        """Deve retornar None para status inesperado."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b"error"

        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        backend._async_client = mock_client

        result = await backend.get_async("mykey")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_async_connect_error(self) -> None:
        """Deve lançar CacheConnectionError em erro de conexão."""
        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        backend._async_client = mock_client

        with pytest.raises(CacheConnectionError):
            await backend.get_async("mykey")

    @pytest.mark.asyncio
    async def test_get_async_timeout(self) -> None:
        """Deve retornar None em timeout."""
        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        backend._async_client = mock_client

        result = await backend.get_async("mykey")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_async_unicode_decode_error(self) -> None:
        """Deve retornar None em erro de decodificação UTF-8."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\xff\xfe"  # Bytes inválidos UTF-8

        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        backend._async_client = mock_client

        result = await backend.get_async("mykey")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_async_success(self) -> None:
        """Deve retornar True para set bem sucedido."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        backend._async_client = mock_client

        result = await backend.set_async("mykey", b"value", 3600)
        assert result is True

    @pytest.mark.asyncio
    async def test_set_async_failure(self) -> None:
        """Deve retornar False para set falho."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        backend._async_client = mock_client

        result = await backend.set_async("mykey", b"value", 3600)
        assert result is False

    @pytest.mark.asyncio
    async def test_set_async_connect_error(self) -> None:
        """Deve lançar CacheConnectionError em erro de conexão."""
        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        backend._async_client = mock_client

        with pytest.raises(CacheConnectionError):
            await backend.set_async("mykey", b"value", 3600)

    @pytest.mark.asyncio
    async def test_set_async_timeout(self) -> None:
        """Deve retornar False em timeout."""
        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        backend._async_client = mock_client

        result = await backend.set_async("mykey", b"value", 3600)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_async_success(self) -> None:
        """Deve retornar True para delete bem sucedido."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_response)
        backend._async_client = mock_client

        result = await backend.delete_async("mykey")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_async_http_error(self) -> None:
        """Deve retornar False em erro HTTP."""
        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(side_effect=httpx.HTTPError("Error"))
        backend._async_client = mock_client

        result = await backend.delete_async("mykey")
        assert result is False

    @pytest.mark.asyncio
    async def test_aclose_with_client(self) -> None:
        """Deve fechar cliente async."""
        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        mock_client = AsyncMock()
        backend._async_client = mock_client
        await backend.aclose()
        mock_client.aclose.assert_called_once()
        assert backend._async_client is None

    @pytest.mark.asyncio
    async def test_aclose_without_client(self) -> None:
        """Deve funcionar mesmo sem cliente."""
        backend = DaprStateBackend("store", dapr_url="http://test:3500")
        await backend.aclose()  # Não deve lançar exceção
