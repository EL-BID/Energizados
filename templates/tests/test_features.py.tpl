"""
Tests para selección de features de {{project_name}}.
"""

import pytest
import pandas as pd
import numpy as np
from {{project_name}}.src.features.custom_selector import CustomSelector


class TestCustomSelector:
    """Tests para la clase CustomSelector."""

    def test_selector_initialization(self):
        """Verifica que el selector se inicialice correctamente."""
        selector = CustomSelector(config={'threshold': 0.1})
        assert selector.config is not None

    def test_fit_raises_not_implemented(self):
        """Verifica que fit() lance NotImplementedError si no está implementado."""
        selector = CustomSelector()
        X = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        y = pd.Series([0, 1, 1])
        with pytest.raises(NotImplementedError):
            selector.fit(X, y)

    def test_transform_raises_error_before_fit(self):
        """Verifica que transform() falle si no se llamó a fit()."""
        selector = CustomSelector()
        X = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        with pytest.raises(ValueError, match="fit"):
            selector.transform(X)
