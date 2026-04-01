"""Tests for innovo_backend.shared.utils (password hashing)."""
import pytest
from innovo_backend.shared.utils import hash_password, verify_password


def test_hash_password_returns_string():
    hashed = hash_password("mypassword")
    assert isinstance(hashed, str)


def test_hash_password_produces_bcrypt_format():
    hashed = hash_password("mypassword")
    # bcrypt hashes start with $2b$
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


def test_hash_password_different_salts():
    """Same password must produce different hashes (salt randomness)."""
    h1 = hash_password("same_password")
    h2 = hash_password("same_password")
    assert h1 != h2


def test_verify_password_correct():
    password = "correct_horse_battery_staple"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_empty_against_hashed():
    hashed = hash_password("notempty")
    assert verify_password("", hashed) is False


def test_hash_empty_string():
    hashed = hash_password("")
    assert verify_password("", hashed) is True


def test_hash_unicode_password():
    password = "pässwörd_üñícode"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
    assert verify_password("passwort", hashed) is False
