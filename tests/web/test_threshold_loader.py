"""
Tests for Threshold Data Loader helper.

Phase 4 Task 14: Test threshold data loader (RED).
Following strict TDD: RED test first, then GREEN implementation.
"""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_run_manager():
    """Mock RunManager for testing."""
    with patch("energizados.web.app.RunManager") as mock:
        manager_instance = Mock()
        mock.return_value = manager_instance
        yield manager_instance


class TestThresholdDataLoader:
    """Test suite for _load_threshold_data helper function."""

    def test_threshold_load_single_model_full_data(self, mock_run_manager, tmp_path):
        """Should return threshold_metrics and cumulative_gains for single-model runs."""
        # Setup mock run directory
        mock_run = Mock()
        mock_run.run_id = "test-run-123"
        mock_run_manager.get_run.return_value = mock_run
        mock_run_manager.run_dir.return_value = tmp_path

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

        # Import and test the function
        from energizados.web.app import _load_threshold_data

        result = _load_threshold_data("test-run-123")

        assert result is not None
        assert result["threshold_metrics"] is not None
        assert result["cumulative_gains"] is not None
        assert result["current_threshold"] == 0.5
        assert result["is_multi"] is False
        assert result["available_models"] is None
        assert len(result["threshold_metrics"]["thresholds"]) == 3

    def test_threshold_load_ensemble_returns_null_metrics(self, mock_run_manager, tmp_path):
        """Ensemble runs should return null threshold_metrics with available_models."""
        # Setup mock run directory
        mock_run = Mock()
        mock_run.run_id = "ensemble-run-456"
        mock_run_manager.get_run.return_value = mock_run
        mock_run_manager.run_dir.return_value = tmp_path

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

        # Import and test the function
        from energizados.web.app import _load_threshold_data

        result = _load_threshold_data("ensemble-run-456")

        assert result is not None
        assert result["threshold_metrics"] is None  # No threshold data for ensembles
        assert result["cumulative_gains"] is None
        assert result["current_threshold"] is None
        assert result["is_multi"] is True
        assert result["available_models"] == ["lgbm", "catboost"]

    def test_threshold_load_missing_threshold_metrics(self, mock_run_manager, tmp_path):
        """Old runs without threshold_metrics should handle gracefully with nulls."""
        # Setup mock run directory
        mock_run = Mock()
        mock_run.run_id = "old-run-789"
        mock_run_manager.get_run.return_value = mock_run
        mock_run_manager.run_dir.return_value = tmp_path

        # Create evaluation report WITHOUT threshold_metrics (old run)
        eval_dir = tmp_path / "reports" / "evaluation"
        eval_dir.mkdir(parents=True)

        eval_report = eval_dir / "evaluation_report.json"
        import json

        eval_report.write_text(
            json.dumps(
                {
                    "metrics": {
                        "auc": 0.85,
                        "f1": 0.78,
                        # No threshold_metrics, no cumulative_gains
                    }
                }
            )
        )

        # Import and test the function
        from energizados.web.app import _load_threshold_data

        result = _load_threshold_data("old-run-789")

        assert result is not None
        # Should return nulls for missing data (graceful degradation)
        assert result["threshold_metrics"] is None
        assert result["cumulative_gains"] is None
        assert result["is_multi"] is False
        assert result["available_models"] is None

    def test_threshold_load_missing_cumulative_gains(self, mock_run_manager, tmp_path):
        """Runs with threshold_metrics but missing cumulative_gains should handle gracefully."""
        # Setup mock run directory
        mock_run = Mock()
        mock_run.run_id = "partial-run-999"
        mock_run_manager.get_run.return_value = mock_run
        mock_run_manager.run_dir.return_value = tmp_path

        # Create evaluation report with threshold_metrics but NO cumulative_gains
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
                        "threshold": 0.5
                        # No cumulative_gains
                    },
                }
            )
        )

        # Import and test the function
        from energizados.web.app import _load_threshold_data

        result = _load_threshold_data("partial-run-999")

        assert result is not None
        # Should have threshold_metrics but null cumulative_gains
        assert result["threshold_metrics"] is not None
        assert result["cumulative_gains"] is None
        assert result["current_threshold"] == 0.5

    def test_threshold_load_missing_run_returns_none(self, mock_run_manager):
        """Non-existent run should return None."""
        # Setup mock for non-existent run
        mock_run_manager.get_run.return_value = None
        mock_run_manager.run_dir.return_value = None

        # Import and test the function
        from energizados.web.app import _load_threshold_data

        result = _load_threshold_data("non-existent-run")

        assert result is None
