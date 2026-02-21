"""
Inference Module for Energizados Framework.

Este módulo proporciona clases base e implementaciones
para inferencia y predicción.
"""

from energizados.inference.base import BaseInference
from energizados.inference.default import DefaultInference

__all__ = ["BaseInference", "DefaultInference"]
