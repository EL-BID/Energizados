"""
Unit tests for the unified Registry class.

Tests follow STRICT TDD mode: RED tests written before implementation.
Coverage includes:
- Case-insensitive lookup
- KeyError with available names on missing get()
- Per-domain isolation
- ModelRegistry backward compatibility (alias)
"""

import pytest

from energizados.core.registry import (
    Registry,
    model_registry,
    selector_registry,
)

# Import ModelRegistry FIRST to trigger default model registration
from energizados.modeling.registry import ModelRegistry

# ---------------------------------------------------------------------------
# RED TESTS: Registry class behavior (written BEFORE implementation)
# ---------------------------------------------------------------------------


def test_registry_case_insensitive_lookup():
    """Test that 'CatBoost', 'catboost', 'CATBOOST' resolve to same factory."""
    registry = Registry("test")

    # Register a factory under one casing
    class DummyModel:
        pass

    registry.register("CatBoost", DummyModel)

    # Should resolve under different casings
    assert registry.get("catboost") is DummyModel
    assert registry.get("CATBOOST") is DummyModel
    assert registry.get("CatBoost") is DummyModel


def test_registry_independent_instances():
    """Test that model_registry and selector_registry are isolated."""
    # Get the original built-in model count to preserve them
    original_models = set(model_registry.list_registered())

    class DummyModel:
        pass

    class DummySelector:
        pass

    # Register same name in different registries
    model_registry.register("dummy", DummyModel)
    selector_registry.register("dummy", DummySelector)

    # Should resolve to different factories
    assert model_registry.get("dummy") is DummyModel
    assert selector_registry.get("dummy") is DummySelector

    # Cleanup: only remove the test models, preserve built-in ones
    model_registry._registry = {
        k: v for k, v in model_registry._registry.items() if k in original_models
    }
    selector_registry._registry.clear()


def test_registry_get_missing_with_available_names():
    """Test that get() raises KeyError listing available names."""
    registry = Registry("test")

    class DummyModel:
        pass

    registry.register("lightgbm", DummyModel)
    registry.register("catboost", DummyModel)

    with pytest.raises(KeyError) as exc_info:
        registry.get("nonexistent")

    error_msg = str(exc_info.value)
    assert "nonexistent" in error_msg
    assert "lightgbm" in error_msg or "catboost" in error_msg


def test_registry_is_registered():
    """Test is_registered() method."""
    registry = Registry("test")

    class DummyModel:
        pass

    assert not registry.is_registered("dummy")

    registry.register("dummy", DummyModel)
    assert registry.is_registered("dummy")
    assert registry.is_registered("DUMMY")  # case-insensitive


def test_registry_list_registered():
    """Test list_registered() returns all registered names."""
    registry = Registry("test")

    class DummyModel:
        pass

    registry.register("lightgbm", DummyModel)
    registry.register("catboost", DummyModel)

    names = registry.list_registered()
    assert "lightgbm" in names
    assert "catboost" in names
    assert len(names) == 2


def test_registry_overwrite():
    """Test that registering same name twice overwrites."""
    registry = Registry("test")

    class OldModel:
        pass

    class NewModel:
        pass

    registry.register("dummy", OldModel)
    assert registry.get("dummy") is OldModel

    registry.register("dummy", NewModel)
    assert registry.get("dummy") is NewModel  # overwritten


def test_registry_name_property():
    """Test that Registry name is stored correctly."""
    registry = Registry("models")
    assert registry.name == "models"


# ---------------------------------------------------------------------------
# MODEL REGISTRY ALIAS TESTS (backward compatibility)
# ---------------------------------------------------------------------------


def test_model_registry_alias_compatibility():
    """Test that ModelRegistry class still works via old import path."""
    # The ModelRegistry class should delegate to model_registry
    # This tests backward compatibility - users can still import and use ModelRegistry

    # Get the original built-in model count to preserve them
    original_models = set(model_registry.list_registered())

    # Test that the alias methods delegate correctly
    class DummyModel:
        pass

    # Register via old alias
    ModelRegistry.register("test_model_alias", DummyModel)

    # Should be available in model_registry
    assert model_registry.is_registered("test_model_alias")

    # Should be able to get via old alias
    assert ModelRegistry.get("test_model_alias") is DummyModel

    # Should be listed in old alias
    assert "test_model_alias" in ModelRegistry.list_models()

    # Cleanup: only remove the test model, preserve built-in ones
    model_registry._registry = {
        k: v for k, v in model_registry._registry.items() if k in original_models
    }


def test_model_registry_alias_case_insensitive():
    """Test that ModelRegistry alias preserves case-insensitive behavior."""
    # Get the original built-in model count to preserve them
    original_models = set(model_registry.list_registered())

    class DummyModel:
        pass

    ModelRegistry.register("CaseTest", DummyModel)

    # All casings should work via alias
    assert ModelRegistry.is_registered("casetest")
    assert ModelRegistry.get("CaseTest") is DummyModel
    assert ModelRegistry.get("casetest") is DummyModel

    # Cleanup: only remove the test model, preserve built-in ones
    model_registry._registry = {
        k: v for k, v in model_registry._registry.items() if k in original_models
    }


# ---------------------------------------------------------------------------
# INTEGRATION TESTS: Verify model_registry default registration
# ---------------------------------------------------------------------------


def test_model_registry_default_models_registered():
    """Test that all built-in models are registered in model_registry."""
    # All built-in model names should be registered
    expected_models = [
        "lightgbm",
        "lgbm",
        "catboost",
        "cat",
        "xgboost",
        "xgb",
        "neural_network",
        "nn",
        "lstm",
        "simple_trend",
        "simple_constant",
    ]

    for model_name in expected_models:
        assert model_registry.is_registered(
            model_name
        ), f"Expected model '{model_name}' not registered in model_registry"


def test_model_registry_get_builtin_models():
    """Test that all built-in models can be retrieved via model_registry."""
    from energizados.modeling.adapters import (
        CATModelAdapter,
        LGBMModelAdapter,
        LSTMNNModelAdapter,
        NNModelAdapter,
        SimpleConstantAdapter,
        SimpleTrendAdapter,
        XGBModelAdapter,
    )

    # Test primary aliases
    assert model_registry.get("lightgbm") is LGBMModelAdapter
    assert model_registry.get("catboost") is CATModelAdapter
    assert model_registry.get("xgboost") is XGBModelAdapter
    assert model_registry.get("neural_network") is NNModelAdapter
    assert model_registry.get("lstm") is LSTMNNModelAdapter
    assert model_registry.get("simple_trend") is SimpleTrendAdapter
    assert model_registry.get("simple_constant") is SimpleConstantAdapter

    # Test short aliases
    assert model_registry.get("lgbm") is LGBMModelAdapter
    assert model_registry.get("cat") is CATModelAdapter
    assert model_registry.get("xgb") is XGBModelAdapter
    assert model_registry.get("nn") is NNModelAdapter


def test_model_registry_case_insensitive_builtin():
    """Test that built-in model names are case-insensitive."""
    # Primary names should work with different casing
    assert model_registry.is_registered("LightGBM")
    assert model_registry.is_registered("CATBOOST")
    assert model_registry.is_registered("XgBoost")

    # Should retrieve the same classes
    assert model_registry.get("lightgbm") is model_registry.get("LightGBM")
    assert model_registry.get("LIGHTGBM") is model_registry.get("lgbm")
