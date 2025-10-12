"""
Unit tests for cacheable decorator.

Tests @cacheable decorator with 100% coverage including all 10 parameters,
descriptor protocol, invalidation methods, and sync/async support following AAA pattern and TDD.
"""

import os
from unittest.mock import Mock, AsyncMock, patch

import pytest

from dapr_state_cache.decorators import (
    cacheable,
    CacheableWrapper,
    BoundMethodWrapper,
    CacheConfig,
)
from dapr_state_cache.protocols import KeyBuilder, Serializer, ObservabilityHooks


class TestCacheConfig:
    """Test CacheConfig configuration management."""

    def test_resolve_store_name_explicit_value(self) -> None:
        """Test store name resolution with explicit value."""
        # Arrange
        explicit_value = "explicit-store"
        
        # Act
        result = CacheConfig.resolve_store_name(explicit_value)
        
        # Assert
        assert result == explicit_value

    @patch.dict(os.environ, {"DAPR_CACHE_DEFAULT_STORE_NAME": "env-store"})
    def test_resolve_store_name_environment_variable(self) -> None:
        """Test store name resolution from environment variable."""
        # Arrange & Act
        result = CacheConfig.resolve_store_name(None)
        
        # Assert
        assert result == "env-store"

    @patch.dict(os.environ, {}, clear=True)
    def test_resolve_store_name_default_value(self) -> None:
        """Test store name resolution with default value."""
        # Arrange & Act
        result = CacheConfig.resolve_store_name(None)
        
        # Assert
        assert result == "cache"

    def test_resolve_crypto_component_name_explicit_value(self) -> None:
        """Test crypto component name resolution with explicit value."""
        # Arrange
        explicit_value = "explicit-crypto"
        
        # Act
        result = CacheConfig.resolve_crypto_component_name(explicit_value)
        
        # Assert
        assert result == explicit_value

    @patch.dict(os.environ, {"DAPR_CACHE_DEFAULT_CRYPTO_NAME": "env-crypto"})
    def test_resolve_crypto_component_name_environment_variable(self) -> None:
        """Test crypto component name resolution from environment variable."""
        # Arrange & Act
        result = CacheConfig.resolve_crypto_component_name(None)
        
        # Assert
        assert result == "env-crypto"

    @patch.dict(os.environ, {}, clear=True)
    def test_resolve_crypto_component_name_default_value(self) -> None:
        """Test crypto component name resolution with default value."""
        # Arrange & Act
        result = CacheConfig.resolve_crypto_component_name(None)
        
        # Assert
        assert result == "cache-crypto"

    def test_resolve_ttl_seconds_explicit_value(self) -> None:
        """Test TTL resolution with explicit value."""
        # Arrange
        explicit_value = 7200
        
        # Act
        result = CacheConfig.resolve_ttl_seconds(explicit_value)
        
        # Assert
        assert result == explicit_value

    def test_resolve_ttl_seconds_default_value(self) -> None:
        """Test TTL resolution with default value."""
        # Arrange & Act
        result = CacheConfig.resolve_ttl_seconds(None)
        
        # Assert
        assert result == 3600

    def test_validate_parameters_valid_configuration(self) -> None:
        """Test parameter validation with valid configuration."""
        # Arrange & Act & Assert - should not raise
        CacheConfig.validate_parameters(
            store_name="valid-store",
            ttl_seconds=3600,
            key_prefix="valid-prefix",
            use_dapr_crypto=False,
            crypto_component_name=None
        )

    def test_validate_parameters_empty_store_name(self) -> None:
        """Test parameter validation with empty store name."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="store_name cannot be empty"):
            CacheConfig.validate_parameters(
                store_name="",
                ttl_seconds=3600,
                key_prefix="valid-prefix",
                use_dapr_crypto=False,
                crypto_component_name=None
            )

    def test_validate_parameters_invalid_ttl(self) -> None:
        """Test parameter validation with invalid TTL."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="ttl_seconds must be >= 1"):
            CacheConfig.validate_parameters(
                store_name="valid-store",
                ttl_seconds=0,
                key_prefix="valid-prefix",
                use_dapr_crypto=False,
                crypto_component_name=None
            )

    def test_validate_parameters_empty_key_prefix(self) -> None:
        """Test parameter validation with empty key prefix."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="key_prefix cannot be empty"):
            CacheConfig.validate_parameters(
                store_name="valid-store",
                ttl_seconds=3600,
                key_prefix="",
                use_dapr_crypto=False,
                crypto_component_name=None
            )

    def test_validate_parameters_crypto_without_component_name(self) -> None:
        """Test parameter validation with crypto enabled but no component name."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="crypto_component_name is required"):
            CacheConfig.validate_parameters(
                store_name="valid-store",
                ttl_seconds=3600,
                key_prefix="valid-prefix",
                use_dapr_crypto=True,
                crypto_component_name=None
            )


