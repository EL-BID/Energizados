"""
Custom Feature Selector for {{project_name}}.

This module implements specific feature selection logic
for this project.

Edit the fit() and transform() methods as needed.
"""

from energizados.feature_selection.base import BaseFeatureSelector
import pandas as pd


class CustomSelector(BaseFeatureSelector):
    """
    Custom feature selector for {{project_name}}.

    Inherits from BaseFeatureSelector and implements the abstract methods
    to define the specific logic for this project.
    """

    def __init__(self, config = None, **kwargs):
        """
        Initialize the selector.

        Args:
            config: Configuration dictionary (optional)
            **kwargs: Additional parameters from YAML configuration
        """
        super().__init__(config)
        # Add your custom parameters here
        # self.threshold = config.get('threshold', 0.01) if config else 0.01

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "CustomSelector":
        """
        Learn which features to select.

        Edit this method to implement your selection logic.

        Args:
            X: Training features
            y: Training target

        Returns:
            self: Returns the trained instance
        """
        # TODO: Implement your selection logic
        # Simple example with variance:
        # from sklearn.feature_selection import VarianceThreshold
        # selector = VarianceThreshold(threshold=0.01)
        # selector.fit(X)
        # self.selected_features_ = X.columns[selector.get_support()].tolist()

        # Example with correlation:
        # corr_matrix = X.corr().abs()
        # upper_triangle = corr_matrix.where(
        #     np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        # )
        # to_drop = [column for column in upper_triangle.columns if any(upper_triangle[column] > 0.95)]
        # self.selected_features_ = [col for col in X.columns if col not in to_drop]

        raise NotImplementedError("Implement the fit() method in your selector")

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform X keeping only selected features.

        Args:
            X: DataFrame to transform

        Returns:
            pd.DataFrame: DataFrame with selected features
        """
        if self.selected_features_ is None:
            raise ValueError("You must call fit() before transform()")

        return X[self.selected_features_]
