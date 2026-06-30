"""
Unit tests for HierarchicalInference.

Tests cover: initialization, condition evaluation, routing logic,
model loading, and integration with InferenceBuilder.
"""

import pickle  # nosec B403
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from energizados.core.builders.inference_builder import InferenceBuilder
from energizados.core.exceptions import InferenceError
from energizados.inference.hierarchical import HierarchicalInference


class _TrackingFE:
    """FE that tracks calls."""

    def __init__(self):
        self.transform_called = False

    def transform(self, df):
        self.transform_called = True
        return df.assign(fe_col=1)


class _MockModel:
    """Simple picklable mock model that returns fixed probabilities."""

    def __init__(self, proba_value=0.5):
        self._proba_value = proba_value

    def predict_proba(self, X):
        n = len(X)
        return np.full(n, self._proba_value, dtype=np.float64)


class _SimpleFE:
    """Simple picklable feature engineering transformer."""

    def transform(self, df):
        return df.assign(fe_col=1)


class TestHierarchicalInferenceInit:
    """Tests for HierarchicalInference initialization."""

    def test_init_default(self):
        """Test default initialization."""
        inference = HierarchicalInference()

        assert inference.threshold == 0.5
        assert inference.routes == []
        assert inference.default_model_path is None
        assert inference.feature_engineering_paths == {}
        assert not inference._is_loaded

    def test_init_with_routes(self):
        """Test initialization with route definitions."""
        routes = [
            {
                "name": "fln",
                "condition": {"geo_region": "FLORIANOPOLIS"},
                "model_path": "models/fln.pkl",
            }
        ]
        inference = HierarchicalInference(
            threshold=0.3,
            routes=routes,
            default_model_path="models/global.pkl",
            feature_engineering_paths={"fln": "models/fln_fe.pkl"},
        )

        assert inference.threshold == 0.3
        assert len(inference.routes) == 1
        assert inference.default_model_path == "models/global.pkl"
        assert inference.feature_engineering_paths == {"fln": "models/fln_fe.pkl"}


class TestHierarchicalInferenceConditionEvaluation:
    """Tests for _evaluate_condition static method."""

    def test_single_value_equality(self):
        """Condition with single value matches exact rows."""
        data = pd.DataFrame(
            {
                "geo_region": ["FLN", "BLU", "FLN", "LAG"],
                "consumo": [100, 200, 300, 400],
            }
        )
        mask = HierarchicalInference._evaluate_condition(data, {"geo_region": "FLN"})
        expected = pd.Series([True, False, True, False])
        pd.testing.assert_series_equal(mask.reset_index(drop=True), expected)

    def test_list_values(self):
        """Condition with list matches any value in the list."""
        data = pd.DataFrame(
            {
                "geo_region": ["FLN", "BLU", "LAG", "ITJ"],
            }
        )
        mask = HierarchicalInference._evaluate_condition(data, {"geo_region": ["FLN", "BLU"]})
        expected = pd.Series([True, True, False, False])
        pd.testing.assert_series_equal(mask.reset_index(drop=True), expected)

    def test_multiple_columns_and(self):
        """Multiple conditions are combined with AND."""
        data = pd.DataFrame(
            {
                "zona": ["A", "A", "B", "B"],
                "tension": ["ALTA", "BAJA", "ALTA", "BAJA"],
            }
        )
        mask = HierarchicalInference._evaluate_condition(data, {"zona": "A", "tension": "ALTA"})
        expected = pd.Series([True, False, False, False])
        pd.testing.assert_series_equal(mask.reset_index(drop=True), expected)

    def test_missing_column_returns_all_false(self):
        """Condition on missing column returns all False and logs warning."""
        data = pd.DataFrame({"zona": ["A", "B"]})
        mask = HierarchicalInference._evaluate_condition(data, {"missing_col": "X"})
        assert mask.sum() == 0

    def test_callable_condition(self):
        """Condition can be a callable applied to each row."""
        data = pd.DataFrame({"consumo": [100, 200, 300, 400]})
        mask = HierarchicalInference._evaluate_condition(data, {"consumo": lambda x: x > 250})
        expected = pd.Series([False, False, True, True])
        pd.testing.assert_series_equal(mask.reset_index(drop=True), expected)


