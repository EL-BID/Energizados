"""
preprocessing.py Module

This module contains classes and functions used for data preprocessing before analysis.

Classes:
- ToDummy: Transforms categorical variables into dummy variables.
- TeEncoder: Encodes categorical variables using target encoding.
- CardinalityReducer: Reduces cardinality of categorical variables.
- MinMaxScalerRow: Applies Min-Max transformation to matrix rows.
- TsfelVars: Calculates features using tsfel library.
- ExtraVars: Creates additional features based on previous values.

Functions:
- fill_empty_values_cycle: Fills empty values in consumption columns with previous or subsequent
  values.
- fill_empty_values_str: Fills empty values in string columns with a specific value.
- fill_empty_values_numeric: Fills empty values in numeric columns with a specific value.
"""

import logging
import re
import warnings
from itertools import groupby

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, OneToOneFeatureMixin, TransformerMixin
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)


def _sanitize_feature_name(name):
    """Remove special JSON characters from feature name.

    LightGBM does not support special JSON characters in feature names:
    { } [ ] : , "

    Args:
        name: String to sanitize.

    Returns:
        Sanitized string with special characters replaced by underscore.
    """
    pattern = r'[{}\[\]:,"]'
    return re.sub(pattern, "_", str(name))


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
        """Learn the categories for each column.

        Args:
            X: Input DataFrame with columns to transform.
            y: Ignored. Kept for API compatibility.

        Returns:
            self: The fitted transformer.
        """
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
                name = _sanitize_feature_name(f"dummy_{col}_{cat}")
                names.append(name)
        return names

    def transform(self, X, y=None):
        """Apply one-hot encoding to columns.

        Args:
            X: Input DataFrame with columns to encode.
            y: Ignored. Kept for API compatibility.

        Returns:
            numpy.ndarray or scipy.sparse matrix: Encoded dummy columns.
        """
        # X is a DataFrame with only the columns to transform
        X_transformed = pd.DataFrame(index=X.index)

        for col in self.cols:
            # Create dummies only for this column
            dummies = pd.get_dummies(X[col], prefix=f"dummy_{col}", dtype=float)

            # Add missing columns (categories in train but not in test)
            for cat in self.categories_[col]:
                col_name = _sanitize_feature_name(f"dummy_{col}_{cat}")
                if col_name not in dummies.columns:
                    dummies[col_name] = 0

            # Remove extra columns (categories in test but not in train)
            cols_to_keep = [
                _sanitize_feature_name(f"dummy_{col}_{cat}") for cat in self.categories_[col]
            ]
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
        """Generate output column name."""
        if self.cols is None:
            return "target_enc_prob"
        return _sanitize_feature_name("_".join(self.cols) + "_prob")

    def fit(self, X, y=None):
        """Compute target encoding mapping from training data.

        Args:
            X: Input DataFrame with columns to encode.
            y: Target Series with binary labels (required for target encoding).

        Returns:
            self: The fitted transformer.
        """
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
        te[self.te_var_name] = ((te["mean"] * te["count"]) + (self.mean_global * self.w)) / (
            te["count"] + self.w
        )

        # Store only the necessary columns for merge
        self.te_mapping_ = te[self.cols + [self.te_var_name]]

        return self

    def transform(self, X):
        """Apply target encoding using the fitted mapping.

        Args:
            X: Input DataFrame with columns to encode.

        Returns:
            numpy.ndarray: 2D array with the encoded column values. Unseen
                categories are filled with the global target mean.
        """
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
        """Return categories whose frequency proportion meets the threshold.

        Args:
            feature: pandas Series with categorical values.

        Returns:
            numpy.ndarray: Array of category values that appear with frequency
                >= self.threshold.
        """
        proportions = feature.value_counts(normalize=True)
        categories = proportions[proportions >= self.threshold].index.values
        return categories

    def fit(self, X, y=None):
        """Learn the frequent categories for each column.

        Args:
            X: Input DataFrame with categorical columns.
            y: Ignored. Kept for API compatibility.

        Returns:
            self: The fitted transformer.
        """
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
        """Replace infrequent categories with 'otros'.

        Args:
            X: Input DataFrame with categorical columns.

        Returns:
            pd.DataFrame: DataFrame with infrequent categories replaced by 'otros'.
        """
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
        return (
            np.array([f"x{i}" for i in range(self.n_features_in_)])
            if hasattr(self, "n_features_in_")
            else np.array([])
        )


