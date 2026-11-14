"""Local JWT authentication and password hashing helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

_PASSWORD_ALGORITHM = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 260_000
_PASSWORD_SALT_BYTES = 16
_MAX_PASSWORD_BYTES = 1024


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a random per-user salt."""

    password_bytes = password.encode("utf-8")
    if len(password_bytes) > _MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long")

    salt = secrets.token_bytes(_PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password_bytes,
        salt,
        _PASSWORD_ITERATIONS,
    )
    return (
        f"{_PASSWORD_ALGORITHM}${_PASSWORD_ITERATIONS}"
        f"${_b64encode(salt)}${_b64encode(digest)}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash."""

    try:
        algorithm, iterations, encoded_salt, encoded_digest = stored_hash.split("$", 3)
        if algorithm != _PASSWORD_ALGORITHM:
            return False
        salt = _b64decode(encoded_salt)
        expected_digest = _b64decode(encoded_digest)
        candidate_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
    except (AttributeError, TypeError, ValueError):
        return False

    return hmac.compare_digest(candidate_digest, expected_digest)


def create_access_token(user_id: str) -> str:
    """Create a signed HS256 access token whose ``sub`` is the user id."""

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _credentials_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    """FastAPI dependency returning the authenticated user's id (JWT ``sub``)."""

    if credentials is None or not credentials.credentials:
        raise _credentials_error("Not authenticated")

    if credentials.scheme.lower() != "bearer":
        raise _credentials_error("Invalid authentication scheme")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _credentials_error("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _credentials_error("Invalid token") from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise _credentials_error("Invalid token payload")

    return user_id
