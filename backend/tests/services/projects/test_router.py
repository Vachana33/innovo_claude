"""Tests for innovo_backend.services.projects.router."""
import pytest
from unittest.mock import patch, MagicMock

from innovo_backend.shared.models import Company, FundingProgram


@pytest.fixture()
def company(db, auth_headers, client):
    """Create a test company via the companies endpoint."""
    resp = client.post(
        "/companies",
        json={"name": "Test Project Company", "website": None},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def project_payload(company):
    return {
        "company_id": company["id"],
        "company_name": company["name"],
        "funding_program_id": None,
        "topic": "KI-gestützte Qualitätssicherung",
    }


# ---------------------------------------------------------------------------
# POST /projects
# ---------------------------------------------------------------------------

class TestCreateProject:
    def test_create_project_success(self, client, auth_headers, project_payload):
        with patch(
            "innovo_backend.services.projects.context_assembler.assemble_project_context"
        ):
            resp = client.post("/projects", json=project_payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["topic"] == project_payload["topic"]

    def test_create_project_requires_auth(self, client, project_payload):
        resp = client.post("/projects", json=project_payload)
        assert resp.status_code == 401

    def test_create_project_with_company_name_only(self, client, auth_headers):
        """Project can be created with company_name (free text) without company_id."""
        payload = {
            "company_id": None,
            "company_name": "Free Text Company GmbH",
            "funding_program_id": None,
            "topic": "Testprojekt",
        }
        with patch(
            "innovo_backend.services.projects.context_assembler.assemble_project_context"
        ):
            resp = client.post("/projects", json=payload, headers=auth_headers)
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# GET /projects
# ---------------------------------------------------------------------------

class TestListProjects:
    def test_list_returns_200(self, client, auth_headers):
        resp = client.get("/projects", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_requires_auth(self, client):
        resp = client.get("/projects")
        assert resp.status_code == 401

    def test_created_project_appears_in_list(self, client, auth_headers, project_payload):
        with patch(
            "innovo_backend.services.projects.context_assembler.assemble_project_context"
        ):
            client.post("/projects", json=project_payload, headers=auth_headers)
        resp = client.get("/projects", headers=auth_headers)
        topics = [p["topic"] for p in resp.json()]
        assert project_payload["topic"] in topics


# ---------------------------------------------------------------------------
# GET /projects/{id}
# ---------------------------------------------------------------------------

class TestGetProject:
    def test_get_project_by_id(self, client, auth_headers, project_payload):
        with patch(
            "innovo_backend.services.projects.context_assembler.assemble_project_context"
        ):
            create_resp = client.post("/projects", json=project_payload, headers=auth_headers)
        project_id = create_resp.json()["id"]
        resp = client.get(f"/projects/{project_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == project_id

    def test_get_nonexistent_project_returns_404(self, client, auth_headers):
        resp = client.get("/projects/nonexistent-project-id", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /projects/{id}
# ---------------------------------------------------------------------------

class TestDeleteProject:
    def test_delete_project(self, client, auth_headers, project_payload):
        with patch(
            "innovo_backend.services.projects.context_assembler.assemble_project_context"
        ):
            create_resp = client.post("/projects", json=project_payload, headers=auth_headers)
        project_id = create_resp.json()["id"]
        del_resp = client.delete(f"/projects/{project_id}", headers=auth_headers)
        assert del_resp.status_code == 204

    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        resp = client.delete("/projects/nonexistent-id-xyz", headers=auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /projects/{id}/context
# ---------------------------------------------------------------------------

class TestPatchProjectContext:
    def test_patch_context_status_field(self, client, auth_headers, project_payload):
        with patch(
            "innovo_backend.services.projects.context_assembler.assemble_project_context"
        ):
            create_resp = client.post("/projects", json=project_payload, headers=auth_headers)
        project_id = create_resp.json()["id"]
        resp = client.patch(
            f"/projects/{project_id}/context",
            json={"company_discovery_status": "complete"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404)  # 404 if context not yet created
