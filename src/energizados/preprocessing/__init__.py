"""
Preprocessing Module for Energizados Framework.

This module provides transformers and utilities for data preprocessing
before analysis and modeling.
"""

from energizados.preprocessing.preprocessing import (
    CardinalityReducer,
    ExtraVars,
    MinMaxScalerRow,
    ToDummy,
    TsfelVars,
    build_feature_engineering_pipeline,
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
    # Utility functions
    "fill_empty_values_cycle",
    "fill_empty_values_str",
    "fill_empty_values_numeric",
    "build_feature_engineering_pipeline",
]
