"""
Unit tests for EnsembleModel.

Tests cover soft voting, stacking (blending and OOF), name resolution,
ensemble_description property, and the skip_base_fit flag.
"""

import numpy as np
import pandas as pd
import pytest

from energizados.modeling.ensemble import EnsembleModel

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_dummy_model(proba_value: float):
    """Return a pre-fitted dummy BaseModel that always predicts ``proba_value``."""
    from energizados.core.base import BaseModel

    class DummyModel(BaseModel):
        def __init__(self, proba=0.5):
            super().__init__()
            self.proba = proba

        def fit(self, X, y, X_val=None, y_val=None):
            self.is_fitted_ = True
            return self

        def predict(self, X):
            self.check_fitted()
            return (np.full(len(X), self.proba) >= 0.5).astype(int)

        def predict_proba(self, X):
            self.check_fitted()
            return np.full(len(X), self.proba)

    m = DummyModel(proba=proba_value)
    m.is_fitted_ = True
    return m


@pytest.fixture
def sample_data():
    """Small binary classification dataset."""
    rng = np.random.default_rng(42)
    X = pd.DataFrame({"f1": rng.standard_normal(50), "f2": rng.standard_normal(50)})
    y = pd.Series((rng.standard_normal(50) > 0).astype(int))
    return X, y


@pytest.fixture
def split_data(sample_data):
    """80/20 train/val split."""
    X, y = sample_data
    X_train, X_val = X.iloc[:40], X.iloc[40:]
    y_train, y_val = y.iloc[:40], y.iloc[40:]
    return X_train, y_train, X_val, y_val


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestEnsembleModelConstruction:
    def test_default_attributes(self):
        m1 = _make_dummy_model(0.3)
        m2 = _make_dummy_model(0.7)
        ens = EnsembleModel(
            base_models=[m1, m2],
            model_types=["lightgbm", "catboost"],
            model_names=["lgbm", "cat"],
        )
        assert ens.method == "soft_voting"
        assert ens.weights is None
        assert ens.use_val_as_oof is True
        assert ens.cv == 5
        assert ens.skip_base_fit is False
        assert ens.is_fitted_ is False

    def test_ensemble_description_two_models(self):
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.3), _make_dummy_model(0.7)],
            model_types=["lightgbm", "catboost"],
            model_names=["lgbm", "cat"],
        )
        assert ens.ensemble_description == "Ensemble (lightgbm, catboost)"

    def test_ensemble_description_three_models(self):
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.3)] * 3,
            model_types=["lightgbm", "catboost", "neural_network"],
            model_names=["lgbm", "cat", "nn"],
        )
        assert ens.ensemble_description == "Ensemble (lightgbm, catboost, neural_network)"


# ---------------------------------------------------------------------------
# Soft voting
# ---------------------------------------------------------------------------


class TestSoftVoting:
    def test_predict_proba_equal_weights(self, split_data):
        """Equal-weight soft voting averages base probabilities."""
        X_train, y_train, X_val, y_val = split_data
        m1 = _make_dummy_model(0.2)
        m2 = _make_dummy_model(0.8)

        ens = EnsembleModel(
            base_models=[m1, m2],
            model_types=["a", "b"],
            model_names=["m1", "m2"],
            method="soft_voting",
            skip_base_fit=True,
        )
        ens.fit(X_train, y_train, X_val=X_val, y_val=y_val)

        proba = ens.predict_proba(X_val)
        expected = np.full(len(X_val), 0.5)  # (0.2 + 0.8) / 2
        np.testing.assert_allclose(proba, expected)

    def test_predict_proba_custom_weights(self, split_data):
        """Custom weights are applied correctly."""
        X_train, y_train, X_val, y_val = split_data
        m1 = _make_dummy_model(0.0)
        m2 = _make_dummy_model(1.0)

        ens = EnsembleModel(
            base_models=[m1, m2],
            model_types=["a", "b"],
            model_names=["m1", "m2"],
            method="soft_voting",
            weights=[0.7, 0.3],
            skip_base_fit=True,
        )
        ens.fit(X_train, y_train, X_val=X_val, y_val=y_val)

        proba = ens.predict_proba(X_val)
        expected = np.full(len(X_val), 0.3)  # 0.7*0.0 + 0.3*1.0
        np.testing.assert_allclose(proba, expected)

    def test_predict_binary(self, split_data):
        """predict() applies 0.5 threshold on predict_proba."""
        X_train, y_train, X_val, y_val = split_data
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.9), _make_dummy_model(0.8)],
            model_types=["a", "b"],
            model_names=["m1", "m2"],
            method="soft_voting",
            skip_base_fit=True,
        )
        ens.fit(X_train, y_train)
        preds = ens.predict(X_val)
        assert set(preds).issubset({0, 1})
        assert np.all(preds == 1)  # both models predict > 0.5

    def test_not_fitted_raises(self, sample_data):
        X, y = sample_data
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.5)],
            model_types=["a"],
            model_names=["m"],
            method="soft_voting",
        )
        from energizados.core.exceptions import ModelNotFittedError

        with pytest.raises(ModelNotFittedError):
            ens.predict_proba(X)

    def test_fit_base_models_internally(self, split_data):
        """When skip_base_fit=False, EnsembleModel fits the base models itself."""
        from energizados.core.base import BaseModel

        class TrackingModel(BaseModel):
            fitted_count = 0

            def fit(self, X, y, X_val=None, y_val=None):
                TrackingModel.fitted_count += 1
                self.is_fitted_ = True
                return self

            def predict(self, X):
                return np.zeros(len(X), dtype=int)

            def predict_proba(self, X):
                return np.full(len(X), 0.4)

        X_train, y_train, X_val, y_val = split_data
        TrackingModel.fitted_count = 0
        m1, m2 = TrackingModel(), TrackingModel()

        ens = EnsembleModel(
            base_models=[m1, m2],
            model_types=["x", "y"],
            model_names=["m1", "m2"],
            method="soft_voting",
            skip_base_fit=False,
        )
        ens.fit(X_train, y_train)
        assert TrackingModel.fitted_count == 2


