"""
Unit tests for DefaultInference and InferenceStep.

Tests cover: initialization, load_model, predict, save_predictions,
standalone loading, output enrichment, metadata sidecar, and schema validation.
"""

import json
import pickle  # nosec B403
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from energizados.core.builders.inference_builder import InferenceBuilder
from energizados.core.schemas.config_validator import ConfigValidator
from energizados.core.schemas.schemas import INFERENCE_SCHEMA
from energizados.inference.default import DefaultInference


# Simple picklable mock model class
class _MockModel:
    """Simple picklable mock model for testing."""

    def __init__(self, proba_values=None):
        self.is_fitted_ = True
        self._proba_values = proba_values or [0.5] * 5

    def predict_proba(self, X):
        n = len(X)
        return np.array(
            self._proba_values[:n]
            if len(self._proba_values) >= n
            else self._proba_values * (n // len(self._proba_values) + 1)
        )


class TestDefaultInference:
    """Test suite for DefaultInference class."""

    def test_inference_init_default(self):
        """Test inference initialization with default parameters."""
        inference = DefaultInference()

        assert inference.model_path is None
        assert inference.threshold == 0.5
        assert inference.model is None

    def test_inference_init_custom_threshold(self):
        """Test inference initialization with custom threshold."""
        inference = DefaultInference(threshold=0.7)

        assert inference.threshold == 0.7

    def test_inference_init_with_model_path(self, temp_dir):
        """Test inference initialization with model_path."""
        model_path = temp_dir / "model.pkl"

        # Create empty model file
        with open(model_path, "wb") as f:
            pickle.dump({}, f)

        inference = DefaultInference(model_path=str(model_path))

        assert inference.model_path == str(model_path)

    def test_inference_load_model_success(self, temp_dir):
        """Test loading a model successfully."""
        # Create a mock model
        mock_model = _MockModel()

        model_path = temp_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(mock_model, f)

        # Mock secure_load at its source
        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.return_value = mock_model

            inference = DefaultInference()
            loaded_model = inference.load_model(str(model_path))

            assert loaded_model is not None
            assert inference.model is loaded_model
            mock_load.assert_called_once()

    def test_inference_load_model_no_path_raises(self):
        """Test that loading without path raises ValueError."""
        inference = DefaultInference()

        with pytest.raises(ValueError, match="No model path provided"):
            inference.load_model()

    def test_inference_load_model_file_not_found(self, temp_dir):
        """Test that loading non-existent file raises FileNotFoundError."""
        inference = DefaultInference()
        non_existent_path = temp_dir / "nonexistent.pkl"

        with pytest.raises(FileNotFoundError):
            inference.load_model(str(non_existent_path))

    def test_inference_predict_binary(self, temp_dir):
        """Test binary prediction flow."""
        # Create a mock model
        mock_model = _MockModel(proba_values=[0.3, 0.7, 0.4, 0.6, 0.2])

        model_path = temp_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(mock_model, f)

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.return_value = mock_model

            inference = DefaultInference()
            inference.load_model(str(model_path))

            X = pd.DataFrame({"f1": [1, 2, 3, 4, 5]})
            predictions = inference.predict(inference.model, X)

            assert isinstance(predictions, np.ndarray)
            assert len(predictions) == len(X)
            # With threshold 0.5: [0, 1, 0, 1, 0]
            assert predictions[0] == 0  # 0.3 < 0.5
            assert predictions[1] == 1  # 0.7 >= 0.5

    def test_inference_predict_proba(self, temp_dir):
        """Test probability prediction flow."""
        # Create a mock model
        proba_values = [0.3, 0.7, 0.4, 0.6, 0.2]
        mock_model = _MockModel(proba_values=proba_values)

        model_path = temp_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(mock_model, f)

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.return_value = mock_model

            inference = DefaultInference()
            inference.load_model(str(model_path))

            X = pd.DataFrame({"f1": [1, 2, 3, 4, 5]})
            probas = inference.predict_proba(inference.model, X)

            assert isinstance(probas, np.ndarray)
            assert len(probas) == len(X)
            np.testing.assert_array_equal(probas, proba_values)

    def test_inference_predict_custom_threshold(self, temp_dir):
        """Test prediction with custom threshold."""
        # Create a mock model with different probabilities
        mock_model = _MockModel(proba_values=[0.3, 0.7, 0.4, 0.6, 0.2])

        model_path = temp_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(mock_model, f)

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.return_value = mock_model

            inference = DefaultInference(threshold=0.65)
            inference.load_model(str(model_path))

            X = pd.DataFrame({"f1": [1, 2, 3, 4, 5]})
            predictions = inference.predict(inference.model, X)

            # With threshold 0.65: [0, 1, 0, 0, 0]
            assert predictions[0] == 0  # 0.3 < 0.65
            assert predictions[1] == 1  # 0.7 >= 0.65
            assert predictions[2] == 0  # 0.4 < 0.65
            assert predictions[3] == 0  # 0.6 < 0.65
            assert predictions[4] == 0  # 0.2 < 0.65

    def test_inference_save_predictions(self, temp_dir):
        """Test saving predictions to CSV."""
        predictions = np.array([0, 1, 0, 1, 0])
        output_path = temp_dir / "predictions.csv"

        inference = DefaultInference()
        inference.save_predictions(predictions, str(output_path))

        assert output_path.exists()

        # Verify content
        df = pd.read_csv(output_path)
        assert "prediction" in df.columns
        assert len(df) == len(predictions)
        np.testing.assert_array_equal(df["prediction"].values, predictions)

    def test_inference_save_predictions_with_proba(self, temp_dir):
        """Test saving predictions and probabilities to CSV."""
        predictions = np.array([0, 1, 0, 1, 0])
        probas = np.array([0.3, 0.7, 0.4, 0.6, 0.2])
        output_path = temp_dir / "predictions_with_proba.csv"

        inference = DefaultInference()
        inference.save_predictions_with_proba(predictions, probas, str(output_path))

        assert output_path.exists()

        # Verify content
        df = pd.read_csv(output_path)
        assert "prediction" in df.columns
        assert "probability" in df.columns
        assert len(df) == len(predictions)
        np.testing.assert_array_equal(df["prediction"].values, predictions)
        np.testing.assert_array_almost_equal(df["probability"].values, probas)

    def test_inference_save_creates_directory(self, temp_dir):
        """Test that save_predictions creates parent directory if not exists."""
        predictions = np.array([0, 1, 0])
        # Path with non-existent parent directory
        output_path = temp_dir / "subdir" / "nested" / "predictions.csv"

        inference = DefaultInference()
        inference.save_predictions(predictions, str(output_path))

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_inference_model_attribute_set_after_load(self, temp_dir):
        """Test that model attribute is set after load_model()."""
        mock_model = _MockModel()

        model_path = temp_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(mock_model, f)

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.return_value = mock_model

            inference = DefaultInference()
            assert inference.model is None

            inference.load_model(str(model_path))

            assert inference.model is not None

    def test_inference_predict_uses_stored_threshold(self, temp_dir):
        """Test that predict uses the instance threshold, not default."""
        # Create a mock model with different probabilities
        mock_model = _MockModel(proba_values=[0.3, 0.7, 0.5])

        model_path = temp_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(mock_model, f)

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.return_value = mock_model

            # Use threshold=0.5 (default)
            inference = DefaultInference(threshold=0.5)
            inference.load_model(str(model_path))
            X = pd.DataFrame({"f1": [1, 2, 3]})
            predictions_default = inference.predict(inference.model, X)

            # Use threshold=0.8
            inference_high = DefaultInference(threshold=0.8)
            inference_high.load_model(str(model_path))
            predictions_high = inference_high.predict(inference_high.model, X)

            # Results should differ based on threshold
            assert not np.array_equal(predictions_default, predictions_high)


# ---------------------------------------------------------------------------
# Task 1.1 — INFERENCE_SCHEMA new fields
# ---------------------------------------------------------------------------


class TestInferenceSchema:
    """Tests for INFERENCE_SCHEMA accepting new production-inference fields."""

    def test_schema_accepts_model_path(self):
        """INFERENCE_SCHEMA must accept model_path (string)."""
        props = INFERENCE_SCHEMA["properties"]
        assert "model_path" in props
        assert props["model_path"]["type"] == "string"

    def test_schema_accepts_feature_engineering_path(self):
        """INFERENCE_SCHEMA must accept feature_engineering_path (string)."""
        props = INFERENCE_SCHEMA["properties"]
        assert "feature_engineering_path" in props
        assert props["feature_engineering_path"]["type"] == "string"

    def test_schema_accepts_output_include_input(self):
        """INFERENCE_SCHEMA must accept output_include_input (boolean)."""
        props = INFERENCE_SCHEMA["properties"]
        assert "output_include_input" in props
        assert props["output_include_input"]["type"] == "boolean"

    def test_schema_accepts_output_format(self):
        """INFERENCE_SCHEMA must accept output_format with enum csv|parquet."""
        props = INFERENCE_SCHEMA["properties"]
        assert "output_format" in props
        assert props["output_format"]["type"] == "string"
        assert set(props["output_format"]["enum"]) == {"csv", "parquet"}


# ---------------------------------------------------------------------------
# Task 1.2 — _validate_inference expansion
# ---------------------------------------------------------------------------


class TestInferenceValidation:
    """Tests for expanded _validate_inference() with new field checks."""

    def test_valid_new_fields_no_errors(self):
        """A valid config with all new fields produces zero errors."""
        validator = ConfigValidator()
        config = {
            "infer": {
                "enabled": True,
                "input_path": "data/processed/test.parquet",
                "output_path": "output/predictions.csv",
                "model_path": "output/train-20260101_1200/models/model.pkl",
                "feature_engineering_path": "output/train-20260101_1200/models/fe.pkl",
                "output_include_input": True,
                "output_format": "csv",
                "threshold": 0.5,
            }
        }
        errors = validator._validate_inference(config["infer"])
        assert errors == []

    def test_invalid_output_format_rejected(self):
        """output_format must be 'csv' or 'parquet' — 'json' is invalid."""
        validator = ConfigValidator()
        config = {
            "infer": {
                "output_format": "json",
            }
        }
        errors = validator._validate_inference(config["infer"])
        assert len(errors) >= 1
        assert any("output_format" in str(e) for e in errors)

    def test_non_bool_output_include_input_rejected(self):
        """output_include_input must be a boolean — string is invalid."""
        validator = ConfigValidator()
        config = {
            "infer": {
                "output_include_input": "yes",
            }
        }
        errors = validator._validate_inference(config["infer"])
        assert len(errors) >= 1
        assert any("output_include_input" in str(e) for e in errors)

    def test_model_path_nonexistent_warning_not_error(self, temp_dir):
        """model_path pointing to a non-existent file should warn, not error."""
        validator = ConfigValidator()
        config = {
            "infer": {
                "model_path": "not/a/real/path.pkl",
            }
        }
        errors = validator._validate_inference(config["infer"])
        # Should NOT be an error — just a warning at runtime
        assert not any("model_path" in str(e) for e in errors)

    def test_legacy_config_still_valid(self):
        """An old-style config without any new fields must still validate."""
        validator = ConfigValidator()
        config = {
            "infer": {
                "enabled": True,
                "input_path": "data/processed/test.parquet",
                "output_path": "output/predictions.csv",
                "threshold": 0.5,
            }
        }
        errors = validator._validate_inference(config["infer"])
        assert errors == []


# ---------------------------------------------------------------------------
# Tasks 2.1-2.5 — InferenceStep standalone loading & output enrichment
# ---------------------------------------------------------------------------


def _make_mock_model(proba_values=None):
    """Create a mock model for InferenceStep tests."""
    model = MagicMock()
    model.is_fitted_ = True
    _proba = proba_values or [0.5] * 5

    def _predict_proba(X):
        n = len(X)
        return np.array(_proba[:n] if len(_proba) >= n else _proba * (n // len(_proba) + 1))

    model.predict_proba = _predict_proba
    return model


class TestInferenceStepStandalone:
    """Tests for InferenceStep loading model/FE from config paths."""

    def test_load_model_from_config_path(self, temp_dir):
        """When model_path is in config, model loads via secure_load."""
        mock_model = _make_mock_model([0.3, 0.7, 0.4])
        # Create a dummy file at model_path (content doesn't matter — secure_load is mocked)
        model_path = temp_dir / "model.pkl"
        model_path.write_bytes(b"fake")

        input_path = temp_dir / "input.parquet"
        pd.DataFrame({"f1": [1, 2, 3]}).to_parquet(input_path, index=False)

        config = {
            "model_path": str(model_path),
            "input_path": str(input_path),
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        with patch("energizados.core.utils.secure_pickle.secure_load", return_value=mock_model):
            context = step.execute({})

        assert "predictions" in context
        assert "prediction_probas" in context
        assert len(context["predictions"]) == 3

    def test_load_fe_from_config_path(self, temp_dir):
        """When feature_engineering_path is in config, FE loads via secure_load."""
        mock_model = _make_mock_model([0.3, 0.7])
        mock_fe = MagicMock()
        mock_fe.transform = lambda df: df  # passthrough

        model_path = temp_dir / "model.pkl"
        model_path.write_bytes(b"fake")
        fe_path = temp_dir / "fe.pkl"
        fe_path.write_bytes(b"fake")

        input_path = temp_dir / "input.parquet"
        pd.DataFrame({"f1": [1, 2]}).to_parquet(input_path, index=False)

        config = {
            "model_path": str(model_path),
            "feature_engineering_path": str(fe_path),
            "input_path": str(input_path),
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        def _secure_load_side_effect(path, **kwargs):
            if "fe" in str(path):
                return mock_fe
            return mock_model

        with patch(
            "energizados.core.utils.secure_pickle.secure_load",
            side_effect=_secure_load_side_effect,
        ):
            context = step.execute({})

        assert "predictions" in context

    def test_context_fallback_no_config_paths(self, temp_dir):
        """Without config paths, model from context is used (backward compat)."""
        mock_model = _make_mock_model([0.3, 0.7])

        input_path = temp_dir / "input.parquet"
        pd.DataFrame({"f1": [1, 2]}).to_parquet(input_path, index=False)

        config = {
            "input_path": str(input_path),
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        context = {"model": mock_model}
        result = step.execute(context)

        assert "predictions" in result
        assert len(result["predictions"]) == 2

    def test_error_when_no_model_available(self, temp_dir):
        """Without config paths AND no context model → ValueError with clear message."""
        input_path = temp_dir / "input.parquet"
        pd.DataFrame({"f1": [1, 2]}).to_parquet(input_path, index=False)

        config = {
            "input_path": str(input_path),
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        with pytest.raises(ValueError, match="No model available"):
            step.execute({})

    def test_no_fe_warns_not_errors(self, temp_dir):
        """Without FE in config or context, predictions proceed with a warning."""
        mock_model = _make_mock_model([0.3, 0.7])

        input_path = temp_dir / "input.parquet"
        pd.DataFrame({"f1": [1, 2]}).to_parquet(input_path, index=False)

        config = {
            "input_path": str(input_path),
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        with patch("energizados.core.builders.inference_builder.logger") as mock_logger:
            context = {"model": mock_model}
            result = step.execute(context)
            # A warning about missing FE should be logged
            mock_logger.warning.assert_called()
            warn_msg = mock_logger.warning.call_args[0][0]
            assert "No feature engineering" in warn_msg or "raw features" in warn_msg

        assert "predictions" in result

    def test_validate_input_true_with_model_path(self):
        """validate_input returns True when model_path is in config (standalone mode)."""
        config = {
            "model_path": "output/model.pkl",
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        # Even with empty context, should return True
        assert step.validate_input({}) is True

    def test_validate_input_false_without_model_path_or_context(self):
        """validate_input returns False when no model_path and no context model."""
        config = {
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        assert step.validate_input({}) is False


class TestInferenceStepEnrichedOutput:
    """Tests for enriched output (input columns + prediction + probability)."""

    def test_csv_output_includes_input_columns(self, temp_dir):
        """output_include_input=true → CSV has original columns + prediction + probability."""
        mock_model = _make_mock_model([0.3, 0.7])
        input_data = pd.DataFrame({"f1": [1.0, 2.0], "f2": ["a", "b"]})
        input_path = temp_dir / "input.parquet"
        input_data.to_parquet(input_path, index=False)
        output_path = temp_dir / "predictions.csv"

        config = {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "output_include_input": True,
            "output_format": "csv",
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        context = {"model": mock_model}
        step.execute(context)

        assert output_path.exists()
        df = pd.read_csv(output_path)
        assert "f1" in df.columns
        assert "f2" in df.columns
        assert "prediction" in df.columns
        assert "probability" in df.columns
        assert len(df) == 2

    def test_parquet_output_includes_input_columns(self, temp_dir):
        """output_format='parquet' → parquet file with enriched columns."""
        mock_model = _make_mock_model([0.3, 0.7])
        input_data = pd.DataFrame({"f1": [1.0, 2.0], "f2": ["a", "b"]})
        input_path = temp_dir / "input.parquet"
        input_data.to_parquet(input_path, index=False)
        output_path = temp_dir / "predictions.parquet"

        config = {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "output_include_input": True,
            "output_format": "parquet",
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        context = {"model": mock_model}
        step.execute(context)

        assert output_path.exists()
        df = pd.read_parquet(output_path)
        assert "f1" in df.columns
        assert "prediction" in df.columns
        assert "probability" in df.columns

    def test_output_without_include_input(self, temp_dir):
        """output_include_input=false → only prediction + probability columns."""
        mock_model = _make_mock_model([0.3, 0.7])
        input_data = pd.DataFrame({"f1": [1.0, 2.0], "f2": ["a", "b"]})
        input_path = temp_dir / "input.parquet"
        input_data.to_parquet(input_path, index=False)
        output_path = temp_dir / "predictions.csv"

        config = {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "output_include_input": False,
            "output_format": "csv",
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        context = {"model": mock_model}
        step.execute(context)

        df = pd.read_csv(output_path)
        assert set(df.columns) == {"prediction", "probability"}

    def test_metadata_sidecar_content(self, temp_dir):
        """Metadata sidecar has model_hash, timestamp, threshold, row_count."""
        mock_model = _make_mock_model([0.3, 0.7])
        input_data = pd.DataFrame({"f1": [1.0, 2.0]})
        input_path = temp_dir / "input.parquet"
        input_data.to_parquet(input_path, index=False)
        output_path = temp_dir / "predictions.csv"

        # Create a .sig file for model_path
        model_path = temp_dir / "model.pkl"
        model_path.write_bytes(b"fake")
        sig_path = str(model_path) + ".sig"
        with open(sig_path, "w") as f:
            f.write("abc123fake_hash")

        config = {
            "model_path": str(model_path),
            "input_path": str(input_path),
            "output_path": str(output_path),
            "output_include_input": True,
            "output_format": "csv",
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        with patch("energizados.core.utils.secure_pickle.secure_load", return_value=mock_model):
            step.execute({})

        metadata_path = Path(str(output_path) + ".metadata.json")
        assert metadata_path.exists()

        meta = json.loads(metadata_path.read_text())
        assert "model_hash" in meta
        assert meta["model_hash"] == "abc123fake_hash"
        assert "timestamp" in meta
        assert "threshold" in meta
        assert meta["threshold"] == 0.5
        assert "row_count" in meta
        assert meta["row_count"] == 2
        assert "output_format" in meta
        assert meta["output_format"] == "csv"
        assert "include_input" in meta
        assert meta["include_input"] is True

    def test_metadata_sidecar_no_sig_file(self, temp_dir):
        """Metadata sidecar has model_hash=null when no .sig file exists."""
        mock_model = _make_mock_model([0.3, 0.7])
        input_data = pd.DataFrame({"f1": [1.0, 2.0]})
        input_path = temp_dir / "input.parquet"
        input_data.to_parquet(input_path, index=False)
        output_path = temp_dir / "predictions.csv"

        model_path = temp_dir / "model.pkl"
        model_path.write_bytes(b"fake")
        # No .sig file

        config = {
            "model_path": str(model_path),
            "input_path": str(input_path),
            "output_path": str(output_path),
            "output_format": "csv",
            "threshold": 0.5,
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        with patch("energizados.core.utils.secure_pickle.secure_load", return_value=mock_model):
            step.execute({})

        metadata_path = Path(str(output_path) + ".metadata.json")
        assert metadata_path.exists()
        meta = json.loads(metadata_path.read_text())
        assert meta["model_hash"] is None


# ---------------------------------------------------------------------------
# Task 3.2 — Template security check
# ---------------------------------------------------------------------------


class TestInferenceTemplate:
    """Tests for 03_inference.py.tpl template using secure_load."""

    def test_template_uses_secure_load(self):
        """Generated template must use secure_load, not pickle.load."""
        tpl_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "energizados"
            / "templates"
            / "src"
            / "run"
            / "03_inference.py.tpl"
        )
        content = tpl_path.read_text()
        assert "secure_load" in content
        assert "pickle.load" not in content

    def test_template_no_import_pickle(self):
        """Generated template must not import pickle."""
        tpl_path = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "energizados"
            / "templates"
            / "src"
            / "run"
            / "03_inference.py.tpl"
        )
        content = tpl_path.read_text()
        assert "import pickle" not in content
