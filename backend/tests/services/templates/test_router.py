"""Tests for innovo_backend.services.templates.router."""
import pytest


# ---------------------------------------------------------------------------
# System templates
# ---------------------------------------------------------------------------

class TestSystemTemplate:
    def test_get_system_template_wtt_v1(self, client, auth_headers):
        resp = client.get("/templates/system/wtt_v1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["template_name"] == "wtt_v1"
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) > 0

    def test_get_system_template_unknown_returns_404(self, client, auth_headers):
        resp = client.get("/templates/system/nonexistent_template_xyz", headers=auth_headers)
        assert resp.status_code in (404, 500)

    def test_system_template_requires_auth(self, client):
        resp = client.get("/templates/system/wtt_v1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /templates/list  — combined system + user templates
# ---------------------------------------------------------------------------

class TestTemplateList:
    def test_list_returns_dict(self, client, auth_headers):
        resp = client.get("/templates/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_list_includes_system_templates(self, client, auth_headers):
        resp = client.get("/templates/list", headers=auth_headers)
        data = resp.json()
        assert "wtt_v1" in data

    def test_list_requires_auth(self, client):
        resp = client.get("/templates/list")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# User Templates CRUD
# ---------------------------------------------------------------------------

SAMPLE_SECTIONS = [
    {"id": "1", "title": "Einleitung", "type": "text", "content": ""},
    {"id": "2", "title": "Ziele", "type": "text", "content": ""},
]


class TestUserTemplateCRUD:
    def test_create_user_template(self, client, auth_headers):
        resp = client.post(
            "/templates/user",
            json={"name": "My Custom Template", "sections": SAMPLE_SECTIONS},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Custom Template"
        assert "id" in data

    def test_create_template_requires_auth(self, client):
        resp = client.post(
            "/templates/user",
            json={"name": "Unauth Template", "sections": SAMPLE_SECTIONS},
        )
        assert resp.status_code == 401

    def test_list_user_templates(self, client, auth_headers):
        client.post(
            "/templates/user",
            json={"name": "Listed Template", "sections": SAMPLE_SECTIONS},
            headers=auth_headers,
        )
        resp = client.get("/templates/user", headers=auth_headers)
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert "Listed Template" in names

    def test_get_user_template_by_id(self, client, auth_headers):
        create_resp = client.post(
            "/templates/user",
            json={"name": "Get By ID", "sections": SAMPLE_SECTIONS},
            headers=auth_headers,
        )
        template_id = create_resp.json()["id"]
        resp = client.get(f"/templates/user/{template_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get By ID"

    def test_get_nonexistent_template_returns_404(self, client, auth_headers):
        resp = client.get(
            "/templates/user/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_update_user_template(self, client, auth_headers):
        create_resp = client.post(
            "/templates/user",
            json={"name": "Original Name", "sections": SAMPLE_SECTIONS},
            headers=auth_headers,
        )
        template_id = create_resp.json()["id"]
        resp = client.put(
            f"/templates/user/{template_id}",
            json={"name": "Updated Name", "sections": SAMPLE_SECTIONS},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_delete_user_template(self, client, auth_headers):
        create_resp = client.post(
            "/templates/user",
            json={"name": "Delete Me", "sections": SAMPLE_SECTIONS},
            headers=auth_headers,
        )
        template_id = create_resp.json()["id"]
        del_resp = client.delete(f"/templates/user/{template_id}", headers=auth_headers)
        assert del_resp.status_code == 204

    def test_duplicate_user_template(self, client, auth_headers):
        create_resp = client.post(
            "/templates/user",
            json={"name": "Original", "sections": SAMPLE_SECTIONS},
            headers=auth_headers,
        )
        template_id = create_resp.json()["id"]
        resp = client.post(
            f"/templates/user/{template_id}/duplicate",
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert "Original" in resp.json()["name"] or "Copy" in resp.json()["name"]
