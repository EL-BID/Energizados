"""
Model Registry for Energizados Framework.

Mantiene un registro centralizado de los modelos disponibles
para ser utilizados en el pipeline del framework.
"""

from typing import Any, Dict


class ModelRegistry:
    """
    Registro centralizado de modelos disponibles.

    Permite registrar y recuperar modelos por su nombre.
    """

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, model_class: type) -> None:
        """
        Registra un modelo con un nombre.

        Args:
            name: Nombre del modelo
            model_class: Clase del modelo (debe heredar de BaseModel)
        """
        cls._registry[name.lower()] = model_class

    @classmethod
    def get(cls, name: str) -> type:
        """
        Obtiene una clase de modelo por su nombre.

        Args:
            name: Nombre del modelo

        Returns:
            type: Clase del modelo

        Raises:
            KeyError: Si el modelo no está registrado
        """
        name_lower = name.lower()
        if name_lower not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise KeyError(f"Modelo '{name}' no encontrado. Modelos disponibles: {available}")
        return cls._registry[name_lower]

    @classmethod
    def list_models(cls) -> list:
        """
        Retorna la lista de modelos registrados.

        Returns:
            list: Nombres de modelos registrados
        """
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Verifica si un modelo está registrado.

        Args:
            name: Nombre del modelo

        Returns:
            bool: True si el modelo está registrado
        """
        return name.lower() in cls._registry

    @classmethod
    def create(cls, name: str, **kwargs) -> Any:
        """
        Crea una instancia de un modelo.

        Args:
            name: Nombre del modelo
            **kwargs: Argumentos para pasar al constructor del modelo

        Returns:
            Instancia del modelo
        """
        model_class = cls.get(name)
        return model_class(**kwargs)


# Registro de modelos disponibles
def _register_default_models():
    """
    Registra los modelos por defecto del framework.

    Esta función se llama automáticamente al importar el módulo.
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

        # Modelos supervisados (adapters que implementan BaseModel)
        ModelRegistry.register("lightgbm", LGBMModelAdapter)
        ModelRegistry.register("lgbm", LGBMModelAdapter)
        ModelRegistry.register("catboost", CATModelAdapter)
        ModelRegistry.register("cat", CATModelAdapter)
        ModelRegistry.register("neural_network", NNModelAdapter)
        ModelRegistry.register("nn", NNModelAdapter)
        ModelRegistry.register("lstm", LSTMNNModelAdapter)

        # Modelos simples (baseline)
        ModelRegistry.register("simple_trend", SimpleTrendAdapter)
        ModelRegistry.register("simple_constant", SimpleConstantAdapter)

    except ImportError as e:
        # Los modelos pueden no estar disponibles si faltan dependencias
        import warnings

        warnings.warn(f"No se pudieron registrar todos los modelos: {e}")


# Registrar modelos al importar
_register_default_models()


class InferenceRegistry:
    """
    Registro centralizado de clases de inferencia disponibles.

    Permite registrar y recuperar clases de inferencia por su nombre.
    """

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, inference_class: type) -> None:
        """
        Registra una clase de inferencia con un nombre.

        Args:
            name: Nombre de la clase de inferencia
            inference_class: Clase de inferencia (debe heredar de BaseInference)
        """
        cls._registry[name.lower()] = inference_class

    @classmethod
    def get(cls, name: str) -> type:
        """
        Obtiene una clase de inferencia por su nombre.

        Args:
            name: Nombre de la clase de inferencia

        Returns:
            type: Clase de inferencia

        Raises:
            KeyError: Si la clase de inferencia no está registrada
        """
        name_lower = name.lower()
        if name_lower not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise KeyError(f"Clase de inferencia '{name}' no encontrada. Clases disponibles: {available}")
        return cls._registry[name_lower]

    @classmethod
    def list_inference(cls) -> list:
        """
        Retorna la lista de clases de inferencia registradas.

        Returns:
            list: Nombres de clases de inferencia registradas
        """
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Verifica si una clase de inferencia está registrada.

        Args:
            name: Nombre de la clase de inferencia

        Returns:
            bool: True si la clase de inferencia está registrada
        """
        return name.lower() in cls._registry

    @classmethod
    def create(cls, name: str, **kwargs) -> Any:
        """
        Crea una instancia de una clase de inferencia.

        Args:
            name: Nombre de la clase de inferencia
            **kwargs: Argumentos para pasar al constructor

        Returns:
            Instancia de la clase de inferencia
        """
        inference_class = cls.get(name)
        return inference_class(**kwargs)


# Registro de clases de inferencia disponibles
def _register_default_inference():
    """
    Registra las clases de inferencia por defecto del framework.

    Esta función se llama automáticamente al importar el módulo.
    """
    try:
        from energizados.inference import DefaultInference

        InferenceRegistry.register("default", DefaultInference)

    except ImportError as e:
        # Las clases de inferencia pueden no estar disponibles si faltan dependencias
        import warnings

        warnings.warn(f"No se pudieron registrar todas las clases de inferencia: {e}")


# Registrar clases de inferencia al importar
_register_default_inference()
