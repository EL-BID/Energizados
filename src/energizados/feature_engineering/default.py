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
from energizados.preprocessing.preprocessing import (
    CardinalityReducer,
    CastDtype,
    ExtraVars,
    TeEncoder,
    ToDummy,
    TsfelVars,
)

logger = logging.getLogger(__name__)


def _build_transformer_from_config(transform_name: str, params: dict, column: str, custom_class: str = None):
    """
    Construye un transformer desde config YAML.

    Args:
        transform_name: Nombre del transformer en YAML (o "custom_class")
        params: Diccionario de parámetros desde YAML
        column: Nombre de la columna a transformar
        custom_class: Path completo de la clase custom (solo cuando transform_name=="custom_class")

    Returns:
        Instancia del transformer configurado
    """
    from sklearn.preprocessing import OrdinalEncoder

    from energizados.preprocessing.preprocessing import MinMaxScalerRow
    from energizados.utils import import_class

    # Caso especial para custom_class por columna (formato plano)
    if transform_name == "custom_class":
        if custom_class is None:
            raise ValueError("Se debe especificar 'custom_class' cuando se usa el transformer 'custom_class'")
        return import_class(custom_class)(**params)

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
        "cast_dtype": (CastDtype, {"dtype": "float32"}),
        # Global transformers (no requieren column name)
        "tsfel_vars": (
            TsfelVars,
            {
                "num_periodos": 12,
                "features_names_path": None,
                "periods_suffix": "_anterior",
                "n_jobs": 1,
                "chunk_size": 500,
                "cache_dir": None,
            },
        ),
        "extra_vars": (ExtraVars, {"num_periodos": 3, "periods_suffix": "_anterior"}),
    }

    if transform_name not in transformer_map:
        raise ValueError(f"Transformer desconocido: {transform_name}. " f"Opciones disponibles: {list(transformer_map.keys())}")

    cls, default_params = transformer_map[transform_name]
    params = {**default_params, **(params or {})}

    # Special handling para transformers que necesitan column name
    if transform_name in ["to_dummy", "target_encoding"]:
        params["cols"] = [column]

    return cls(**params)


def _build_global_transformers_pipeline(global_transformers_config: list) -> Pipeline:
    """
    Construye un pipeline de transformers globales desde config YAML.

    Args:
        global_transformers_config: Lista de dicts con configuración de transformers globales

    Returns:
        Pipeline: Pipeline con los transformers globales (o None si no hay config)
    """
    if not global_transformers_config:
        return None

    steps = []
    for i, transformer_config in enumerate(global_transformers_config):
        # Caso custom_class
        if "custom_class" in transformer_config:
            custom_class_path = transformer_config.get("custom_class")
            custom_params = transformer_config.get("params", {})
            transformer = _build_transformer_from_config("custom_class", custom_params, None, custom_class=custom_class_path)
            name = f"global_custom_{i}"
        else:
            # Transformers built-in
            for transform_name, params in transformer_config.items():
                transformer = _build_transformer_from_config(transform_name, params, None)
                name = f"global_{transform_name}_{i}"
                break  # solo un transformer por item

        steps.append((name, transformer))

    if steps:
        return Pipeline(steps)
    return None


