"""SHAP explainer for model interpretability."""

import logging
from typing import Any, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ShapExplainer:
    """Computes SHAP values for model explainability.

    Supports:
    - TreeExplainer: for LGBM and CatBoost (fast, accurate)
    - KernelExplainer: fallback for ensembles, NN, LSTM (model-agnostic, slower)

    Args:
        model: Fitted model adapter (BaseModel) or raw sklearn/lightgbm/catboost model
        X_background: Background data for SHAP (subsampled if needed)
        feature_names: List of feature names
        max_samples: Maximum samples for background data (default 500)
    """

    def __init__(
        self,
        model: Any,
        X_background: pd.DataFrame,
        feature_names: List[str],
        max_samples: int = 500,
    ):
        self.feature_names = feature_names
        self.max_samples = max_samples
        self._explainer = None
        self._is_tree = False

        if len(X_background) > max_samples:
            X_background = X_background.sample(n=max_samples, random_state=42)
        self._X_background = X_background

        self._setup_explainer(model)

    def _setup_explainer(self, model: Any) -> None:
        """Set up the appropriate SHAP explainer based on model type."""
        import shap

        raw_model = self._get_raw_model(model)

        if raw_model is None:
            logger.warning("Could not extract raw model. SHAP not available.")
            return

        model_type = type(raw_model).__name__

        if model_type in (
            "LGBMClassifier",
            "LGBMRegressor",
            "CatBoostClassifier",
            "CatBoostRegressor",
        ):
            try:
                self._explainer = shap.TreeExplainer(raw_model)
                self._is_tree = True
                logger.info(f"Using TreeExplainer for {model_type}")
            except Exception as e:
                logger.warning(
                    f"TreeExplainer failed for {model_type}: {e}. Falling back to KernelExplainer."
                )
                self._setup_kernel_explainer(raw_model)
        else:
            self._setup_kernel_explainer(raw_model)

    def _setup_kernel_explainer(self, raw_model: Any) -> None:
        """Set up KernelExplainer as fallback."""
        import shap

        try:
            predict_fn = self._get_predict_fn(raw_model)
            background_summary = shap.kmeans(self._X_background, min(50, len(self._X_background)))
            self._explainer = shap.KernelExplainer(predict_fn, background_summary)
            logger.info("Using KernelExplainer (model-agnostic)")
        except Exception as e:
            logger.error(f"Failed to create KernelExplainer: {e}")

    def _get_raw_model(self, model: Any) -> Any:
        """Extract raw model from adapter or use directly."""
        if hasattr(model, "get_raw_model"):
            raw = model.get_raw_model()
            if isinstance(raw, dict):
                raw = next(iter(raw.values()))
            return raw
        return model

    def _get_predict_fn(self, raw_model: Any) -> Any:
        """Get prediction function for KernelExplainer."""
        model_type = type(raw_model).__name__

        if model_type in ("LGBMClassifier", "CatBoostClassifier"):
            return raw_model.predict_proba
        elif "keras" in str(type(raw_model)).lower() or "Sequential" in model_type:
            return raw_model.predict
        elif hasattr(raw_model, "predict_proba"):
            return raw_model.predict_proba
        elif hasattr(raw_model, "predict"):
            return raw_model.predict
        else:
            raise ValueError(f"Cannot find prediction function for {model_type}")

    def compute_shap_values(
        self,
        X: pd.DataFrame,
        max_samples: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """Compute SHAP values for the given data.

        Args:
            X: Feature matrix to explain
            max_samples: If set, subsample X to this many rows

        Returns:
            SHAP values array (n_samples, n_features) or None if explainer not available
        """
        if self._explainer is None:
            logger.warning("SHAP explainer not available. Cannot compute SHAP values.")
            return None

        if max_samples and len(X) > max_samples:
            X = X.sample(n=max_samples, random_state=42)

        try:
            if self._is_tree:
                shap_values = self._explainer.shap_values(X)
                if isinstance(shap_values, list):
                    shap_values = shap_values[1]
            else:
                shap_values = self._explainer.shap_values(X, nsamples=100)
                if isinstance(shap_values, list):
                    shap_values = shap_values[1]

            logger.info(f"Computed SHAP values: shape={shap_values.shape}")
            return shap_values

        except Exception as e:
            logger.error(f"Failed to compute SHAP values: {e}")
            return None

    def get_top_features(
        self,
        shap_values: np.ndarray,
        top_n: int = 20,
    ) -> List[str]:
        """Get top N features by mean absolute SHAP value.

        Args:
            shap_values: SHAP values array
            top_n: Number of top features to return

        Returns:
            List of feature names sorted by importance (descending)
        """
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        top_indices = np.argsort(mean_abs_shap)[-top_n:][::-1]
        return [self.feature_names[i] for i in top_indices]
