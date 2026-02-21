"""
Inferencia Personalizada para {{project_name}}.

Este módulo implementa la lógica de inferencia y predicción
específica para este proyecto.

Edita los métodos predict() y predict_proba() según tus necesidades.
"""

from energizados.inference.base import BaseInference
from energizados.core.base import BaseModel
import pandas as pd
import numpy as np


class CustomInference(BaseInference):
    """
    Inferencia personalizada para {{project_name}}.

    Hereda de BaseInference e implementa métodos personalizados
    para cargar modelos y hacer predicciones.
    """

    def __init__(self, model_path: str = None, threshold: float = 0.5, **kwargs):
        """
        Inicializa el motor de inferencia.

        Args:
            model_path: Ruta al archivo del modelo entrenado
            threshold: Umbral para predicciones binarias (default: 0.5)
            **kwargs: Parámetros adicionales
        """
        self.model_path = model_path
        self.threshold = threshold
        self.model = None

    def load_model(self, model_path: str = None) -> BaseModel:
        """
        Carga un modelo entrenado desde archivo.

        Args:
            model_path: Ruta al archivo del modelo

        Returns:
            BaseModel: Modelo cargado
        """
        import pickle

        path = model_path or self.model_path
        if not path:
            raise ValueError("No se especificó ruta del modelo")

        with open(path, "rb") as f:
            self.model = pickle.load(f)

        return self.model

    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones binarias.

        Args:
            model: Modelo entrenado
            data: Datos para predicción

        Returns:
            np.ndarray: Predicciones binarias (0 o 1)
        """
        proba = self.predict_proba(model, data)
        return (proba >= self.threshold).astype(int)

    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones de probabilidad.

        Args:
            model: Modelo entrenado
            data: Datos para predicción

        Returns:
            np.ndarray: Probabilidades de la clase positiva
        """
        return model.predict_proba(data)

    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """
        Guarda predicciones en archivo.

        Args:
            predictions: Predicciones a guardar
            output_path: Ruta de salida
        """
        from pathlib import Path

        import pandas as pd

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"prediction": predictions}).to_csv(output_path, index=False)
