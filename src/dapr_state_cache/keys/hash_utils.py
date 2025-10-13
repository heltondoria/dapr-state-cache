"""
Hash utilities for deterministic cache key generation.

Provides SHA256-based hashing functions that ensure consistent and stable
cache keys across different executions and Python versions.
"""

import hashlib


def calculate_deterministic_hash(data: str) -> str:
    """Calculate SHA256 hash of string data.

    Creates a deterministic hash that is stable across Python versions
    and executions. Used for generating consistent cache keys.

    Args:
        data: String data to hash

    Returns:
        Hexadecimal hash string (64 characters)
    """
    # Use UTF-8 encoding for consistent byte representation
    data_bytes = data.encode("utf-8")

    # Calculate SHA256 hash
    hash_obj = hashlib.sha256(data_bytes)

    # Return hexadecimal representation
    return hash_obj.hexdigest()


def calculate_hash_for_args(serialized_args: str) -> str:
    """Calculate hash specifically for function arguments.

    Wrapper around calculate_deterministic_hash for semantic clarity
    when hashing serialized function arguments.

    Args:
        serialized_args: JSON-serialized representation of function arguments

    Returns:
        Hexadecimal hash string
    """
    return calculate_deterministic_hash(serialized_args)


def truncate_hash(full_hash: str, length: int = 16) -> str:
    """Truncate hash to specified length for shorter keys.

    Takes the first N characters of a hash for use cases where
    full hash length is not needed or desired.

    Args:
        full_hash: Full hexadecimal hash string
        length: Number of characters to keep (default: 16)

    Returns:
        Truncated hash string

    Raises:
        ValueError: If length is greater than full hash length
    """
    if length > len(full_hash):
        raise ValueError(f"Requested length {length} exceeds hash length {len(full_hash)}")

    return full_hash[:length]


def create_cache_key(prefix: str, function_path: str, args_hash: str) -> str:
    """Create final cache key from components.

    Combines prefix, function path, and arguments hash into the final
    cache key format: {prefix}:{function_path}:{args_hash}

    Args:
        prefix: Key prefix (typically "cache" or custom value)
        function_path: Full path to function (module.class.function)
        args_hash: Hash of serialized function arguments

    Returns:
        Complete cache key string

    Raises:
        ValueError: If any component is empty
    """
    if not prefix:
        raise ValueError("Key prefix cannot be empty")

    if not function_path:
        raise ValueError("Function path cannot be empty")

    if not args_hash:
        raise ValueError("Arguments hash cannot be empty")

    return f"{prefix}:{function_path}:{args_hash}"
