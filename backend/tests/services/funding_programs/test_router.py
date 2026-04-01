"""Tests for innovo_backend.services.funding_programs.router."""
import pytest
from innovo_backend.shared.models import User
from innovo_backend.shared.utils import hash_password


ADMIN_EMAIL = "admin@innovo-consulting.de"
ADMIN_PASSWORD = "adminpass123"


@pytest.fixture()
def admin_headers(client, db):
    """Register an admin user and return auth headers."""
    user = User(
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        is_admin=True,
    )
    db.add(user)
    db.commit()

    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /funding-programs  (admin only)
# ---------------------------------------------------------------------------

class TestCreateFundingProgram:
    def test_create_success_as_admin(self, client, admin_headers):
        resp = client.post(
            "/funding-programs",
            json={"title": "ZIM 2025", "website": "https://www.zim.de"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "ZIM 2025"
        assert "id" in data

    def test_create_forbidden_for_non_admin(self, client, auth_headers):
        resp = client.post(
            "/funding-programs",
            json={"title": "Forbidden Program"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_create_requires_auth(self, client):
        resp = client.post("/funding-programs", json={"title": "No Auth"})
        assert resp.status_code == 401

    def test_create_empty_title_rejected(self, client, admin_headers):
        resp = client.post(
            "/funding-programs",
            json={"title": "   "},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_create_without_website(self, client, admin_headers):
        resp = client.post(
            "/funding-programs",
            json={"title": "No Website Program"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["website"] is None


# ---------------------------------------------------------------------------
# GET /funding-programs
# ---------------------------------------------------------------------------

class TestListFundingPrograms:
    def test_list_returns_200(self, client, auth_headers):
        resp = client.get("/funding-programs", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_requires_auth(self, client):
        resp = client.get("/funding-programs")
        assert resp.status_code == 401

    def test_list_contains_created_program(self, client, admin_headers):
        client.post(
            "/funding-programs",
            json={"title": "Visible Program"},
            headers=admin_headers,
        )
        resp = client.get("/funding-programs", headers=admin_headers)
        titles = [p["title"] for p in resp.json()]
        assert "Visible Program" in titles


# ---------------------------------------------------------------------------
# DELETE /funding-programs/{id}  (admin only)
# ---------------------------------------------------------------------------

class TestDeleteFundingProgram:
    def test_delete_as_admin(self, client, admin_headers):
        create_resp = client.post(
            "/funding-programs",
            json={"title": "To Delete"},
            headers=admin_headers,
        )
        program_id = create_resp.json()["id"]
        del_resp = client.delete(f"/funding-programs/{program_id}", headers=admin_headers)
        assert del_resp.status_code == 204

    def test_delete_nonexistent_returns_404(self, client, admin_headers):
        resp = client.delete("/funding-programs/999999", headers=admin_headers)
        assert resp.status_code == 404

    def test_delete_forbidden_for_non_admin(self, client, auth_headers, admin_headers):
        create_resp = client.post(
            "/funding-programs",
            json={"title": "Protected Program"},
            headers=admin_headers,
        )
        program_id = create_resp.json()["id"]
        resp = client.delete(f"/funding-programs/{program_id}", headers=auth_headers)
        assert resp.status_code == 403
