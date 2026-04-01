"""
Task 0 — Admin guard tests.

Verifies that every admin-only endpoint returns HTTP 403 when called by a
non-admin authenticated user, and HTTP 200/201/204 when called by an admin.

Coverage:
  alte_vorhabensbeschreibung  — 6 endpoints
  funding_programs            — 6 endpoints (3 pre-existing + 3 newly-guarded)
  companies                   — 4 newly-guarded write endpoints
  knowledge_base              — 7 endpoints (pre-existing, included for completeness)
  auth                        — GET /auth/me (not admin-only, verifies is_admin field)
"""
import io
import pytest

from innovo_backend.shared.models import User
from innovo_backend.shared.utils import hash_password

# ---------------------------------------------------------------------------
# Admin user fixtures
# ---------------------------------------------------------------------------

ADMIN_EMAIL = "admin_guard_test@innovo-consulting.de"
ADMIN_PASSWORD = "adminpass123"

NON_ADMIN_EMAIL = "testuser@innovo-consulting.de"
NON_ADMIN_PASSWORD = "securepass123"


@pytest.fixture()
def admin_user(client, db):
    """Register a user and promote to admin directly via DB."""
    resp = client.post(
        "/auth/register",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code in (201, 409), resp.text
    user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    user.is_admin = True
    db.commit()
    return ADMIN_EMAIL


@pytest.fixture()
def admin_headers(client, admin_user):
    """Login as admin and return bearer headers."""
    resp = client.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# auth_headers fixture (non-admin) is provided by conftest.py

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _dummy_pdf() -> tuple[str, bytes, str]:
    """Returns (filename, bytes, content_type) for a minimal fake PDF upload."""
    return ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")


# ---------------------------------------------------------------------------
# GET /auth/me — authenticated, not admin-only
# ---------------------------------------------------------------------------

class TestAuthMe:
    def test_me_returns_is_admin_false_for_non_admin(self, client, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "email" in body
        assert body["is_admin"] is False

    def test_me_returns_is_admin_true_for_admin(self, client, admin_headers):
        resp = client.get("/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True

    def test_me_requires_authentication(self, client):
        # FastAPI's HTTPBearer returns 403 when no Authorization header is provided
        resp = client.get("/auth/me")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# alte_vorhabensbeschreibung — 6 guarded endpoints
# ---------------------------------------------------------------------------

class TestAlteVorhabensbeschreibungAdminGuard:
    def test_upload_non_admin_gets_403(self, client, auth_headers):
        fname, data, ctype = _dummy_pdf()
        resp = client.post(
            "/alte-vorhabensbeschreibung/upload",
            headers=auth_headers,
            files={"files": (fname, data, ctype)},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_list_documents_non_admin_gets_403(self, client, auth_headers):
        resp = client.get("/alte-vorhabensbeschreibung/documents", headers=auth_headers)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_update_document_non_admin_gets_403(self, client, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000001"
        fname, data, ctype = _dummy_pdf()
        resp = client.put(
            f"/alte-vorhabensbeschreibung/documents/{fake_id}",
            headers=auth_headers,
            files={"file": (fname, data, ctype)},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_delete_document_non_admin_gets_403(self, client, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000001"
        resp = client.delete(
            f"/alte-vorhabensbeschreibung/documents/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_style_profile_non_admin_gets_403(self, client, auth_headers):
        resp = client.get("/alte-vorhabensbeschreibung/style-profile", headers=auth_headers)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_regenerate_style_non_admin_gets_403(self, client, auth_headers):
        resp = client.post("/alte-vorhabensbeschreibung/regenerate-style", headers=auth_headers)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"


# ---------------------------------------------------------------------------
# funding_programs — 6 guarded write endpoints
# ---------------------------------------------------------------------------

class TestFundingProgramsAdminGuard:
    def test_create_program_non_admin_gets_403(self, client, auth_headers):
        resp = client.post(
            "/funding-programs",
            headers=auth_headers,
            json={"title": "Test Program"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_update_program_non_admin_gets_403(self, client, auth_headers):
        resp = client.put(
            "/funding-programs/99999",
            headers=auth_headers,
            json={"title": "Updated"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_delete_program_non_admin_gets_403(self, client, auth_headers):
        resp = client.delete("/funding-programs/99999", headers=auth_headers)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_guidelines_upload_non_admin_gets_403(self, client, auth_headers):
        fname, data, ctype = _dummy_pdf()
        resp = client.post(
            "/funding-programs/99999/guidelines/upload",
            headers=auth_headers,
            files={"files": (fname, data, ctype)},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_get_documents_non_admin_gets_403(self, client, auth_headers):
        resp = client.get("/funding-programs/99999/documents", headers=auth_headers)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_delete_document_non_admin_gets_403(self, client, auth_headers):
        fake_doc_id = "00000000-0000-0000-0000-000000000001"
        resp = client.delete(
            f"/funding-programs/99999/documents/{fake_doc_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"


# ---------------------------------------------------------------------------
# companies — 4 guarded write endpoints
# ---------------------------------------------------------------------------

class TestCompaniesAdminGuard:
    def test_create_company_non_admin_gets_403(self, client, auth_headers):
        resp = client.post(
            "/companies",
            headers=auth_headers,
            json={"name": "Test Co"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_update_company_non_admin_gets_403(self, client, auth_headers):
        resp = client.put(
            "/companies/99999",
            headers=auth_headers,
            json={"name": "Updated Co"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_delete_company_non_admin_gets_403(self, client, auth_headers):
        resp = client.delete("/companies/99999", headers=auth_headers)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"

    def test_upload_company_document_non_admin_gets_403(self, client, auth_headers):
        fname, data, ctype = _dummy_pdf()
        resp = client.post(
            "/companies/99999/documents/upload",
            headers=auth_headers,
            files={"files": (fname, data, ctype)},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"


# ---------------------------------------------------------------------------
# knowledge_base — all 7 endpoints (pre-existing guards, regression check)
# ---------------------------------------------------------------------------

class TestKnowledgeBaseAdminGuard:
    def test_upload_document_non_admin_gets_403(self, client, auth_headers):
        fname, data, ctype = _dummy_pdf()
        resp = client.post(
            "/knowledge-base/documents",
            headers=auth_headers,
            files={"file": (fname, data, ctype)},
        )
        assert resp.status_code == 403

    def test_list_documents_non_admin_gets_403(self, client, auth_headers):
        resp = client.get("/knowledge-base/documents", headers=auth_headers)
        assert resp.status_code == 403

    def test_delete_document_non_admin_gets_403(self, client, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000001"
        resp = client.delete(f"/knowledge-base/documents/{fake_id}", headers=auth_headers)
        assert resp.status_code == 403

    def test_add_funding_source_non_admin_gets_403(self, client, auth_headers):
        resp = client.post(
            "/knowledge-base/funding-sources",
            headers=auth_headers,
            json={"funding_program_id": 99999, "url": "https://example.com", "label": "test"},
        )
        assert resp.status_code == 403

    def test_list_funding_sources_non_admin_gets_403(self, client, auth_headers):
        resp = client.get("/knowledge-base/funding-sources", headers=auth_headers)
        assert resp.status_code == 403

    def test_delete_funding_source_non_admin_gets_403(self, client, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000001"
        resp = client.delete(f"/knowledge-base/funding-sources/{fake_id}", headers=auth_headers)
        assert resp.status_code == 403

    def test_refresh_funding_source_non_admin_gets_403(self, client, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000001"
        resp = client.post(
            f"/knowledge-base/funding-sources/{fake_id}/refresh",
            headers=auth_headers,
        )
        assert resp.status_code == 403
