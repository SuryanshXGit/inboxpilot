"""Symmetric token encryption helper for storing OAuth credentials at rest.

Uses authenticated counter-mode keystream encryption with HMAC-SHA256,
requiring no third-party binary C-extensions and guaranteed to work across
all platforms and environments.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from app.core.config import settings


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate a pseudo-random keystream using HMAC-SHA256 counter mode."""
    blocks: list[bytes] = []
    counter = 0
    generated = 0
    while generated < length:
        block = hmac.digest(key, nonce + counter.to_bytes(4, "big"), "sha256")
        blocks.append(block)
        counter += 1
        generated += len(block)
    return b"".join(blocks)[:length]


def encrypt_token(plain_token: str) -> str:
    """Encrypt a plaintext OAuth token or secret using authenticated keystream encryption."""
    if not plain_token:
        return ""
    key = hashlib.sha256(settings.JWT_SECRET.encode("utf-8")).digest()
    nonce = secrets.token_bytes(16)
    data = plain_token.encode("utf-8")
    stream = _keystream(key, nonce, len(data))
    ciphertext = bytes(a ^ b for a, b in zip(data, stream))
    tag = hmac.digest(key, nonce + ciphertext, "sha256")[:16]
    envelope = nonce + tag + ciphertext
    return base64.urlsafe_b64encode(envelope).decode("ascii")


def decrypt_token(cipher_token: str) -> str:
    """Decrypt a ciphertext token back to plaintext with tag verification."""
    if not cipher_token:
        return ""
    try:
        envelope = base64.urlsafe_b64decode(cipher_token.encode("ascii"))
        if len(envelope) < 32:
            return ""
        nonce = envelope[:16]
        tag = envelope[16:32]
        ciphertext = envelope[32:]
        key = hashlib.sha256(settings.JWT_SECRET.encode("utf-8")).digest()
        expected_tag = hmac.digest(key, nonce + ciphertext, "sha256")[:16]
        if not hmac.compare_digest(tag, expected_tag):
            return ""
        stream = _keystream(key, nonce, len(ciphertext))
        plain_bytes = bytes(a ^ b for a, b in zip(ciphertext, stream))
        return plain_bytes.decode("utf-8")
    except Exception:
        return ""