class TestHierarchicalInferenceRouting:
    """Tests for predict_proba routing logic."""

    def test_single_route(self, temp_dir):
        """Rows matching route use route model; others use default."""
        fln_model = _MockModel(proba_value=0.9)
        default_model = _MockModel(proba_value=0.1)

        fln_path = temp_dir / "fln.pkl"
        default_path = temp_dir / "default.pkl"
        with open(fln_path, "wb") as f:
            pickle.dump(fln_model, f)
        with open(default_path, "wb") as f:
            pickle.dump(default_model, f)

        inference = HierarchicalInference(
            routes=[
                {
                    "name": "fln",
                    "condition": {"geo_region": "FLN"},
                    "model_path": str(fln_path),
                }
            ],
            default_model_path=str(default_path),
        )

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            # secure_load is called for each model path in order
            mock_load.side_effect = [fln_model, default_model]
            inference.load_model()

        data = pd.DataFrame(
            {
                "geo_region": ["FLN", "BLU", "FLN", "LAG"],
            }
        )
        probas = inference.predict_proba(None, data)

        # FLN rows (0, 2) -> 0.9; others (1, 3) -> 0.1
        expected = np.array([0.9, 0.1, 0.9, 0.1])
        np.testing.assert_array_almost_equal(probas, expected)

    def test_multiple_routes_first_match_wins(self, temp_dir):
        """First matching route wins; subsequent routes don't override."""
        route1_model = _MockModel(proba_value=0.9)
        route2_model = _MockModel(proba_value=0.8)
        default_model = _MockModel(proba_value=0.1)

        p1 = temp_dir / "r1.pkl"
        p2 = temp_dir / "r2.pkl"
        p_default = temp_dir / "default.pkl"
        for path, model in [(p1, route1_model), (p2, route2_model), (p_default, default_model)]:
            with open(path, "wb") as f:
                pickle.dump(model, f)

        inference = HierarchicalInference(
            routes=[
                {
                    "name": "fln",
                    "condition": {"geo_region": "FLN"},
                    "model_path": str(p1),
                },
                {
                    "name": "blu",
                    "condition": {"geo_region": "BLU"},
                    "model_path": str(p2),
                },
            ],
            default_model_path=str(p_default),
        )

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.side_effect = [route1_model, route2_model, default_model]
            inference.load_model()

        data = pd.DataFrame(
            {
                "geo_region": ["FLN", "BLU", "FLN", "LAG"],
            }
        )
        probas = inference.predict_proba(None, data)

        expected = np.array([0.9, 0.8, 0.9, 0.1])
        np.testing.assert_array_almost_equal(probas, expected)

    def test_no_default_unmatched_rows_get_zero(self, temp_dir):
        """Without default model, unmatched rows get probability 0.0."""
        fln_model = _MockModel(proba_value=0.9)

        fln_path = temp_dir / "fln.pkl"
        with open(fln_path, "wb") as f:
            pickle.dump(fln_model, f)

        inference = HierarchicalInference(
            routes=[
                {
                    "name": "fln",
                    "condition": {"geo_region": "FLN"},
                    "model_path": str(fln_path),
                }
            ],
            # No default_model_path
        )

        with patch("energizados.core.utils.secure_pickle.secure_load", return_value=fln_model):
            inference.load_model()

        data = pd.DataFrame({"geo_region": ["FLN", "BLU"]})
        probas = inference.predict_proba(None, data)

        expected = np.array([0.9, 0.0])
        np.testing.assert_array_almost_equal(probas, expected)

    def test_predict_without_load_raises(self):
        """predict_proba before load_model raises RuntimeError."""
        inference = HierarchicalInference(routes=[])
        with pytest.raises(RuntimeError, match="Models not loaded"):
            inference.predict_proba(None, pd.DataFrame({"x": [1]}))

    def test_predict_without_load_raises_inference_error(self):
        """predict_proba before load_model raises InferenceError (REQ4).

        InferenceError subclasses RuntimeError, so the backward-compat
        ``except RuntimeError`` path above still catches it.
        """
        inference = HierarchicalInference(routes=[])
        with pytest.raises(InferenceError, match="Models not loaded"):
            inference.predict_proba(None, pd.DataFrame({"x": [1]}))


