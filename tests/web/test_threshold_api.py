"""
Tests for Threshold API endpoint.

Phase 4 Task 16: Test Threshold API endpoint (RED).
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


@pytest.fixture
def mock_run_manager():
    """Mock RunManager for testing."""
    with patch("energizados.web.app.RunManager") as mock:
        manager_instance = Mock()
        mock.return_value = manager_instance
        yield manager_instance


class TestThresholdApi:
    """Test suite for threshold API endpoint."""

    def test_threshold_api_single_model_returns_data(self, client, mock_run_manager, tmp_path):
        """API should return full threshold data for single-model runs."""
        # Setup mock run
        mock_run = Mock()
        mock_run.run_id = "single-model-run"
        mock_run_manager.get_run.return_value = mock_run

        # Create evaluation report with threshold data
        eval_dir = tmp_path / "reports" / "evaluation"
        eval_dir.mkdir(parents=True)

        eval_report = eval_dir / "evaluation_report.json"
        import json

        eval_report.write_text(
            json.dumps(
                {
                    "threshold_metrics": {
                        "thresholds": [0.1, 0.5, 0.9],
                        "precisions": [0.8, 0.85, 0.9],
                        "recalls": [0.95, 0.8, 0.6],
                        "f1s": [0.87, 0.82, 0.72],
                    },
                    "metrics": {
                        "threshold": 0.5,
                        "cumulative_gains": {
                            "deciles": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                            "cumulative_gain": [
                                0.1,
                                0.25,
                                0.45,
                                0.6,
                                0.7,
                                0.8,
                                0.85,
                                0.9,
                                0.95,
                                1.0,
                            ],
                            "cumulative_population": [
                                0.1,
                                0.2,
                                0.3,
                                0.4,
                                0.5,
                                0.6,
                                0.7,
                                0.8,
                                0.9,
                                1.0,
                            ],
                        },
                    },
                }
            )
        )

        with patch("energizados.web.app._resolve_run_dir", return_value=tmp_path):
            response = client.get("/api/runs/single-model-run/thresholds")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "threshold_metrics" in data
        assert "cumulative_gains" in data
        assert "current_threshold" in data
        assert data["threshold_metrics"] is not None
        assert data["cumulative_gains"] is not None
        assert data["current_threshold"] == 0.5
        assert data["is_multi"] is False

    def test_threshold_api_ensemble_returns_null_metrics_with_message(
        self, client, mock_run_manager, tmp_path
    ):
        """API should return available_models with null threshold_metrics for ensemble runs."""
        # Setup mock run
        mock_run = Mock()
        mock_run.run_id = "ensemble-run"
        mock_run_manager.get_run.return_value = mock_run

        # Create comparison.json (ensemble marker)
        eval_dir = tmp_path / "reports" / "evaluation"
        eval_dir.mkdir(parents=True)

        comparison_file = eval_dir / "comparison.json"
        import json

        comparison_file.write_text(
            json.dumps(
                {
                    "ranking": [
                        {"name": "lgbm", "metrics": {"auc": 0.85}},
                        {"name": "catboost", "metrics": {"auc": 0.82}},
                    ],
                    "best_model": "lgbm",
                }
            )
        )

        with patch("energizados.web.app._resolve_run_dir", return_value=tmp_path):
            response = client.get("/api/runs/ensemble-run/thresholds")

        assert response.status_code == 200
        data = response.json()

        # Should return 200 with null threshold_metrics
        assert data["threshold_metrics"] is None
        assert data["cumulative_gains"] is None
        assert data["is_multi"] is True
        assert data["available_models"] == ["lgbm", "catboost"]

    def test_threshold_api_missing_threshold_metrics_returns_partial(
        self, client, mock_run_manager, tmp_path
    ):
        """API should return 200 with nulls for old runs lacking threshold_metrics."""
        # Setup mock run
        mock_run = Mock()
        mock_run.run_id = "old-run"
        mock_run_manager.get_run.return_value = mock_run

        # Create evaluation report WITHOUT threshold_metrics (old run)
        eval_dir = tmp_path / "reports" / "evaluation"
        eval_dir.mkdir(parents=True)

        eval_report = eval_dir / "evaluation_report.json"
        import json

        eval_report.write_text(json.dumps({"metrics": {"auc": 0.85, "f1": 0.78}}))

        with patch("energizados.web.app._resolve_run_dir", return_value=tmp_path):
            response = client.get("/api/runs/old-run/thresholds")

        # Should return 200 with null threshold_metrics (graceful degradation)
        assert response.status_code == 200
        data = response.json()

        assert data["threshold_metrics"] is None
        assert data["cumulative_gains"] is None
        assert data["is_multi"] is False

    def test_threshold_api_missing_run_returns_404(self, client, mock_run_manager):
        """API should return 404 for non-existent runs."""
        # Setup mock for non-existent run
        mock_run_manager.get_run.return_value = None

        response = client.get("/api/runs/non-existent-run/thresholds")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_threshold_api_response_structure(self, client, mock_run_manager, tmp_path):
        """API should return correct JSON structure with all required fields."""
        # Setup mock run
        mock_run = Mock()
        mock_run.run_id = "structure-test-run"
        mock_run_manager.get_run.return_value = mock_run

        # Create minimal evaluation report
        eval_dir = tmp_path / "reports" / "evaluation"
        eval_dir.mkdir(parents=True)

        eval_report = eval_dir / "evaluation_report.json"
        import json

        eval_report.write_text(
            json.dumps(
                {
                    "threshold_metrics": {
                        "thresholds": [0.5],
                        "precisions": [0.85],
                        "recalls": [0.8],
                        "f1s": [0.82],
                    },
                    "metrics": {
                        "threshold": 0.5,
                        "cumulative_gains": {
                            "deciles": [1],
                            "cumulative_gain": [0.5],
                            "cumulative_population": [0.5],
                        },
                    },
                }
            )
        )

        with patch("energizados.web.app._resolve_run_dir", return_value=tmp_path):
            response = client.get("/api/runs/structure-test-run/thresholds")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields present
        required_fields = [
            "threshold_metrics",
            "cumulative_gains",
            "current_threshold",
            "available_models",
            "is_multi",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
