"""
Clases Base Abstractas para el Framework Energizados.

Este módulo define las interfaces que los usuarios pueden implementar
para personalizar el comportamiento del framework.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


class BaseModel(ABC):
    """
    Clase base para modelos personalizados.

    El usuario hereda e implementa los métodos abstractos para definir
    su propio modelo de ML.

    Example:
        >>> from energizados.core.base import BaseModel
        >>> import numpy as np
        >>> class MyModel(BaseModel):
        ...     def fit(self, X, y, X_val=None, y_val=None):
        ...         self.model_ = SomeClassifier()
        ...         self.model_.fit(X, y)
        ...         self.is_fitted_ = True
        ...         return self
        ...     def predict(self, X):
        ...         return self.model_.predict(X)
        ...     def predict_proba(self, X):
        ...         return self.model_.predict_proba(X)[:, 1]
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa el modelo.

        Args:
            config: Diccionario de configuración opcional
        """
        self.config = config or {}
        self.model_ = None
        self.is_fitted_ = False

    @abstractmethod
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "BaseModel":
        """
        Entrena el modelo.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento
            X_val: Features de validación (opcional)
            y_val: Target de validación (opcional)

        Returns:
            self: Retorna la instancia entrenada
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> "np.ndarray":
        """
        Realiza predicciones binarias.

        Args:
            X: Features para predicción

        Returns:
            np.ndarray: Predicciones binarias (0 o 1)

        Raises:
            ModelNotFittedError: Si el modelo no está entrenado
        """
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> "np.ndarray":
        """
        Realiza predicciones de probabilidad.

        Args:
            X: Features para predicción

        Returns:
            np.ndarray: Probabilidades de la clase positiva

        Raises:
            ModelNotFittedError: Si el modelo no está entrenado
        """
        pass

    def check_fitted(self):
        """
        Verifica que el modelo esté entrenado.

        Raises:
            ModelNotFittedError: Si el modelo no está entrenado
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)


class BaseFeatureSelector(ABC):
    """
    Clase base para selección de variables personalizada.

    El usuario hereda e implementa los métodos abstractos para definir
    su propia lógica de selección de features.

    Example:
        >>> from energizados.core.base import BaseFeatureSelector
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


class BaseInference(ABC):
    """
    Clase base para inferencia y predicción.

    Los usuarios pueden heredar e implementar los métodos abstractos
    para definir su propia lógica de inferencia.

    Example:
        >>> from energizados.core.base import BaseInference, BaseModel
        >>> class MyInference(BaseInference):
        ...     def predict(self, model, data):
        ...         return model.predict(data)
        ...     def predict_proba(self, model, data):
        ...         return model.predict_proba(data)
    """

    @abstractmethod
    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones binarias.

        Args:
            model: Modelo entrenado
            data: Datos para predicción

        Returns:
            np.ndarray: Predicciones binarias (0 o 1)
        """
        pass

    @abstractmethod
    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones de probabilidad.

        Args:
            model: Modelo entrenado
            data: Datos para predicción

        Returns:
            np.ndarray: Probabilidades de la clase positiva
        """
        pass

    def load_model(self, model_path: str) -> BaseModel:
        """
        Carga un modelo entrenado desde disco.

        Args:
            model_path: Ruta al archivo del modelo

        Returns:
            BaseModel: Modelo cargado
        """
        raise NotImplementedError("Subclasses must implement load_model")

    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """
        Guarda predicciones en archivo.

        Args:
            predictions: Predicciones a guardar
            output_path: Ruta de salida
        """
        raise NotImplementedError("Subclasses must implement save_predictions")


class PipelineStep(ABC):
    """
    Clase base para pasos del pipeline.

    Los pasos del pipeline deben heredar de esta clase e implementar
    los métodos para validar la entrada y ejecutar el paso.

    Example:
        >>> from energizados.core.base import PipelineStep
        >>> class MyStep(PipelineStep):
        ...     def validate_input(self, context):
        ...         return 'data' in context
        ...     def execute(self, context):
        ...         context['result'] = process(context['data'])
        ...         return context
    """

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta el paso del pipeline.

        Args:
            context: Diccionario con datos del pipeline

        Returns:
            Dict: Contexto actualizado con los resultados del paso

        Raises:
            PipelineError: Si ocurre un error durante la ejecución
        """
        pass

    @abstractmethod
    def validate_input(self, context: Dict[str, Any]) -> bool:
        """
        Valida que el contexto tenga los datos necesarios.

        Args:
            context: Diccionario con datos del pipeline

        Returns:
            bool: True si la validación es exitosa, False en caso contrario
        """
        pass

    def get_required_keys(self) -> list:
        """
        Retorna la lista de claves requeridas en el contexto.

        Este método puede sobrescribirse para especificar qué claves
        son necesarias para que el paso pueda ejecutarse.

        Returns:
            list: Lista de nombres de claves requeridas
        """
        return []

    def get_output_keys(self) -> list:
        """
        Retorna la lista de claves que este paso agrega al contexto.

        Este método puede sobrescribirse para especificar qué claves
        agrega este paso al contexto.

        Returns:
            list: Lista de nombres de claves de salida
        """
        return []
