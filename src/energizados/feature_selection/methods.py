"""
Feature Selection Methods for Energizados Framework.

Implementations of feature selection methods based on
existing project code.
"""

import logging
import warnings
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd
from boruta import BorutaPy
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
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

        target_corr = df_corr["target"].drop("target").abs().sort_values(ascending=False)

        selected = []
        dropped = []
        for feat in target_corr.index:
            if feat in dropped:
                continue
            keep = True
            for sel_feat in selected:
                if np.abs(df_corr.loc[feat, sel_feat]) > self.threshold:
                    keep = False
                    break
            if keep:
                selected.append(feat)
            else:
                dropped.append(feat)

        self.vars_to_drop_ = dropped
        self.selected_features_ = selected

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

    def get_audit_stats(self) -> Dict:
        """
        Return audit statistics for correlation selector.

        Returns:
            Dict: Contains vars_to_drop, method, and threshold.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return {
            "vars_to_drop": self.vars_to_drop_ or [],
            "method": self.method,
            "threshold": self.threshold,
        }


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

        constant_per_feature = {}
        for label in all_labels:
            vc = X[label].value_counts()
            if len(vc) == 0:
                constant_per_feature[label] = 1.0
            else:
                constant_per_feature[label] = vc.iloc[0] / num_rows

        self.vars_to_drop_ = [
            label for label in all_labels if constant_per_feature[label] > self.threshold
        ]
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

    def get_audit_stats(self) -> Dict:
        """
        Return audit statistics for constant selector.

        Returns:
            Dict: Contains vars_to_drop and threshold.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return {
            "vars_to_drop": self.vars_to_drop_ or [],
            "threshold": self.threshold,
        }


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
        self.vote_counts_: Optional[Dict] = None  # Initialized to None, set after fit

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
        pbar = tqdm(total=self.n_runs_, desc="Running Boruta", leave=False)
        for i in range(self.n_runs_):
            # Add random variable as shadow feature.
            # IMPORTANT: derive the shadow column from a per-iteration RNG seeded
            # from ``self.random_state``. Previously this used the unseeded global
            # NumPy RNG and the shadow varied run-to-run, which made
            # ``selected_features_`` non-deterministic even with the same
            # ``random_state``. The seed offset ``+ i`` mirrors the per-iteration
            # seed already used by BorutaPy below.
            shadow_rng = np.random.default_rng(self.random_state + i)
            X_temp = X.copy()
            X_temp["random"] = shadow_rng.standard_normal(len(X_temp))

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

            ranking = pd.DataFrame(
                {"col": X_temp.columns, "ranking": feat_selector.ranking_}
            ).sort_values("ranking")

            # Variables up to the "random"
            random_idx = ranking[ranking.col == "random"].index
            if len(random_idx) > 0:
                random_rank = ranking[ranking.col == "random"]["ranking"].values[0]
                variables = ranking[ranking.ranking < random_rank].col.values
            else:
                variables = ranking.columns.values

            d[i] = variables
            pbar.update(1)

        pbar.close()

        # Count how many times each variable appeared
        E = {}
        for i in d.keys():
            for var in d[i]:
                if var not in E.keys():
                    E[var] = 1
                else:
                    E[var] += 1

        # Store vote counts for audit logging (exclude "random" shadow feature)
        self.vote_counts_ = {k: v for k, v in E.items() if k != "random"}

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

    def get_audit_stats(self) -> Dict:
        """
        Return audit statistics for Boruta selector.

        Returns:
            Dict: Contains vote_counts, n_runs, and threshold.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return {
            "vote_counts": self.vote_counts_ or {},
            "n_runs": self.n_runs_,
            "threshold": self.n_runs_ // 2,
        }


def feature_selection_by_correlation(x_train, y_train, variables, method="pearson", th=0.9):
    """
    Legacy function for compatibility with existing code.

    .. deprecated::
        Use :class:`CorrelationSelector` instead.
        Will be removed in a future version.
    """
    warnings.warn(
        "feature_selection_by_correlation is deprecated and will be removed in a future version. "
        "Use CorrelationSelector instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    selector = CorrelationSelector(method=method, threshold=th)
    selector.fit(x_train[variables], y_train)
    return selector.get_selected_features()


def feature_selection_by_constant(x_train, y_train, variables, th=0.99):
    """
    Legacy function for compatibility with existing code.

    .. deprecated::
        Use :class:`ConstantSelector` instead.
        Will be removed in a future version.
    """
    warnings.warn(
        "feature_selection_by_constant is deprecated and will be removed in a future version. "
        "Use ConstantSelector instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    selector = ConstantSelector(threshold=th)
    selector.fit(x_train[variables], y_train)
    return selector.get_selected_features()


def feature_selection_by_boruta(X_train, y_train, N=10):
    """
    Legacy function for compatibility with existing code.

    .. deprecated::
        Use :class:`BorutaSelector` instead.
        Will be removed in a future version.
    """
    warnings.warn(
        "feature_selection_by_boruta is deprecated and will be removed in a future version. "
        "Use BorutaSelector instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    selector = BorutaSelector(max_iter=N)
    selector.fit(X_train, y_train)
    return selector.get_selected_features()


class CategoricalSelector(BaseFeatureSelector):
    """
    Selector that filters to keep only categorical columns.

    Returns columns with dtype 'object' or 'category'. Useful for
    scoping categorical variables in a multi-step pipeline.

    Args:
        include_category: If True (default), includes 'category' dtype.
        include_object: If True (default), includes 'object' dtype.
    """

    def __init__(
        self,
        include_category: bool = True,
        include_object: bool = True,
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.include_category = include_category
        self.include_object = include_object
        self.vars_to_drop_ = None

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: pd.Series) -> "CategoricalSelector":
        """
        Learn which columns are categorical.

        Args:
            X: Training features.
            y: Training target (not used in this method).

        Returns:
            self: The fitted instance.
        """
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        include = []
        if self.include_object:
            include.append("object")
        if self.include_category:
            include.append("category")

        categorical_cols = X.select_dtypes(include=include).columns.tolist()
        all_cols = X.columns.tolist()

        self.selected_features_ = categorical_cols
        self.vars_to_drop_ = [c for c in all_cols if c not in categorical_cols]

        logger.info(f"Selected {len(self.selected_features_)} categorical columns")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform X keeping only categorical columns.

        Args:
            X: DataFrame to transform.

        Returns:
            pd.DataFrame: DataFrame with only categorical columns.

        Raises:
            ValueError: If fit() has not been called previously.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return X[self.selected_features_].copy()

    def get_audit_stats(self) -> Dict:
        """
        Return audit statistics for categorical selector.

        Returns:
            Dict: Contains vars_to_drop and selected count.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return {
            "vars_to_drop": self.vars_to_drop_ or [],
            "selected_count": len(self.selected_features_),
        }