class TestCacheableWrapper:
    """Test CacheableWrapper functionality."""

    def test_cacheable_wrapper_initialization(self) -> None:
        """Test CacheableWrapper initialization."""
        # Arrange
        def test_func() -> str:
            return "test"
        
        mock_orchestrator = Mock()
        mock_bridge = Mock()
        
        # Act
        wrapper = CacheableWrapper(
            func=test_func,
            orchestrator=mock_orchestrator,
            bridge=mock_bridge,
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        # Assert
        assert wrapper._func is test_func
        assert wrapper._orchestrator is mock_orchestrator
        assert wrapper._bridge is mock_bridge
        assert wrapper._ttl_seconds == 3600
        assert wrapper.__name__ == "test_func"

    def test_cacheable_wrapper_set_name_descriptor(self) -> None:
        """Test __set_name__ for descriptor protocol."""
        # Arrange
        def test_method(self) -> str:
            return "test"
        
        wrapper = CacheableWrapper(
            func=test_method,
            orchestrator=Mock(),
            bridge=Mock(),
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        class TestClass:
            pass
        
        # Act
        wrapper.__set_name__(TestClass, "cached_method")
        
        # Assert
        assert wrapper._owner_class is TestClass
        assert wrapper.__name__ == "cached_method"

    def test_cacheable_wrapper_get_unbound(self) -> None:
        """Test __get__ returning unbound wrapper (class access)."""
        # Arrange
        def test_method(self) -> str:
            return "test"
        
        wrapper = CacheableWrapper(
            func=test_method,
            orchestrator=Mock(),
            bridge=Mock(),
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        class TestClass:
            pass
        
        # Act
        result = wrapper.__get__(None, TestClass)
        
        # Assert
        assert result is wrapper

    def test_cacheable_wrapper_get_bound(self) -> None:
        """Test __get__ returning bound method wrapper (instance access)."""
        # Arrange
        def test_method(self) -> str:
            return "test"
        
        wrapper = CacheableWrapper(
            func=test_method,
            orchestrator=Mock(),
            bridge=Mock(),
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        class TestClass:
            pass
        
        instance = TestClass()
        
        # Act
        result = wrapper.__get__(instance, TestClass)
        
        # Assert
        assert isinstance(result, BoundMethodWrapper)
        assert result._instance is instance
        assert result._wrapper is wrapper

    @pytest.mark.asyncio
    async def test_cacheable_wrapper_call_async(self) -> None:
        """Test async call through wrapper."""
        # Arrange
        def test_func(x: int) -> str:
            return f"result_{x}"
        
        mock_orchestrator = AsyncMock()
        mock_orchestrator.execute_with_cache.return_value = "cached_result"
        
        wrapper = CacheableWrapper(
            func=test_func,
            orchestrator=mock_orchestrator,
            bridge=Mock(),
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        # Act
        result = await wrapper(5)
        
        # Assert
        assert result == "cached_result"
        mock_orchestrator.execute_with_cache.assert_called_once_with(
            func=test_func,
            args=(5,),
            kwargs={},
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )

    def test_cacheable_wrapper_call_sync_with_async_func(self) -> None:
        """Test sync call of wrapper with async function."""
        # Arrange
        async def test_async_func(x: int) -> str:
            return f"async_result_{x}"
        
        mock_bridge = Mock()
        mock_bridge.run_async_in_sync.return_value = "sync_result"
        
        wrapper = CacheableWrapper(
            func=test_async_func,
            orchestrator=Mock(),
            bridge=mock_bridge,
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        # Act
        result = wrapper.__call_sync__(5)
        
        # Assert
        assert result == "sync_result"
        mock_bridge.run_async_in_sync.assert_called_once()

    def test_cacheable_wrapper_call_sync_with_sync_func(self) -> None:
        """Test sync call of wrapper with sync function."""
        # Arrange
        def test_sync_func(x: int) -> str:
            return f"sync_result_{x}"
        
        mock_bridge = Mock()
        mock_bridge.execute_auto_sync.return_value = "bridge_result"
        
        wrapper = CacheableWrapper(
            func=test_sync_func,
            orchestrator=Mock(),
            bridge=mock_bridge,
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        # Act
        result = wrapper.__call_sync__(5)
        
        # Assert
        assert result == "bridge_result"
        mock_bridge.execute_auto_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_cacheable_wrapper_invalidate_async(self) -> None:
        """Test async cache invalidation."""
        # Arrange
        def test_func() -> str:
            return "test"
        
        mock_orchestrator = AsyncMock()
        mock_orchestrator.invalidate_cache.return_value = True
        
        wrapper = CacheableWrapper(
            func=test_func,
            orchestrator=mock_orchestrator,
            bridge=Mock(),
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        # Act
        result = await wrapper.invalidate(5, key="value")
        
        # Assert
        assert result is True
        mock_orchestrator.invalidate_cache.assert_called_once_with(
            test_func, (5,), {"key": "value"}
        )

    @pytest.mark.asyncio
    async def test_cacheable_wrapper_invalidate_prefix_async(self) -> None:
        """Test async cache prefix invalidation."""
        # Arrange
        def test_func() -> str:
            return "test"
        
        mock_orchestrator = AsyncMock()
        mock_orchestrator.invalidate_cache_prefix.return_value = True
        
        wrapper = CacheableWrapper(
            func=test_func,
            orchestrator=mock_orchestrator,
            bridge=Mock(),
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        # Act
        result = await wrapper.invalidate_prefix("cache:prefix")
        
        # Assert
        assert result is True
        mock_orchestrator.invalidate_cache_prefix.assert_called_once_with("cache:prefix")

    def test_cacheable_wrapper_invalidate_sync(self) -> None:
        """Test sync cache invalidation."""
        # Arrange
        def test_func() -> str:
            return "test"
        
        mock_bridge = Mock()
        mock_bridge.execute_auto_sync.return_value = True
        
        wrapper = CacheableWrapper(
            func=test_func,
            orchestrator=Mock(),
            bridge=mock_bridge,
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        # Act
        result = wrapper.invalidate_sync(5, key="value")
        
        # Assert
        assert result is True
        mock_bridge.execute_auto_sync.assert_called_once()

    def test_cacheable_wrapper_invalidate_prefix_sync(self) -> None:
        """Test sync cache prefix invalidation."""
        # Arrange
        def test_func() -> str:
            return "test"
        
        mock_bridge = Mock()
        mock_bridge.execute_auto_sync.return_value = True
        
        wrapper = CacheableWrapper(
            func=test_func,
            orchestrator=Mock(),
            bridge=mock_bridge,
            ttl_seconds=3600,
            condition=None,
            bypass=None
        )
        
        # Act
        result = wrapper.invalidate_prefix_sync("cache:prefix")
        
        # Assert
        assert result is True
        mock_bridge.execute_auto_sync.assert_called_once()


class TestBoundMethodWrapper:
    """Test BoundMethodWrapper functionality."""

    def test_bound_method_wrapper_initialization(self) -> None:
        """Test BoundMethodWrapper initialization."""
        # Arrange
        class TestClass:
            pass
        
        instance = TestClass()
        mock_cacheable_wrapper = Mock()
        mock_cacheable_wrapper.__name__ = "test_method"
        mock_cacheable_wrapper.__doc__ = "Test method"
        
        # Act
        bound_wrapper = BoundMethodWrapper(instance, mock_cacheable_wrapper)
        
        # Assert
        assert bound_wrapper._instance is instance
        assert bound_wrapper._wrapper is mock_cacheable_wrapper
        assert bound_wrapper.__name__ == "test_method"
        assert bound_wrapper.__doc__ == "Test method"

    @pytest.mark.asyncio
    async def test_bound_method_wrapper_call_async_context(self) -> None:
        """Test bound method call in async context."""
        # Arrange
        class TestClass:
            pass
        
        instance = TestClass()
        mock_cacheable_wrapper = AsyncMock()
        mock_cacheable_wrapper.return_value = "bound_result"
        
        bound_wrapper = BoundMethodWrapper(instance, mock_cacheable_wrapper)
        
        # Act
        result = await bound_wrapper(5, key="value")
        
        # Assert
        assert result == "bound_result"
        mock_cacheable_wrapper.assert_called_once_with(instance, 5, key="value")

    def test_bound_method_wrapper_call_sync_context(self) -> None:
        """Test bound method call in sync context."""
        # Arrange
        class TestClass:
            pass
        
        instance = TestClass()
        mock_cacheable_wrapper = Mock()
        mock_cacheable_wrapper.__name__ = "test_method"
        mock_cacheable_wrapper.__doc__ = "Test method"
        
        # Configure __call_sync__ as a regular method
        mock_call_sync = Mock(return_value="sync_bound_result")
        mock_cacheable_wrapper.__call_sync__ = mock_call_sync
        
        bound_wrapper = BoundMethodWrapper(instance, mock_cacheable_wrapper)
        
        # Act
        result = bound_wrapper(5, key="value")
        
        # Assert
        assert result == "sync_bound_result"
        mock_call_sync.assert_called_once_with(instance, 5, key="value")

    @pytest.mark.asyncio
    async def test_bound_method_wrapper_invalidate_async(self) -> None:
        """Test bound method invalidation (async)."""
        # Arrange
        class TestClass:
            pass
        
        instance = TestClass()
        mock_cacheable_wrapper = AsyncMock()
        mock_cacheable_wrapper.invalidate.return_value = True
        
        bound_wrapper = BoundMethodWrapper(instance, mock_cacheable_wrapper)
        
        # Act
        result = await bound_wrapper.invalidate(5, key="value")
        
        # Assert
        assert result is True
        mock_cacheable_wrapper.invalidate.assert_called_once_with(instance, 5, key="value")

    def test_bound_method_wrapper_invalidate_sync(self) -> None:
        """Test bound method invalidation (sync)."""
        # Arrange
        class TestClass:
            pass
        
        instance = TestClass()
        mock_cacheable_wrapper = Mock()
        mock_cacheable_wrapper.__name__ = "test_method"
        mock_cacheable_wrapper.__doc__ = "Test method"
        mock_cacheable_wrapper.invalidate_sync.return_value = True
        
        bound_wrapper = BoundMethodWrapper(instance, mock_cacheable_wrapper)
        
        # Act
        result = bound_wrapper.invalidate_sync(5, key="value")
        
        # Assert
        assert result is True
        mock_cacheable_wrapper.invalidate_sync.assert_called_once_with(instance, 5, key="value")

    @pytest.mark.asyncio
    async def test_bound_method_wrapper_invalidate_prefix_async(self) -> None:
        """Test bound method prefix invalidation (async)."""
        # Arrange
        class TestClass:
            pass
        
        instance = TestClass()
        mock_cacheable_wrapper = AsyncMock()
        mock_cacheable_wrapper.invalidate_prefix.return_value = True
        
        bound_wrapper = BoundMethodWrapper(instance, mock_cacheable_wrapper)
        
        # Act
        result = await bound_wrapper.invalidate_prefix("cache:prefix")
        
        # Assert
        assert result is True
        mock_cacheable_wrapper.invalidate_prefix.assert_called_once_with("cache:prefix")

    def test_bound_method_wrapper_invalidate_prefix_sync(self) -> None:
        """Test bound method prefix invalidation (sync)."""
        # Arrange
        class TestClass:
            pass
        
        instance = TestClass()
        mock_cacheable_wrapper = Mock()
        mock_cacheable_wrapper.__name__ = "test_method"
        mock_cacheable_wrapper.__doc__ = "Test method"
        mock_cacheable_wrapper.invalidate_prefix_sync.return_value = True
        
        bound_wrapper = BoundMethodWrapper(instance, mock_cacheable_wrapper)
        
        # Act
        result = bound_wrapper.invalidate_prefix_sync("cache:prefix")
        
        # Assert
        assert result is True
        mock_cacheable_wrapper.invalidate_prefix_sync.assert_called_once_with("cache:prefix")


class TestCacheableDecorator:
    """Test @cacheable decorator functionality."""

    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_orchestrator')
    def test_cacheable_decorator_minimal_parameters(
        self, 
        mock_create_orchestrator: Mock,
        mock_create_service: Mock
    ) -> None:
        """Test @cacheable decorator with minimal parameters."""
        # Arrange
        mock_service = Mock()
        mock_orchestrator = Mock()
        mock_create_service.return_value = mock_service
        mock_create_orchestrator.return_value = mock_orchestrator
        
        def test_func() -> str:
            return "test"
        
        # Act
        decorated_func = cacheable()(test_func)
        
        # Assert
        assert isinstance(decorated_func, CacheableWrapper)
        assert decorated_func._func is test_func
        mock_create_service.assert_called_once()
        mock_create_orchestrator.assert_called_once_with(
            cache_service=mock_service,
            enable_deduplication=True
        )

    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_orchestrator')
    def test_cacheable_decorator_all_parameters(
        self, 
        mock_create_orchestrator: Mock,
        mock_create_service: Mock
    ) -> None:
        """Test @cacheable decorator with all parameters."""
        # Arrange
        mock_service = Mock()
        mock_orchestrator = Mock()
        mock_create_service.return_value = mock_service
        mock_create_orchestrator.return_value = mock_orchestrator
        
        mock_key_builder = Mock(spec=KeyBuilder)
        mock_serializer = Mock(spec=Serializer)
        mock_hooks = Mock(spec=ObservabilityHooks)
        
        def mock_condition(x: int) -> bool:
            return x > 0
        
        def mock_bypass(x: int) -> bool:
            return x < 0
        
        def test_func(x: int) -> str:
            return f"result_{x}"
        
        # Act
        decorated_func = cacheable(
            store_name="custom-store",
            ttl_seconds=7200,
            key_prefix="custom-prefix",
            key_builder=mock_key_builder,
            serializer=mock_serializer,
            use_dapr_crypto=True,
            crypto_component_name="custom-crypto",
            condition=mock_condition,
            bypass=mock_bypass,
            hooks=mock_hooks
        )(test_func)
        
        # Assert
        assert isinstance(decorated_func, CacheableWrapper)
        assert decorated_func._ttl_seconds == 7200
        assert decorated_func._condition is mock_condition
        assert decorated_func._bypass is mock_bypass
        
        mock_create_service.assert_called_once_with(
            store_name="custom-store",
            key_prefix="custom-prefix",
            serializer=mock_serializer,
            key_builder=mock_key_builder,
            use_dapr_crypto=True,
            crypto_component_name="custom-crypto",
            hooks=mock_hooks
        )

    @patch.dict(os.environ, {"DAPR_CACHE_DEFAULT_STORE_NAME": "env-store"})
    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_orchestrator')
    def test_cacheable_decorator_environment_variable_resolution(
        self, 
        mock_create_orchestrator: Mock,
        mock_create_service: Mock
    ) -> None:
        """Test @cacheable decorator with environment variable resolution."""
        # Arrange
        mock_service = Mock()
        mock_orchestrator = Mock()
        mock_create_service.return_value = mock_service
        mock_create_orchestrator.return_value = mock_orchestrator
        
        def test_func() -> str:
            return "test"
        
        # Act
        cacheable()(test_func)
        
        # Assert
        mock_create_service.assert_called_once()
        # Verify store_name was resolved from environment
        args, kwargs = mock_create_service.call_args
        assert kwargs["store_name"] == "env-store"

    def test_cacheable_decorator_parameter_validation_error(self) -> None:
        """Test @cacheable decorator with invalid parameters."""
        # Arrange
        def test_func() -> str:
            return "test"
        
        # Act & Assert
        with pytest.raises(ValueError, match="store_name cannot be empty"):
            cacheable(store_name="")(test_func)

    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    def test_cacheable_decorator_service_creation_error(self, mock_create_service: Mock) -> None:
        """Test @cacheable decorator when service creation fails."""
        # Arrange
        mock_create_service.side_effect = Exception("Service creation failed")
        
        def test_func() -> str:
            return "test"
        
        # Act & Assert
        with pytest.raises(Exception, match="Service creation failed"):
            cacheable()(test_func)


class TestIntegrationScenarios:
    """Integration tests for decorator usage scenarios."""

    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_orchestrator')
    def test_function_decoration_and_metadata_preservation(
        self, 
        mock_create_orchestrator: Mock,
        mock_create_service: Mock
    ) -> None:
        """Test that function decoration preserves metadata."""
        # Arrange
        mock_service = Mock()
        mock_orchestrator = Mock()
        mock_create_service.return_value = mock_service
        mock_create_orchestrator.return_value = mock_orchestrator
        
        def original_function(x: int, y: str = "default") -> str:
            """Original function docstring."""
            return f"{x}_{y}"
        
        # Act
        decorated_func = cacheable()(original_function)
        
        # Assert
        assert decorated_func.__name__ == "original_function"
        assert decorated_func.__doc__ == "Original function docstring."
        assert decorated_func.__module__ == original_function.__module__

    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_orchestrator')
    def test_method_decoration_descriptor_protocol(
        self, 
        mock_create_orchestrator: Mock,
        mock_create_service: Mock
    ) -> None:
        """Test method decoration with descriptor protocol."""
        # Arrange
        mock_service = Mock()
        mock_orchestrator = Mock()
        mock_create_service.return_value = mock_service
        mock_create_orchestrator.return_value = mock_orchestrator
        
        class TestClass:
            @cacheable()
            def cached_method(self, x: int) -> str:
                return f"method_result_{x}"
        
        instance = TestClass()
        
        # Act - access method on class (unbound)
        unbound = TestClass.cached_method
        
        # Act - access method on instance (bound)
        bound = instance.cached_method
        
        # Assert
        assert isinstance(unbound, CacheableWrapper)
        assert isinstance(bound, BoundMethodWrapper)
        assert bound._instance is instance

    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_orchestrator')
    def test_static_method_decoration(
        self, 
        mock_create_orchestrator: Mock,
        mock_create_service: Mock
    ) -> None:
        """Test static method decoration."""
        # Arrange
        mock_service = Mock()
        mock_orchestrator = Mock()
        mock_create_service.return_value = mock_service
        mock_create_orchestrator.return_value = mock_orchestrator
        
        class TestClass:
            @staticmethod
            @cacheable()
            def cached_static_method(x: int) -> str:
                return f"static_result_{x}"
        
        # Act - access static method
        static_method = TestClass.cached_static_method
        
        # Assert
        assert isinstance(static_method, CacheableWrapper)

    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_orchestrator')
    def test_class_method_decoration(
        self, 
        mock_create_orchestrator: Mock,
        mock_create_service: Mock
    ) -> None:
        """Test class method decoration."""
        # Arrange
        mock_service = Mock()
        mock_orchestrator = Mock()
        mock_create_service.return_value = mock_service
        mock_create_orchestrator.return_value = mock_orchestrator
        
        class TestClass:
            @classmethod
            @cacheable()
            def cached_class_method(cls, x: int) -> str:
                return f"class_result_{x}"
        
        # Act - access class method
        class_method = TestClass.cached_class_method
        
        # Assert
        # Class method returns bound method automatically
        assert hasattr(class_method, '__call__')


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch('dapr_state_cache.decorators.cacheable.logger')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    def test_decorator_logs_errors_during_creation(
        self, 
        mock_create_service: Mock,
        mock_logger: Mock
    ) -> None:
        """Test that decorator logs errors during wrapper creation."""
        # Arrange
        mock_create_service.side_effect = RuntimeError("Mock error")
        
        def test_func() -> str:
            return "test"
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Mock error"):
            cacheable()(test_func)
        
        # Verify logging
        mock_logger.error.assert_called_once()

    @patch('dapr_state_cache.decorators.cacheable.logger')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_service')
    @patch('dapr_state_cache.decorators.cacheable.create_cache_orchestrator')
    def test_decorator_logs_successful_creation(
        self, 
        mock_create_orchestrator: Mock,
        mock_create_service: Mock,
        mock_logger: Mock
    ) -> None:
        """Test that decorator logs successful wrapper creation."""
        # Arrange
        mock_service = Mock()
        mock_orchestrator = Mock()
        mock_create_service.return_value = mock_service
        mock_create_orchestrator.return_value = mock_orchestrator
        
        def test_func() -> str:
            return "test"
        
        # Act
        decorated_func = cacheable()(test_func)
        
        # Assert
        assert isinstance(decorated_func, CacheableWrapper)
        
        # Verify logging
        mock_logger.debug.assert_any_call(
            "Applying @cacheable decorator to function test_func"
        )
        mock_logger.debug.assert_any_call(
            "Successfully created cacheable wrapper for test_func"
        )
