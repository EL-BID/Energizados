"""
Feature Pipeline Module for Energizados Framework.

Este módulo combina preprocessing y feature_selection en un solo paso,
permitiendo transformaciones más eficientes y un manejo unificado del
pipeline de características.
"""

from energizados.feature_pipeline.base import BaseFeaturePipeline
from energizados.feature_pipeline.default import DefaultFeaturePipeline

__all__ = ["BaseFeaturePipeline", "DefaultFeaturePipeline"]
