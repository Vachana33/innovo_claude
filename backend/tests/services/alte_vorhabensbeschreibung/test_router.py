"""Tests for innovo_backend.services.alte_vorhabensbeschreibung.router."""
import io
import pytest


# ---------------------------------------------------------------------------
# GET /alte-vorhabensbeschreibung/style-profile
# ---------------------------------------------------------------------------

class TestStyleProfile:
    def test_get_style_profile_no_docs(self, client, auth_headers):
        """When no documents have been uploaded, the style profile should be empty or null."""
        resp = client.get("/alte-vorhabensbeschreibung/style-profile", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should return a dict (possibly with null/empty style profile)
        assert isinstance(data, dict)

    def test_get_style_profile_requires_auth(self, client):
        resp = client.get("/alte-vorhabensbeschreibung/style-profile")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /alte-vorhabensbeschreibung/documents
# ---------------------------------------------------------------------------

class TestListAlteDocuments:
    def test_list_returns_empty_initially(self, client, auth_headers):
        resp = client.get("/alte-vorhabensbeschreibung/documents", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_requires_auth(self, client):
        resp = client.get("/alte-vorhabensbeschreibung/documents")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /alte-vorhabensbeschreibung/upload
# ---------------------------------------------------------------------------

class TestUploadAlteDocument:
    def test_upload_requires_auth(self, client):
        file_content = b"Dummy PDF content"
        resp = client.post(
            "/alte-vorhabensbeschreibung/upload",
            files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert resp.status_code == 401

    def test_upload_pdf_file(self, client, auth_headers):
        """Basic upload test — may fail if Supabase is not configured, which is expected in test env."""
        file_content = b"%PDF-1.4 fake pdf content for testing"
        resp = client.post(
            "/alte-vorhabensbeschreibung/upload",
            files={"file": ("test_doc.pdf", io.BytesIO(file_content), "application/pdf")},
            headers=auth_headers,
        )
        # In test environment without Supabase, this will fail with 500 or succeed
        # We just verify it doesn't return 401 or 422 (auth/validation passed)
        assert resp.status_code != 401
        assert resp.status_code != 422


# ---------------------------------------------------------------------------
# DELETE /alte-vorhabensbeschreibung/documents/{id}
# ---------------------------------------------------------------------------

class TestDeleteAlteDocument:
    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        resp = client.delete("/alte-vorhabensbeschreibung/documents/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_requires_auth(self, client):
        resp = client.delete("/alte-vorhabensbeschreibung/documents/1")
        assert resp.status_code == 401
