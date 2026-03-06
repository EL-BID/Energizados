"""
Model Adapters for Energizados Framework.

Proporciona adaptadores/wrappers para los modelos existentes
para que cumplan con la interfaz de BaseModel del framework.
"""

from typing import Optional

import numpy as np
import pandas as pd

from energizados.core.base import BaseModel


class LGBMModelAdapter(BaseModel):
    """
    Adaptador para LGBMModel que implementa la interfaz BaseModel.

    Este wrapper permite que el modelo LGBMModel existente
    se use en el pipeline del framework.

    Args:
        cols_for_model: Columnas a usar para el modelo
        hyperparams: Hiperparámetros del modelo
        search_hip: Si es True, realiza búsqueda de hiperparámetros
        sampling_th: Umbral de muestreo para clases desbalanceadas
        sampling_method: Método de muestreo ('over', 'under', 'none')
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

        # Importar el modelo original
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
        Entrena el modelo LightGBM.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento
            X_val: Features de validación (opcional)
            y_val: Target de validación (opcional)

        Returns:
            self
        """
        self._model = self._model.train(X, y, X_val, y_val)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones binarias.

        Args:
            X: Features para predicción

        Returns:
            np.ndarray: Predicciones binarias (0 o 1)
        """
        self.check_fitted()
        return (self._model.predict_proba(X[self.cols_for_model])[:, 1] > 0.5).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones de probabilidad.

        Args:
            X: Features para predicción

        Returns:
            np.ndarray: Probabilidades de la clase positiva
        """
        self.check_fitted()
        return self._model.predict_proba(X[self.cols_for_model])[:, 1]


class CATModelAdapter(BaseModel):
    """
    Adaptador para CATModel que implementa la interfaz BaseModel.
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
    Adaptador para NNModel que implementa la interfaz BaseModel.
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
    Adaptador para LSTMNNModel que implementa la interfaz BaseModel.
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
    Adaptador para ChangeTrendPercentajeIdentifierWide que implementa BaseModel.
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
        # Modelo simple no requiere entrenamiento
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        result = self._model.predict(X)
        return result["is_fraud_trend_perc"].values

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        result = self._model.predict(X)
        # Usar trend_perc como proxy de probabilidad
        return (100 - result["trend_perc"]).values / 100


class SimpleConstantAdapter(BaseModel):
    """
    Adaptador para ConstantConsumptionClassifierWide que implementa BaseModel.
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
        # Modelo simple no requiere entrenamiento
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        return self._model.predict(X).values

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        self.check_fitted()
        # Para este modelo, las predicciones binarias son las únicas disponibles
        return self._model.predict(X).values.astype(float)
