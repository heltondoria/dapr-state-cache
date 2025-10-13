"""
Additional tests for 100% coverage of decorators module.

These tests focus on edge cases and code paths not covered by existing tests.
"""


from dapr_state_cache.decorators.cacheable import (
    DescriptorProtocolMixin,
    InvalidationMethods,
)


class TestMixinCoverage:
    """Test mixin classes in isolation to ensure full coverage."""

    def test_invalidation_methods_init_sets_default_attributes(self) -> None:
        """Test InvalidationMethods.__init__ sets default attributes when not already present."""
        # Arrange & Act
        mixin = InvalidationMethods()

        # Assert - check that default attributes were set
        assert mixin._orchestrator is None
        assert mixin._bridge is None
        assert mixin._func is None

    def test_descriptor_protocol_mixin_init_sets_default_attributes(self) -> None:
        """Test DescriptorProtocolMixin.__init__ sets default attributes when not already present."""
        # Arrange & Act
        mixin = DescriptorProtocolMixin()

        # Assert - check that default attributes were set
        assert mixin._owner_class is None
        assert mixin._instance_bound is False

    def test_descriptor_protocol_mixin_init_preserves_existing_attributes(self) -> None:
        """Test DescriptorProtocolMixin.__init__ preserves existing attributes."""
        # Arrange
        mixin = DescriptorProtocolMixin()
        mixin._owner_class = str  # Set existing value
        mixin._instance_bound = True  # Set existing value

        # Act - reinitialize
        DescriptorProtocolMixin.__init__(mixin)

        # Assert - existing values preserved
        assert mixin._owner_class is str
        assert mixin._instance_bound is True

    def test_invalidation_methods_init_preserves_existing_attributes(self) -> None:
        """Test InvalidationMethods.__init__ preserves existing attributes."""
        # Arrange
        from unittest.mock import Mock

        mixin = InvalidationMethods()
        mixin._orchestrator = Mock()  # Set existing value
        mixin._bridge = Mock()  # Set existing value
        mixin._func = Mock()  # Set existing value

        # Act - reinitialize
        InvalidationMethods.__init__(mixin)

        # Assert - existing values preserved
        assert mixin._orchestrator is not None
        assert mixin._bridge is not None
        assert mixin._func is not None


class TestCacheableWrapperCoverage:
    """Test CacheableWrapper edge cases for full coverage."""

    def test_cacheable_wrapper_call_in_sync_context_no_running_loop(self) -> None:
        """Test __call__ method when no event loop is running (sync context)."""
        from unittest.mock import Mock

        from dapr_state_cache.decorators.cacheable import CacheableWrapper

        # Arrange
        def test_func() -> str:
            return "test_result"

        mock_orchestrator = Mock()
        mock_bridge = Mock()
        mock_bridge.run_async_in_sync.return_value = "sync_result"

        wrapper = CacheableWrapper(
            func=test_func,
            orchestrator=mock_orchestrator,
            bridge=mock_bridge,
            ttl_seconds=3600,
            condition=None,
            bypass=None,
        )

        # Act - Call from sync context (no running loop)
        result = wrapper(123)

        # Assert
        assert result == "sync_result"
        mock_bridge.run_async_in_sync.assert_called_once()

    def test_cacheable_wrapper_properties_access(self) -> None:
        """Test cache_service and orchestrator property access."""
        from unittest.mock import Mock

        from dapr_state_cache.decorators.cacheable import CacheableWrapper

        # Arrange
        mock_orchestrator = Mock()
        mock_cache_service = Mock()
        mock_orchestrator.cache_service = mock_cache_service

        wrapper = CacheableWrapper(
            func=lambda: None,
            orchestrator=mock_orchestrator,
            bridge=Mock(),
            ttl_seconds=3600,
            condition=None,
            bypass=None,
        )

        # Act & Assert
        assert wrapper.cache_service is mock_cache_service
        assert wrapper.orchestrator is mock_orchestrator

    def test_bound_method_wrapper_properties_access(self) -> None:
        """Test BoundMethodWrapper property access."""
        from unittest.mock import Mock

        from dapr_state_cache.decorators.cacheable import BoundMethodWrapper

        # Arrange
        instance = object()
        mock_cache_service = Mock()
        mock_orchestrator = Mock()
        mock_wrapper = Mock()
        mock_wrapper.__name__ = "test_method"
        mock_wrapper.__doc__ = "test doc"
        mock_wrapper.cache_service = mock_cache_service
        mock_wrapper.orchestrator = mock_orchestrator

        bound_wrapper = BoundMethodWrapper(instance, mock_wrapper)

        # Act & Assert
        assert bound_wrapper.cache_service is mock_cache_service
        assert bound_wrapper.orchestrator is mock_orchestrator
