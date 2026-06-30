"""
Model Registry for Energizados Framework.

Maintains a centralized registry of available models
for use in the framework pipeline.
"""

from typing import Any, Dict


class ModelRegistry:
    """
    Centralized registry of available models.

    Allows registering and retrieving models by name.
    """

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, model_class: type) -> None:
        """
        Register a model with a name.

        Args:
            name: Model name.
            model_class: Model class (must inherit from BaseModel).
        """
        cls._registry[name.lower()] = model_class

    @classmethod
    def get(cls, name: str) -> type:
        """
        Get a model class by name.

        Args:
            name: Model name.

        Returns:
            type: Model class.

        Raises:
            KeyError: If the model is not registered.
        """
        name_lower = name.lower()
        if name_lower not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise KeyError(f"Model '{name}' not found. Available models: {available}")
        return cls._registry[name_lower]

    @classmethod
    def list_models(cls) -> list:
        """
        Return the list of registered models.

        Returns:
            list: Names of registered models.
        """
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a model is registered.

        Args:
            name: Model name.

        Returns:
            bool: True if the model is registered.
        """
        return name.lower() in cls._registry

    @classmethod
    def create(cls, name: str, **kwargs) -> Any:
        """
        Create a model instance.

        Args:
            name: Model name.
            **kwargs: Arguments to pass to the model constructor.

        Returns:
            Model instance.
        """
        model_class = cls.get(name)
        return model_class(**kwargs)


# Registration of available models
def _register_default_models():
    """
    Register the framework's default models.

    This function is called automatically when importing the module.
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
        ModelRegistry.register("lightgbm", LGBMModelAdapter)
        ModelRegistry.register("lgbm", LGBMModelAdapter)
        ModelRegistry.register("catboost", CATModelAdapter)
        ModelRegistry.register("cat", CATModelAdapter)
        ModelRegistry.register("xgboost", XGBModelAdapter)
        ModelRegistry.register("xgb", XGBModelAdapter)
        ModelRegistry.register("neural_network", NNModelAdapter)
        ModelRegistry.register("nn", NNModelAdapter)
        ModelRegistry.register("lstm", LSTMNNModelAdapter)

        # Simple models (baseline)
        ModelRegistry.register("simple_trend", SimpleTrendAdapter)
        ModelRegistry.register("simple_constant", SimpleConstantAdapter)

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
