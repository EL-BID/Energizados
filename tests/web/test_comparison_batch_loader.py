"""
Tests for Comparison View batch evaluation loader.

Phase 4 Task 8-9: Batch evaluation loader helper.
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


class TestBatchEvaluationLoader:
    """Test suite for batch evaluation loading helper."""

    def test_batch_load_multiple_runs(self, client, tmp_path):
        """Should load evaluation data for all runs successfully."""
        from energizados.web.app import _load_run_evaluations_batch

        # Mock the evaluation data for each run
        mock_eval_1 = {"metrics": {"auc": 0.85, "f1": 0.78}, "is_multi": False}
        mock_eval_2 = {"metrics": {"auc": 0.82, "f1": 0.75}, "is_multi": False}

        with patch("energizados.web.app._load_run_evaluation") as mock_load:
            # Setup mock to return different data for each run_id
            def side_effect(run_id):
                if run_id == "run1":
                    return mock_eval_1
                elif run_id == "run2":
                    return mock_eval_2
                return None

            mock_load.side_effect = side_effect

            result = _load_run_evaluations_batch(["run1", "run2"])

            assert result == {"run1": mock_eval_1, "run2": mock_eval_2}
            assert mock_load.call_count == 2

    def test_batch_load_skips_missing_eval_json(self, client, tmp_path):
        """Should skip runs without evaluation data gracefully."""
        from energizados.web.app import _load_run_evaluations_batch

        mock_eval_1 = {"metrics": {"auc": 0.85}, "is_multi": False}
        # run2 has None (missing eval file)
        mock_eval_3 = {"metrics": {"auc": 0.80}, "is_multi": False}

        with patch("energizados.web.app._load_run_evaluation") as mock_load:

            def side_effect(run_id):
                if run_id == "run1":
                    return mock_eval_1
                elif run_id == "run2":
                    return None  # Missing eval file
                elif run_id == "run3":
                    return mock_eval_3
                return None

            mock_load.side_effect = side_effect

            result = _load_run_evaluations_batch(["run1", "run2", "run3"])

            # Should only include runs with valid data
            assert result == {"run1": mock_eval_1, "run3": mock_eval_3}
            assert "run2" not in result

    def test_batch_load_handles_single_model(self, client, tmp_path):
        """Should normalize single-model structure correctly."""
        from energizados.web.app import _load_run_evaluations_batch

        mock_single = {
            "metrics": {"auc": 0.85, "f1": 0.78, "precision": 0.80, "recall": 0.75},
            "is_multi": False,
        }

        with patch("energizados.web.app._load_run_evaluation") as mock_load:
            mock_load.return_value = mock_single

            result = _load_run_evaluations_batch(["single-run"])

            assert result == {"single-run": mock_single}
            assert result["single-run"]["is_multi"] is False

    def test_batch_load_handles_multi_model(self, client, tmp_path):
        """Should normalize multi-model structure correctly."""
        from energizados.web.app import _load_run_evaluations_batch

        mock_ensemble = {
            "ranking": ["lgbm", "cat"],
            "models": {
                "lgbm": {"metrics": {"auc": 0.85}},
                "cat": {"metrics": {"auc": 0.82}},
            },
            "is_multi": True,
        }

        with patch("energizados.web.app._load_run_evaluation") as mock_load:
            mock_load.return_value = mock_ensemble

            result = _load_run_evaluations_batch(["ensemble-run"])

            assert result == {"ensemble-run": mock_ensemble}
            assert result["ensemble-run"]["is_multi"] is True
            assert "ranking" in result["ensemble-run"]

    def test_batch_load_empty_list(self, client, tmp_path):
        """Should return empty dict for empty run list."""
        from energizados.web.app import _load_run_evaluations_batch

        with patch("energizados.web.app._load_run_evaluation") as mock_load:
            result = _load_run_evaluations_batch([])

            assert result == {}
            mock_load.assert_not_called()
