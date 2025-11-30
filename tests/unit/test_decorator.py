"""Testes para o decorator @cacheable."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dapr_state_cache.decorator import CacheableWrapper, cacheable
from dapr_state_cache.metrics import InMemoryMetrics


class TestCacheableDecorator:
    """Testes para o decorator @cacheable."""

    def test_decorator_without_parens(self) -> None:
        """Deve funcionar sem parênteses."""
        with patch("dapr_state_cache.decorator._get_backend") as mock_backend:
            mock_backend.return_value = MagicMock()

            @cacheable
            def my_func(x: int) -> int:
                return x * 2

            assert isinstance(my_func, CacheableWrapper)

    def test_decorator_with_parens(self) -> None:
        """Deve funcionar com parênteses e argumentos."""
        with patch("dapr_state_cache.decorator._get_backend") as mock_backend:
            mock_backend.return_value = MagicMock()

            @cacheable(store_name="custom", ttl_seconds=600)
            def my_func(x: int) -> int:
                return x * 2

            assert isinstance(my_func, CacheableWrapper)

    def test_preserves_function_name(self) -> None:
        """Deve preservar nome da função."""
        with patch("dapr_state_cache.decorator._get_backend") as mock_backend:
            mock_backend.return_value = MagicMock()

            @cacheable
            def original_name(x: int) -> int:
                return x

            assert original_name.__name__ == "original_name"

    def test_preserves_function_doc(self) -> None:
        """Deve preservar docstring da função."""
        with patch("dapr_state_cache.decorator._get_backend") as mock_backend:
            mock_backend.return_value = MagicMock()

            @cacheable
            def documented_func(x: int) -> int:
                """This is the docstring."""
                return x

            assert documented_func.__doc__ == "This is the docstring."


class TestCacheableWrapperSync:
    """Testes para wrapper síncrono."""

    def test_sync_function_cache_miss(self) -> None:
        """Deve executar função no cache miss."""
        mock_backend = MagicMock()
        mock_backend.get.return_value = None
        mock_backend.set.return_value = True

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            @cacheable
            def compute(x: int) -> int:
                return x * 2

            result = compute(5)

            assert result == 10
            mock_backend.get.assert_called_once()
            mock_backend.set.assert_called_once()

    def test_sync_function_cache_hit(self) -> None:
        """Deve retornar cache no hit."""
        import msgpack

        mock_backend = MagicMock()
        mock_backend.get.return_value = msgpack.packb(42)

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):
            call_count = 0

            @cacheable
            def compute(x: int) -> int:
                nonlocal call_count
                call_count += 1
                return x * 2

            result = compute(21)

            assert result == 42
            assert call_count == 0  # Função não foi chamada
            mock_backend.set.assert_not_called()

    def test_sync_function_with_metrics(self) -> None:
        """Deve registrar métricas."""
        mock_backend = MagicMock()
        mock_backend.get.return_value = None
        mock_backend.set.return_value = True
        metrics = InMemoryMetrics()

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            @cacheable(metrics=metrics)
            def compute(x: int) -> int:
                return x * 2

            compute(5)
            stats = metrics.get_stats()

            assert stats.misses == 1
            assert stats.writes == 1


class TestCacheableWrapperAsync:
    """Testes para wrapper assíncrono."""

    @pytest.mark.asyncio
    async def test_async_function_cache_miss(self) -> None:
        """Deve executar função async no cache miss."""
        mock_backend = MagicMock()
        mock_backend.get_async = AsyncMock(return_value=None)
        mock_backend.set_async = AsyncMock(return_value=True)

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            @cacheable
            async def compute(x: int) -> int:
                return x * 2

            result = await compute(5)

            assert result == 10
            mock_backend.get_async.assert_called_once()
            mock_backend.set_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_function_cache_hit(self) -> None:
        """Deve retornar cache no hit para async."""
        import msgpack

        mock_backend = MagicMock()
        mock_backend.get_async = AsyncMock(return_value=msgpack.packb(42))

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):
            call_count = 0

            @cacheable
            async def compute(x: int) -> int:
                nonlocal call_count
                call_count += 1
                return x * 2

            result = await compute(21)

            assert result == 42
            assert call_count == 0


class TestCacheableWrapperInvalidation:
    """Testes para invalidação de cache."""

    def test_invalidate_sync(self) -> None:
        """Deve invalidar cache (sync)."""
        mock_backend = MagicMock()
        mock_backend.get.return_value = None
        mock_backend.set.return_value = True
        mock_backend.delete.return_value = True

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            @cacheable
            def compute(x: int) -> int:
                return x * 2

            compute(5)  # Popula cache
            result = compute.invalidate(5)

            assert result is True
            mock_backend.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_async(self) -> None:
        """Deve invalidar cache (async)."""
        mock_backend = MagicMock()
        mock_backend.get_async = AsyncMock(return_value=None)
        mock_backend.set_async = AsyncMock(return_value=True)
        mock_backend.delete_async = AsyncMock(return_value=True)

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            @cacheable
            async def compute(x: int) -> int:
                return x * 2

            await compute(5)
            result = await compute.invalidate_async(5)

            assert result is True
            mock_backend.delete_async.assert_called_once()


class TestCacheableWrapperDescriptor:
    """Testes para suporte a métodos via descriptor protocol."""

    def test_instance_method(self) -> None:
        """Deve funcionar com métodos de instância."""
        mock_backend = MagicMock()
        mock_backend.get.return_value = None
        mock_backend.set.return_value = True

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            class MyClass:
                def __init__(self, multiplier: int) -> None:
                    self.multiplier = multiplier

                @cacheable
                def compute(self, x: int) -> int:
                    return x * self.multiplier

            obj = MyClass(3)
            result = obj.compute(5)

            assert result == 15

    def test_instance_method_invalidate(self) -> None:
        """Deve invalidar cache de método de instância."""
        mock_backend = MagicMock()
        mock_backend.get.return_value = None
        mock_backend.set.return_value = True
        mock_backend.delete.return_value = True

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            class MyClass:
                @cacheable
                def compute(self, x: int) -> int:
                    return x * 2

            obj = MyClass()
            obj.compute(5)
            result = obj.compute.invalidate(5)

            assert result is True

    def test_descriptor_get_without_instance(self) -> None:
        """Deve retornar wrapper quando acessado da classe."""
        mock_backend = MagicMock()

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            class MyClass:
                @cacheable
                def compute(self, x: int) -> int:
                    return x * 2

            # Acessando da classe (sem instância)
            assert isinstance(MyClass.compute, CacheableWrapper)


class TestCacheableWrapperErrors:
    """Testes para tratamento de erros."""

    def test_sync_cache_get_error(self) -> None:
        """Deve continuar execução se get falhar."""
        mock_backend = MagicMock()
        mock_backend.get.side_effect = Exception("Connection error")
        mock_backend.set.return_value = True

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            @cacheable
            def compute(x: int) -> int:
                return x * 2

            result = compute(5)
            assert result == 10

    def test_sync_cache_set_error(self) -> None:
        """Deve continuar se set falhar."""
        mock_backend = MagicMock()
        mock_backend.get.return_value = None
        mock_backend.set.side_effect = Exception("Write error")

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            @cacheable
            def compute(x: int) -> int:
                return x * 2

            result = compute(5)
            assert result == 10

    @pytest.mark.asyncio
    async def test_async_cache_get_error(self) -> None:
        """Deve continuar execução se get_async falhar."""
        mock_backend = MagicMock()
        mock_backend.get_async = AsyncMock(side_effect=Exception("Connection error"))
        mock_backend.set_async = AsyncMock(return_value=True)

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            @cacheable
            async def compute(x: int) -> int:
                return x * 2

            result = await compute(5)
            assert result == 10

    @pytest.mark.asyncio
    async def test_async_cache_set_error(self) -> None:
        """Deve continuar se set_async falhar."""
        mock_backend = MagicMock()
        mock_backend.get_async = AsyncMock(return_value=None)
        mock_backend.set_async = AsyncMock(side_effect=Exception("Write error"))

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            @cacheable
            async def compute(x: int) -> int:
                return x * 2

            result = await compute(5)
            assert result == 10


class TestBoundCacheableMethodAsync:
    """Testes para métodos bound assíncronos."""

    @pytest.mark.asyncio
    async def test_bound_method_invalidate_async(self) -> None:
        """Deve invalidar cache de método bound (async)."""
        mock_backend = MagicMock()
        mock_backend.get_async = AsyncMock(return_value=None)
        mock_backend.set_async = AsyncMock(return_value=True)
        mock_backend.delete_async = AsyncMock(return_value=True)

        with patch("dapr_state_cache.decorator._get_backend", return_value=mock_backend):

            class MyClass:
                @cacheable
                async def compute(self, x: int) -> int:
                    return x * 2

            obj = MyClass()
            await obj.compute(5)
            result = await obj.compute.invalidate_async(5)

            assert result is True
            mock_backend.delete_async.assert_called_once()
