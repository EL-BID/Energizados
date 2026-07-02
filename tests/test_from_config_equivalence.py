"""
Behavior-preservation tests for adapter from_config classmethods.

These tests verify that from_config correctly processes configuration
into constructor kwargs. The equivalence to the old _prepare_model_params
ladder was proven during development; the ladder has now been deleted.
Tests follow RED → GREEN → REFACTOR TDD cycle.
"""

import pandas as pd
import pytest


@pytest.fixture
def sample_x_train():
    """Create sample X_train DataFrame for testing."""
    return pd.DataFrame(
        {
            "feature_1": [1.0, 2.0, 3.0],
            "feature_2": [4.0, 5.0, 6.0],
            "consumption_1_anterior": [10.0, 20.0, 30.0],
            "consumption_2_anterior": [15.0, 25.0, 35.0],
            "actividad": ["A", "B", "A"],
        }
    )


class TestFromConfigBehavior:
    """
    Tests for adapter from_config methods.

    Each test verifies correct parameter extraction from config.
    Tests follow RED → GREEN → REFACTOR TDD cycle.
    """

    def test_from_config_lgbm_behavior(self, sample_x_train):
        """Test LGBMModelAdapter.from_config extracts correct parameters."""
        from energizados.modeling.adapters import LGBMModelAdapter

        config = {
            "type": "lightgbm",
            "name": "test_lgbm",
            "sampling": {"method": "undersample", "threshold": 0.3},
            "hyperparams": {"num_leaves": 31, "learning_rate": 0.05},
            "hyperparam_search": {"enabled": True, "n_iter": 50, "cv": 3, "n_splits": 5},
            "class_weight": "balanced",
        }

        params = LGBMModelAdapter.from_config(config.copy(), sample_x_train)

        # Verify key parameter extractions
        assert params["cols_for_model"] == sample_x_train.columns.tolist()
        assert params["sampling_method"] == "undersample"
        assert params["sampling_th"] == 0.3
        assert params["hyperparams"] == {"num_leaves": 31, "learning_rate": 0.05}
        assert params["search_hip"] is True
        assert params["n_iter"] == 50
        assert params["cv"] == 3
        assert params["n_splits"] == 5
        assert params["class_weight"] == "balanced"
        assert params["config"] == {"type": "lightgbm"}
        assert "type" not in params
        assert "name" not in params
        assert "sampling" not in params  # Should be flattened

    def test_from_config_cat_behavior(self, sample_x_train):
        """Test CATModelAdapter.from_config extracts correct parameters."""
        from energizados.modeling.adapters import CATModelAdapter

        config = {
            "type": "catboost",
            "name": "test_cat",
            "sampling": {"method": "oversample", "threshold": 0.7},
            "hyperparams": {"iterations": 300, "depth": 6},
            "hyperparam_search": {"enabled": True, "n_iter": 40, "cv": 5, "n_splits": 3},
        }

        params = CATModelAdapter.from_config(config.copy(), sample_x_train)

        assert params["cols_for_model"] == sample_x_train.columns.tolist()
        assert params["sampling_method"] == "oversample"
        assert params["sampling_th"] == 0.7
        assert params["search_hip"] is True
        assert params["n_iter"] == 40
        assert params["cv"] == 5

    def test_from_config_xgb_behavior(self, sample_x_train):
        """Test XGBModelAdapter.from_config extracts correct parameters."""
        from energizados.modeling.adapters import XGBModelAdapter

        config = {
            "type": "xgboost",
            "name": "test_xgb",
            "sampling": {"method": "undersample", "threshold": 0.5},
            "hyperparams": {"max_depth": 6, "eta": 0.1},
            "hyperparam_search": {"enabled": False},
        }

        params = XGBModelAdapter.from_config(config.copy(), sample_x_train)

        assert params["cols_for_model"] == sample_x_train.columns.tolist()
        assert params["sampling_method"] == "undersample"
        assert params["search_hip"] is False
        assert params["config"] == {"type": "xgboost"}

    def test_from_config_nn_behavior(self, sample_x_train):
        """Test NNModelAdapter.from_config derives features_names/spents_names correctly."""
        from energizados.modeling.adapters import NNModelAdapter

        config = {
            "type": "neural_network",
            "name": "test_nn",
            "sampling": {"method": "undersample", "threshold": 0.5},
            "hyperparam_search": {"enabled": False},
        }

        params = NNModelAdapter.from_config(config.copy(), sample_x_train)

        # Verify column separation
        expected_consumption = ["consumption_1_anterior", "consumption_2_anterior"]
        expected_features = ["feature_1", "feature_2", "actividad"]
        assert params["spents_names"] == expected_consumption
        assert params["features_names"] == expected_features
        assert params["sampling_method"] == "undersample"
        assert params["search_hip"] is False
        assert params["config"] == {"type": "neural_network"}

    def test_from_config_lstm_behavior(self, sample_x_train):
        """Test LSTMNNModelAdapter.from_config derives features_names/spents_names correctly."""
        from energizados.modeling.adapters import LSTMNNModelAdapter

        config = {
            "type": "lstm",
            "name": "test_lstm",
            "sampling": {"method": "undersample", "threshold": 0.5},
            "hyperparam_search": {"enabled": False},
        }

        params = LSTMNNModelAdapter.from_config(config.copy(), sample_x_train)

        # Verify column separation
        expected_consumption = ["consumption_1_anterior", "consumption_2_anterior"]
        expected_features = ["feature_1", "feature_2", "actividad"]
        assert params["spents_names"] == expected_consumption
        assert params["features_names"] == expected_features
        assert params["config"] == {"type": "lstm"}

    def test_from_config_simple_trend_behavior(self, sample_x_train):
        """Test SimpleTrendAdapter.from_config extracts parameters and removes invalid keys."""
        from energizados.modeling.adapters import SimpleTrendAdapter

        config = {
            "type": "simple_trend",
            "name": "test_trend",
            "last_base_value": 6,
            "last_eval_value": 3,
            "threshold": 50,
            "sampling": {"method": "none"},
            "class_weight": "balanced",
            "hyperparams": {"dummy": 1},
        }

        params = SimpleTrendAdapter.from_config(config.copy(), sample_x_train)

        # Verify valid parameters are extracted
        assert params["last_base_value"] == 6
        assert params["last_eval_value"] == 3
        assert params["threshold"] == 50
        assert params["config"] == {"type": "simple_trend"}

        # Verify invalid keys are removed
        assert "sampling" not in params
        assert "class_weight" not in params
        assert "hyperparams" not in params
        assert "hyperparam_search" not in params

    def test_from_config_simple_constant_behavior(self, sample_x_train):
        """Test SimpleConstantAdapter.from_config extracts parameters and removes invalid keys."""
        from energizados.modeling.adapters import SimpleConstantAdapter

        config = {
            "type": "simple_constant",
            "name": "test_constant",
            "min_count_constante": 3,
            "sampling": {"method": "none"},
            "hyperparam_search": {"enabled": True},
        }

        params = SimpleConstantAdapter.from_config(config.copy(), sample_x_train)

        # Verify valid parameter is extracted
        assert params["min_count_constante"] == 3
        assert params["config"] == {"type": "simple_constant"}

        # Verify invalid keys are removed
        assert "sampling" not in params
        assert "hyperparam_search" not in params


