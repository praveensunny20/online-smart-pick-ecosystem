"""
Encryption utility for sensitive data (platform API credentials, tokens, etc.)

Uses Fernet symmetric encryption from the `cryptography` library.
Fernet = AES-128-CBC + HMAC-SHA256 (authenticated encryption).

For true AES-256 we use a custom implementation wrapping AES-256-GCM below.
Platform credentials will be encrypted at rest in the database.
"""
import base64
import json
import os
from typing import Any, Dict

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data using AES-256-GCM.

    AES-256-GCM is an authenticated encryption mode:
    - AES-256 = 256-bit symmetric encryption (very strong)
    - GCM = Galois/Counter Mode — provides authentication (detects tampering)

    The key is stored in ENCRYPTION_KEY env var (must be 32 bytes, base64-encoded = 44 chars).
    """

    def __init__(self, key: str | None = None):
        """
        Initialize with encryption key.

        Args:
            key: Base64-encoded 32-byte key. If None, uses settings.ENCRYPTION_KEY.
        """
        key_str = key or settings.ENCRYPTION_KEY
        if not key_str:
            raise ValueError("ENCRYPTION_KEY is not set. Generate one with generate_key().")

        # Decode the base64 key to raw bytes (must be exactly 32 bytes for AES-256)
        try:
            key_bytes = base64.urlsafe_b64decode(key_str.encode("utf-8"))
        except Exception as e:
            raise ValueError(f"ENCRYPTION_KEY is not valid base64: {e}")

        if len(key_bytes) != 32:
            raise ValueError(
                f"ENCRYPTION_KEY must decode to exactly 32 bytes (got {len(key_bytes)}). "
                "Generate a valid key with EncryptionService.generate_key()."
            )

        self._key = key_bytes
        self._aesgcm = AESGCM(self._key)

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new 32-byte AES-256 key, returned as url-safe base64 string.
        Use this once to create the ENCRYPTION_KEY value for your .env file.
        """
        key_bytes = AESGCM.generate_key(bit_length=256)
        return base64.urlsafe_b64encode(key_bytes).decode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Returns base64-encoded string containing:
            [12 bytes nonce][ciphertext + 16 bytes auth tag]

        Args:
            plaintext: The string to encrypt.

        Returns:
            Base64-encoded encrypted string, safe to store in a text column.
        """
        if not isinstance(plaintext, str):
            raise TypeError("plaintext must be a string")

        # Nonce must be unique for every encryption with the same key.
        # 12 bytes (96 bits) is the recommended size for GCM.
        nonce = os.urandom(12)

        plaintext_bytes = plaintext.encode("utf-8")
        # encrypt() returns ciphertext with the 16-byte auth tag appended
        ciphertext = self._aesgcm.encrypt(nonce, plaintext_bytes, associated_data=None)

        # Prepend nonce so we can decrypt later (nonce is not secret, just unique)
        combined = nonce + ciphertext
        return base64.urlsafe_b64encode(combined).decode("utf-8")

    def decrypt(self, ciphertext_b64: str) -> str:
        """
        Decrypt a string previously encrypted with encrypt().

        Args:
            ciphertext_b64: Base64 string produced by encrypt().

        Returns:
            The original plaintext string.

        Raises:
            cryptography.exceptions.InvalidTag: If data was tampered with or key is wrong.
        """
        if not isinstance(ciphertext_b64, str):
            raise TypeError("ciphertext must be a string")

        combined = base64.urlsafe_b64decode(ciphertext_b64.encode("utf-8"))

        if len(combined) < 12 + 16:
            raise ValueError("Ciphertext too short — must contain nonce + tag + data")

        nonce = combined[:12]
        ciphertext = combined[12:]

        plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext, associated_data=None)
        return plaintext_bytes.decode("utf-8")

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """
        Serialize a dict to JSON and encrypt it.
        Useful for storing OAuth tokens + refresh tokens + metadata together.
        """
        json_str = json.dumps(data, separators=(",", ":"), sort_keys=True)
        return self.encrypt(json_str)

    def decrypt_dict(self, ciphertext_b64: str) -> Dict[str, Any]:
        """Decrypt and parse JSON back to dict."""
        json_str = self.decrypt(ciphertext_b64)
        return json.loads(json_str)


# Singleton instance — created on first import, reused everywhere
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get the singleton EncryptionService instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
