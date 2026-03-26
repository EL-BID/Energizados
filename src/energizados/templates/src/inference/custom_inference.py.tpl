"""
Custom Inference for {{project_name}}.

This module implements specific inference and prediction logic
for this project.

Edit the predict() and predict_proba() methods as needed.
"""

from energizados.inference.base import BaseInference
from energizados.core.base import BaseModel
import pandas as pd
import numpy as np


class CustomInference(BaseInference):
    """
    Custom inference for {{project_name}}.

    Inherits from BaseInference and implements custom methods
    to load models and make predictions.
    """

    def __init__(self, model_path: str = None, threshold: float = 0.5, **kwargs):
        """
        Initialize the inference engine.

        Args:
            model_path: Path to the trained model file
            threshold: Threshold for binary predictions (default: 0.5)
            **kwargs: Additional parameters
        """
        self.model_path = model_path
        self.threshold = threshold
        self.model = None

    def load_model(self, model_path: str = None) -> BaseModel:
        """
        Load a trained model from file.

        Args:
            model_path: Path to the model file

        Returns:
            BaseModel: Loaded model
        """
        import pickle

        path = model_path or self.model_path
        if not path:
            raise ValueError("Model path not specified")

        with open(path, "rb") as f:
            self.model = pickle.load(f)

        return self.model

    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Make binary predictions.

        Args:
            model: Trained model
            data: Data for prediction

        Returns:
            np.ndarray: Binary predictions (0 or 1)
        """
        proba = self.predict_proba(model, data)
        return (proba >= self.threshold).astype(int)

    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            model: Trained model
            data: Data for prediction

        Returns:
            np.ndarray: Probabilities of the positive class
        """
        return model.predict_proba(data)

    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """
        Save predictions to file.

        Args:
            predictions: Predictions to save
            output_path: Output path
        """
        from pathlib import Path

        import pandas as pd

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"prediction": predictions}).to_csv(output_path, index=False)
