"""
Unit tests for NNModelAdapter.

Tests cover: initialization, fit, predict, predict_proba methods.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from energizados.core.exceptions import ModelNotFittedError
from energizados.modeling.adapters import NNModelAdapter


class TestNNModelAdapter:
    """Test suite for NNModelAdapter class."""

    def test_adapter_init_default(self, nn_adapter_data):
        """Test adapter initialization with default parameters."""
        X, y, features_names, spents_names = nn_adapter_data

        adapter = NNModelAdapter(
            features_names=features_names,
            spents_names=spents_names,
        )

        assert adapter.features_names == features_names
        assert adapter.spents_names == spents_names
        assert adapter.search_hip is False
        assert adapter.sampling_th == 0.5
        assert adapter.sampling_method == "undersample"

    def test_adapter_init_custom_params(self, nn_adapter_data):
        """Test adapter initialization with custom parameters."""
        X, y, features_names, spents_names = nn_adapter_data

        adapter = NNModelAdapter(
            features_names=features_names,
            spents_names=spents_names,
            search_hip=True,
            sampling_th=0.3,
            sampling_method="oversample",
        )

        assert adapter.features_names == features_names
        assert adapter.spents_names == spents_names
        assert adapter.search_hip is True
        assert adapter.sampling_th == 0.3
        assert adapter.sampling_method == "oversample"

    def test_adapter_fit_sets_fitted(self, nn_adapter_data):
        """Test that fit() sets is_fitted_ to True."""
        X, y, features_names, spents_names = nn_adapter_data

        # Mock the internal components
        mock_model = MagicMock()
        mock_pipe_features = MagicMock()
        mock_pipe_spent = MagicMock()

        # Mock train return value
        mock_model.train.return_value = (mock_model, mock_pipe_features, mock_pipe_spent)

        adapter = NNModelAdapter(
            features_names=features_names,
            spents_names=spents_names,
        )
        adapter._model = mock_model

        result = adapter.fit(X, y)

        assert adapter.is_fitted_ is True
        assert adapter.model_ is mock_model
        assert adapter._pipe_features is mock_pipe_features
        assert adapter._pipe_spent is mock_pipe_spent
        assert result is adapter

    def test_adapter_predict_output_shape(self, nn_adapter_data):
        """Test that predict() returns correct output shape."""
        X, y, features_names, spents_names = nn_adapter_data

        mock_model = MagicMock()
        mock_pipe_features = MagicMock()
        mock_pipe_spent = MagicMock()

        # Mock transforms
        mock_pipe_features.transform.return_value = np.random.rand(len(X), 3)
        mock_pipe_spent.transform.return_value = np.random.rand(len(X), 12)
        # Return 1D array like real Keras models
        mock_model.predict.return_value = np.array([0.8] * len(X))

        adapter = NNModelAdapter(
            features_names=features_names,
            spents_names=spents_names,
        )
        adapter.model_ = mock_model
        adapter._pipe_features = mock_pipe_features
        adapter._pipe_spent = mock_pipe_spent
        adapter.is_fitted_ = True

        predictions = adapter.predict(X)

        assert isinstance(predictions, np.ndarray)
        assert predictions.shape == (len(X),)
        assert predictions.dtype == np.int32 or predictions.dtype == np.int64

    def test_adapter_predict_proba_output_shape(self, nn_adapter_data):
        """Test that predict_proba() returns correct output shape."""
        X, y, features_names, spents_names = nn_adapter_data

        mock_model = MagicMock()
        mock_pipe_features = MagicMock()
        mock_pipe_spent = MagicMock()

        # Mock transforms
        mock_pipe_features.transform.return_value = np.random.rand(len(X), 3)
        mock_pipe_spent.transform.return_value = np.random.rand(len(X), 12)
        mock_model.predict.return_value = np.array([[0.8]] * len(X))

        adapter = NNModelAdapter(
            features_names=features_names,
            spents_names=spents_names,
        )
        adapter.model_ = mock_model
        adapter._pipe_features = mock_pipe_features
        adapter._pipe_spent = mock_pipe_spent
        adapter.is_fitted_ = True

        probas = adapter.predict_proba(X)

        assert isinstance(probas, np.ndarray)
        assert probas.shape == (len(X),)

    def test_adapter_predict_raises_when_not_fitted(self, nn_adapter_data):
        """Test that predict() raises error when model is not fitted."""
        X, y, features_names, spents_names = nn_adapter_data

        adapter = NNModelAdapter(
            features_names=features_names,
            spents_names=spents_names,
        )

        with pytest.raises(ModelNotFittedError):
            adapter.predict(X)

    def test_adapter_predict_proba_raises_when_not_fitted(self, nn_adapter_data):
        """Test that predict_proba() raises error when model is not fitted."""
        X, y, features_names, spents_names = nn_adapter_data

        adapter = NNModelAdapter(
            features_names=features_names,
            spents_names=spents_names,
        )

        with pytest.raises(ModelNotFittedError):
            adapter.predict_proba(X)

    def test_adapter_with_config(self, nn_adapter_data):
        """Test adapter initialization with config parameter."""
        X, y, features_names, spents_names = nn_adapter_data
        config = {"output_dir": "output/test"}

        adapter = NNModelAdapter(
            features_names=features_names,
            spents_names=spents_names,
            config=config,
        )

        assert adapter.config == config
