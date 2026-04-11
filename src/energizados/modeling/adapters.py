"""
Model Adapters for Energizados Framework.

Provides adapters/wrappers for existing models
to comply with the framework's BaseModel interface.
"""

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

from energizados.core.base import BaseModel

logger = logging.getLogger(__name__)


def _warn_column_mismatch(available_columns, expected_columns, adapter_name: str) -> None:
    """Log a warning when there is a mismatch between available and expected columns."""
    extra = set(expected_columns) - set(available_columns)
    new = set(available_columns) - set(expected_columns)
    if extra:
        logger.warning(
            "%s: %d expected columns missing from input: %s",
            adapter_name,
            len(extra),
            extra if len(extra) <= 5 else list(extra)[:5],
        )
    if new:
        logger.debug(
            "%s: %d input columns not used by model (ignored silently).",
            adapter_name,
            len(new),
        )


class LGBMModelAdapter(BaseModel):
    """
    Adapter for LGBMModel that implements the BaseModel interface.

    This wrapper allows the existing LGBMModel
    to be used in the framework pipeline.

    Args:
        cols_for_model: Columns to use for the model.
        hyperparams: Model hyperparameters.
        search_hip: If True, performs hyperparameter search.
        sampling_th: Sampling threshold for imbalanced classes.
        sampling_method: Sampling method ('over', 'undersample', 'none').
        threshold: Classification threshold for binary predictions (default 0.5).
    """

    def __init__(
        self,
        cols_for_model: list,
        hyperparams: Optional[dict] = None,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "undersample",
        n_iter: int = 60,
        cv: int = 3,
        n_splits: int = 5,
        config: Optional[dict] = None,
        class_weight: Optional[dict] = None,
        threshold: float = 0.5,
    ):
        super().__init__(config)
        self.cols_for_model = cols_for_model
        self.hyperparams = hyperparams or {}
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method
        self.n_iter = n_iter
        self.cv = cv
        self.n_splits = n_splits
        self.class_weight = class_weight
        self.threshold = threshold
        self._trained_pipeline = None

        # Import the original model
        from energizados.modeling.supervised_models import LGBMModel as OriginalLGBM

        self._model = OriginalLGBM(
            cols_for_model=cols_for_model,
            hyperparams=hyperparams,
            search_hip=search_hip,
            sampling_th=sampling_th,
            sampling_method=sampling_method,
            n_iter=n_iter,
            cv=cv,
            n_splits=n_splits,
            class_weight=class_weight,
        )

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "LGBMModelAdapter":
        """
        Train the LightGBM model.

        Args:
            X: Training features.
            y: Training target.
            X_val: Validation features (optional).
            y_val: Validation target (optional).

        Returns:
            self: The fitted instance.
        """
        self._trained_pipeline = self._model.train(X, y, X_val, y_val)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make binary predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Binary predictions (0 or 1).
        """
        self.check_fitted()
        _warn_column_mismatch(X.columns, self.cols_for_model, self.__class__.__name__)
        return (
            self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1] > self.threshold
        ).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Positive class probabilities.
        """
        self.check_fitted()
        _warn_column_mismatch(X.columns, self.cols_for_model, self.__class__.__name__)
        return self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1]

    def get_raw_model(self) -> Any:
        """Extract the fitted LGBMClassifier from the trained pipeline.

        Returns:
            The fitted LGBMClassifier instance, or None if not yet trained.
        """
        if self._trained_pipeline is None:
            logger.warning("LGBMModelAdapter.get_raw_model() called before fit().")
            return None
        raw = self._trained_pipeline.named_steps.get("lgbmclassifier")
        if raw is None:
            logger.warning(
                "Step 'lgbmclassifier' not found in pipeline. Available: %s",
                list(self._trained_pipeline.named_steps.keys()),
            )
        return raw


