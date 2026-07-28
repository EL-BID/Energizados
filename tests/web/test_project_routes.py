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
        (run_dir / "run_metadata.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")

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
        (run_dir / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

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

    def test_global_editor_route(self, client):
        """GET /global renders the legacy global YAML editor + job list.

        Phase 4 redirected ``GET /`` to ``/projects``, orphaning the global
        editor (``index.html``). The dedicated ``/global`` route keeps it
        reachable.
        """
        r = client.get("/global")
        assert r.status_code == 200
        # The editor form (components/editor.html, included by index.html) is
        # present — confirms the editor renders, not just a blank page.
        assert "Pipeline Configuration (YAML)" in r.text

    def test_root_route_redirects_to_projects(self, client):
        """GET / now 302-redirects to /projects (projects home is the entry point)."""
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"] == "/projects"

    def test_global_dashboard_uses_global_timeline_url(self, client):
        """Regression guard: the global /dashboard references the global timeline URL."""
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "/api/dashboard/timeline" in r.text
        # Must NOT reference a project-scoped timeline URL
        assert "/projects/" not in r.text.split("api/dashboard/timeline")[0].splitlines()[-1]

    def test_project_dashboard_uses_project_timeline_url(self, client, project_service):
        """The project dashboard wires the chart to the project-scoped timeline URL."""
        project = _make_valid_project_on_disk(project_service, "proj-dash")
        r = client.get(f"/projects/{project.project_id}/dashboard")
        assert r.status_code == 200
        # The embedded JS must reference the project-scoped timeline endpoint
        assert f"/projects/{project.project_id}/api/dashboard/timeline" in r.text
        # And the project-scoped run link base (RUNS_BASE const, no trailing slash)
        assert f"/projects/{project.project_id}/runs" in r.text


def _write_run_metadata(
    run_dir, run_id, *, status="success", val_auc=0.9, val_f1=0.8, timestamp="2024-01-01T00:00:00Z"
):
    """Fabricate a run directory with run_metadata.json (mirrors RunManager output)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "run_id": run_id,
        "timestamp": timestamp,
        "duration_seconds": 1.0,
        "status": status,
        "model_types": ["lightgbm"],
        "val_auc": val_auc,
        "val_f1": val_f1,
        "feature_count": 5,
        "energizados_version": "0.3.0",
        "python_version": "3.10",
        "git_commit": "",
        "config_files": [],
        "output_paths": {},
    }
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return run_dir


def _write_run_metadata_derived(
    run_dir, run_id, *, derived_from=None, timestamp="2024-01-01T00:00:00Z"
):
    """Write a run_metadata.json carrying the ADR-0003 derived_from link.

    Mirrors RunManager output for a finalized typed run. When ``derived_from``
    is None it is omitted (matching RunMetadata.to_dict for non-derived runs).
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "run_id": run_id,
        "timestamp": timestamp,
        "duration_seconds": 1.0,
        "status": "success",
        "model_types": ["lightgbm"],
        "val_auc": 0.9,
        "val_f1": 0.8,
        "feature_count": 5,
        "energizados_version": "0.3.0",
        "python_version": "3.10",
        "git_commit": "",
        "config_files": [],
        "output_paths": {},
        "run_type": "training",
    }
    if derived_from is not None:
        metadata["derived_from"] = derived_from
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return run_dir


def _lineage_section(html):
    """Extract the Lineage card slice from the project detail HTML.

    Run ids also appear in the "Latest training" hero and the type-grouped
    tables, so whole-document ordering checks are unreliable. This isolates the
    lineage card (between its heading and the next section) for robust asserts.
    """
    start = html.index("Lineage")
    # The next section after Lineage is the YAML editor ("Submit a job").
    end = html.index("Submit a job", start)
    return html[start:end]


