"""
Tests for IsolationForestAdapter removal.

Verifies that IsolationForestAdapter is completely removed from the codebase.
This test MUST FAIL initially (adapter still exists), then PASS after removal.
"""

import pytest


class TestIsolationForestAdapterRemoval:
    """Test that IsolationForestAdapter has been completely removed."""

    def test_isolation_forest_adapter_not_importable(self):
        """IsolationForestAdapter should raise ImportError when imported."""
        with pytest.raises(ImportError):
            from energizados.modeling.adapters import (  # noqa: F401
                IsolationForestAdapter,
            )

    def test_isolation_forest_not_in_registry(self):
        """'isolation_forest' should NOT be in ModelRegistry.list_models()."""
        from energizados.modeling.registry import ModelRegistry

        registered_models = ModelRegistry.list_models()
        assert (
            "isolation_forest" not in registered_models
        ), f"'isolation_forest' found in registered models: {registered_models}"

    def test_isolation_forest_model_raises_keyerror(self):
        """Trying to create an isolation_forest model should raise KeyError."""
        from energizados.modeling.registry import ModelRegistry

        with pytest.raises(KeyError) as exc_info:
            ModelRegistry.create("isolation_forest", cols_for_model=["col1"])

        # Verify the error message mentions isolation_forest
        assert "isolation_forest" in str(exc_info.value).lower()

    def test_isolation_forest_adapter_class_not_in_adapters_module(self):
        """IsolationForestAdapter class should not exist in adapters module."""
        import inspect

        from energizados.modeling import adapters

        # Check that IsolationForestAdapter is not a member of the module
        module_members = dict(inspect.getmembers(adapters, inspect.isclass))
        assert (
            "IsolationForestAdapter" not in module_members
        ), f"IsolationForestAdapter class found in adapters module: {list(module_members.keys())}"
