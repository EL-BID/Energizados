"""
Tests for the public exception hierarchy.

Covers REQ1 (exception hierarchy completeness). Later work units append
classes for REQ2 (Pipeline.run preservation) and REQ3 (fitted-state guards).
"""

import pandas as pd
import pytest

from energizados.core.base import PipelineStep
from energizados.core.exceptions import (
    ConfigurationError,
    EnergizadosError,
    ETLDependencyError,
    EvaluatorError,
    FeatureSelectionError,
    InferenceError,
    ModelNotFittedError,
    PipelineError,
    TransformerError,
)
from energizados.core.pipeline import Pipeline
from energizados.feature_engineering.base import BaseFeatureEngineering
from energizados.feature_selection.base import BaseFeatureSelector


class TestExceptionHierarchy:
    """REQ1: every public type subclasses EnergizadosError and its stdlib base."""

    @pytest.mark.parametrize(
        "exc_type",
        [
            TransformerError,
            FeatureSelectionError,
            InferenceError,
            EvaluatorError,
            ModelNotFittedError,
        ],
    )
    def test_subclasses_energizados_error(self, exc_type):
        assert issubclass(exc_type, EnergizadosError)

    @pytest.mark.parametrize(
        "exc_type",
        [TransformerError, FeatureSelectionError, ModelNotFittedError],
    )
    def test_value_error_backed_types(self, exc_type):
        assert issubclass(exc_type, ValueError)

    def test_inference_error_is_runtime_error(self):
        assert issubclass(InferenceError, RuntimeError)

    def test_evaluator_error_has_no_stdlib_base(self):
        # EvaluatorError is framework-only: no ValueError/RuntimeError base
        # (no conversion site today — adding a stdlib base would be a
        # gratuitous API commitment).
        assert not issubclass(EvaluatorError, ValueError)
        assert not issubclass(EvaluatorError, RuntimeError)


class TestBackwardCompat:
    """REQ1: stdlib catches still work; ModelNotFittedError stays directly usable."""

    @pytest.mark.parametrize(
        "exc_type",
        [
            TransformerError,
            FeatureSelectionError,
            InferenceError,
            EvaluatorError,
            ModelNotFittedError,
        ],
    )
    def test_catch_as_energizados_error(self, exc_type):
        with pytest.raises(EnergizadosError):
            raise exc_type("boom")

    @pytest.mark.parametrize(
        "exc_type",
        [TransformerError, FeatureSelectionError, ModelNotFittedError],
    )
    def test_catch_as_value_error(self, exc_type):
        with pytest.raises(ValueError):
            raise exc_type("boom")

    def test_inference_error_catch_as_runtime_error(self):
        with pytest.raises(RuntimeError):
            raise InferenceError("boom")

    def test_model_not_fitted_error_still_raised_directly(self):
        # Backward compat: existing callers do `except ModelNotFittedError`.
        with pytest.raises(ModelNotFittedError):
            raise ModelNotFittedError(model_name="MyModel")


class TestMROComputability:
    """REQ1: importing the module and building each multi-base type raises no TypeError."""

    @pytest.mark.parametrize(
        "exc_type,args",
        [
            (TransformerError, ("boom",)),
            (FeatureSelectionError, ("boom",)),
            (InferenceError, ("boom",)),
            (EvaluatorError, ("boom",)),
            (ModelNotFittedError, ()),
            (ModelNotFittedError, ("MyModel",)),
        ],
    )
    def test_instantiable_without_type_error(self, exc_type, args):
        # If the C3 linearization were uncomputable, class definition would
        # have raised TypeError at import time. Instantiating confirms
        # __init__ resolves through the merged MRO.
        instance = exc_type(*args)
        assert isinstance(instance, EnergizadosError)

    def test_model_not_fitted_mro_contains_both_bases(self):
        mro = ModelNotFittedError.__mro__
        assert EnergizadosError in mro
        assert ValueError in mro


class TestExistingTypesUnchanged:
    """REQ1: pre-existing types keep a single EnergizadosError base (no stdlib base)."""

    @pytest.mark.parametrize(
        "exc_type",
        [PipelineError, ConfigurationError, ETLDependencyError],
    )
    def test_subclasses_energizados_error(self, exc_type):
        assert issubclass(exc_type, EnergizadosError)

    @pytest.mark.parametrize(
        "exc_type",
        [PipelineError, ConfigurationError, ETLDependencyError],
    )
    def test_not_value_or_runtime_error(self, exc_type):
        assert not issubclass(exc_type, ValueError)
        assert not issubclass(exc_type, RuntimeError)


class _RaisingStep(PipelineStep):
    """Minimal pipeline step that raises a fixed exception on execute.

    No YAML, no real dependencies — exercises Pipeline.run's error boundary.
    """

    def __init__(self, exc):
        self._exc = exc

    def validate_input(self, context):
        return True

    def execute(self, context):
        raise self._exc


