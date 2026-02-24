"""
Default Feature Engineering Implementation for Energizados Framework.

Este módulo proporciona una implementación por defecto que combina
preprocessing y feature_selection en un solo paso unificado.
"""

import logging
from typing import Dict, Optional

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from energizados.feature_engineering.base import BaseFeatureEngineering
from energizados.feature_selection.methods import (
    BorutaSelector,
    ConstantSelector,
    CorrelationSelector,
)
from energizados.preprocessing.preprocessing import (
    CardinalityReducer,
    TeEncoder,
    ToDummy,
)

logger = logging.getLogger(__name__)


def _build_transformer_from_config(transform_name: str, params: dict, column: str):
    """
    Construye un transformer desde config YAML.

    Args:
        transform_name: Nombre del transformer en YAML
        params: Diccionario de parámetros desde YAML
        column: Nombre de la columna a transformar

    Returns:
        Instancia del transformer configurado
    """
    from sklearn.preprocessing import OrdinalEncoder

    from energizados.preprocessing.preprocessing import MinMaxScalerRow

    # Mapeo de nombres a (clase, params_default)
    transformer_map = {
        "cardinality_reducer": (CardinalityReducer, {"threshold": 0.001}),
        "to_dummy": (ToDummy, {}),
        "target_encoding": (TeEncoder, {"w": 20}),
        "ordinal_encoding": (
            OrdinalEncoder,
            {"handle_unknown": "use_encoded_value", "unknown_value": -1},
        ),
        "minmax_scaler_row": (MinMaxScalerRow, {"feature_range": (0, 1)}),
    }

    if transform_name not in transformer_map:
        raise ValueError(f"Transformer desconocido: {transform_name}. " f"Opciones disponibles: {list(transformer_map.keys())}")

    cls, default_params = transformer_map[transform_name]
    params = {**default_params, **(params or {})}

    # Special handling para transformers que necesitan column name
    if transform_name in ["to_dummy", "target_encoding"]:
        params["cols"] = [column]

    return cls(**params)


def get_preprocesor(preprocessing_config: dict) -> ColumnTransformer:
    """
    Construye el preprocesador desde config YAML.

    Args:
        preprocessing_config: Dict con configuración de preprocessing.
                              Requiere 'columns': dict mapeando columna→lista de transformaciones

    Returns:
        ColumnTransformer: Preprocesador configurado

    Raises:
        ValueError: Si no se encuentra configuración válida
    """
    # MODO NUEVO: Configuración por columna
    # Verificar si 'columns' key existe (incluso si está vacío)
    if "columns" in preprocessing_config:
        columns_config = preprocessing_config["columns"]
        if not columns_config:
            raise ValueError("El config 'columns' no puede estar vacío. Especifica al menos una columna con sus transformaciones.")

        transformers = []

        for column, transformations in columns_config.items():
            # Construir Pipeline secuencial para esta columna
            steps = []
            for transform_config in transformations:
                for transform_name, params in transform_config.items():
                    transformer = _build_transformer_from_config(transform_name, params, column)
                    steps.append((transform_name, transformer))

            if steps:
                pipeline = Pipeline(steps)
                transformers.append((f"{column}_pipeline", pipeline, [column]))

        # ColumnTransformer con passthrough para columnas no mencionadas
        return ColumnTransformer(transformers=transformers, remainder="passthrough")

    # Error si no hay configuración válida
    raise ValueError("Configuración de preprocessing inválida. Se requiere 'columns' con la configuración por columna. ")


class DefaultFeatureEngineering(BaseFeatureEngineering):
    """
    Implementación por defecto del Feature Engineering.

    Combina preprocessing (codificación de variables categóricas)
    y feature selection (métodos como Boruta, correlación, constantes)
    en un solo paso.

    Attributes:
        preprocessor: Pipeline de preprocessing (scikit-learn ColumnTransformer)
        selector: Selector de features (BorutaSelector, CorrelationSelector, etc.)
        preprocessing_config: Configuración de preprocessing
        feature_selection_config: Configuración de feature selection
    """

    def __init__(
        self,
        preprocessing_config: Optional[Dict] = None,
        feature_selection_config: Optional[Dict] = None,
        config: Optional[Dict] = None,
    ):
        """
        Inicializa el Feature Engineering por defecto.

        Args:
            preprocessing_config: Configuración de preprocessing (nuevo formato con 'columns')
            feature_selection_config: Configuración de feature selection
            config: Diccionario de configuración general (opcional)
        """
        super().__init__(config)

        # Construir preprocessing_config desde config si no se proporciona
        if preprocessing_config is None:
            preprocessing_config = self.config.get("preprocessing", {})

        self.preprocessing_config = preprocessing_config
        self.feature_selection_config = feature_selection_config or self.config.get("feature_selection", {})
        self.preprocessor = None
        self.selector = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "DefaultFeatureEngineering":
        """
        Aprende las transformaciones de preprocessing y feature selection.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento

        Returns:
            self: Retorna la instancia entrenada
        """
        logger.info("Iniciando fit del Feature Engineering...")

        # 1. Construir y ajustar preprocesador
        logger.info("Construyendo preprocesador desde configuración...")
        self.preprocessor = get_preprocesor(self.preprocessing_config)

        logger.info("Aplicando preprocessing de entrenamiento...")
        X_prep = self.preprocessor.fit_transform(X, y)

        logger.info(f"Features después de preprocessing: {X_prep.shape[1]}")

        # 2. Feature Selection (si está habilitado)
        if self.feature_selection_config.get("enabled", True):
            logger.info("Aplicando feature selection...")
            self.selector = self._build_selector()
            self.selector.fit(X_prep, y)
            logger.info(f"Features seleccionadas: {len(self.selector.get_selected_features())}")
        else:
            logger.info("Feature selection deshabilitado, usando todas las features")
            self.selector = None

        self.is_fitted_ = True
        logger.info("Fit del Feature Engineering completado")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica preprocessing y feature selection a los datos.

        Args:
            X: DataFrame a transformar

        Returns:
            pd.DataFrame: DataFrame transformado

        Raises:
            ValueError: Si fit() no fue llamado previamente
        """
        self.check_fitted()

        # 1. Aplicar preprocessing
        X_prep = self.preprocessor.transform(X)

        # 2. Aplicar feature selection si está habilitado
        if self.selector is not None:
            X_transformed = self.selector.transform(X_prep)
            return X_transformed

        return X_prep

    def _build_selector(self):
        """
        Construye el selector de features según la configuración.

        Returns:
            BaseFeatureSelector: Selector configurado
        """
        method = self.feature_selection_config.get("method", "boruta")
        params = self.feature_selection_config.get("params", {})

        if method == "boruta":
            return BorutaSelector(**params)
        elif method == "correlation":
            return CorrelationSelector(**params)
        elif method == "constant":
            return ConstantSelector(**params)
        else:
            raise ValueError(f"Método de feature selection desconocido: {method}")

    def _get_feature_names_out(self) -> list:
        """
        Retorna los nombres de las features después de todas las transformaciones.

        Returns:
            list: Lista de nombres de features finales
        """
        if self.selector is not None:
            return self.selector.get_selected_features()

    def get_preprocessor(self):
        """
        Retorna el preprocesador ajustado.

        Returns:
            ColumnTransformer: Preprocesador ajustado
        """
        self.check_fitted()
        return self.preprocessor

    def get_selector(self):
        """
        Retorna el selector ajustado.

        Returns:
            BaseFeatureSelector: Selector ajustado o None
        """
        self.check_fitted()
        return self.selector
