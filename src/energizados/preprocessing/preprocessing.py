"""
Módulo preprocessing.py

Este módulo contiene clases y funciones utilizadas para el preprocesamiento de datos antes de su análisis.

Clases:
- ToDummy: Transforma variables categóricas en variables dummy.
- TeEncoder: Codifica variables categóricas utilizando target encoding.
- CardinalityReducer: Reduce la cardinalidad de variables categóricas.
- MinMaxScalerRow: Aplica la transformación Min-Max a las filas de una matriz.
- TsfelVars: Calcula características utilizando la biblioteca tsfel.
- ExtraVars: Crea características adicionales basadas en los valores anteriores.

Funciones:
- fill_empty_values_cycle: Rellena los valores vacíos en las columnas de consumo con los valores anteriores o posteriores.
- fill_empty_values_str: Rellena los valores vacíos en columnas de tipo string con un valor específico.
- fill_empty_values_numeric: Rellena los valores vacíos en columnas numéricas con un valor específico.
- build_feature_engineering_pipeline: Construye una tubería de preprocesamiento para la ingeniería de características.
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


# tsfel se importa de forma lazy para evitar problemas de compatibilidad con scipy
def _get_tsfel():
    """Importa tsfel de forma lazy."""
    import tsfel

    return tsfel


class ToDummy(BaseEstimator, TransformerMixin):
    """
    Transforma variables categóricas en variables dummy.

    Parámetros:
    - cols: list, lista de columnas que se convertirán en variables dummy.
    - sparse: bool, si True devuelve matriz sparse (default=False)
    """

    def __init__(self, cols=None, sparse=False):
        self.cols = cols
        self.sparse = sparse

    def fit(self, X, y=None):
        # X es un DataFrame con solo las columnas a transformar
        if self.cols is None:
            self.cols = X.columns.tolist()

        # Guardar categorías vistas durante fit
        self.categories_ = {}
        for col in self.cols:
            self.categories_[col] = set(X[col].unique())

        # Generar nombres de columnas dummy
        self.dummy_names_ = self._generate_dummy_names(self.categories_)
        return self

    def _generate_dummy_names(self, categories):
        """Genera nombres de columnas dummy basado en las categorías"""
        names = []
        for col, cats in categories.items():
            for cat in cats:
                names.append(f"dummy_{col}_{cat}")
        return names

    def transform(self, X, y=None):
        # X es un DataFrame con solo las columnas a transformar
        X_transformed = pd.DataFrame(index=X.index)

        for col in self.cols:
            # Crear dummies solo para esta columna
            dummies = pd.get_dummies(X[col], prefix=f"dummy_{col}", dtype=float)

            # Agregar columnas faltantes (categorías en train pero no en test)
            for cat in self.categories_[col]:
                col_name = f"dummy_{col}_{cat}"
                if col_name not in dummies.columns:
                    dummies[col_name] = 0

            # Eliminar columnas extra (categorías en test pero no en train)
            cols_to_keep = [f"dummy_{col}_{cat}" for cat in self.categories_[col]]
            dummies = dummies[cols_to_keep]

            X_transformed = pd.concat([X_transformed, dummies], axis=1)

        # Devolver en el orden correcto y como array numpy
        X_transformed = X_transformed[self.dummy_names_]

        if self.sparse:
            from scipy import sparse

            return sparse.csr_matrix(X_transformed.values)

        return X_transformed.values

    def get_feature_names_out(self, input_features=None):
        """Metodo requerido por scikit-learn 1.2+ para set_output"""
        return self.dummy_names_


class TeEncoder(BaseEstimator, TransformerMixin):
    """
    Codifica variables categóricas utilizando target encoding.

    Parámetros:
    - cols: list, lista de columnas que se codificarán.
    - w: int, peso para el cálculo del target encoding (suavizado).
    """

    def __init__(self, cols=None, w=20):
        self.cols = cols
        self.w = w
        self.te_var_name = None

    def _generate_output_name(self):
        """Genera el nombre de la columna de salida"""
        if self.cols is None:
            return "target_enc_prob"
        return "_".join(self.cols) + "_prob"

    def fit(self, X, y=None):
        # X es un DataFrame con solo las columnas a codificar
        if self.cols is None:
            self.cols = X.columns.tolist()

        self.te_var_name = self._generate_output_name()
        self.mean_global = y.mean()

        # Crear mapping sin modificar X original
        df = X.copy()
        df["target"] = y.values

        # Agrupar y calcular target encoding con suavizado
        te = df.groupby(self.cols)["target"].agg(["mean", "count"]).reset_index()
        te[self.te_var_name] = ((te["mean"] * te["count"]) + (self.mean_global * self.w)) / (te["count"] + self.w)

        # Guardar solo las columnas necesarias para el merge
        self.te_mapping_ = te[self.cols + [self.te_var_name]]

        return self

    def transform(self, X):
        # X es un DataFrame con solo las columnas a codificar
        X_copy = X.copy()

        # Hacer merge con el mapping
        X_copy = X_copy.merge(self.te_mapping_, on=self.cols, how="left")

        # Rellenar NaNs con la media global
        X_copy[self.te_var_name] = X_copy[self.te_var_name].fillna(self.mean_global)

        # Devolver solo la columna codificada como numpy array (2D)
        return X_copy[[self.te_var_name]].values

    def get_feature_names_out(self, input_features=None):
        """Método requerido por scikit-learn 1.2+ para set_output"""
        if self.te_var_name is None:
            self.te_var_name = self._generate_output_name()
        return np.array([self.te_var_name])


class CardinalityReducer(OneToOneFeatureMixin, BaseEstimator, TransformerMixin):
    """
    Clase CardinalityReducer

    Transformador para reducir la cardinalidad de variables categóricas.

    Parámetros:
    - cols: list, lista de columnas categóricas a reducir su cardinalidad.
    - threshold: int, límite de frecuencia para agrupar categorías poco frecuentes en una categoría "otro".
    """

    def __init__(self, threshold=0.1):
        self.threshold = threshold

    def find_top_categories(self, feature):
        proportions = feature.value_counts(normalize=True)
        categories = proportions[proportions >= self.threshold].index.values
        return categories

    def fit(self, X, y=None):
        # Guardar nombres de columnas para soporte de set_output
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
        Método requerido por scikit-learn 1.2+ para set_output.
        Devuelve los nombres de las características de salida (iguales a las de entrada).
        """
        if input_features is not None:
            return input_features
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        # Fallback: generar nombres genéricos si no se guardaron
        return np.array([f"x{i}" for i in range(self.n_features_in_)]) if hasattr(self, "n_features_in_") else np.array([])


