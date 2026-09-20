"""Tests for LGBMModel n_jobs handling.

Verifies that:
- The framework default is n_jobs=-1 (all cores).
- User-specified n_jobs in hyperparams overrides the framework default.
- User-specified keys outside the hyperparameter search space (e.g. n_jobs)
  are preserved when search_hip is enabled.
- hyperparams=None is accepted and normalized to an empty dict.
"""

from energizados.modeling.supervised_models import LGBMModel


class TestLGBMModelNJobs:
    """Tests for n_jobs configuration in LGBMModel."""

    def test_default_n_jobs_is_all_cores(self):
        """Built pipeline uses n_jobs=-1 (all cores) when no n_jobs is given."""
        pipe = LGBMModel(cols_for_model=["feature_0", "feature_1"], hyperparams={})
        pipe = pipe.build_pipeline_preproceso_model()
        assert pipe.named_steps["lgbmclassifier"].n_jobs == -1

    def test_user_n_jobs_overrides_default(self, synthetic_classification_data_small):
        """User-specified n_jobs in hyperparams overrides the framework default."""
        X, y = synthetic_classification_data_small
        model = LGBMModel(
            cols_for_model=list(X.columns),
            hyperparams={"n_jobs": 2, "n_estimators": 10, "verbosity": -1},
            sampling_method="none",
        )
        pipe = model.train(X, y)
        assert pipe.named_steps["lgbmclassifier"].n_jobs == 2

    def test_search_preserves_user_hyperparams(
        self, synthetic_classification_data_small, monkeypatch
    ):
        """Keys outside the search space (e.g. n_jobs) survive hyperparameter search."""
        X, y = synthetic_classification_data_small
        model = LGBMModel(
            cols_for_model=list(X.columns),
            hyperparams={"n_jobs": 2},
            search_hip=True,
            sampling_method="none",
        )
        monkeypatch.setattr(
            model,
            "find_hyp_lgbm_model",
            lambda *a, **k: (
                0.9,
                {
                    "lgbmclassifier__num_leaves": 7,
                    "lgbmclassifier__n_estimators": 10,
                    "lgbmclassifier__verbosity": -1,
                },
            ),
        )
        pipe = model.train(X, y)
        assert pipe.named_steps["lgbmclassifier"].n_jobs == 2
        assert pipe.named_steps["lgbmclassifier"].num_leaves == 7

    def test_hyperparams_none_accepted(self):
        """hyperparams=None is normalized to an empty dict."""
        model = LGBMModel(cols_for_model=["a"], hyperparams=None)
        assert model.hyperparams == {}
