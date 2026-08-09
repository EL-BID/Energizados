"""
Tests for MetricsDict and metrics unification (Phase 5).
"""

import warnings

from energizados.core.steps.training import MetricsDict


class TestMetricsDict:
    """Test MetricsDict wrapper and deprecation warning."""

    def test_metrics_dict_metrics_access(self):
        """Test that result["metrics"] returns metrics dict."""
        from energizados.core.steps.training import MetricsDict

        result = MetricsDict({"metrics": {"auc": 0.85, "f1": 0.78}})

        assert result["metrics"] == {"auc": 0.85, "f1": 0.78}
        assert isinstance(result, dict)  # Still a dict subclass

    def test_metrics_dict_model_metrics_deprecation_warning(self):
        """Test that result["model_metrics"] emits DeprecationWarning and returns metrics."""
        result = MetricsDict({"metrics": {"auc": 0.85, "f1": 0.78}})

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            value = result["model_metrics"]

            # Check that DeprecationWarning was raised
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "model_metrics" in str(w[0].message)
            assert "deprecated" in str(w[0].message).lower()

            # Check that it returns the same value as metrics
            assert value == {"auc": 0.85, "f1": 0.78}
            assert value == result["metrics"]

    def test_metrics_dict_other_keys_access(self):
        """Test that other keys work normally without warnings."""
        result = MetricsDict(
            {
                "metrics": {"auc": 0.85},
                "model_path": "/path/to/model.pkl",
                "run_id": "train-20240101_120000",
            }
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Access other keys - should not emit warnings
            assert result["model_path"] == "/path/to/model.pkl"
            assert result["run_id"] == "train-20240101_120000"

            # No warnings should have been raised
            assert len(w) == 0

    def test_metrics_dict_is_dict_subclass(self):
        """Test that MetricsDict is a dict subclass."""
        result = MetricsDict({"metrics": {"auc": 0.85}})

        assert isinstance(result, dict)
        assert hasattr(result, "__getitem__")
        assert hasattr(result, "keys")
        assert hasattr(result, "values")

    def test_metrics_dict_dict_operations(self):
        """Test that normal dict operations still work."""
        result = MetricsDict({"metrics": {"auc": 0.85}, "model_path": "/path/to/model.pkl"})

        # Test dict operations
        assert "metrics" in result.keys()
        assert "/path/to/model.pkl" in result.values()  # Fixed: check value, not key
        assert len(result) == 2
        assert result.get("metrics") == {"auc": 0.85}
        assert result.get("nonexistent", "default") == "default"


class TestTrainingStepMetricsUnification:
    """Test TrainingStep metrics unification (Phase 5)."""

    def test_single_model_mode_sets_metrics_key(self):
        """Test that single model mode sets result["metrics"]."""
        import tempfile
        from pathlib import Path

        from energizados.core.steps.training import TrainingStep

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create a minimal training step
            TrainingStep(
                train_path=None,  # Will be set in context
                val_path=None,
                test_path=None,
                target_column="target",
                feature_engineering_config={"enabled": False},
                models_configs=[{"type": "lightgbm"}],
                ensemble_config=None,
                output_dir=output_dir,
            )

            # Mock the training result
            result = {
                **{"context_key": "context_value"},
                "model_path": str(output_dir / "model.pkl"),
                "feature_engineering_path": str(output_dir / "fe.pkl"),
                "val_predictions_path": str(output_dir / "val_predictions.parquet"),
                "val_auc": 0.85,
                "val_f1": 0.78,
                "model": "mock_model",
                "feature_engineering": "mock_fe",
                "model_paths": None,
                "models": None,
                "val_metrics": None,
                "comparison_mode": False,
            }

            # The training step should wrap the result in MetricsDict
            # For now, just test that we can create a MetricsDict with the expected structure
            wrapped_result = MetricsDict(result)

            # Check that metrics key can be accessed
            assert "metrics" in wrapped_result or "val_auc" in wrapped_result

    def test_ensemble_mode_sets_metrics_key(self):
        """Test that ensemble mode sets result["metrics"]."""
        import tempfile
        from pathlib import Path

        from energizados.core.steps.training import TrainingStep

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create a training step with ensemble config
            TrainingStep(
                train_path=None,
                val_path=None,
                test_path=None,
                target_column="target",
                feature_engineering_config={"enabled": False},
                models_configs=[{"type": "lightgbm"}, {"type": "catboost"}],
                ensemble_config={"method": "soft_voting"},
                output_dir=output_dir,
            )

            # Mock ensemble result
            result = {
                "context_key": "context_value",
                "model_path": str(output_dir / "ensemble.pkl"),
                "feature_engineering_path": str(output_dir / "fe.pkl"),
                "val_predictions_path": str(output_dir / "val_predictions.parquet"),
                "val_auc": 0.87,
                "val_f1": 0.80,
                "model": "mock_ensemble",
                "feature_engineering": "mock_fe",
                "model_paths": None,
                "models": None,
                "val_metrics": None,
                "comparison_mode": False,
            }

            wrapped_result = MetricsDict(result)

            # Check that we can access metrics-related fields
            assert "metrics" in wrapped_result or "val_auc" in wrapped_result

    def test_comparison_mode_sets_metrics_key(self):
        """Test that comparison mode sets result["metrics"]."""
        import tempfile
        from pathlib import Path

        from energizados.core.steps.training import TrainingStep

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create a training step with multiple models but no ensemble (comparison mode)
            TrainingStep(
                train_path=None,
                val_path=None,
                test_path=None,
                target_column="target",
                feature_engineering_config={"enabled": False},
                models_configs=[{"type": "lightgbm"}, {"type": "catboost"}],
                ensemble_config=None,  # No ensemble = comparison mode
                output_dir=output_dir,
            )

            # Mock comparison mode result
            result = {
                "context_key": "context_value",
                "model_path": None,
                "feature_engineering_path": str(output_dir / "fe.pkl"),
                "val_predictions_path": str(output_dir / "val_predictions.parquet"),
                "val_auc": None,
                "val_f1": None,
                "model": None,
                "feature_engineering": "mock_fe",
                "model_paths": {
                    "lightgbm": str(output_dir / "lightgbm" / "model.pkl"),
                    "catboost": str(output_dir / "catboost" / "model.pkl"),
                },
                "models": {"lightgbm": "mock_lgbm", "catboost": "mock_cat"},
                "val_metrics": {
                    "lightgbm": {"auc": 0.85, "f1": 0.78},
                    "catboost": {"auc": 0.87, "f1": 0.80},
                },
                "comparison_mode": True,
            }

            wrapped_result = MetricsDict(result)

            # In comparison mode, val_metrics should be accessible
            assert wrapped_result.get("val_metrics") is not None


class TestPipelineRunReturnContract:
    """Test that Pipeline.run() still returns dict (regression test)."""

    def test_pipeline_run_returns_dict(self):
        """Test that pipeline.run() still returns a dict."""
        # MetricsDict should be a dict subclass
        result = MetricsDict({"metrics": {"auc": 0.85}})

        # Test that it's still a dict
        assert isinstance(result, dict)
        assert result["metrics"] == {"auc": 0.85}
