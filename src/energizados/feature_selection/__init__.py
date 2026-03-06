"""
Feature Selection Module for Energizados Framework.

This module provides base classes and implementations
for feature selection.
"""

from energizados.feature_selection.base import BaseFeatureSelector
from energizados.feature_selection.column_resolver import ColumnResolver
from energizados.feature_selection.methods import (
    BorutaSelector,
    ConstantSelector,
    CorrelationSelector,
    feature_selection_by_boruta,
    feature_selection_by_constant,
    feature_selection_by_correlation,
)
from energizados.feature_selection.pipeline import (
    FeatureSelectionPipeline,
    SelectionStep,
)

__all__ = [
    "BaseFeatureSelector",
    "BorutaSelector",
    "ColumnResolver",
    "ConstantSelector",
    "CorrelationSelector",
    "FeatureSelectionPipeline",
    "SelectionStep",
    # Legacy functions for backward compatibility
    "feature_selection_by_correlation",
    "feature_selection_by_constant",
    "feature_selection_by_boruta",
]
