"""Testes para o gerenciador de deduplicação."""

import asyncio
import contextlib

import pytest

from dapr_state_cache.deduplication import DeduplicationManager


class TestDeduplicationManager:
    """Testes para DeduplicationManager."""

    @pytest.mark.asyncio
    async def test_single_computation(self) -> None:
        """Deve executar computação única."""
        manager = DeduplicationManager()
        call_count = 0

        async def compute() -> str:
            nonlocal call_count
            call_count += 1
            return "result"

        result = await manager.deduplicate("key1", compute)

        assert result == "result"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_calls_deduplicated(self) -> None:
        """Deve deduplicar chamadas concorrentes."""
        manager = DeduplicationManager()
        call_count = 0

        async def compute() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simula trabalho
            return "result"

        # Executa 5 chamadas concorrentes
        results = await asyncio.gather(*[manager.deduplicate("same_key", compute) for _ in range(5)])

        # Todas devem ter o mesmo resultado
        assert all(r == "result" for r in results)
        # Mas apenas uma computação deve ter sido executada
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_different_keys_not_deduplicated(self) -> None:
        """Chaves diferentes não devem ser deduplicadas."""
        manager = DeduplicationManager()
        call_count = 0

        async def compute() -> str:
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        results = await asyncio.gather(
            manager.deduplicate("key1", compute),
            manager.deduplicate("key2", compute),
            manager.deduplicate("key3", compute),
        )

        assert len(set(results)) == 3  # Resultados diferentes
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_error_propagated_to_all_waiters(self) -> None:
        """Erros devem ser propagados para todos os waiters."""
        manager = DeduplicationManager()

        async def compute() -> str:
            await asyncio.sleep(0.05)
            raise ValueError("computation failed")

        # Todas as chamadas devem receber o mesmo erro
        with pytest.raises(ValueError, match="computation failed"):
            await asyncio.gather(*[manager.deduplicate("error_key", compute) for _ in range(3)])

    @pytest.mark.asyncio
    async def test_is_pending(self) -> None:
        """Deve reportar se há computação pendente."""
        manager = DeduplicationManager()

        async def compute() -> str:
            await asyncio.sleep(0.1)
            return "result"

        # Inicia computação
        task = asyncio.create_task(manager.deduplicate("key1", compute))

        # Aguarda um pouco para a computação iniciar
        await asyncio.sleep(0.01)

        # Deve estar pendente
        assert await manager.is_pending("key1")
        assert not await manager.is_pending("key2")

        # Aguarda conclusão
        await task

        # Não deve mais estar pendente
        assert not await manager.is_pending("key1")

    @pytest.mark.asyncio
    async def test_pending_count(self) -> None:
        """Deve contar computações pendentes."""
        manager = DeduplicationManager()

        async def compute() -> str:
            await asyncio.sleep(0.1)
            return "result"

        tasks = [asyncio.create_task(manager.deduplicate(f"key{i}", compute)) for i in range(3)]

        await asyncio.sleep(0.01)
        assert await manager.pending_count() == 3

        await asyncio.gather(*tasks)
        assert await manager.pending_count() == 0

    @pytest.mark.asyncio
    async def test_clear_removes_pending(self) -> None:
        """Deve remover computações pendentes ao limpar."""
        manager = DeduplicationManager()

        async def compute() -> str:
            await asyncio.sleep(0.1)
            return "result"

        task = asyncio.create_task(manager.deduplicate("key1", compute))
        await asyncio.sleep(0.01)

        # Verifica que há uma computação pendente
        assert await manager.pending_count() == 1

        # Limpa as computações pendentes
        cleared = await manager.clear()
        assert cleared == 1
        assert await manager.pending_count() == 0

        # Task vai completar ou ser cancelada
        with contextlib.suppress(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_sequential_calls_not_deduplicated(self) -> None:
        """Chamadas sequenciais não devem ser deduplicadas."""
        manager = DeduplicationManager()
        call_count = 0

        async def compute() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        result1 = await manager.deduplicate("key1", compute)
        result2 = await manager.deduplicate("key1", compute)

        # Cada chamada deve executar independentemente
        assert result1 == 1
        assert result2 == 2
        assert call_count == 2
