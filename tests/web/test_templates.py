"""
Tests for Phase 2 — Config authoring: templates API + project config serving +
editor UI controls (template select + load-from-project-config).

These cover:
- ``GET /api/templates`` enumerates the shipped ``.yaml.tpl`` stems.
- ``GET /api/templates/{name}`` returns raw ``text/yaml`` for a valid name and
  404 for unknown names and traversal attempts (the ``name`` is validated
  against the fixed set of shipped templates — never an arbitrary path read).
- ``GET /projects/{project_id}/config/{type}`` serves the project's real
  ``config/{type}.yaml`` with a strict ``^[A-Za-z0-9_]+$`` guard plus a
  ``relative_to`` anchor under the project's ``config/`` dir.
- The project detail page renders the new template + config loader controls.
"""

import pytest
from fastapi.testclient import TestClient

from energizados.web.projects import ProjectService

#: The fixed set of config templates shipped under energizados/templates/config.
EXPECTED_TEMPLATE_NAMES = {"eda", "etl", "infer", "train"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client with an isolated workspace root and registry under tmp_path."""
    monkeypatch.setenv("ENERGIZADOS_WORKSPACE_ROOT", str(tmp_path / "ws"))
    from energizados.web.app import app

    app.state.project_service = ProjectService(
        workspace_root=tmp_path / "ws",
        registry_path=tmp_path / "projects.json",
    )
    monkeypatch.setenv("ENERGIZADOS_JOBS_DB", str(tmp_path / "jobs.db"))
    return TestClient(app)


@pytest.fixture
def project_service(client):
    """The ProjectService wired into the test app."""
    from energizados.web.app import app

    return app.state.project_service


def _make_project(svc, name="demo"):
    """Create a real project on disk under the workspace root."""
    return svc.create_project(name)


class TestTemplatesApi:
    """``GET /api/templates`` and ``GET /api/templates/{name}``."""

    def test_list_templates_returns_expected_names(self, client):
        r = client.get("/api/templates")
        assert r.status_code == 200
        data = r.json()
        assert "templates" in data
        assert set(data["templates"]) == EXPECTED_TEMPLATE_NAMES

    @pytest.mark.parametrize("name", sorted(EXPECTED_TEMPLATE_NAMES))
    def test_get_template_returns_nonempty_yaml(self, client, name):
        r = client.get(f"/api/templates/{name}")
        assert r.status_code == 200
        assert "yaml" in r.headers["content-type"].lower()
        assert r.text.strip(), f"template {name} should not be empty"

    def test_get_template_unknown_name_404(self, client):
        r = client.get("/api/templates/does-not-exist")
        assert r.status_code == 404

    def test_get_template_traversal_dotdot_404(self, client):
        # ".." matches the route's {name} param but is not in the fixed set → 404.
        r = client.get("/api/templates/..")
        assert r.status_code == 404

    def test_get_template_traversal_slash_404(self, client):
        # A slash in the name cannot match the single-segment {name} route → 404.
        r = client.get("/api/templates/foo/bar")
        assert r.status_code == 404


class TestProjectConfigRoute:
    """``GET /projects/{project_id}/config/{type}``."""

    def test_serves_existing_project_config(self, client, project_service):
        project = _make_project(project_service, "cfg-ok")
        cfg_file = project.path / "config" / "etl.yaml"
        cfg_file.write_text("etl:\n  sample:\n    enabled: true\n", encoding="utf-8")

        r = client.get(f"/projects/{project.project_id}/config/etl")
        assert r.status_code == 200
        assert "yaml" in r.headers["content-type"].lower()
        assert "etl:" in r.text

    def test_unknown_project_404(self, client):
        r = client.get("/projects/no-such-project/config/etl")
        assert r.status_code == 404

    def test_missing_config_file_404(self, client, project_service):
        project = _make_project(project_service, "cfg-missing")
        r = client.get(f"/projects/{project.project_id}/config/no_such_file_xyz")
        assert r.status_code == 404

    def test_invalid_type_with_dot_404(self, client, project_service):
        """A type containing '.' fails the filename guard (regex) → 404."""
        project = _make_project(project_service, "cfg-dot")
        r = client.get(f"/projects/{project.project_id}/config/etl.yaml")
        assert r.status_code == 404

    def test_invalid_type_traversal_404(self, client, project_service):
        """A traversal-shaped type (encoded ``..``) reaches the handler and is
        rejected by the filename guard → 404. (The raw ``..`` literal is
        normalized away by HTTP clients before reaching the server, so the
        encoded form is the meaningful server-side guard test.)"""
        project = _make_project(project_service, "cfg-trav")
        r = client.get(f"/projects/{project.project_id}/config/%2e%2e")
        assert r.status_code == 404

    def test_invalid_type_with_slash_404(self, client, project_service):
        project = _make_project(project_service, "cfg-slash")
        r = client.get(f"/projects/{project.project_id}/config/foo/bar")
        assert r.status_code == 404


class TestEditorUiControls:
    """The project detail page renders the new config-authoring controls."""

    def test_project_detail_renders_template_and_config_loaders(self, client, project_service):
        project = _make_project(project_service, "ui-proj")
        r = client.get(f"/projects/{project.project_id}")
        assert r.status_code == 200
        # Template loader
        assert "/api/templates/" in r.text
        # Load-from-project-config control, scoped to this project
        assert f"/projects/{project.project_id}/config/" in r.text