class CATModelAdapter(BaseModel):
    """Adapter for CATModel that implements the BaseModel interface.

    Wraps CATModel to integrate CatBoost with the Energizados framework pipeline.

    Args:
        cols_for_model: Feature column names to pass to the model.
        hyperparams: CatBoost hyperparameter dict.
        search_hip: If True, performs hyperparameter search before training.
        sampling_th: Sampling ratio for the imblearn sampler.
        sampling_method: Sampling strategy ('over', 'undersample', or other for none).
        n_iter: Number of iterations for RandomizedSearchCV.
        cv: Number of cross-validation folds for RandomizedSearchCV.
        config: Optional framework configuration dict.
        class_weight: Class weights (dict or "balanced").
        threshold: Classification threshold for binary predictions (default 0.5).
    """

    def __init__(
        self,
        cols_for_model: list,
        hyperparams: Optional[dict] = None,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "undersample",
        n_iter: int = 60,
        cv: int = 3,
        n_splits: int = 5,
        config: Optional[dict] = None,
        class_weight: Optional[dict] = None,
        threshold: float = 0.5,
    ):
        super().__init__(config)
        self.cols_for_model = cols_for_model
        self.hyperparams = hyperparams or {}
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method
        self.n_iter = n_iter
        self.cv = cv
        self.n_splits = n_splits
        self.class_weight = class_weight
        self.threshold = threshold

        from energizados.modeling.supervised_models import CATModel as OriginalCAT

        self._model = OriginalCAT(
            cols_for_model=cols_for_model,
            hyperparams=hyperparams,
            search_hip=search_hip,
            sampling_th=sampling_th,
            sampling_method=sampling_method,
            n_iter=n_iter,
            cv=cv,
            n_splits=n_splits,
            class_weight=class_weight,
        )
        self._trained_pipeline = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "CATModelAdapter":
        """Train the CatBoost model.

        Args:
            X: Training features.
            y: Training target.
            X_val: Validation features (optional).
            y_val: Validation target (optional).

        Returns:
            self: The fitted instance.
        """
        self._trained_pipeline = self._model.train(X, y, X_val, y_val)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Binary predictions (0 or 1).
        """
        self.check_fitted()
        _warn_column_mismatch(X.columns, self.cols_for_model, self.__class__.__name__)
        return (
            self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1] > self.threshold
        ).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Make probability predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Positive class probabilities.
        """
        self.check_fitted()
        _warn_column_mismatch(X.columns, self.cols_for_model, self.__class__.__name__)
        return self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1]

    def get_raw_model(self) -> Any:
        """Extract the fitted CatBoostClassifier from the trained pipeline.

        Returns:
            The fitted CatBoostClassifier instance, or None if not yet trained.
        """
        if self._trained_pipeline is None:
            logger.warning("CATModelAdapter.get_raw_model() called before fit().")
            return None
        raw = self._trained_pipeline.named_steps.get("catboostclassifier")
        if raw is None:
            logger.warning(
                "Step 'catboostclassifier' not found in pipeline. Available: %s",
                list(self._trained_pipeline.named_steps.keys()),
            )
        return raw


