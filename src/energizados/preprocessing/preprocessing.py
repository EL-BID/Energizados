"""
preprocessing.py Module

This module contains classes and functions used for data preprocessing before analysis.

Classes:
- ToDummy: Transforms categorical variables into dummy variables.
- TeEncoder: Encodes categorical variables using target encoding.
- CardinalityReducer: Reduces the cardinality of categorical variables.
- MinMaxScalerRow: Applies Min-Max transformation to matrix rows.
- TsfelVars: Calculates features using the tsfel library.
- ExtraVars: Creates additional features based on previous values.

Functions:
- fill_empty_values_cycle: Fills empty values in consumption columns with previous or subsequent values.
- fill_empty_values_str: Fills empty values in string columns with a specific value.
- fill_empty_values_numeric: Fills empty values in numeric columns with a specific value.
- build_feature_engineering_pipeline: Builds a preprocessing pipeline for feature engineering.
"""

import logging
from itertools import groupby

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, OneToOneFeatureMixin, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler
from tqdm import tqdm

logger = logging.getLogger()


# tsfel is imported lazily to avoid scipy compatibility issues
def _get_tsfel():
    """Import tsfel lazily."""
    import tsfel

    return tsfel


class ToDummy(BaseEstimator, TransformerMixin):
    """
    Transforms categorical variables into dummy variables.

    Parameters:
    - cols: list, list of columns to convert to dummy variables.
    - sparse: bool, if True returns sparse matrix (default=False).
    """

    def __init__(self, cols=None, sparse=False):
        self.cols = cols
        self.sparse = sparse

    def fit(self, X, y=None):
        # X is a DataFrame with only the columns to transform
        if self.cols is None:
            self.cols = X.columns.tolist()

        # Store categories seen during fit
        self.categories_ = {}
        for col in self.cols:
            self.categories_[col] = set(X[col].unique())

        # Generate dummy column names
        self.dummy_names_ = self._generate_dummy_names(self.categories_)
        return self

    def _generate_dummy_names(self, categories):
        """Generate dummy column names based on categories."""
        names = []
        for col, cats in categories.items():
            for cat in cats:
                names.append(f"dummy_{col}_{cat}")
        return names

    def transform(self, X, y=None):
        # X is a DataFrame with only the columns to transform
        X_transformed = pd.DataFrame(index=X.index)

        for col in self.cols:
            # Create dummies only for this column
            dummies = pd.get_dummies(X[col], prefix=f"dummy_{col}", dtype=float)

            # Add missing columns (categories in train but not in test)
            for cat in self.categories_[col]:
                col_name = f"dummy_{col}_{cat}"
                if col_name not in dummies.columns:
                    dummies[col_name] = 0

            # Remove extra columns (categories in test but not in train)
            cols_to_keep = [f"dummy_{col}_{cat}" for cat in self.categories_[col]]
            dummies = dummies[cols_to_keep]

            X_transformed = pd.concat([X_transformed, dummies], axis=1)

        # Return in correct order and as numpy array
        X_transformed = X_transformed[self.dummy_names_]

        if self.sparse:
            from scipy import sparse

            return sparse.csr_matrix(X_transformed.values)

        return X_transformed.values

    def get_feature_names_out(self, input_features=None):
        """Method required by scikit-learn 1.2+ for set_output."""
        return self.dummy_names_


