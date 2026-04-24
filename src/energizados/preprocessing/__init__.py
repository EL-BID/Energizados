"""
Preprocessing Module for Energizados Framework.

This module provides transformers and utilities for data preprocessing
before analysis and modeling.
"""

from energizados.preprocessing.geo_features import GeoFeatures
from energizados.preprocessing.group_features import (
    GroupRelativeConsumption,
    SeasonalAnomaly,
)
from energizados.preprocessing.isolation_forest_score import IsolationForestScore
from energizados.preprocessing.preprocessing import (
    CardinalityReducer,
    ConsumptionPatterns,
    ExtraVars,
    MinMaxScalerRow,
    TemporalFeatures,
    ToDummy,
    TsfelVars,
    fill_empty_values_cycle,
    fill_empty_values_numeric,
    fill_empty_values_str,
)

__all__ = [
    # Transformation classes
    "ToDummy",
    "CardinalityReducer",
    "MinMaxScalerRow",
    "TsfelVars",
    "ExtraVars",
    "ConsumptionPatterns",
    "TemporalFeatures",
    "GeoFeatures",
    "IsolationForestScore",
    "GroupRelativeConsumption",
    "SeasonalAnomaly",
    # Utility functions
    "fill_empty_values_cycle",
    "fill_empty_values_str",
    "fill_empty_values_numeric",
]
