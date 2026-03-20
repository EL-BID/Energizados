"""
Unit tests for BaseModel.

Tests for the Model base class that defines the interface
that all custom models must implement.
"""

import numpy as np
import pandas as pd
import pytest

from energizados.core.base import BaseModel


class TestBaseModel:
    """Tests for the BaseModel class."""

    @pytest.fixture
    def sample_data(self):
        """Returns sample data for testing.

        Returns:
            tuple: A tuple containing:
                - X (pd.DataFrame): Feature DataFrame with 5 rows and 2 columns.
                - y (pd.Series): Target Series with 5 binary labels.
        """
        X = pd.DataFrame(
            {
                "feature1": [1, 2, 3, 4, 5],
                "feature2": [2, 4, 6, 8, 10],
            }
        )
        y = pd.Series([0, 0, 1, 1, 1])
        return X, y

    def test_base_model_has_config(self):
        """Verify that BaseModel accepts config."""

        # Create minimal concrete implementation to test config
        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

            def get_raw_model(self):
                return self.model_

        model = ConcreteModel(config={"learning_rate": 0.01})
        assert model.config == {"learning_rate": 0.01}

    def test_base_model_default_config(self):
        """Verify that BaseModel uses empty config by default."""

        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

            def get_raw_model(self):
                return self.model_

        model = ConcreteModel()
        assert model.config == {}

    def test_base_model_initialized_attributes(self):
        """Verify the initial attributes of the model."""

        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

            def get_raw_model(self):
                return self.model_

        model = ConcreteModel()
        assert model.model_ is None
        assert model.is_fitted_ is False

    def test_concrete_model_must_implement_fit(self):
        """Verify that a model must implement fit()."""

        class IncompleteModel(BaseModel):
            def predict(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0, 0])

            def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0.0, 0.0])

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_concrete_model_must_implement_predict(self):
        """Verify that a model must implement predict()."""

        class IncompleteModel(BaseModel):
            def fit(self, X: pd.DataFrame, y: pd.Series, X_val=None, y_val=None):
                self.is_fitted_ = True
                return self

            def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0.0, 0.0])

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_concrete_model_must_implement_predict_proba(self):
        """Verify that a model must implement predict_proba()."""

        class IncompleteModel(BaseModel):
            def fit(self, X: pd.DataFrame, y: pd.Series, X_val=None, y_val=None):
                self.is_fitted_ = True
                return self

            def predict(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0, 0])

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_concrete_model_must_implement_get_raw_model(self):
        """Verify that a model must implement get_raw_model()."""

        class IncompleteModel(BaseModel):
            def fit(self, X: pd.DataFrame, y: pd.Series, X_val=None, y_val=None):
                self.is_fitted_ = True
                return self

            def predict(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0, 0])

            def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0.0, 0.0])

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_complete_model_can_be_instantiated(self):
        """Verify that a complete model can be instantiated."""

        class CompleteModel(BaseModel):
            def fit(self, X: pd.DataFrame, y: pd.Series, X_val=None, y_val=None):
                self.model_ = "dummy_model"
                self.is_fitted_ = True
                return self

            def predict(self, X: pd.DataFrame) -> np.ndarray:
                self.check_fitted()
                return np.array([0, 0])

            def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
                self.check_fitted()
                return np.array([0.5, 0.5])

            def get_raw_model(self):
                return self.model_

        model = CompleteModel()
        assert model is not None

    def test_check_fitted_raises_error_if_not_fitted(self):
        """Verify that check_fitted raises error if model is not trained."""
        from energizados.core.exceptions import ModelNotFittedError

        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

            def get_raw_model(self):
                return self.model_

        model = ConcreteModel()

        with pytest.raises(ModelNotFittedError, match="is not fitted"):
            model.check_fitted()

    def test_check_fitted_passes_if_fitted(self):
        """Verify that check_fitted does not raise error if model is trained."""

        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

            def get_raw_model(self):
                return self.model_

        model = ConcreteModel()
        model.is_fitted_ = True

        # Should not raise exception
        model.check_fitted()

    def test_fit_accepts_validation_data(self, sample_data):
        """Verify that fit() accepts optional validation data."""
        X, y = sample_data
        X_val = X.iloc[:2]
        y_val = y.iloc[:2]

        class TestModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                self.model_ = "trained"
                self.is_fitted_ = True
                return self

            def predict(self, X):
                return np.array([0, 0])

            def predict_proba(self, X):
                return np.array([0.5, 0.5])

            def get_raw_model(self):
                return self.model_

        model = TestModel()
        model.fit(X, y, X_val=X_val, y_val=y_val)

        assert model.is_fitted_

    def test_fit_without_validation_data(self, sample_data):
        """Verify that fit() works without validation data."""
        X, y = sample_data

        class TestModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                self.model_ = "trained"
                self.is_fitted_ = True
                return self

            def predict(self, X):
                return np.array([0, 0])

            def predict_proba(self, X):
                return np.array([0.5, 0.5])

            def get_raw_model(self):
                return self.model_

        model = TestModel()
        model.fit(X, y)

        assert model.is_fitted_