class TeEncoder(BaseEstimator, TransformerMixin):
    """
    Encodes categorical variables using target encoding.

    Parameters:
    - cols: list, list of columns to encode.
    - w: int, weight for target encoding calculation (smoothing).
    """

    def __init__(self, cols=None, w=20):
        self.cols = cols
        self.w = w
        self.te_var_name = None

    def _generate_output_name(self):
        """Generate the output column name."""
        if self.cols is None:
            return "target_enc_prob"
        return "_".join(self.cols) + "_prob"

    def fit(self, X, y=None):
        # X is a DataFrame with only the columns to encode
        if self.cols is None:
            self.cols = X.columns.tolist()

        self.te_var_name = self._generate_output_name()
        self.mean_global = y.mean()

        # Create mapping without modifying original X
        df = X.copy()
        df["target"] = y.values

        # Group and calculate target encoding with smoothing
        te = df.groupby(self.cols)["target"].agg(["mean", "count"]).reset_index()
        te[self.te_var_name] = ((te["mean"] * te["count"]) + (self.mean_global * self.w)) / (te["count"] + self.w)

        # Store only the necessary columns for merge
        self.te_mapping_ = te[self.cols + [self.te_var_name]]

        return self

    def transform(self, X):
        # X is a DataFrame with only the columns to encode
        X_copy = X.copy()

        # Merge with the mapping
        X_copy = X_copy.merge(self.te_mapping_, on=self.cols, how="left")

        # Fill NaNs with global mean
        X_copy[self.te_var_name] = X_copy[self.te_var_name].fillna(self.mean_global)

        # Return only the encoded column as numpy array (2D)
        return X_copy[[self.te_var_name]].values

    def get_feature_names_out(self, input_features=None):
        """Method required by scikit-learn 1.2+ for set_output."""
        if self.te_var_name is None:
            self.te_var_name = self._generate_output_name()
        return np.array([self.te_var_name])


class CardinalityReducer(OneToOneFeatureMixin, BaseEstimator, TransformerMixin):
    """
    CardinalityReducer Class

    Transformer to reduce the cardinality of categorical variables.

    Parameters:
    - cols: list, list of categorical columns to reduce cardinality.
    - threshold: int, frequency limit to group infrequent categories into an "other" category.
    """

    def __init__(self, threshold=0.1):
        self.threshold = threshold

    def find_top_categories(self, feature):
        proportions = feature.value_counts(normalize=True)
        categories = proportions[proportions >= self.threshold].index.values
        return categories

    def fit(self, X, y=None):
        # Store column names for set_output support
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.array(X.columns.tolist())
        else:
            self.feature_names_in_ = None

        self.columns = X.columns
        self.categories = {}
        for feature in self.columns:
            self.categories[feature] = self.find_top_categories(X[feature])
        return self

    def transform(self, X):
        X = X.copy()
        for feature in self.columns:
            X[feature] = np.where(X[feature].isin(self.categories[feature]), X[feature], "otros")
        return X

    def get_feature_names_out(self, input_features=None):
        """
        Method required by scikit-learn 1.2+ for set_output.
        Returns output feature names (same as input features).
        """
        if input_features is not None:
            return input_features
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        # Fallback: generate generic names if none were stored
        return np.array([f"x{i}" for i in range(self.n_features_in_)]) if hasattr(self, "n_features_in_") else np.array([])


class CastDtype(OneToOneFeatureMixin, BaseEstimator, TransformerMixin):
    """
    Converts columns to a specific pandas dtype.

    Parameters:
    - dtype: str or pandas type, target dtype (e.g., 'float32', 'int8', 'category', 'bool').
    """

    def __init__(self, dtype="float32"):
        self.dtype = dtype

    def fit(self, X, y=None):
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.array(X.columns.tolist())
        return self

    def transform(self, X, y=None):
        return X.astype(self.dtype)


class MinMaxScalerRow(OneToOneFeatureMixin, BaseEstimator, TransformerMixin):
    """
    MinMaxScalerRow Class

    Transformer to scale matrix rows using Min-Max Scaling.

    Parameters:
    - feature_range: tuple, range of values for scaling.
    """

    def __init__(self, feature_range=(0, 1)):
        self.feature_range = feature_range

    def fit(self, X, y=None):
        # Store column names for set_output support
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.array(X.columns.tolist())
        else:
            self.feature_names_in_ = None
        return self

    def transform(self, X):
        scaler = MinMaxScaler(feature_range=self.feature_range)
        X_scaled = scaler.fit_transform(X.T).T

        # If X is a DataFrame, return a DataFrame with same names and index
        if hasattr(X, "columns") and hasattr(X, "index"):
            import pandas as pd

            return pd.DataFrame(X_scaled, columns=X.columns, index=X.index)

        return X_scaled

    def get_feature_names_out(self, input_features=None):
        """
        Method required by scikit-learn 1.2+ for set_output.
        Returns output feature names (same as input features).
        """
        if input_features is not None:
            return input_features
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        # Fallback: generate generic names if none were stored
        return np.array([f"x{i}" for i in range(self.n_features_in_)]) if hasattr(self, "n_features_in_") else np.array([])


