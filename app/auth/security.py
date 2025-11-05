"""Security utilities for token encryption and decryption."""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_refresh_token(key: bytes, plaintext: str) -> bytes:
    """
    Encrypt a refresh token using AES-GCM.

    Args:
        key: 32-byte encryption key (AES-256)
        plaintext: The refresh token string to encrypt

    Returns:
        Encrypted blob with nonce prepended (12 bytes nonce + ciphertext)
    """
    if len(key) != 32:
        raise ValueError("Encryption key must be exactly 32 bytes for AES-256")

    aes = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_refresh_token(key: bytes, blob: bytes) -> str:
    """
    Decrypt a refresh token using AES-GCM.

    Args:
        key: 32-byte encryption key (AES-256)
        blob: Encrypted data with nonce prepended

    Returns:
        Decrypted refresh token string

    Raises:
        ValueError: If key length is invalid
        cryptography.exceptions.InvalidTag: If decryption fails (wrong key or tampered data)
    """
    if len(key) != 32:
        raise ValueError("Encryption key must be exactly 32 bytes for AES-256")

    if len(blob) < 12:
        raise ValueError("Encrypted blob too short (must include 12-byte nonce)")

    aes = AESGCM(key)
    nonce = blob[:12]
    ciphertext = blob[12:]
    plaintext = aes.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
