"""
Abstract Base Classes for the Energizados Framework.

This module defines the interfaces that users can implement
to customize the behavior of the framework.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


class BaseModel(ABC):
    """
    Base class for custom models.

    Users inherit and implement abstract methods to define
    their own ML model.

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
        Initialize the model.

        Args:
            config: Optional configuration dictionary
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
        Train the model.

        Args:
            X: Training features
            y: Training target
            X_val: Validation features (optional)
            y_val: Validation target (optional)

        Returns:
            self: Returns the trained instance
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> "np.ndarray":
        """
        Make binary predictions.

        Args:
            X: Features for prediction

        Returns:
            np.ndarray: Binary predictions (0 or 1)

        Raises:
            ModelNotFittedError: If the model is not fitted
        """
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> "np.ndarray":
        """
        Make probability predictions.

        Args:
            X: Features for prediction

        Returns:
            np.ndarray: Probabilities of the positive class

        Raises:
            ModelNotFittedError: If the model is not fitted
        """
        pass

    def check_fitted(self):
        """
        Check that the model is fitted.

        Raises:
            ModelNotFittedError: If the model is not fitted
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)


class BaseInference(ABC):
    """
    Base class for inference and prediction.

    Users can inherit and implement abstract methods
    to define their own inference logic.

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
        Make binary predictions.

        Args:
            model: Trained model
            data: Data for prediction

        Returns:
            np.ndarray: Binary predictions (0 or 1)
        """
        pass

    @abstractmethod
    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            model: Trained model
            data: Data for prediction

        Returns:
            np.ndarray: Probabilities of the positive class
        """
        pass

    def load_model(self, model_path: str) -> BaseModel:
        """
        Load a trained model from disk.

        Args:
            model_path: Path to the model file

        Returns:
            BaseModel: Loaded model
        """
        raise NotImplementedError("Subclasses must implement load_model")

    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """
        Save predictions to file.

        Args:
            predictions: Predictions to save
            output_path: Output path
        """
        raise NotImplementedError("Subclasses must implement save_predictions")


class PipelineStep(ABC):
    """
    Base class for pipeline steps.

    Pipeline steps must inherit from this class and implement
    methods to validate input and execute the step.

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
        Execute the pipeline step.

        Args:
            context: Dictionary with pipeline data

        Returns:
            Dict: Context updated with step results

        Raises:
            PipelineError: If an error occurs during execution
        """
        pass

    @abstractmethod
    def validate_input(self, context: Dict[str, Any]) -> bool:
        """
        Validate that the context has the necessary data.

        Args:
            context: Dictionary with pipeline data

        Returns:
            bool: True if validation is successful, False otherwise
        """
        pass

    def get_required_keys(self) -> list:
        """
        Return the list of required keys in the context.

        This method can be overridden to specify which keys
        are necessary for the step to be able to execute.

        Returns:
            list: List of required key names
        """
        return []

    def get_output_keys(self) -> list:
        """
        Return the list of keys that this step adds to the context.

        This method can be overridden to specify which keys
        this step adds to the context.

        Returns:
            list: List of output key names
        """
        return []
