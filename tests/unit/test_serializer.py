"""Testes para o serializer MsgPack."""

import pytest

from dapr_state_cache.exceptions import CacheSerializationError
from dapr_state_cache.serializer import MsgPackSerializer


class TestMsgPackSerializer:
    """Testes para MsgPackSerializer."""

    def test_serialize_dict(self) -> None:
        """Deve serializar dicionário."""
        serializer = MsgPackSerializer()
        data = {"key": "value", "number": 42}

        result = serializer.serialize(data)

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_deserialize_dict(self) -> None:
        """Deve deserializar para dicionário."""
        serializer = MsgPackSerializer()
        data = {"key": "value", "number": 42}
        serialized = serializer.serialize(data)

        result = serializer.deserialize(serialized)

        assert result == data

    def test_serialize_list(self) -> None:
        """Deve serializar lista."""
        serializer = MsgPackSerializer()
        data = [1, 2, 3, "four", {"five": 5}]

        result = serializer.serialize(data)
        deserialized = serializer.deserialize(result)

        assert deserialized == data

    def test_serialize_none(self) -> None:
        """Deve serializar None."""
        serializer = MsgPackSerializer()

        result = serializer.serialize(None)
        deserialized = serializer.deserialize(result)

        assert deserialized is None

    def test_serialize_bytes(self) -> None:
        """Deve serializar bytes."""
        serializer = MsgPackSerializer()
        data = b"binary data"

        result = serializer.serialize(data)
        deserialized = serializer.deserialize(result)

        assert deserialized == data

    def test_serialize_nested_structure(self) -> None:
        """Deve serializar estruturas aninhadas."""
        serializer = MsgPackSerializer()
        data = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            "metadata": {"count": 2, "active": True},
        }

        result = serializer.serialize(data)
        deserialized = serializer.deserialize(result)

        assert deserialized == data

    def test_deserialize_invalid_data_raises_error(self) -> None:
        """Deve lançar erro ao deserializar dados inválidos."""
        serializer = MsgPackSerializer()

        with pytest.raises(CacheSerializationError):
            serializer.deserialize(b"invalid msgpack data \xff\xfe")

    def test_roundtrip_preserves_types(self) -> None:
        """Deve preservar tipos após roundtrip."""
        serializer = MsgPackSerializer()
        data = {
            "int": 42,
            "float": 3.14,
            "str": "hello",
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
        }

        result = serializer.deserialize(serializer.serialize(data))

        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["str"] == "hello"
        assert result["bool"] is True
        assert result["none"] is None
        assert result["list"] == [1, 2, 3]