class CastDtype(OneToOneFeatureMixin, BaseEstimator, TransformerMixin):
    """
    Convierte columnas a un tipo de dato pandas específico.

    Parámetros:
    - dtype: str o tipo pandas, dtype destino (ej: 'float32', 'int8', 'category', 'bool').
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
    Clase MinMaxScalerRow

    Transformador para escalar las filas de una matriz utilizando Min-Max Scaling.

    Parámetros:
    - feature_range: tuple, rango de valores para el escalado.
    """

    def __init__(self, feature_range=(0, 1)):
        self.feature_range = feature_range

    def fit(self, X, y=None):
        # Guardar nombres de columnas para soporte de set_output
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.array(X.columns.tolist())
        else:
            self.feature_names_in_ = None
        return self

    def transform(self, X):
        scaler = MinMaxScaler(feature_range=self.feature_range)
        X_scaled = scaler.fit_transform(X.T).T

        # Si X es un DataFrame, devolver un DataFrame con los mismos nombres e índice
        if hasattr(X, "columns") and hasattr(X, "index"):
            import pandas as pd

            return pd.DataFrame(X_scaled, columns=X.columns, index=X.index)

        return X_scaled

    def get_feature_names_out(self, input_features=None):
        """
        Método requerido por scikit-learn 1.2+ para set_output.
        Devuelve los nombres de las características de salida (iguales a las de entrada).
        """
        if input_features is not None:
            return input_features
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        # Fallback: generar nombres genéricos si no se guardaron
        return np.array([f"x{i}" for i in range(self.n_features_in_)]) if hasattr(self, "n_features_in_") else np.array([])


def _tsfel_process_chunk(chunk_values, chunk_indices, cfg):
    """
    Procesa un chunk de filas con tsfel. Función a nivel de módulo para ser
    serializable por joblib en modo multiprocessing.

    Args:
        chunk_values: numpy array (N_filas, N_periodos)
        chunk_indices: lista de índices originales del DataFrame
        cfg: configuración de tsfel (resultado de get_features_by_domain)

    Returns:
        pd.DataFrame con features extraídas + columna 'index'
    """
    tsfel = _get_tsfel()
    results = []
    for idx, values in zip(chunk_indices, chunk_values):
        features = tsfel.time_series_features_extractor(cfg, values, fs=1, verbose=0)
        null_count = features.isnull().sum().sum()
        if null_count > 0:
            null_cols = features.columns[features.isnull().any()].tolist()
            logger.warning(f"TsfelVars: índice {idx} generó {null_count} nulos " f"(ej: {null_cols[:3]}). values={values}")
        features["index"] = idx
        results.append(features)
    return pd.concat(results, ignore_index=True)