class XGBModelAdapter(BaseModel):
    """Adapter for XGBModel that implements the BaseModel interface.

    Wraps XGBModel to integrate XGBoost with the Energizados framework pipeline.

    Args:
        cols_for_model: Feature column names to pass to the model.
        hyperparams: XGBoost hyperparameter dict.
        search_hip: If True, performs hyperparameter search before training.
        sampling_th: Sampling ratio for the imblearn sampler.
        sampling_method: Sampling strategy ('oversample', 'undersample', 'smotetomek', or other for none).
        n_iter: Number of iterations for RandomizedSearchCV.
        cv: Number of cross-validation folds for RandomizedSearchCV.
        config: Optional framework configuration dict.
        class_weight: scale_pos_weight value for XGBoost (int/float).
        threshold: Classification threshold for binary predictions (default 0.5).
    """

    def __init__(
        self,
        cols_for_model: list,
        hyperparams: Optional[dict] = None,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "undersample",
        n_iter: int = 60,
        cv: int = 3,
        n_splits: int = 5,
        config: Optional[dict] = None,
        class_weight: Optional[dict] = None,
        threshold: float = 0.5,
    ):
        super().__init__(config)
        self.cols_for_model = cols_for_model
        self.hyperparams = hyperparams or {}
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method
        self.n_iter = n_iter
        self.cv = cv
        self.n_splits = n_splits
        self.class_weight = class_weight
        self.threshold = threshold

        from energizados.modeling.supervised_models import XGBModel as OriginalXGB

        self._model = OriginalXGB(
            cols_for_model=cols_for_model,
            hyperparams=hyperparams,
            search_hip=search_hip,
            sampling_th=sampling_th,
            sampling_method=sampling_method,
            n_iter=n_iter,
            cv=cv,
            n_splits=n_splits,
            class_weight=class_weight,
        )
        self._trained_pipeline = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "XGBModelAdapter":
        """Train the XGBoost model.

        Args:
            X: Training features.
            y: Training target.
            X_val: Validation features (optional).
            y_val: Validation target (optional).

        Returns:
            self: The fitted instance.
        """
        self._trained_pipeline = self._model.train(X, y, X_val, y_val)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Binary predictions (0 or 1).
        """
        self.check_fitted()
        _warn_column_mismatch(X.columns, self.cols_for_model, self.__class__.__name__)
        return (
            self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1] > self.threshold
        ).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Make probability predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Positive class probabilities.
        """
        self.check_fitted()
        _warn_column_mismatch(X.columns, self.cols_for_model, self.__class__.__name__)
        return self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1]

    def get_raw_model(self) -> Any:
        """Extract the fitted XGBClassifier from the trained pipeline.

        Returns:
            The fitted XGBClassifier instance, or None if not yet trained.
        """
        if self._trained_pipeline is None:
            logger.warning("XGBModelAdapter.get_raw_model() called before fit().")
            return None
        raw = self._trained_pipeline.named_steps.get("xgbclassifier")
        if raw is None:
            logger.warning(
                "Step 'xgbclassifier' not found in pipeline. Available: %s",
                list(self._trained_pipeline.named_steps.keys()),
            )
        return raw


class NNModelAdapter(BaseModel):
    """Adapter for NNModel that implements the BaseModel interface.

    Wraps NNModel to integrate the feedforward neural network with the Energizados
    framework pipeline. Stores separate feature and consumption scalers after training.

    Args:
        features_names: Categorical feature column names.
        spents_names: Consumption column names (ordered oldest to newest).
        search_hip: If True, performs hyperparameter search (not currently used by NNModel).
        sampling_th: Sampling ratio for the imblearn sampler.
        sampling_method: Sampling strategy ('over', 'undersample', or other for none).
        config: Optional framework configuration dict.
        threshold: Classification threshold for binary predictions (default 0.5).
    """

    def __init__(
        self,
        features_names: list,
        spents_names: list,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "undersample",
        config: Optional[dict] = None,
        threshold: float = 0.5,
    ):
        super().__init__(config)
        self.features_names = features_names
        self.spents_names = spents_names
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method
        self.threshold = threshold

        from energizados.modeling.supervised_models import NNModel as OriginalNN

        self._model = OriginalNN(
            features_names=features_names,
            spents_names=spents_names,
            search_hip=search_hip,
            sampling_th=sampling_th,
            sampling_method=sampling_method,
        )
        self._pipe_features = None
        self._pipe_spent = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "NNModelAdapter":
        """Train the feedforward neural network.

        Args:
            X: Training features.
            y: Training target.
            X_val: Validation features (optional).
            y_val: Validation target (optional).

        Returns:
            self: The fitted instance.
        """
        result = self._model.train(X, y, X_val, y_val)
        self.model_ = result[0]
        self._pipe_features = result[1]
        self._pipe_spent = result[2]
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Binary predictions (0 or 1).
        """
        self.check_fitted()
        _warn_column_mismatch(
            X.columns, self.features_names + self.spents_names, self.__class__.__name__
        )
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        X_combined = np.concatenate([X_features, X_spents], axis=1)
        return (self.model_.predict(X_combined, verbose=0) > self.threshold).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Make probability predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Positive class probabilities.
        """
        self.check_fitted()
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        X_combined = np.concatenate([X_features, X_spents], axis=1)
        return self.model_.predict(X_combined, verbose=0).flatten()

    def get_raw_model(self) -> Any:
        """Extract the fitted Keras model.

        Returns:
            The fitted Keras Model instance, or None if not yet trained.
        """
        if self.model_ is None:
            logger.warning("NNModelAdapter.get_raw_model() called before fit().")
            return None
        logger.debug("Returning raw Keras model from NNModelAdapter.")
        return self.model_


