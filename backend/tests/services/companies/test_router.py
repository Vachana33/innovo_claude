"""Tests for innovo_backend.services.companies.router."""
import io
import pytest


# ---------------------------------------------------------------------------
# POST /companies
# ---------------------------------------------------------------------------

class TestCreateCompany:
    def test_create_company_success(self, client, auth_headers):
        resp = client.post(
            "/companies",
            json={"name": "Acme GmbH", "website": "https://acme.de"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Acme GmbH"
        assert "id" in data

    def test_create_company_requires_auth(self, client):
        resp = client.post("/companies", json={"name": "No Auth Corp"})
        assert resp.status_code == 401

    def test_create_company_without_website(self, client, auth_headers):
        resp = client.post(
            "/companies",
            json={"name": "No Website GmbH"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["website"] is None

    def test_create_company_empty_name_rejected(self, client, auth_headers):
        resp = client.post(
            "/companies",
            json={"name": ""},
            headers=auth_headers,
        )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# GET /companies
# ---------------------------------------------------------------------------

class TestListCompanies:
    def test_list_returns_200(self, client, auth_headers):
        resp = client.get("/companies", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_requires_auth(self, client):
        resp = client.get("/companies")
        assert resp.status_code == 401

    def test_created_company_appears_in_list(self, client, auth_headers):
        client.post(
            "/companies",
            json={"name": "Listed Company AG"},
            headers=auth_headers,
        )
        resp = client.get("/companies", headers=auth_headers)
        names = [c["name"] for c in resp.json()]
        assert "Listed Company AG" in names


# ---------------------------------------------------------------------------
# GET /companies/{id}
# ---------------------------------------------------------------------------

class TestGetCompany:
    def test_get_company_by_id(self, client, auth_headers):
        create_resp = client.post(
            "/companies",
            json={"name": "Specific Company"},
            headers=auth_headers,
        )
        company_id = create_resp.json()["id"]
        resp = client.get(f"/companies/{company_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Specific Company"

    def test_get_nonexistent_returns_404(self, client, auth_headers):
        resp = client.get("/companies/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_cannot_access_other_users_company(self, client, auth_headers, db):
        """Company owned by a different user must return 404."""
        from innovo_backend.shared.models import Company, User
        from innovo_backend.shared.utils import hash_password

        other_user = User(
            email="other@innovo-consulting.de",
            password_hash=hash_password("otherpass123"),
        )
        db.add(other_user)
        db.flush()

        other_company = Company(
            name="Other Users Company",
            user_email="other@innovo-consulting.de",
        )
        db.add(other_company)
        db.commit()

        resp = client.get(f"/companies/{other_company.id}", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /companies/{id}
# ---------------------------------------------------------------------------

class TestUpdateCompany:
    def test_update_company_name(self, client, auth_headers):
        create_resp = client.post(
            "/companies",
            json={"name": "Old Name GmbH"},
            headers=auth_headers,
        )
        company_id = create_resp.json()["id"]
        resp = client.put(
            f"/companies/{company_id}",
            json={"name": "New Name GmbH"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name GmbH"

    def test_update_nonexistent_returns_404(self, client, auth_headers):
        resp = client.put(
            "/companies/999999",
            json={"name": "Ghost Company"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /companies/{id}
# ---------------------------------------------------------------------------

class TestDeleteCompany:
    def test_delete_company(self, client, auth_headers):
        create_resp = client.post(
            "/companies",
            json={"name": "Delete Me GmbH"},
            headers=auth_headers,
        )
        company_id = create_resp.json()["id"]
        del_resp = client.delete(f"/companies/{company_id}", headers=auth_headers)
        assert del_resp.status_code == 204

    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        resp = client.delete("/companies/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_deleted_company_not_in_list(self, client, auth_headers):
        create_resp = client.post(
            "/companies",
            json={"name": "Temporary Company"},
            headers=auth_headers,
        )
        company_id = create_resp.json()["id"]
        client.delete(f"/companies/{company_id}", headers=auth_headers)

        resp = client.get("/companies", headers=auth_headers)
        ids = [c["id"] for c in resp.json()]
        assert company_id not in ids


# ---------------------------------------------------------------------------
# Company documents
# ---------------------------------------------------------------------------

class TestCompanyDocuments:
    def test_list_documents_initially_empty(self, client, auth_headers):
        create_resp = client.post(
            "/companies",
            json={"name": "Doc Test Company"},
            headers=auth_headers,
        )
        company_id = create_resp.json()["id"]
        resp = client.get(f"/companies/{company_id}/documents", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_upload_document_requires_auth(self, client):
        resp = client.post(
            "/companies/1/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(b"fake content"), "application/pdf")},
        )
        assert resp.status_code == 401
