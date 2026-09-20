"""Tests for the configurable ``hyperparam_search.n_jobs`` wiring.

Covers two layers:

- Adapter ``from_config`` mapping of ``hyperparam_search.n_jobs`` to the
  ``search_n_jobs`` constructor kwarg, with per-model defaults preserved
  (lightgbm: -1, catboost: 4, xgboost: -1).
- Each model's ``find_hyp_*`` method forwarding ``search_n_jobs`` to
  ``RandomizedSearchCV(n_jobs=...)``.
"""

import pandas as pd
import pytest
from sklearn.pipeline import make_pipeline

from energizados.modeling import supervised_models
from energizados.modeling.adapters import (
    CATModelAdapter,
    LGBMModelAdapter,
    XGBModelAdapter,
)
from energizados.modeling.supervised_models import CATModel, LGBMModel, XGBModel


def _tiny_frame() -> pd.DataFrame:
    """Return a tiny DataFrame for from_config tests."""
    return pd.DataFrame(
        {
            "feature_1": [1.0, 2.0, 3.0, 4.0, 5.0],
            "feature_2": [5.0, 4.0, 3.0, 2.0, 1.0],
            "actividad": ["A", "B", "A", "B", "A"],
        }
    )


def _search_data():
    """Return synthetic X/y (20 rows, 3 columns, binary target) for search tests."""
    X = pd.DataFrame(
        {
            "f1": [float(i) for i in range(20)],
            "f2": [float((i * 7) % 13) for i in range(20)],
            "f3": [float((i * 3) % 5) for i in range(20)],
        }
    )
    y = pd.Series([0, 1] * 10, name="target")
    return X, y


class RecordingSearch:
    """Fake RandomizedSearchCV recording constructor kwargs; fit short-circuits."""

    calls = []

    def __init__(self, **kwargs):
        RecordingSearch.calls.append(kwargs)

    def fit(self, X, y=None, **fit_kwargs):
        self.best_score_ = 0.9
        self.best_params_ = {}
        return self


@pytest.fixture(autouse=True)
def _reset_recorded_calls():
    """Keep recorded constructor kwargs isolated per test."""
    RecordingSearch.calls = []
    yield


class TestFromConfigSearchNJobs:
    """hyperparam_search.n_jobs maps to search_n_jobs with model-specific defaults."""

    def test_lgbm_default_is_minus_one(self):
        """LGBM from_config defaults search_n_jobs to -1 when n_jobs is absent."""
        config = {
            "type": "lightgbm",
            "sampling": {"method": "undersample", "threshold": 0.5},
            "hyperparams": {"num_leaves": 31},
            "hyperparam_search": {"enabled": True, "n_iter": 10, "cv": 3},
        }
        params = LGBMModelAdapter.from_config(config.copy(), _tiny_frame())
        assert params["search_n_jobs"] == -1

    def test_lgbm_explicit_value(self):
        """LGBM from_config maps hyperparam_search.n_jobs to search_n_jobs."""
        config = {
            "type": "lightgbm",
            "sampling": {"method": "undersample", "threshold": 0.5},
            "hyperparams": {"num_leaves": 31},
            "hyperparam_search": {"enabled": True, "n_iter": 10, "cv": 3, "n_jobs": 2},
        }
        params = LGBMModelAdapter.from_config(config.copy(), _tiny_frame())
        assert params["search_n_jobs"] == 2

    def test_cat_default_is_four(self):
        """CAT from_config defaults search_n_jobs to 4 when n_jobs is absent."""
        config = {
            "type": "catboost",
            "sampling": {"method": "undersample", "threshold": 0.5},
            "hyperparams": {"iterations": 300},
            "hyperparam_search": {"enabled": True, "n_iter": 10, "cv": 3},
        }
        params = CATModelAdapter.from_config(config.copy(), _tiny_frame())
        assert params["search_n_jobs"] == 4

    def test_cat_explicit_value(self):
        """CAT from_config maps hyperparam_search.n_jobs to search_n_jobs."""
        config = {
            "type": "catboost",
            "sampling": {"method": "undersample", "threshold": 0.5},
            "hyperparams": {"iterations": 300},
            "hyperparam_search": {"enabled": True, "n_iter": 10, "cv": 3, "n_jobs": 2},
        }
        params = CATModelAdapter.from_config(config.copy(), _tiny_frame())
        assert params["search_n_jobs"] == 2

    def test_xgb_default_is_minus_one(self):
        """XGB from_config defaults search_n_jobs to -1 when n_jobs is absent."""
        config = {
            "type": "xgboost",
            "sampling": {"method": "undersample", "threshold": 0.5},
            "hyperparams": {"max_depth": 6},
            "hyperparam_search": {"enabled": True, "n_iter": 10, "cv": 3},
        }
        params = XGBModelAdapter.from_config(config.copy(), _tiny_frame())
        assert params["search_n_jobs"] == -1

    def test_xgb_explicit_value(self):
        """XGB from_config maps hyperparam_search.n_jobs to search_n_jobs."""
        config = {
            "type": "xgboost",
            "sampling": {"method": "undersample", "threshold": 0.5},
            "hyperparams": {"max_depth": 6},
            "hyperparam_search": {"enabled": True, "n_iter": 10, "cv": 3, "n_jobs": 2},
        }
        params = XGBModelAdapter.from_config(config.copy(), _tiny_frame())
        assert params["search_n_jobs"] == 2


