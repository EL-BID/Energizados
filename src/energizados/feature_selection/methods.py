"""
Feature Selection Methods for Energizados Framework.

Implementations of feature selection methods based on
the existing project code.
"""

import logging
from typing import Optional, Union

import numpy as np
import pandas as pd
from boruta import BorutaPy
from sklearn.ensemble import RandomForestClassifier
from tqdm import tqdm

from energizados.feature_selection.base import BaseFeatureSelector

logger = logging.getLogger(__name__)


class CorrelationSelector(BaseFeatureSelector):
    """
    Feature selector based on correlation.

    Removes highly correlated variables, keeping the one with
    the highest correlation with the target.

    Args:
        method: Correlation method ('pearson', 'spearman', 'kendall').
        threshold: Correlation threshold for removing variables (default: 0.9).
    """

    def __init__(
        self,
        method: str = "pearson",
        threshold: float = 0.9,
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.method = method
        self.threshold = threshold
        self.vars_to_drop_ = None

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: pd.Series) -> "CorrelationSelector":
        """
        Learn which variables to remove due to high correlation.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            self: The fitted instance.
        """
        # Convert numpy array to DataFrame if needed
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        # Filter out non-numeric columns (datetime, object, etc.)
        X = X.select_dtypes(include=[np.number])
        logger.info(f"Filtered to {X.shape[1]} numeric columns for correlation analysis")

        X = X.copy()
        variables = X.columns.tolist()

        logger.info("Calculating Correlation Between Variables")
        X["target"] = y.values
        df_corr = X[variables + ["target"]].corr(method=self.method)

        # Find most correlated variables
        vars_to_drop_corr = []
        for x in variables:
            for y_var in variables:
                if x != y_var:
                    c_value = df_corr[x][y_var]
                    if np.abs(c_value) > self.threshold:
                        corr_x_t = np.abs(df_corr[x]["target"])
                        corr_y_t = np.abs(df_corr[y_var]["target"])
                        if corr_x_t > corr_y_t:
                            vars_to_drop_corr.append(y_var)

        self.vars_to_drop_ = list(set(vars_to_drop_corr))
        self.selected_features_ = [v for v in variables if v not in self.vars_to_drop_]

        logger.info(f"Removing {len(self.vars_to_drop_)} Highly Correlated Variables")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform X by removing correlated variables.

        Args:
            X: DataFrame to transform.

        Returns:
            pd.DataFrame: DataFrame without highly correlated variables.

        Raises:
            ValueError: If fit() has not been called previously.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return X[self.selected_features_].copy()


class ConstantSelector(BaseFeatureSelector):
    """
    Selector that removes variables with constant values.

    Removes variables where a single value represents more than
    the specified percentage of rows.

    Args:
        threshold: Variability threshold (default: 0.99).
                   A variable is removed if a value represents
                   more than this percentage of rows.
    """

    def __init__(self, threshold: float = 0.99, config: Optional[dict] = None):
        super().__init__(config)
        self.threshold = threshold
        self.vars_to_drop_ = None

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: pd.Series) -> "ConstantSelector":
        """
        Learn which variables are constant.

        Args:
            X: Training features.
            y: Training target (not used in this method).

        Returns:
            self: The fitted instance.
        """
        # Convert numpy array to DataFrame if needed
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        # Filter out non-numeric columns (datetime, object, etc.)
        X = X.select_dtypes(include=[np.number])
        logger.info(f"Filtered to {X.shape[1]} numeric columns for constant detection")

        num_rows = X.shape[0]
        all_labels = X.columns.tolist()

        constant_per_feature = {label: X[label].value_counts().iloc[0] / num_rows for label in all_labels}

        self.vars_to_drop_ = [label for label in all_labels if constant_per_feature[label] > self.threshold]
        self.selected_features_ = [x for x in all_labels if x not in self.vars_to_drop_]

        logger.info(f"Removing {len(self.vars_to_drop_)} Constant Variables")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform X by removing constant variables.

        Args:
            X: DataFrame to transform.

        Returns:
            pd.DataFrame: DataFrame without constant variables.

        Raises:
            ValueError: If fit() has not been called previously.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return X[self.selected_features_].copy()