class LSTMNNModelAdapter(BaseModel):
    """Adapter for LSTMNNModel that implements the BaseModel interface.

    Wraps LSTMNNModel to integrate the LSTM neural network with the Energizados
    framework pipeline. Stores separate feature and consumption scalers after training
    and reshapes consumption sequences to (samples, periodo, 1) for inference.

    Args:
        features_names: Categorical feature column names.
        spents_names: Consumption column names (ordered oldest to newest).
        search_hip: If True, performs hyperparameter search (not currently used by LSTMNNModel).
        sampling_th: Sampling ratio for the imblearn sampler.
        sampling_method: Sampling strategy ('over', 'undersample', or other for none).
        config: Optional framework configuration dict.
        threshold: Classification threshold for binary predictions (default 0.5).
    """

    def __init__(
        self,
        features_names: list,
        spents_names: list,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "undersample",
        config: Optional[dict] = None,
        threshold: float = 0.5,
    ):
        super().__init__(config)
        self.features_names = features_names
        self.spents_names = spents_names
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method
        self.threshold = threshold
        self.periodo = 12

        from energizados.modeling.supervised_models import LSTMNNModel as OriginalLSTM

        self._model = OriginalLSTM(
            features_names=features_names,
            spents_names=spents_names,
            search_hip=search_hip,
            sampling_th=sampling_th,
            sampling_method=sampling_method,
        )
        self._pipe_features = None
        self._pipe_spent = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "LSTMNNModelAdapter":
        """Train the LSTM neural network.

        Args:
            X: Training features.
            y: Training target.
            X_val: Validation features (optional).
            y_val: Validation target (optional).

        Returns:
            self: The fitted instance.
        """
        result = self._model.train(X, y, X_val, y_val)
        self.model_ = result[0]
        self._pipe_features = result[1]
        self._pipe_spent = result[2]
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Binary predictions (0 or 1).
        """
        self.check_fitted()
        _warn_column_mismatch(
            X.columns, self.features_names + self.spents_names, self.__class__.__name__
        )
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        if hasattr(X_features, "values"):
            X_features = X_features.values
        if hasattr(X_spents, "values"):
            X_spents = X_spents.values
        X_spents = X_spents.reshape((X_spents.shape[0], self.periodo, 1))
        probs = self.model_.predict([X_spents, X_features], verbose=0)
        return (probs > self.threshold).astype(int).flatten()

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Make probability predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Positive class probabilities.
        """
        self.check_fitted()
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        # Convert to numpy arrays if needed (sklearn may return DataFrames)
        if hasattr(X_features, "values"):
            X_features = X_features.values
        if hasattr(X_spents, "values"):
            X_spents = X_spents.values
        X_spents = X_spents.reshape((X_spents.shape[0], self.periodo, 1))
        return self.model_.predict([X_spents, X_features], verbose=0).flatten()

    def get_raw_model(self) -> Any:
        """Extract the fitted Keras model.

        Returns:
            The fitted Keras Model instance, or None if not yet trained.
        """
        if self.model_ is None:
            logger.warning("LSTMNNModelAdapter.get_raw_model() called before fit().")
            return None
        logger.debug("Returning raw Keras model from LSTMNNModelAdapter.")
        return self.model_