class TestProjectDetailLineage:
    """Phase 3 (ADR-0003): the project hero renders the Run→Run retrain chain.

    ``project_detail`` walks ``run.derived_from`` via ``RunManager.get_run`` and
    passes ``lineage_available`` + ``lineage_chain`` (ordered root→leaf) to the
    template. The muted placeholder is the empty-state when no run has a
    ``derived_from``.
    """

    def test_lineage_empty_state_when_no_derived_from(self, client, project_service):
        """A project whose runs have no derived_from renders the muted placeholder."""
        project = _make_valid_project_on_disk(project_service, "lineage-empty")
        _write_run_metadata_derived(
            project.path / "output" / "train-20240101_120000",
            "train-20240101_120000",
            timestamp="2024-01-01T12:00:00Z",
        )

        r = client.get(f"/projects/{project.project_id}")
        assert r.status_code == 200
        text = r.text
        # The empty-state placeholder copy is present.
        assert "No retrain lineage yet" in text
        assert "derived_from" in text

    def test_lineage_available_when_derived_from_present(self, client, project_service):
        """A latest run with derived_from triggers lineage_available + chain depth 2."""
        project = _make_valid_project_on_disk(project_service, "lineage-one")
        root = "train-20240101_120000"
        leaf = "train-20240201_120000"
        _write_run_metadata_derived(
            project.path / "output" / root, root, timestamp="2024-01-01T12:00:00Z"
        )
        _write_run_metadata_derived(
            project.path / "output" / leaf,
            leaf,
            derived_from=root,
            timestamp="2024-02-01T12:00:00Z",
        )

        r = client.get(f"/projects/{project.project_id}")
        assert r.status_code == 200
        section = _lineage_section(r.text)
        # Both run ids appear within the lineage section.
        assert root in section
        assert leaf in section
        # An arrow separator is rendered between chain links.
        assert "→" in section

    def test_lineage_chain_depth_three_root_to_leaf(self, client, project_service):
        """A→B→C chain renders all three runs ordered root→leaf."""
        project = _make_valid_project_on_disk(project_service, "lineage-chain")
        a = "train-20240101_120000"
        b = "train-20240201_120000"
        c = "train-20240301_120000"
        _write_run_metadata_derived(
            project.path / "output" / a, a, timestamp="2024-01-01T12:00:00Z"
        )
        _write_run_metadata_derived(
            project.path / "output" / b, b, derived_from=a, timestamp="2024-02-01T12:00:00Z"
        )
        _write_run_metadata_derived(
            project.path / "output" / c, c, derived_from=b, timestamp="2024-03-01T12:00:00Z"
        )

        r = client.get(f"/projects/{project.project_id}")
        assert r.status_code == 200
        section = _lineage_section(r.text)
        # All three chain members render within the lineage section, root→leaf.
        assert a in section
        assert b in section
        assert c in section
        assert section.index(a) < section.index(b) < section.index(c)


class TestProjectsHomeStats:
    """Item B — per-project card stats on the /projects home."""

    def test_project_card_shows_run_count_last_run_and_queue_depth(self, client, project_service):
        from energizados.web.store import JobStore

        project = _make_valid_project_on_disk(project_service, "statme")
        out = project.path / "output"
        # Two runs — the second is the most recent (newer timestamp).
        _write_run_metadata(
            out / "train-20240101_120000",
            "train-20240101_120000",
            status="success",
            val_auc=0.91,
            val_f1=0.77,
            timestamp="2024-01-01T12:00:00Z",
        )
        _write_run_metadata(
            out / "train-20240201_120000",
            "train-20240201_120000",
            status="success",
            val_auc=0.85,
            val_f1=0.66,
            timestamp="2024-02-01T12:00:00Z",
        )
        # One queued job for this project.
        JobStore().create_job({"etl": {}}, "etl", project_path=str(project.path))

        r = client.get("/projects")
        assert r.status_code == 200
        text = r.text
        # Run count
        assert "2 runs" in text
        # Queue depth
        assert "queued: 1" in text
        # Last run AUC of the most-recent run (0.85)
        assert "0.85" in text

    def test_project_card_zero_state(self, client, project_service):
        """A brand-new project shows 0 runs and queued: 0, no metrics."""
        _make_valid_project_on_disk(project_service, "emptystats")
        r = client.get("/projects")
        assert r.status_code == 200
        text = r.text
        assert "0 runs" in text
        assert "queued: 0" in text
        # The empty metrics placeholder
        assert "—" in text


class TestJobDetailProjectLink:
    """Item D — job_detail shows the owning project + project-scoped run link."""

    def test_job_with_registered_project_shows_project_link(self, client, project_service):
        from energizados.web.store import JobStore

        project = _make_valid_project_on_disk(project_service, "joblink")
        store = JobStore()
        job_id = store.create_job({"train": {}}, "train", project_path=str(project.path))

        r = client.get(f"/jobs/{job_id}")
        assert r.status_code == 200
        text = r.text
        # Project deep link present
        assert f'href="/projects/{project.project_id}"' in text
        assert "joblink" in text

    def test_global_job_shows_no_project_link(self, client):
        from energizados.web.store import JobStore

        store = JobStore()
        # Global job — project_path=None — but with a run_id to render the run button.
        job_id = store.create_job({"train": {}}, "train", project_path=None)
        # Stamp a run_id so the "View Run Results" button renders.
        with store._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET run_id = ? WHERE job_id = ?",
                ("train-global-1", job_id),
            )
            conn.commit()

        r = client.get(f"/jobs/{job_id}")
        assert r.status_code == 200
        text = r.text
        # No project section header/link for a global job
        assert "Project:" not in text
        # The run button points to the GLOBAL run route
        assert 'href="/runs/train-global-1"' in text
        # And NOT to a project-scoped route
        assert "/projects/" not in text.split("View Run Results")[1].split("</a>")[0]

    def test_job_with_project_uses_project_scoped_run_link(self, client, project_service):
        from energizados.web.store import JobStore

        project = _make_valid_project_on_disk(project_service, "jobrunlink")
        store = JobStore()
        job_id = store.create_job({"train": {}}, "train", project_path=str(project.path))
        run_id = "train-scoped-1"
        with store._get_connection() as conn:
            conn.execute("UPDATE jobs SET run_id = ? WHERE job_id = ?", (run_id, job_id))
            conn.commit()

        r = client.get(f"/jobs/{job_id}")
        assert r.status_code == 200
        text = r.text
        # Run button points to the PROJECT-scoped run route
        assert f'href="/projects/{project.project_id}/runs/{run_id}"' in text