class TestSearchUsesSearchNJobs:
    """find_hyp_* forwards search_n_jobs to RandomizedSearchCV(n_jobs=...)."""

    def test_lgbm_search_uses_search_n_jobs(self, monkeypatch):
        """LGBM RandomizedSearchCV receives n_jobs from search_n_jobs."""
        monkeypatch.setattr(supervised_models, "RandomizedSearchCV", RecordingSearch)
        X, y = _search_data()
        model = LGBMModel(
            cols_for_model=list(X.columns),
            hyperparams={},
            search_hip=True,
            search_n_jobs=2,
        )
        pipeline = model.build_pipeline_preproceso_model()
        model.find_hyp_lgbm_model(X, y, X, y, pipeline)
        assert len(RecordingSearch.calls) == 1
        assert RecordingSearch.calls[0]["n_jobs"] == 2

    def test_cat_search_uses_search_n_jobs(self, monkeypatch):
        """CAT RandomizedSearchCV receives n_jobs from search_n_jobs."""
        monkeypatch.setattr(supervised_models, "RandomizedSearchCV", RecordingSearch)
        X, y = _search_data()
        model = CATModel(
            cols_for_model=list(X.columns),
            hyperparams={},
            search_hip=True,
            search_n_jobs=2,
        )
        try:
            pipeline = model.build_pipeline_preproceso_model(cat_features=[])
        except ImportError:
            # catboost is an optional dependency and may not be installed; the
            # CatBoost search path only forwards the estimator to
            # RandomizedSearchCV, so any pipeline exercises the same wiring.
            pipeline = make_pipeline()
        model.find_hyp_catboost_model(X, y, X, y, pipeline)
        assert len(RecordingSearch.calls) == 1
        assert RecordingSearch.calls[0]["n_jobs"] == 2

    def test_xgb_search_uses_search_n_jobs(self, monkeypatch):
        """XGB RandomizedSearchCV receives n_jobs from search_n_jobs."""
        monkeypatch.setattr(supervised_models, "RandomizedSearchCV", RecordingSearch)
        X, y = _search_data()
        model = XGBModel(
            cols_for_model=list(X.columns),
            hyperparams={},
            search_hip=True,
            search_n_jobs=2,
        )
        try:
            pipeline = model.build_pipeline_preproceso_model()
        except ImportError:
            # xgboost is an optional dependency and may not be installed; the
            # XGBoost search path only forwards the estimator to
            # RandomizedSearchCV, so any pipeline exercises the same wiring.
            pipeline = make_pipeline()
        model.find_hyp_xgb_model(X, y, X, y, pipeline)
        assert len(RecordingSearch.calls) == 1
        assert RecordingSearch.calls[0]["n_jobs"] == 2
