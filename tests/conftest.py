"""
Test configuration and shared fixtures.

Provides cleanup for threads and async resources to prevent test hanging.
"""

import pytest
import asyncio
import threading
from typing import Any

def pytest_configure(config: Any) -> None:
    """Configure pytest with thread and async cleanup."""
    # Ensure proper cleanup of resources
    import atexit
    from src.dapr_state_cache.core.sync_async_bridge import shutdown_thread_pool
    
    def cleanup() -> None:
        """Clean up resources on exit."""
        shutdown_thread_pool()
    
    atexit.register(cleanup)

@pytest.fixture(autouse=True)
def cleanup_threads():
    """Automatically cleanup threads after each test."""
    yield
    
    # Clean up thread pool after each test
    try:
        from src.dapr_state_cache.core.sync_async_bridge import shutdown_thread_pool, _reset_default_bridge
        shutdown_thread_pool()
        _reset_default_bridge()
    except ImportError:
        # Modules might not be loaded yet
        pass
    
    # Wait a bit for threads to cleanup
    import time
    time.sleep(0.05)

@pytest.fixture(autouse=True)
def cleanup_async_resources():
    """Automatically cleanup async resources after each test."""
    yield
    
    # Close any pending event loops
    try:
        loop = asyncio.get_running_loop()
        if loop and not loop.is_closed():
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            if pending:
                for task in pending:
                    if not task.done():
                        task.cancel()
                
                # Give tasks a chance to cleanup
                loop.run_until_complete(asyncio.sleep(0.01))
    except RuntimeError:
        # No running loop, which is fine
        pass

@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state between tests."""
    yield
    
    # Reset the default bridge
    from src.dapr_state_cache.core.sync_async_bridge import _reset_default_bridge
    try:
        _reset_default_bridge()
    except:
        # Function might not exist yet, ignore
        pass
