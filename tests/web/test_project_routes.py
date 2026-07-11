"""
Tests for project-scoped web routes (Phase 1 multi-project).

Covers: project create/register/list routes, project-scoped job routes,
project-scoped run routes, the _resolve_run_dir bug fix, and the path-
traversal guard on project artifacts. Also verifies the Global view still works.
"""

import json

import pytest
from fastapi.testclient import TestClient

from energizados.web.projects import ProjectService


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client with an isolated workspace root and registry under tmp_path."""
    monkeypatch.setenv("ENERGIZADOS_WORKSPACE_ROOT", str(tmp_path / "ws"))
    from energizados.web.app import app

    # Build a ProjectService with explicit paths under tmp_path so tests are isolated.
    app.state.project_service = ProjectService(
        workspace_root=tmp_path / "ws",
        registry_path=tmp_path / "projects.json",
    )
    monkeypatch.setenv("ENERGIZADOS_JOBS_DB", str(tmp_path / "jobs.db"))
    return TestClient(app)


@pytest.fixture
def project_service(client, tmp_path):
    """The ProjectService wired into the test app."""
    from energizados.web.app import app

    return app.state.project_service


def _make_valid_project_on_disk(svc, name="demo"):
    """Create a real project via the service (lands under workspace root)."""
    return svc.create_project(name)


class TestProjectRoutes:
    """Project registry CRUD routes."""

    def test_list_projects_empty(self, client):
        r = client.get("/projects")
        assert r.status_code == 200
        assert "Projects" in r.text

    def test_create_project_route(self, client, project_service):
        r = client.post(
            "/projects",
            data={"name": "via-route", "template": "default"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "/projects/" in r.headers["location"]
        # Project actually created on disk
        created = project_service.get_project("via-route")
        assert created is not None
        assert (created.path / "config").is_dir()

    def test_register_existing_route(self, client, tmp_path, project_service):
        existing = tmp_path / "external" / "regproj"
        (existing / "config").mkdir(parents=True)
        (existing / "src").mkdir(parents=True)

        r = client.post(
            "/projects/register",
            data={"path": str(existing)},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "/projects/" in r.headers["location"]

    def test_register_invalid_path_returns_400(self, client, tmp_path):
        bad = tmp_path / "nope"
        bad.mkdir()
        r = client.post("/projects/register", data={"path": str(bad)})
        assert r.status_code == 400

    def test_project_detail_404_unknown(self, client):
        r = client.get("/projects/nonexistent-id")
        assert r.status_code == 404

    def test_project_detail_renders(self, client, project_service):
        project = _make_valid_project_on_disk(project_service, "viewme")
        r = client.get(f"/projects/{project.project_id}")
        assert r.status_code == 200
        assert "viewme" in r.text


class TestProjectScopedJobRoutes:
    """Project-scoped job routes."""

    def test_list_project_jobs_empty(self, client, project_service):
        project = _make_valid_project_on_disk(project_service, "proj-jobs")
        r = client.get(f"/projects/{project.project_id}/jobs")
        assert r.status_code == 200

    def test_create_project_job_sets_project_path(self, client, project_service):
        from energizados.web.store import JobStore

        project = _make_valid_project_on_disk(project_service, "proj-create")
        valid_yaml = """
        etl:
          sample:
            enabled: true
            input: "data/raw/test.csv"
            output: "data/processed/test.parquet"
            custom_class: "energizados.etl.pipeline.SourceETL"
        """
        r = client.post(
            f"/projects/{project.project_id}/jobs?config_type=etl",
            data=valid_yaml,
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 201

        # The created job has project_path set
        store = JobStore()
        jobs = store.list_jobs(project_path=str(project.path))
        assert len(jobs) == 1
        assert jobs[0].project_path == str(project.path)

    def test_project_job_404_for_unknown_project(self, client):
        r = client.get("/projects/nope/jobs")
        assert r.status_code == 404

    def test_project_job_detail(self, client, project_service):
        from energizados.web.store import JobStore

        project = _make_valid_project_on_disk(project_service, "proj-detail")
        store = JobStore()
        job_id = store.create_job({"etl": {}}, "etl", project_path=str(project.path))

        r = client.get(f"/projects/{project.project_id}/jobs/{job_id}")
        assert r.status_code == 200

    def test_project_job_progress_404_for_unknown_project(self, client):
        r = client.get("/projects/nope/jobs/job-x/progress")
        assert r.status_code == 404


class TestProjectScopedRunRoutes:
    """Project-scoped run routes."""

    def test_project_runs_list_404_unknown_project(self, client):
        r = client.get("/projects/nope/runs")
        assert r.status_code == 404

    def test_project_runs_list_empty(self, client, project_service):
        project = _make_valid_project_on_disk(project_service, "proj-runs")
        r = client.get(f"/projects/{project.project_id}/runs")
        assert r.status_code == 200

    def test_project_artifact_traversal_rejected(self, client, project_service, tmp_path):
        """Project artifact route rejects path traversal (..)."""
        project = _make_valid_project_on_disk(project_service, "proj-art")

        # Build a real run dir under the project output
        run_id = "train-20240101_120000"
        run_dir = project.path / "output" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "run_metadata.json").write_text(json.dumps({"run_id": run_id}))

        # Traversal attempt
        r = client.get(f"/projects/{project.project_id}/runs/{run_id}/artifacts/../../etc/passwd")
        # Either 403 (traversal detected) or 404 — must NOT be 200
        assert r.status_code in (403, 404)

    def test_project_run_detail_404_unknown_project(self, client):
        r = client.get("/projects/nope/runs/some-run")
        assert r.status_code == 404

    def test_project_dashboard_404_unknown_project(self, client):
        r = client.get("/projects/nope/dashboard")
        assert r.status_code == 404

    def test_project_timeline_404_unknown_project(self, client):
        r = client.get("/projects/nope/api/dashboard/timeline")
        assert r.status_code == 404


class TestResolveRunDirBugFix:
    """Verify the run_dir 500 bug is fixed (was manager.run_dir(run_id) on a property)."""

    def test_resolve_run_dir_returns_dir_when_exists(self, tmp_path):
        from energizados.api import RunManager
        from energizados.web.app import _resolve_run_dir

        base = tmp_path / "output"
        run_id = "train-x"
        (base / run_id).mkdir(parents=True)

        manager = RunManager(output_dir=str(base))
        result = _resolve_run_dir(manager, run_id)
        assert result == base / run_id

    def test_resolve_run_dir_returns_none_when_missing(self, tmp_path):
        from energizados.api import RunManager
        from energizados.web.app import _resolve_run_dir

        manager = RunManager(output_dir=str(tmp_path / "output"))
        assert _resolve_run_dir(manager, "nope") is None

    def test_run_detail_no_longer_500s_on_fresh_manager(self, client, project_service, tmp_path):
        """The Global /runs/{run_id} route no longer throws TypeError on run_dir."""
        project = _make_valid_project_on_disk(project_service, "proj-bug")

        run_id = "train-20240101_120000"
        run_dir = project.path / "output" / run_id
        run_dir.mkdir(parents=True)
        metadata = {
            "run_id": run_id,
            "timestamp": "2024-01-01T00:00:00Z",
            "duration_seconds": 1.0,
            "status": "success",
            "model_types": [],
            "val_auc": None,
            "val_f1": None,
            "feature_count": 0,
            "energizados_version": "0.3.0",
            "python_version": "3.10",
            "git_commit": "",
            "config_files": [],
            "output_paths": {},
        }
        (run_dir / "run_metadata.json").write_text(json.dumps(metadata))

        # Global route (uses RunManager() with cwd-relative output) — since the
        # project output is not at ./output, this returns 404, NOT 500.
        # We verify the project-scoped route renders without error instead.
        r = client.get(f"/projects/{project.project_id}/runs/{run_id}")
        assert r.status_code == 200
        assert run_id in r.text


class TestGlobalViewStillWorks:
    """The un-scoped Global routes must keep working."""

    def test_global_jobs_route(self, client):
        r = client.get("/jobs")
        assert r.status_code == 200

    def test_global_runs_route(self, client):
        r = client.get("/runs")
        assert r.status_code == 200

    def test_global_dashboard_route(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200

    def test_root_route(self, client):
        r = client.get("/")
        assert r.status_code == 200
