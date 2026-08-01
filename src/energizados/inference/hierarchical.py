"""
Hierarchical inference implementation for Energizados Framework.

Routes predictions to different models based on configurable conditions
on the input dataframe. Supports per-route feature engineering and
fallback to a default model.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from energizados.contracts import ModelContainer
from energizados.core.base import BaseInference

logger = logging.getLogger(__name__)


class HierarchicalInference(BaseInference):
    """
    Inference engine that routes rows to different models based on conditions.

    Each route defines a condition (column-value mapping) and a model path.
    Rows matching a route's condition are predicted by that route's model.
    Rows matching no route use the default model.

    Supports per-route feature engineering pipelines.

    Args:
        threshold: Global threshold for binary predictions (default: 0.5).
        routes: List of route definitions. Each route is a dict with:
            - name (str): descriptive name
            - condition (dict): {column: value_or_list} to match
            - model_path (str): path to the model .pkl file
        default_model_path: Path to fallback model .pkl.
        feature_engineering_paths: Optional dict mapping route name to FE .pkl path.
            Use "__default__" as the key to provide FE for the default model's rows.

    Example:
        >>> inference = HierarchicalInference(
        ...     threshold=0.5,
        ...     routes=[
        ...         {
        ...             "name": "fln",
        ...             "condition": {"geo_region": "FLORIANOPOLIS"},
        ...             "model_path": "models/fln/model.pkl",
        ...         },
        ...         {
        ...             "name": "alta_tension",
        ...             "condition": {
        ...                 "nivel_tension": "ALTA",
        ...                 "zona": "RURAL",
        ...             },
        ...             "model_path": "models/alta/model.pkl",
        ...         },
        ...     ],
        ...     default_model_path="models/global/model.pkl",
        ...     feature_engineering_paths={
        ...         "fln": "models/fln/feature_engineering.pkl",
        ...     },
        ... )
        >>> model = inference.load_model()  # loads all route models
        >>> probas = inference.predict_proba(model, data)
    """

    def __init__(
        self,
        threshold: float = 0.5,
        routes: Optional[List[Dict[str, Any]]] = None,
        default_model_path: Optional[str] = None,
        feature_engineering_paths: Optional[Dict[str, str]] = None,
    ):
        self.threshold = threshold
        self.routes = routes or []
        self.default_model_path = default_model_path
        self.feature_engineering_paths = feature_engineering_paths or {}
        self._models: Dict[str, Any] = {}
        self._feature_engineerings: Dict[str, Any] = {}
        self._is_loaded = False

        # Collision guard: reject "__default__" as a user route name
        for route in self.routes:
            if route.get("name") == "__default__":
                raise ValueError(
                    "Route name '__default__' is reserved for the default model. "
                    "Please choose a different name for your route."
                )

    def load_model(self, model_path: Optional[str] = None) -> ModelContainer:
        """
        Load all route models and feature engineering pipelines.

        Args:
            model_path: Ignored. Models are loaded from route definitions.

        Returns:
            ModelContainer: A lightweight container representing
            all loaded models.
        """
        from energizados.core.utils.integrity_pickle import load

        if self._is_loaded:
            return HierarchicalModelContainer(self._models, self._feature_engineerings)

        # Load route-specific models and FE pipelines
        for route in self.routes:
            name = route["name"]
            mpath = route["model_path"]

            logger.info(f"[HierarchicalInference] Loading model for route '{name}': {mpath}")
            self._models[name] = load(mpath)

            fe_path = self.feature_engineering_paths.get(name)
            if fe_path:
                logger.info(f"[HierarchicalInference] Loading FE for route '{name}': {fe_path}")
                self._feature_engineerings[name] = load(fe_path)

        # Load default model
        if self.default_model_path:
            logger.info(f"[HierarchicalInference] Loading default model: {self.default_model_path}")
            self._models["__default__"] = load(self.default_model_path)

            # Load the default model's feature engineering when configured. Without
            # this, unrouted rows are sent RAW to a model trained on feature-
            # engineered data (crash or garbage predictions).
            default_fe_path = self.feature_engineering_paths.get("__default__")
            if default_fe_path:
                logger.info(
                    f"[HierarchicalInference] Loading FE for default model: {default_fe_path}"
                )
                self._feature_engineerings["__default__"] = load(default_fe_path)

        self._is_loaded = True
        return HierarchicalModelContainer(self._models, self._feature_engineerings)

    def predict(self, model: Any, data: pd.DataFrame) -> np.ndarray:
        """
        Make binary predictions using per-row thresholds.

        Args:
            model: HierarchicalModelContainer (ignored, uses internal state).
            data: Data for prediction.

        Returns:
            np.ndarray: Binary predictions (0 or 1).
        """
        probas = self.predict_proba(model, data)
        return (probas >= self.threshold).astype(int)

    def predict_proba(self, model: Any, data: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions by routing rows to their matching models.

        Args:
            model: HierarchicalModelContainer (ignored, uses internal state).
            data: Data for prediction.

        Returns:
            np.ndarray: Probabilities of the positive class.
        """
        if not self._is_loaded:
            from energizados.core.exceptions import InferenceError

            raise InferenceError("Models not loaded. Call load_model() before predict_proba().")

        n_rows = len(data)
        probas = np.zeros(n_rows, dtype=np.float64)
        routed = np.zeros(n_rows, dtype=bool)

        # Apply routes in order (first match wins)
        for route in self.routes:
            name = route["name"]
            condition = route["condition"]

            mask = self._evaluate_condition(data, condition)
            # Only route rows not already handled by a previous route
            effective_mask = mask & (~routed)

            if effective_mask.any():
                n_matched = effective_mask.sum()
                logger.debug(f"[HierarchicalInference] Route '{name}' matches {n_matched} rows")

                model_obj = self._models[name]
                fe_obj = self._feature_engineerings.get(name)

                subset = data[effective_mask]
                if fe_obj is not None:
                    subset = fe_obj.transform(subset)

                probas[effective_mask] = model_obj.predict_proba(subset)
                routed[effective_mask] = True

        # Fallback for unrouted rows
        unrouted = ~routed
        if unrouted.any():
            n_unrouted = unrouted.sum()
            if "__default__" in self._models:
                logger.debug(f"[HierarchicalInference] Fallback model handles {n_unrouted} rows")
                default_subset = data[unrouted]
                default_fe = self._feature_engineerings.get("__default__")
                if default_fe is not None:
                    default_subset = default_fe.transform(default_subset)
                probas[unrouted] = self._models["__default__"].predict_proba(default_subset)
            else:
                logger.warning(
                    f"[HierarchicalInference] {n_unrouted} rows unmatched and no "
                    "default model configured. Returning 0.0 for these rows."
                )
                probas[unrouted] = 0.0

        return probas

    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """Save predictions to CSV."""
        from energizados.core.utils.integrity_pickle import validate_no_traversal

        validate_no_traversal(output_path, label="inference output_path")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"prediction": predictions}).to_csv(output_path, index=False)

    def save_predictions_with_proba(
        self,
        predictions: np.ndarray,
        probas: np.ndarray,
        output_path: str,
    ) -> None:
        """Save binary predictions and probabilities to CSV."""
        from energizados.core.utils.integrity_pickle import validate_no_traversal

        validate_no_traversal(output_path, label="inference output_path")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "prediction": predictions,
                "probability": probas,
            }
        ).to_csv(output_path, index=False)

    @staticmethod
    def _evaluate_condition(data: pd.DataFrame, condition: Dict[str, Any]) -> pd.Series:
        """
        Evaluate a condition dict against a dataframe.

        Args:
            data: Input dataframe.
            condition: Dict of {column: value_or_list_of_values}.

        Returns:
            pd.Series: Boolean mask of matching rows.
        """
        mask = pd.Series(True, index=data.index)

        for col, expected in condition.items():
            if col not in data.columns:
                # Column missing → no rows match this condition
                logger.warning(
                    f"[HierarchicalInference] Condition column '{col}' not found in data. "
                    f"Available: {list(data.columns)}"
                )
                return pd.Series(False, index=data.index)

            if isinstance(expected, list):
                mask &= data[col].isin(expected)
            elif callable(expected):
                mask &= data[col].apply(expected)
            else:
                mask &= data[col] == expected

        return mask


class HierarchicalModelContainer:
    """
    Lightweight container for hierarchical model state.

    This object is returned by HierarchicalInference.load_model() and
    passed back to predict/predict_proba. It serves as a sentinel that
    the inference engine is properly loaded.
    """

    def __init__(
        self,
        models: Dict[str, Any],
        feature_engineerings: Dict[str, Any],
    ):
        self.models = models
        self.feature_engineerings = feature_engineerings

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probabilities (ModelContainer Protocol stub).

        This method is required by the ModelContainer Protocol but is not
        actually used. The real prediction logic is in HierarchicalInference.
        """
        # This is a stub to satisfy the ModelContainer Protocol
        raise NotImplementedError("Use HierarchicalInference.predict_proba() instead")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return binary predictions (ModelContainer Protocol stub).

        This method is required by the ModelContainer Protocol but is not
        actually used. The real prediction logic is in HierarchicalInference.
        """
        # This is a stub to satisfy the ModelContainer Protocol
        raise NotImplementedError("Use HierarchicalInference.predict() instead")
