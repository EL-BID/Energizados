"""
Feature Selection Module for Energizados Framework.

Este módulo proporciona clases base e implementaciones
para selección de características.
"""

from energizados.feature_selection.base import BaseFeatureSelector
from energizados.feature_selection.methods import (
    BorutaSelector,
    ConstantSelector,
    CorrelationSelector,
    feature_selection_by_boruta,
    feature_selection_by_constant,
    feature_selection_by_correlation,
)

__all__ = [
    "BaseFeatureSelector",
    "BorutaSelector",
    "ConstantSelector",
    "CorrelationSelector",
    # Funciones legacy para compatibilidad
    "feature_selection_by_correlation",
    "feature_selection_by_constant",
    "feature_selection_by_boruta",
]
