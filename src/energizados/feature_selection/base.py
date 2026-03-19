"""
Base Feature Selector Module.

Defines the BaseFeatureSelector abstract class that users can
inherit to implement their own feature selection methods.

This module re-exports BaseFeatureSelector from core for backward compatibility.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

import pandas as pd


class BaseFeatureSelector(ABC):
    """
    Base class for custom feature selection.

    Users inherit and implement the abstract methods to define
    their own feature selection logic.

    Example:
        >>> from energizados.feature_selection.base import BaseFeatureSelector
        >>> class MySelector(BaseFeatureSelector):
        ...     def fit(self, X, y):
        ...         self.selected_features_ = X.columns[:10].tolist()
        ...         return self
        ...     def transform(self, X):
        ...         return X[self.selected_features_]
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the selector.

        Args:
            config: Optional configuration dictionary.
        """
        self.config = config or {}
        self.selected_features_ = None

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeatureSelector":
        """
        Learn which features to select.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            self: The fitted instance.
        """
        pass

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform X keeping only the selected features.

        Args:
            X: DataFrame to transform.

        Returns:
            pd.DataFrame: DataFrame with selected features.

        Raises:
            ValueError: If fit() has not been called previously.
        """
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """
        Fit and transform in one step.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            pd.DataFrame: Transformed DataFrame.
        """
        return self.fit(X, y).transform(X)

    def get_selected_features(self) -> list:
        """
        Return the list of selected features.

        Returns:
            list: List of selected feature names.

        Raises:
            ValueError: If fit() has not been called previously.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return self.selected_features_

    def get_audit_stats(self) -> Dict:
        """
        Return audit statistics for the selector.

        Subclasses should override this method to provide selector-specific
        statistics such as vote counts, dropped features, scores, etc.

        Raises:
            ValueError: If fit() has not been called previously.

        Returns:
            Dict: Selector-specific stats. Subclasses return relevant stats.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return {}
