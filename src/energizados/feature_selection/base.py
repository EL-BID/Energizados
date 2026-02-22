"""
Base Feature Selector Module.

Define la clase abstracta BaseFeatureSelector que los usuarios pueden
heredar para implementar sus propios métodos de selección de variables.

This module re-exports BaseFeatureSelector from core for backward compatibility.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

import pandas as pd


class BaseFeatureSelector(ABC):
    """
    Clase base para selección de variables personalizada.

    El usuario hereda e implementa los métodos abstractos para definir
    su propia lógica de selección de features.

    Example:
        >>> from energizados.feature_selection.base import BaseFeatureSelector
        >>> class MySelector(BaseFeatureSelector):
        ...     def fit(self, X, y):
        ...         self.selected_features_ = X.columns[:10].tolist()
        ...         return self
        ...     def transform(self, X):
        ...         return X[self.selected_features_]
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa el selector.

        Args:
            config: Diccionario de configuración opcional
        """
        self.config = config or {}
        self.selected_features_ = None

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeatureSelector":
        """
        Aprende qué variables seleccionar.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento

        Returns:
            self: Retorna la instancia entrenada
        """
        pass

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma X dejando solo las variables seleccionadas.

        Args:
            X: DataFrame a transformar

        Returns:
            pd.DataFrame: DataFrame con variables seleccionadas

        Raises:
            ValueError: Si fit() no fue llamado previamente
        """
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """
        Fit y transform en un paso.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento

        Returns:
            pd.DataFrame: DataFrame transformado
        """
        return self.fit(X, y).transform(X)

    def get_selected_features(self) -> list:
        """
        Retorna la lista de variables seleccionadas.

        Returns:
            list: Lista de nombres de variables seleccionadas

        Raises:
            ValueError: Si fit() no fue llamado previamente
        """
        if self.selected_features_ is None:
            raise ValueError("Debe llamar a fit() primero")
        return self.selected_features_
