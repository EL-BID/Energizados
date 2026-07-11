"""
Slow integration test for project-scoped job execution (Phase 1 multi-project).

Creates a real project under a tmp_path workspace root, enqueues a lightweight
training job scoped to that project (project_path set), and runs one poll cycle
of the worker (spawning a real child process). Asserts:

- The job row records the correct project_path + run_id (child-written).
- The run directory lands under <project>/output/ and contains run_metadata.json.
- A project-scoped RunManager(output_dir=<project>/output) finds the run.

Uses training (not EDA/ETL) because only training produces a run_dir with
run_metadata.json. Marked ``slow``: it spawns a child process and runs a real
(minimal) LightGBM training. Excluded from the default pytest run.
"""

import shutil
from pathlib import Path

import pytest
import yaml

from energizados.api import RunManager
from energizados.web.models import JobStatus
from energizados.web.projects import ProjectService
from energizados.web.runner import JobRunner
from energizados.web.store import JobStore


def _sample_dataset_src() -> Path:
    """Locate the bundled sample dataset shipped with the framework templates."""
    import energizados

    return (
        Path(energizados.__file__).parent / "templates" / "data" / "raw" / "sample_dataset.parquet"
    )


@pytest.mark.slow
def test_project_scoped_job_lands_under_project_output(tmp_path, monkeypatch):
    """A project-scoped training job runs in the project dir and is attributed."""
    # Isolate workspace root, registry, and DB under tmp_path.
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    registry_path = tmp_path / "projects.json"
    db_path = tmp_path / "jobs.db"

    # The child process inherits this env var so its JobStore() writes to the
    # same DB even after os.chdir into the project directory.
    monkeypatch.setenv("ENERGIZADOS_JOBS_DB", str(db_path))

    ps = ProjectService(workspace_root=workspace_root, registry_path=registry_path)
    project = ps.create_project(name="integ")

    # The generated train.yaml expects data/processed/sample_dataset.parquet.
    processed_dir = project.path / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(_sample_dataset_src(), processed_dir / "sample_dataset.parquet")

    # Build a known-valid train config from the generated template, tweaked for speed.
    cfg = yaml.safe_load((project.path / "config" / "train.yaml").read_text())
    cfg["train"]["split"] = {
        "method": "random",
        "test_size": 0.2,
        "val_size": 0.15,
        "random_state": 42,
    }
    model = cfg["train"]["models"][0]
    model["hyperparams"] = {
        "num_leaves": 15,
        "learning_rate": 0.1,
        "n_estimators": 30,
        "verbose": -1,
    }
    model["hyperparam_search"] = {"enabled": False}
    model["sampling"] = {"method": "undersample", "threshold": 0.5}
    cfg["train"]["evaluation"]["generate_plots"] = False

    store = JobStore(db_path=str(db_path))
    job_id = store.create_job(cfg, "train", project_path=str(project.path))

    # Run one poll cycle. This spawns a real child process (multiprocessing.Process)
    # that os.chdir's into the project dir and runs the training pipeline.
    runner = JobRunner(store=store)
    processed = runner._poll()
    assert processed is True

    job = store.get_job(job_id)
    assert job.project_path == str(project.path)
    assert job.status == JobStatus.SUCCESS
    # The child writes run_id directly to the row on success (child = source of truth).
    assert job.run_id is not None, "child should have written run_id to the row"

    # The run directory lives under <project>/output/<run_id>/
    run_dir = project.path / "output" / job.run_id
    assert run_dir.is_dir(), f"run dir {run_dir} should exist"
    assert (run_dir / "run_metadata.json").is_file(), "run_metadata.json should exist"

    # A project-scoped RunManager finds the run.
    scoped_manager = RunManager(output_dir=str(project.path / "output"))
    metadata = scoped_manager.get_run(job.run_id)
    assert metadata is not None, "scoped RunManager should find the run"
    assert metadata.run_id == job.run_id
