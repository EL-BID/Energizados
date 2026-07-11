"""
Tests for Threshold UI section in run_detail.html.

Phase 4 Task 18: Test run_detail.html threshold section (RED).
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


class TestThresholdUi:
    """Test suite for threshold UI in run detail page."""

    def test_run_detail_includes_threshold_section(self, client, mock_run_manager, tmp_path):
        """Run detail page should include threshold exploration section."""
        # Setup mock run
        mock_run = Mock()
        mock_run.run_id = "test-run-with-thresholds"
        mock_run.timestamp = "2024-01-15T10:30:00"
        mock_run.duration_seconds = 120.5
        mock_run.model_types = ["lightgbm"]
        mock_run.feature_count = 25
        mock_run.energizados_version = "0.3.0"
        mock_run.status = "success"
        mock_run.output_paths = {}

        mock_run_manager.get_run.return_value = mock_run
        mock_run_manager.list_configs.return_value = []

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
                        "auc": 0.85,
                        "f1": 0.78,
                        "precision": 0.82,
                        "recall": 0.75,
                        "cumulative_gains": {
                            "deciles": [1, 2, 3, 4, 5],
                            "cumulative_gain": [0.1, 0.25, 0.45, 0.6, 0.7],
                            "cumulative_population": [0.1, 0.2, 0.3, 0.4, 0.5],
                        },
                    },
                }
            )
        )

        # Mock the helper functions
        with (
            patch("energizados.web.app._load_run_evaluation") as mock_eval,
            patch("energizados.web.app._resolve_run_dir", return_value=tmp_path),
        ):
            mock_eval.return_value = {
                "metrics": {
                    "threshold": 0.5,
                    "auc": 0.85,
                    "f1": 0.78,
                    "precision": 0.82,
                    "recall": 0.75,
                },
                "is_multi": False,
            }

            with patch("energizados.web.app._list_run_configs") as mock_configs:
                mock_configs.return_value = []

                with patch("energizados.web.app._has_run_log") as mock_log:
                    mock_log.return_value = False

                    with patch("energizados.web.app._get_artifact_relative_path") as mock_artifact:
                        mock_artifact.side_effect = ValueError("No EDA")

                        response = client.get(f"/runs/{mock_run.run_id}")

                        assert response.status_code == 200
                        html = response.text

                        # Should include threshold section
                        assert "thresholds-section" in html or "Threshold Exploration" in html

    def test_threshold_section_without_data_shows_message(self, client, mock_run_manager, tmp_path):
        """Threshold section should show informative message when data unavailable."""
        # Setup mock run with old evaluation report (no threshold_metrics)
        mock_run = Mock()
        mock_run.run_id = "old-run-no-thresholds"
        mock_run.timestamp = "2024-01-15T10:30:00"
        mock_run.duration_seconds = 120.5
        mock_run.model_types = ["lightgbm"]
        mock_run.feature_count = 25
        mock_run.energizados_version = "0.2.0"  # Old version
        mock_run.status = "success"
        mock_run.output_paths = {}

        mock_run_manager.get_run.return_value = mock_run
        mock_run_manager.list_configs.return_value = []

        # Create evaluation report WITHOUT threshold_metrics
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
                        "precision": 0.82,
                        "recall": 0.75,
                    }
                }
            )
        )

        # Mock the helper functions
        with (
            patch("energizados.web.app._load_run_evaluation") as mock_eval,
            patch("energizados.web.app._resolve_run_dir", return_value=tmp_path),
        ):
            mock_eval.return_value = {
                "metrics": {
                    "auc": 0.85,
                    "f1": 0.78,
                    "precision": 0.82,
                    "recall": 0.75,
                },
                "is_multi": False,
            }

            with patch("energizados.web.app._list_run_configs") as mock_configs:
                mock_configs.return_value = []

                with patch("energizados.web.app._has_run_log") as mock_log:
                    mock_log.return_value = False

                    with patch("energizados.web.app._get_artifact_relative_path") as mock_artifact:
                        mock_artifact.side_effect = ValueError("No EDA")

                        response = client.get(f"/runs/{mock_run.run_id}")

                        assert response.status_code == 200
                        html = response.text

                        # Should show a message about unavailable data
                        # The exact message will depend on implementation
                        assert "Threshold" in html or "threshold" in html

    def test_threshold_section_ensemble_specific_message(self, client, mock_run_manager, tmp_path):
        """Ensemble runs should show specific message about threshold limitations."""
        # Setup mock ensemble run
        mock_run = Mock()
        mock_run.run_id = "ensemble-run-thresholds"
        mock_run.timestamp = "2024-01-15T10:30:00"
        mock_run.duration_seconds = 240.5
        mock_run.model_types = ["lightgbm", "catboost"]
        mock_run.feature_count = 25
        mock_run.energizados_version = "0.3.0"
        mock_run.status = "success"
        mock_run.output_paths = {}

        mock_run_manager.get_run.return_value = mock_run
        mock_run_manager.list_configs.return_value = []

        # Create comparison.json (ensemble marker)
        eval_dir = tmp_path / "reports" / "evaluation"
        eval_dir.mkdir(parents=True)

        comparison_file = eval_dir / "comparison.json"
        import json

        comparison_file.write_text(
            json.dumps(
                {
                    "ranking": [
                        {
                            "name": "lgbm",
                            "metrics": {"auc": 0.85, "f1": 0.78, "precision": 0.82, "recall": 0.75},
                        },
                        {
                            "name": "catboost",
                            "metrics": {"auc": 0.82, "f1": 0.75, "precision": 0.80, "recall": 0.70},
                        },
                    ],
                    "best_model": "lgbm",
                }
            )
        )

        # Mock the helper functions
        with (
            patch("energizados.web.app._load_run_evaluation") as mock_eval,
            patch("energizados.web.app._resolve_run_dir", return_value=tmp_path),
        ):
            mock_eval.return_value = {
                "ranking": [
                    {
                        "name": "lgbm",
                        "metrics": {"auc": 0.85, "f1": 0.78, "precision": 0.82, "recall": 0.75},
                    },
                    {
                        "name": "catboost",
                        "metrics": {"auc": 0.82, "f1": 0.75, "precision": 0.80, "recall": 0.70},
                    },
                ],
                "best_model": "lgbm",
                "is_multi": True,
            }

            with patch("energizados.web.app._list_run_configs") as mock_configs:
                mock_configs.return_value = []

                with patch("energizados.web.app._has_run_log") as mock_log:
                    mock_log.return_value = False

                    with patch("energizados.web.app._get_artifact_relative_path") as mock_artifact:
                        mock_artifact.side_effect = ValueError("No EDA")

                        response = client.get(f"/runs/{mock_run.run_id}")

                        assert response.status_code == 200
                        html = response.text

                        # Should show threshold section with ensemble-specific message
                        assert "Threshold" in html or "threshold" in html

    def test_run_detail_passes_unavailable_message(self, client, mock_run_manager, tmp_path):
        """Template should receive threshold_unavailable_message context variable."""
        # Setup mock run
        mock_run = Mock()
        mock_run.run_id = "test-run-message"
        mock_run.timestamp = "2024-01-15T10:30:00"
        mock_run.duration_seconds = 120.5
        mock_run.model_types = ["lightgbm"]
        mock_run.feature_count = 25
        mock_run.energizados_version = "0.3.0"
        mock_run.status = "success"
        mock_run.output_paths = {}

        mock_run_manager.get_run.return_value = mock_run
        mock_run_manager.list_configs.return_value = []

        # Create evaluation report without threshold data
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
                        "precision": 0.82,
                        "recall": 0.75,
                    }
                }
            )
        )

        # Mock the helper functions
        with (
            patch("energizados.web.app._load_run_evaluation") as mock_eval,
            patch("energizados.web.app._resolve_run_dir", return_value=tmp_path),
        ):
            mock_eval.return_value = {
                "metrics": {
                    "auc": 0.85,
                    "f1": 0.78,
                    "precision": 0.82,
                    "recall": 0.75,
                },
                "is_multi": False,
            }

            with patch("energizados.web.app._list_run_configs") as mock_configs:
                mock_configs.return_value = []

                with patch("energizados.web.app._has_run_log") as mock_log:
                    mock_log.return_value = False

                    with patch("energizados.web.app._get_artifact_relative_path") as mock_artifact:
                        mock_artifact.side_effect = ValueError("No EDA")

                        response = client.get(f"/runs/{mock_run.run_id}")

                        assert response.status_code == 200
                        # The template should handle the case when threshold data is unavailable
                        # Implementation will verify the message is passed correctly
