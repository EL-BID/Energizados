"""
Inference Module for Energizados Framework.

This module provides base classes and implementations
for inference and prediction.
"""

from energizados.inference.base import BaseInference
from energizados.inference.default import DefaultInference

__all__ = ["BaseInference", "DefaultInference"]
