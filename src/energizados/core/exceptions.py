"""
Custom exceptions for the Energizados framework.

This module defines the specific exceptions that are used
in the pipeline and its components.
"""


class EnergizadosError(Exception):
    """Base class for all Energizados exceptions."""

    pass


class PipelineError(EnergizadosError):
    """
    Exception raised when an error occurs during pipeline execution.

    This exception is used for general errors that occur during
    the execution of the ML pipeline.
    """

    def __init__(self, message: str, step: str = None):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            step: Name of the pipeline step where the error occurred (optional)
        """
        self.step = step
        if step:
            full_message = f"Error in step '{step}': {message}"
        else:
            full_message = message
        super().__init__(full_message)


class StepValidationError(EnergizadosError):
    """
    Exception raised when the validation of a pipeline step fails.

    This exception is used when a pipeline step does not receive
    the necessary data in the context to be able to execute.
    """

    def __init__(self, message: str, step: str = None, missing_keys: list = None):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            step: Name of the step that failed validation (optional)
            missing_keys: List of missing context keys (optional)
        """
        self.step = step
        self.missing_keys = missing_keys or []

        full_message = message
        if step:
            full_message = f"Validation failed in step '{step}': {message}"
        if missing_keys:
            full_message += f" | Missing keys: {missing_keys}"

        super().__init__(full_message)


class ConfigurationError(EnergizadosError):
    """
    Exception raised when there is an error in the pipeline configuration.

    This exception is used when the YAML configuration file
    has format errors, invalid values, or missing required fields.
    """

    def __init__(self, message: str, config_path: str = None):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            config_path: Path to the configuration file (optional)
        """
        self.config_path = config_path
        if config_path:
            full_message = f"Error in configuration '{config_path}': {message}"
        else:
            full_message = message
        super().__init__(full_message)


class ModelNotFittedError(EnergizadosError):
    """
    Exception raised when trying to predict with an unfitted model.

    This exception is used when predict() or predict_proba()
    is called on a model that has not been previously trained with fit().
    """

    def __init__(self, model_name: str = None):
        """
        Initialize the exception.

        Args:
            model_name: Name of the model (optional)
        """
        if model_name:
            message = f"Model '{model_name}' is not fitted. Call fit() first."
        else:
            message = "Model is not fitted. Call fit() first."
        super().__init__(message)


class ETLError(EnergizadosError):
    """
    Exception raised when an error occurs in the ETL process.

    This exception is used for specific errors that occur
    during extract, transform, or load phases.
    """

    def __init__(self, message: str, phase: str = None):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            phase: ETL phase where the error occurred (extract/transform/load)
        """
        self.phase = phase
        if phase:
            full_message = f"Error in phase '{phase}': {message}"
        else:
            full_message = message
        super().__init__(full_message)


class ETLDependencyError(EnergizadosError):
    """
    Exception raised when there are errors in dependencies between ETLs.

    This exception is used when:
    - An ETL references a non-existent dependency
    - There is a cycle in the dependency graph
    - A dependency did not execute correctly
    """

    def __init__(self, message: str):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
        """
        super().__init__(message)
