"""
Unit tests for BaseModel.

Pruebas para la clase base de Model que define la interfaz
que deben implementar todos los modelos personalizados.
"""

import numpy as np
import pandas as pd
import pytest

from energizados.core.base import BaseModel


class TestBaseModel:
    """Tests para la clase BaseModel."""

    @pytest.fixture
    def sample_data(self):
        """Retorna datos de ejemplo para pruebas."""
        X = pd.DataFrame(
            {
                "feature1": [1, 2, 3, 4, 5],
                "feature2": [2, 4, 6, 8, 10],
            }
        )
        y = pd.Series([0, 0, 1, 1, 1])
        return X, y

    def test_base_model_has_config(self):
        """Verifica que BaseModel acepte config."""

        # Crear implementación concreta mínima para testear config
        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

        model = ConcreteModel(config={"learning_rate": 0.01})
        assert model.config == {"learning_rate": 0.01}

    def test_base_model_default_config(self):
        """Verifica que BaseModel use config vacío por defecto."""

        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

        model = ConcreteModel()
        assert model.config == {}

    def test_base_model_initialized_attributes(self):
        """Verifica los atributos iniciales del modelo."""

        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

        model = ConcreteModel()
        assert model.model_ is None
        assert model.is_fitted_ is False

    def test_concrete_model_must_implement_fit(self):
        """Verifica que un modelo deba implementar fit()."""

        class IncompleteModel(BaseModel):
            def predict(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0, 0])

            def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0.0, 0.0])

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_concrete_model_must_implement_predict(self):
        """Verifica que un modelo deba implementar predict()."""

        class IncompleteModel(BaseModel):
            def fit(self, X: pd.DataFrame, y: pd.Series, X_val=None, y_val=None):
                self.is_fitted_ = True
                return self

            def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0.0, 0.0])

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_concrete_model_must_implement_predict_proba(self):
        """Verifica que un modelo deba implementar predict_proba()."""

        class IncompleteModel(BaseModel):
            def fit(self, X: pd.DataFrame, y: pd.Series, X_val=None, y_val=None):
                self.is_fitted_ = True
                return self

            def predict(self, X: pd.DataFrame) -> np.ndarray:
                return np.array([0, 0])

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_complete_model_can_be_instantiated(self):
        """Verifica que un modelo completo pueda instanciarse."""

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

        model = CompleteModel()
        assert model is not None

    def test_check_fitted_raises_error_if_not_fitted(self):
        """Verifica que check_fitted lance error si el modelo no está entrenado."""
        from energizados.core.exceptions import ModelNotFittedError

        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

        model = ConcreteModel()

        with pytest.raises(ModelNotFittedError, match="no está entrenado"):
            model.check_fitted()

    def test_check_fitted_passes_if_fitted(self):
        """Verifica que check_fitted no lance error si el modelo está entrenado."""

        class ConcreteModel(BaseModel):
            def fit(self, X, y, X_val=None, y_val=None):
                return self

            def predict(self, X):
                return np.array([0])

            def predict_proba(self, X):
                return np.array([0.5])

        model = ConcreteModel()
        model.is_fitted_ = True

        # No debería lanzar excepción
        model.check_fitted()

    def test_fit_accepts_validation_data(self, sample_data):
        """Verifica que fit() acepte datos de validación opcionales."""
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

        model = TestModel()
        model.fit(X, y, X_val=X_val, y_val=y_val)

        assert model.is_fitted_

    def test_fit_without_validation_data(self, sample_data):
        """Verifica que fit() funcione sin datos de validación."""
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

        model = TestModel()
        model.fit(X, y)

        assert model.is_fitted_