def _tsfel_process_chunk(chunk_values, chunk_indices, cfg):
    """
    Process a chunk of rows with tsfel. Module-level function to be
    serializable by joblib in multiprocessing mode.

    Args:
        chunk_values: numpy array (N_rows, N_periods).
        chunk_indices: list of original DataFrame indices.
        cfg: tsfel configuration (result of get_features_by_domain).

    Returns:
        pd.DataFrame with extracted features + 'index' column.
    """
    tsfel = _get_tsfel()
    results = []
    for idx, values in zip(chunk_indices, chunk_values):
        features = tsfel.time_series_features_extractor(cfg, values, fs=1, verbose=0)
        null_count = features.isnull().sum().sum()
        if null_count > 0:
            null_cols = features.columns[features.isnull().any()].tolist()
            logger.warning(f"TsfelVars: index {idx} generated {null_count} nulls " f"(e.g., {null_cols[:3]}). values={values}")
        features["index"] = idx
        results.append(features)
    return pd.concat(results, ignore_index=True)


class TsfelVars(BaseEstimator, TransformerMixin):
    """
    Transformer to extract time series features using tsfel.

    Parameters:
    - features_names_path: str or None, path to JSON with custom tsfel config.
    - num_periodos: int, number of consumption periods to use (default=12).
    - periods_suffix: str, suffix of consumption columns (default="_anterior").
    - n_jobs: int, number of parallel processes. 1=sequential, -1=all cores.
    - chunk_size: int, rows per chunk sent to each worker (default=500).
    - cache_dir: str or None, directory to cache results on disk.
      If None, no caching. Useful for iterative experimentation.
    """

    def __init__(
        self,
        features_names_path=None,
        num_periodos=12,
        periods_suffix: str = "_anterior",
        n_jobs: int = 1,
        chunk_size: int = 500,
        cache_dir: str = None,
    ):
        self.num_periodos = num_periodos
        self.features_names_path = features_names_path
        self.periods_suffix = periods_suffix
        self.n_jobs = n_jobs
        self.chunk_size = chunk_size
        self.cache_dir = cache_dir

    def obtener_cols_anterior(self, num_cols=12):
        return [f"{i}{self.periods_suffix}" for i in range(num_cols, 0, -1)]

    def _run_parallel(self, df, cols, cfg, desc="tsfel"):
        """
        Split df into chunks and process them in parallel (or sequential if n_jobs=1).

        Args:
            df: Complete DataFrame.
            cols: Consumption columns to use.
            cfg: tsfel configuration.
            desc: Description for progress bar.

        Returns:
            pd.DataFrame with all features concatenated + 'index' column.
        """
        from joblib import Parallel, delayed

        data = df[cols].values
        indices = df.index.tolist()
        n = len(df)

        # Split into chunks
        chunks = [(data[i : i + self.chunk_size], indices[i : i + self.chunk_size]) for i in range(0, n, self.chunk_size)]

        logger.info(f"TsfelVars [{desc}]: {n} rows in {len(chunks)} chunks, n_jobs={self.n_jobs}")

        results = Parallel(n_jobs=self.n_jobs)(
            delayed(_tsfel_process_chunk)(chunk_values, chunk_indices, cfg) for chunk_values, chunk_indices in tqdm(chunks, desc=desc)
        )

        return pd.concat(results, ignore_index=True)

    def _get_cached_transform(self):
        """Return cached version of _compute if cache_dir is configured."""
        if self.cache_dir is not None:
            from joblib import Memory

            memory = Memory(location=self.cache_dir, verbose=0)
            return memory.cache(self._compute)
        return self._compute

    def _compute(self, df_values, df_indices, cols, cfg_domain=None, cfg_json_path=None):
        """
        Core computation, separated to allow caching with joblib.Memory.

        Args:
            df_values: numpy array with consumption column values.
            df_indices: list of original indices.
            cols: column names (to reconstruct DataFrame).
            cfg_domain: tsfel domain name ('statistical', 'temporal', etc.).
            cfg_json_path: path to tsfel config JSON (mutually exclusive with cfg_domain).
        """
        tsfel = _get_tsfel()
        if cfg_json_path is not None:
            cfg = tsfel.get_features_by_domain(json_path=cfg_json_path)
            desc = "tsfel_json"
        else:
            cfg = tsfel.get_features_by_domain(cfg_domain)
            desc = cfg_domain

        # Reconstruct temporary DataFrame for _run_parallel
        df_temp = pd.DataFrame(df_values, index=df_indices, columns=cols)
        return self._run_parallel(df_temp, cols, cfg, desc=desc)

    def extra_cols(self, df, domain, cols, window=12):
        tsfel = _get_tsfel()
        cfg = tsfel.get_features_by_domain(domain)
        return self._run_parallel(df, cols, cfg, desc=domain)

    def compute_by_json(self, df, cols, window=12):
        tsfel = _get_tsfel()
        cfg = tsfel.get_features_by_domain(json_path=self.features_names_path)
        return self._run_parallel(df, cols, cfg, desc="tsfel_json")

    def crear_all_tsfel(self, df):
        cols_anterior = self.obtener_cols_anterior(self.num_periodos)
        df_result_stat = self.extra_cols(df, "statistical", cols_anterior, window=self.num_periodos)
        df_result_temporal = self.extra_cols(df, "temporal", cols_anterior, window=self.num_periodos)
        # df_result_spectral = self.extra_cols(df, "spectral", cols_anterior, window=self.num_periodos)
        self.temp_vars = [c for c in df_result_temporal.columns if c != "index"]
        self.stat_vars = [c for c in df_result_stat.columns if c != "index"]
        # self.spec_vars = [c for c in df_result_spectral.columns if c != "index"]
        return df_result_stat, df_result_temporal  # , df_result_spectral

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        cached_compute = self._get_cached_transform()
        cols_anterior = self.obtener_cols_anterior(self.num_periodos)

        if self.features_names_path is not None:
            df_tsfel = cached_compute(
                X[cols_anterior].values,
                X["index"].tolist(),
                cols_anterior,
                cfg_json_path=self.features_names_path,
            )
            X = X.merge(df_tsfel, on="index", how="left")
        else:
            df_result_stat = cached_compute(
                X[cols_anterior].values,
                X["index"].tolist(),
                cols_anterior,
                cfg_domain="statistical",
            )
            df_result_temporal = cached_compute(
                X[cols_anterior].values,
                X["index"].tolist(),
                cols_anterior,
                cfg_domain="temporal",
            )

            df_tsfel = pd.merge(df_result_stat, df_result_temporal, how="inner", on="index")

            X = X.merge(df_tsfel, on="index", how="left")

        return X