def get_preprocesor(preprocessing_config: dict) -> Pipeline:
    """
    Construye el preprocesador desde config YAML.

    El pipeline resultante tiene dos pasos:
    1. column_transformer: Preprocessing por columnas (column-based)
    2. global_transformers: Transformers globales (opcional, dataset-wide)

    Args:
        preprocessing_config: Dict con configuración de preprocessing.

    Returns:
        Pipeline: Pipeline con column_transformer + global_transformers

    Raises:
        ValueError: Si no se encuentra configuración válida
    """
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
                # Caso especial: custom_class por columna (formato plano)
                # YAML: - custom_class: "path.to.Class", params: {...}
                if "custom_class" in transform_config:
                    custom_class_path = transform_config.get("custom_class")
                    custom_params = transform_config.get("params", {})
                    transformer = _build_transformer_from_config("custom_class", custom_params, column, custom_class=custom_class_path)
                    steps.append(("custom_class", transformer))
                else:
                    # Transformers built-in estándar
                    for transform_name, params in transform_config.items():
                        transformer = _build_transformer_from_config(transform_name, params, column)
                        steps.append((transform_name, transformer))

            if steps:
                pipeline = Pipeline(steps)
                transformers.append((f"{column}_pipeline", pipeline, [column]))

        # ColumnTransformer con passthrough para columnas no mencionadas
        ct = ColumnTransformer(transformers=transformers, remainder="passthrough", verbose_feature_names_out=False)
        ct.set_output(transform="pandas")

        # Construir Pipeline de global_transformers
        global_config = preprocessing_config.get("global_transformers", [])
        global_pipeline = _build_global_transformers_pipeline(global_config)

        # Combinar en Pipeline final
        if global_pipeline is not None:
            final_pipeline = Pipeline([("column_transformer", ct), ("global_transformers", global_pipeline)])
        else:
            # Si no hay global transformers, envolver ct en Pipeline para consistencia
            final_pipeline = Pipeline([("column_transformer", ct)])

        return final_pipeline

    # Error si no hay configuración válida
    raise ValueError("Configuración de preprocessing inválida. Se requiere 'columns' con la configuración por columna. ")


class DefaultFeatureEngineering(BaseFeatureEngineering):
    """
    Implementación por defecto del Feature Engineering.

    Combina preprocessing (codificación de variables categóricas)
    y feature selection (métodos como Boruta, correlación, constantes)
    en un solo paso.

    Attributes:
        preprocessor: Pipeline de preprocessing (scikit-learn Pipeline con ColumnTransformer + global_transformers)
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

        # Verificar si preprocessing está habilitado
        preprocessing_enabled = self.preprocessing_config.get("enabled", True)

        # 1. Construir y ajustar preprocesador
        if preprocessing_enabled:
            # Verificar si hay custom_class
            custom_class = self.preprocessing_config.get("custom_class")

            if custom_class:
                # Importar y usar custom preprocessor
                from energizados.utils import import_class

                params = self.preprocessing_config.get("params", {})
                self.preprocessor = import_class(custom_class)(**params)
                logger.info(f"Usando custom preprocessor: {custom_class}")
            else:
                # Usar configuración YAML
                logger.info("Construyendo preprocesador desde configuración...")
                self.preprocessor = get_preprocesor(self.preprocessing_config)

            logger.info("Aplicando preprocessing de entrenamiento...")
            X_prep = self.preprocessor.fit_transform(X, y)
            logger.info(f"Features después de preprocessing: {X_prep.shape[1]}")
        else:
            logger.info("Preprocessing deshabilitado, usando features originales")
            self.preprocessor = None
            X_prep = X.copy()

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

        # 1. Aplicar preprocessing si está habilitado
        if self.preprocessor is not None:
            X_prep = self.preprocessor.transform(X)
        else:
            X_prep = X.copy()

        # 2. Aplicar feature selection si está habilitado
        if self.selector is not None:
            X_transformed = self.selector.transform(X_prep)
            return X_transformed

        return X_prep

    def _build_selector(self):
        """
        Construye el selector de features según la configuración.

        Returns:
            FeatureSelectionPipeline: Selector configurado
        """
        from energizados.feature_selection.pipeline import FeatureSelectionPipeline

        cfg = self.feature_selection_config
        if "steps" not in cfg:
            raise ValueError(
                "feature_selection config must contain a 'steps' list. "
                "Example:\n"
                "  feature_selection:\n"
                "    enabled: true\n"
                "    steps:\n"
                "      - name: drop_constant\n"
                "        method: constant\n"
                "        params:\n"
                "          threshold: 0.99\n"
            )
        return FeatureSelectionPipeline(steps_config=cfg["steps"])

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
            Pipeline: Preprocesador ajustado (column_transformer + global_transformers)
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