class TestPipelinePreservation:
    """REQ2: framework exceptions reach the caller unchanged (no re-wrap)."""

    def test_etl_dependency_error_not_wrapped(self):
        original = ETLDependencyError("missing dependency")
        pipeline = Pipeline().add_step(_RaisingStep(original))
        with pytest.raises(ETLDependencyError) as exc_info:
            pipeline.run()
        assert exc_info.value is original
        assert not isinstance(exc_info.value, PipelineError)

    def test_configuration_error_not_wrapped(self):
        original = ConfigurationError("bad yaml", config_path="x.yaml")
        pipeline = Pipeline().add_step(_RaisingStep(original))
        with pytest.raises(ConfigurationError) as exc_info:
            pipeline.run()
        assert exc_info.value is original
        # Attributes are preserved (no re-wrap erasing them)
        assert exc_info.value.config_path == "x.yaml"
        assert not isinstance(exc_info.value, PipelineError)


class TestPipelineWrapping:
    """REQ2: unexpected exceptions are wrapped into PipelineError, cause chained."""

    def test_key_error_wrapped_with_cause(self):
        original = KeyError("nope")
        pipeline = Pipeline().add_step(_RaisingStep(original))
        with pytest.raises(PipelineError) as exc_info:
            pipeline.run()
        assert exc_info.value.__cause__ is original
        assert exc_info.value.step == _RaisingStep.__name__


class TestPipelineCallback:
    """REQ2: on_step_error fires once for both framework and unexpected paths."""

    def test_callback_fires_for_framework_exception(self):
        original = ETLDependencyError("missing dependency")
        calls = []
        pipeline = Pipeline().add_step(_RaisingStep(original))
        pipeline.on_step_error = lambda name, err: calls.append((name, err))
        with pytest.raises(ETLDependencyError):
            pipeline.run()
        assert len(calls) == 1
        assert calls[0][0] == _RaisingStep.__name__
        assert calls[0][1] is original

    def test_callback_fires_for_unexpected_exception(self):
        original = KeyError("nope")
        calls = []
        pipeline = Pipeline().add_step(_RaisingStep(original))
        pipeline.on_step_error = lambda name, err: calls.append((name, err))
        with pytest.raises(PipelineError):
            pipeline.run()
        assert len(calls) == 1
        assert calls[0][0] == _RaisingStep.__name__
        assert calls[0][1] is original


class _UnfittedFE(BaseFeatureEngineering):
    """Concrete FE that delegates transform to check_fitted (guard site)."""

    def fit(self, X, y):
        self.is_fitted_ = True
        return self

    def transform(self, X):
        self.check_fitted()
        return X


class _UnfittedSelector(BaseFeatureSelector):
    """Concrete selector for exercising the base fitted-state guards."""

    def fit(self, X, y):
        self.selected_features_ = list(X.columns)
        return self

    def transform(self, X):
        return X


class TestFittedGuards:
    """REQ3: fitted-state guards raise ModelNotFittedError (ValueError-compatible)."""

    # --- BaseFeatureEngineering: check_fitted (via transform), get_feature_names_out, save ---

    def test_fe_transform_unfitted_raises_model_not_fitted(self):
        fe = _UnfittedFE()
        with pytest.raises(ModelNotFittedError):
            fe.transform(pd.DataFrame({"x": [1]}))

    def test_fe_transform_unfitted_catchable_as_value_error(self):
        fe = _UnfittedFE()
        with pytest.raises(ValueError):
            fe.transform(pd.DataFrame({"x": [1]}))

    def test_fe_get_feature_names_out_unfitted_raises_model_not_fitted(self):
        fe = _UnfittedFE()
        with pytest.raises(ModelNotFittedError):
            fe.get_feature_names_out()

    def test_fe_save_unfitted_raises_model_not_fitted(self, tmp_path):
        fe = _UnfittedFE()
        with pytest.raises(ModelNotFittedError):
            fe.save(str(tmp_path / "fe.pkl"))

    # --- BaseFeatureSelector: get_selected_features, get_audit_stats ---

    def test_selector_get_selected_features_unfitted_raises_model_not_fitted(self):
        selector = _UnfittedSelector()
        with pytest.raises(ModelNotFittedError):
            selector.get_selected_features()

    def test_selector_get_audit_stats_unfitted_raises_model_not_fitted(self):
        selector = _UnfittedSelector()
        with pytest.raises(ModelNotFittedError):
            selector.get_audit_stats()

    def test_selector_guards_catchable_as_value_error(self):
        selector = _UnfittedSelector()
        with pytest.raises(ValueError):
            selector.get_selected_features()
        with pytest.raises(ValueError):
            selector.get_audit_stats()
