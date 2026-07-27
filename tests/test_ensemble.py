"""Tests for EnsembleModel no-holdout compatibility (FR6)."""
import numpy as np
import pandas as pd
import pytest

from energizados.core.exceptions import ConfigurationError
from energizados.modeling.ensemble import EnsembleModel


class _MockModel:
    """Minimal fitted base model for ensemble tests."""

    def __init__(self):
        self.is_fitted_ = True

    def fit(self, X, y, X_val=None, y_val=None):
        return self

    def predict_proba(self, X):
        return np.random.rand(len(X))


def _data(n=40):
    X = pd.DataFrame({"f": np.random.rand(n)})
    y = pd.Series([0, 1] * (n // 2))
    return X, y


class TestEnsembleNoHoldout:
    """FR6: blending raises ConfigurationError; soft-voting and K-fold-OOF work."""

    def test_ensemble_blending_no_val_raises_config_error(self):
        X, y = _data()
        ens = EnsembleModel(
            base_models=[_MockModel(), _MockModel()],
            model_types=["lightgbm", "lightgbm"],
            model_names=["a", "b"],
            method="stacking",
            use_val_as_oof=True,
            skip_base_fit=True,
        )
        with pytest.raises(ConfigurationError, match="use_val_as_oof"):
            ens.fit(X, y, X_val=None, y_val=None)

    def test_ensemble_soft_voting_no_holdout_succeeds(self):
        X, y = _data()
        ens = EnsembleModel(
            base_models=[_MockModel(), _MockModel()],
            model_types=["lightgbm", "lightgbm"],
            model_names=["a", "b"],
            method="soft_voting",
            skip_base_fit=True,
        )
        ens.fit(X, y, X_val=None, y_val=None)  # should not raise
        assert ens.is_fitted_ is True

    def test_ensemble_kfold_oof_no_holdout_succeeds(self):
        X, y = _data(60)
        ens = EnsembleModel(
            base_models=[_MockModel(), _MockModel()],
            model_types=["lightgbm", "lightgbm"],
            model_names=["a", "b"],
            method="stacking",
            use_val_as_oof=False,
            cv=2,
            skip_base_fit=True,
        )
        ens.fit(X, y, X_val=None, y_val=None)  # K-fold OOF, no val needed
        assert ens.is_fitted_ is True
