"""
Unit tests for BaseFeatureSelector.

Pruebas para la clase base de Feature Selection que define la interfaz
que deben implementar todos los selectores personalizados.
"""

import pandas as pd
import pytest

from energizados.feature_selection.base import BaseFeatureSelector


class TestBaseFeatureSelector:
    """Tests para la clase BaseFeatureSelector."""

    @pytest.fixture
    def sample_data(self):
        """Retorna datos de ejemplo para pruebas."""
        X = pd.DataFrame(
            {
                "feature1": [1, 2, 3, 4, 5],
                "feature2": [2, 4, 6, 8, 10],
                "feature3": [1, 1, 1, 1, 1],  # Constante
                "feature4": [5, 4, 3, 2, 1],
            }
        )
        y = pd.Series([0, 0, 1, 1, 1])
        return X, y

    def test_base_selector_has_config(self):
        """Verifica que BaseFeatureSelector acepte config."""

        # Crear implementación concreta mínima para testear config
        class ConcreteSelector(BaseFeatureSelector):
            def fit(self, X, y):
                return self

            def transform(self, X):
                return X

        selector = ConcreteSelector(config={"threshold": 0.5})
        assert selector.config == {"threshold": 0.5}

    def test_base_selector_default_config(self):
        """Verifica que BaseFeatureSelector use config vacío por defecto."""

        class ConcreteSelector(BaseFeatureSelector):
            def fit(self, X, y):
                return self

            def transform(self, X):
                return X

        selector = ConcreteSelector()
        assert selector.config == {}

    def test_base_selector_initialized_with_selected_features(self):
        """Verifica que selected_features_ se inicialice como None."""

        class ConcreteSelector(BaseFeatureSelector):
            def fit(self, X, y):
                return self

            def transform(self, X):
                return X

        selector = ConcreteSelector()
        assert selector.selected_features_ is None

    def test_concrete_selector_must_implement_fit(self):
        """Verifica que un selector deba implementar fit()."""

        class IncompleteSelector(BaseFeatureSelector):
            def transform(self, X: pd.DataFrame) -> pd.DataFrame:
                return X

        with pytest.raises(TypeError):
            IncompleteSelector()

    def test_concrete_selector_must_implement_transform(self):
        """Verifica que un selector deba implementar transform()."""

        class IncompleteSelector(BaseFeatureSelector):
            def fit(self, X: pd.DataFrame, y: pd.Series):
                return self

        with pytest.raises(TypeError):
            IncompleteSelector()

    def test_complete_selector_can_be_instantiated(self):
        """Verifica que un selector completo pueda instanciarse."""

        class CompleteSelector(BaseFeatureSelector):
            def fit(self, X: pd.DataFrame, y: pd.Series):
                self.selected_features_ = ["feature1", "feature2"]
                return self

            def transform(self, X: pd.DataFrame) -> pd.DataFrame:
                return X[self.selected_features_]

        selector = CompleteSelector()
        assert selector is not None

    def test_fit_transform_method(self, sample_data):
        """Verifica que fit_transform funcione correctamente."""
        X, y = sample_data

        class TestSelector(BaseFeatureSelector):
            def fit(self, X: pd.DataFrame, y: pd.Series):
                self.selected_features_ = ["feature1", "feature2"]
                return self

            def transform(self, X: pd.DataFrame) -> pd.DataFrame:
                return X[self.selected_features_]

        selector = TestSelector()
        result = selector.fit_transform(X, y)

        expected = pd.DataFrame({"feature1": [1, 2, 3, 4, 5], "feature2": [2, 4, 6, 8, 10]})
        pd.testing.assert_frame_equal(result, expected)

    def test_get_selected_features_raises_error_if_not_fitted(self):
        """Verifica que get_selected_features lance error si no se llamó a fit."""

        class ConcreteSelector(BaseFeatureSelector):
            def fit(self, X, y):
                return self

            def transform(self, X):
                return X

        selector = ConcreteSelector()

        with pytest.raises(ValueError, match="Debe llamar a fit"):
            selector.get_selected_features()

    def test_get_selected_features_returns_features(self, sample_data):
        """Verifica que get_selected_features retorne las features seleccionadas."""
        X, y = sample_data

        class TestSelector(BaseFeatureSelector):
            def fit(self, X: pd.DataFrame, y: pd.Series):
                self.selected_features_ = ["feature1", "feature4"]
                return self

            def transform(self, X: pd.DataFrame) -> pd.DataFrame:
                return X[self.selected_features_]

        selector = TestSelector()
        selector.fit(X, y)

        features = selector.get_selected_features()
        assert features == ["feature1", "feature4"]
