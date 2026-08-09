"""
Model Registry for Energizados Framework.

**BACKWARD-COMPATIBLE ALIAS** (Design Decision 5 from unified-registry SDD):

This module now provides a silent alias to the unified `model_registry` from
`energizados.core.registry`. All public methods delegate to the centralized
registry, allowing existing code to continue using `ModelRegistry` without
changes while internally using the unified pattern.

No deprecation warning in this release (public extension point must remain stable).
"""

from typing import Any

# Import the unified registry
from energizados.core.registry import model_registry


class ModelRegistry:
    """
    **Silent backward-compatible alias** to the unified model_registry.

    This class delegates all method calls to the centralized `model_registry`
    instance from `energizados.core.registry`. Existing code using
    `from energizados.modeling.registry import ModelRegistry` continues to work
    without changes.

    No deprecation warning — this is a permanent alias, not transitional.
    """

    @classmethod
    def register(cls, name: str, model_class: type) -> None:
        """Register a model with a name (delegates to model_registry)."""
        model_registry.register(name, model_class)

    @classmethod
    def get(cls, name: str) -> type:
        """Get a model class by name (delegates to model_registry)."""
        return model_registry.get(name)

    @classmethod
    def list_models(cls) -> list:
        """Return the list of registered models (delegates to model_registry)."""
        return model_registry.list_registered()

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a model is registered (delegates to model_registry)."""
        return model_registry.is_registered(name)

    @classmethod
    def create(cls, name: str, **kwargs) -> Any:
        """Create a model instance (delegates to model_registry)."""
        model_class = cls.get(name)
        return model_class(**kwargs)


# Registration of available models
def _register_default_models():
    """
    Register the framework's default models.

    This function is called automatically when importing the module.
    Models are now registered in the unified model_registry from
    energizados.core.registry.
    """
    try:
        from energizados.modeling.adapters import (
            CATModelAdapter,
            LGBMModelAdapter,
            LSTMNNModelAdapter,
            NNModelAdapter,
            SimpleConstantAdapter,
            SimpleTrendAdapter,
            XGBModelAdapter,
        )

        # Supervised models (adapters that implement BaseModel)
        # Now using unified model_registry instead of ModelRegistry._registry
        model_registry.register("lightgbm", LGBMModelAdapter)
        model_registry.register("lgbm", LGBMModelAdapter)
        model_registry.register("catboost", CATModelAdapter)
        model_registry.register("cat", CATModelAdapter)
        model_registry.register("xgboost", XGBModelAdapter)
        model_registry.register("xgb", XGBModelAdapter)
        model_registry.register("neural_network", NNModelAdapter)
        model_registry.register("nn", NNModelAdapter)
        model_registry.register("lstm", LSTMNNModelAdapter)

        # Simple models (baseline)
        model_registry.register("simple_trend", SimpleTrendAdapter)
        model_registry.register("simple_constant", SimpleConstantAdapter)

        # NOTE: EnsembleModel is intentionally NOT registered here. It cannot be
        # created through the registry (its __init__ requires base_models /
        # model_types / model_names) and MODEL_CONFIG_SCHEMA.type.enum does not
        # include "ensemble". It is built directly in TrainingStep._train_ensemble.

    except ImportError as e:
        # Models may not be available if dependencies are missing
        import warnings

        warnings.warn(f"Could not register all models: {e}")


# Register models on import
_register_default_models()