class TsfelVars(BaseEstimator, TransformerMixin):
    """
    Transformador para extraer características de series de tiempo usando tsfel.

    Parámetros:
    - features_names_path: str o None, path a JSON con config custom de tsfel.
    - num_periodos: int, número de periodos de consumo a usar (default=12).
    - periods_suffix: str, sufijo de las columnas de consumo (default="_anterior").
    - n_jobs: int, número de procesos paralelos. 1=secuencial, -1=todos los cores.
    - chunk_size: int, filas por chunk enviadas a cada worker (default=500).
    - cache_dir: str o None, directorio para cachear resultados en disco.
      Si None, no se cachea. Útil para experimentación iterativa.
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
        Divide df en chunks y los procesa en paralelo (o secuencial si n_jobs=1).

        Args:
            df: DataFrame completo
            cols: columnas de consumo a usar
            cfg: configuración de tsfel
            desc: descripción para la barra de progreso

        Returns:
            pd.DataFrame con todas las features concatenadas + columna 'index'
        """
        from joblib import Parallel, delayed

        data = df[cols].values
        indices = df.index.tolist()
        n = len(df)

        # Dividir en chunks
        chunks = [(data[i : i + self.chunk_size], indices[i : i + self.chunk_size]) for i in range(0, n, self.chunk_size)]

        logger.info(f"TsfelVars [{desc}]: {n} filas en {len(chunks)} chunks, n_jobs={self.n_jobs}")

        results = Parallel(n_jobs=self.n_jobs)(
            delayed(_tsfel_process_chunk)(chunk_values, chunk_indices, cfg) for chunk_values, chunk_indices in tqdm(chunks, desc=desc)
        )

        return pd.concat(results, ignore_index=True)

    def _get_cached_transform(self):
        """Retorna versión cacheada de _compute si cache_dir está configurado."""
        if self.cache_dir is not None:
            from joblib import Memory

            memory = Memory(location=self.cache_dir, verbose=0)
            return memory.cache(self._compute)
        return self._compute

    def _compute(self, df_values, df_indices, cols, cfg_domain=None, cfg_json_path=None):
        """
        Núcleo del cómputo, separado para permitir caching con joblib.Memory.

        Args:
            df_values: numpy array con los valores de las columnas de consumo
            df_indices: lista de índices originales
            cols: nombres de columnas (para reconstruir DataFrame)
            cfg_domain: nombre del dominio tsfel ('statistical', 'temporal', etc.)
            cfg_json_path: path a JSON de config tsfel (mutuamente excluyente con cfg_domain)
        """
        tsfel = _get_tsfel()
        if cfg_json_path is not None:
            cfg = tsfel.get_features_by_domain(json_path=cfg_json_path)
            desc = "tsfel_json"
        else:
            cfg = tsfel.get_features_by_domain(cfg_domain)
            desc = cfg_domain

        # Reconstruir DataFrame temporal para _run_parallel
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
                X.index.tolist(),
                cols_anterior,
                cfg_json_path=self.features_names_path,
            )
            X = X.merge(df_tsfel, on="index", how="left")
        else:
            df_result_stat = cached_compute(
                X[cols_anterior].values,
                X.index.tolist(),
                cols_anterior,
                cfg_domain="statistical",
            )
            df_result_temporal = cached_compute(
                X[cols_anterior].values,
                X.index.tolist(),
                cols_anterior,
                cfg_domain="temporal",
            )
            # df_result_spectral = cached_compute(..., cfg_domain="spectral")
            df_tsfel = pd.merge(df_result_stat, df_result_temporal, how="inner", on="index")
            # df_tsfel = pd.merge(df_tsfel, df_result_spectral, how='inner', on='index')
            X = X.merge(df_tsfel, on="index", how="left")

        return X


class ExtraVars(BaseEstimator, TransformerMixin):
    """
    Clase ExtraVars

    Transformador para generar variables adicionales basadas en datos de series de tiempo.

    Parámetros:
    - aggregation_functions: dict, diccionario que mapea el nombre de la nueva variable con una función de agregación.
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
        # generar listado de cols de atras hacia delante i.e: ['3_anterior', '2_anterior', '1_anterior'], etc.
        cols_3_anterior = self.obtener_cols_anterior(num_cols=self.num_periodos)
        num_periodos_str = str(self.num_periodos)
        # promedios
        df_total_super.loc[:, "mean_" + num_periodos_str] = df_total_super[cols_3_anterior].mean(axis=1)
        # Cantidad de ceros
        df_total_super.loc[:, "cant_ceros_" + num_periodos_str] = df_total_super[cols_3_anterior].apply(self.count_cero, axis=1)
        df_total_super.loc[:, "max_cant_ceros_seg_" + num_periodos_str] = df_total_super[cols_3_anterior].apply(
            self.count_cero_seguidos, axis=1
        )
        # Slope
        df_total_super.loc[:, "slope_" + num_periodos_str] = df_total_super[cols_3_anterior].apply(self.calc_slope, axis=1)
        # Min, Max, STD, Varianza 3 periodos
        df_total_super.loc[:, "min_cons" + num_periodos_str] = df_total_super[cols_3_anterior].min(axis=1)
        df_total_super.loc[:, "max_cons" + num_periodos_str] = df_total_super[cols_3_anterior].max(axis=1)
        df_total_super.loc[:, "std_cons" + num_periodos_str] = df_total_super[cols_3_anterior].std(axis=1)
        df_total_super.loc[:, "var_cons" + num_periodos_str] = df_total_super[cols_3_anterior].var(axis=1)
        # skewness y kurtosis 3 periodos
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
