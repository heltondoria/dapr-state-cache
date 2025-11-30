"""Testes para o construtor de chaves."""

import pytest

from dapr_state_cache.key_builder import DefaultKeyBuilder


class TestDefaultKeyBuilder:
    """Testes para DefaultKeyBuilder."""

    def test_build_key_with_simple_args(self) -> None:
        """Deve construir chave com argumentos simples."""
        builder = DefaultKeyBuilder(prefix="test")

        def my_func(x: int) -> int:
            return x * 2

        key = builder.build_key(my_func, (42,), {})

        assert key.startswith("test:")
        assert "my_func" in key

    def test_build_key_with_kwargs(self) -> None:
        """Deve construir chave com kwargs."""
        builder = DefaultKeyBuilder(prefix="cache")

        def get_user(user_id: int, include_profile: bool = False) -> dict:
            return {}

        key = builder.build_key(get_user, (123,), {"include_profile": True})

        assert key.startswith("cache:")

    def test_same_args_produce_same_key(self) -> None:
        """Mesmos argumentos devem produzir mesma chave."""
        builder = DefaultKeyBuilder()

        def fetch_data(x: int, y: str) -> dict:
            return {}

        key1 = builder.build_key(fetch_data, (1, "test"), {})
        key2 = builder.build_key(fetch_data, (1, "test"), {})

        assert key1 == key2

    def test_different_args_produce_different_keys(self) -> None:
        """Argumentos diferentes devem produzir chaves diferentes."""
        builder = DefaultKeyBuilder()

        def fetch_data(x: int) -> dict:
            return {}

        key1 = builder.build_key(fetch_data, (1,), {})
        key2 = builder.build_key(fetch_data, (2,), {})

        assert key1 != key2

    def test_kwargs_order_does_not_affect_key(self) -> None:
        """Ordem dos kwargs não deve afetar a chave."""
        builder = DefaultKeyBuilder()

        def fetch_data(a: int = 0, b: int = 0) -> dict:
            return {}

        key1 = builder.build_key(fetch_data, (), {"a": 1, "b": 2})
        key2 = builder.build_key(fetch_data, (), {"b": 2, "a": 1})

        assert key1 == key2

    def test_empty_prefix_raises_error(self) -> None:
        """Prefixo vazio deve lançar erro."""
        with pytest.raises(ValueError):
            DefaultKeyBuilder(prefix="")

    def test_key_format(self) -> None:
        """Deve ter formato correto: prefix:path:hash."""
        builder = DefaultKeyBuilder(prefix="myprefix")

        def sample_function(x: int) -> int:
            return x

        key = builder.build_key(sample_function, (42,), {})

        parts = key.split(":")
        assert len(parts) == 3
        assert parts[0] == "myprefix"
        assert "sample_function" in parts[1]
        assert len(parts[2]) == 16  # SHA256 truncado para 16 chars

    def test_method_self_filtered(self) -> None:
        """Deve filtrar 'self' de métodos."""
        builder = DefaultKeyBuilder()

        class MyClass:
            def my_method(self, x: int) -> int:
                return x

        obj = MyClass()
        key1 = builder.build_key(obj.my_method, (obj, 42), {})
        key2 = builder.build_key(obj.my_method, (obj, 42), {})

        # Mesma instância, mesmos args = mesma chave
        assert key1 == key2

    def test_prefix_property(self) -> None:
        """Deve expor o prefixo."""
        builder = DefaultKeyBuilder(prefix="custom")
        assert builder.prefix == "custom"

    def test_complex_types_in_args(self) -> None:
        """Deve lidar com tipos complexos nos argumentos."""
        builder = DefaultKeyBuilder()

        def process(data: dict, items: list) -> None:
            pass

        key = builder.build_key(
            process,
            ({"nested": {"value": 1}}, [1, 2, 3]),
            {},
        )

        assert key.startswith("cache:")

    def test_normalize_bytes(self) -> None:
        """Deve normalizar bytes para string."""
        builder = DefaultKeyBuilder()

        def process(data: bytes) -> None:
            pass

        key = builder.build_key(process, (b"hello",), {})
        assert key.startswith("cache:")

    def test_normalize_set(self) -> None:
        """Deve normalizar set para lista ordenada."""
        builder = DefaultKeyBuilder()

        def process(data: set) -> None:  # type: ignore[type-arg]
            pass

        key1 = builder.build_key(process, ({1, 2, 3},), {})
        key2 = builder.build_key(process, ({3, 2, 1},), {})
        # Sets com mesmos elementos devem produzir mesma chave
        assert key1 == key2

    def test_normalize_frozenset(self) -> None:
        """Deve normalizar frozenset para lista ordenada."""
        builder = DefaultKeyBuilder()

        def process(data: frozenset) -> None:  # type: ignore[type-arg]
            pass

        key = builder.build_key(process, (frozenset([1, 2, 3]),), {})
        assert key.startswith("cache:")

    def test_normalize_set_with_mixed_types(self) -> None:
        """Deve normalizar set com tipos mistos sem lançar TypeError.

        Bug fix: sorted() em sets com tipos mistos (ex: {1, "string", 3.14})
        lançava TypeError. A correção usa key function para ordenar por tipo+valor.
        """
        builder = DefaultKeyBuilder()

        def process(data: set) -> None:  # type: ignore[type-arg]
            pass

        # Set com tipos mistos que causaria TypeError em sorted()
        mixed_set = {1, "string", 3.14, True, None}
        key = builder.build_key(process, (mixed_set,), {})
        assert key.startswith("cache:")

        # Deve ser determinístico
        key2 = builder.build_key(process, (mixed_set,), {})
        assert key == key2

    def test_normalize_custom_object(self) -> None:
        """Deve usar str() para objetos customizados."""
        builder = DefaultKeyBuilder()

        class CustomObj:
            def __str__(self) -> str:
                return "custom_value"

        def process(obj: object) -> None:
            pass

        key = builder.build_key(process, (CustomObj(),), {})
        assert key.startswith("cache:")

    def test_empty_args(self) -> None:
        """Deve lidar com args vazios."""
        builder = DefaultKeyBuilder()

        def no_args() -> None:
            pass

        key = builder.build_key(no_args, (), {})
        assert key.startswith("cache:")

    def test_filter_cls_from_classmethod(self) -> None:
        """Deve filtrar 'cls' de métodos de classe."""
        builder = DefaultKeyBuilder()

        class MyClass:
            @classmethod
            def my_classmethod(cls, x: int) -> int:
                return x

        key = builder.build_key(MyClass.my_classmethod, (MyClass, 42), {})
        assert key.startswith("cache:")

    def test_function_without_module(self) -> None:
        """Deve lidar com função sem __module__."""
        builder = DefaultKeyBuilder()

        def func(x: int) -> int:
            return x

        # Remove __module__ temporariamente
        original_module = func.__module__
        del func.__module__  # type: ignore[attr-defined]

        try:
            key = builder.build_key(func, (1,), {})
            # Quando __module__ é removido, getattr retorna None
            assert "None" in key or "unknown" in key
        finally:
            func.__module__ = original_module

    def test_json_serialization_fallback(self) -> None:
        """Deve usar fallback para tipos não serializáveis em JSON."""
        builder = DefaultKeyBuilder()

        def process(data: object) -> None:
            pass

        # Objeto que json.dumps não consegue serializar diretamente
        # mas o default=str vai lidar com ele
        class Unserializable:
            pass

        key = builder.build_key(process, (Unserializable(),), {})
        assert key.startswith("cache:")
