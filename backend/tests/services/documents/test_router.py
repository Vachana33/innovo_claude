"""Tests for innovo_backend.services.documents.router."""
import pytest


@pytest.fixture()
def company(client, auth_headers):
    resp = client.post(
        "/companies",
        json={"name": "Document Test Corp"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def document(client, auth_headers, company):
    """Create a vorhabensbeschreibung document for the test company."""
    resp = client.get(
        f"/documents/{company['id']}/vorhabensbeschreibung",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# GET /documents
# ---------------------------------------------------------------------------

class TestListDocuments:
    def test_list_returns_200(self, client, auth_headers):
        resp = client.get("/documents", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_requires_auth(self, client):
        resp = client.get("/documents")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /documents/{company_id}/vorhabensbeschreibung
# ---------------------------------------------------------------------------

class TestGetOrCreateDocument:
    def test_creates_document_for_company(self, client, auth_headers, company):
        resp = client.get(
            f"/documents/{company['id']}/vorhabensbeschreibung",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_id"] == company["id"]
        assert data["type"] == "vorhabensbeschreibung"

    def test_returns_existing_document_on_second_call(self, client, auth_headers, company):
        """Legacy mode: second call returns the same document (no new creation)."""
        resp1 = client.get(
            f"/documents/{company['id']}/vorhabensbeschreibung",
            headers=auth_headers,
        )
        resp2 = client.get(
            f"/documents/{company['id']}/vorhabensbeschreibung",
            headers=auth_headers,
        )
        assert resp1.json()["id"] == resp2.json()["id"]

    def test_document_has_sections(self, client, auth_headers, company):
        resp = client.get(
            f"/documents/{company['id']}/vorhabensbeschreibung",
            headers=auth_headers,
        )
        doc = resp.json()
        content_json = doc.get("content_json", {})
        assert "sections" in content_json
        assert isinstance(content_json["sections"], list)

    def test_nonexistent_company_returns_404(self, client, auth_headers):
        resp = client.get("/documents/999999/vorhabensbeschreibung", headers=auth_headers)
        assert resp.status_code == 404

    def test_requires_auth(self, client, company):
        resp = client.get(f"/documents/{company['id']}/vorhabensbeschreibung")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /documents/by-id/{id}
# ---------------------------------------------------------------------------

class TestGetDocumentById:
    def test_get_by_id_success(self, client, auth_headers, document):
        resp = client.get(f"/documents/by-id/{document['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == document["id"]

    def test_get_nonexistent_returns_404(self, client, auth_headers):
        resp = client.get("/documents/by-id/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_requires_auth(self, client, document):
        resp = client.get(f"/documents/by-id/{document['id']}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PUT /documents/{id}
# ---------------------------------------------------------------------------

class TestUpdateDocument:
    def test_update_document_content(self, client, auth_headers, document):
        doc_id = document["id"]
        original_sections = document.get("content_json", {}).get("sections", [])

        # Update first section content if available
        if original_sections:
            updated_sections = list(original_sections)
            updated_sections[0] = {**updated_sections[0], "content": "Aktualisierter Inhalt."}
        else:
            updated_sections = [{"id": "1", "title": "Test", "type": "text", "content": "Neu"}]

        resp = client.put(
            f"/documents/{doc_id}",
            json={"content_json": {"sections": updated_sections}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["content_json"]["sections"] == updated_sections

    def test_update_nonexistent_returns_404(self, client, auth_headers):
        resp = client.put(
            "/documents/999999",
            json={"content_json": {"sections": []}},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_update_requires_auth(self, client, document):
        resp = client.put(
            f"/documents/{document['id']}",
            json={"content_json": {"sections": []}},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /documents/{id}
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    def test_delete_document(self, client, auth_headers, document):
        resp = client.delete(f"/documents/{document['id']}", headers=auth_headers)
        assert resp.status_code == 204

    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        resp = client.delete("/documents/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_deleted_document_not_retrievable(self, client, auth_headers, document):
        doc_id = document["id"]
        client.delete(f"/documents/{doc_id}", headers=auth_headers)
        resp = client.get(f"/documents/by-id/{doc_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_requires_auth(self, client, document):
        resp = client.delete(f"/documents/{document['id']}")
        assert resp.status_code == 401
