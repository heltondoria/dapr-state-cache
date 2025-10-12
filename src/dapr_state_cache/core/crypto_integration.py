"""
Integration with Dapr Cryptography building block.

Provides encryption and decryption capabilities using Dapr's native
cryptography API with graceful error handling and fallback mechanisms.
"""

import logging
from typing import Any

from ..backend.exceptions import RecoverableCacheError
from .constants import (
    DEFAULT_CRYPTO_ALGORITHM,
    DEFAULT_CRYPTO_KEY_NAME,
    ERROR_CRYPTO_COMPONENT_REQUIRED,
)

logger = logging.getLogger(__name__)


class DaprCryptoError(RecoverableCacheError):
    """Error related to Dapr cryptography operations.

    This is a recoverable error that should not break the cache flow.
    Operations should fall back to plaintext when this occurs.
    """

    pass


class CryptoIntegration:
    """Integration with Dapr Cryptography building block.

    Provides encryption and decryption services using Dapr's native
    cryptography API. Implements graceful error handling with fallback
    to plaintext operations when cryptography is unavailable.

    Features:
    - Encryption using Dapr Cryptography API
    - Graceful fallback on cryptography errors
    - Lazy initialization of Dapr client
    - Support for different crypto components
    - Error recovery and logging
    """

    def __init__(self, crypto_component_name: str, dapr_client: Any | None = None) -> None:
        """Initialize crypto integration.

        Args:
            crypto_component_name: Name of Dapr crypto component
            dapr_client: Optional DaprClient instance (lazy init if None)
        """
        self._crypto_component_name = crypto_component_name
        self._dapr_client = dapr_client
        self._crypto_available = True  # Assume available until proven otherwise

    async def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using Dapr Cryptography.

        Args:
            data: Raw bytes to encrypt

        Returns:
            Encrypted bytes

        Raises:
            DaprCryptoError: If encryption fails (recoverable error)
        """
        if not self._crypto_available:
            logger.debug("Cryptography marked as unavailable, skipping encryption")
            return data

        try:
            client = await self._get_dapr_client()

            logger.debug(f"Encrypting {len(data)} bytes using component '{self._crypto_component_name}'")

            # Use Dapr Cryptography API
            encrypt_response = await client.encrypt(
                data=data,
                component_name=self._crypto_component_name,
                key_name=DEFAULT_CRYPTO_KEY_NAME,
                algorithm=DEFAULT_CRYPTO_ALGORITHM,
            )

            encrypted_data = encrypt_response.data
            logger.debug(f"Successfully encrypted to {len(encrypted_data)} bytes")
            return encrypted_data

        except ImportError as e:
            logger.error(f"Dapr client not available for cryptography: {e}. Falling back to plaintext storage.")
            self._crypto_available = False
            raise DaprCryptoError(f"Dapr client not available: {e}") from e

        except Exception as e:
            logger.error(
                f"Failed to encrypt data using component '{self._crypto_component_name}': {e}. "
                "Falling back to plaintext storage."
            )
            raise DaprCryptoError(f"Encryption failed: {e}") from e

    async def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt data using Dapr Cryptography.

        Args:
            encrypted_data: Encrypted bytes to decrypt

        Returns:
            Decrypted bytes

        Raises:
            DaprCryptoError: If decryption fails (recoverable error)
        """
        if not self._crypto_available:
            logger.debug("Cryptography marked as unavailable, treating as plaintext")
            return encrypted_data

        try:
            client = await self._get_dapr_client()

            logger.debug(f"Decrypting {len(encrypted_data)} bytes using component '{self._crypto_component_name}'")

            # Use Dapr Cryptography API
            decrypt_response = await client.decrypt(
                data=encrypted_data,
                component_name=self._crypto_component_name,
                key_name=DEFAULT_CRYPTO_KEY_NAME,
            )

            decrypted_data = decrypt_response.data
            logger.debug(f"Successfully decrypted to {len(decrypted_data)} bytes")
            return decrypted_data

        except ImportError as e:
            logger.error(f"Dapr client not available for cryptography: {e}. Treating data as plaintext.")
            self._crypto_available = False
            raise DaprCryptoError(f"Dapr client not available: {e}") from e

        except Exception as e:
            logger.error(
                f"Failed to decrypt data using component '{self._crypto_component_name}': {e}. Treating as cache miss."
            )
            raise DaprCryptoError(f"Decryption failed: {e}") from e

    async def is_available(self) -> bool:
        """Check if cryptography is available.

        Returns:
            True if crypto operations are available, False otherwise
        """
        if not self._crypto_available:
            return False

        try:
            client = await self._get_dapr_client()
            # Simple availability check - try to access the client
            return client is not None
        except Exception:
            self._crypto_available = False
            return False

    async def _get_dapr_client(self) -> Any:
        """Get Dapr client instance with lazy initialization.

        Returns:
            DaprClient instance

        Raises:
            ImportError: If Dapr client cannot be imported/created
        """
        if self._dapr_client is None:
            try:
                from dapr.clients import DaprClient  # type: ignore[import-not-found]

                self._dapr_client = DaprClient()
                logger.debug("Initialized Dapr client for cryptography")
            except ImportError as e:
                logger.error(f"Failed to import DaprClient: {e}")
                raise ImportError(f"Dapr client not available: {e}") from e

        return self._dapr_client

    @property
    def crypto_component_name(self) -> str:
        """Get the crypto component name."""
        return self._crypto_component_name

    def reset_availability(self) -> None:
        """Reset crypto availability flag.

        Useful for testing or recovering from temporary failures.
        """
        self._crypto_available = True
        logger.debug("Reset cryptography availability flag")


