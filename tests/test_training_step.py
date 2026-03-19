"""
Unit tests for the refactored TrainingStep.

Tests cover: models_configs list, name resolution, single-model path,
ensemble path (soft voting + stacking), and pipeline config parsing.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from energizados.core.base import BaseModel
from energizados.core.steps.training import TrainingStep

# ---------------------------------------------------------------------------
# Module-level dummy model (must be at module level to be picklable)
# ---------------------------------------------------------------------------


class _DummyModel(BaseModel):
    """Minimal BaseModel that always returns a fixed probability. Picklable."""

    def __init__(
        self,
        proba: float = 0.6,
        cols_for_model=None,
        hyperparams=None,
        sampling_method="undersample",
        sampling_th=0.5,
        search_hip=False,
        n_iter=60,
        cv=3,
        config=None,
    ):
        super().__init__(config)
        self.proba = proba
        self.cols_for_model = cols_for_model or []

    def fit(self, X, y, X_val=None, y_val=None):
        self.is_fitted_ = True
        return self

    def predict(self, X):
        self.check_fitted()
        return np.ones(len(X), dtype=int)

    def predict_proba(self, X):
        self.check_fitted()
        return np.full(len(X), self.proba)


def _dummy_model_class(proba: float = 0.6):
    """Return _DummyModel (module-level, picklable). proba ignored — uses default 0.6."""
    return _DummyModel


@pytest.fixture
def temp_dir():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d)


@pytest.fixture
def parquet_splits(temp_dir):
    """Write tiny train/val parquet files and return their paths."""
    rng = np.random.default_rng(0)
    n = 40

    def _df():
        return pd.DataFrame(
            {
                "f1": rng.standard_normal(n),
                "f2": rng.standard_normal(n),
                "target": (rng.standard_normal(n) > 0).astype(int),
            }
        )

    train_path = temp_dir / "train.parquet"
    val_path = temp_dir / "val.parquet"
    _df().to_parquet(train_path)
    _df().to_parquet(val_path)
    return str(train_path), str(val_path)


# ---------------------------------------------------------------------------
# Name resolution
# ---------------------------------------------------------------------------


class TestResolveModelNames:
    def _step(self):
        return TrainingStep(models_configs=[], output_dir="/tmp/x")  # nosec B108

    def test_explicit_names_used(self):
        step = self._step()
        cfgs = [{"name": "lgbm", "type": "lightgbm"}, {"name": "cat", "type": "catboost"}]
        assert step._resolve_model_names(cfgs) == ["lgbm", "cat"]

    def test_unique_types_use_type_string(self):
        step = self._step()
        cfgs = [{"type": "lightgbm"}, {"type": "catboost"}]
        assert step._resolve_model_names(cfgs) == ["lightgbm", "catboost"]

    def test_duplicate_types_get_suffix(self):
        step = self._step()
        cfgs = [{"type": "lightgbm"}, {"type": "lightgbm"}]
        names = step._resolve_model_names(cfgs)
        assert names == ["lightgbm_0", "lightgbm_1"]

    def test_three_duplicates(self):
        step = self._step()
        cfgs = [{"type": "lightgbm"}] * 3
        assert step._resolve_model_names(cfgs) == ["lightgbm_0", "lightgbm_1", "lightgbm_2"]

    def test_mixed_explicit_and_auto(self):
        step = self._step()
        cfgs = [
            {"name": "my_lgbm", "type": "lightgbm"},
            {"type": "catboost"},
            {"type": "catboost"},
        ]
        names = step._resolve_model_names(cfgs)
        assert names[0] == "my_lgbm"
        assert names[1] == "catboost_0"
        assert names[2] == "catboost_1"

    def test_single_model_uses_type(self):
        step = self._step()
        assert step._resolve_model_names([{"type": "catboost"}]) == ["catboost"]


# ---------------------------------------------------------------------------
# Param preparation
# ---------------------------------------------------------------------------


class TestPrepareModelParams:
    def _step(self):
        return TrainingStep(models_configs=[], output_dir="/tmp/x")  # nosec B108

    def _X(self, cols=None):
        return pd.DataFrame({c: [1, 2] for c in (cols or ["f1", "f2"])})

    def test_lgbm_cols_for_model(self):
        step = self._step()
        X = self._X(["a", "b", "c"])
        params = step._prepare_model_params({"type": "lightgbm", "hyperparams": {}}, X)
        assert params["cols_for_model"] == ["a", "b", "c"]

    def test_sampling_config_extracted(self):
        step = self._step()
        cfg = {"type": "lightgbm", "sampling": {"method": "over", "threshold": 0.3}}
        params = step._prepare_model_params(cfg, self._X())
        assert params["sampling_method"] == "over"
        assert params["sampling_th"] == 0.3
        assert "sampling" not in params

    def test_hyperparam_search_extracted(self):
        step = self._step()
        cfg = {"type": "catboost", "hyperparam_search": {"enabled": True, "n_iter": 30, "cv": 5}}
        params = step._prepare_model_params(cfg, self._X())
        assert params["search_hip"] is True
        assert params["n_iter"] == 30
        assert params["cv"] == 5
        assert "hyperparam_search" not in params

    def test_type_stored_in_config(self):
        step = self._step()
        params = step._prepare_model_params({"type": "lightgbm"}, self._X())
        assert params["config"] == {"type": "lightgbm"}

    def test_type_and_name_removed(self):
        step = self._step()
        params = step._prepare_model_params({"type": "catboost", "name": "cat"}, self._X())
        assert "type" not in params
        assert "name" not in params

    def test_neural_cols_split(self):
        step = self._step()
        cols = ["actividad", "zona", "12_anterior", "6_anterior"]
        X = self._X(cols)
        params = step._prepare_model_params({"type": "neural_network"}, X)
        assert "12_anterior" in params["spents_names"]
        assert "actividad" in params["features_names"]
        assert "12_anterior" not in params["features_names"]


# ---------------------------------------------------------------------------
# Single-model execute
# ---------------------------------------------------------------------------


class TestTrainingStepSingleModel:
    @pytest.fixture
    def step_with_mock(self, parquet_splits, temp_dir):
        """TrainingStep with ModelRegistry patched to return a dummy model.

        DefaultFeatureEngineering is NOT mocked so the real object is pickled.
        We disable all FE processing via feature_engineering_config.
        """
        train_path, val_path = parquet_splits
        DummyCls = _dummy_model_class(0.6)

        with patch("energizados.core.steps.training.ModelRegistry") as mock_reg:
            mock_reg.get.return_value = DummyCls

            step = TrainingStep(
                train_path=train_path,
                val_path=val_path,
                models_configs=[{"type": "lightgbm", "hyperparams": {}}],
                feature_engineering_config={"enabled": False},
                output_dir=str(temp_dir / "models"),
            )
            yield step, temp_dir

    def test_model_pkl_saved(self, step_with_mock):
        step, temp_dir = step_with_mock
        result = step.execute({})
        assert Path(result["model_path"]).exists()
        assert Path(result["model_path"]).name == "model.pkl"

    def test_context_keys_present(self, step_with_mock):
        step, temp_dir = step_with_mock
        result = step.execute({})
        for key in [
            "model",
            "model_path",
            "feature_engineering_path",
            "val_predictions_path",
            "val_auc",
            "val_f1",
        ]:
            assert key in result

    def test_val_auc_is_float(self, step_with_mock):
        step, temp_dir = step_with_mock
        result = step.execute({})
        assert isinstance(result["val_auc"], float)
        assert 0.0 <= result["val_auc"] <= 1.0

    def test_model_is_base_model_instance(self, step_with_mock):
        step, temp_dir = step_with_mock
        result = step.execute({})
        assert isinstance(result["model"], BaseModel)


# ---------------------------------------------------------------------------
# Ensemble execute
# ---------------------------------------------------------------------------


class TestTrainingStepEnsemble:
    @pytest.fixture
    def ensemble_step(self, parquet_splits, temp_dir):
        """TrainingStep configured for a 2-model soft voting ensemble."""
        train_path, val_path = parquet_splits
        DummyCls = _dummy_model_class(0.6)

        with patch("energizados.core.steps.training.ModelRegistry") as mock_reg:
            mock_reg.get.return_value = DummyCls

            step = TrainingStep(
                train_path=train_path,
                val_path=val_path,
                models_configs=[
                    {"name": "lgbm", "type": "lightgbm", "hyperparams": {}},
                    {"name": "cat", "type": "catboost", "hyperparams": {}},
                ],
                ensemble_config={"method": "soft_voting"},
                feature_engineering_config={"enabled": False},
                output_dir=str(temp_dir / "models"),
            )
            yield step, temp_dir

    def test_ensemble_pkl_saved(self, ensemble_step):
        step, temp_dir = ensemble_step
        result = step.execute({})
        ensemble_path = temp_dir / "models" / "ensemble.pkl"
        assert ensemble_path.exists()
        assert result["model_path"] == str(ensemble_path)

    def test_base_model_pkls_saved(self, ensemble_step):
        step, temp_dir = ensemble_step
        step.execute({})
        assert (temp_dir / "models" / "lgbm" / "model.pkl").exists()
        assert (temp_dir / "models" / "cat" / "model.pkl").exists()

    def test_model_is_ensemble(self, ensemble_step):
        from energizados.modeling.ensemble import EnsembleModel

        step, _ = ensemble_step
        result = step.execute({})
        assert isinstance(result["model"], EnsembleModel)

    def test_ensemble_description(self, ensemble_step):
        from energizados.modeling.ensemble import EnsembleModel

        step, _ = ensemble_step
        result = step.execute({})
        model = result["model"]
        assert isinstance(model, EnsembleModel)
        assert "lightgbm" in model.ensemble_description
        assert "catboost" in model.ensemble_description

    def test_ensemble_requires_ensemble_config(self, parquet_splits, temp_dir):
        """Multiple models without ensemble_config now enters comparison mode (no error)."""
        train_path, val_path = parquet_splits
        DummyCls = _dummy_model_class(0.6)

        with patch("energizados.core.steps.training.ModelRegistry") as mock_reg:
            mock_reg.get.return_value = DummyCls

            step = TrainingStep(
                train_path=train_path,
                val_path=val_path,
                models_configs=[
                    {"type": "lightgbm", "hyperparams": {}},
                    {"type": "catboost", "hyperparams": {}},
                ],
                ensemble_config=None,  # missing → comparison mode
                feature_engineering_config={"enabled": False},
                output_dir=str(temp_dir / "models"),
            )
            result = step.execute({})
            # Should NOT raise ValueError anymore - comparison mode is valid
            assert result["comparison_mode"] is True
            assert result["model_paths"] is not None
            assert result["model_path"] is None

    def test_stacking_ensemble_fits_meta_learner(self, parquet_splits, temp_dir):
        """Stacking ensemble saves ensemble.pkl with a meta_learner."""
        train_path, val_path = parquet_splits
        DummyCls = _dummy_model_class(0.55)

        with patch("energizados.core.steps.training.ModelRegistry") as mock_reg:
            mock_reg.get.return_value = DummyCls

            step = TrainingStep(
                train_path=train_path,
                val_path=val_path,
                models_configs=[
                    {"name": "m1", "type": "lightgbm", "hyperparams": {}},
                    {"name": "m2", "type": "catboost", "hyperparams": {}},
                ],
                ensemble_config={
                    "method": "stacking",
                    "use_val_as_oof": True,
                    "meta_learner": {"type": "logistic_regression", "params": {"max_iter": 100}},
                },
                feature_engineering_config={"enabled": False},
                output_dir=str(temp_dir / "models"),
            )
            result = step.execute({})

        from energizados.modeling.ensemble import EnsembleModel

        assert isinstance(result["model"], EnsembleModel)
        assert result["model"]._meta_learner is not None


# ---------------------------------------------------------------------------
# Multi-model comparison mode
# ---------------------------------------------------------------------------


class TestTrainingStepMultiModel:
    """Tests for comparison mode (multiple models without ensemble)."""

    @pytest.fixture
    def multi_model_step(self, parquet_splits, temp_dir):
        """TrainingStep configured for comparison mode (2 models, no ensemble)."""
        train_path, val_path = parquet_splits
        DummyCls = _dummy_model_class(0.6)

        with patch("energizados.core.steps.training.ModelRegistry") as mock_reg:
            mock_reg.get.return_value = DummyCls

            step = TrainingStep(
                train_path=train_path,
                val_path=val_path,
                models_configs=[
                    {"name": "lgbm", "type": "lightgbm", "hyperparams": {}},
                    {"name": "cat", "type": "catboost", "hyperparams": {}},
                ],
                ensemble_config=None,  # No ensemble → comparison mode
                feature_engineering_config={"enabled": False},
                output_dir=str(temp_dir / "models"),
            )
            yield step, temp_dir

    def test_comparison_mode_saves_individual_models(self, multi_model_step):
        """Each model should be saved to its own subdirectory."""
        step, temp_dir = multi_model_step
        step.execute({})

        # Check individual model files
        assert (temp_dir / "models" / "lgbm" / "model.pkl").exists()
        assert (temp_dir / "models" / "cat" / "model.pkl").exists()

    def test_comparison_mode_context_keys(self, multi_model_step):
        """Context should have model_paths dict, not single model_path."""
        step, _ = multi_model_step
        result = step.execute({})

        # New comparison mode keys
        assert "model_paths" in result
        assert isinstance(result["model_paths"], dict)
        assert "lgbm" in result["model_paths"]
        assert "cat" in result["model_paths"]

        # Single model keys should be None
        assert result["model_path"] is None
        assert result["model"] is None

        # Metrics should be per-model dict
        assert "val_metrics" in result
        assert isinstance(result["val_metrics"], dict)
        assert "lgbm" in result["val_metrics"]
        assert "cat" in result["val_metrics"]

        # Single metrics should be None
        assert result["val_auc"] is None
        assert result["val_f1"] is None

        # Comparison mode flag
        assert result["comparison_mode"] is True

    def test_comparison_mode_returns_models_dict(self, multi_model_step):
        """result["models"] should be a dict of fitted models."""
        step, _ = multi_model_step
        result = step.execute({})

        assert "models" in result
        assert isinstance(result["models"], dict)
        assert "lgbm" in result["models"]
        assert "cat" in result["models"]
        assert isinstance(result["models"]["lgbm"], _DummyModel)
        assert isinstance(result["models"]["cat"], _DummyModel)

    def test_comparison_mode_val_metrics_structure(self, multi_model_step):
        """val_metrics should contain auc and f1 for each model."""
        step, _ = multi_model_step
        result = step.execute({})

        for model_name in ["lgbm", "cat"]:
            assert model_name in result["val_metrics"]
            metrics = result["val_metrics"][model_name]
            assert "auc" in metrics
            assert "f1" in metrics
            assert isinstance(metrics["auc"], float)
            assert isinstance(metrics["f1"], float)
            assert 0.0 <= metrics["auc"] <= 1.0
            assert 0.0 <= metrics["f1"] <= 1.0

    def test_three_way_branching(self, parquet_splits, temp_dir):
        """Verify three-way branching: single/ensemble/comparison."""
        train_path, val_path = parquet_splits
        DummyCls = _dummy_model_class(0.6)

        with patch("energizados.core.steps.training.ModelRegistry") as mock_reg:
            mock_reg.get.return_value = DummyCls

            # 1. Single model
            step_single = TrainingStep(
                train_path=train_path,
                val_path=val_path,
                models_configs=[{"type": "lightgbm", "hyperparams": {}}],
                ensemble_config=None,
                feature_engineering_config={"enabled": False},
                output_dir=str(temp_dir / "single"),
            )
            result_single = step_single.execute({})
            assert result_single["comparison_mode"] is False
            assert result_single["model_path"] is not None
            assert result_single["model_paths"] is None

            # 2. Ensemble mode
            step_ensemble = TrainingStep(
                train_path=train_path,
                val_path=val_path,
                models_configs=[
                    {"type": "lightgbm", "hyperparams": {}},
                    {"type": "catboost", "hyperparams": {}},
                ],
                ensemble_config={"method": "soft_voting"},
                feature_engineering_config={"enabled": False},
                output_dir=str(temp_dir / "ensemble"),
            )
            result_ensemble = step_ensemble.execute({})
            assert result_ensemble["comparison_mode"] is False
            assert result_ensemble["model_path"] is not None
            assert result_ensemble["model_paths"] is None

            # 3. Comparison mode
            step_compare = TrainingStep(
                train_path=train_path,
                val_path=val_path,
                models_configs=[
                    {"name": "lgbm", "type": "lightgbm", "hyperparams": {}},
                    {"name": "cat", "type": "catboost", "hyperparams": {}},
                ],
                ensemble_config=None,
                feature_engineering_config={"enabled": False},
                output_dir=str(temp_dir / "compare"),
            )
            result_compare = step_compare.execute({})
            assert result_compare["comparison_mode"] is True
            assert result_compare["model_path"] is None
            assert result_compare["model_paths"] is not None


# ---------------------------------------------------------------------------
# Validate input / get_required_keys
# ---------------------------------------------------------------------------
# Validate input / get_required_keys
# ---------------------------------------------------------------------------


class TestTrainingStepValidation:
    def test_validate_fails_without_paths(self, temp_dir):
        step = TrainingStep(models_configs=[], output_dir=str(temp_dir))
        assert step.validate_input({}) is False

    def test_validate_passes_with_valid_paths(self, parquet_splits, temp_dir):
        train_path, val_path = parquet_splits
        step = TrainingStep(
            train_path=train_path,
            val_path=val_path,
            models_configs=[],
            output_dir=str(temp_dir),
        )
        assert step.validate_input({}) is True

    def test_required_keys_empty_when_paths_provided(self, parquet_splits, temp_dir):
        train_path, val_path = parquet_splits
        step = TrainingStep(
            train_path=train_path,
            val_path=val_path,
            models_configs=[],
            output_dir=str(temp_dir),
        )
        assert step.get_required_keys() == []

    def test_required_keys_when_paths_not_provided(self, temp_dir):
        step = TrainingStep(models_configs=[], output_dir=str(temp_dir))
        keys = step.get_required_keys()
        assert "train_path" in keys
        assert "val_path" in keys

    def test_output_keys(self, temp_dir):
        step = TrainingStep(models_configs=[], output_dir=str(temp_dir))
        keys = step.get_output_keys()
        for k in [
            "model",
            "model_path",
            "feature_engineering_path",
            "val_predictions_path",
            "val_auc",
            "val_f1",
        ]:
            assert k in keys


# ---------------------------------------------------------------------------
# Pipeline config parsing
# ---------------------------------------------------------------------------


class TestPipelineConfigParsing:
    """Verify that ConfigPipelineBuilder correctly passes models_configs to TrainingStep."""

    def test_pipeline_passes_models_list(self, temp_dir):
        """ConfigPipelineBuilder reads training.models list."""
        import yaml

        from energizados.core.pipeline import ConfigPipelineBuilder
        from energizados.core.steps.training import TrainingStep

        cfg_file = temp_dir / "cfg.yaml"
        cfg_file.write_text(
            yaml.dump(
                {
                    "train": {
                        "enabled": True,
                        "target_column": "target",
                        "models": [{"type": "lightgbm", "hyperparams": {}}],
                        "feature_engineering": {"enabled": False},
                    }
                }
            )
        )

        pipeline = ConfigPipelineBuilder(str(cfg_file)).build()
        step = pipeline.steps[0]
        assert isinstance(step, TrainingStep)
        assert len(step.models_configs) == 1
        assert step.models_configs[0]["type"] == "lightgbm"

    def test_pipeline_passes_ensemble_config(self, temp_dir):
        """ConfigPipelineBuilder reads training.ensemble dict."""
        import yaml

        from energizados.core.pipeline import ConfigPipelineBuilder
        from energizados.core.steps.training import TrainingStep

        cfg_file = temp_dir / "cfg2.yaml"
        cfg_file.write_text(
            yaml.dump(
                {
                    "train": {
                        "enabled": True,
                        "models": [{"type": "lightgbm"}, {"type": "catboost"}],
                        "ensemble": {"method": "soft_voting", "weights": [0.6, 0.4]},
                        "feature_engineering": {"enabled": False},
                    }
                }
            )
        )

        pipeline = ConfigPipelineBuilder(str(cfg_file)).build()
        step = pipeline.steps[0]
        assert isinstance(step, TrainingStep)
        assert step.ensemble_config["method"] == "soft_voting"

    def test_pipeline_no_ensemble_when_single_model(self, temp_dir):
        """ensemble_config is None when only one model is specified."""
        import yaml

        from energizados.core.pipeline import ConfigPipelineBuilder
        from energizados.core.steps.training import TrainingStep

        cfg_file = temp_dir / "cfg3.yaml"
        cfg_file.write_text(
            yaml.dump(
                {
                    "train": {
                        "enabled": True,
                        "models": [{"type": "lightgbm"}],
                        "feature_engineering": {"enabled": False},
                    }
                }
            )
        )

        pipeline = ConfigPipelineBuilder(str(cfg_file)).build()
        step = pipeline.steps[0]
        assert isinstance(step, TrainingStep)
        assert step.ensemble_config is None
