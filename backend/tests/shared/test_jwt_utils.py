"""Tests for innovo_backend.shared.jwt_utils."""
import time
import pytest
from innovo_backend.shared.jwt_utils import (
    create_access_token,
    verify_token,
    create_password_reset_token,
    verify_password_reset_token,
)


# ---------------------------------------------------------------------------
# create_access_token / verify_token
# ---------------------------------------------------------------------------

def test_create_access_token_returns_string():
    token = create_access_token({"email": "test@innovo-consulting.de"})
    assert isinstance(token, str)
    assert len(token) > 20


def test_verify_token_valid():
    email = "user@aiio.de"
    token = create_access_token({"email": email})
    payload = verify_token(token)
    assert payload is not None
    assert payload["email"] == email


def test_verify_token_has_exp():
    token = create_access_token({"email": "user@aiio.de"})
    payload = verify_token(token)
    assert "exp" in payload


def test_verify_token_invalid_signature():
    token = create_access_token({"email": "user@aiio.de"})
    # Tamper with the signature
    tampered = token[:-4] + "XXXX"
    assert verify_token(tampered) is None


def test_verify_token_garbage():
    assert verify_token("not.a.jwt.token") is None


def test_verify_token_empty_string():
    assert verify_token("") is None


# ---------------------------------------------------------------------------
# create_password_reset_token / verify_password_reset_token
# ---------------------------------------------------------------------------

def test_create_password_reset_token_returns_string():
    token = create_password_reset_token("user@aiio.de")
    assert isinstance(token, str)


def test_verify_password_reset_token_valid():
    email = "reset@innovo-consulting.de"
    token = create_password_reset_token(email)
    result = verify_password_reset_token(token)
    assert result == email


def test_verify_password_reset_token_rejects_access_token():
    """An access token must not be accepted as a password reset token."""
    access_token = create_access_token({"email": "user@aiio.de"})
    result = verify_password_reset_token(access_token)
    assert result is None


def test_verify_password_reset_token_invalid():
    assert verify_password_reset_token("garbage.token.here") is None


def test_verify_password_reset_token_tampered():
    token = create_password_reset_token("user@aiio.de")
    tampered = token[:-4] + "XXXX"
    assert verify_password_reset_token(tampered) is None
