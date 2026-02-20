"""
Feature Selection Module for Energizados Framework.

Este módulo proporciona clases base e implementaciones
para selección de características.
"""

from energizados.preprocessing.feature_selection.base import BaseFeatureSelector
from energizados.preprocessing.feature_selection.methods import (
    BorutaSelector,
    ConstantSelector,
    CorrelationSelector,
)

__all__ = [
    "BaseFeatureSelector",
    "BorutaSelector",
    "ConstantSelector",
    "CorrelationSelector",
]