class TestMetaLearnerWrapper:
    """
    Tests for _SklearnCalibWrapper used in ensemble meta-learner fix.

    The wrapper provides 2D predict_proba output for adapters that only expose 1D.
    """

    def test_sklearn_calib_wrapper_predict_proba_2d(self):
        """Test _SklearnCalibWrapper exposes 2D predict_proba output."""
        import numpy as np

        from energizados.core.steps.training import _SklearnCalibWrapper
        from energizados.modeling.adapters import LGBMModelAdapter

        # Create a mock adapter with 1D predict_proba
        adapter = LGBMModelAdapter(cols_for_model=["feature_1", "feature_2"])

        # Mock the adapter's predict_proba to return 1D
        adapter.predict_proba = lambda X: np.array([0.3, 0.7, 0.5, 0.9])

        # Wrap the adapter
        wrapper = _SklearnCalibWrapper(adapter)

        # Create test data
        X_test = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])

        # Verify 2D output
        probas = wrapper.predict_proba(X_test)
        assert probas.shape == (4, 2), f"Expected shape (4, 2), got {probas.shape}"

        # Verify the second column matches the adapter's 1D output
        expected_positive = np.array([0.3, 0.7, 0.5, 0.9])
        assert np.array_equal(probas[:, 1], expected_positive)

        # Verify sklearn classifier interface attributes
        assert hasattr(wrapper, "classes_")
        assert np.array_equal(wrapper.classes_, np.array([0, 1]))
        assert wrapper._estimator_type == "classifier"

    def test_sklearn_calib_wrapper_integration_stacking(self):
        """Test that stacking ensemble can use wrapped meta-learner without [:,1] error."""
        import numpy as np

        from energizados.core.steps.training import _SklearnCalibWrapper
        from energizados.modeling.adapters import CATModelAdapter

        # Create a mock CatBoost adapter as meta-learner
        meta_adapter = CATModelAdapter(cols_for_model=["prob_0", "prob_1"])

        # Mock the adapter's predict_proba to return 1D
        meta_adapter.predict_proba = lambda X: np.array([0.4, 0.6, 0.3, 0.7])

        # Wrap the adapter
        wrapped_meta = _SklearnCalibWrapper(meta_adapter)

        # Simulate base model predictions (2D array from stacking)
        base_predictions = np.array(
            [
                [0.2, 0.8],
                [0.5, 0.5],
                [0.7, 0.3],
                [0.4, 0.6],
            ]
        )

        # This is what ensemble.predict_proba does: meta_learner.predict_proba(base_preds)[:, 1]
        # Before the fix, this would fail because meta_adapter.predict_proba returns 1D
        # After the fix, wrapped_meta.predict_proba returns 2D
        meta_probas = wrapped_meta.predict_proba(base_predictions)
        final_predictions = meta_probas[:, 1]  # This should work now!

        assert final_predictions.shape == (4,)
        assert np.array_equal(final_predictions, np.array([0.4, 0.6, 0.3, 0.7]))
