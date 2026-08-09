"""
Work-unit 1: typed-Run alignment for the web console UI (ADR-0001).

The backend now emits typed Runs (``run_type``: training/etl/eda/inference) and
``RunMetadata`` omits ``val_auc``/``val_f1``/``model_types``/``feature_count``
for non-training runs. The dashboard / runs-list / run-detail surfaces predate
typing and assumed every run was a training run. These tests pin the gaps so
non-training runs stop leaking ``None`` metrics into the AUC/F1 timeline and
stop rendering empty training-only markup.

Strict TDD: every test below FAILS on the pre-fix code (red), then passes once
the surgical run_type filter/guard is applied (green).
"""

import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from energizados.core.builders.run_manager import RunMetadata
from energizados.web.projects import ProjectService

# NOTE: the timeline routes call ``run.timestamp.isoformat()`` — i.e. they expect
# a datetime-like timestamp (this is the contract the existing Mock-based
# timeline tests already rely on). RunMetadata stores timestamps as strings on
# disk, so timeline tests below inject datetime objects to match the route
# contract and isolate the run_type filtering gap.


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client with an isolated workspace root, registry and jobs DB."""
    monkeypatch.setenv("ENERGIZADOS_WORKSPACE_ROOT", str(tmp_path / "ws"))
    monkeypatch.setenv("ENERGIZADOS_JOBS_DB", str(tmp_path / "jobs.db"))
    from energizados.web.app import app

    app.state.project_service = ProjectService(
        workspace_root=tmp_path / "ws",
        registry_path=tmp_path / "projects.json",
    )
    return TestClient(app)


@pytest.fixture
def project_service(client):
    """The ProjectService wired into the test client."""
    from energizados.web.app import app

    return app.state.project_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta_dict(
    run_id,
    run_type,
    val_auc=None,
    val_f1=None,
    model_types=None,
    feature_count=None,
    status="success",
    timestamp="2024-01-15T10:30:00",
    output_paths=None,
):
    """Build a run_metadata.json-style dict.

    Training-specific keys are only emitted for training runs, mirroring the
    real ``RunMetadata.to_dict`` serialization (ADR-0001).
    """
    d = {
        "run_id": run_id,
        "timestamp": timestamp,
        "duration_seconds": 1.0,
        "energizados_version": "0.0.0-test",
        "python_version": "3.11.0",
        "git_commit": "deadbeef",
        "config_files": [],
        "status": status,
        "output_paths": output_paths or {},
        "run_type": run_type,
        "model_types": model_types if model_types is not None else [],
    }
    if run_type == "training":
        d["val_auc"] = val_auc
        d["val_f1"] = val_f1
        d["feature_count"] = feature_count
    return d


def _meta(run_id, run_type, timestamp=None, **kwargs):
    """Build a real RunMetadata via the tolerant from_dict loader.

    ``timestamp`` (when given) overrides the on-disk string form with a
    datetime-like value so timeline routes (which call ``.isoformat()``) work.
    """
    run = RunMetadata.from_dict(_meta_dict(run_id, run_type, **kwargs))
    if timestamp is not None:
        run.timestamp = timestamp
    return run


def _training_meta(run_id="train-001", timestamp=None):
    return _meta(
        run_id,
        "training",
        val_auc=0.909,
        val_f1=0.808,
        model_types=["LGBMModel"],
        feature_count=42,
        timestamp=timestamp,
    )


def _etl_meta(run_id="etl-001", timestamp=None):
    return _meta(run_id, "etl", timestamp=timestamp)


def _write_run_on_disk(output_dir, run_id, metadata_dict):
    """Write a run_metadata.json for run_id under output_dir (real on-disk run)."""
    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata_dict), encoding="utf-8")
    return run_dir


def _extract_row(html, run_id):
    """Return the first <tr>...</tr> block containing run_id, or None."""
    for row in re.findall(r"<tr>.*?</tr>", html, re.DOTALL):
        if run_id in row:
            return row
    return None


def _bucket_section(html, bucket):
    """Return the <section data-run-type="bucket">...</section> block, or None."""
    m = re.search(
        rf'<section[^>]*data-run-type="{re.escape(bucket)}"[^>]*>.*?</section>',
        html,
        re.DOTALL,
    )
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Familia 1 (HIGH): timeline leakage
# ---------------------------------------------------------------------------


class TestTimelineFiltersNonTrainingRuns:
    """AUC/F1 timeline must include training runs only.

    Non-training runs carry ``val_auc=None``/``val_f1=None`` and would inject
    null data points into the metrics chart. The canonical filter pattern is
    ``_resolve_run_type`` (reused from project_detail/Compare).
    """

    def test_global_timeline_excludes_non_training_runs(self, client):
        """GET /api/dashboard/timeline omits etl/eda/inference runs."""
        runs = [
            _training_meta("train-001", timestamp=datetime(2024, 1, 15, 10, 30, 0)),
            _etl_meta("etl-001", timestamp=datetime(2024, 1, 15, 11, 0, 0)),
            _meta("eda-001", "eda", timestamp=datetime(2024, 1, 15, 12, 0, 0)),
            _meta("inf-001", "inference", timestamp=datetime(2024, 1, 15, 13, 0, 0)),
        ]
        with patch("energizados.web.app.RunManager") as mock_rm:
            mock_rm.return_value.list_runs.return_value = runs
            response = client.get("/api/dashboard/timeline")

        assert response.status_code == 200
        data = response.json()
        # Only the training run survives as a data point.
        assert data["run_ids"] == ["train-001"]
        assert data["auc"] == [0.909]
        assert data["f1"] == [0.808]

    def test_global_timeline_keeps_legacy_training_runs(self, client):
        """Runs without run_type (legacy/untyped Mocks) default to training."""
        from datetime import datetime
        from unittest.mock import Mock

        legacy = Mock()
        legacy.run_id = "legacy-001"
        legacy.timestamp = datetime(2024, 1, 15, 10, 30, 0)
        legacy.val_auc = 0.77
        legacy.val_f1 = 0.66
        legacy.status = "success"
        # run_type intentionally unset on the Mock -> _resolve_run_type defaults
        # to "training".
        with patch("energizados.web.app.RunManager") as mock_rm:
            mock_rm.return_value.list_runs.return_value = [legacy]
            response = client.get("/api/dashboard/timeline")

        assert response.status_code == 200
        data = response.json()
        assert data["run_ids"] == ["legacy-001"]
        assert data["auc"] == [0.77]

    def test_project_timeline_excludes_non_training_runs(self, client, project_service):
        """Project-scoped timeline omits non-training runs too."""
        project = project_service.create_project("timetravel")
        runs = [
            _training_meta("train-001", timestamp=datetime(2024, 1, 15, 10, 30, 0)),
            _etl_meta("etl-001", timestamp=datetime(2024, 1, 15, 11, 0, 0)),
        ]
        with patch("energizados.web.app._run_manager_for") as mock_rm_for:
            mock_rm_for.return_value.list_runs.return_value = runs
            response = client.get(f"/projects/{project.project_id}/api/dashboard/timeline")

        assert response.status_code == 200
        data = response.json()
        assert data["run_ids"] == ["train-001"]
        assert data["auc"] == [0.909]
        assert data["f1"] == [0.808]


class TestTimelineHandlesStringTimestamps:
    """RunMetadata.timestamp is a serialized ISO string on disk, not a datetime.

    ``RunManager.list_runs`` returns it unparsed (it even sorts by the string).
    The timeline routes must return the string verbatim and never call
    ``.isoformat()`` on it — that raises ``AttributeError`` on a str and 500s
    the endpoint for every real run.
    """

    def test_global_timeline_accepts_string_timestamp(self, client):
        train_run = _training_meta("train-001")  # timestamp is a real ISO str
        # Contract under test: the timestamp is a str (what list_runs yields).
        assert isinstance(train_run.timestamp, str)
        with patch("energizados.web.app.RunManager") as mock_rm:
            mock_rm.return_value.list_runs.return_value = [train_run]
            response = client.get("/api/dashboard/timeline")

        assert response.status_code == 200
        data = response.json()
        assert data["run_ids"] == ["train-001"]
        assert data["timestamps"] == [train_run.timestamp]

    def test_project_timeline_accepts_string_timestamp(self, client, project_service):
        project = project_service.create_project("timestr")
        train_run = _training_meta("train-001")
        assert isinstance(train_run.timestamp, str)
        with patch("energizados.web.app._run_manager_for") as mock_rm_for:
            mock_rm_for.return_value.list_runs.return_value = [train_run]
            response = client.get(f"/projects/{project.project_id}/api/dashboard/timeline")

        assert response.status_code == 200
        data = response.json()
        assert data["run_ids"] == ["train-001"]
        assert data["timestamps"] == [train_run.timestamp]


# ---------------------------------------------------------------------------
# Familia 2 (MEDIUM): runs_list template guards
# ---------------------------------------------------------------------------


class TestRunsListTemplateGuards:
    """runs_list.html must hide AUC/F1 cells for non-training runs."""

    def test_runs_list_hides_auc_f1_for_non_training(self, client):
        runs = [_training_meta("train-001"), _etl_meta("etl-001")]
        with patch("energizados.web.app.RunManager") as mock_rm:
            mock_rm.return_value.list_runs.return_value = runs
            response = client.get("/runs")

        assert response.status_code == 200
        html = response.text
        # Training row renders its formatted AUC.
        train_row = _extract_row(html, "train-001")
        assert train_row is not None
        assert "0.909" in train_row
        # Non-training row must not render the None-metric dash markup that the
        # unguarded template emits for missing val_auc/val_f1.
        etl_row = _extract_row(html, "etl-001")
        assert etl_row is not None
        assert "—" not in etl_row


# ---------------------------------------------------------------------------
# Familia 2 (MEDIUM): run_detail template guards
# ---------------------------------------------------------------------------


class TestRunDetailTemplateGuards:
    """run_detail.html must hide model_types/feature_count for non-training runs."""

    def test_run_detail_hides_training_only_fields_for_non_training(self, client):
        etl_run = _etl_meta("etl-001")
        with (
            patch("energizados.web.app.RunManager") as mock_rm,
            patch("energizados.web.app._resolve_run_dir", return_value=None),
        ):
            mock_rm.return_value.get_run.return_value = etl_run
            response = client.get("/runs/etl-001")

        assert response.status_code == 200
        html = response.text
        # Training-only metadata rows must be absent for a non-training run.
        assert "<th>Models</th>" not in html
        assert "<th>Features</th>" not in html

    def test_run_detail_shows_training_only_fields_for_training(self, client):
        train_run = _training_meta("train-001")
        with (
            patch("energizados.web.app.RunManager") as mock_rm,
            patch("energizados.web.app._resolve_run_dir", return_value=None),
        ):
            mock_rm.return_value.get_run.return_value = train_run
            response = client.get("/runs/train-001")

        assert response.status_code == 200
        html = response.text
        assert "<th>Models</th>" in html
        assert "LGBMModel" in html
        assert "<th>Features</th>" in html
        assert "<td>42</td>" in html


# ---------------------------------------------------------------------------
# Familia 2 (MEDIUM): project_detail by-type table guards
# ---------------------------------------------------------------------------


class TestProjectDetailByTypeTable:
    """The Jobs & Runs by-type table must render AUC/F1 columns only for training."""

    def test_by_type_table_only_shows_auc_f1_for_training(self, client, project_service):
        project = project_service.create_project("bytype")
        output_dir = Path(project.path) / "output"
        _write_run_on_disk(output_dir, "train-001", _training_meta("train-001").to_dict())
        _write_run_on_disk(
            output_dir, "etl-001", _meta_dict("etl-001", "etl", timestamp="2024-01-15T11:00:00")
        )

        response = client.get(f"/projects/{project.project_id}")

        assert response.status_code == 200
        html = response.text
        # AUC/F1 column headers appear in exactly one bucket (training). The
        # unguarded template emits them once per bucket (training + etl => 2).
        assert html.count("<th>AUC</th>") == 1
        assert html.count("<th>F1</th>") == 1
        # The training run's formatted AUC still renders inside its bucket.
        assert "0.909" in html


# ---------------------------------------------------------------------------
# Work-unit 2: global /runs grouped by run_type + /dashboard type-awareness
# ---------------------------------------------------------------------------


class TestRunsListGroupedByType:
    """/runs HTML groups runs by run_type, mirroring project_detail by-type tables.

    The JSON API contract stays flat ({"runs": [...]}).
    """

    def test_runs_list_groups_runs_by_type_html(self, client):
        etl_with_output = _meta(
            "etl-001",
            "etl",
            output_paths={"etl_sample": "data/processed/sample.parquet"},
        )
        runs = [_training_meta("train-001"), etl_with_output]
        with patch("energizados.web.app.RunManager") as mock_rm:
            mock_rm.return_value.list_runs.return_value = runs
            response = client.get("/runs")

        assert response.status_code == 200
        html = response.text
        # The etl run lands in the etl bucket; the training run does not.
        etl_section = _bucket_section(html, "etl")
        assert etl_section is not None
        assert "etl-001" in etl_section
        assert "train-001" not in etl_section
        # Non-training bucket renders the produced-artifact label (not the raw
        # filesystem path) as its "Output".
        assert "ETL: sample" in etl_section
        # Training bucket keeps its AUC column.
        train_section = _bucket_section(html, "training")
        assert train_section is not None
        assert "train-001" in train_section
        assert "0.909" in train_section

    def test_runs_list_json_api_still_flat(self, client):
        """The /runs JSON branch must keep the flat {"runs": [...]} contract."""
        runs = [_training_meta("train-001"), _etl_meta("etl-001")]
        with patch("energizados.web.app.RunManager") as mock_rm:
            mock_rm.return_value.list_runs.return_value = runs
            response = client.get("/runs", headers={"accept": "application/json"})

        assert response.status_code == 200
        data = response.json()
        assert list(data.keys()) == ["runs"]
        assert {r["run_id"] for r in data["runs"]} == {"train-001", "etl-001"}


class TestDashboardTypeAwareness:
    """/dashboard communicates the training-only timeline + per-type counts."""

    def test_dashboard_renders_run_counts_and_training_label(self, client):
        runs = [
            _training_meta("train-001", timestamp=datetime(2024, 1, 15, 10, 30, 0)),
            _etl_meta("etl-a", timestamp=datetime(2024, 1, 15, 11, 0, 0)),
            _etl_meta("etl-b", timestamp=datetime(2024, 1, 15, 12, 0, 0)),
            _meta("eda-001", "eda", timestamp=datetime(2024, 1, 15, 13, 0, 0)),
        ]
        with patch("energizados.web.app.RunManager") as mock_rm:
            mock_rm.return_value.list_runs.return_value = runs
            response = client.get("/dashboard")

        assert response.status_code == 200
        html = response.text
        # Timeline is training-only since work-unit 1 — the chart is labeled so.
        assert "Training runs" in html
        # Per-type count tiles (data-run-count="<bucket>">N<) are rendered.
        assert 'data-run-count="training">1<' in html
        assert 'data-run-count="etl">2<' in html
        assert 'data-run-count="eda">1<' in html
        assert 'data-run-count="inference">0<' in html
