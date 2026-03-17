"""
Unit tests for LGBMModelAdapter.

Tests cover: initialization, fit, predict, predict_proba methods.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from energizados.core.exceptions import ModelNotFittedError
from energizados.modeling.adapters import LGBMModelAdapter


class TestLGBMModelAdapter:
    """Test suite for LGBMModelAdapter class."""

    def test_adapter_init_default(self):
        """Test adapter initialization with default parameters."""
        cols_for_model = ["feature_0", "feature_1"]
        adapter = LGBMModelAdapter(cols_for_model=cols_for_model)

        assert adapter.cols_for_model == cols_for_model
        assert adapter.hyperparams == {}
        assert adapter.search_hip is False
        assert adapter.sampling_th == 0.5
        assert adapter.sampling_method == "undersample"
        assert adapter.n_iter == 60
        assert adapter.cv == 3

    def test_adapter_init_custom_params(self):
        """Test adapter initialization with custom parameters."""
        cols_for_model = ["feature_0", "feature_1"]
        hyperparams = {"num_leaves": 31, "learning_rate": 0.05}

        adapter = LGBMModelAdapter(
            cols_for_model=cols_for_model,
            hyperparams=hyperparams,
            search_hip=True,
            sampling_th=0.3,
            sampling_method="over",
            n_iter=100,
            cv=5,
            class_weight="balanced",
        )

        assert adapter.cols_for_model == cols_for_model
        assert adapter.hyperparams == hyperparams
        assert adapter.search_hip is True
        assert adapter.sampling_th == 0.3
        assert adapter.sampling_method == "over"
        assert adapter.n_iter == 100
        assert adapter.cv == 5
        assert adapter.class_weight == "balanced"

    def test_adapter_fit_sets_fitted(self, synthetic_classification_data):
        """Test that fit() sets is_fitted_ to True."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        # Mock the internal model's train method directly
        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.3, 0.7]] * len(X))

        with patch("energizados.modeling.supervised_models.LGBMModel") as MockLGBM:
            mock_instance = MagicMock()
            mock_instance.train.return_value = mock_pipeline
            MockLGBM.return_value = mock_instance

            adapter = LGBMModelAdapter(cols_for_model=cols)
            result = adapter.fit(X, y)

            assert adapter.is_fitted_ is True
            assert result is adapter

    def test_adapter_predict_output_shape(self, synthetic_classification_data):
        """Test that predict() returns correct output shape."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.3, 0.7]] * len(X))

        adapter = LGBMModelAdapter(cols_for_model=cols)
        adapter._trained_pipeline = mock_pipeline
        adapter.is_fitted_ = True

        predictions = adapter.predict(X)

        assert isinstance(predictions, np.ndarray)
        assert predictions.shape == (len(X),)
        assert predictions.dtype == np.int32 or predictions.dtype == np.int64

    def test_adapter_predict_proba_output_shape(self, synthetic_classification_data):
        """Test that predict_proba() returns correct output shape."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        # Mock returns 2D array for predict_proba
        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.3, 0.7]] * len(X))

        adapter = LGBMModelAdapter(cols_for_model=cols)
        adapter._trained_pipeline = mock_pipeline
        adapter.is_fitted_ = True

        probas = adapter.predict_proba(X)

        assert isinstance(probas, np.ndarray)
        # Should return the positive class probabilities (second column)
        assert probas.shape == (len(X),)
        # Probabilities should be in [0, 1]
        assert np.all(probas >= 0)
        assert np.all(probas <= 1)

    def test_adapter_predict_raises_when_not_fitted(self, synthetic_classification_data):
        """Test that predict() raises error when model is not fitted."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        adapter = LGBMModelAdapter(cols_for_model=cols)
        # Don't set is_fitted_

        with pytest.raises(ModelNotFittedError):
            adapter.predict(X)

    def test_adapter_predict_proba_raises_when_not_fitted(self, synthetic_classification_data):
        """Test that predict_proba() raises error when model is not fitted."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        adapter = LGBMModelAdapter(cols_for_model=cols)
        # Don't set is_fitted_

        with pytest.raises(ModelNotFittedError):
            adapter.predict_proba(X)

    def test_adapter_with_config(self, synthetic_classification_data):
        """Test adapter initialization with config parameter."""
        cols = ["feature_0", "feature_1"]
        config = {"output_dir": "output/test"}

        adapter = LGBMModelAdapter(cols_for_model=cols, config=config)

        assert adapter.config == config
