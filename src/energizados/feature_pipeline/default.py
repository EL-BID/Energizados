"""
Default Feature Pipeline Implementation for Energizados Framework.

Este módulo proporciona una implementación por defecto que combina
preprocessing y feature_selection en un solo paso unificado.
"""

import logging
from typing import Dict, List, Optional

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from energizados.feature_pipeline.base import BaseFeaturePipeline
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


def _get_get_preprocesor():
    """Importa get_preprocesor de forma lazy para evitar problemas con tensorflow."""
    from energizados.modeling.supervised_models import get_preprocesor

    return get_preprocesor


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


def _get_legacy_preprocesor(preprocessor_num: int, categorical_features: List[str]) -> ColumnTransformer:
    """
    Construye el preprocesador usando el formato legacy (preprocessor_num).

    Args:
        preprocessor_num: Número de preprocesador
        categorical_features: Lista de features categóricas

    Returns:
        ColumnTransformer: Preprocesador configurado
    """
    logger.warning(
        f"preprocessor_num está deprecated. Usar 'columns' en su lugar. "
        f"preprocessor_num={preprocessor_num} será removido en versiones futuras."
    )

    # Usar la función de supervised_models que ya tiene la lógica implementada
    # Para preprocessor_num 4, construye el preprocesador localmente
    if preprocessor_num == 4:
        # Actividad
        if "actividad" in categorical_features:
            pipe_actividad = Pipeline([("cardinality_reducer", CardinalityReducer(threshold=0.001)), ("a_dummy", ToDummy(["actividad"]))])
        else:
            pipe_actividad = None

        # Segmento Tarifa
        if "tipo_tarifa" in categorical_features:
            pipe_tarifa = Pipeline(
                [
                    ("cardinality_reducer", CardinalityReducer(threshold=0.001)),
                    ("tarifa_te", TeEncoder(["tipo_tarifa"], w=20)),
                ]
            )
        else:
            pipe_tarifa = None

        vars_enc = []
        if "zona" in categorical_features:
            vars_enc.append("zona")
        if "nivel_tension" in categorical_features:
            vars_enc.append("nivel_tension")

        from sklearn.preprocessing import OrdinalEncoder

        t_features = []

        if vars_enc:
            t_features.append(("var_encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), vars_enc))

        if "material_instalacion" in categorical_features:
            t_features.append(("material_instalacion_te", TeEncoder(["material_instalacion"], w=10), ["material_instalacion"]))

        if pipe_actividad is not None:
            t_features.append(("actividad_cr_dummy", pipe_actividad, ["actividad"]))

        if pipe_tarifa is not None:
            t_features.append(("tarifa_cr_te", pipe_tarifa, ["tipo_tarifa"]))

        preprocessor = ColumnTransformer(transformers=t_features, remainder="passthrough")
    else:
        # Para preprocessor_num 1-3, usar la función de supervised_models
        get_preprocesor_fn = _get_get_preprocesor()
        preprocessor = get_preprocesor_fn(preprocessor_num)

    return preprocessor


def get_preprocesor(preprocessing_config: dict) -> ColumnTransformer:
    """
    Construye el preprocesador desde config YAML.

    Args:
        preprocessing_config: Dict con configuración de preprocessing.
                              Puede tener:
                              - 'columns': dict mapeando columna→lista de transformaciones (NUEVO)
                              - 'preprocessor_num': int con número de preprocesador (LEGACY)
                              - 'categorical_features': list de features categóricos (LEGACY)

    Returns:
        ColumnTransformer: Preprocesador configurado
    """
    # MODO NUEVO: Configuración por columna
    columns_config = preprocessing_config.get("columns")

    if columns_config:
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

    # MODO LEGACY: preprocessor_num
    preprocessor_num = preprocessing_config.get("preprocessor_num", 4)
    categorical_features = preprocessing_config.get("categorical_features", [])
    return _get_legacy_preprocesor(preprocessor_num, categorical_features)


class DefaultFeaturePipeline(BaseFeaturePipeline):
    """
    Implementación por defecto del Feature Pipeline.

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
        # Legacy params (deprecated)
        preprocessor_num: Optional[int] = None,
        categorical_features: Optional[List[str]] = None,
    ):
        """
        Inicializa el Feature Pipeline por defecto.

        Args:
            preprocessing_config: Configuración de preprocessing (nuevo formato con 'columns')
            feature_selection_config: Configuración de feature selection
            config: Diccionario de configuración general (opcional)
            preprocessor_num: (DEPRECATED) Número de preprocesador
            categorical_features: (DEPRECATED) Lista de features categóricas
        """
        super().__init__(config)

        # Construir preprocessing_config desde config si no se proporciona
        if preprocessing_config is None:
            preprocessing_config = self.config.get("preprocessing", {})

        # Legacy: si se pasan preprocessor_num/categorical_features, construir config antigua
        if preprocessor_num is not None or categorical_features is not None:
            logger.warning(
                "preprocessor_num y categorical_features están deprecated. " "Usar preprocessing_config con 'columns' en su lugar."
            )
            if preprocessing_config.get("columns"):
                logger.warning("Ignorando preprocessor_num/categorical_features porque 'columns' está presente")
            else:
                preprocessing_config["preprocessor_num"] = preprocessor_num or 4
                preprocessing_config["categorical_features"] = categorical_features or []

        self.preprocessing_config = preprocessing_config
        self.feature_selection_config = feature_selection_config or self.config.get("feature_selection", {})
        self.preprocessor = None
        self.selector = None
        self.feature_names_out_ = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "DefaultFeaturePipeline":
        """
        Aprende las transformaciones de preprocessing y feature selection.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento

        Returns:
            self: Retorna la instancia entrenada
        """
        logger.info("Iniciando fit del Feature Pipeline...")

        # 1. Construir y ajustar preprocesador
        logger.info("Construyendo preprocesador desde configuración...")
        self.preprocessor = get_preprocesor(self.preprocessing_config)

        logger.info("Aplicando preprocessing de entrenamiento...")
        X_prep = self.preprocessor.fit_transform(X, y)

        # Obtener nombres de features después del preprocessing
        self.feature_names_out_ = self._get_feature_names_after_preprocessing(X)

        # Convertir a DataFrame si es necesario
        if not isinstance(X_prep, pd.DataFrame):
            X_prep = pd.DataFrame(X_prep, columns=self.feature_names_out_)

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
        logger.info("Fit del Feature Pipeline completado")
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

        if not isinstance(X_prep, pd.DataFrame):
            X_prep = pd.DataFrame(X_prep, columns=self.feature_names_out_)

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

    def _get_feature_names_after_preprocessing(self, X: pd.DataFrame) -> List[str]:
        """
        Obtiene los nombres de las features después del preprocessing.

        Args:
            X: DataFrame original

        Returns:
            List[str]: Lista de nombres de features
        """
        # Para ColumnTransformer, podemos obtener los nombres
        if hasattr(self.preprocessor, "get_feature_names_out"):
            try:
                return self.preprocessor.get_feature_names_out()
            except (AttributeError, ValueError, TypeError) as e:
                # get_feature_names_out puede fallar en algunos casos de sklearn
                logger.debug(f"get_feature_names_out falló: {e}, usando método fallback")
                # Continuar con el método fallback

        # Extraer columnas categóricas desde la configuración
        categorical_features = []
        if "columns" in self.preprocessing_config:
            categorical_features = list(self.preprocessing_config["columns"].keys())
        elif "categorical_features" in self.preprocessing_config:
            categorical_features = self.preprocessing_config["categorical_features"]

        # Método fallback: construir nombres manualmente
        feature_names = []
        for col in X.columns:
            if col not in categorical_features:
                feature_names.append(col)

        # Agregar nombres de features categóricas procesadas
        # (esto es una simplificación, en realidad los transformers generan sus propios nombres)
        for cat_col in categorical_features:
            if cat_col == "actividad":
                # ToDummy genera múltiples columnas
                for i in range(50):  # Estimación
                    feature_names.append(f"dummy_actividad_{i}")
            elif cat_col == "tipo_tarifa":
                feature_names.append(f"{cat_col}_prob")
            elif cat_col in ["zona", "nivel_tension"]:
                feature_names.append(f"{cat_col}_encoded")
            elif cat_col == "material_instalacion":
                feature_names.append(f"{cat_col}_prob")

        return feature_names

    def _get_feature_names_out(self) -> list:
        """
        Retorna los nombres de las features después de todas las transformaciones.

        Returns:
            list: Lista de nombres de features finales
        """
        if self.selector is not None:
            return self.selector.get_selected_features()
        return self.feature_names_out_

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
