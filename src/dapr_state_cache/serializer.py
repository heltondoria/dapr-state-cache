"""Serialização de dados para cache usando MsgPack."""

from typing import Any, Protocol

import msgpack

from .exceptions import CacheSerializationError


class Serializer(Protocol):
    """Protocol para serializers customizados."""

    def serialize(self, data: Any) -> bytes:
        """Serializa dados Python para bytes."""
        ...

    def deserialize(self, data: bytes) -> Any:
        """Deserializa bytes para dados Python."""
        ...


class MsgPackSerializer:
    """Serializer usando MessagePack.

    MsgPack é um formato binário eficiente, mais compacto que JSON
    e com melhor performance para serialização/deserialização.

    Suporta tipos Python nativos:
    - None, bool, int, float, str, bytes
    - list, tuple, dict
    - datetime (via timestamp extension)
    """

    def serialize(self, data: Any) -> bytes:
        """Serializa dados Python para bytes MsgPack.

        Args:
            data: Dados a serializar

        Returns:
            Dados serializados em bytes

        Raises:
            CacheSerializationError: Se falhar ao serializar
        """
        try:
            result = msgpack.packb(data, use_bin_type=True)
            if result is None:
                raise CacheSerializationError("msgpack.packb retornou None")
            return result
        except (TypeError, ValueError) as e:
            raise CacheSerializationError(f"Falha ao serializar dados: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        """Deserializa bytes MsgPack para dados Python.

        Args:
            data: Bytes MsgPack

        Returns:
            Dados Python deserializados

        Raises:
            CacheSerializationError: Se falhar ao deserializar
        """
        try:
            return msgpack.unpackb(data, raw=False)
        except (msgpack.UnpackException, ValueError) as e:
            raise CacheSerializationError(f"Falha ao deserializar dados: {e}") from e
