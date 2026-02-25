"""
Preprocessing Module for Energizados Framework.

Este módulo proporciona transformadores y utilidades para el preprocesamiento
de datos antes del análisis y modelado.
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
    # Clases de transformación
    "ToDummy",
    "CardinalityReducer",
    "MinMaxScalerRow",
    "TsfelVars",
    "ExtraVars",
    # Funciones de utilidad
    "fill_empty_values_cycle",
    "fill_empty_values_str",
    "fill_empty_values_numeric",
    "build_feature_engineering_pipeline",
]
