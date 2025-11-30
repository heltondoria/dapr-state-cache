"""Construtor de chaves de cache determinísticas."""

import hashlib
import inspect
import json
from collections.abc import Callable
from typing import Any


class DefaultKeyBuilder:
    """Construtor de chaves padrão usando SHA256.

    Gera chaves determinísticas no formato:
    {prefix}:{module}.{qualname}:{hash_args}

    O hash é calculado sobre os argumentos serializados,
    excluindo 'self' e 'cls' para métodos.

    Attributes:
        prefix: Prefixo para todas as chaves geradas
    """

    def __init__(self, prefix: str = "cache") -> None:
        """Inicializa o key builder.

        Args:
            prefix: Prefixo das chaves (default: "cache")

        Raises:
            ValueError: Se prefix for vazio
        """
        if not prefix:
            raise ValueError("Prefix não pode ser vazio")
        self._prefix = prefix

    @property
    def prefix(self) -> str:
        """Prefixo das chaves."""
        return self._prefix

    def build_key(self, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Constrói chave de cache.

        Args:
            func: Função decorada
            args: Argumentos posicionais
            kwargs: Argumentos nomeados

        Returns:
            Chave no formato prefix:path:hash
        """
        func_path = self._get_function_path(func)
        filtered_args = self._filter_method_args(func, args)
        args_hash = self._hash_arguments(filtered_args, kwargs)
        return f"{self._prefix}:{func_path}:{args_hash}"

    def _get_function_path(self, func: Callable[..., Any]) -> str:
        """Obtém caminho completo da função."""
        module = getattr(func, "__module__", "unknown")
        qualname = getattr(func, "__qualname__", func.__name__)
        return f"{module}.{qualname}"

    def _filter_method_args(self, func: Callable[..., Any], args: tuple[Any, ...]) -> tuple[Any, ...]:
        """Remove 'self' ou 'cls' dos argumentos de métodos.

        Isso permite que cache seja compartilhado entre instâncias
        da mesma classe quando chamado com os mesmos argumentos.
        """
        if not args:
            return args

        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            if params and params[0] in ("self", "cls"):
                return args[1:]
        except (ValueError, TypeError):
            pass

        return args

    def _hash_arguments(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Calcula hash SHA256 dos argumentos."""
        # Ordena kwargs para determinismo
        sorted_kwargs = dict(sorted(kwargs.items()))

        # Serializa para JSON (tipos básicos)
        try:
            serialized = json.dumps(
                {"args": self._normalize(args), "kwargs": self._normalize(sorted_kwargs)},
                sort_keys=True,
                default=str,  # Fallback para tipos não serializáveis
            )
        except (TypeError, ValueError):
            # Fallback: usa representação string
            serialized = f"{args!r}:{sorted_kwargs!r}"

        # Calcula hash
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _normalize(self, obj: Any) -> Any:
        """Normaliza objeto para serialização JSON."""
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, (list, tuple)):
            return [self._normalize(item) for item in obj]
        if isinstance(obj, dict):
            return {str(k): self._normalize(v) for k, v in obj.items()}
        if isinstance(obj, (set, frozenset)):
            # Converte para string antes de ordenar para evitar TypeError
            # quando o set contém tipos mistos (ex: {1, "string", 3.14})
            normalized_items = [self._normalize(item) for item in obj]
            return sorted(normalized_items, key=lambda x: (type(x).__name__, str(x)))
        # Para outros tipos, usa representação string
        return str(obj)
