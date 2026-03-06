"""
Custom Model for {{project_name}}.

This module implements a specific ML model
for this project.

Edit the fit(), predict() and predict_proba() methods as needed.
"""

from energizados.modeling.base import BaseModel
import pandas as pd
import numpy as np


class CustomModel(BaseModel):
    """
    Custom model for {{project_name}}.

    Inherits from BaseModel and implements the abstract methods
    to define the specific logic for this project.
    """

    def __init__(self, config = None, **kwargs):
        """
        Initialize the model.

        Args:
            config: Configuration dictionary (optional)
            **kwargs: Additional parameters from YAML configuration
        """
        super().__init__(config)
        # Add your custom parameters here
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
        Train the model.

        Edit this method to implement your training logic.

        Args:
            X: Training features
            y: Training target
            X_val: Validation features (optional)
            y_val: Validation target (optional)

        Returns:
            self: Returns the trained instance
        """
        # TODO: Implement your training logic
        # Simple example with scikit-learn:
        # from sklearn.ensemble import RandomForestClassifier
        # self.model_ = RandomForestClassifier(
        #     n_estimators=100,
        #     max_depth=10,
        #     random_state=42
        # )
        # self.model_.fit(X, y)
        # self.is_fitted_ = True

        raise NotImplementedError("Implement the fit() method in your model")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make binary predictions.

        Args:
            X: Features for prediction

        Returns:
            np.ndarray: Binary predictions (0 or 1)
        """
        self.check_fitted()

        # TODO: Implement your prediction logic
        # Example:
        # return self.model_.predict(X).astype(int)

        raise NotImplementedError("Implement the predict() method in your model")

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            X: Features for prediction

        Returns:
            np.ndarray: Probabilities of the positive class
        """
        self.check_fitted()

        # TODO: Implement your probability prediction logic
        # Example:
        # return self.model_.predict_proba(X)[:, 1]

        raise NotImplementedError("Implement the predict_proba() method in your model")
