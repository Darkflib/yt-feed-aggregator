"""Cryptographic utilities for token encryption."""

import base64


def validate_encryption_key(enc_key: str | bytes) -> bytes:
    """
    Validate and convert encryption key to 32-byte format.

    The encryption key must be exactly 32 bytes when decoded. String keys
    must be base64-encoded.

    Args:
        enc_key: Encryption key as base64 string or raw bytes

    Returns:
        32-byte encryption key

    Raises:
        ValueError: If key is invalid format or wrong length

    Example:
        >>> import secrets, base64
        >>> key = base64.b64encode(secrets.token_bytes(32)).decode()
        >>> key_bytes = validate_encryption_key(key)
        >>> len(key_bytes)
        32
    """
    if isinstance(enc_key, str):
        try:
            enc_key_bytes = base64.b64decode(enc_key, validate=True)
        except Exception as e:
            raise ValueError(
                "Encryption key must be base64-encoded. "
                'Generate with: python -c "import secrets, base64; '
                'print(base64.b64encode(secrets.token_bytes(32)).decode())"'
            ) from e
    else:
        enc_key_bytes = enc_key

    if len(enc_key_bytes) != 32:
        raise ValueError(
            f"Encryption key must be exactly 32 bytes, got {len(enc_key_bytes)} bytes. "
            f'Generate with: python -c "import secrets, base64; '
            f'print(base64.b64encode(secrets.token_bytes(32)).decode())"'
        )

    return enc_key_bytes
