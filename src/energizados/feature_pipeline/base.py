"""
Base Feature Pipeline Module.

Define la clase abstracta BaseFeaturePipeline que los usuarios pueden
heredar para implementar sus propios pipelines de características.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class BaseFeaturePipeline(ABC):
    """
    Clase base para pipeline de características personalizado.

    El usuario hereda e implementa los métodos abstractos para definir
    su propia lógica de preprocessing y feature selection.

    Combina ambas operaciones en un solo paso para mayor eficiencia
    y mejor manejo del estado del pipeline.

    Example:
        >>> from energizados.feature_pipeline.base import BaseFeaturePipeline
        >>> import pandas as pd
        >>> class MyFeaturePipeline(BaseFeaturePipeline):
        ...     def __init__(self):
        ...         self.scaler = StandardScaler()
        ...         self.selector = SelectKBest(k=10)
        ...
        ...     def fit(self, X, y):
        ...         X_prep = self._preprocess(X)
        ...         X_scaled = self.scaler.fit_transform(X_prep)
        ...         self.selector.fit(X_scaled, y)
        ...         return self
        ...
        ...     def transform(self, X):
        ...         X_prep = self._preprocess(X)
        ...         X_scaled = self.scaler.transform(X_prep)
        ...         return self.selector.transform(X_scaled)
        ...
        ...     def save(self, path):
        ...         import pickle
        ...         with open(path, 'wb') as f:
        ...             pickle.dump(self, f)
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa el pipeline de características.

        Args:
            config: Diccionario de configuración opcional
        """
        self.config = config or {}
        self.is_fitted_ = False

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeaturePipeline":
        """
        Aprende las transformaciones de preprocessing y feature selection.

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
        Aplica preprocessing y feature selection a los datos.

        Args:
            X: DataFrame a transformar

        Returns:
            pd.DataFrame: DataFrame transformado

        Raises:
            ValueError: Si fit() no fue llamado previamente
        """
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """
        Fit y transform en un solo paso.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento

        Returns:
            pd.DataFrame: DataFrame transformado
        """
        return self.fit(X, y).transform(X)

    def save(self, path: str) -> None:
        """
        Guarda el pipeline completo en disco.

        Guarda todo el estado del pipeline incluyendo preprocesadores
        y selectores entrenados para su uso posterior.

        Args:
            path: Ruta donde guardar el pipeline (extension .pkl)

        Raises:
            ValueError: Si fit() no fue llamado previamente
        """
        if not self.is_fitted_:
            raise ValueError("Debe llamar a fit() antes de guardar el pipeline")

        import pickle  # nosec: B403 - pickle usado solo para datos internos del usuario

        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump(self, f)  # nosec: B301 - pickle usado solo para datos internos

        logger.info(f"Feature pipeline guardado en: {path}")

    @classmethod
    def load(cls, path: str) -> "BaseFeaturePipeline":
        """
        Carga un pipeline guardado desde disco.

        Args:
            path: Ruta al archivo del pipeline guardado

        Returns:
            BaseFeaturePipeline: Pipeline cargado
        """
        import pickle  # nosec: B403 - pickle usado solo para datos internos del usuario

        with open(path, "rb") as f:
            pipeline = pickle.load(f)  # nosec: B301 - pickle usado solo para datos internos

        logger.info(f"Feature pipeline cargado desde: {path}")
        return pipeline

    def get_feature_names_out(self) -> list:
        """
        Retorna los nombres de las features después de las transformaciones.

        Returns:
            list: Lista de nombres de features de salida

        Raises:
            ValueError: Si fit() no fue llamado previamente
        """
        if not self.is_fitted_:
            raise ValueError("Debe llamar a fit() primero")
        return self._get_feature_names_out()

    def _get_feature_names_out(self) -> list:
        """
        Método interno para obtener los nombres de features.

        Puede ser sobrescrito por subclases.

        Returns:
            list: Lista de nombres de features
        """
        return []

    def check_fitted(self) -> None:
        """
        Verifica que el pipeline esté entrenado.

        Raises:
            ValueError: Si el pipeline no está entrenado
        """
        if not self.is_fitted_:
            raise ValueError(f"{self.__class__.__name__} no está entrenado. Llame a fit() primero.")
