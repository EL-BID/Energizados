"""
Tests for the public exception hierarchy.

Covers REQ1 (exception hierarchy completeness). Later work units append
classes for REQ2 (Pipeline.run preservation) and REQ3 (fitted-state guards).
"""

import pytest

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
