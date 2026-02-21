"""
Default inference implementation for Energizados Framework.

Implementación por defecto de inferencia que permite cargar modelos,
hacer predicciones y guardar resultados.
"""

import pickle  # nosec: B403 - Standard for ML model serialization in Python ecosystem
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from energizados.core.base import BaseInference, BaseModel


class DefaultInference(BaseInference):
    """
    Implementación por defecto de inferencia.

    Esta clase proporciona funcionalidad estándar para:
    - Cargar modelos entrenados desde archivos pickle
    - Realizar predicciones binarias y de probabilidad
    - Guardar predicciones en archivos CSV

    Args:
        model_path: Ruta al archivo del modelo entrenado
        threshold: Umbral para predicciones binarias (default: 0.5)

    Example:
        >>> from energizados.inference import DefaultInference
        >>> inference = DefaultInference(model_path="models/model.pkl")
        >>> model = inference.load_model()
        >>> predictions = inference.predict(model, data)
    """

    def __init__(self, model_path: Optional[str] = None, threshold: float = 0.5):
        """
        Inicializa el motor de inferencia.

        Args:
            model_path: Ruta al archivo del modelo entrenado
            threshold: Umbral para predicciones binarias (default: 0.5)
        """
        self.model_path = model_path
        self.threshold = threshold
        self.model: Optional[BaseModel] = None

    def load_model(self, model_path: str = None) -> BaseModel:
        """
        Carga un modelo entrenado desde archivo pickle.

        SECURITY NOTE: Only load models from trusted sources. Pickle can execute
        arbitrary code during deserialization. This is the standard method for
        ML model serialization in the Python/scikit-learn ecosystem.

        Args:
            model_path: Ruta al archivo del modelo (usa self.model_path si es None)

        Returns:
            BaseModel: Modelo cargado

        Raises:
            ValueError: Si no se proporciona una ruta válida
            FileNotFoundError: Si el archivo no existe
        """
        path = model_path or self.model_path
        if not path:
            raise ValueError("No model path provided")

        with open(path, "rb") as f:
            self.model = pickle.load(f)  # nosec: B301 - Standard for ML models; ensure trusted source

        return self.model

    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones binarias.

        Convierte las probabilidades en predicciones binarias usando
        el umbral configurado.

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
        Guarda predicciones en archivo CSV.

        Crea el directorio padre si no existe.

        Args:
            predictions: Predicciones a guardar
            output_path: Ruta de salida
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"prediction": predictions}).to_csv(output_path, index=False)

    def save_predictions_with_proba(
        self,
        predictions: np.ndarray,
        probas: np.ndarray,
        output_path: str,
    ) -> None:
        """
        Guarda predicciones binarias y probabilidades en archivo CSV.

        Args:
            predictions: Predicciones binarias
            probas: Probabilidades
            output_path: Ruta de salida
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "prediction": predictions,
                "probability": probas,
            }
        ).to_csv(output_path, index=False)
