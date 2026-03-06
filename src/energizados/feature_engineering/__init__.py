"""
Feature Engineering Module for Energizados Framework.

This module combines preprocessing and feature_selection in a single step,
allowing more efficient transformations and unified management of the
feature pipeline.
"""

from energizados.feature_engineering.base import BaseFeatureEngineering
from energizados.feature_engineering.default import DefaultFeatureEngineering

__all__ = [
    "BaseFeatureEngineering",
    "DefaultFeatureEngineering",
]