class CastDtype(OneToOneFeatureMixin, BaseEstimator, TransformerMixin):
    """
    Converts columns to a specific pandas dtype.

    Parameters:
    - dtype: str or pandas type, target dtype (e.g., 'float32', 'int8', 'category', 'bool').
    """

    def __init__(self, dtype="float32"):
        self.dtype = dtype

    def fit(self, X, y=None):
        """Record input feature names. No computation is performed.

        Args:
            X: Input DataFrame or array.
            y: Ignored. Kept for API compatibility.

        Returns:
            self: The fitted transformer.
        """
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.array(X.columns.tolist())
        return self

    def transform(self, X, y=None):
        """Cast all columns to the target dtype.

        Args:
            X: Input DataFrame.
            y: Ignored. Kept for API compatibility.

        Returns:
            pd.DataFrame: DataFrame with columns cast to self.dtype.
        """
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
        """Record input feature names. No computation is performed.

        Args:
            X: Input DataFrame or array.
            y: Ignored. Kept for API compatibility.

        Returns:
            self: The fitted transformer.
        """
        # Store column names for set_output support
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.array(X.columns.tolist())
        else:
            self.feature_names_in_ = None
        return self

    def transform(self, X):
        """Apply row-wise Min-Max scaling.

        Each row is independently scaled so that the minimum value in the row
        maps to feature_range[0] and the maximum to feature_range[1].

        Args:
            X: Input DataFrame or array.

        Returns:
            pd.DataFrame or numpy.ndarray: Row-scaled data with the same shape as X.
        """
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
        return (
            np.array([f"x{i}" for i in range(self.n_features_in_)])
            if hasattr(self, "n_features_in_")
            else np.array([])
        )


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
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")
                features = tsfel.time_series_features_extractor(cfg, values, fs=1, verbose=0)
        except Exception as e:
            # Constant/zero series can crash tsfel (e.g. ecdf_percentile on constant input).
            # Skip this row — the left join in transform() will leave its tsfel cols as NaN,
            # which are then filled with 0.
            logger.debug(
                f"TsfelVars: index {idx} raised {type(e).__name__} (likely constant/zero "
                f"series). values={values}. Row will be filled with 0."
            )
            continue
        null_count = features.isnull().sum().sum()
        if null_count > 0:
            null_cols = features.columns[features.isnull().any()].tolist()
            logger.debug(
                f"TsfelVars: index {idx} generated {null_count} nulls "
                f"(e.g., {null_cols[:3]}). values={values}"
            )
        features["index"] = idx
        results.append(features)
    if not results:
        # All rows in this chunk crashed (e.g. all-constant series).
        # Return empty DataFrame so the left join in transform() fills them with NaN → 0.
        return pd.DataFrame(columns=["index"])
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
        """Build consumption column names in chronological order.

        Args:
            num_cols: Number of periods to include.

        Returns:
            list: Column names like ['12_anterior', '11_anterior', ..., '1_anterior'].
        """
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
        chunks = [
            (data[i : i + self.chunk_size], indices[i : i + self.chunk_size])
            for i in range(0, n, self.chunk_size)
        ]

        logger.info(f"TsfelVars [{desc}]: {n} rows in {len(chunks)} chunks, n_jobs={self.n_jobs}")

        results = Parallel(n_jobs=self.n_jobs)(
            delayed(_tsfel_process_chunk)(chunk_values, chunk_indices, cfg)
            for chunk_values, chunk_indices in chunks
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
        """Extract tsfel features for a given domain.

        Args:
            df: Input DataFrame containing consumption columns.
            domain: tsfel domain name ('statistical', 'temporal', or 'spectral').
            cols: List of consumption column names to process.
            window: Number of periods (unused, kept for API compatibility).

        Returns:
            pd.DataFrame: Features extracted for the domain plus an 'index' column.
        """
        tsfel = _get_tsfel()
        cfg = tsfel.get_features_by_domain(domain)
        return self._run_parallel(df, cols, cfg, desc=domain)

    def compute_by_json(self, df, cols, window=12):
        """Extract tsfel features using a custom JSON configuration.

        Args:
            df: Input DataFrame containing consumption columns.
            cols: List of consumption column names to process.
            window: Number of periods (unused, kept for API compatibility).

        Returns:
            pd.DataFrame: Features extracted from the JSON config plus an 'index' column.
        """
        tsfel = _get_tsfel()
        cfg = tsfel.get_features_by_domain(json_path=self.features_names_path)
        return self._run_parallel(df, cols, cfg, desc="tsfel_json")

    def crear_all_tsfel(self, df):
        """Extract statistical and temporal tsfel features for all periods.

        Args:
            df: Input DataFrame with consumption columns.

        Returns:
            tuple: (df_result_stat, df_result_temporal) — two DataFrames with
                statistical and temporal features respectively.
        """
        cols_anterior = self.obtener_cols_anterior(self.num_periodos)
        df_result_stat = self.extra_cols(df, "statistical", cols_anterior, window=self.num_periodos)
        df_result_temporal = self.extra_cols(
            df, "temporal", cols_anterior, window=self.num_periodos
        )
        # df_result_spectral = self.extra_cols(
        #     df, "spectral", cols_anterior, window=self.num_periodos
        # )
        self.temp_vars = [c for c in df_result_temporal.columns if c != "index"]
        self.stat_vars = [c for c in df_result_stat.columns if c != "index"]
        # self.spec_vars = [c for c in df_result_spectral.columns if c != "index"]
        return df_result_stat, df_result_temporal  # , df_result_spectral

    def fit(self, X, y=None):
        """No-op fit. TsfelVars is stateless and does not learn from training data.

        Args:
            X: Input DataFrame (not used).
            y: Ignored. Kept for API compatibility.

        Returns:
            self: Returns the transformer unchanged.
        """
        return self

    def transform(self, X):
        """Extract time series features and append them to the DataFrame.

        Rows with constant consumption (max == min across all periods) are skipped
        from tsfel processing and receive 0 for all tsfel features. They are never
        removed from the output — index and row order are fully preserved.

        Args:
            X: Input DataFrame with consumption columns (e.g., '12_anterior', ..., '1_anterior').

        Returns:
            pd.DataFrame: Original DataFrame with new tsfel-derived feature columns appended.
        """
        cached_compute = self._get_cached_transform()
        cols_anterior = self.obtener_cols_anterior(self.num_periodos)

        # Detect constant-consumption rows: max == min means std == 0, so kurtosis/skewness
        # are undefined. We skip tsfel for these rows and fill with 0.
        cons = X[cols_anterior]
        is_constant = cons.max(axis=1) == cons.min(axis=1)
        X_variable = X[~is_constant]
        n_constant = int(is_constant.sum())

        if n_constant > 0:
            logger.debug(
                f"TsfelVars: {n_constant} rows with constant consumption — "
                f"tsfel skipped, features set to 0."
            )

        if self.features_names_path is not None:
            df_tsfel = cached_compute(
                X_variable[cols_anterior].values,
                X_variable.index.tolist(),
                cols_anterior,
                cfg_json_path=self.features_names_path,
            )
            df_tsfel = df_tsfel.set_index("index")
            tsfel_cols = df_tsfel.columns.tolist()
        else:
            df_result_stat = cached_compute(
                X_variable[cols_anterior].values,
                X_variable.index.tolist(),
                cols_anterior,
                cfg_domain="statistical",
            )
            df_result_temporal = cached_compute(
                X_variable[cols_anterior].values,
                X_variable.index.tolist(),
                cols_anterior,
                cfg_domain="temporal",
            )
            df_tsfel = pd.merge(df_result_stat, df_result_temporal, how="inner", on="index")
            df_tsfel = df_tsfel.set_index("index")
            tsfel_cols = df_tsfel.columns.tolist()

        # Add constant rows back with 0 for all tsfel features
        if n_constant > 0 and tsfel_cols:
            df_constant = pd.DataFrame(0.0, index=X[is_constant].index, columns=tsfel_cols)
            df_tsfel = pd.concat([df_tsfel, df_constant])

        X = X.join(df_tsfel, how="left")

        # Residual NaN guard (e.g. tsfel crashed mid-chunk on a non-constant row)
        nan_counts = X[tsfel_cols].isnull().sum()
        nan_cols = nan_counts[nan_counts > 0]
        if len(nan_cols) > 0:
            logger.warning(
                f"TsfelVars: {len(nan_cols)} tsfel columns still have NaN after constant-row "
                f"handling ({len(X)} rows). Top: {nan_cols.nlargest(5).to_dict()}. Filling with 0."
            )
            X[tsfel_cols] = X[tsfel_cols].fillna(0)

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
        """No-op fit. ExtraVars is stateless and does not learn from training data.

        Args:
            X: Input DataFrame (not used).
            y: Ignored. Kept for API compatibility.

        Returns:
            self: Returns the transformer unchanged.
        """
        return self

    def obtener_cols_anterior(self, num_cols=12):
        """Build consumption column names in chronological order.

        Args:
            num_cols: Number of periods to include.

        Returns:
            list: Column names like ['12_anterior', '11_anterior', ..., '1_anterior'].
        """
        return [f"{i}{self.periods_suffix}" for i in range(num_cols, 0, -1)]

    def transform(self, X):
        """Compute and append statistical features to the DataFrame.

        Args:
            X: Input DataFrame with consumption columns.

        Returns:
            pd.DataFrame: Original DataFrame with new feature columns appended.
        """
        return self.create_vbles(X.copy())

    def count_cero(self, x):
        """Count how many values in the Series are zero.

        Args:
            x: pandas Series of numeric consumption values.

        Returns:
            int: Number of zero values.
        """
        return (x == 0.0).sum()

    def count_cero_seguidos(self, x):
        """Find the maximum run length of consecutive zeros.

        Args:
            x: pandas Series of numeric consumption values.

        Returns:
            int: Length of the longest consecutive zero run, or 0 if none.
        """
        ceros_seguidos = 2
        consumo = x.values
        g = [[k, len(list(v))] for k, v in groupby(consumo)]
        g = [x for x in g if (x[0] == 0.0) & (x[1] >= ceros_seguidos)]
        if any(g):
            return sorted(g, reverse=True, key=lambda x: x[-1])[0][1]
        else:
            return 0

    def calc_slope(self, x):
        """Compute the linear regression slope of a consumption series.

        Args:
            x: pandas Series of numeric consumption values.

        Returns:
            float: Slope of the best-fit line.
        """
        consumo = list(x.values)
        slope = np.polyfit(range(len(consumo)), consumo, 1)[0]
        return slope

    def create_vbles(self, df_total_super):
        """Compute and append all statistical features to the DataFrame.

        Adds mean, zero counts, consecutive zero runs, slope, min, max, std,
        variance, skewness, and (if num_periodos > 3) kurtosis.

        Args:
            df_total_super: Input DataFrame with consumption columns.

        Returns:
            pd.DataFrame: DataFrame with new feature columns appended in place.
        """
        # generate list of cols from back to front i.e: ['3_anterior', '2_anterior', '1_anterior']
        cols_3_anterior = self.obtener_cols_anterior(num_cols=self.num_periodos)
        num_periodos_str = str(self.num_periodos)
        # averages
        df_total_super.loc[:, "mean_" + num_periodos_str] = df_total_super[cols_3_anterior].mean(
            axis=1
        )
        # Zero count
        df_total_super.loc[:, "cant_ceros_" + num_periodos_str] = df_total_super[
            cols_3_anterior
        ].apply(self.count_cero, axis=1)
        df_total_super.loc[:, "max_cant_ceros_seg_" + num_periodos_str] = df_total_super[
            cols_3_anterior
        ].apply(self.count_cero_seguidos, axis=1)
        # Slope
        df_total_super.loc[:, "slope_" + num_periodos_str] = df_total_super[cols_3_anterior].apply(
            self.calc_slope, axis=1
        )
        # Min, Max, STD, Variance for 3 periods
        df_total_super.loc[:, "min_cons" + num_periodos_str] = df_total_super[cols_3_anterior].min(
            axis=1
        )
        df_total_super.loc[:, "max_cons" + num_periodos_str] = df_total_super[cols_3_anterior].max(
            axis=1
        )
        df_total_super.loc[:, "std_cons" + num_periodos_str] = df_total_super[cols_3_anterior].std(
            axis=1
        )
        df_total_super.loc[:, "var_cons" + num_periodos_str] = df_total_super[cols_3_anterior].var(
            axis=1
        )
        # skewness and kurtosis for 3 periods
        # fillna(0): pandas returns NaN for constant/zero series (std=0), 0 is the correct value
        df_total_super.loc[:, "skew_cons" + num_periodos_str] = (
            df_total_super[cols_3_anterior].skew(axis=1).fillna(0)
        )
        if self.num_periodos > 3:
            df_total_super.loc[:, "kurt_cons" + num_periodos_str] = (
                df_total_super[cols_3_anterior].kurt(axis=1).fillna(0)
            )

        return df_total_super


def fill_empty_values_cycle(df, cant_ciclos_validos, suffix: str = "_anterior"):
    """Fill missing values in consumption columns using forward and backward fill.

    Fills nulls row-wise: first forward-fill across periods (left to right),
    then backward-fill so that leading nulls are also covered.

    Args:
        df: Input DataFrame with consumption columns.
        cant_ciclos_validos: Number of consumption periods to process.
        suffix: Suffix identifying consumption columns (default "_anterior").

    Returns:
        pd.DataFrame: DataFrame with null values in consumption columns filled.
    """
    cols_consumo = [f"{i}{suffix}" for i in range(cant_ciclos_validos, 0, -1)]

    df.loc[:, cols_consumo] = df.loc[:, cols_consumo].ffill(axis=1)
    df.loc[:, cols_consumo] = df.loc[:, cols_consumo].bfill(axis=1)
    return df


def fill_empty_values_str(df, cols, str_value: str = "sin_dato"):
    """Fill missing values in string columns with a fixed string.

    Args:
        df: Input DataFrame.
        cols: List of column names to fill.
        str_value: String value to use as fill.

    Returns:
        pd.DataFrame: DataFrame with nulls in the specified columns replaced by str_value.
    """
    for x in cols:
        df.loc[:, x] = df[x].fillna(str_value)
    return df


def fill_empty_values_numeric(df, cols, numeric_value):
    """Fill missing values in numeric columns with a fixed number.

    Args:
        df: Input DataFrame.
        cols: List of column names to fill.
        numeric_value: Numeric value to use as fill.

    Returns:
        pd.DataFrame: DataFrame with nulls in the specified columns replaced by numeric_value.
    """
    for x in cols:
        df.loc[:, x] = df[x].fillna(numeric_value)
    return df
