"""
Default Feature Engineering Implementation for Energizados Framework.

This module provides a default implementation that combines
preprocessing and feature_selection in a single unified step.
"""

import logging
from typing import Dict, Optional

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from energizados.feature_engineering.base import BaseFeatureEngineering
from energizados.preprocessing.geo_features import GeoFeatures
from energizados.preprocessing.preprocessing import (
    CardinalityReducer,
    CastDtype,
    ConsumptionPatterns,
    ExtraVars,
    TeEncoder,
    ToDummy,
    TsfelVars,
)

logger = logging.getLogger(__name__)


def _build_transformer_from_config(
    transform_name: str, params: dict, column: str, custom_class: str = None
):
    """Builds a transformer from YAML config.

    Args:
        transform_name: Transformer name in YAML (or "custom_class").
        params: Parameter dictionary from YAML.
        column: Name of the column to transform.
        custom_class: Full path of custom class (only when transform_name=="custom_class").

    Returns:
        Configured transformer instance.
    """
    from sklearn.preprocessing import OrdinalEncoder

    from energizados.core.utils import import_class
    from energizados.preprocessing.preprocessing import MinMaxScalerRow

    # Special case for custom_class per column (flat format)
    if transform_name == "custom_class":
        if custom_class is None:
            raise ValueError("Must specify 'custom_class' path when using custom transformer")
        return import_class(custom_class)(**params)

    # Mapping of names to (class, default_params)
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
        # Global transformers (don't require column name)
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
        "consumption_patterns": (
            ConsumptionPatterns,
            {"num_periodos": 12, "periods_suffix": "_anterior"},
        ),
        "geo_features": (
            GeoFeatures,
            {
                "lat_col": "latitud",
                "lon_col": "longitud",
                "include_hierarchy": True,
                "include_target_encoding": True,
                "te_w": 20,
                "include_distances": True,
                "distance_cities": [
                    "sao_paulo",
                    "rio_de_janeiro",
                    "brasilia",
                    "salvador",
                    "belo_horizonte",
                ],
                "include_coords": False,
            },
        ),
    }

    if transform_name not in transformer_map:
        raise ValueError(
            f"Unknown transformer: {transform_name}. "
            f"Available options: {list(transformer_map.keys())}"
        )

    cls, default_params = transformer_map[transform_name]
    params = {**default_params, **(params or {})}

    # Special handling for transformers that need column name
    if transform_name in ["to_dummy", "target_encoding"]:
        params["cols"] = [column]

    return cls(**params)


def _build_global_transformers_pipeline(global_transformers_config: list) -> Pipeline:
    """Builds a global transformers pipeline from YAML config.

    Args:
        global_transformers_config: List of dicts with global transformers configuration.

    Returns:
        Pipeline: Pipeline with global transformers (or None if no config).
    """
    if not global_transformers_config:
        return None

    steps = []
    for i, transformer_config in enumerate(global_transformers_config):
        # Custom class case
        if "custom_class" in transformer_config:
            custom_class_path = transformer_config.get("custom_class")
            custom_params = transformer_config.get("params", {})
            transformer = _build_transformer_from_config(
                "custom_class", custom_params, None, custom_class=custom_class_path
            )
            name = f"global_custom_{i}"
        else:
            # Built-in transformers
            for transform_name, params in transformer_config.items():
                transformer = _build_transformer_from_config(transform_name, params, None)
                name = f"global_{transform_name}_{i}"
                break  # only one transformer per item

        steps.append((name, transformer))

    if steps:
        return Pipeline(steps)
    return None


def get_preprocesor(preprocessing_config: dict) -> Pipeline:
    """Builds the preprocessor from YAML config.

    The resulting pipeline has two steps:
    1. column_transformer: Column-based preprocessing (column-based).
    2. global_transformers: Global transformers (optional, dataset-wide).

    Args:
        preprocessing_config: Dictionary with preprocessing configuration.

    Returns:
        Pipeline: Pipeline with column_transformer + global_transformers.

    Raises:
        ValueError: If no valid configuration is found.
    """
    # Check if 'columns' key exists (even if empty)
    if "columns" in preprocessing_config:
        columns_config = preprocessing_config["columns"]
        if not columns_config:
            raise ValueError(
                "The 'columns' config cannot be empty. Specify at least one column with its transformations."
            )

        transformers = []

        # Drop columns explícitamente antes de passthrough
        drop_columns = preprocessing_config.get("drop_columns", [])
        for col in drop_columns:
            transformers.append((f"drop_{col}", "drop", [col]))

        for column, transformations in columns_config.items():
            # Build sequential Pipeline for this column
            steps = []
            for transform_config in transformations:
                # Special case: custom_class per column (flat format)
                # YAML: - custom_class: "path.to.Class", params: {...}
                if "custom_class" in transform_config:
                    custom_class_path = transform_config.get("custom_class")
                    custom_params = transform_config.get("params", {})
                    transformer = _build_transformer_from_config(
                        "custom_class", custom_params, column, custom_class=custom_class_path
                    )
                    steps.append(("custom_class", transformer))
                else:
                    # Standard built-in transformers
                    for transform_name, params in transform_config.items():
                        transformer = _build_transformer_from_config(transform_name, params, column)
                        steps.append((transform_name, transformer))

            if steps:
                pipeline = Pipeline(steps)
                transformers.append((f"{column}_pipeline", pipeline, [column]))

        # ColumnTransformer with passthrough for unmentioned columns
        ct = ColumnTransformer(
            transformers=transformers, remainder="passthrough", verbose_feature_names_out=False
        )
        ct.set_output(transform="pandas")

        # Build global_transformers Pipeline
        global_config = preprocessing_config.get("global_transformers", [])
        global_pipeline = _build_global_transformers_pipeline(global_config)

        # Combine into final Pipeline
        if global_pipeline is not None:
            final_pipeline = Pipeline(
                [("column_transformer", ct), ("global_transformers", global_pipeline)]
            )
        else:
            # If no global transformers, wrap ct in Pipeline for consistency
            final_pipeline = Pipeline([("column_transformer", ct)])

        return final_pipeline

    # Error if no valid configuration
    raise ValueError(
        "Invalid preprocessing configuration. 'columns' is required with per-column configuration."
    )


