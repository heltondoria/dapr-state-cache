"""
Unit tests for backend module.

Tests Dapr State Backend implementation and exception hierarchy
with 100% coverage following AAA pattern and TDD principles.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from dapr_state_cache.backend import (
    DaprStateBackend,
    CacheBackendError,
    RecoverableCacheError,
    IrrecoverableCacheError,
    CacheTimeoutError,
    CacheSerializationError,
    CacheCryptographyError,
    DaprUnavailableError,
    StateStoreNotConfiguredError,
    CacheAuthenticationError,
)


class TestCacheExceptions:
    """Test cache exception hierarchy."""

    def test_cache_backend_error_base_exception(self) -> None:
        """Test CacheBackendError base class."""
        # Arrange
        message = "Test error"
        key = "test:key"
        
        # Act
        error = CacheBackendError(message, key)
        
        # Assert
        assert str(error) == message
        assert error.key == key
        assert isinstance(error, Exception)

    def test_cache_backend_error_without_key(self) -> None:
        """Test CacheBackendError without key."""
        # Arrange
        message = "Test error without key"
        
        # Act
        error = CacheBackendError(message)
        
        # Assert
        assert str(error) == message
        assert error.key is None

    def test_recoverable_cache_error_inheritance(self) -> None:
        """Test RecoverableCacheError inherits from CacheBackendError."""
        # Arrange
        message = "Recoverable error"
        key = "test:key"
        
        # Act
        error = RecoverableCacheError(message, key)
        
        # Assert
        assert isinstance(error, CacheBackendError)
        assert str(error) == message
        assert error.key == key

    def test_irrecoverable_cache_error_inheritance(self) -> None:
        """Test IrrecoverableCacheError inherits from CacheBackendError."""
        # Arrange
        message = "Irrecoverable error"
        key = "test:key"
        
        # Act
        error = IrrecoverableCacheError(message, key)
        
        # Assert
        assert isinstance(error, CacheBackendError)
        assert str(error) == message
        assert error.key == key

    def test_specific_recoverable_errors(self) -> None:
        """Test specific recoverable error types."""
        # Arrange & Act & Assert
        timeout_error = CacheTimeoutError("Timeout", "key1")
        assert isinstance(timeout_error, RecoverableCacheError)
        
        serialization_error = CacheSerializationError("Serialization failed", "key2")
        assert isinstance(serialization_error, RecoverableCacheError)
        
        crypto_error = CacheCryptographyError("Crypto failed", "key3")
        assert isinstance(crypto_error, RecoverableCacheError)

    def test_specific_irrecoverable_errors(self) -> None:
        """Test specific irrecoverable error types."""
        # Arrange & Act & Assert
        dapr_error = DaprUnavailableError("Dapr unavailable")
        assert isinstance(dapr_error, IrrecoverableCacheError)
        
        store_error = StateStoreNotConfiguredError("Store not configured")
        assert isinstance(store_error, IrrecoverableCacheError)
        
        auth_error = CacheAuthenticationError("Auth failed")
        assert isinstance(auth_error, IrrecoverableCacheError)


class TestDaprStateBackend:
    """Test DaprStateBackend implementation."""

    def test_dapr_state_backend_init_valid_params(self) -> None:
        """Test DaprStateBackend initialization with valid parameters."""
        # Arrange
        store_name = "test-store"
        timeout = 10.0
        
        # Act
        with patch('dapr.clients.DaprClient'):
            backend = DaprStateBackend(store_name, timeout)
        
        # Assert
        assert backend.store_name == store_name
        assert backend._timeout_seconds == timeout

    def test_dapr_state_backend_init_default_timeout(self) -> None:
        """Test DaprStateBackend initialization with default timeout."""
        # Arrange
        store_name = "test-store"
        
        # Act
        with patch('dapr.clients.DaprClient'):
            backend = DaprStateBackend(store_name)
        
        # Assert
        assert backend.store_name == store_name
        assert backend._timeout_seconds == 5.0

    def test_dapr_state_backend_init_empty_store_raises_error(self) -> None:
        """Test that empty store name raises ValueError."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError) as exc_info:
            DaprStateBackend("")
        
        assert "Store name cannot be empty" in str(exc_info.value)

    @patch('dapr.clients.DaprClient')
    def test_ensure_dapr_client_success(self, mock_dapr_client: Mock) -> None:
        """Test successful Dapr client initialization."""
        # Arrange
        backend = DaprStateBackend("test-store")
        
        # Act
        backend._ensure_dapr_client()
        
        # Assert
        mock_dapr_client.assert_called_once()
        assert backend._dapr_client is not None

    @patch('dapr.clients.DaprClient')
    def test_ensure_dapr_client_import_error(self, mock_dapr_client: Mock) -> None:
        """Test Dapr client initialization with import error."""
        # Arrange
        mock_dapr_client.side_effect = ImportError("No module named 'dapr'")
        
        # Act & Assert - exception should be raised during initialization
        with pytest.raises(DaprUnavailableError) as exc_info:
            DaprStateBackend("test-store")
        
        assert "Dapr Python SDK not available" in str(exc_info.value)

    @patch('dapr.clients.DaprClient')
    def test_ensure_dapr_client_connection_error(self, mock_dapr_client: Mock) -> None:
        """Test Dapr client initialization with connection error."""
        # Arrange
        mock_dapr_client.side_effect = Exception("Connection refused")
        
        # Act & Assert - exception should be raised during initialization
        with pytest.raises(DaprUnavailableError) as exc_info:
            DaprStateBackend("test-store")
        
        assert "Failed to connect to Dapr sidecar" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_successful(self) -> None:
        """Test successful cache get operation."""
        # Arrange
        key = "test:key"
        expected_data = b"test data"
        
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.data = expected_data
        mock_client.get_state.return_value = mock_response
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act
        result = await backend.get(key)
        
        # Assert
        assert result == expected_data
        mock_client.get_state.assert_called_once_with(
            store_name="test-store",
            key=key,
            timeout=5.0
        )

    @pytest.mark.asyncio
    async def test_get_cache_miss(self) -> None:
        """Test cache get with cache miss."""
        # Arrange
        key = "test:key"
        
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.data = None  # Cache miss
        mock_client.get_state.return_value = mock_response
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act
        result = await backend.get(key)
        
        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_empty_key_raises_error(self) -> None:
        """Test that empty key raises ValueError."""
        # Arrange
        with patch('dapr.clients.DaprClient'):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await backend.get("")
        
        assert "Cache key cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_store_not_configured_error(self) -> None:
        """Test get operation with store not configured error."""
        # Arrange
        key = "test:key"
        
        mock_client = AsyncMock()
        mock_client.get_state.side_effect = Exception("store not configured")
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(StateStoreNotConfiguredError) as exc_info:
            await backend.get(key)
        
        assert "not configured" in str(exc_info.value)
        assert exc_info.value.key == key

    @pytest.mark.asyncio
    async def test_get_timeout_error(self) -> None:
        """Test get operation with timeout error."""
        # Arrange
        key = "test:key"
        
        mock_client = AsyncMock()
        mock_client.get_state.side_effect = Exception("timeout occurred")
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(CacheTimeoutError) as exc_info:
            await backend.get(key)
        
        assert "timeout" in str(exc_info.value)
        assert exc_info.value.key == key

    @pytest.mark.asyncio
    async def test_get_generic_recoverable_error(self) -> None:
        """Test get operation with generic recoverable error."""
        # Arrange
        key = "test:key"
        
        mock_client = AsyncMock()
        mock_client.get_state.side_effect = Exception("network error")
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(RecoverableCacheError) as exc_info:
            await backend.get(key)
        
        assert "Cache get failed" in str(exc_info.value)
        assert exc_info.value.key == key

    @pytest.mark.asyncio
    async def test_set_successful(self) -> None:
        """Test successful cache set operation."""
        # Arrange
        key = "test:key"
        value = b"test data"
        ttl = 3600
        
        mock_client = AsyncMock()
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act
        await backend.set(key, value, ttl)
        
        # Assert
        mock_client.save_state.assert_called_once_with(
            store_name="test-store",
            key=key,
            value=value,
            metadata={"ttlInSeconds": "3600"},
            timeout=5.0
        )

    @pytest.mark.asyncio
    async def test_set_empty_key_raises_error(self) -> None:
        """Test that empty key raises ValueError."""
        # Arrange
        with patch('dapr.clients.DaprClient'):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await backend.set("", b"data", 3600)
        
        assert "Cache key cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_set_non_bytes_value_raises_error(self) -> None:
        """Test that non-bytes value raises ValueError."""
        # Arrange
        with patch('dapr.clients.DaprClient'):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await backend.set("key", "not bytes", 3600)  # type: ignore
        
        assert "Cache value must be bytes" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_set_invalid_ttl_raises_error(self) -> None:
        """Test that invalid TTL raises ValueError."""
        # Arrange
        with patch('dapr.clients.DaprClient'):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await backend.set("key", b"data", 0)
        
        assert "TTL must be >= 1 second" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_set_store_not_configured_error(self) -> None:
        """Test set operation with store not configured error."""
        # Arrange
        key = "test:key"
        value = b"test data"
        ttl = 3600
        
        mock_client = AsyncMock()
        mock_client.save_state.side_effect = Exception("store not found")
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(StateStoreNotConfiguredError) as exc_info:
            await backend.set(key, value, ttl)
        
        assert "not configured" in str(exc_info.value)
        assert exc_info.value.key == key

    @pytest.mark.asyncio
    async def test_set_timeout_error(self) -> None:
        """Test set operation with timeout error."""
        # Arrange
        key = "test:key"
        value = b"test data"
        ttl = 3600
        
        mock_client = AsyncMock()
        mock_client.save_state.side_effect = Exception("operation timeout")
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(CacheTimeoutError) as exc_info:
            await backend.set(key, value, ttl)
        
        assert "timeout" in str(exc_info.value)
        assert exc_info.value.key == key

    @pytest.mark.asyncio
    async def test_set_generic_recoverable_error(self) -> None:
        """Test set operation with generic recoverable error."""
        # Arrange
        key = "test:key"
        value = b"test data" 
        ttl = 3600
        
        mock_client = AsyncMock()
        mock_client.save_state.side_effect = Exception("disk full")
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act & Assert
        with pytest.raises(RecoverableCacheError) as exc_info:
            await backend.set(key, value, ttl)
        
        assert "Cache set failed" in str(exc_info.value)
        assert exc_info.value.key == key

    @pytest.mark.asyncio
    async def test_invalidate_successful(self) -> None:
        """Test successful cache invalidation."""
        # Arrange
        key = "test:key"
        
        mock_client = AsyncMock()
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act
        await backend.invalidate(key)
        
        # Assert
        mock_client.delete_state.assert_called_once_with(
            store_name="test-store",
            key=key,
            timeout=5.0
        )

    @pytest.mark.asyncio
    async def test_invalidate_empty_key_noop(self) -> None:
        """Test that invalidating empty key is no-op."""
        # Arrange
        mock_client = AsyncMock()
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act
        await backend.invalidate("")
        
        # Assert
        mock_client.delete_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_error_best_effort(self) -> None:
        """Test that invalidation errors are logged but not propagated."""
        # Arrange
        key = "test:key"
        
        mock_client = AsyncMock()
        mock_client.delete_state.side_effect = Exception("delete failed")
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act - should not raise exception
        await backend.invalidate(key)
        
        # Assert
        mock_client.delete_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_prefix_best_effort_not_implemented(self) -> None:
        """Test prefix invalidation logs warning about not being implemented."""
        # Arrange
        prefix = "test:prefix"
        
        mock_client = AsyncMock()
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act - should not raise exception
        await backend.invalidate_prefix(prefix)
        
        # Assert - no actual delete operations should be called
        mock_client.delete_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_prefix_empty_prefix_noop(self) -> None:
        """Test that invalidating empty prefix is no-op."""
        # Arrange
        mock_client = AsyncMock()
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act
        await backend.invalidate_prefix("")
        
        # Assert - no operations should be performed
        assert not mock_client.method_calls

    def test_close_successful(self) -> None:
        """Test successful client close."""
        # Arrange
        mock_client = Mock()
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act
        backend.close()
        
        # Assert
        mock_client.close.assert_called_once()
        assert backend._dapr_client is None

    def test_close_with_error(self) -> None:
        """Test client close with error (should not propagate)."""
        # Arrange
        mock_client = Mock()
        mock_client.close.side_effect = Exception("Close failed")
        
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            backend = DaprStateBackend("test-store")
        
        # Act - should not raise exception
        backend.close()
        
        # Assert
        assert backend._dapr_client is None

    def test_close_no_client(self) -> None:
        """Test close when no client exists."""
        # Arrange
        backend = DaprStateBackend.__new__(DaprStateBackend)  # Skip __init__
        backend._dapr_client = None
        
        # Act - should not raise exception
        backend.close()
        
        # Assert
        assert backend._dapr_client is None

    def test_context_manager(self) -> None:
        """Test context manager functionality."""
        # Arrange
        mock_client = Mock()
        
        # Act & Assert
        with patch('dapr.clients.DaprClient', return_value=mock_client):
            with DaprStateBackend("test-store") as backend:
                assert backend is not None
                assert isinstance(backend, DaprStateBackend)
            
            # After exiting context, client should be closed
            mock_client.close.assert_called_once()

    def test_store_name_property(self) -> None:
        """Test store_name property."""
        # Arrange
        store_name = "my-test-store"
        
        # Act
        with patch('dapr.clients.DaprClient'):
            backend = DaprStateBackend(store_name)
        
        # Assert
        assert backend.store_name == store_name
