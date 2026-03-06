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
        sampling_method: Sampling method ('over', 'under', 'none').
    """

    def __init__(
        self,
        cols_for_model: list,
        hyperparams: Optional[dict] = None,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "under",
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.cols_for_model = cols_for_model
        self.hyperparams = hyperparams or {}
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method

        # Import the original model
        from energizados.modeling.supervised_models import LGBMModel as OriginalLGBM

        self._model = OriginalLGBM(
            cols_for_model=cols_for_model,
            hyperparams=hyperparams,
            search_hip=search_hip,
            sampling_th=sampling_th,
            sampling_method=sampling_method,
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
        self._model = self._model.train(X, y, X_val, y_val)
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
        return (self._model.predict_proba(X[self.cols_for_model])[:, 1] > 0.5).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            X: Features for prediction.

        Returns:
            np.ndarray: Positive class probabilities.
        """
        self.check_fitted()
        return self._model.predict_proba(X[self.cols_for_model])[:, 1]


class CATModelAdapter(BaseModel):
    """
    Adapter for CATModel that implements the BaseModel interface.
    """

    def __init__(
        self,
        cols_for_model: list,
        hyperparams: Optional[dict] = None,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "under",
        config: Optional[dict] = None,
    ):
        super().__init__(config)
        self.cols_for_model = cols_for_model
        self.hyperparams = hyperparams or {}
        self.search_hip = search_hip
        self.sampling_th = sampling_th
        self.sampling_method = sampling_method

        from energizados.modeling.supervised_models import CATModel as OriginalCAT

        self._model = OriginalCAT(
            cols_for_model=cols_for_model,
            hyperparams=hyperparams,
            search_hip=search_hip,
            sampling_th=sampling_th,
            sampling_method=sampling_method,
        )

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "CATModelAdapter":
        self._model.train(X, y, X_val, y_val)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        return (self._model.predict_proba(X[self.cols_for_model])[:, 1] > 0.5).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        return self._model.predict_proba(X[self.cols_for_model])[:, 1]


class NNModelAdapter(BaseModel):
    """
    Adapter for NNModel that implements the BaseModel interface.
    """

    def __init__(
        self,
        features_names: list,
        spents_names: list,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "under",
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
        result = self._model.train(X, y, X_val, y_val)
        self.model_ = result[0]
        self._pipe_features = result[1]
        self._pipe_spent = result[2]
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        X_combined = np.concatenate([X_features, X_spents], axis=1)
        return (self.model_.predict(X_combined, verbose=0) > 0.5).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        X_combined = np.concatenate([X_features, X_spents], axis=1)
        return self.model_.predict(X_combined, verbose=0).flatten()


class LSTMNNModelAdapter(BaseModel):
    """
    Adapter for LSTMNNModel that implements the BaseModel interface.
    """

    def __init__(
        self,
        features_names: list,
        spents_names: list,
        search_hip: bool = False,
        sampling_th: float = 0.5,
        sampling_method: str = "under",
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
        result = self._model.train(X, y, X_val, y_val)
        self.model_ = result[0]
        self._pipe_features = result[1]
        self._pipe_spent = result[2]
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        X_spents = X_spents.reshape((X_spents.shape[0], self.periodo, 1))
        probs = self.model_.predict([X_spents, X_features], verbose=0)
        return (probs > 0.5).astype(int).flatten()

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        X_features = self._pipe_features.transform(X[self.features_names])
        X_spents = self._pipe_spent.transform(X[self.spents_names])
        X_spents = X_spents.reshape((X_spents.shape[0], self.periodo, 1))
        return self.model_.predict([X_spents, X_features], verbose=0).flatten()


class SimpleTrendAdapter(BaseModel):
    """
    Adapter for ChangeTrendPercentajeIdentifierWide that implements BaseModel.
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
        # Simple model does not require training
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        result = self._model.predict(X)
        return result["is_fraud_trend_perc"].values

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        result = self._model.predict(X)
        # Use trend_perc as probability proxy
        return (100 - result["trend_perc"]).values / 100


class SimpleConstantAdapter(BaseModel):
    """
    Adapter for ConstantConsumptionClassifierWide that implements BaseModel.
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
        # Simple model does not require training
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        return self._model.predict(X).values

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        # For this model, binary predictions are the only ones available
        return self._model.predict(X).values.astype(float)
