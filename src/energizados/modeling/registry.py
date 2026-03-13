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
        )

        # Supervised models (adapters that implement BaseModel)
        ModelRegistry.register("lightgbm", LGBMModelAdapter)
        ModelRegistry.register("lgbm", LGBMModelAdapter)
        ModelRegistry.register("catboost", CATModelAdapter)
        ModelRegistry.register("cat", CATModelAdapter)
        ModelRegistry.register("neural_network", NNModelAdapter)
        ModelRegistry.register("nn", NNModelAdapter)
        ModelRegistry.register("lstm", LSTMNNModelAdapter)

        # Simple models (baseline)
        ModelRegistry.register("simple_trend", SimpleTrendAdapter)
        ModelRegistry.register("simple_constant", SimpleConstantAdapter)

        # Ensemble model
        from energizados.modeling.ensemble import EnsembleModel

        ModelRegistry.register("ensemble", EnsembleModel)

    except ImportError as e:
        # Models may not be available if dependencies are missing
        import warnings

        warnings.warn(f"Could not register all models: {e}")


# Register models on import
_register_default_models()


class InferenceRegistry:
    """
    Centralized registry of available inference classes.

    Allows registering and retrieving inference classes by name.
    """

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, inference_class: type) -> None:
        """
        Register an inference class with a name.

        Args:
            name: Inference class name.
            inference_class: Inference class (must inherit from BaseInference).
        """
        cls._registry[name.lower()] = inference_class

    @classmethod
    def get(cls, name: str) -> type:
        """
        Get an inference class by name.

        Args:
            name: Inference class name.

        Returns:
            type: Inference class.

        Raises:
            KeyError: If the inference class is not registered.
        """
        name_lower = name.lower()
        if name_lower not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise KeyError(f"Inference class '{name}' not found. Available classes: {available}")
        return cls._registry[name_lower]

    @classmethod
    def list_inference(cls) -> list:
        """
        Return the list of registered inference classes.

        Returns:
            list: Names of registered inference classes.
        """
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if an inference class is registered.

        Args:
            name: Inference class name.

        Returns:
            bool: True if the inference class is registered.
        """
        return name.lower() in cls._registry

    @classmethod
    def create(cls, name: str, **kwargs) -> Any:
        """
        Create an inference class instance.

        Args:
            name: Inference class name.
            **kwargs: Arguments to pass to the constructor.

        Returns:
            Inference class instance.
        """
        inference_class = cls.get(name)
        return inference_class(**kwargs)


# Registration of available inference classes
def _register_default_inference():
    """
    Register the framework's default inference classes.

    This function is called automatically when importing the module.
    """
    try:
        from energizados.inference import DefaultInference

        InferenceRegistry.register("default", DefaultInference)

    except ImportError as e:
        # Inference classes may not be available if dependencies are missing
        import warnings

        warnings.warn(f"Could not register all inference classes: {e}")


# Register inference classes on import
_register_default_inference()
