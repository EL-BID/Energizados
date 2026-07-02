"""
Ensemble Model for Energizados Framework.

Combines N base models via soft voting or stacking with a meta-learner.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from energizados.core.base import BaseModel

logger = logging.getLogger(__name__)


class EnsembleModel(BaseModel):
    """
    Combines N base models into an ensemble using soft voting or stacking.

    Base models are trained externally (in TrainingStep) and passed in already
    fitted. This class only orchestrates combination logic and, for stacking,
    trains the meta-learner.

    Args:
        base_models: Already-instantiated (and optionally pre-fitted) base models.
        model_types: Type string per model (e.g. ["lightgbm", "catboost"]).
        model_names: Name per model (e.g. ["lgbm", "cat"]).
        method: Combination strategy — "soft_voting" or "stacking".
        meta_learner_config: Config dict for the meta-learner when method="stacking".
            Keys: "type" (default "logistic_regression"), "params" (dict).
        weights: Per-model weights for soft voting. None means equal weights.
        use_val_as_oof: When True (blending), use val set predictions as stack
            features for the meta-learner. When False, generate proper K-fold OOF
            predictions on the training set (expensive).
        cv: Number of folds used when use_val_as_oof=False.
        skip_base_fit: When True, base models are assumed already fitted and
            EnsembleModel.fit() only trains the meta-learner.
        threshold: Classification threshold for binary predictions (default 0.5).

    Note (data leakage in stacking with blending):
        When ``use_val_as_oof=True`` (blending mode), base models may have seen
        ``X_val`` during their own early-stopping phase.  This means the meta-learner
        is trained on predictions that are not truly out-of-fold.  For production-
        grade evaluation, set ``use_val_as_oof=False`` to generate proper K-fold OOF
        predictions, or reserve a separate hold-out set for the meta-learner.
    """

    def __init__(
        self,
        base_models: List[BaseModel],
        model_types: List[str],
        model_names: List[str],
        method: str = "soft_voting",
        meta_learner_config: Optional[Dict] = None,
        weights: Optional[List[float]] = None,
        use_val_as_oof: bool = True,
        cv: int = 5,
        skip_base_fit: bool = False,
        threshold: float = 0.5,
    ):
        super().__init__()
        self.base_models = base_models
        self.model_types = model_types
        self.model_names = model_names
        self.method = method
        self.meta_learner_config = meta_learner_config or {}
        self.weights = weights
        self.use_val_as_oof = use_val_as_oof
        self.cv = cv
        self.skip_base_fit = skip_base_fit
        self.threshold = threshold
        self._meta_learner = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "EnsembleModel":
        """
        Fit the ensemble.

        When skip_base_fit=True, assumes base models are already fitted and only
        trains the meta-learner (stacking). For soft_voting, fit() is a no-op
        after base models are fitted.

        Args:
            X: Training features.
            y: Training target.
            X_val: Validation features (used for blending when use_val_as_oof=True).
            y_val: Validation target (used for blending when use_val_as_oof=True).

        Returns:
            self: The fitted ensemble.
        """
        if not self.skip_base_fit:
            logger.info("Fitting base models inside EnsembleModel...")
            for name, model in zip(self.model_names, self.base_models):
                logger.info(f"  Fitting base model: {name}")
                model.fit(X, y, X_val=X_val, y_val=y_val)

        if self.method == "stacking":
            self._fit_meta_learner(X, y, X_val, y_val)

        self.is_fitted_ = True
        return self

    def _fit_meta_learner(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame],
        y_val: Optional[pd.Series],
    ) -> None:
        """Train the meta-learner on stacked predictions."""
        if self.use_val_as_oof:
            if X_val is None or y_val is None:
                raise ValueError("use_val_as_oof=True requires X_val and y_val.")
            logger.info("Stacking: using val set as blending data for meta-learner.")
            stack_X = self._stack_predictions(X_val)
            stack_y = y_val
        else:
            logger.info(f"Stacking: generating OOF predictions via {self.cv}-fold CV.")
            stack_X, stack_y = self._generate_oof(X, y)

        meta = self._build_meta_learner()
        meta.fit(stack_X, stack_y)
        self._meta_learner = meta
        logger.info("Meta-learner fitted.")

    def _stack_predictions(self, X: pd.DataFrame) -> np.ndarray:
        """Return column-stacked predict_proba output from all base models."""
        return np.column_stack([m.predict_proba(X) for m in self.base_models])

    def _generate_oof(self, X: pd.DataFrame, y: pd.Series):
        """
        Generate out-of-fold predictions for stacking without data leakage.

        Re-instantiates each base model per fold using the same class and config,
        trains on the in-fold split, and predicts on the out-of-fold split.

        Returns:
            Tuple[np.ndarray, np.ndarray]: (stack_features, stack_targets)
        """
        from sklearn.model_selection import StratifiedKFold

        skf = StratifiedKFold(n_splits=self.cv, shuffle=True, random_state=42)
        n_samples = len(y)
        oof_preds = np.zeros((n_samples, len(self.base_models)))

        X_arr = X.reset_index(drop=True)
        y_arr = y.reset_index(drop=True)

        for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X_arr, y_arr)):
            logger.info(f"  OOF fold {fold_idx + 1}/{self.cv}")
            X_fold_train = X_arr.iloc[train_idx]
            y_fold_train = y_arr.iloc[train_idx]
            X_fold_val = X_arr.iloc[val_idx]

            for model_idx, (base_model, name) in enumerate(zip(self.base_models, self.model_names)):
                # Clone the model by re-creating an instance of the same class with same init params
                fold_model = self._clone_model(base_model)
                fold_model.fit(X_fold_train, y_fold_train)
                oof_preds[val_idx, model_idx] = fold_model.predict_proba(X_fold_val)

        return oof_preds, y_arr.values

    def _clone_model(self, model: BaseModel) -> BaseModel:
        """
        Create a fresh (unfitted) copy of a base model with the same parameters.

        Uses sklearn's clone() when possible (requires ``get_params()``), otherwise
        falls back to re-instantiating with the same ``__init__`` arguments via
        ``__dict__``.
        """
        try:
            from sklearn.base import clone as sklearn_clone

            return sklearn_clone(model)
        except Exception:  # nosec B110
            logger.debug(
                "sklearn clone failed for %s — falling back to __dict__ re-instantiation.",
                type(model).__name__,
            )

        # Fallback: re-instantiate with same class using public init params only.
        # Excludes private attrs (prefixed with '_'), fitted state, and config.
        cls = model.__class__
        init_params = {
            k: v
            for k, v in model.__dict__.items()
            if not k.startswith("_") and k not in ("is_fitted_", "model_", "config")
        }
        return cls(**init_params)

    def _build_meta_learner(self):
        """Instantiate the meta-learner from config."""
        meta_type = self.meta_learner_config.get("type", "logistic_regression")
        params = self.meta_learner_config.get("params", {})

        if meta_type == "logistic_regression":
            from sklearn.linear_model import LogisticRegression

            return LogisticRegression(**params)

        # Delegate to ModelRegistry for other types (lightgbm, catboost, etc.)
        from energizados.modeling.registry import ModelRegistry

        cls = ModelRegistry.get(meta_type)
        meta = cls(**params)

        # Wrap adapters with _SklearnCalibWrapper to provide 2D predict_proba
        # (adapters expose 1D predict_proba, but sklearn stacking expects 2D)
        from energizados.core.steps.training import _SklearnCalibWrapper

        return _SklearnCalibWrapper(meta)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict positive-class probabilities.

        For soft voting: weighted (or equal) average of base model probabilities.
        For stacking: meta-learner prediction over stacked base probabilities.

        Args:
            X: Feature DataFrame.

        Returns:
            np.ndarray: 1-D array of positive-class probabilities.
        """
        self.check_fitted()
        base_preds = self._stack_predictions(X)

        if self.method == "stacking":
            return self._meta_learner.predict_proba(base_preds)[:, 1]

        # soft_voting
        w = self.weights or [1.0 / len(self.base_models)] * len(self.base_models)
        return np.average(base_preds, axis=1, weights=w)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make binary predictions using a 0.5 threshold on predict_proba.

        Args:
            X: Feature DataFrame.

        Returns:
            np.ndarray: Binary predictions (0 or 1).
        """
        return (self.predict_proba(X) >= self.threshold).astype(int)

    @property
    def ensemble_description(self) -> str:
        """Human-readable description for reports, e.g. 'Ensemble (lightgbm, catboost)'."""
        return f"Ensemble ({', '.join(self.model_types)})"

    def get_raw_model(self) -> Any:
        """Extract raw models from all base models.

        Returns:
            Dict mapping model names to their raw fitted models.
            Returns None if no base models are available.
        """
        if not self.base_models:
            logger.warning("EnsembleModel.get_raw_model() called with no base models.")
            return None
        raw_models = {}
        for name, model in zip(self.model_names, self.base_models):
            raw = model.get_raw_model()
            if raw is not None:
                raw_models[name] = raw
            else:
                logger.warning("Base model '%s' returned None from get_raw_model().", name)
        logger.debug("EnsembleModel.get_raw_model() returning %d raw models.", len(raw_models))
        return raw_models if raw_models else None
