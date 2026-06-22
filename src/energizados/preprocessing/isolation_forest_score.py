"""
IsolationForestScore transformer for Energizados Framework.

Provides an sklearn-compatible global transformer that trains an Isolation Forest
during fit() and appends an anomaly score column during transform().
Higher scores indicate more anomalous observations.
"""

import logging
import warnings
from typing import List, Optional, Union

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import IsolationForest
from sklearn.exceptions import NotFittedError

logger = logging.getLogger(__name__)


class IsolationForestScore(BaseEstimator, TransformerMixin):
    """Isolation Forest anomaly score transformer.

        Trains an Isolation Forest during fit() and appends an anomaly score column
    during transform(). Scores are inverted so that higher values indicate more
        anomalous observations (matching fraud detection intuition).

        Parameters:
        -----------
        columns : list of str or None
            Column names to use for the Isolation Forest. If None, columns are
            auto-detected during fit() based on periods_suffix.
        n_estimators : int, default=100
            Number of base estimators in the ensemble.
        max_samples : int or str, default="auto"
            Number of samples to draw for training each base estimator.
        max_features : float, default=1.0
            Proportion of features to use for training each base estimator.
        contamination : float or str, default="auto"
            Expected proportion of anomalies in the data.
        random_state : int or None, default=None
            Random seed for reproducibility.
        contamination_from_target : bool, default=False
            If True and y is provided, set contamination to y.mean().
        output_column : str, default="if_score"
            Name of the anomaly score column appended by transform().
        periods_suffix : str, default="_anterior"
            Suffix pattern used for auto-detecting consumption columns.

        Attributes:
        -----------
        selected_columns_ : list of str
            Columns actually used for the Isolation Forest (set during fit()).
        train_medians_ : pd.Series
            Column-wise medians from training data for NaN imputation.
        contamination_ : float
            Actual contamination value used (set during fit()).
        if_model_ : IsolationForest
            Fitted Isolation Forest model.
        is_fitted_ : bool
            Whether the transformer has been fitted.

        Examples:
        ---------
        >>> transformer = IsolationForestScore(random_state=42)
        >>> X = pd.DataFrame({"1_anterior": [1.0, 2.0, 3.0], "2_anterior": [3.0, 2.0, 1.0]})
        >>> result = transformer.fit_transform(X)
        >>> "if_score" in result.columns
        True
    """

    def __init__(
        self,
        columns: Optional[List[str]] = None,
        n_estimators: int = 100,
        max_samples: Union[int, str] = "auto",
        max_features: float = 1.0,
        contamination: Union[float, str] = "auto",
        random_state: Optional[int] = None,
        contamination_from_target: bool = False,
        output_column: str = "if_score",
        periods_suffix: str = "_anterior",
    ):
        self.columns = columns
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.max_features = max_features
        self.contamination = contamination
        self.random_state = random_state
        self.contamination_from_target = contamination_from_target
        self.output_column = output_column
        self.periods_suffix = periods_suffix

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> "IsolationForestScore":
        """Fit the Isolation Forest transformer.

        Parameters:
        -----------
        X : pd.DataFrame
            Training data.
        y : pd.Series or None, optional
            Target variable. Used only if contamination_from_target=True.

        Returns:
        --------
        self : IsolationForestScore
            Fitted transformer.
        """
        # 1. Resolve columns
        if self.columns is None:
            # Auto-detect numeric columns ending with periods_suffix
            numeric_cols = X.select_dtypes(include="number").columns.tolist()
            suffix_cols = [c for c in numeric_cols if c.endswith(self.periods_suffix)]

            if suffix_cols:
                self.selected_columns_ = suffix_cols
                logger.info(
                    f"Auto-detected {len(suffix_cols)} columns with suffix "
                    f"'{self.periods_suffix}': {suffix_cols}"
                )
            else:
                # Fallback to all numeric columns
                self.selected_columns_ = numeric_cols
                logger.info(
                    f"No columns with suffix '{self.periods_suffix}' found. "
                    f"Falling back to all {len(numeric_cols)} numeric columns: {numeric_cols}"
                )
        else:
            # Validate explicit columns exist
            missing_cols = set(self.columns) - set(X.columns)
            if missing_cols:
                raise ValueError(f"Columns not found in DataFrame: {sorted(missing_cols)}")
            self.selected_columns_ = list(self.columns)

        # 2. Resolve contamination
        if self.contamination_from_target and y is not None:
            y_mean = float(y.mean())
            # IsolationForest requires contamination in (0.0, 0.5]. Both extremes
            # are degenerate subpopulations that crash fit() otherwise:
            #   - fraud-MAJORITY (y.mean() > 0.5): region-filtered dataset, e.g. 56% fraud
            #     (CELESC v3 F3E1) — passed y.mean()>0.5 and crashed.
            #   - all-negative (y.mean() == 0.0): a region with no positives in train —
            #     0.0 is excluded from sklearn's range too.
            # Clip into the valid open interval. The if_score feature is unaffected:
            # transform() uses score_samples, which is independent of contamination;
            # only the internal predict() decision offset is capped.
            contamination_clipped = min(max(y_mean, 1e-6), 0.5)
            if contamination_clipped != y_mean:
                logger.warning(
                    f"contamination_from_target derived y.mean()={y_mean:.4f} "
                    f"outside sklearn's valid range (0.0, 0.5] for IsolationForest; "
                    f"clipping to {contamination_clipped} (degenerate subpopulation)."
                )
            self.contamination_ = contamination_clipped
            logger.info(f"Contamination set from y.mean(): {self.contamination_}")
        else:
            if self.contamination_from_target and y is None:
                warnings.warn(
                    "contamination_from_target=True but no y was provided. "
                    f"Using constructor contamination={self.contamination}",
                    UserWarning,
                )
            self.contamination_ = self.contamination

        # 3. Compute column-wise medians and impute NaN
        X_selected = X[self.selected_columns_].copy()
        self.train_medians_ = X_selected.median()

        # Handle all-NaN columns (median will be NaN → replace with 0)
        all_nan_cols = self.train_medians_[self.train_medians_.isna()].index.tolist()
        if all_nan_cols:
            logger.warning(
                f"IsolationForestScore: {len(all_nan_cols)} columns are entirely NaN "
                f"in training data, filling with 0: {all_nan_cols}"
            )
            self.train_medians_ = self.train_medians_.fillna(0.0)

        X_imputed = X_selected.fillna(self.train_medians_)

        # 4. Train Isolation Forest
        self.if_model_ = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            max_features=self.max_features,
            contamination=self.contamination_,
            random_state=self.random_state,
        )
        self.if_model_.fit(X_imputed)

        # 5. Set fitted flag
        self.is_fitted_ = True

        logger.info(
            f"IsolationForestScore fitted with {len(self.selected_columns_)} columns, "
            f"contamination={self.contamination_}"
        )

        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform data by appending anomaly scores.

        Parameters:
        -----------
        X : pd.DataFrame
            Data to transform.

        Returns:
        --------
        pd.DataFrame
            Copy of X with output_column appended containing anomaly scores.

        Raises:
        -------
        NotFittedError
            If fit() has not been called.
        """
        # 1. Validate fitted state
        if not hasattr(self, "is_fitted_") or not self.is_fitted_:
            raise NotFittedError(
                "This IsolationForestScore instance is not fitted yet. "
                "Call 'fit' with appropriate arguments before using this transformer."
            )

        # 2. Select columns and impute NaN
        X_selected = X[self.selected_columns_].copy()
        X_imputed = X_selected.fillna(self.train_medians_)
        X_imputed = X_imputed.fillna(0.0)

        # 3. Compute scores (inverted so higher = more anomalous)
        scores = -self.if_model_.score_samples(X_imputed)

        # 4. Warn if output column already exists
        if self.output_column in X.columns:
            warnings.warn(
                f"Output column '{self.output_column}' already exists in DataFrame. "
                "It will be overwritten with anomaly scores.",
                UserWarning,
            )

        # 5. Append column and return
        result = X.copy()
        result[self.output_column] = scores

        return result