class MutualInformationSelector(BaseFeatureSelector):
    """
    Feature selector based on mutual information with the target.

    Mutual information measures the dependency between variables.
    Higher values indicate stronger predictive power.

    Args:
        k: Number of top features to select (default: 10).
        random_state: Random seed for reproducibility (default: 42).
        discrete_features: List of indices of discrete features.
                       If 'auto', features are inferred from dtype.
    """

    def __init__(
        self,
        k: int = 10,
        random_state: int = 42,
        discrete_features: Union[str, list] = "auto",
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.k = k
        self.random_state = random_state
        self.discrete_features = discrete_features
        self.scores_ = None

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: pd.Series) -> "MutualInformationSelector":
        """
        Learn which features to select using mutual information.

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
        logger.info(f"Filtered to {X.shape[1]} numeric columns for mutual information")

        X = X.copy()
        y = y.copy()

        # Determine target type
        if y.nunique() <= 2:
            # Binary or multi-class classification
            logger.info("Computing mutual information (classification)")
            scores = mutual_info_classif(
                X,
                y,
                discrete_features=self.discrete_features,
                random_state=self.random_state,
            )
        else:
            # Regression
            logger.info("Computing mutual information (regression)")
            scores = mutual_info_regression(
                X,
                y,
                discrete_features=self.discrete_features,
                random_state=self.random_state,
            )

        self.scores_ = pd.Series(scores, index=X.columns)

        # Get top k features
        top_k = self.scores_.nlargest(self.k)
        self.selected_features_ = top_k.index.tolist()

        logger.info(
            f"Selected {len(self.selected_features_)} features by mutual information (top {self.k})"
        )
        logger.info(f"Top 5 features: {self.selected_features_[:5]}")

        return self

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
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")

        # Ensure all selected features exist
        available_features = [f for f in self.selected_features_ if f in X.columns]
        return X[available_features].copy()

    def get_audit_stats(self) -> Dict:
        """
        Return audit statistics for mutual information selector.

        Returns:
            Dict: Contains scores and k (number of top features).
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        scores = self.scores_.to_dict() if self.scores_ is not None else {}
        return {"scores": scores, "k": self.k}
