"""
Tests for template helper functions (Phase 3, task 3.6).

Tests for _load_run_evaluation, _list_run_configs, _has_run_log, _read_run_log, _get_artifact_relative_path.
"""

import json
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def sample_run_metadata():
    """Create sample RunMetadata for testing."""
    from energizados.core.builders.run_manager import RunMetadata

    return RunMetadata.from_dict(
        {
            "run_id": "test-run-123",
            "timestamp": "2024-01-01T00:00:00Z",
            "duration_seconds": 60.0,
            "status": "success",
            "model_types": ["lightgbm"],
            "val_auc": 0.85,
            "val_f1": 0.78,
            "feature_count": 10,
            "energizados_version": "0.3.0",
            "python_version": "3.10",
            "git_commit": "abc123",
            "config_files": ["train.yaml"],
            "output_paths": {},
        }
    )


@pytest.fixture
def temp_run_dir(tmp_path):
    """Create temporary run directory structure for testing."""
    run_dir = tmp_path / "test-run-123"
    run_dir.mkdir(exist_ok=True)

    # Create reports directory
    reports_dir = run_dir / "reports" / "evaluation"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Create config directory
    config_dir = run_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Create sample config files
    (config_dir / "train.yaml").write_text("train: config")
    (config_dir / "etl.yaml").write_text("etl: config")

    return run_dir


class TestLoadRunEvaluation:
    """Tests for _load_run_evaluation helper."""

    def test_load_evaluation_single_model(self, temp_run_dir):
        """Test _load_run_evaluation with single-model structure."""
        from energizados.web.app import _load_run_evaluation

        # Create single-model evaluation report
        single_model_data = {
            "metrics": {"auc": 0.85, "f1": 0.78, "precision": 0.81, "recall": 0.75},
            "model_info": {"model_class": "LGBMModelAdapter", "hyperparams": {"num_leaves": 31}},
        }

        report_path = temp_run_dir / "reports" / "evaluation" / "evaluation_report.json"
        report_path.write_text(json.dumps(single_model_data))

        with patch("energizados.web.app.RunManager") as mock_rm_class:
            mock_rm_instance = Mock()
            mock_rm_class.return_value = mock_rm_instance

            from energizados.core.builders.run_manager import RunMetadata

            mock_metadata = RunMetadata.from_dict(
                {
                    "run_id": "test-run-123",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "duration_seconds": 60.0,
                    "status": "success",
                    "model_types": ["lightgbm"],
                    "val_auc": 0.85,
                    "val_f1": 0.78,
                    "feature_count": 10,
                    "energizados_version": "0.3.0",
                    "python_version": "3.10",
                    "git_commit": "abc123",
                    "config_files": ["train.yaml"],
                    "output_paths": {},
                }
            )

            mock_rm_instance.get_run.return_value = mock_metadata
            mock_rm_instance.run_dir.return_value = temp_run_dir

            result = _load_run_evaluation("test-run-123")

            assert result is not None
            assert result["is_multi"] is False
            assert "metrics" in result
            assert result["metrics"]["auc"] == 0.85
            assert "model_info" in result


class TestListRunConfigs:
    """Tests for _list_run_configs helper."""

    def test_list_run_configs(self, temp_run_dir, sample_run_metadata):
        """Test _list_run_configs returns config filenames."""
        from energizados.web.app import _list_run_configs

        with patch("energizados.web.app.RunManager") as mock_rm_class:
            mock_rm_instance = Mock()
            mock_rm_class.return_value = mock_rm_instance
            mock_rm_instance.run_dir.return_value = temp_run_dir

            configs = _list_run_configs(sample_run_metadata)

            assert len(configs) == 2
            assert "train.yaml" in configs
            assert "etl.yaml" in configs
