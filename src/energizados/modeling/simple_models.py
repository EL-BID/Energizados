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
        df_wide = pd.pivot(df, index=["index"], columns=["date"], values=["consumo"]).reset_index()
        # organize columns with appropriate names
        df_wide.columns = ["index"] + [str(i) + "_anterior" for i in range(self.last_eval_value + self.last_base_value)][::-1]
        return df_wide

    def get_cant_cols(self):
        # get base columns and columns used for evaluation
        cols_base = [str(i) + "_anterior" for i in range(self.last_eval_value + 1, self.last_base_value + self.last_eval_value + 1)][
            ::-1
        ]  # last_base_value
        cols_eval = [str(i) + "_anterior" for i in range(1, self.last_eval_value + 1)][::-1]  # last_eval_value
        #         print('[INFO]...cols base:', cols_base)
        #         print('[INFO]...cols eval:', cols_eval)
        return cols_base, cols_eval

    def compute_trend_percentage_wide(self, X):
        if not self.is_wide:
            X = self.convert_wide(X)

        cols_base, cols_eval = self.get_cant_cols()
        X["trend_perc"] = 100 * X[cols_eval].mean(axis=1) / (X[cols_base].mean(axis=1) + 0.000001)
        return X

    def fit(self, X, y=None):

        return self

    def predict(self, X):
        X_copy = X.copy()
        X_copy = self.compute_trend_percentage_wide(X_copy)
        X_copy["is_fraud_trend_perc"] = (100 - X_copy["trend_perc"] > self.threshold).astype(int)
        return X_copy[["trend_perc", "is_fraud_trend_perc"]]


class ConstantConsumptionClassifierWide(BaseEstimator, ClassifierMixin):

    def __init__(self, min_count_constante):
        """
        Initialize the ConstantConsumptionClassifierWide class.

        Parameters:
        - min_count_constante: int, the minimum number of consecutive occurrences of a value to be considered constant.

        """
        self.min_count_constante = min_count_constante

    def fit(self, X, y=None):
        return self

    def len_max_consumo_constante_seg(self, consumo):
        #         print(consumo)
        g = [[k, len(list(v))] for k, v in groupby(consumo)]
        g = [x for x in g if (x[1] >= self.min_count_constante)]
        if any(g):
            return 1
        #             return sorted(g, reverse=True, key=lambda x: x[-1])[0][1]
        else:
            return 0

    def predict(self, X):
        pred = X.apply(lambda x: self.len_max_consumo_constante_seg(x.values), axis=1)
        return pred
