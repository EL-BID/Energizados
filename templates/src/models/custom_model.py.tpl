"""
Modelo Personalizado para {{project_name}}.

Este módulo implementa un modelo de ML
específico para este proyecto.

Edita los métodos fit(), predict() y predict_proba() según tus necesidades.
"""

from energizados.modeling.base import BaseModel
import pandas as pd
import numpy as np


class CustomModel(BaseModel):
    """
    Modelo personalizado para {{project_name}}.

    Hereda de BaseModel e implementa los métodos abstractos
    para definir la lógica específica de este proyecto.
    """

    def __init__(self, config = None, **kwargs):
        """
        Inicializa el modelo.

        Args:
            config: Diccionario de configuración (opcional)
            **kwargs: Parámetros adicionales desde la configuración YAML
        """
        super().__init__(config)
        # Agrega tus parámetros personalizados aquí
        # self.learning_rate = config.get('learning_rate', 0.01) if config else 0.01
        self.model_ = None
        self.is_fitted_ = False

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None
    ) -> "CustomModel":
        """
        Entrena el modelo.

        Edita este método para implementar tu lógica de entrenamiento.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento
            X_val: Features de validación (opcional)
            y_val: Target de validación (opcional)

        Returns:
            self: Retorna la instancia entrenada
        """
        # TODO: Implementar tu lógica de entrenamiento
        # Ejemplo simple con scikit-learn:
        # from sklearn.ensemble import RandomForestClassifier
        # self.model_ = RandomForestClassifier(
        #     n_estimators=100,
        #     max_depth=10,
        #     random_state=42
        # )
        # self.model_.fit(X, y)
        # self.is_fitted_ = True

        raise NotImplementedError("Implementa el método fit() en tu modelo")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones binarias.

        Args:
            X: Features para predicción

        Returns:
            np.ndarray: Predicciones binarias (0 o 1)
        """
        self.check_fitted()

        # TODO: Implementar tu lógica de predicción
        # Ejemplo:
        # return self.model_.predict(X).astype(int)

        raise NotImplementedError("Implementa el método predict() en tu modelo")

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones de probabilidad.

        Args:
            X: Features para predicción

        Returns:
            np.ndarray: Probabilidades de la clase positiva
        """
        self.check_fitted()

        # TODO: Implementar tu lógica de predicción de probabilidades
        # Ejemplo:
        # return self.model_.predict_proba(X)[:, 1]

        raise NotImplementedError("Implementa el método predict_proba() en tu modelo")
