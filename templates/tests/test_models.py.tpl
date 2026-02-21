"""
Tests para modelos de {{project_name}}.
"""

import pytest
import pandas as pd
import numpy as np
from {{project_name}}.src.models.custom_model import CustomModel


class TestCustomModel:
    """Tests para la clase CustomModel."""

    def test_model_initialization(self):
        """Verifica que el modelo se inicialice correctamente."""
        model = CustomModel(config={'learning_rate': 0.01})
        assert model.config is not None
        assert not model.is_fitted_

    def test_fit_raises_not_implemented(self):
        """Verifica que fit() lance NotImplementedError si no está implementado."""
        model = CustomModel()
        X = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        y = pd.Series([0, 1, 1])
        with pytest.raises(NotImplementedError):
            model.fit(X, y)

    def test_predict_raises_error_before_fit(self):
        """Verifica que predict() falle si el modelo no está entrenado."""
        model = CustomModel()
        X = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        with pytest.raises(ValueError, match="entrenado"):
            model.predict(X)

    def test_predict_proba_raises_error_before_fit(self):
        """Verifica que predict_proba() falle si el modelo no está entrenado."""
        model = CustomModel()
        X = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        with pytest.raises(ValueError, match="entrenado"):
            model.predict_proba(X)
