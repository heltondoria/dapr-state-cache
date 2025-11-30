"""Deduplicação de cache miss (thundering herd protection)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DeduplicationManager:
    """Gerenciador de deduplicação para evitar thundering herd.

    Quando múltiplas chamadas concorrentes tentam computar o mesmo valor
    (cache miss), apenas uma computação é executada e o resultado é
    compartilhado com todas as chamadas aguardando.

    Isso evita computações redundantes e reduz carga no sistema.

    Exemplo:
        ```python
        manager = DeduplicationManager()

        async def expensive_compute():
            await asyncio.sleep(1)
            return "result"

        # Apenas uma computação é executada, mesmo com 10 chamadas
        results = await asyncio.gather(*[
            manager.deduplicate("key", expensive_compute)
            for _ in range(10)
        ])
        ```
    """

    def __init__(self) -> None:
        """Inicializa o gerenciador de deduplicação."""
        self._pending: dict[str, asyncio.Future[Any]] = {}
        # asyncio.Lock é criado lazy para evitar "no current event loop" em Python 3.10+
        # quando a classe é instanciada antes de um event loop existir (ex: tempo de decorator)
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        """Obtém ou cria lock assíncrono (lazy init).

        Cria o asyncio.Lock na primeira chamada async, quando já existe
        um event loop ativo. Evita RuntimeError em Python 3.10+ quando
        a classe é instanciada antes de um event loop existir.
        """
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def deduplicate(
        self,
        key: str,
        compute_func: Callable[[], Awaitable[T]],
    ) -> T:
        """Executa computação com deduplicação.

        Se já existe uma computação em andamento para a mesma chave,
        aguarda e retorna o mesmo resultado.

        Args:
            key: Chave de deduplicação (normalmente a cache key)
            compute_func: Função async que computa o valor

        Returns:
            Resultado da computação

        Raises:
            Exception: Propaga exceções da computação para todos os waiters
        """
        # Verifica se já existe computação pendente e registra nova se não existir
        # Tudo em um único lock para evitar race conditions
        future: asyncio.Future[T] | None = None
        pending_future: asyncio.Future[Any] | None = None

        async with self._get_lock():
            pending_future = self._pending.get(key)
            if pending_future is None:
                # Não há computação pendente - esta task será responsável
                # Cria future para esta computação (usando get_running_loop() para Python 3.12+)
                future = asyncio.get_running_loop().create_future()
                self._pending[key] = future
            else:
                logger.debug(f"Aguardando computação existente para: {key}")
                # IMPORTANTE: Apenas captura a referência, NÃO await dentro do lock!
                # A task que está computando precisa do lock no finally para cleanup.

        # Se há computação pendente, aguarda FORA do lock (evita deadlock)
        if pending_future is not None:
            return await pending_future

        # Aqui future nunca é None (garantido pelo fluxo acima)
        # Mas precisamos verificar para satisfazer o type checker
        if future is None:
            raise RuntimeError("future não pode ser None neste ponto")  # pragma: no cover

        try:
            # Executa a computação
            logger.debug(f"Iniciando computação para: {key}")
            result = await compute_func()

            # Completa a future com sucesso (se não foi cancelada)
            if not future.done():
                future.set_result(result)
            return result

        except Exception as e:
            # Propaga a exceção para todos os waiters (se não foi cancelada)
            if not future.done():
                future.set_exception(e)
            raise

        finally:
            # Remove da lista de pendentes
            async with self._get_lock():
                self._pending.pop(key, None)

    async def is_pending(self, key: str) -> bool:
        """Verifica se há computação pendente para a chave."""
        async with self._get_lock():
            return key in self._pending

    async def pending_count(self) -> int:
        """Retorna número de computações pendentes."""
        async with self._get_lock():
            return len(self._pending)

    async def clear(self) -> int:
        """Limpa computações pendentes (cancela todas).

        Returns:
            Número de computações canceladas
        """
        async with self._get_lock():
            count = len(self._pending)
            for future in self._pending.values():
                if not future.done():
                    future.cancel()
            self._pending.clear()
            return count
