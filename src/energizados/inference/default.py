"""
Default inference implementation for Energizados Framework.

Default inference implementation that allows loading models,
making predictions, and saving results.
"""

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from energizados.core.base import BaseInference, BaseModel


class DefaultInference(BaseInference):
    """
    Default inference implementation.

    This class provides standard functionality for:
    - Loading trained models from pickle files
    - Making binary and probability predictions
    - Saving predictions to CSV files

    Args:
        model_path: Path to the trained model file.
        threshold: Threshold for binary predictions (default: 0.5).

    Example:
        >>> from energizados.inference import DefaultInference
        >>> inference = DefaultInference(model_path="models/model.pkl")
        >>> model = inference.load_model()
        >>> predictions = inference.predict(model, data)
    """

    def __init__(self, model_path: Optional[str] = None, threshold: float = 0.5):
        """
        Initialize the inference engine.

        Args:
            model_path: Path to the trained model file.
            threshold: Threshold for binary predictions (default: 0.5).
        """
        self.model_path = model_path
        self.threshold = threshold
        self.model: Optional[BaseModel] = None

    def load_model(self, model_path: str = None) -> BaseModel:
        """
        Load a trained model from a pickle file.

        SECURITY NOTE: Only load models from trusted sources. Pickle can execute
        arbitrary code during deserialization. This is the standard method for
        ML model serialization in the Python/scikit-learn ecosystem.

        Args:
            model_path: Path to the model file (uses self.model_path if None).

        Returns:
            BaseModel: The loaded model.

        Raises:
            ValueError: If no valid path is provided.
            FileNotFoundError: If the file does not exist.
        """
        from energizados.core.utils.secure_pickle import secure_load

        path = model_path or self.model_path
        if not path:
            raise ValueError("No model path provided")

        self.model = secure_load(path)
        return self.model

    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Make binary predictions.

        Converts probabilities to binary predictions using the configured threshold.

        Args:
            model: Trained model.
            data: Data for prediction.

        Returns:
            np.ndarray: Binary predictions (0 or 1).
        """
        proba = self.predict_proba(model, data)
        return (proba >= self.threshold).astype(int)

    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            model: Trained model.
            data: Data for prediction.

        Returns:
            np.ndarray: Probabilities of the positive class.
        """
        return model.predict_proba(data)

    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """
        Save predictions to a CSV file.

        Creates the parent directory if it does not exist.

        Args:
            predictions: Predictions to save.
            output_path: Output path.
        """
        from energizados.core.utils.secure_pickle import validate_no_traversal

        validate_no_traversal(output_path, label="inference output_path")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"prediction": predictions}).to_csv(output_path, index=False)

    def save_predictions_with_proba(
        self,
        predictions: np.ndarray,
        probas: np.ndarray,
        output_path: str,
    ) -> None:
        """
        Save binary predictions and probabilities to a CSV file.

        Args:
            predictions: Binary predictions.
            probas: Probabilities.
            output_path: Output path.
        """
        from energizados.core.utils.secure_pickle import validate_no_traversal

        validate_no_traversal(output_path, label="inference output_path")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "prediction": predictions,
                "probability": probas,
            }
        ).to_csv(output_path, index=False)


def apply_segment_thresholds(
    probas: np.ndarray,
    segment_values: pd.Series,
    thresholds_dict: Dict[str, float],
    fallback_threshold: float,
) -> np.ndarray:
    """Apply per-segment thresholds to probability predictions.

    Maps each row's segment value to its specific threshold from thresholds_dict.
    Rows with unknown segment values use the fallback_threshold.

    Args:
        probas: Array of predicted probabilities (positive class).
        segment_values: Series containing segment value for each row.
        thresholds_dict: Dictionary mapping segment values to their thresholds.
        fallback_threshold: Threshold to use for segment values not in thresholds_dict.

    Returns:
        np.ndarray: Binary predictions (0 or 1) based on per-row thresholds.

    Example:
        >>> probas = np.array([0.4, 0.6, 0.3])
        >>> segments = pd.Series(["Norte", "Sul", "Norte"])
        >>> thresholds = {"Norte": 0.3, "Sul": 0.7}
        >>> apply_segment_thresholds(probas, segments, thresholds, 0.5)
        array([1, 0, 0])  # Norte: 0.4>=0.3->1, 0.3<0.3->0; Sul: 0.6<0.7->0
    """
    # Map each row's segment value to its threshold
    row_thresholds = segment_values.map(lambda x: thresholds_dict.get(x, fallback_threshold))

    # Apply per-row thresholds to get binary predictions
    predictions = (probas >= row_thresholds.values).astype(int)

    return predictions
