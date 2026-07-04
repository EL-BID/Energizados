"""
Custom exceptions for the Energizados framework.

This module defines the specific exceptions that are used
in the pipeline and its components.
"""

from typing import Any, Dict


class EnergizadosError(Exception):
    """Base class for all Energizados exceptions."""

    error_code: str = "ENERGIZADOS_ERROR"

    def __init__(self, message: str, error_code: str = None, **details):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            error_code: Optional per-instance error code override
            **details: Additional error context stored in details dict
        """
        super().__init__(message)
        # Store error_code as instance attribute if provided (shadows class attr)
        if error_code is not None:
            self.error_code = error_code
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        """Machine-readable error representation."""
        return {
            "error_code": self.error_code,
            "message": str(self),
            "details": self.details,
        }


class PipelineError(EnergizadosError):
    """
    Exception raised when an error occurs during pipeline execution.

    This exception is used for general errors that occur during
    the execution of the ML pipeline.
    """

    error_code = "PIPELINE_EXECUTION_FAILED"

    def __init__(self, message: str, step: str = None, error_code: str = None, **details):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            step: Name of the pipeline step where the error occurred (optional)
            error_code: Optional per-instance error code override
            **details: Additional error context
        """
        self.step = step
        if step:
            full_message = f"Error in step '{step}': {message}"
        else:
            full_message = message
        # Forward error_code to base class for instance-level storage
        super().__init__(full_message, error_code=error_code, step=step, **details)


class StepValidationError(EnergizadosError):
    """
    Exception raised when the validation of a pipeline step fails.

    This exception is used when a pipeline step does not receive
    the necessary data in the context to be able to execute.
    """

    error_code = "STEP_VALIDATION_FAILED"

    def __init__(
        self,
        message: str,
        step: str = None,
        missing_keys: list = None,
        error_code: str = None,
        **details,
    ):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            step: Name of the step that failed validation (optional)
            missing_keys: List of missing context keys (optional)
            error_code: Optional per-instance error code override
            **details: Additional error context
        """
        self.step = step
        self.missing_keys = missing_keys or []

        full_message = message
        if step:
            full_message = f"Validation failed in step '{step}': {message}"
        if missing_keys:
            full_message += f" | Missing keys: {missing_keys}"

        # Forward error_code to base class for instance-level storage
        super().__init__(
            full_message,
            error_code=error_code,
            step=step,
            missing_keys=missing_keys or [],
            **details,
        )


class ConfigurationError(EnergizadosError):
    """
    Exception raised when there is an error in the pipeline configuration.

    This exception is used when the YAML configuration file
    has format errors, invalid values, or missing required fields.
    """

    error_code = "CONFIG_INVALID"

    def __init__(self, message: str, config_path: str = None, error_code: str = None, **details):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            config_path: Path to the configuration file (optional)
            error_code: Optional per-instance error code override (e.g., for prefix violations)
            **details: Additional error context
        """
        self.config_path = config_path
        if config_path:
            full_message = f"Error in configuration '{config_path}': {message}"
        else:
            full_message = message
        # Forward error_code to base class for instance-level storage
        # NOTE: config_path is NOT included in details to avoid duplication
        # It's added back by to_dict() as a top-level field
        super().__init__(full_message, error_code=error_code, **details)

    def to_dict(self) -> Dict[str, Any]:
        """Machine-readable error representation with config_path field."""
        d = super().to_dict()
        d["config_path"] = self.config_path
        return d


class ModelNotFittedError(EnergizadosError, ValueError):
    """
    Exception raised when trying to predict with an unfitted model.

    This exception is used when predict() or predict_proba()
    is called on a model that has not been previously trained with fit().

    Also subclasses ``ValueError`` so existing ``except ValueError`` callers
    (fitted-state guards) keep working while gaining the framework catch path.
    """

    error_code = "MODEL_NOT_FITTED"

    def __init__(self, model_name: str = None, error_code: str = None, **details):
        """
        Initialize the exception.

        Args:
            model_name: Name of the model (optional)
            error_code: Optional per-instance error code override
            **details: Additional error context
        """
        if model_name:
            message = f"Model '{model_name}' is not fitted. Call fit() first."
        else:
            message = "Model is not fitted. Call fit() first."
        # Forward error_code to base class for instance-level storage
        super().__init__(message, error_code=error_code, model_name=model_name, **details)

    # Inherits to_dict() from EnergizadosError
    # except ValueError continues to work (stdlib base unchanged)


class ETLError(EnergizadosError):
    """
    Exception raised when an error occurs in the ETL process.

    This exception is used for specific errors that occur
    during extract, transform, or load phases.
    """

    error_code = "ETL_EXECUTION_FAILED"

    def __init__(self, message: str, phase: str = None, error_code: str = None, **details):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            phase: ETL phase where the error occurred (extract/transform/load)
            error_code: Optional per-instance error code override
            **details: Additional error context
        """
        self.phase = phase
        if phase:
            full_message = f"Error in phase '{phase}': {message}"
        else:
            full_message = message
        # Forward error_code to base class for instance-level storage
        super().__init__(full_message, error_code=error_code, phase=phase, **details)


class ETLDependencyError(EnergizadosError):
    """
    Exception raised when there are errors in dependencies between ETLs.

    This exception is used when:
    - An ETL references a non-existent dependency
    - There is a cycle in the dependency graph
    - A dependency did not execute correctly
    """

    error_code = "ETL_DEPENDENCY_CYCLE"

    def __init__(self, message: str, error_code: str = None, **details):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            error_code: Optional per-instance error code override
            **details: Additional error context
        """
        # Forward error_code to base class for instance-level storage
        super().__init__(message, error_code=error_code, **details)


class TransformerError(EnergizadosError, ValueError):
    """
    Exception raised when a feature-engineering transform fails.

    Subclasses ``ValueError`` so existing ``except ValueError`` callers
    keep working while gaining the framework catch path.
    """

    error_code = "TRANSFORM_FAILED"


class FeatureSelectionError(EnergizadosError, ValueError):
    """
    Exception raised when a feature-selection operation fails.

    Subclasses ``ValueError`` so existing ``except ValueError`` callers
    keep working while gaining the framework catch path.
    """

    error_code = "FEATURE_SELECTION_FAILED"


class InferenceError(EnergizadosError, RuntimeError):
    """
    Exception raised when an inference engine fails.

    Subclasses ``RuntimeError`` so existing ``except RuntimeError`` callers
    keep working while gaining the framework catch path.
    """

    error_code = "INFERENCE_FAILED"


class EvaluatorError(EnergizadosError):
    """
    Exception raised when an evaluation or reporting operation fails.

    Framework-only (no stdlib base): there is no conversion site today, so
    adding a stdlib base would be a gratuitous API commitment. It exists for
    symmetry/completeness and is the natural home for the next evaluator
    failure.
    """

    error_code = "EVALUATION_FAILED"