class BorutaSelector(BaseFeatureSelector):
    """
    Feature selector using the Boruta algorithm.

    Boruta is a feature selection algorithm that compares the importance
    of original variables with random variables ("shadow features") to
    determine which are truly important.

    Args:
        n_estimators: Number of trees in the RandomForest.
        max_depth: Maximum depth of the trees.
        max_iter: Number of iterations to run Boruta.
        perc: Percentile for confirmed features (default: 100).
        random_state: Random seed.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 8,
        max_iter: int = 100,
        perc: int = 100,
        random_state: int = 42,
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.max_iter = max_iter
        self.perc = perc
        self.random_state = random_state
        self.n_runs_ = 10  # Number of runs for stability

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: pd.Series) -> "BorutaSelector":
        """
        Learn which features to select using Boruta.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            self: The fitted instance.
        """
        # Convert numpy array to DataFrame if needed
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        # Filter out non-numeric columns (datetime, object, etc.)
        X = X.select_dtypes(include=[np.number])
        logger.info(f"Filtered to {X.shape[1]} numeric columns for Boruta")

        # Additional safety: remove object columns that contain datetime values
        # This handles the case where datetime columns are stored as object dtype
        # (e.g., when passed through ColumnTransformer with remainder="passthrough")
        for col in X.select_dtypes(include=["object"]).columns:
            if len(X[col].dropna()) > 0:
                sample = X[col].dropna().iloc[0]
                if hasattr(sample, "timestamp"):  # Check for Timestamp/datetime
                    logger.warning(f"Removing datetime column stored as object: {col}")
                    X = X.drop(columns=[col])

        X = X.copy()
        y = y.copy()

        d = {}
        for i in tqdm(range(self.n_runs_), total=self.n_runs_, desc="Running Boruta"):
            # Add random variable as shadow feature
            X_temp = X.copy()
            X_temp["random"] = np.random.randn(len(X_temp))

            rf = RandomForestClassifier(
                n_jobs=-1,
                class_weight="balanced",
                max_depth=self.max_depth,
                n_estimators=self.n_estimators,
                random_state=i,
            )

            feat_selector = BorutaPy(
                rf,
                n_estimators="auto",
                verbose=0,
                random_state=self.random_state + i,
                perc=self.perc,
            )

            feat_selector.fit(X_temp.values, y.values)

            ranking = pd.DataFrame({"col": X_temp.columns, "ranking": feat_selector.ranking_}).sort_values("ranking")

            # Variables up to the "random"
            random_idx = ranking[ranking.col == "random"].index
            if len(random_idx) > 0:
                random_rank = ranking[ranking.col == "random"]["ranking"].values[0]
                variables = ranking[ranking.ranking < random_rank].col.values
            else:
                variables = ranking.columns.values

            d[i] = variables

        # Count how many times each variable appeared
        E = {}
        for i in d.keys():
            for var in d[i]:
                if var not in E.keys():
                    E[var] = 1
                else:
                    E[var] += 1

        # Variables that appear in at least half of the runs
        self.selected_features_ = [k for k in E.keys() if E[k] >= self.n_runs_ // 2]
        self.selected_features_ = [v for v in self.selected_features_ if v != "random"]

        logger.info(f"Selected {len(self.selected_features_)} variables by Boruta")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform X keeping only the selected variables.

        Args:
            X: DataFrame to transform.

        Returns:
            pd.DataFrame: DataFrame with selected variables.

        Raises:
            ValueError: If fit() has not been called previously.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")

        # Ensure all variables exist
        available_features = [f for f in self.selected_features_ if f in X.columns]
        return X[available_features].copy()


def feature_selection_by_correlation(x_train, y_train, variables, method="pearson", th=0.9):
    """
    Legacy function for compatibility with existing code.

    .. deprecated::
        Use CorrelationSelector instead.
    """
    selector = CorrelationSelector(method=method, threshold=th)
    selector.fit(x_train[variables], y_train)
    return selector.get_selected_features()


def feature_selection_by_constant(x_train, y_train, variables, th=0.99):
    """
    Legacy function for compatibility with existing code.

    .. deprecated::
        Use ConstantSelector instead.
    """
    selector = ConstantSelector(threshold=th)
    selector.fit(x_train[variables], y_train)
    return selector.get_selected_features()


def feature_selection_by_boruta(X_train, y_train, N=10):
    """
    Legacy function for compatibility with existing code.

    .. deprecated::
        Use BorutaSelector instead.
    """
    selector = BorutaSelector(max_iter=N, n_runs_=N)
    selector.fit(X_train, y_train)
    return selector.get_selected_features()
