"""
Model Adapters for Energizados Framework.

Provides adapters/wrappers for existing models
to comply with the framework's BaseModel interface.
"""

from typing import Optional

import numpy as np
import pandas as pd

from energizados.core.base import BaseModel


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
        config: Optional[dict] = None,
        class_weight: Optional[dict] = None,
    ):
        super().__init__(config)
        self.cols_for_model = cols_for_model
        self.hyperparams = hyperparams or {}
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method
        self.n_iter = n_iter
        self.cv = cv
        self.class_weight = class_weight
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
        return (self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1] > 0.5).astype(
            int
        )

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Positive class probabilities.
        """
        self.check_fitted()
        return self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1]


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
        config: Optional[dict] = None,
        class_weight: Optional[dict] = None,
    ):
        super().__init__(config)
        self.cols_for_model = cols_for_model
        self.hyperparams = hyperparams or {}
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method
        self.n_iter = n_iter
        self.cv = cv
        self.class_weight = class_weight

        from energizados.modeling.supervised_models import CATModel as OriginalCAT

        self._model = OriginalCAT(
            cols_for_model=cols_for_model,
            hyperparams=hyperparams,
            search_hip=search_hip,
            sampling_th=sampling_th,
            sampling_method=sampling_method,
            n_iter=n_iter,
            cv=cv,
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
        return (self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1] > 0.5).astype(
            int
        )

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Make probability predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Positive class probabilities.
        """
        self.check_fitted()
        return self._trained_pipeline.predict_proba(X[self.cols_for_model])[:, 1]


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
    """

    def __init__(
        self,
        features_names: list,
        spents_names: list,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "undersample",
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.features_names = features_names
        self.spents_names = spents_names
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method

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
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        X_combined = np.concatenate([X_features, X_spents], axis=1)
        return (self.model_.predict(X_combined, verbose=0) > 0.5).astype(int)

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
    """

    def __init__(
        self,
        features_names: list,
        spents_names: list,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "undersample",
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.features_names = features_names
        self.spents_names = spents_names
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method
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
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        # Convert to numpy arrays if needed (sklearn may return DataFrames)
        if hasattr(X_features, "values"):
            X_features = X_features.values
        if hasattr(X_spents, "values"):
            X_spents = X_spents.values
        X_spents = X_spents.reshape((X_spents.shape[0], self.periodo, 1))
        probs = self.model_.predict([X_spents, X_features], verbose=0)
        return (probs > 0.5).astype(int).flatten()

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
        # Use trend_perc as probability proxy, handle NaN values
        proba = (100 - result["trend_perc"]).values / 100
        # Replace NaN with 0.5 (neutral probability) for rows with missing consumption data
        proba = np.where(np.isnan(proba), 0.5, proba)
        return proba


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
