"""
simple_models.py Module

This module contains implementations of simple models used in data analysis.

Classes:
- ChangeTrendPercentajeIdentifierWide: A classifier to identify changes in trend percentage
in wide-format data.
- ConstantConsumptionClassifierWide: A classifier to identify constant consumption in wide-format data.
"""

from itertools import groupby

import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin


class ChangeTrendPercentajeIdentifierWide(BaseEstimator, ClassifierMixin):
    """Rule-based classifier that flags users whose recent consumption dropped sharply.

    Computes a trend percentage as ``100 * mean(eval_periods) / mean(base_periods)``
    and marks a user as fraudulent when ``100 - trend_perc > threshold``.
    """

    def __init__(self, last_base_value, last_eval_value, threshold, is_wide=True):
        """
        Initialize the ChangeTrendPercentajeIdentifierWide class.

        Parameters:
        - last_base_value: int, the number of base values used for trend percentage calculation.
        - last_eval_value: int, the number of evaluation values used for trend percentage calculation.
        - threshold: float, the threshold used to determine if trend percentage indicates fraud.
        - is_wide: bool, indicates whether input data is in wide format or not.

        """
        self.last_base_value = last_base_value
        self.last_eval_value = last_eval_value
        self.threshold = threshold
        self.is_wide = is_wide

    def convert_wide(self, df):
        """Pivot long-format consumption data to wide format.

        Args:
            df: Long-format DataFrame with columns ``index``, ``date``, and ``consumo``.

        Returns:
            pd.DataFrame: Wide-format DataFrame with one consumption column per period.
        """
        df_wide = pd.pivot(df, index=["index"], columns=["date"], values=["consumo"]).reset_index()
        # organize columns with appropriate names
        df_wide.columns = ["index"] + [str(i) + "_anterior" for i in range(self.last_eval_value + self.last_base_value)][::-1]
        return df_wide

    def get_cant_cols(self):
        """Return the base and evaluation consumption column name lists.

        Returns:
            tuple: (cols_base, cols_eval) where cols_base contains the historical reference
                columns and cols_eval contains the recent evaluation columns.
        """
        # get base columns and columns used for evaluation
        cols_base = [str(i) + "_anterior" for i in range(self.last_eval_value + 1, self.last_base_value + self.last_eval_value + 1)][
            ::-1
        ]  # last_base_value
        cols_eval = [str(i) + "_anterior" for i in range(1, self.last_eval_value + 1)][::-1]  # last_eval_value
        #         print('[INFO]...cols base:', cols_base)
        #         print('[INFO]...cols eval:', cols_eval)
        return cols_base, cols_eval

    def compute_trend_percentage_wide(self, X):
        """Compute the trend percentage for each row.

        Args:
            X: Wide-format DataFrame with consumption columns. If ``is_wide`` is False,
                the data is first pivoted via ``convert_wide``.

        Returns:
            pd.DataFrame: Input DataFrame with an additional ``trend_perc`` column.
        """
        if not self.is_wide:
            X = self.convert_wide(X)

        cols_base, cols_eval = self.get_cant_cols()
        X["trend_perc"] = 100 * X[cols_eval].mean(axis=1) / (X[cols_base].mean(axis=1) + 0.000001)
        return X

    def fit(self, X, y=None):
        """No-op fit. This model has no learnable parameters.

        Args:
            X: Ignored.
            y: Ignored.

        Returns:
            self
        """
        return self

    def predict(self, X):
        """Predict fraud labels based on trend percentage drop.

        Args:
            X: Wide-format DataFrame with consumption columns.

        Returns:
            pd.DataFrame: DataFrame with columns ``trend_perc`` (float) and
                ``is_fraud_trend_perc`` (int, 1 if flagged as fraud).
        """
        X_copy = X.copy()
        X_copy = self.compute_trend_percentage_wide(X_copy)
        X_copy["is_fraud_trend_perc"] = (100 - X_copy["trend_perc"] > self.threshold).astype(int)
        return X_copy[["trend_perc", "is_fraud_trend_perc"]]


class ConstantConsumptionClassifierWide(BaseEstimator, ClassifierMixin):
    """Rule-based classifier that flags users with suspiciously constant consumption.

    A user is classified as fraudulent when any run of consecutive identical consumption
    values meets or exceeds ``min_count_constante``.
    """

    def __init__(self, min_count_constante):
        """
        Initialize the ConstantConsumptionClassifierWide class.

        Parameters:
        - min_count_constante: int, the minimum number of consecutive occurrences of a value to be considered constant.

        """
        self.min_count_constante = min_count_constante

    def fit(self, X, y=None):
        """No-op fit. This model has no learnable parameters.

        Args:
            X: Ignored.
            y: Ignored.

        Returns:
            self
        """
        return self

    def len_max_consumo_constante_seg(self, consumo):
        """Return 1 if any run of identical values meets the minimum count.

        Args:
            consumo: Iterable of consumption values for a single user.

        Returns:
            int: 1 if a qualifying constant run exists, 0 otherwise.
        """
        g = [[k, len(list(v))] for k, v in groupby(consumo)]
        g = [x for x in g if (x[1] >= self.min_count_constante)]
        if any(g):
            return 1
        else:
            return 0

    def predict(self, X):
        """Predict fraud labels based on constant consumption runs.

        Args:
            X: DataFrame where each row contains the consumption sequence for one user.

        Returns:
            pd.Series: Binary predictions (1 = fraud, 0 = normal).
        """
        pred = X.apply(lambda x: self.len_max_consumo_constante_seg(x.values), axis=1)
        return pred
