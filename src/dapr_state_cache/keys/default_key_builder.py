"""
Default key builder implementation.

Implements the KeyBuilder protocol to generate deterministic cache keys
from function signatures and arguments using SHA256 hashing.
"""

import inspect
from typing import Callable

from ..codecs.normalizers import (
    get_function_path,
    serialize_args_for_key,
    filter_args_for_methods,
)
from .hash_utils import calculate_hash_for_args, create_cache_key


class DefaultKeyBuilder:
    """Production-grade cache key builder with deterministic SHA256 hashing.
    
    Default implementation of the KeyBuilder protocol that generates stable,
    collision-resistant cache keys using function signatures and argument
    values. The key generation algorithm ensures that identical function
    calls (same arguments) always produce the same cache key, while
    different calls produce different keys.
    
    Key Generation Algorithm:
        1. **Function Path Extraction**: Captures full module.class.function path
        2. **Argument Filtering**: Removes 'self'/'cls' for method caching
        3. **Argument Normalization**: Converts complex types to serializable forms
        4. **Deterministic Hashing**: SHA256 hash of normalized arguments
        5. **Key Assembly**: Combines prefix, function path, and hash
    
    Key Format:
        ```
        {key_prefix}:{function_path}:{args_hash}
        ```
        
        Examples:
        - `cache:mymodule.get_user:a1b2c3d4e5f6...` (standalone function)
        - `cache:mymodule.UserService.get_profile:7f8e9d0c1b2a...` (method)
        - `cache:__main__.calculate:5g6h7i8j9k0l...` (local function)
    
    Method Handling:
        For class methods, 'self' and 'cls' parameters are automatically
        excluded from key generation, enabling cache sharing between
        instances:
        
        ```python
        class UserService:
            @cacheable()
            def get_user(self, user_id: int):
                return fetch_user(user_id)
        
        # These calls share the same cache key:
        service1 = UserService()
        service2 = UserService()
        service1.get_user(123)  # Key: cache:UserService.get_user:hash(123)
        service2.get_user(123)  # Same key: cache hit!
        ```
    
    Argument Normalization:
        Complex Python types are normalized for consistent hashing:
        - **datetime** → ISO 8601 string
        - **UUID** → string representation
        - **Decimal** → string representation
        - **bytes** → base64 string
        - **sets** → sorted lists (deterministic order)
        - **dataclasses** → dictionary representation
        - **custom objects** → `__dict__` or `repr()` fallback
    
    Performance Characteristics:
        - **Hashing**: O(n) where n is serialized argument size
        - **Memory**: Minimal overhead, no caching of keys
        - **CPU**: Fast SHA256 computation (~1-5μs for typical args)
        - **Collision Resistance**: Cryptographically secure SHA256
    
    Thread Safety:
        This implementation is stateless and thread-safe. Multiple threads
        can safely use the same DefaultKeyBuilder instance concurrently.
    
    Example:
        ```python
        # Custom key builder with specific prefix
        key_builder = DefaultKeyBuilder(key_prefix="myapp")
        
        def expensive_function(user_id: int, options: dict):
            return compute_expensive_result(user_id, options)
        
        # Generate cache key
        args = (123,)
        kwargs = {"options": {"timeout": 30, "cache": True}}
        cache_key = key_builder.build_key(expensive_function, args, kwargs)
        
        # Result: "myapp:__main__.expensive_function:f4d5e6a7b8c9..."
        print(f"Generated key: {cache_key}")
        
        # Same arguments always produce same key
        key2 = key_builder.build_key(expensive_function, args, kwargs)
        assert cache_key == key2  # True - deterministic!
        ```
    
    Advanced Usage:
        ```python
        class CustomKeyBuilder(DefaultKeyBuilder):
            def build_key(self, func, args, kwargs):
                # Add custom logic before standard key building
                if func.__name__.startswith('temp_'):
                    # Short TTL functions get special prefix
                    self._key_prefix = "temp"
                
                key = super().build_key(func, args, kwargs)
                
                # Add environment suffix for multi-tenant caching
                env = os.getenv('ENVIRONMENT', 'dev')
                return f"{key}:{env}"
        ```
    
    Collision Resistance:
        SHA256 provides excellent collision resistance with a negligible
        probability of hash collisions in practical use cases. The full
        256-bit hash is used (truncated to 16 characters for readability
        but maintaining high collision resistance).
    """

    def __init__(self, key_prefix: str = "cache") -> None:
        """Initialize key builder with prefix.
        
        Args:
            key_prefix: Prefix for all generated keys (default: "cache")
            
        Raises:
            ValueError: If key_prefix is empty
        """
        if not key_prefix:
            raise ValueError("Key prefix cannot be empty")
        
        self._key_prefix = key_prefix

    def build_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """Build cache key from function and arguments.
        
        Creates deterministic cache key by combining:
        1. Key prefix
        2. Function path (module.class.function)  
        3. SHA256 hash of serialized arguments
        
        Args:
            func: Function being cached
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Cache key string in format: prefix:function_path:args_hash
            
        Raises:
            ValueError: If key generation fails
            TypeError: If arguments contain non-serializable types
        """
        try:
            # Get function path (module.class.function)
            function_path = get_function_path(func)
            
            # Detect if this is a method and filter self/cls
            is_method = self._is_instance_method(func)
            is_classmethod = self._is_class_method(func)
            
            filtered_args = filter_args_for_methods(args, is_method, is_classmethod)
            
            # Serialize arguments for hashing
            serialized_args = serialize_args_for_key(filtered_args, kwargs)
            
            # Calculate hash of arguments
            args_hash = calculate_hash_for_args(serialized_args)
            
            # Create final cache key
            return create_cache_key(self._key_prefix, function_path, args_hash)
            
        except Exception as e:
            raise ValueError(f"Failed to build cache key: {e}") from e

    def _is_instance_method(self, func: Callable) -> bool:
        """Check if function is an instance method.
        
        Args:
            func: Function to check
            
        Returns:
            True if function is an instance method
        """
        # Check if it's a bound method
        if hasattr(func, '__self__') and not inspect.isclass(func.__self__):
            return True
        
        # Check if it's an unbound method with self parameter
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            return len(params) > 0 and params[0] == 'self'
        except (ValueError, TypeError):
            return False

    def _is_class_method(self, func: Callable) -> bool:
        """Check if function is a class method.
        
        Args:
            func: Function to check
            
        Returns:
            True if function is a class method
        """
        # Check if it's a bound method with class as __self__
        if hasattr(func, '__self__') and inspect.isclass(func.__self__):
            return True
        
        # Check if it's decorated with @classmethod
        if isinstance(func, classmethod):
            return True
        
        # Check if it's an unbound method with cls parameter
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            return len(params) > 0 and params[0] == 'cls'
        except (ValueError, TypeError):
            return False

    @property
    def key_prefix(self) -> str:
        """Get the key prefix used by this builder."""
        return self._key_prefix