# ---------------------------------------------------------------------------
# Stacking — blending (use_val_as_oof=True)
# ---------------------------------------------------------------------------


class TestStackingBlending:
    def test_stacking_blending_fits_meta_learner(self, split_data):
        """Stacking with use_val_as_oof=True trains a meta-learner."""
        X_train, y_train, X_val, y_val = split_data
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.3), _make_dummy_model(0.7)],
            model_types=["a", "b"],
            model_names=["m1", "m2"],
            method="stacking",
            meta_learner_config={"type": "logistic_regression", "params": {"max_iter": 200}},
            use_val_as_oof=True,
            skip_base_fit=True,
        )
        ens.fit(X_train, y_train, X_val=X_val, y_val=y_val)

        assert ens._meta_learner is not None
        assert ens.is_fitted_

    def test_stacking_blending_predict_proba_shape(self, split_data):
        """predict_proba returns 1-D array of length n_samples."""
        X_train, y_train, X_val, y_val = split_data
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.3), _make_dummy_model(0.6)],
            model_types=["a", "b"],
            model_names=["m1", "m2"],
            method="stacking",
            use_val_as_oof=True,
            skip_base_fit=True,
        )
        ens.fit(X_train, y_train, X_val=X_val, y_val=y_val)
        proba = ens.predict_proba(X_val)

        assert proba.shape == (len(X_val),)
        assert np.all((proba >= 0) & (proba <= 1))

    def test_stacking_requires_val_when_blending(self, split_data):
        """use_val_as_oof=True raises if X_val/y_val are not provided."""
        X_train, y_train, _, _ = split_data
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.3), _make_dummy_model(0.6)],
            model_types=["a", "b"],
            model_names=["m1", "m2"],
            method="stacking",
            use_val_as_oof=True,
            skip_base_fit=True,
        )
        with pytest.raises(ValueError, match="X_val"):
            ens.fit(X_train, y_train)  # no X_val/y_val

    def test_stacking_meta_learner_default_is_logistic_regression(self, split_data):
        """Default meta-learner is LogisticRegression."""
        from sklearn.linear_model import LogisticRegression

        X_train, y_train, X_val, y_val = split_data
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.3), _make_dummy_model(0.7)],
            model_types=["a", "b"],
            model_names=["m1", "m2"],
            method="stacking",
            use_val_as_oof=True,
            skip_base_fit=True,
        )
        ens.fit(X_train, y_train, X_val=X_val, y_val=y_val)
        assert isinstance(ens._meta_learner, LogisticRegression)


# ---------------------------------------------------------------------------
# Stacking — proper OOF (use_val_as_oof=False)
# ---------------------------------------------------------------------------


class TestStackingOOF:
    def test_stacking_oof_fits_meta_learner(self, split_data):
        """Stacking with use_val_as_oof=False generates OOF and trains meta-learner."""
        X_train, y_train, X_val, y_val = split_data
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.3), _make_dummy_model(0.7)],
            model_types=["a", "b"],
            model_names=["m1", "m2"],
            method="stacking",
            use_val_as_oof=False,
            cv=3,
            skip_base_fit=True,
        )
        ens.fit(X_train, y_train, X_val=X_val, y_val=y_val)

        assert ens._meta_learner is not None
        assert ens.is_fitted_

    def test_stacking_oof_predict_proba_shape(self, split_data):
        """predict_proba works after OOF stacking."""
        X_train, y_train, X_val, y_val = split_data
        ens = EnsembleModel(
            base_models=[_make_dummy_model(0.4), _make_dummy_model(0.6)],
            model_types=["a", "b"],
            model_names=["m1", "m2"],
            method="stacking",
            use_val_as_oof=False,
            cv=2,
            skip_base_fit=True,
        )
        ens.fit(X_train, y_train, X_val=X_val, y_val=y_val)
        proba = ens.predict_proba(X_val)

        assert proba.shape == (len(X_val),)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestEnsembleRegistry:
    def test_ensemble_registered(self):
        from energizados.modeling.registry import ModelRegistry

        assert ModelRegistry.is_registered("ensemble")

    def test_ensemble_class_is_ensemble_model(self):
        from energizados.modeling.registry import ModelRegistry

        cls = ModelRegistry.get("ensemble")
        assert cls is EnsembleModel