class TestHierarchicalInferenceFeatureEngineering:
    """Tests for per-route feature engineering."""

    def test_route_with_fe_transform(self, temp_dir):
        """Route with FE applies transform before prediction."""
        mock_model = _MockModel(proba_value=0.7)

        mock_fe = _SimpleFE()
        default_model = _MockModel(proba_value=0.2)

        model_path = temp_dir / "model.pkl"
        fe_path = temp_dir / "fe.pkl"
        default_path = temp_dir / "default.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(mock_model, f)
        with open(fe_path, "wb") as f:
            pickle.dump(mock_fe, f)
        with open(default_path, "wb") as f:
            pickle.dump(default_model, f)

        inference = HierarchicalInference(
            routes=[
                {
                    "name": "special",
                    "condition": {"zona": "SPECIAL"},
                    "model_path": str(model_path),
                }
            ],
            default_model_path=str(default_path),
            feature_engineering_paths={"special": str(fe_path)},
        )

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.side_effect = [mock_model, mock_fe, default_model]
            inference.load_model()

        data = pd.DataFrame({"zona": ["SPECIAL", "NORMAL"]})
        probas = inference.predict_proba(None, data)

        # SPECIAL -> route model (0.7), NORMAL -> default (0.2)
        expected = np.array([0.7, 0.2])
        np.testing.assert_array_almost_equal(probas, expected)

    def test_default_fe_applied_to_unrouted_rows(self, temp_dir):
        """Default FE is applied to unrouted rows when __default__ key is configured."""
        route_model = _MockModel(proba_value=0.8)
        default_model = _MockModel(proba_value=0.2)

        default_fe = _TrackingFE()
        route_fe = _SimpleFE()

        model_path = temp_dir / "route_model.pkl"
        route_fe_path = temp_dir / "route_fe.pkl"
        default_model_path = temp_dir / "default_model.pkl"
        default_fe_path = temp_dir / "default_fe.pkl"

        with open(model_path, "wb") as f:
            pickle.dump(route_model, f)
        with open(route_fe_path, "wb") as f:
            pickle.dump(route_fe, f)
        with open(default_model_path, "wb") as f:
            pickle.dump(default_model, f)
        with open(default_fe_path, "wb") as f:
            pickle.dump(default_fe, f)

        inference = HierarchicalInference(
            routes=[
                {
                    "name": "fln",
                    "condition": {"geo_region": "FLN"},
                    "model_path": str(model_path),
                }
            ],
            default_model_path=str(default_model_path),
            feature_engineering_paths={
                "fln": str(route_fe_path),
                "__default__": str(default_fe_path),
            },
        )

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.side_effect = [route_model, route_fe, default_model, default_fe]
            inference.load_model()

        data = pd.DataFrame({"geo_region": ["FLN", "BLU", "LAG"]})
        probas = inference.predict_proba(None, data)

        # FLN -> route model (0.8), BLU and LAG -> default (0.2)
        expected = np.array([0.8, 0.2, 0.2])
        np.testing.assert_array_almost_equal(probas, expected)

        # Verify that default FE was actually called for unrouted rows
        assert default_fe.transform_called, "Default FE should be called for unrouted rows"

    def test_default_name_reserved_rejects_collision(self):
        """Route name '__default__' is reserved and raises ValueError."""
        with pytest.raises(ValueError, match="Route name '__default__' is reserved"):
            HierarchicalInference(
                routes=[
                    {
                        "name": "__default__",
                        "condition": {"geo_region": "FLN"},
                        "model_path": "models/default.pkl",
                    }
                ]
            )


class TestHierarchicalInferenceBuilderIntegration:
    """Tests for HierarchicalInference integration with InferenceBuilder."""

    def test_builder_passes_routes_to_inference(self, temp_dir):
        """InferenceBuilder passes routes/default_model_path kwargs to constructor."""
        config = {
            "custom_class": "energizados.inference.hierarchical.HierarchicalInference",
            "threshold": 0.3,
            "routes": [
                {
                    "name": "fln",
                    "condition": {"geo_region": "FLN"},
                    "model_path": str(temp_dir / "fln.pkl"),
                }
            ],
            "default_model_path": str(temp_dir / "default.pkl"),
            "input_path": str(temp_dir / "input.parquet"),
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        assert step is not None
        assert hasattr(step.inference, "routes")
        assert len(step.inference.routes) == 1
        assert step.inference.threshold == 0.3
        assert step.inference.default_model_path == str(temp_dir / "default.pkl")

    def test_validate_input_true_for_hierarchical(self, temp_dir):
        """validate_input returns True when inference has routes (no model_path needed)."""
        config = {
            "custom_class": "energizados.inference.hierarchical.HierarchicalInference",
            "routes": [
                {
                    "name": "fln",
                    "condition": {"geo_region": "FLN"},
                    "model_path": str(temp_dir / "fln.pkl"),
                }
            ],
            "input_path": str(temp_dir / "input.parquet"),
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        # Should pass even with empty context (hierarchical loads its own models)
        assert step.validate_input({}) is True

    def test_hierarchical_execute_loads_models(self, temp_dir):
        """execute() calls load_model() for hierarchical inference and produces predictions."""
        fln_model = _MockModel(proba_value=0.9)
        default_model = _MockModel(proba_value=0.1)

        fln_path = temp_dir / "fln.pkl"
        default_path = temp_dir / "default.pkl"
        with open(fln_path, "wb") as f:
            pickle.dump(fln_model, f)
        with open(default_path, "wb") as f:
            pickle.dump(default_model, f)

        input_path = temp_dir / "input.parquet"
        pd.DataFrame({"geo_region": ["FLN", "BLU", "FLN"]}).to_parquet(input_path, index=False)

        config = {
            "custom_class": "energizados.inference.hierarchical.HierarchicalInference",
            "routes": [
                {
                    "name": "fln",
                    "condition": {"geo_region": "FLN"},
                    "model_path": str(fln_path),
                }
            ],
            "default_model_path": str(default_path),
            "input_path": str(input_path),
        }
        builder = InferenceBuilder(config)
        step = builder.build()

        with patch("energizados.core.utils.secure_pickle.secure_load") as mock_load:
            mock_load.side_effect = [fln_model, default_model]
            result = step.execute({})

        assert "predictions" in result
        assert "prediction_probas" in result
        assert len(result["predictions"]) == 3
        # FLN rows -> prob 0.9 >= 0.5 -> 1; BLU row -> prob 0.1 < 0.5 -> 0
        expected = np.array([1, 0, 1])
        np.testing.assert_array_equal(result["predictions"], expected)
