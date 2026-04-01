"""Tests for innovo_backend.services.auth.router."""
import pytest


VALID_EMAIL = "authtest@innovo-consulting.de"
VALID_PASSWORD = "securepassword123"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/auth/register",
            json={"email": VALID_EMAIL, "password": VALID_PASSWORD},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True

    def test_register_duplicate_returns_409(self, client):
        payload = {"email": VALID_EMAIL, "password": VALID_PASSWORD}
        client.post("/auth/register", json=payload)
        resp = client.post("/auth/register", json=payload)
        assert resp.status_code == 409

    def test_register_invalid_email_domain(self, client):
        resp = client.post(
            "/auth/register",
            json={"email": "user@gmail.com", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        resp = client.post(
            "/auth/register",
            json={"email": VALID_EMAIL, "password": "abc"},
        )
        assert resp.status_code == 422

    def test_register_aiio_domain(self, client):
        resp = client.post(
            "/auth/register",
            json={"email": "user@aiio.de", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 201

    def test_register_email_lowercased(self, client):
        resp = client.post(
            "/auth/register",
            json={"email": "UPPER@innovo-consulting.de", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 201
        # Second registration with lowercase should conflict
        resp2 = client.post(
            "/auth/register",
            json={"email": "upper@innovo-consulting.de", "password": VALID_PASSWORD},
        )
        assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_success(self, client):
        client.post("/auth/register", json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
        resp = client.post("/auth/login", json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["success"] is True

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
        resp = client.post("/auth/login", json={"email": VALID_EMAIL, "password": "wrongpass"})
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        resp = client.post(
            "/auth/login",
            json={"email": "nobody@innovo-consulting.de", "password": VALID_PASSWORD},
        )
        assert resp.status_code == 401

    def test_login_returns_bearer_token(self, client):
        client.post("/auth/register", json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
        resp = client.post("/auth/login", json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
        token = resp.json()["access_token"]
        # Basic JWT structure: 3 parts separated by dots
        assert token.count(".") == 2


# ---------------------------------------------------------------------------
# Password Reset Flow
# ---------------------------------------------------------------------------

class TestPasswordReset:
    def test_request_reset_nonexistent_email_still_200(self, client):
        """Security: must not reveal whether email exists."""
        resp = client.post(
            "/auth/request-password-reset",
            json={"email": "ghost@innovo-consulting.de"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_full_reset_flow(self, client):
        email = "resetme@innovo-consulting.de"
        password = "originalpass"
        client.post("/auth/register", json={"email": email, "password": password})

        # Request reset
        resp = client.post("/auth/request-password-reset", json={"email": email})
        assert resp.status_code == 200
        # In dev mode, token is returned in the message
        message = resp.json()["message"]
        assert "Token" in message or "token" in message
        # Extract token from message (DEV ONLY response format)
        token = message.split("Token (DEV ONLY): ")[-1].strip()

        # Reset password
        new_password = "newpassword456"
        resp2 = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": new_password},
        )
        assert resp2.status_code == 200
        assert resp2.json()["success"] is True

        # Login with new password
        resp3 = client.post("/auth/login", json={"email": email, "password": new_password})
        assert resp3.status_code == 200

        # Old password no longer works
        resp4 = client.post("/auth/login", json={"email": email, "password": password})
        assert resp4.status_code == 401

    def test_reset_with_invalid_token(self, client):
        resp = client.post(
            "/auth/reset-password",
            json={"token": "invalid.token.here", "new_password": "newpass123"},
        )
        assert resp.status_code == 400

    def test_reset_password_too_short(self, client):
        resp = client.post(
            "/auth/reset-password",
            json={"token": "sometoken", "new_password": "abc"},
        )
        assert resp.status_code == 422
