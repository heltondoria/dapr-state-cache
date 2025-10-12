"""
Backend constants for Dapr State Cache.

Defines all magic numbers and configuration values used across
the backend module to improve maintainability and readability.
"""

# Timeout configuration
DEFAULT_TIMEOUT_SECONDS: float = 5.0
"""Default timeout for Dapr operations in seconds."""

# TTL configuration
MIN_TTL_SECONDS: int = 1
"""Minimum TTL value in seconds (Dapr constraint)."""

# Dapr configuration
DEFAULT_STORE_NAME: str = "state-store"
"""Default state store name if not specified."""

# Error handling
DAPR_NOT_CONFIGURED_INDICATORS = ["not configured", "not found"]
"""String indicators that suggest Dapr state store is not configured."""

DAPR_TIMEOUT_INDICATORS = ["timeout"]
"""String indicators that suggest operation timed out."""
