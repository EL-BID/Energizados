"""
Feature Selection Methods for Energizados Framework.

Implementaciones de métodos de selección de características basadas
en el código existente del proyecto.
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
    Selector de variables basado en correlación.

    Elimina variables altamente correlacionadas entre sí, manteniendo
    la que tiene mayor correlación con el target.

    Args:
        method: Método de correlación ('pearson', 'spearman', 'kendall')
        threshold: Umbral de correlación para eliminar variables (0.9 por defecto)
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
        Aprende qué variables eliminar por alta correlación.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento

        Returns:
            self
        """
        # Convert numpy array to DataFrame if needed
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        # Filter out non-numeric columns (datetime, object, etc.)
        X = X.select_dtypes(include=[np.number])
        logger.info(f"Filtered to {X.shape[1]} numeric columns for correlation analysis")

        X = X.copy()
        variables = X.columns.tolist()

        logger.info("Calculando Correlación Entre Variables")
        X["target"] = y.values
        df_corr = X[variables + ["target"]].corr(method=self.method)

        # Buscar variables más correlacionadas
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

        logger.info(f"Eliminando {len(self.vars_to_drop_)} Variables Altamente Correlacionadas")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma X eliminando variables correlacionadas.

        Args:
            X: DataFrame a transformar

        Returns:
            pd.DataFrame: DataFrame sin variables altamente correlacionadas
        """
        if self.selected_features_ is None:
            raise ValueError("Debe llamar a fit() primero")
        return X[self.selected_features_].copy()


class ConstantSelector(BaseFeatureSelector):
    """
    Selector que elimina variables con valores constantes.

    Elimina variables donde un mismo valor representa más del
    porcentaje especificado de las filas.

    Args:
        threshold: Umbral de variabilidad (0.99 por defecto).
                   Una variable se elimina si un valor representa
                   más de este porcentaje de las filas.
    """

    def __init__(self, threshold: float = 0.99, config: Optional[dict] = None):
        super().__init__(config)
        self.threshold = threshold
        self.vars_to_drop_ = None

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: pd.Series) -> "ConstantSelector":
        """
        Aprende qué variables son constantes.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento (no usado en este método)

        Returns:
            self
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

        logger.info(f"Eliminando {len(self.vars_to_drop_)} Variables Constantes")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma X eliminando variables constantes.

        Args:
            X: DataFrame a transformar

        Returns:
            pd.DataFrame: DataFrame sin variables constantes
        """
        if self.selected_features_ is None:
            raise ValueError("Debe llamar a fit() primero")
        return X[self.selected_features_].copy()


class BorutaSelector(BaseFeatureSelector):
    """
    Selector de variables usando el algoritmo Boruta.

    Boruta es un algoritmo de selección de features que compara
    la importancia de variables originales con variables aleatorias
    ("shadow features") para determinar cuáles son realmente importantes.

    Args:
        n_estimators: Número de árboles en el RandomForest
        max_depth: Profundidad máxima de los árboles
        max_iter: Número de iteraciones para ejecutar Boruta
        perc: Percentil para features confirmados (default: 100)
        random_state: Semilla aleatoria
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
        self.n_runs_ = 10  # Número de ejecuciones para estabilidad

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: pd.Series) -> "BorutaSelector":
        """
        Aprende qué variables seleccionar usando Boruta.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento

        Returns:
            self
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
        for i in tqdm(range(self.n_runs_), total=self.n_runs_, desc="Ejecutando Boruta"):
            # Agregar variable aleatoria como shadow feature
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

            # Variables hasta el "random"
            random_idx = ranking[ranking.col == "random"].index
            if len(random_idx) > 0:
                random_rank = ranking[ranking.col == "random"]["ranking"].values[0]
                variables = ranking[ranking.ranking < random_rank].col.values
            else:
                variables = ranking.columns.values

            d[i] = variables

        # Contar cuántas veces apareció cada variable
        E = {}
        for i in d.keys():
            for var in d[i]:
                if var not in E.keys():
                    E[var] = 1
                else:
                    E[var] += 1

        # Variables que aparecen en al menos la mitad de las ejecuciones
        self.selected_features_ = [k for k in E.keys() if E[k] >= self.n_runs_ // 2]
        self.selected_features_ = [v for v in self.selected_features_ if v != "random"]

        logger.info(f"Seleccionadas {len(self.selected_features_)} variables por Boruta")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma X dejando solo las variables seleccionadas.

        Args:
            X: DataFrame a transformar

        Returns:
            pd.DataFrame: DataFrame con variables seleccionadas
        """
        if self.selected_features_ is None:
            raise ValueError("Debe llamar a fit() primero")

        # Asegurar que todas las variables existan
        available_features = [f for f in self.selected_features_ if f in X.columns]
        return X[available_features].copy()


def feature_selection_by_correlation(x_train, y_train, variables, method="pearson", th=0.9):
    """
    Función legada para compatibilidad con código existente.

    .. deprecated::
        Use CorrelationSelector en su lugar.
    """
    selector = CorrelationSelector(method=method, threshold=th)
    selector.fit(x_train[variables], y_train)
    return selector.get_selected_features()


def feature_selection_by_constant(x_train, y_train, variables, th=0.99):
    """
    Función legada para compatibilidad con código existente.

    .. deprecated::
        Use ConstantSelector en su lugar.
    """
    selector = ConstantSelector(threshold=th)
    selector.fit(x_train[variables], y_train)
    return selector.get_selected_features()


def feature_selection_by_boruta(X_train, y_train, N=10):
    """
    Función legada para compatibilidad con código existente.

    .. deprecated::
        Use BorutaSelector en su lugar.
    """
    selector = BorutaSelector(max_iter=N, n_runs_=N)
    selector.fit(X_train, y_train)
    return selector.get_selected_features()