class DefaultFeatureEngineering(BaseFeatureEngineering):
    """Default Feature Engineering implementation.

    Combines preprocessing (categorical variable encoding)
    and feature selection (methods like Boruta, correlation, constants)
    in a single step.

    Attributes:
        preprocessor: Preprocessing pipeline (scikit-learn Pipeline with ColumnTransformer + global_transformers).
        selector: Feature selector (BorutaSelector, CorrelationSelector, etc.).
        preprocessing_config: Preprocessing configuration.
        feature_selection_config: Feature selection configuration.
    """

    def __init__(
        self,
        preprocessing_config: Optional[Dict] = None,
        feature_selection_config: Optional[Dict] = None,
        config: Optional[Dict] = None,
    ):
        """Initializes the default Feature Engineering.

        Args:
            preprocessing_config: Preprocessing configuration (new format with 'columns').
            feature_selection_config: Feature selection configuration.
            config: General configuration dictionary (optional).
        """
        super().__init__(config)

        # Build preprocessing_config from config if not provided
        if preprocessing_config is None:
            preprocessing_config = self.config.get("preprocessing", {})

        self.preprocessing_config = preprocessing_config
        self.feature_selection_config = feature_selection_config or self.config.get(
            "feature_selection", {}
        )
        self.preprocessor = None
        self.selector = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "DefaultFeatureEngineering":
        """Learns preprocessing and feature selection transformations.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            self: Returns the trained instance.
        """
        logger.info("Starting Feature Engineering fit...")

        # Check if preprocessing is enabled
        preprocessing_enabled = self.preprocessing_config.get("enabled", True)

        # 1. Build and fit preprocessor
        if preprocessing_enabled:
            # Check if there's a custom_class
            custom_class = self.preprocessing_config.get("custom_class")

            if custom_class:
                # Import and use custom preprocessor
                from energizados.core.utils import import_class

                params = self.preprocessing_config.get("params", {})
                self.preprocessor = import_class(custom_class)(**params)
                logger.info(f"Using custom preprocessor: {custom_class}")
            else:
                # Use YAML configuration
                logger.info("Building preprocessor from configuration...")
                self.preprocessor = get_preprocesor(self.preprocessing_config)

            logger.info("Applying training preprocessing...")
            X_prep = self.preprocessor.fit_transform(X, y)
            logger.info(f"Features after preprocessing: {X_prep.shape[1]}")
        else:
            logger.info("Preprocessing disabled, using original features")
            self.preprocessor = None
            X_prep = X.copy()

        # 2. Feature Selection (if enabled)
        if self.feature_selection_config.get("enabled", True):
            logger.info("Applying feature selection...")
            self.selector = self._build_selector()
            self.selector.fit(X_prep, y)
            logger.info(f"Selected features: {len(self.selector.get_selected_features())}")
        else:
            logger.info("Feature selection disabled, using all features")
            self.selector = None

        self.is_fitted_ = True
        logger.info("Feature Engineering fit completed")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Applies preprocessing and feature selection to data.

        Args:
            X: DataFrame to transform.

        Returns:
            pd.DataFrame: Transformed DataFrame.

        Raises:
            ValueError: If fit() was not called previously.
        """
        self.check_fitted()

        # 1. Apply preprocessing if enabled
        if self.preprocessor is not None:
            X_prep = self.preprocessor.transform(X)
        else:
            X_prep = X.copy()

        # 2. Apply feature selection if enabled
        if self.selector is not None:
            X_transformed = self.selector.transform(X_prep)
            return X_transformed

        return X_prep

    def _build_selector(self):
        """Builds the feature selector according to configuration.

        Returns:
            FeatureSelectionPipeline: Configured selector.
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
        """Returns feature names after all transformations.

        Returns:
            list: List of final feature names.
        """
        if self.selector is not None:
            return self.selector.get_selected_features()

    def get_preprocessor(self):
        """Returns the fitted preprocessor.

        Returns:
            Pipeline: Fitted preprocessor (column_transformer + global_transformers).
        """
        self.check_fitted()
        return self.preprocessor

    def get_selector(self):
        """Returns the fitted selector.

        Returns:
            BaseFeatureSelector: Fitted selector or None.
        """
        self.check_fitted()
        return self.selector
