"""
Unit tests for core module (CacheService and CryptoIntegration).

Tests cache service facade and cryptography integration with 100% coverage
following AAA pattern and TDD principles.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from dapr_state_cache.backend.dapr_state_backend import DaprStateBackend
from dapr_state_cache.backend.exceptions import CacheKeyEmptyError, InvalidTTLValueError
from dapr_state_cache.codecs.json_serializer import JsonSerializer
from dapr_state_cache.core import (
    CacheService,
    CryptoIntegration,
    DaprCryptoError,
    NoOpCryptoIntegration,
    create_cache_service,
    create_crypto_integration,
)
from dapr_state_cache.keys.default_key_builder import DefaultKeyBuilder
from dapr_state_cache.protocols import KeyBuilder, ObservabilityHooks, Serializer


class TestDaprCryptoError:
    """Test DaprCryptoError exception."""

    def test_dapr_crypto_error_inheritance(self) -> None:
        """Test that DaprCryptoError inherits from RecoverableCacheError."""
        # Arrange
        message = "Crypto error"

        # Act
        error = DaprCryptoError(message)

        # Assert
        assert str(error) == message
        from dapr_state_cache.backend.exceptions import RecoverableCacheError

        assert isinstance(error, RecoverableCacheError)


class TestCryptoIntegration:
    """Test CryptoIntegration implementation."""

    def test_crypto_integration_initialization(self) -> None:
        """Test CryptoIntegration initialization."""
        # Arrange
        component_name = "test-crypto"
        mock_client = Mock()

        # Act
        crypto = CryptoIntegration(component_name, mock_client)

        # Assert
        assert crypto._crypto_component_name == component_name
        assert crypto._dapr_client is mock_client
        assert crypto._crypto_available is True

    @pytest.mark.asyncio
    @patch("dapr_state_cache.core.crypto_integration.logger")
    async def test_encrypt_success(self, mock_logger: Mock) -> None:
        """Test successful encryption."""
        # Arrange
        component_name = "test-crypto"
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.data = b"encrypted_data"
        mock_client.encrypt.return_value = mock_response

        crypto = CryptoIntegration(component_name, mock_client)
        data = b"test_data"

        # Act
        result = await crypto.encrypt(data)

        # Assert
        assert result == b"encrypted_data"
        mock_client.encrypt.assert_called_once_with(
            data=data, component_name=component_name, key_name="cache-encryption-key", algorithm="AES-GCM-256"
        )

    @pytest.mark.asyncio
    async def test_encrypt_crypto_unavailable(self) -> None:
        """Test encryption when crypto is marked unavailable."""
        # Arrange
        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)
        crypto._crypto_available = False
        data = b"test_data"

        # Act
        result = await crypto.encrypt(data)

        # Assert
        assert result == data  # Returns original data

    @pytest.mark.asyncio
    async def test_encrypt_import_error(self) -> None:
        """Test encryption with import error."""
        # Arrange
        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)

        # Mock _get_dapr_client to raise ImportError
        with patch.object(crypto, "_get_dapr_client", side_effect=ImportError("No Dapr")):
            data = b"test_data"

            # Act & Assert
            with pytest.raises(DaprCryptoError, match="Dapr client not available"):
                await crypto.encrypt(data)

            # Should mark crypto as unavailable
            assert crypto._crypto_available is False

    @pytest.mark.asyncio
    async def test_encrypt_general_error(self) -> None:
        """Test encryption with general error."""
        # Arrange
        component_name = "test-crypto"
        mock_client = AsyncMock()
        mock_client.encrypt.side_effect = Exception("Encryption failed")

        crypto = CryptoIntegration(component_name, mock_client)
        data = b"test_data"

        # Act & Assert
        with pytest.raises(DaprCryptoError, match="Encryption failed"):
            await crypto.encrypt(data)

    @pytest.mark.asyncio
    async def test_decrypt_success(self) -> None:
        """Test successful decryption."""
        # Arrange
        component_name = "test-crypto"
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.data = b"decrypted_data"
        mock_client.decrypt.return_value = mock_response

        crypto = CryptoIntegration(component_name, mock_client)
        encrypted_data = b"encrypted_data"

        # Act
        result = await crypto.decrypt(encrypted_data)

        # Assert
        assert result == b"decrypted_data"
        mock_client.decrypt.assert_called_once_with(
            data=encrypted_data, component_name=component_name, key_name="cache-encryption-key"
        )

    @pytest.mark.asyncio
    async def test_decrypt_crypto_unavailable(self) -> None:
        """Test decryption when crypto is marked unavailable."""
        # Arrange
        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)
        crypto._crypto_available = False
        encrypted_data = b"encrypted_data"

        # Act
        result = await crypto.decrypt(encrypted_data)

        # Assert
        assert result == encrypted_data  # Returns original data

    @pytest.mark.asyncio
    async def test_decrypt_import_error(self) -> None:
        """Test decryption with import error."""
        # Arrange
        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)

        # Mock _get_dapr_client to raise ImportError
        with patch.object(crypto, "_get_dapr_client", side_effect=ImportError("No Dapr")):
            encrypted_data = b"encrypted_data"

            # Act & Assert
            with pytest.raises(DaprCryptoError, match="Dapr client not available"):
                await crypto.decrypt(encrypted_data)

            # Should mark crypto as unavailable
            assert crypto._crypto_available is False

    @pytest.mark.asyncio
    async def test_decrypt_general_error(self) -> None:
        """Test decryption with general error."""
        # Arrange
        component_name = "test-crypto"
        mock_client = AsyncMock()
        mock_client.decrypt.side_effect = Exception("Decryption failed")

        crypto = CryptoIntegration(component_name, mock_client)
        encrypted_data = b"encrypted_data"

        # Act & Assert
        with pytest.raises(DaprCryptoError, match="Decryption failed"):
            await crypto.decrypt(encrypted_data)

    @pytest.mark.asyncio
    async def test_is_available_true(self) -> None:
        """Test is_available when crypto is available."""
        # Arrange
        component_name = "test-crypto"
        mock_client = Mock()
        crypto = CryptoIntegration(component_name, mock_client)

        # Act
        result = await crypto.is_available()

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_false_marked_unavailable(self) -> None:
        """Test is_available when marked unavailable."""
        # Arrange
        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)
        crypto._crypto_available = False

        # Act
        result = await crypto.is_available()

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_false_client_error(self) -> None:
        """Test is_available when client access fails."""
        # Arrange
        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)

        # Mock _get_dapr_client to raise exception
        with patch.object(crypto, "_get_dapr_client", side_effect=Exception("Client error")):
            # Act
            result = await crypto.is_available()

            # Assert
            assert result is False
            assert crypto._crypto_available is False

    @pytest.mark.asyncio
    @patch("dapr.clients.DaprClient")
    async def test_get_dapr_client_lazy_init(self, mock_dapr_client_class: Mock) -> None:
        """Test lazy initialization of Dapr client."""
        # Arrange
        mock_client_instance = Mock()
        mock_dapr_client_class.return_value = mock_client_instance

        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)

        # Act
        result = await crypto._get_dapr_client()

        # Assert
        assert result is mock_client_instance
        assert crypto._dapr_client is mock_client_instance
        mock_dapr_client_class.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_get_dapr_client_import_error(self) -> None:
        """Test Dapr client initialization with import error."""
        # Arrange
        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)

        # Mock import to fail by patching the import location
        with patch("dapr.clients.DaprClient", side_effect=ImportError("No module")):
            # Act & Assert
            with pytest.raises(ImportError, match="Dapr client not available"):
                await crypto._get_dapr_client()

    def test_crypto_component_name_property(self) -> None:
        """Test crypto_component_name property."""
        # Arrange
        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)

        # Act
        result = crypto.crypto_component_name

        # Assert
        assert result == component_name

    def test_reset_availability(self) -> None:
        """Test reset_availability method."""
        # Arrange
        component_name = "test-crypto"
        crypto = CryptoIntegration(component_name)
        crypto._crypto_available = False

        # Act
        crypto.reset_availability()

        # Assert
        assert crypto._crypto_available is True


class TestNoOpCryptoIntegration:
    """Test NoOpCryptoIntegration implementation."""

    def test_noop_crypto_initialization(self) -> None:
        """Test NoOpCryptoIntegration initialization."""
        # Arrange & Act
        crypto = NoOpCryptoIntegration()

        # Assert - should not raise any exception
        assert crypto is not None

    @pytest.mark.asyncio
    async def test_noop_encrypt_passthrough(self) -> None:
        """Test that no-op encrypt passes data through unchanged."""
        # Arrange
        crypto = NoOpCryptoIntegration()
        data = b"test_data"

        # Act
        result = await crypto.encrypt(data)

        # Assert
        assert result is data

    @pytest.mark.asyncio
    async def test_noop_decrypt_passthrough(self) -> None:
        """Test that no-op decrypt passes data through unchanged."""
        # Arrange
        crypto = NoOpCryptoIntegration()
        encrypted_data = b"encrypted_data"

        # Act
        result = await crypto.decrypt(encrypted_data)

        # Assert
        assert result is encrypted_data

    @pytest.mark.asyncio
    async def test_noop_is_available_always_true(self) -> None:
        """Test that no-op is_available always returns True."""
        # Arrange
        crypto = NoOpCryptoIntegration()

        # Act
        result = await crypto.is_available()

        # Assert
        assert result is True

    def test_noop_crypto_component_name_empty(self) -> None:
        """Test that no-op crypto_component_name returns empty string."""
        # Arrange
        crypto = NoOpCryptoIntegration()

        # Act
        result = crypto.crypto_component_name

        # Assert
        assert result == ""

    def test_noop_reset_availability_noop(self) -> None:
        """Test that no-op reset_availability does nothing."""
        # Arrange
        crypto = NoOpCryptoIntegration()

        # Act & Assert - should not raise any exception
        crypto.reset_availability()


class TestCreateCryptoIntegration:
    """Test create_crypto_integration factory function."""

    def test_create_crypto_integration_disabled(self) -> None:
        """Test creating crypto integration when disabled."""
        # Arrange & Act
        crypto = create_crypto_integration(use_dapr_crypto=False)

        # Assert
        assert isinstance(crypto, NoOpCryptoIntegration)

    def test_create_crypto_integration_enabled_with_component(self) -> None:
        """Test creating crypto integration when enabled with component."""
        # Arrange
        component_name = "test-crypto"
        mock_client = Mock()

        # Act
        crypto = create_crypto_integration(
            use_dapr_crypto=True, crypto_component_name=component_name, dapr_client=mock_client
        )

        # Assert
        assert isinstance(crypto, CryptoIntegration)
        assert crypto.crypto_component_name == component_name

    def test_create_crypto_integration_enabled_no_component(self) -> None:
        """Test creating crypto integration when enabled but no component name."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="crypto_component_name is required"):
            create_crypto_integration(use_dapr_crypto=True)

    def test_create_crypto_integration_enabled_empty_component(self) -> None:
        """Test creating crypto integration with empty component name."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="crypto_component_name is required"):
            create_crypto_integration(use_dapr_crypto=True, crypto_component_name="")


class TestCacheService:
    """Test CacheService implementation."""

    @patch("dapr.clients.DaprClient")
    def test_cache_service_initialization_defaults(self, mock_dapr_client: Mock) -> None:
        """Test CacheService initialization with defaults."""
        # Arrange
        store_name = "test-store"
        mock_client_instance = Mock()
        mock_client_instance.get_state.return_value = Mock()
        mock_dapr_client.return_value = mock_client_instance

        # Act
        service = CacheService(store_name)

        # Assert
        assert service.store_name == store_name
        assert service.key_prefix == "cache"
        assert isinstance(service.backend, DaprStateBackend)
        assert isinstance(service.serializer, JsonSerializer)
        assert isinstance(service.key_builder, DefaultKeyBuilder)
        assert isinstance(service.crypto_integration, NoOpCryptoIntegration)
        assert service.hooks is None

    def test_cache_service_initialization_custom_components(self) -> None:
        """Test CacheService initialization with custom components."""
        # Arrange
        store_name = "test-store"
        key_prefix = "custom"
        mock_backend = Mock(spec=DaprStateBackend)
        mock_serializer = Mock(spec=Serializer)
        mock_key_builder = Mock(spec=KeyBuilder)
        mock_crypto = Mock(spec=CryptoIntegration)
        mock_hooks = Mock(spec=ObservabilityHooks)

        # Act
        service = CacheService(
            store_name=store_name,
            backend=mock_backend,
            serializer=mock_serializer,
            key_builder=mock_key_builder,
            crypto_integration=mock_crypto,
            hooks=mock_hooks,
            key_prefix=key_prefix,
        )

        # Assert
        assert service.store_name == store_name
        assert service.key_prefix == key_prefix
        assert service.backend is mock_backend
        assert service.serializer is mock_serializer
        assert service.key_builder is mock_key_builder
        assert service.crypto_integration is mock_crypto
        assert service.hooks is mock_hooks

    @pytest.mark.asyncio
    async def test_get_cache_hit(self) -> None:
        """Test successful cache get (hit)."""
        # Arrange
        mock_backend = AsyncMock()
        mock_backend.get.return_value = b'{"result": "test"}'

        mock_serializer = Mock()
        mock_serializer.deserialize.return_value = {"result": "test"}

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        mock_crypto = AsyncMock()
        mock_crypto.decrypt.return_value = b'{"result": "test"}'

        mock_hooks = Mock()

        service = CacheService(
            store_name="test",
            backend=mock_backend,
            serializer=mock_serializer,
            key_builder=mock_key_builder,
            crypto_integration=mock_crypto,
            hooks=mock_hooks,
        )

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}

        # Act
        result = await service.get(func, args, kwargs)

        # Assert
        assert result == {"result": "test"}
        mock_backend.get.assert_called_once_with("test:key:hash123")
        mock_crypto.decrypt.assert_called_once_with(b'{"result": "test"}')
        mock_serializer.deserialize.assert_called_once_with(b'{"result": "test"}')
        mock_hooks.on_cache_hit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_miss(self) -> None:
        """Test cache get with miss (no data)."""
        # Arrange
        mock_backend = AsyncMock()
        mock_backend.get.return_value = None

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        mock_hooks = Mock()

        service = CacheService(store_name="test", backend=mock_backend, key_builder=mock_key_builder, hooks=mock_hooks)

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}

        # Act
        result = await service.get(func, args, kwargs)

        # Assert
        assert result is None
        mock_hooks.on_cache_miss.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_decryption_failure(self) -> None:
        """Test cache get with decryption failure."""
        # Arrange
        mock_backend = AsyncMock()
        mock_backend.get.return_value = b"encrypted_data"

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        mock_crypto = AsyncMock()
        mock_crypto.decrypt.side_effect = DaprCryptoError("Decryption failed")

        mock_hooks = Mock()

        service = CacheService(
            store_name="test",
            backend=mock_backend,
            key_builder=mock_key_builder,
            crypto_integration=mock_crypto,
            hooks=mock_hooks,
        )

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}

        # Act
        result = await service.get(func, args, kwargs)

        # Assert
        assert result is None
        mock_hooks.on_cache_error.assert_called_once()
        mock_hooks.on_cache_miss.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_deserialization_failure(self) -> None:
        """Test cache get with deserialization failure."""
        # Arrange
        mock_backend = AsyncMock()
        mock_backend.get.return_value = b"invalid_data"

        mock_serializer = Mock()
        mock_serializer.deserialize.side_effect = ValueError("Invalid data")

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        mock_crypto = AsyncMock()
        mock_crypto.decrypt.return_value = b"invalid_data"

        mock_hooks = Mock()

        service = CacheService(
            store_name="test",
            backend=mock_backend,
            serializer=mock_serializer,
            key_builder=mock_key_builder,
            crypto_integration=mock_crypto,
            hooks=mock_hooks,
        )

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}

        # Act
        result = await service.get(func, args, kwargs)

        # Assert
        assert result is None
        mock_hooks.on_cache_error.assert_called_once()
        mock_hooks.on_cache_miss.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_success(self) -> None:
        """Test successful cache set."""
        # Arrange
        mock_backend = AsyncMock()

        mock_serializer = Mock()
        mock_serializer.serialize.return_value = b'{"result": "test"}'

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        mock_crypto = AsyncMock()
        mock_crypto.encrypt.return_value = b"encrypted_data"

        mock_hooks = Mock()

        service = CacheService(
            store_name="test",
            backend=mock_backend,
            serializer=mock_serializer,
            key_builder=mock_key_builder,
            crypto_integration=mock_crypto,
            hooks=mock_hooks,
        )

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}
        value = {"result": "test"}
        ttl_seconds = 3600

        # Act
        result = await service.set(func, args, kwargs, value, ttl_seconds)

        # Assert
        assert result is True
        mock_serializer.serialize.assert_called_once_with(value)
        mock_crypto.encrypt.assert_called_once_with(b'{"result": "test"}')
        mock_backend.set.assert_called_once_with("test:key:hash123", b"encrypted_data", ttl_seconds)
        mock_hooks.on_cache_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_serialization_failure(self) -> None:
        """Test cache set with serialization failure."""
        # Arrange
        mock_backend = AsyncMock()

        mock_serializer = Mock()
        mock_serializer.serialize.side_effect = TypeError("Cannot serialize")

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        mock_hooks = Mock()

        service = CacheService(
            store_name="test",
            backend=mock_backend,
            serializer=mock_serializer,
            key_builder=mock_key_builder,
            hooks=mock_hooks,
        )

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}
        value = object()  # Non-serializable

        # Act
        result = await service.set(func, args, kwargs, value)

        # Assert
        assert result is False
        mock_hooks.on_cache_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_encryption_failure_fallback(self) -> None:
        """Test cache set with encryption failure (fallback to plaintext)."""
        # Arrange
        mock_backend = AsyncMock()

        mock_serializer = Mock()
        mock_serializer.serialize.return_value = b'{"result": "test"}'

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        mock_crypto = AsyncMock()
        mock_crypto.encrypt.side_effect = DaprCryptoError("Encryption failed")

        mock_hooks = Mock()

        service = CacheService(
            store_name="test",
            backend=mock_backend,
            serializer=mock_serializer,
            key_builder=mock_key_builder,
            crypto_integration=mock_crypto,
            hooks=mock_hooks,
        )

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}
        value = {"result": "test"}

        # Act
        result = await service.set(func, args, kwargs, value)

        # Assert
        assert result is True
        mock_hooks.on_cache_error.assert_called_once()
        mock_hooks.on_cache_write.assert_called_once()
        # Should store plaintext data with default TTL
        mock_backend.set.assert_called_once_with("test:key:hash123", b'{"result": "test"}', 3600)

    @pytest.mark.asyncio
    async def test_invalidate_success(self) -> None:
        """Test successful cache invalidation."""
        # Arrange
        mock_backend = AsyncMock()

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        service = CacheService(store_name="test", backend=mock_backend, key_builder=mock_key_builder)

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}

        # Act
        result = await service.invalidate(func, args, kwargs)

        # Assert
        assert result is True
        mock_backend.invalidate.assert_called_once_with("test:key:hash123")

    @pytest.mark.asyncio
    async def test_invalidate_failure(self) -> None:
        """Test cache invalidation failure."""
        # Arrange
        mock_backend = AsyncMock()
        mock_backend.invalidate.side_effect = Exception("Invalidation failed")

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        mock_hooks = Mock()

        service = CacheService(store_name="test", backend=mock_backend, key_builder=mock_key_builder, hooks=mock_hooks)

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}

        # Act
        result = await service.invalidate(func, args, kwargs)

        # Assert
        assert result is False
        mock_hooks.on_cache_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_prefix_success(self) -> None:
        """Test successful prefix invalidation."""
        # Arrange
        mock_backend = AsyncMock()

        service = CacheService(store_name="test", backend=mock_backend)

        prefix = "cache:prefix"

        # Act
        result = await service.invalidate_prefix(prefix)

        # Assert
        assert result is True
        mock_backend.invalidate_prefix.assert_called_once_with(prefix)

    @pytest.mark.asyncio
    async def test_invalidate_prefix_failure(self) -> None:
        """Test prefix invalidation failure."""
        # Arrange
        mock_backend = AsyncMock()
        mock_backend.invalidate_prefix.side_effect = Exception("Prefix invalidation failed")

        mock_hooks = Mock()

        service = CacheService(store_name="test", backend=mock_backend, hooks=mock_hooks)

        prefix = "cache:prefix"

        # Act
        result = await service.invalidate_prefix(prefix)

        # Assert
        assert result is False
        mock_hooks.on_cache_error.assert_called_once()

    def test_build_cache_key_success(self) -> None:
        """Test successful cache key building."""
        # Arrange
        mock_backend = AsyncMock()

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "test:key:hash123"

        service = CacheService(store_name="test", backend=mock_backend, key_builder=mock_key_builder)

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}

        # Act
        result = service._build_cache_key(func, args, kwargs)

        # Assert
        assert result == "test:key:hash123"
        mock_key_builder.build_key.assert_called_once_with(func, args, kwargs)

    def test_build_cache_key_empty_result(self) -> None:
        """Test cache key building with empty result."""
        # Arrange
        mock_backend = AsyncMock()

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = ""

        service = CacheService(store_name="test", backend=mock_backend, key_builder=mock_key_builder)

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}

        # Act & Assert
        with pytest.raises(CacheKeyEmptyError, match="Generated cache key is empty"):
            service._build_cache_key(func, args, kwargs)

    def test_build_cache_key_whitespace_only(self) -> None:
        """Test cache key building with whitespace-only result."""
        # Arrange
        mock_backend = AsyncMock()

        mock_key_builder = Mock()
        mock_key_builder.build_key.return_value = "   "

        service = CacheService(store_name="test", backend=mock_backend, key_builder=mock_key_builder)

        func = Mock(__name__="test_func")
        args = (1, 2)
        kwargs = {"key": "value"}

        # Act & Assert
        with pytest.raises(CacheKeyEmptyError, match="Generated cache key is empty"):
            service._build_cache_key(func, args, kwargs)

    def test_validate_ttl_valid_value(self) -> None:
        """Test TTL validation with valid value."""
        # Arrange
        mock_backend = AsyncMock()
        service = CacheService("test", backend=mock_backend)

        # Act & Assert - should not raise
        service.validate_ttl(3600)
        service.validate_ttl(1)
        service.validate_ttl(None)

    def test_validate_ttl_invalid_value(self) -> None:
        """Test TTL validation with invalid value."""
        # Arrange
        mock_backend = AsyncMock()
        service = CacheService("test", backend=mock_backend)

        # Act & Assert
        with pytest.raises(InvalidTTLValueError, match="TTL must be >= 1 second"):
            service.validate_ttl(0)

        with pytest.raises(InvalidTTLValueError, match="TTL must be >= 1 second"):
            service.validate_ttl(-1)

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self) -> None:
        """Test health check with all components healthy."""
        # Arrange
        mock_backend = AsyncMock()

        mock_serializer = Mock()
        mock_serializer.serialize.return_value = b'{"test": "health_check"}'
        mock_serializer.deserialize.return_value = {"test": "health_check"}

        mock_crypto = AsyncMock()
        mock_crypto.is_available.return_value = True

        service = CacheService(
            store_name="test-store",
            backend=mock_backend,
            key_prefix="test-prefix",
            serializer=mock_serializer,
            crypto_integration=mock_crypto,
        )

        # Act
        result = await service.health_check()

        # Assert
        assert result["service"] == "healthy"
        assert result["store_name"] == "test-store"
        assert result["key_prefix"] == "test-prefix"
        assert result["components"]["backend"] == "healthy"
        assert result["components"]["crypto"] == "healthy"
        assert result["components"]["serializer"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_crypto_disabled(self) -> None:
        """Test health check with crypto disabled."""
        # Arrange
        mock_backend = AsyncMock()

        mock_crypto = AsyncMock()
        mock_crypto.is_available.return_value = False

        service = CacheService(store_name="test-store", backend=mock_backend, crypto_integration=mock_crypto)

        # Act
        result = await service.health_check()

        # Assert
        assert result["components"]["crypto"] == "disabled"

    @pytest.mark.asyncio
    async def test_health_check_serializer_unhealthy(self) -> None:
        """Test health check with serializer unhealthy."""
        # Arrange
        mock_backend = AsyncMock()

        mock_serializer = Mock()
        mock_serializer.serialize.side_effect = Exception("Serializer error")

        service = CacheService(store_name="test-store", backend=mock_backend, serializer=mock_serializer)

        # Act
        result = await service.health_check()

        # Assert
        assert result["service"] == "degraded"
        assert "unhealthy: Serializer error" in result["components"]["serializer"]


class TestCreateCacheService:
    """Test create_cache_service factory function."""

    @patch("dapr_state_cache.core.cache_service.DaprStateBackend")
    def test_create_cache_service_minimal(self, mock_backend_class: Mock) -> None:
        """Test creating cache service with minimal parameters."""
        # Arrange
        mock_backend_instance = AsyncMock()
        mock_backend_class.return_value = mock_backend_instance
        store_name = "test-store"

        # Act
        service = create_cache_service(store_name)

        # Assert
        assert isinstance(service, CacheService)
        assert service.store_name == store_name
        assert service.key_prefix == "cache"

    @patch("dapr_state_cache.core.cache_service.DaprStateBackend")
    def test_create_cache_service_full_config(self, mock_backend_class: Mock) -> None:
        """Test creating cache service with full configuration."""
        # Arrange
        mock_backend_instance = AsyncMock()
        mock_backend_class.return_value = mock_backend_instance

        store_name = "test-store"
        key_prefix = "custom"
        mock_serializer = Mock(spec=Serializer)
        mock_key_builder = Mock(spec=KeyBuilder)
        mock_hooks = Mock(spec=ObservabilityHooks)
        mock_dapr_client = Mock()

        # Act
        service = create_cache_service(
            store_name=store_name,
            key_prefix=key_prefix,
            serializer=mock_serializer,
            key_builder=mock_key_builder,
            use_dapr_crypto=True,
            crypto_component_name="test-crypto",
            hooks=mock_hooks,
            dapr_client=mock_dapr_client,
        )

        # Assert
        assert isinstance(service, CacheService)
        assert service.store_name == store_name
        assert service.key_prefix == key_prefix
        assert service.serializer is mock_serializer
        assert service.key_builder is mock_key_builder
        assert service.hooks is mock_hooks
        assert isinstance(service.crypto_integration, CryptoIntegration)

    def test_create_cache_service_empty_store_name(self) -> None:
        """Test creating cache service with empty store name."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="store_name cannot be empty"):
            create_cache_service("")

    def test_create_cache_service_empty_key_prefix(self) -> None:
        """Test creating cache service with empty key prefix."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="key_prefix cannot be empty"):
            create_cache_service("test-store", key_prefix="")

    @patch("dapr_state_cache.core.cache_service.DaprStateBackend")
    def test_create_cache_service_crypto_without_component(self, mock_backend_class: Mock) -> None:
        """Test creating cache service with crypto enabled but no component."""
        # Arrange
        mock_backend_instance = AsyncMock()
        mock_backend_class.return_value = mock_backend_instance

        # Act & Assert
        with pytest.raises(ValueError, match="crypto_component_name is required"):
            create_cache_service("test-store", use_dapr_crypto=True)
