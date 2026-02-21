"""
Base Feature Selector Module.

Define la clase abstracta BaseFeatureSelector que los usuarios pueden
heredar para implementar sus propios métodos de selección de variables.

This module re-exports BaseFeatureSelector from core for backward compatibility.
"""

from energizados.core.base import BaseFeatureSelector

__all__ = ["BaseFeatureSelector"]