class NoOpCryptoIntegration:
    """No-operation crypto integration for when cryptography is disabled.

    This implementation performs no encryption/decryption, effectively
    passing data through unchanged. Used when use_dapr_crypto=False.
    """

    def __init__(self) -> None:
        """Initialize no-op crypto integration."""
        pass

    async def encrypt(self, data: bytes) -> bytes:
        """Pass-through encryption (no-op).

        Args:
            data: Data to "encrypt"

        Returns:
            Same data unchanged
        """
        return data

    async def decrypt(self, encrypted_data: bytes) -> bytes:
        """Pass-through decryption (no-op).

        Args:
            encrypted_data: Data to "decrypt"

        Returns:
            Same data unchanged
        """
        return encrypted_data

    async def is_available(self) -> bool:
        """Always returns True for no-op implementation.

        Returns:
            True (no-op is always "available")
        """
        return True

    @property
    def crypto_component_name(self) -> str:
        """Get component name (none for no-op).

        Returns:
            Empty string indicating no crypto component
        """
        return ""

    def reset_availability(self) -> None:
        """No-op for availability reset."""
        pass


def create_crypto_integration(
    use_dapr_crypto: bool, crypto_component_name: str | None = None, dapr_client: Any | None = None
) -> CryptoIntegration | NoOpCryptoIntegration:
    """Create appropriate crypto integration based on configuration.

    Args:
        use_dapr_crypto: Whether to use Dapr cryptography
        crypto_component_name: Name of crypto component (required if use_dapr_crypto=True)
        dapr_client: Optional DaprClient instance

    Returns:
        CryptoIntegration or NoOpCryptoIntegration instance

    Raises:
        ValueError: If use_dapr_crypto=True but no component name provided
    """
    if not use_dapr_crypto:
        logger.debug("Cryptography disabled, using no-op implementation")
        return NoOpCryptoIntegration()

    if not crypto_component_name:
        raise ValueError(ERROR_CRYPTO_COMPONENT_REQUIRED)

    logger.debug(f"Cryptography enabled using component '{crypto_component_name}'")
    return CryptoIntegration(crypto_component_name=crypto_component_name, dapr_client=dapr_client)
