"""
Feature Engineering Module for Energizados Framework.

Este módulo combina preprocessing y feature_selection en un solo paso,
permitiendo transformaciones más eficientes y un manejo unificado del
pipeline de características.
"""

from energizados.feature_engineering.base import BaseFeatureEngineering
from energizados.feature_engineering.default import DefaultFeatureEngineering

__all__ = [
    "BaseFeatureEngineering",
    "DefaultFeatureEngineering",
]
