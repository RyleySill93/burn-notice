"""Encryption utilities for storing sensitive data like API keys and client secrets."""

import base64
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data using Fernet symmetric encryption."""

    _instance: Optional['EncryptionService'] = None
    _fernet: Optional[Fernet] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._fernet is None:
            self._fernet = self._get_fernet()

    @staticmethod
    def _get_fernet() -> Fernet:
        """
        Create a Fernet instance using the DB_ENCRYPTION_KEY from settings.
        Derives a proper Fernet key from the DB_ENCRYPTION_KEY using PBKDF2.
        """
        if not settings.DB_ENCRYPTION_KEY:
            raise ValueError(
                'DB_ENCRYPTION_KEY must be set in environment variables. '
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

        password = settings.DB_ENCRYPTION_KEY.encode()

        # Use a fixed salt for deterministic key generation
        # The salt ensures the derived key is different even if the password is reused elsewhere
        salt = settings.DB_ENCRYPTION_SALT.encode('utf-8')

        # Derive a 32-byte key from the SECRET_KEY
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))

        return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string and return the encrypted value as a string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return plaintext

        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: The encrypted string to decrypt

        Returns:
            The decrypted plaintext string
        """
        if not ciphertext:
            return ciphertext

        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
            return decrypted_bytes.decode('utf-8')
        except Exception:
            # If decryption fails, return the original value
            # This helps with migration from unencrypted to encrypted data
            return ciphertext


# Singleton instance
_encryption_service = EncryptionService()


# Convenience functions for direct usage
def encrypt(plaintext: str) -> str:
    """
    Encrypt a string using the singleton EncryptionService.

    Args:
        plaintext: The string to encrypt

    Returns:
        Encrypted string
    """
    return _encryption_service.encrypt(plaintext)


def decrypt(ciphertext: str) -> str:
    """
    Decrypt an encrypted string using the singleton EncryptionService.

    Args:
        ciphertext: The encrypted string to decrypt

    Returns:
        Decrypted string
    """
    return _encryption_service.decrypt(ciphertext)
