"""Security and cryptographic utilities for Cadence backend.

Handles:
- Argon2id password hashing, verification, and rehash checks.
- JWT access and refresh token generation, expiration, and decoding.
- Token type verification and security exceptions.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from core.config import settings

# Password hasher instance with default Argon2id parameters
_hasher = PasswordHasher()

# Token types
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class SecurityError(Exception):
    """Base exception for security-related errors."""


class TokenError(SecurityError):
    """Base exception for JWT token errors."""


class TokenExpiredError(TokenError):
    """Raised when a JWT token has expired."""


class InvalidTokenError(TokenError):
    """Raised when a JWT token is invalid, malformed, or has an invalid type."""


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using Argon2id.

    Args:
        plain_password: The plaintext password string to hash.

    Returns:
        The Argon2 hash string.

    Raises:
        ValueError: If plain_password is empty or not a string.
    """
    if not plain_password or not isinstance(plain_password, str):
        raise ValueError("Password must be a non-empty string.")
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against an Argon2 hash.

    Args:
        plain_password: The plaintext password candidate.
        hashed_password: The stored Argon2 hash string.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Check if the hashed password needs to be rehashed.

    Args:
        hashed_password: The stored Argon2 hash string.

    Returns:
        True if rehash is recommended, False otherwise.
    """
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except (InvalidHashError, VerificationError):
        return True


def create_access_token(
    subject: str | int,
    role: str | None = None,
    scopes: dict[str, Any] | None = None,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT access token.

    Args:
        subject: The unique user identifier (stored in 'sub').
        role: User role (e.g., 'CO', 'ANO', 'JUO', 'Leader', 'Cadet').
        scopes: Dictionary containing unit, squad, or other scope constraints.
        extra_claims: Additional metadata or custom claims.
        expires_delta: Custom token lifetime. Defaults to
            settings.access_token_expire_minutes.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire_at = now + expires_delta
    else:
        expire_at = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(expire_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    if role is not None:
        payload["role"] = role

    if scopes is not None:
        payload["scopes"] = scopes

    if extra_claims:
        # Prevent overwriting critical claims
        for key, value in extra_claims.items():
            if key not in ("sub", "type", "iat", "exp", "jti"):
                payload[key] = value

    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str | int,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT refresh token.

    Args:
        subject: The unique user identifier (stored in 'sub').
        extra_claims: Additional metadata or custom claims.
        expires_delta: Custom lifetime. Defaults to settings.refresh_token_expire_days.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire_at = now + expires_delta
    else:
        expire_at = now + timedelta(days=settings.refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": TOKEN_TYPE_REFRESH,
        "iat": int(now.timestamp()),
        "exp": int(expire_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    if extra_claims:
        for key, value in extra_claims.items():
            if key not in ("sub", "type", "iat", "exp", "jti"):
                payload[key] = value

    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(
    token: str,
    expected_type: str | None = None,
) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The encoded JWT token string.
        expected_type: Optional expected token type (e.g. 'access' or 'refresh').

    Returns:
        The decoded payload dictionary.

    Raises:
        TokenExpiredError: If the token expiration time ('exp') is in the past.
        InvalidTokenError: If the token is invalid, has an invalid signature,
                           is missing 'sub', or does not match expected_type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired.") from e
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Token is invalid: {e}") from e

    token_type = payload.get("type")
    if expected_type is not None and token_type != expected_type:
        raise InvalidTokenError(
            f"Invalid token type: expected '{expected_type}', got '{token_type}'."
        )

    return payload
