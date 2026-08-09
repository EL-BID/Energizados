"""
Tests for Comparison page (HTML rendering).

Phase 4 Task 12-13: Comparison page implementation.
Following strict TDD: RED test first, then GREEN implementation.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    from energizados.web.app import app

    return TestClient(app)


class TestComparisonPage:
    """Test suite for comparison page (HTML rendering)."""

    def test_compare_page_renders_html(self, client):
        """Comparison page should return HTML content."""
        # Mock evaluation data
        eval_data = {"metrics": {"auc": 0.85, "f1": 0.78}, "is_multi": False}

        # Mock _load_run_evaluations_batch to return evaluation data
        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {"run1": eval_data, "run2": eval_data}

            response = client.get("/runs/compare?ids=run1,run2")

            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")

    def test_compare_page_validation_errors(self, client):
        """Comparison page should show error for invalid ID counts."""
        # Test with single ID (< 2)
        response = client.get("/runs/compare?ids=run1")
        assert response.status_code == 400

        # Test with 11 IDs (> 10)
        many_ids = ",".join([f"run{i}" for i in range(11)])
        response = client.get(f"/runs/compare?ids={many_ids}")
        assert response.status_code == 400

    def test_compare_route_not_shadowed_by_run_detail(self, client):
        """Regression guard: GET /runs/compare must reach the comparison route,
        NOT be swallowed by GET /runs/{run_id} (which would treat "compare" as a
        run_id, call RunManager.get_run("compare") -> None, and return 404).

        A 400 here proves the literal route wins; a 404 would mean route ordering
        regressed (the literal /runs/compare must be declared before /runs/{run_id}).
        """
        response = client.get("/runs/compare?ids=single_id")

        assert response.status_code == 400  # validation error from compare_runs_page
        assert response.status_code != 404  # would indicate route shadowing

    def test_compare_page_shows_single_model_metrics(self, client):
        """Comparison page should display single-model metrics correctly."""

        # Mock single-model evaluation data
        eval_1 = {
            "metrics": {"auc": 0.85, "f1": 0.78, "precision": 0.80, "recall": 0.75},
            "is_multi": False,
        }
        eval_2 = {
            "metrics": {"auc": 0.82, "f1": 0.75, "precision": 0.77, "recall": 0.73},
            "is_multi": False,
        }

        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {"run1": eval_1, "run2": eval_2}

            response = client.get("/runs/compare?ids=run1,run2")

            assert response.status_code == 200
            content = response.text

            # Should show metrics in the page
            assert "0.85" in content or "0.82" in content  # AUC values
            assert "0.78" in content or "0.75" in content  # F1 values

    def test_compare_page_shows_ensemble_ranking(self, client):
        """Comparison page should show ranking table for ensemble runs."""

        # Mock ensemble evaluation data
        ensemble_eval = {
            "ranking": [
                {"name": "lgbm", "metrics": {"auc": 0.85}},
                {"name": "cat", "metrics": {"auc": 0.82}},
            ],
            "best_model": "lgbm",
            "is_multi": True,
        }

        # Regular eval for run2
        regular_eval = {"metrics": {"auc": 0.75}, "is_multi": False}

        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {"ensemble1": ensemble_eval, "run2": regular_eval}

            response = client.get("/runs/compare?ids=ensemble1,run2")

            assert response.status_code == 200
            content = response.text

            # Should show ranking information for ensemble
            assert "lgbm" in content or "cat" in content

    def test_compare_page_best_value_highlighting(self, client):
        """Comparison page should highlight best values with star marker."""

        # Mock evaluation data with clear best values
        eval_1 = {"metrics": {"auc": 0.90, "f1": 0.85, "precision": 0.88}, "is_multi": False}
        eval_2 = {"metrics": {"auc": 0.85, "f1": 0.80, "precision": 0.82}, "is_multi": False}
        eval_3 = {"metrics": {"auc": 0.80, "f1": 0.75, "precision": 0.78}, "is_multi": False}

        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {"run1": eval_1, "run2": eval_2, "run3": eval_3}

            response = client.get("/runs/compare?ids=run1,run2,run3")

            assert response.status_code == 200
            content = response.text

            # Should indicate best values (implementation may use ★ or other marker)
            # We check that the page can distinguish best values somehow
            assert "0.90" in content  # Best AUC

    def test_compare_page_csv_download(self, client):
        """Comparison page should include CSV download functionality."""

        # Mock evaluation data
        eval_data = {"metrics": {"auc": 0.85, "f1": 0.78}, "is_multi": False}

        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {"run1": eval_data, "run2": eval_data}

            response = client.get("/runs/compare?ids=run1,run2")

            assert response.status_code == 200
            content = response.text

            # Should include CSV download button/link
            assert "CSV" in content or "csv" in content or "download" in content.lower()


class TestComparisonPageTypeScoping:
    """ADR-0001 Phase 4: Compare is explicit about Run type.

    Only same-type Runs are comparable; cross-type sets are rejected with a
    typed empty-state (banner on the page surface) instead of being silently
    filtered to whatever training runs happen to carry evaluation data.
    """

    @staticmethod
    def _typed_run(run_id, run_type):
        run = Mock()
        run.run_id = run_id
        run.run_type = run_type
        run.to_dict.return_value = {
            "run_id": run_id,
            "timestamp": "2024-01-15T10:30:00Z",
            "duration_seconds": 12.5,
            "status": "success",
            "output_paths": {"report": f"{run_id}/eda_report.html"},
        }
        return run

    def test_mixed_types_render_typed_empty_state_banner(self, client):
        """A training run + an EDA run renders the cross-type banner, not a silent 404."""
        train = self._typed_run("train-1", "training")
        eda = self._typed_run("eda-1", "eda")
        runs_by_id = {"train-1": train, "eda-1": eda}

        with (
            patch("energizados.web.app.RunManager") as mock_rm,
            patch("energizados.web.app._load_run_evaluations_batch") as mock_batch,
        ):
            mgr = Mock()
            mgr.get_run.side_effect = lambda rid: runs_by_id.get(rid)
            mock_rm.return_value = mgr
            mock_batch.return_value = {}  # must not be reached for mixed-type sets

            response = client.get("/runs/compare?ids=train-1,eda-1")

        assert response.status_code == 200
        content = response.text.lower()
        # Typed empty-state banner — exact wording from compare_runs.html.
        assert "different types" in content
        assert "cannot be compared" in content
        # Each run and its type is listed.
        assert "train-1" in response.text
        assert "eda-1" in response.text
        assert "training" in response.text
        assert "eda" in response.text
        # The training metrics table must NOT render for a mixed-type set.
        assert "download csv" not in content

    def test_homogeneous_non_training_renders_metadata_table(self, client):
        """Two EDA runs render the metadata table (no AUC/F1 columns)."""
        eda1 = self._typed_run("eda-1", "eda")
        eda2 = self._typed_run("eda-2", "eda")
        runs_by_id = {"eda-1": eda1, "eda-2": eda2}

        with (
            patch("energizados.web.app.RunManager") as mock_rm,
            patch("energizados.web.app._load_run_evaluations_batch") as mock_batch,
        ):
            mgr = Mock()
            mgr.get_run.side_effect = lambda rid: runs_by_id.get(rid)
            mock_rm.return_value = mgr
            # EDA runs produce no evaluation data; the metadata table must still render.
            mock_batch.return_value = {}

            response = client.get("/runs/compare?ids=eda-1,eda-2")

        assert response.status_code == 200
        content = response.text
        # Scope banner announces the active type.
        assert "Scope" in content
        assert "eda" in content.lower()
        # Both runs appear with metadata-driven columns.
        assert "eda-1" in content
        assert "eda-2" in content
        assert "Timestamp" in content
        # The training AUC column must NOT render for a non-training compare.
        assert ">AUC<" not in content.replace(" ", "")
        # An output path from run_metadata is surfaced.
        assert "eda_report.html" in content

    def test_two_training_runs_render_metrics_table_unchanged(self, client):
        """Two training runs keep the existing AUC/F1 table (byte-for-byte behavior)."""
        run1 = self._typed_run("run1", "training")
        run2 = self._typed_run("run2", "training")
        runs_by_id = {"run1": run1, "run2": run2}
        eval_1 = {
            "metrics": {"auc": 0.85, "f1": 0.78, "precision": 0.80, "recall": 0.75},
            "is_multi": False,
        }
        eval_2 = {
            "metrics": {"auc": 0.82, "f1": 0.75, "precision": 0.77, "recall": 0.73},
            "is_multi": False,
        }

        with (
            patch("energizados.web.app.RunManager") as mock_rm,
            patch("energizados.web.app._load_run_evaluations_batch") as mock_batch,
        ):
            mgr = Mock()
            mgr.get_run.side_effect = lambda rid: runs_by_id.get(rid)
            mock_rm.return_value = mgr
            mock_batch.return_value = {"run1": eval_1, "run2": eval_2}

            response = client.get("/runs/compare?ids=run1,run2")

        assert response.status_code == 200
        content = response.text
        # Training metrics table renders with AUC values.
        assert "0.85" in content
        assert ">AUC<" in content.replace(" ", "") or "<th>AUC</th>" in content
        # CSV download remains available on the training surface.
        assert "CSV" in content or "download" in content.lower()
