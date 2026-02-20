"""
Excepciones personalizadas para el framework Energizados.

Este módulo define las excepciones específicas que se utilizan
en el pipeline y sus componentes.
"""


class EnergizadosError(Exception):
    """Clase base para todas las excepciones de Energizados."""

    pass


class PipelineError(EnergizadosError):
    """
    Excepción levantada cuando ocurre un error en la ejecución del pipeline.

    Esta excepción se utiliza para errores generales que ocurren durante
    la ejecución del pipeline de ML.
    """

    def __init__(self, message: str, step: str = None):
        """
        Inicializa la excepción.

        Args:
            message: Mensaje de error descriptivo
            step: Nombre del paso del pipeline donde ocurrió el error (opcional)
        """
        self.step = step
        if step:
            full_message = f"Error en paso '{step}': {message}"
        else:
            full_message = message
        super().__init__(full_message)


class StepValidationError(EnergizadosError):
    """
    Excepción levantada cuando la validación de un paso del pipeline falla.

    Esta excepción se utiliza cuando un paso del pipeline no recibe
    los datos necesarios en el contexto para poder ejecutarse.
    """

    def __init__(self, message: str, step: str = None, missing_keys: list = None):
        """
        Inicializa la excepción.

        Args:
            message: Mensaje de error descriptivo
            step: Nombre del paso que falló la validación (opcional)
            missing_keys: Lista de claves del contexto que faltan (opcional)
        """
        self.step = step
        self.missing_keys = missing_keys or []

        full_message = message
        if step:
            full_message = f"Validación falló en paso '{step}': {message}"
        if missing_keys:
            full_message += f" | Claves faltantes: {missing_keys}"

        super().__init__(full_message)


class ConfigurationError(EnergizadosError):
    """
    Excepción levantada cuando hay un error en la configuración del pipeline.

    Esta excepción se utiliza cuando el archivo YAML de configuración
    tiene errores de formato, valores inválidos o falta algún campo requerido.
    """

    def __init__(self, message: str, config_path: str = None):
        """
        Inicializa la excepción.

        Args:
            message: Mensaje de error descriptivo
            config_path: Ruta del archivo de configuración (opcional)
        """
        self.config_path = config_path
        if config_path:
            full_message = f"Error en configuración '{config_path}': {message}"
        else:
            full_message = message
        super().__init__(full_message)


class ModelNotFittedError(EnergizadosError):
    """
    Excepción levantada cuando se intenta predecir con un modelo no entrenado.

    Esta excepción se utiliza cuando se llama a predict() o predict_proba()
    en un modelo que no ha sido entrenado previamente con fit().
    """

    def __init__(self, model_name: str = None):
        """
        Inicializa la excepción.

        Args:
            model_name: Nombre del modelo (opcional)
        """
        if model_name:
            message = f"El modelo '{model_name}' no está entrenado. Llame a fit() primero."
        else:
            message = "El modelo no está entrenado. Llame a fit() primero."
        super().__init__(message)


class ETLError(EnergizadosError):
    """
    Excepción levantada cuando ocurre un error en el proceso ETL.

    Esta excepción se utiliza para errores específicos que ocurren
    durante las fases de extract, transform o load.
    """

    def __init__(self, message: str, phase: str = None):
        """
        Inicializa la excepción.

        Args:
            message: Mensaje de error descriptivo
            phase: Fase del ETL donde ocurrió el error (extract/transform/load)
        """
        self.phase = phase
        if phase:
            full_message = f"Error en fase '{phase}': {message}"
        else:
            full_message = message
        super().__init__(full_message)


class ETLDependencyError(EnergizadosError):
    """
    Excepción levantada cuando hay errores en dependencias entre ETLs.

    Esta excepción se utiliza cuando:
    - Una ETL referencia una dependencia inexistente
    - Hay un ciclo en el grafo de dependencias
    - Una dependencia no se ejecutó correctamente
    """

    def __init__(self, message: str):
        """
        Inicializa la excepción.

        Args:
            message: Mensaje de error descriptivo
        """
        super().__init__(message)
