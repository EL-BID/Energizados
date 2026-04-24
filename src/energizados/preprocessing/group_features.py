"""
group_features.py Module

This module contains transformers that compute group-relative features
for fraud detection in electricity consumption data.

Classes:
- GroupRelativeConsumption: Computes client consumption relative to group
  statistics (e.g., activity, tariff, zone). Generates proportion features
  like ``prop_cons_{window}_{metric}_{group_column}``.
- SeasonalAnomaly: Computes seasonal z-scores for each consumption month
  relative to the group's historical mean/std for that calendar month.
  Generates ``seasonal_anomaly_{i}_anterior`` columns.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

logger = logging.getLogger(__name__)


class GroupRelativeConsumption(BaseEstimator, TransformerMixin):
    """Compute consumption relative to group statistics.

    For each row, calculates the ratio between the client's own consumption
    aggregate (mean or max over a window) and the corresponding aggregate for
    the group defined by ``group_column``.

    This is a strong fraud signal: a residential customer consuming like an
    industrial one is a red flag.

    Anti-leakage note: group statistics are learned from the data passed to
    ``fit()`` (typically the training set). To use population-level statistics,
    ensure the training data includes the full population.

    Parameters
    ----------
    group_column : str, default="actividad"
        Column defining the group (e.g., ``actividad``, ``tipo_tarifa``, ``zona``,
        ``geo_cluster``).
    windows : list[int], default=[3, 6, 12]
        Window sizes (number of recent periods) to evaluate.
    metrics : list[str], default=["mean", "max"]
        Group statistics to compare against. Supported: ``"mean"``, ``"max"``.
    periods_suffix : str, default="_anterior"
        Suffix of consumption columns (e.g., ``12_anterior``).

    Examples
    --------
    >>> transformer = GroupRelativeConsumption(
    ...     group_column="actividad", windows=[3, 6], metrics=["mean", "max"]
    ... )
    >>> transformer.fit(df)
    >>> result = transformer.transform(df)
    """

    pipeline_stage = "pre"
    _SUPPORTED_METRICS = {"mean", "max"}

    def __init__(
        self,
        group_column: str = "actividad",
        windows=None,
        metrics=None,
        periods_suffix: str = "_anterior",
    ):
        self.group_column = group_column
        self.windows = windows if windows is not None else [3, 6, 12]
        self.metrics = metrics if metrics is not None else ["mean", "max"]
        self.periods_suffix = periods_suffix

    def _get_cons_cols(self, window: int):
        """Return consumption column names for a given window."""
        return [f"{i}{self.periods_suffix}" for i in range(window, 0, -1)]

    def _validate_config(self):
        invalid_metrics = set(self.metrics) - self._SUPPORTED_METRICS
        if invalid_metrics:
            raise ValueError(
                f"GroupRelativeConsumption: unsupported metrics {invalid_metrics}. "
                f"Supported: {self._SUPPORTED_METRICS}"
            )
        if not self.windows:
            raise ValueError("GroupRelativeConsumption: 'windows' cannot be empty")

    def fit(self, X, y=None):
        """Learn group statistics from training data.

        Args:
            X: Input DataFrame containing ``group_column`` and consumption columns.
            y: Ignored. Kept for API compatibility.

        Returns:
            self: The fitted transformer.
        """
        self._validate_config()

        if self.group_column not in X.columns:
            raise ValueError(
                f"GroupRelativeConsumption: group column '{self.group_column}' not found "
                f"in input DataFrame"
            )

        self.group_stats_ = {}

        for window in self.windows:
            cols = self._get_cons_cols(window)
            missing = [c for c in cols if c not in X.columns]
            if missing:
                logger.warning(
                    "GroupRelativeConsumption: window=%d missing columns %s — skipped",
                    window,
                    missing,
                )
                continue

            # Build a long-format dataframe: one row per (sample, period)
            df = X[[self.group_column] + cols].copy()
            melted = df.melt(
                id_vars=[self.group_column],
                value_vars=cols,
                value_name="consumo",
            )

            for metric in self.metrics:
                if metric == "mean":
                    grp = melted.groupby(self.group_column)["consumo"].mean()
                elif metric == "max":
                    grp = melted.groupby(self.group_column)["consumo"].max()
                else:
                    continue  # pragma: no cover

                self.group_stats_[(window, metric)] = grp.to_dict()

        if not self.group_stats_:
            logger.warning(
                "GroupRelativeConsumption: no group statistics computed — "
                "verify that consumption columns match windows and suffix"
            )

        return self

    def _generated_columns(self):
        """Return list of column names that this transformer produces."""
        cols = []
        for window in self.windows:
            for metric in self.metrics:
                cols.append(f"prop_cons_{window}_{metric}_{self.group_column}")
        return cols

    def get_feature_names_out(self, input_features=None):
        """Return output feature names (scikit-learn 1.2+ compatibility).

        Returns:
            np.ndarray: Names of generated columns.
        """
        return np.array(self._generated_columns())

    def transform(self, X):
        """Append group-relative proportion features.

        Args:
            X: Input DataFrame with consumption and group columns.

        Returns:
            pd.DataFrame: Original DataFrame with new proportion columns appended.
        """
        df = X.copy()

        if self.group_column not in df.columns:
            logger.warning(
                "GroupRelativeConsumption: group column '%s' missing — skipping",
                self.group_column,
            )
            return df

        for window in self.windows:
            cols = self._get_cons_cols(window)
            missing = [c for c in cols if c not in df.columns]
            if missing:
                continue

            # Client aggregates over the window
            client_mean = df[cols].mean(axis=1)
            client_max = df[cols].max(axis=1)

            for metric in self.metrics:
                key = (window, metric)
                if key not in getattr(self, "group_stats_", {}):
                    continue

                stats_map = self.group_stats_[key]
                group_stat = df[self.group_column].map(stats_map).fillna(0.0)

                if metric == "mean":
                    client_val = client_mean
                elif metric == "max":
                    client_val = client_max
                else:
                    continue  # pragma: no cover

                col_name = f"prop_cons_{window}_{metric}_{self.group_column}"
                df[col_name] = np.where(
                    group_stat > 0,
                    client_val / group_stat,
                    0.0,
                )

        return df


class SeasonalAnomaly(BaseEstimator, TransformerMixin):
    """Compute seasonal z-score for each consumption month.

    For each consumption column (e.g., ``12_anterior`` … ``1_anterior``), the
    transformer determines the calendar month that the column represents (based
    on ``date_column``) and computes:

        (consumption - group_mean_for_that_month) / group_std_for_that_month

    where the group is defined by ``group_column`` (default ``actividad``).

    This tells the model "this client consumes 30 % less than expected for its
    type in this month".

    Anti-leakage note: group monthly statistics are learned from the data
    passed to ``fit()`` (training set) and applied at ``transform()`` time.

    Parameters
    ----------
    group_column : str, default="actividad"
        Column used to group clients (e.g., ``actividad``, ``tipo_tarifa``).
    date_column : str, required
        Column with the inspection/cutoff date (used to map each consumption
        period to a calendar month).
    periods_suffix : str, default="_anterior"
        Suffix of consumption columns.

    Examples
    --------
    >>> transformer = SeasonalAnomaly(
    ...     group_column="actividad", date_column="fecha_inspeccion"
    ... )
    >>> transformer.fit(df)
    >>> result = transformer.transform(df)
    """

    pipeline_stage = "pre"

    def __init__(
        self,
        group_column: str = "actividad",
        date_column: str = None,
        periods_suffix: str = "_anterior",
    ):
        self.group_column = group_column
        self.date_column = date_column
        self.periods_suffix = periods_suffix

    def _get_cons_cols(self, num_periodos: int = 12):
        """Return consumption column names in reverse chronological order."""
        return [f"{i}{self.periods_suffix}" for i in range(num_periodos, 0, -1)]

    def fit(self, X, y=None):
        """Learn group-by-month mean and standard deviation.

        Args:
            X: Input DataFrame containing ``date_column``, ``group_column``,
                and consumption columns.
            y: Ignored. Kept for API compatibility.

        Returns:
            self: The fitted transformer.
        """
        if not self.date_column:
            raise ValueError("SeasonalAnomaly: 'date_column' is required")
        if self.date_column not in X.columns:
            raise ValueError(
                f"SeasonalAnomaly: date column '{self.date_column}' not found in input DataFrame"
            )
        if self.group_column not in X.columns:
            raise ValueError(
                f"SeasonalAnomaly: group column '{self.group_column}' not found in input DataFrame"
            )

        dt = pd.to_datetime(X[self.date_column], errors="coerce")
        inspection_month = dt.dt.month  # NaT -> NaN

        records = []
        for i in range(1, 13):
            col = f"{i}{self.periods_suffix}"
            if col not in X.columns:
                continue
            # Map period i to its actual calendar month
            actual_month = ((inspection_month - i - 1) % 12 + 1).astype("Int64")
            temp = pd.DataFrame(
                {
                    self.group_column: X[self.group_column].values,
                    "month": actual_month.values,
                    "consumo": X[col].values,
                }
            )
            records.append(temp)

        if not records:
            raise ValueError(
                "SeasonalAnomaly: no consumption columns found matching suffix "
                f"'{self.periods_suffix}'"
            )

        long_df = pd.concat(records, ignore_index=True)
        long_df = long_df.dropna(subset=["consumo", "month"])

        if long_df.empty:
            raise ValueError("SeasonalAnomaly: no valid consumption values after dropping NaNs")

        grp = long_df.groupby([self.group_column, "month"])["consumo"]
        mean_series = grp.mean()
        std_series = grp.std().fillna(0.0)  # single-observation groups -> std=0

        self.group_month_mean_ = mean_series.to_dict()
        self.group_month_std_ = std_series.to_dict()

        n_groups = len(mean_series)
        logger.info(
            "SeasonalAnomaly: learned statistics for %d group-month combinations",
            n_groups,
        )

        return self

    def _generated_columns(self):
        """Return list of column names that this transformer produces."""
        return [f"seasonal_anomaly_{i}{self.periods_suffix}" for i in range(1, 13)]

    def get_feature_names_out(self, input_features=None):
        """Return output feature names (scikit-learn 1.2+ compatibility).

        Returns:
            np.ndarray: Names of generated columns.
        """
        return np.array(self._generated_columns())

    def transform(self, X):
        """Append seasonally-adjusted anomaly columns.

        Args:
            X: Input DataFrame with date, group, and consumption columns.

        Returns:
            pd.DataFrame: Original DataFrame with ``seasonal_anomaly_*`` columns appended.
        """
        df = X.copy()

        if self.date_column not in df.columns:
            logger.warning(
                "SeasonalAnomaly: date column '%s' missing — skipping",
                self.date_column,
            )
            return df
        if self.group_column not in df.columns:
            logger.warning(
                "SeasonalAnomaly: group column '%s' missing — skipping",
                self.group_column,
            )
            return df

        dt = pd.to_datetime(df[self.date_column], errors="coerce")
        inspection_month = dt.dt.month

        # Build mapping DataFrames for merge
        mean_df = pd.DataFrame(
            [
                {"__group__": g, "__month__": m, "__mean__": v}
                for (g, m), v in getattr(self, "group_month_mean_", {}).items()
            ]
        )
        std_df = pd.DataFrame(
            [
                {"__group__": g, "__month__": m, "__std__": v}
                for (g, m), v in getattr(self, "group_month_std_", {}).items()
            ]
        )

        for i in range(1, 13):
            col = f"{i}{self.periods_suffix}"
            if col not in df.columns:
                continue

            out_col = f"seasonal_anomaly_{i}{self.periods_suffix}"
            actual_month = ((inspection_month - i - 1) % 12 + 1).astype("Int64")

            tmp = pd.DataFrame(
                {
                    self.group_column: df[self.group_column].values,
                    "__month__": actual_month.values,
                }
            )
            tmp = tmp.merge(
                mean_df,
                left_on=[self.group_column, "__month__"],
                right_on=["__group__", "__month__"],
                how="left",
            )
            tmp = tmp.merge(
                std_df,
                left_on=[self.group_column, "__month__"],
                right_on=["__group__", "__month__"],
                how="left",
                suffixes=("", "_std"),
            )

            mean_vals = tmp["__mean__"].values
            std_vals = tmp["__std__"].values
            mask = std_vals > 0

            zscore = np.zeros(len(df), dtype=float)
            np.divide(df[col].values - mean_vals, std_vals, out=zscore, where=mask)
            df[out_col] = zscore

        return df