class ExtraVars(BaseEstimator, TransformerMixin):
    """
    ExtraVars Class

    Transformer to generate additional features based on time series data.

    Parameters:
    - aggregation_functions: dict, dictionary mapping new feature names to aggregation functions.
    """

    def __init__(self, num_periodos=3, periods_suffix: str = "_anterior"):
        self.num_periodos = num_periodos
        self.periods_suffix = periods_suffix

    def fit(self, X, y=None):
        return self

    def obtener_cols_anterior(self, num_cols=12):
        return [f"{i}{self.periods_suffix}" for i in range(num_cols, 0, -1)]

    def transform(self, X):
        return self.create_vbles(X)

    def count_cero(self, x):
        return (x == 0.0).sum()

    def count_cero_seguidos(self, x):
        ceros_seguidos = 2
        consumo = x.values
        g = [[k, len(list(v))] for k, v in groupby(consumo)]
        g = [x for x in g if (x[0] == 0.0) & (x[1] >= ceros_seguidos)]
        if any(g):
            return sorted(g, reverse=True, key=lambda x: x[-1])[0][1]
        else:
            return 0

    def calc_slope(self, x):
        consumo = list(x.values)
        slope = np.polyfit(range(len(consumo)), consumo, 1)[0]
        return slope

    def create_vbles(self, df_total_super):
        # generate list of cols from back to front i.e: ['3_anterior', '2_anterior', '1_anterior'], etc.
        cols_3_anterior = self.obtener_cols_anterior(num_cols=self.num_periodos)
        num_periodos_str = str(self.num_periodos)
        # averages
        df_total_super.loc[:, "mean_" + num_periodos_str] = df_total_super[cols_3_anterior].mean(axis=1)
        # Zero count
        df_total_super.loc[:, "cant_ceros_" + num_periodos_str] = df_total_super[cols_3_anterior].apply(self.count_cero, axis=1)
        df_total_super.loc[:, "max_cant_ceros_seg_" + num_periodos_str] = df_total_super[cols_3_anterior].apply(
            self.count_cero_seguidos, axis=1
        )
        # Slope
        df_total_super.loc[:, "slope_" + num_periodos_str] = df_total_super[cols_3_anterior].apply(self.calc_slope, axis=1)
        # Min, Max, STD, Variance for 3 periods
        df_total_super.loc[:, "min_cons" + num_periodos_str] = df_total_super[cols_3_anterior].min(axis=1)
        df_total_super.loc[:, "max_cons" + num_periodos_str] = df_total_super[cols_3_anterior].max(axis=1)
        df_total_super.loc[:, "std_cons" + num_periodos_str] = df_total_super[cols_3_anterior].std(axis=1)
        df_total_super.loc[:, "var_cons" + num_periodos_str] = df_total_super[cols_3_anterior].var(axis=1)
        # skewness and kurtosis for 3 periods
        df_total_super.loc[:, "skew_cons" + num_periodos_str] = df_total_super[cols_3_anterior].skew(axis=1)
        if self.num_periodos > 3:
            df_total_super.loc[:, "kurt_cons" + num_periodos_str] = df_total_super[cols_3_anterior].kurt(axis=1)

        return df_total_super


def fill_empty_values_cycle(df, cant_ciclos_validos, suffix: str = "_anterior"):
    cols_consumo = [f"{i}{suffix}" for i in range(cant_ciclos_validos, 0, -1)]

    df.loc[:, cols_consumo] = df.loc[:, cols_consumo].ffill(axis=1)
    df.loc[:, cols_consumo] = df.loc[:, cols_consumo].bfill(axis=1)
    return df


def fill_empty_values_str(df, cols, str_value):
    for x in cols:
        df.loc[:, x] = df[x].fillna(str_value)
    return df


def fill_empty_values_numeric(df, cols, numeric_value):
    for x in cols:
        df.loc[:, x] = df[x].fillna(numeric_value)
    return df


def build_feature_engineering_pipeline(f_names_path, num_periodos):
    pipe_feature_eng_train = Pipeline(
        [
            ("tsfel vars", TsfelVars("all", features_names_path=f_names_path, read=False, num_periodos=num_periodos)),
            ("add vars3", ExtraVars(None, read=False, num_periodos=3)),
            ("add vars6", ExtraVars(None, read=False, num_periodos=6)),
            ("add vars12", ExtraVars(None, read=False, num_periodos=12)),
        ]
    )
    return pipe_feature_eng_train
