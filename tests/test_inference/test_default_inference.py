"""
Unit tests for DefaultInference.

Tests cover: initialization, load_model, predict, save_predictions methods.
"""

import pickle  # nosec B403
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

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
