"""
Tests for Comparison API endpoint.

Phase 4 Task 10-11: Comparison API endpoint implementation.
Following strict TDD: RED test first, then GREEN implementation.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    from energizados.web.app import app

    return TestClient(app)


@pytest.fixture
def mock_run_manager():
    """Mock RunManager for testing."""
    with patch("energizados.web.app.RunManager") as mock:
        manager_instance = Mock()
        mock.return_value = manager_instance
        yield manager_instance


class TestComparisonApi:
    """Test suite for comparison API endpoint."""

    def test_compare_api_returns_correct_structure(self, client, mock_run_manager):
        """API should return correct JSON structure with runs dictionary."""
        # Mock run metadata
        mock_run = Mock()
        mock_run.run_id = "run1"
        mock_run.timestamp = datetime(2024, 1, 15, 10, 30, 0)
        mock_run.status = "success"
        mock_run.to_dict.return_value = {"run_id": "run1", "status": "success"}

        mock_run_manager.get_run.return_value = mock_run

        # Mock evaluation data
        mock_eval = {"metrics": {"auc": 0.85, "f1": 0.78}, "is_multi": False}

        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {"run1": mock_eval}

            response = client.get("/api/runs/compare?ids=run1,run2")

            assert response.status_code == 200
            data = response.json()

            # Verify structure
            assert "runs" in data
            assert isinstance(data["runs"], dict)

    def test_compare_api_validation_errors(self, client):
        """API should return 400 for <2 or >10 IDs."""
        # Test with single ID (< 2)
        response = client.get("/api/runs/compare?ids=run1")
        assert response.status_code == 400

        # Test with 11 IDs (> 10)
        many_ids = ",".join([f"run{i}" for i in range(11)])
        response = client.get(f"/api/runs/compare?ids={many_ids}")
        assert response.status_code == 400

    def test_compare_api_mixed_run_types(self, client, mock_run_manager):
        """API should handle both single-model and multi-model runs."""

        # Mock runs metadata
        def create_mock_run(run_id):
            mock_run = Mock()
            mock_run.run_id = run_id
            mock_run.timestamp = datetime(2024, 1, 15, 10, 30, 0)
            mock_run.status = "success"
            mock_run.to_dict.return_value = {"run_id": run_id, "status": "success"}
            return mock_run

        mock_run_manager.get_run.side_effect = lambda x: create_mock_run(x)

        # Mock mixed evaluation data
        single_eval = {"metrics": {"auc": 0.85}, "is_multi": False}
        multi_eval = {
            "ranking": ["lgbm", "cat"],
            "is_multi": True,
        }

        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {
                "single-run": single_eval,
                "multi-run": multi_eval,
            }

            response = client.get("/api/runs/compare?ids=single-run,multi-run")

            assert response.status_code == 200
            data = response.json()

            # Should handle both types
            assert "single-run" in data["runs"]
            assert "multi-run" in data["runs"]
            assert data["runs"]["single-run"]["is_multi"] is False
            assert data["runs"]["multi-run"]["is_multi"] is True

    def test_compare_api_skips_missing_runs(self, client, mock_run_manager):
        """API should return partial results when some runs missing eval data."""

        # Mock runs metadata
        def create_mock_run(run_id):
            mock_run = Mock()
            mock_run.run_id = run_id
            mock_run.timestamp = datetime(2024, 1, 15, 10, 30, 0)
            mock_run.status = "success"
            mock_run.to_dict.return_value = {"run_id": run_id, "status": "success"}
            return mock_run

        mock_run_manager.get_run.side_effect = lambda x: create_mock_run(x)

        # Mock partial evaluation data (run2 missing)
        eval_1 = {"metrics": {"auc": 0.85}, "is_multi": False}
        eval_3 = {"metrics": {"auc": 0.80}, "is_multi": False}

        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {"run1": eval_1, "run3": eval_3}

            response = client.get("/api/runs/compare?ids=run1,run2,run3")

            assert response.status_code == 200
            data = response.json()

            # Should return partial results
            assert "run1" in data["runs"]
            assert "run3" in data["runs"]
            # run2 is omitted (missing eval data)

    def test_compare_api_all_runs_missing_returns_404(self, client, mock_run_manager):
        """API should return 404 when all runs missing evaluation data."""

        # Mock runs exist
        def create_mock_run(run_id):
            mock_run = Mock()
            mock_run.run_id = run_id
            mock_run.timestamp = datetime(2024, 1, 15, 10, 30, 0)
            mock_run.status = "success"
            mock_run.to_dict.return_value = {"run_id": run_id, "status": "success"}
            return mock_run

        mock_run_manager.get_run.side_effect = lambda x: create_mock_run(x)

        # Mock no evaluation data available
        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {}  # All runs missing

            response = client.get("/api/runs/compare?ids=run1,run2")

            assert response.status_code == 404

    def test_compare_api_includes_available_models(self, client, mock_run_manager):
        """Ensemble runs should show available_models in response."""

        # Mock runs metadata for ensemble and single run
        def create_mock_run(run_id):
            mock_run = Mock()
            mock_run.run_id = run_id
            mock_run.timestamp = datetime(2024, 1, 15, 10, 30, 0)
            mock_run.status = "success"
            mock_run.to_dict.return_value = {"run_id": run_id, "status": "success"}
            return mock_run

        mock_run_manager.get_run.side_effect = lambda x: create_mock_run(x)

        # Mock ensemble evaluation data
        ensemble_eval = {
            "ranking": ["lgbm", "cat", "xgb"],
            "is_multi": True,
            "models": {
                "lgbm": {"metrics": {"auc": 0.85}},
                "cat": {"metrics": {"auc": 0.82}},
                "xgb": {"metrics": {"auc": 0.80}},
            },
        }

        # Mock single run evaluation data
        single_eval = {"metrics": {"auc": 0.80}, "is_multi": False}

        with patch("energizados.web.app._load_run_evaluations_batch") as mock_batch:
            mock_batch.return_value = {
                "ensemble1": ensemble_eval,
                "single1": single_eval,
            }

            response = client.get("/api/runs/compare?ids=ensemble1,single1")

            assert response.status_code == 200
            data = response.json()

            # Should include available_models for ensemble
            assert "ensemble1" in data["runs"]
            # The available_models should be derived from ranking
            assert data["runs"]["ensemble1"]["is_multi"] is True
            assert data["runs"]["ensemble1"]["available_models"] == ["lgbm", "cat", "xgb"]
