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
    MutualInformationSelector,
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
    "MutualInformationSelector",
    "FeatureSelectionPipeline",
    "SelectionStep",
    # Deprecated — kept for backward compatibility but will be removed
    "feature_selection_by_boruta",
    "feature_selection_by_constant",
    "feature_selection_by_correlation",
]
