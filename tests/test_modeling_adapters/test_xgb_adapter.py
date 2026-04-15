"""
Unit tests for XGBModelAdapter.

Tests cover: initialization, fit, predict, predict_proba methods.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from energizados.core.exceptions import ModelNotFittedError
from energizados.modeling.adapters import XGBModelAdapter


class TestXGBModelAdapter:
    """Test suite for XGBModelAdapter class."""

    def test_adapter_init_default(self):
        """Test adapter initialization with default parameters."""
        cols_for_model = ["feature_0", "feature_1"]
        adapter = XGBModelAdapter(cols_for_model=cols_for_model)

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
        hyperparams = {"max_depth": 6, "learning_rate": 0.05}

        adapter = XGBModelAdapter(
            cols_for_model=cols_for_model,
            hyperparams=hyperparams,
            search_hip=True,
            sampling_th=0.3,
            sampling_method="oversample",
            n_iter=100,
            cv=5,
            class_weight=10,
        )

        assert adapter.cols_for_model == cols_for_model
        assert adapter.hyperparams == hyperparams
        assert adapter.search_hip is True
        assert adapter.sampling_th == 0.3
        assert adapter.sampling_method == "oversample"
        assert adapter.n_iter == 100
        assert adapter.cv == 5
        assert adapter.class_weight == 10

    def test_adapter_fit_sets_fitted(self, synthetic_classification_data):
        """Test that fit() sets is_fitted_ to True."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.3, 0.7]] * len(X))

        with patch("energizados.modeling.supervised_models.XGBModel") as MockXGB:
            mock_instance = MagicMock()
            mock_instance.train.return_value = mock_pipeline
            MockXGB.return_value = mock_instance

            adapter = XGBModelAdapter(cols_for_model=cols)
            result = adapter.fit(X, y)

            assert adapter.is_fitted_ is True
            assert result is adapter

    def test_adapter_predict_output_shape(self, synthetic_classification_data):
        """Test that predict() returns correct output shape."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.3, 0.7]] * len(X))

        adapter = XGBModelAdapter(cols_for_model=cols)
        adapter._trained_pipeline = mock_pipeline
        adapter.is_fitted_ = True

        predictions = adapter.predict(X)

        assert isinstance(predictions, np.ndarray)
        assert predictions.shape == (len(X),)
        assert predictions.dtype in (np.int32, np.int64)

    def test_adapter_predict_proba_output_shape(self, synthetic_classification_data):
        """Test that predict_proba() returns correct output shape."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.3, 0.7]] * len(X))

        adapter = XGBModelAdapter(cols_for_model=cols)
        adapter._trained_pipeline = mock_pipeline
        adapter.is_fitted_ = True

        probas = adapter.predict_proba(X)

        assert isinstance(probas, np.ndarray)
        assert probas.shape == (len(X),)
        assert np.all(probas >= 0)
        assert np.all(probas <= 1)

    def test_adapter_predict_raises_when_not_fitted(self, synthetic_classification_data):
        """Test that predict() raises error when model is not fitted."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        adapter = XGBModelAdapter(cols_for_model=cols)

        with pytest.raises(ModelNotFittedError):
            adapter.predict(X)

    def test_adapter_predict_proba_raises_when_not_fitted(self, synthetic_classification_data):
        """Test that predict_proba() raises error when model is not fitted."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        adapter = XGBModelAdapter(cols_for_model=cols)

        with pytest.raises(ModelNotFittedError):
            adapter.predict_proba(X)

    def test_adapter_with_config(self):
        """Test adapter initialization with config parameter."""
        cols = ["feature_0", "feature_1"]
        config = {"output_dir": "output/test"}

        adapter = XGBModelAdapter(cols_for_model=cols, config=config)

        assert adapter.config == config

    def test_get_raw_model_before_fit(self):
        """Test get_raw_model() returns None and logs warning before fit."""
        adapter = XGBModelAdapter(cols_for_model=["f0", "f1"])
        raw = adapter.get_raw_model()
        assert raw is None

    def test_get_raw_model_after_fit(self, synthetic_classification_data):
        """Test get_raw_model() returns xgbclassifier step after fit."""
        X, y = synthetic_classification_data
        cols = list(X.columns[:2])

        mock_xgb_clf = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.named_steps = {"xgbclassifier": mock_xgb_clf}

        adapter = XGBModelAdapter(cols_for_model=cols)
        adapter._trained_pipeline = mock_pipeline
        adapter.is_fitted_ = True

        raw = adapter.get_raw_model()
        assert raw is mock_xgb_clf
