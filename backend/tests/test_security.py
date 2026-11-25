"""Unit tests for core/security.py."""

import time
from datetime import timedelta

import jwt
import pytest

from core.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)


def test_hash_password_success():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True


def test_verify_password_failure():
    password = "CorrectPassword123!"
    wrong_password = "WrongPassword123!"
    hashed = hash_password(password)

    assert verify_password(wrong_password, hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, "") is False
    assert verify_password(password, "invalid_hash_string") is False


def test_hash_password_invalid_input():
    with pytest.raises(ValueError):
        hash_password("")

    with pytest.raises(ValueError):
        hash_password(None)  # type: ignore


def test_needs_rehash():
    password = "TestPassword123!"
    hashed = hash_password(password)

    # A freshly created hash with default parameters does not need rehash
    assert needs_rehash(hashed) is False
    # Malformed hash should return True
    assert needs_rehash("corrupted_hash") is True


def test_create_and_decode_access_token():
    subject = "user-123"
    role = "JUO"
    scopes = {"unit_id": 1, "squad_id": 4}

    token = create_access_token(
        subject=subject,
        role=role,
        scopes=scopes,
        extra_claims={"email": "juo@cadence.ncc"},
    )

    payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)

    assert payload["sub"] == subject
    assert payload["type"] == TOKEN_TYPE_ACCESS
    assert payload["role"] == role
    assert payload["scopes"] == scopes
    assert payload["email"] == "juo@cadence.ncc"
    assert "jti" in payload
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_create_and_decode_refresh_token():
    subject = "user-456"

    token = create_refresh_token(subject=subject)
    payload = decode_token(token, expected_type=TOKEN_TYPE_REFRESH)

    assert payload["sub"] == subject
    assert payload["type"] == TOKEN_TYPE_REFRESH
    assert "jti" in payload
    assert "exp" in payload


def test_token_type_mismatch():
    subject = "user-789"
    access_token = create_access_token(subject=subject)
    refresh_token = create_refresh_token(subject=subject)

    # Attempting to decode an access token when expecting refresh
    with pytest.raises(InvalidTokenError, match="Invalid token type"):
        decode_token(access_token, expected_type=TOKEN_TYPE_REFRESH)

    # Attempting to decode a refresh token when expecting access
    with pytest.raises(InvalidTokenError, match="Invalid token type"):
        decode_token(refresh_token, expected_type=TOKEN_TYPE_ACCESS)


def test_token_expiration():
    subject = "user-expired"
    # Token with negative delta (already expired)
    expired_token = create_access_token(
        subject=subject, expires_delta=timedelta(seconds=-1)
    )

    with pytest.raises(TokenExpiredError, match="Token has expired"):
        decode_token(expired_token)


def test_tampered_token():
    token = create_access_token(subject="user-real")
    tampered_token = token[:-5] + "abcde"

    with pytest.raises(InvalidTokenError):
        decode_token(tampered_token)


def test_wrong_secret_signature():
    payload = {
        "sub": "user-rogue",
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(time.time()),
        "exp": int(time.time() + 300),
    }
    secret = "different_secret_key_that_is_at_least_32_bytes_long"
    rogue_token = jwt.encode(payload, secret, algorithm="HS256")

    with pytest.raises(InvalidTokenError):
        decode_token(rogue_token)


def test_extra_claims_cannot_override_critical_claims():
    token = create_access_token(
        subject="real-user",
        extra_claims={"sub": "hijacked-user", "type": "refresh"},
    )
    payload = decode_token(token)

    assert payload["sub"] == "real-user"
    assert payload["type"] == TOKEN_TYPE_ACCESS
