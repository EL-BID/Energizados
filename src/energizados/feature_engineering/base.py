"""
Base Feature Engineering Module.

Defines the abstract BaseFeatureEngineering class that users can
inherit to implement their own feature pipelines.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class BaseFeatureEngineering(ABC):
    """Base class for custom feature engineering.

    Users inherit and implement abstract methods to define their own
    preprocessing and feature selection logic.

    Combines both operations in a single step for greater efficiency
    and better pipeline state management.

    Example:
        >>> from energizados.feature_engineering.base import BaseFeatureEngineering
        >>> import pandas as pd
        >>> class MyFeatureEngineering(BaseFeatureEngineering):
        ...     def __init__(self):
        ...         self.scaler = StandardScaler()
        ...         self.selector = SelectKBest(k=10)
        ...
        ...     def fit(self, X, y):
        ...         X_prep = self._preprocess(X)
        ...         X_scaled = self.scaler.fit_transform(X_prep)
        ...         self.selector.fit(X_scaled, y)
        ...         return self
        ...
        ...     def transform(self, X):
        ...         X_prep = self._preprocess(X)
        ...         X_scaled = self.scaler.transform(X_prep)
        ...         return self.selector.transform(X_scaled)
        ...
        ...     def save(self, path):
        ...         import pickle
        ...         with open(path, 'wb') as f:
        ...             pickle.dump(self, f)
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initializes the feature pipeline.

        Args:
            config: Optional configuration dictionary.
        """
        self.config = config or {}
        self.is_fitted_ = False

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeatureEngineering":
        """Learns preprocessing and feature selection transformations.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            self: Returns the trained instance.
        """
        pass

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Applies preprocessing and feature selection to data.

        Args:
            X: DataFrame to transform.

        Returns:
            pd.DataFrame: Transformed DataFrame.

        Raises:
            ValueError: If fit() was not called previously.
        """
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """Fit and transform in a single step.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            pd.DataFrame: Transformed DataFrame.
        """
        return self.fit(X, y).transform(X)

    def save(self, path: str) -> None:
        """Saves the complete pipeline to disk.

        Saves the entire pipeline state including preprocessors
        and trained selectors for later use.

        Args:
            path: Path where to save the pipeline (.pkl extension).

        Raises:
            ValueError: If fit() was not called previously.
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)

        from energizados.core.utils.secure_pickle import secure_dump

        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        secure_dump(self, path)
        logger.info(f"Feature engineering saved to: {path}")

    @classmethod
    def load(cls, path: str) -> "BaseFeatureEngineering":
        """Loads a saved pipeline from disk.

        Args:
            path: Path to the saved pipeline file.

        Returns:
            BaseFeatureEngineering: Loaded pipeline.
        """
        from energizados.core.utils.secure_pickle import secure_load

        pipeline = secure_load(path)
        logger.info(f"Feature engineering loaded from: {path}")
        return pipeline

    def get_feature_names_out(self) -> list:
        """Returns feature names after transformations.

        Returns:
            list: List of output feature names.

        Raises:
            ValueError: If fit() was not called previously.
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)
        return self._get_feature_names_out()

    def _get_feature_names_out(self) -> list:
        """Internal method to get feature names.

        Can be overridden by subclasses.

        Returns:
            list: List of feature names.
        """
        return []

    def check_fitted(self) -> None:
        """Verifies the pipeline is trained.

        Raises:
            ValueError: If the pipeline is not trained.
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)
