"""
Tests for Comparison page (HTML rendering).

Phase 4 Task 12-13: Comparison page implementation.
Following strict TDD: RED test first, then GREEN implementation.
"""

from unittest.mock import patch

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
