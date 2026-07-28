"""
Phase 3 — Retrain + Inference UX (project-scoped).

Unit-level enqueue tests for the two new capabilities:

- ``POST /projects/{project_id}/runs/{run_id}/retrain`` — reads the run's saved
  configs, merges them, validates, and enqueues a ``train`` job.
- ``GET  /projects/{project_id}/runs/{run_id}/inference`` — HTMX form fragment
  (or JSON describing eligible runs + input files).
- ``POST /projects/{project_id}/inference`` — enqueue an ``infer`` job built
  from a chosen trained run + input file.

These are enqueue-level tests (no real pipeline execution). Fixtures mirror
``test_project_routes.py``.
"""

import json

import pytest
from fastapi.testclient import TestClient

from energizados.web.projects import ProjectService

# ---------------------------------------------------------------------------
# Fixtures (mirror test_project_routes.py)
# ---------------------------------------------------------------------------


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
    from energizados.web.app import app

    return app.state.project_service


def _make_project(svc, name="demo"):
    """Create a real project via the service (lands under workspace root)."""
    return svc.create_project(name)


def _write_run_metadata(run_dir, run_id, *, model=False, model_types=None):
    """Write a run_metadata.json for a fake run under ``run_dir``.

    Args:
        run_dir: Path to the run directory.
        run_id: Run identifier.
        model: If True, set ``output_paths.model = "models/model.pkl"``.
        model_types: Optional list of model type names for the label.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {"model": "models/model.pkl"} if model else {}
    metadata = {
        "run_id": run_id,
        "timestamp": "2024-01-01T00:00:00",
        "duration_seconds": 1.0,
        "status": "success",
        "model_types": model_types or [],
        "val_auc": None,
        "val_f1": None,
        "feature_count": 0,
        "energizados_version": "0.3.0",
        "python_version": "3.10",
        "git_commit": "",
        "config_files": [],
        "output_paths": output_paths,
    }
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


# Valid config fragments written to run_dir/config/.
_ETL_YAML = (
    "etl:\n"
    "  sample:\n"
    "    enabled: true\n"
    '    input: "data/raw/x.csv"\n'
    '    output: "data/processed/x.parquet"\n'
    '    custom_class: "energizados.etl.pipeline.SourceETL"\n'
)
_TRAIN_YAML = "train:\n" "  enabled: true\n" "  models:\n" "    - type: lightgbm\n"


# ---------------------------------------------------------------------------
# Retrain
# ---------------------------------------------------------------------------


class TestRetrain:
    """POST /projects/{project_id}/runs/{run_id}/retrain."""

    def test_retrain_enqueues_train_job(self, client, project_service):
        from energizados.web.store import JobStore

        project = _make_project(project_service, "retrain-merge")
        run_id = "train-20240101_120000"
        run_dir = project.path / "output" / run_id
        _write_run_metadata(run_dir, run_id)
        (run_dir / "config").mkdir(parents=True, exist_ok=True)
        (run_dir / "config" / "etl.yaml").write_text(_ETL_YAML, encoding="utf-8")
        (run_dir / "config" / "train.yaml").write_text(_TRAIN_YAML, encoding="utf-8")

        r = client.post(
            f"/projects/{project.project_id}/runs/{run_id}/retrain",
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 201, r.text

        store = JobStore()
        jobs = store.list_jobs(project_path=str(project.path))
        assert len(jobs) == 1
        job = jobs[0]
        assert job.config_type == "train"
        # Merged config contains BOTH the etl and train sections.
        assert "etl" in job.config
        assert "train" in job.config
        assert "sample" in job.config["etl"]
        assert "models" in job.config["train"]

    def test_retrain_single_config(self, client, project_service):
        from energizados.web.store import JobStore

        project = _make_project(project_service, "retrain-single")
        run_id = "train-20240102_120000"
        run_dir = project.path / "output" / run_id
        _write_run_metadata(run_dir, run_id)
        (run_dir / "config").mkdir(parents=True, exist_ok=True)
        (run_dir / "config" / "train.yaml").write_text(_TRAIN_YAML, encoding="utf-8")

        r = client.post(
            f"/projects/{project.project_id}/runs/{run_id}/retrain",
        )
        assert r.status_code == 201, r.text
        assert r.json()["config_type"] == "train"

        store = JobStore()
        jobs = store.list_jobs(project_path=str(project.path))
        assert len(jobs) == 1
        assert jobs[0].config == {"train": {"enabled": True, "models": [{"type": "lightgbm"}]}}

    def test_retrain_404_unknown_project(self, client):
        r = client.post("/projects/nope/runs/whatever/retrain")
        assert r.status_code == 404

    def test_retrain_404_unknown_run(self, client, project_service):
        project = _make_project(project_service, "retrain-norun")
        r = client.post(f"/projects/{project.project_id}/runs/does-not-exist/retrain")
        assert r.status_code == 404

    def test_retrain_no_configs(self, client, project_service):
        """Run dir with no config/ directory → 400."""
        project = _make_project(project_service, "retrain-noconfig")
        run_id = "train-20240103_120000"
        run_dir = project.path / "output" / run_id
        _write_run_metadata(run_dir, run_id)  # metadata but NO config/ dir

        r = client.post(
            f"/projects/{project.project_id}/runs/{run_id}/retrain",
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 400

    def test_retrain_rejects_disallowed_custom_class(self, client, project_service):
        """R1-001: a run config with a disallowed custom_class prefix → 400, no job.

        Defense-in-depth: no web route writes ``<run_dir>/config/``, but the
        retrain route reads disk-sourced configs and should enforce the same
        custom_class trust boundary as ``POST /jobs``.
        """
        from energizados.web.store import JobStore

        project = _make_project(project_service, "retrain-evil")
        run_id = "train-20240104_120000"
        run_dir = project.path / "output" / run_id
        _write_run_metadata(run_dir, run_id)
        (run_dir / "config").mkdir(parents=True, exist_ok=True)
        evil_etl = (
            "etl:\n"
            "  sample:\n"
            "    enabled: true\n"
            '    input: "data/raw/x.csv"\n'
            '    output: "data/processed/x.parquet"\n'
            '    custom_class: "evil.module.Evil"\n'
        )
        (run_dir / "config" / "etl.yaml").write_text(evil_etl, encoding="utf-8")
        (run_dir / "config" / "train.yaml").write_text(_TRAIN_YAML, encoding="utf-8")

        # HTMX request → validation fragment.
        r = client.post(
            f"/projects/{project.project_id}/runs/{run_id}/retrain",
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 400, r.text
        store = JobStore()
        assert len(store.list_jobs(project_path=str(project.path))) == 0

        # JSON request → structured error body matching /jobs shape.
        r_json = client.post(
            f"/projects/{project.project_id}/runs/{run_id}/retrain",
        )
        assert r_json.status_code == 400, r_json.text
        detail = r_json.json()["detail"]
        assert detail["error"] == "custom_class_prefix_validation"
        assert "evil.module.Evil" in detail["invalid_prefixes"]
        assert len(store.list_jobs(project_path=str(project.path))) == 0

    def test_retrain_allows_src_prefix_custom_class(self, client, project_service):
        """R1-001: a run config with an allowed ``src.*`` custom_class → 201."""
        from energizados.web.store import JobStore

        project = _make_project(project_service, "retrain-src")
        run_id = "train-20240105_120000"
        run_dir = project.path / "output" / run_id
        _write_run_metadata(run_dir, run_id)
        (run_dir / "config").mkdir(parents=True, exist_ok=True)
        src_etl = (
            "etl:\n"
            "  sample:\n"
            "    enabled: true\n"
            '    input: "data/raw/x.csv"\n'
            '    output: "data/processed/x.parquet"\n'
            '    custom_class: "src.etl.MyETL"\n'
        )
        (run_dir / "config" / "etl.yaml").write_text(src_etl, encoding="utf-8")
        (run_dir / "config" / "train.yaml").write_text(_TRAIN_YAML, encoding="utf-8")

        r = client.post(
            f"/projects/{project.project_id}/runs/{run_id}/retrain",
        )
        assert r.status_code == 201, r.text
        store = JobStore()
        jobs = store.list_jobs(project_path=str(project.path))
        assert len(jobs) == 1
        assert jobs[0].config_type == "train"

    def test_retrain_stores_derived_from_run_id(self, client, project_service):
        """ADR-0003: retrain records the SOURCE run_id as derived_from_run_id.

        The new job's ``derived_from_run_id`` points at the URL path ``run_id``
        (the source Run being re-derived). This is the transport mirror of the
        ``run_metadata.json["derived_from"]`` that the worker later writes via
        ``ConfigPipelineBuilder(derived_from=...)`` (Phase 2 passthrough).
        """
        from energizados.web.store import JobStore

        project = _make_project(project_service, "retrain-lineage")
        run_id = "train-20240106_120000"
        run_dir = project.path / "output" / run_id
        _write_run_metadata(run_dir, run_id)
        (run_dir / "config").mkdir(parents=True, exist_ok=True)
        (run_dir / "config" / "train.yaml").write_text(_TRAIN_YAML, encoding="utf-8")

        r = client.post(
            f"/projects/{project.project_id}/runs/{run_id}/retrain",
        )
        assert r.status_code == 201, r.text

        store = JobStore()
        jobs = store.list_jobs(project_path=str(project.path))
        assert len(jobs) == 1
        # The source run_id is stored on the new job — distinct from retried_from
        # (which is None here: this is a fresh retrain, not a retry).
        assert jobs[0].derived_from_run_id == run_id
        assert jobs[0].retried_from is None


# ---------------------------------------------------------------------------
# Inference — form
# ---------------------------------------------------------------------------


class TestInferenceForm:
    """GET /projects/{project_id}/runs/{run_id}/inference."""

    def test_inference_form_lists_eligible_runs_and_inputs(self, client, project_service):
        project = _make_project(project_service, "infer-form")
        eligible = "train-20240201_120000"
        ineligible = "eda-20240201_120000"
        _write_run_metadata(
            project.path / "output" / eligible,
            eligible,
            model=True,
            model_types=["LGBMModel"],
        )
        _write_run_metadata(project.path / "output" / ineligible, ineligible, model=False)

        # An input file under data/processed/
        (project.path / "data" / "processed").mkdir(parents=True, exist_ok=True)
        (project.path / "data" / "processed" / "foo.parquet").write_bytes(b"")

        # Non-HTMX GET → JSON describing eligible runs + input files.
        r = client.get(f"/projects/{project.project_id}/runs/{eligible}/inference")
        assert r.status_code == 200, r.text
        data = r.json()
        run_ids = [item["run_id"] for item in data["eligible_runs"]]
        assert run_ids == [eligible]  # only the trained run is eligible
        assert "data/processed/foo.parquet" in data["input_files"]
        assert data["context_run_id"] == eligible

    def test_inference_form_htmx_renders_fragment(self, client, project_service):
        project = _make_project(project_service, "infer-form-htmx")
        eligible = "train-20240202_120000"
        _write_run_metadata(project.path / "output" / eligible, eligible, model=True)

        r = client.get(
            f"/projects/{project.project_id}/runs/{eligible}/inference",
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200, r.text
        assert "model_run_id" in r.text  # the form select

    def test_inference_form_404_unknown_run(self, client, project_service):
        project = _make_project(project_service, "infer-form-404")
        r = client.get(f"/projects/{project.project_id}/runs/ghost/inference")
        assert r.status_code == 404

    def test_inference_form_404_unknown_project(self, client):
        r = client.get("/projects/nope/runs/ghost/inference")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Inference — enqueue
# ---------------------------------------------------------------------------


class TestInferenceEnqueue:
    """POST /projects/{project_id}/inference."""

    def _setup_eligible_run(self, project, run_id="train-20240301_120000"):
        _write_run_metadata(
            project.path / "output" / run_id,
            run_id,
            model=True,
            model_types=["LGBMModel"],
        )
        (project.path / "data" / "processed").mkdir(parents=True, exist_ok=True)
        (project.path / "data" / "processed" / "foo.parquet").write_bytes(b"")
        return run_id

    def test_inference_post_enqueues_infer(self, client, project_service):
        from energizados.web.store import JobStore

        project = _make_project(project_service, "infer-post")
        run_id = self._setup_eligible_run(project)

        r = client.post(
            f"/projects/{project.project_id}/inference",
            data={
                "model_run_id": run_id,
                "input_path": "data/processed/foo.parquet",
                "threshold": "0.5",
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["config_type"] == "infer"

        store = JobStore()
        jobs = store.list_jobs(project_path=str(project.path))
        assert len(jobs) == 1
        job = jobs[0]
        assert job.config_type == "infer"
        assert job.project_path == str(project.path)
        infer = job.config["infer"]
        assert infer["model_path"] == f"output/{run_id}/models/model.pkl"
        assert infer["input_path"] == "data/processed/foo.parquet"
        assert infer["threshold"] == 0.5
        assert infer["enabled"] is True

    def test_inference_post_htmx_returns_fragment(self, client, project_service):
        project = _make_project(project_service, "infer-post-htmx")
        run_id = self._setup_eligible_run(project)

        r = client.post(
            f"/projects/{project.project_id}/inference",
            data={
                "model_run_id": run_id,
                "input_path": "data/processed/foo.parquet",
                "threshold": "0.5",
            },
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 201, r.text

    def test_inference_post_400_ineligible_model(self, client, project_service):
        project = _make_project(project_service, "infer-ineligible")
        ineligible = "eda-20240302_120000"
        _write_run_metadata(project.path / "output" / ineligible, ineligible, model=False)
        (project.path / "data" / "processed").mkdir(parents=True, exist_ok=True)
        (project.path / "data" / "processed" / "foo.parquet").write_bytes(b"")

        r = client.post(
            f"/projects/{project.project_id}/inference",
            data={
                "model_run_id": ineligible,
                "input_path": "data/processed/foo.parquet",
                "threshold": "0.5",
            },
        )
        assert r.status_code == 400, r.text

    def test_inference_post_400_bad_input_path_traversal(self, client, project_service):
        project = _make_project(project_service, "infer-traversal")
        run_id = self._setup_eligible_run(project)

        r = client.post(
            f"/projects/{project.project_id}/inference",
            data={
                "model_run_id": run_id,
                "input_path": "../etc/passwd",
                "threshold": "0.5",
            },
        )
        assert r.status_code == 400, r.text

    def test_inference_post_400_nonexistent_input(self, client, project_service):
        project = _make_project(project_service, "infer-noinput")
        run_id = self._setup_eligible_run(project)

        r = client.post(
            f"/projects/{project.project_id}/inference",
            data={
                "model_run_id": run_id,
                "input_path": "data/processed/missing.parquet",
                "threshold": "0.5",
            },
        )
        assert r.status_code == 400, r.text

    def test_inference_post_400_bad_threshold(self, client, project_service):
        project = _make_project(project_service, "infer-badthreshold")
        run_id = self._setup_eligible_run(project)

        r = client.post(
            f"/projects/{project.project_id}/inference",
            data={
                "model_run_id": run_id,
                "input_path": "data/processed/foo.parquet",
                "threshold": "1.5",
            },
        )
        assert r.status_code == 400, r.text

    def test_inference_post_404_unknown_project(self, client):
        r = client.post(
            "/projects/nope/inference",
            data={
                "model_run_id": "x",
                "input_path": "data/processed/x.parquet",
                "threshold": "0.5",
            },
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Route-ordering regression (no route shadowing)
# ---------------------------------------------------------------------------


class TestRouteOrdering:
    """New routes must not shadow each other or be shadowed by param routes."""

    def test_get_inference_form_not_shadowed(self, client, project_service):
        """GET .../runs/{run_id}/inference returns a real status (not 404 from shadowing)."""
        project = _make_project(project_service, "route-get")
        run_id = "train-20240401_120000"
        _write_run_metadata(project.path / "output" / run_id, run_id, model=True)

        r = client.get(f"/projects/{project.project_id}/runs/{run_id}/inference")
        # 200 (form/JSON) — definitely not 404 from route collision.
        assert r.status_code == 200, r.text

    def test_post_inference_not_shadowed(self, client, project_service):
        """POST /projects/{project_id}/inference returns a real status (not 404)."""
        project = _make_project(project_service, "route-post")
        # Missing model_run_id → 400 (form validation), NOT 404 (route shadowing).
        r = client.post(
            f"/projects/{project.project_id}/inference",
            data={"model_run_id": "", "input_path": "", "threshold": "0.5"},
        )
        assert r.status_code != 404