class SimpleTrendAdapter(BaseModel):
    """Adapter for ChangeTrendPercentajeIdentifierWide that implements BaseModel.

    Wraps the rule-based trend classifier to integrate it with the Energizados
    framework pipeline. Uses the trend percentage drop as a fraud probability proxy.

    Args:
        last_base_value: Number of historical periods used as the baseline.
        last_eval_value: Number of recent periods used for evaluation.
        threshold: Percentage drop above which a user is flagged as fraudulent.
        config: Optional framework configuration dict.
    """

    def __init__(
        self,
        last_base_value: int = 6,
        last_eval_value: int = 3,
        threshold: float = 50,
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.last_base_value = last_base_value
        self.last_eval_value = last_eval_value
        self.threshold = threshold

        from energizados.modeling.simple_models import (
            ChangeTrendPercentajeIdentifierWide,
        )

        self._model = ChangeTrendPercentajeIdentifierWide(
            last_base_value=last_base_value,
            last_eval_value=last_eval_value,
            threshold=threshold,
            is_wide=True,
        )

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "SimpleTrendAdapter":
        """No-op fit. This model has no learnable parameters.

        Args:
            X: Ignored.
            y: Ignored.
            X_val: Ignored.
            y_val: Ignored.

        Returns:
            self: The fitted instance.
        """
        # Simple model does not require training
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary fraud predictions based on consumption trend drop.

        Args:
            X: Wide-format DataFrame with consumption columns.

        Returns:
            np.ndarray: Binary predictions (1 = fraud, 0 = normal).
        """
        self.check_fitted()
        result = self._model.predict(X)
        return result["is_fraud_trend_perc"].values

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Estimate fraud probability from the trend percentage drop.

        Args:
            X: Wide-format DataFrame with consumption columns.

        Returns:
            np.ndarray: Fraud probability proxy in [0, 1].
        """
        self.check_fitted()
        result = self._model.predict(X)
        proba = (100 - result["trend_perc"]).values / 100
        proba = np.where(np.isnan(proba), 0.5, proba)
        return np.clip(proba, 0.0, 1.0)

    def get_raw_model(self) -> Any:
        """Rule-based model has no raw fitted model.

        Returns:
            self: The adapter instance itself (SHAP is not applicable).
        """
        logger.debug("SimpleTrendAdapter.get_raw_model() returning self (rule-based).")
        return self


class SimpleConstantAdapter(BaseModel):
    """Adapter for ConstantConsumptionClassifierWide that implements BaseModel.

    Wraps the rule-based constant consumption classifier to integrate it with the
    Energizados framework pipeline.

    Args:
        min_count_constante: Minimum run length of identical values to flag as fraud.
        config: Optional framework configuration dict.
    """

    def __init__(
        self,
        min_count_constante: int = 3,
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.min_count_constante = min_count_constante

        from energizados.modeling.simple_models import ConstantConsumptionClassifierWide

        self._model = ConstantConsumptionClassifierWide(min_count_constante=min_count_constante)

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "SimpleConstantAdapter":
        """No-op fit. This model has no learnable parameters.

        Args:
            X: Ignored.
            y: Ignored.
            X_val: Ignored.
            y_val: Ignored.

        Returns:
            self: The fitted instance.
        """
        # Simple model does not require training
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary fraud predictions based on constant consumption detection.

        Args:
            X: DataFrame where each row contains the consumption sequence for one user.

        Returns:
            np.ndarray: Binary predictions (1 = fraud, 0 = normal).
        """
        self.check_fitted()
        return self._model.predict(X).values

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return binary predictions as float probabilities.

        For this rule-based model, predictions are always 0.0 or 1.0.

        Args:
            X: DataFrame where each row contains the consumption sequence for one user.

        Returns:
            np.ndarray: Float predictions (0.0 or 1.0).
        """
        self.check_fitted()
        # For this model, binary predictions are the only ones available
        return self._model.predict(X).values.astype(float)

    def get_raw_model(self) -> Any:
        """Rule-based model has no raw fitted model.

        Returns:
            self: The adapter instance itself (SHAP is not applicable).
        """
        logger.debug("SimpleConstantAdapter.get_raw_model() returning self (rule-based).")
        return self


class IsolationForestAdapter(BaseModel):
    """Adapter for IsolationForest that implements the BaseModel interface.

    Wraps sklearn's IsolationForest to integrate anomaly detection with the
    Energizados framework pipeline. Isolation Forest is an unsupervised model
    that isolates anomalies by randomly partitioning features.

    The model is trained without labels (y is ignored). Predictions use the
    anomaly score converted to a probability via min-max scaling.

    Args:
        cols_for_model: Columns to use for the model.
        hyperparams: IsolationForest hyperparameters (n_estimators, max_samples, etc.).
        sampling_th: Contamination parameter (proportion of anomalies expected).
            Options: 'auto' or float between 0 and 0.5.
        sampling_method: Ignored (present for interface compatibility).
        config: Optional framework configuration dict.
    """

    def __init__(
        self,
        cols_for_model: list,
        hyperparams: Optional[dict] = None,
        sampling_th: float = 0.1,
        sampling_method: str = "none",
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.cols_for_model = cols_for_model
        self.hyperparams = hyperparams or {}
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method

        # Import sklearn's IsolationForest
        from sklearn.ensemble import IsolationForest as SklearnIF

        # Set contamination from sampling_th
        hyperparams_with_contamination = {**self.hyperparams, "contamination": sampling_th}

        self._model = SklearnIF(**hyperparams_with_contamination)
        self._score_min = None
        self._score_max = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "IsolationForestAdapter":
        """Train the Isolation Forest model.

        Note: IsolationForest is unsupervised, so y is ignored during training.

        Args:
            X: Training features.
            y: Ignored (present for interface compatibility).
            X_val: Ignored.
            y_val: Ignored.

        Returns:
            self: The fitted instance.
        """
        X_train = X[self.cols_for_model].copy()

        self._train_medians = X_train.median()

        X_train = X_train.fillna(self._train_medians)

        self._model.fit(X_train)

        # Store the anomaly scores for min-max scaling later
        self._score_samples = self._model.score_samples(X_train)

        # Store min and max for probability conversion
        self._score_min = np.min(self._score_samples)
        self._score_max = np.max(self._score_samples)

        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions (anomaly = 1, normal = 0).

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Binary predictions (1 = anomaly, 0 = normal).
        """
        self.check_fitted()
        _warn_column_mismatch(X.columns, self.cols_for_model, self.__class__.__name__)
        X_pred = X[self.cols_for_model].copy()
        X_pred = X_pred.fillna(self._train_medians)
        raw_predictions = self._model.predict(X_pred)

        # Convert -1 (outlier) to 1 (fraud), 1 (inlier) to 0 (normal)
        return ((raw_predictions + 1) / 2).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Make probability predictions based on anomaly score.

        Uses min-max scaling of the anomaly scores (fitted on the training set)
        to convert them to probabilities in [0, 1]. Lower scores (more anomalous)
        get higher probability of being fraud.

        **Limitation**: The scaling bounds are derived from the training set.
        Inference samples whose anomaly scores fall outside the training range
        are clipped — they are correctly bounded at 0.0 or 1.0, but the clipping
        discards granularity for very extreme samples. A warning is emitted when
        this occurs so callers are aware.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Anomaly probability in [0, 1].
        """
        self.check_fitted()
        _warn_column_mismatch(X.columns, self.cols_for_model, self.__class__.__name__)
        X_pred = X[self.cols_for_model].copy()
        X_pred = X_pred.fillna(self._train_medians)
        scores = self._model.score_samples(X_pred)

        # Handle edge case where all scores are the same
        if self._score_max == self._score_min:
            return np.full(len(scores), 0.5)

        # Warn when test scores fall outside training range — the clipping below
        # keeps probabilities valid but signals the model may be underfit or that
        # inference data is significantly different from training data.
        out_of_range = int(np.sum((scores < self._score_min) | (scores > self._score_max)))
        if out_of_range > 0:
            logger.warning(
                f"IsolationForestAdapter: {out_of_range}/{len(scores)} samples have anomaly "
                f"scores outside the training range [{self._score_min:.4f}, "
                f"{self._score_max:.4f}]. Probabilities will be clipped to [0, 1]. "
                "Consider retraining on a more representative sample."
            )

        # Min-max scale scores to [0, 1] and invert so higher = more likely anomaly.
        # score_samples returns: higher = more normal → we invert.
        proba = 1 - (scores - self._score_min) / (self._score_max - self._score_min)

        return np.clip(proba, 0.0, 1.0)

    def get_raw_model(self) -> Any:
        """Extract the fitted IsolationForest from the adapter.

        Returns:
            The fitted sklearn IsolationForest instance, or None if not yet trained.
        """
        if self._model is None:
            logger.warning("IsolationForestAdapter.get_raw_model() called before fit().")
            return None
        return self._model
