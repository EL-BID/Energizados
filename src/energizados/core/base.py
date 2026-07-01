"""
Abstract Base Classes for the Energizados Framework.

This module now re-exports from energizados.contracts for backward compatibility.
"""

# PipelineStep stays here (not in contracts)
from abc import ABC, abstractmethod
from typing import Any, Dict

# Re-export from contracts
from energizados.contracts import BaseInference, BaseModel


class PipelineStep(ABC):
    """
    Base class for pipeline steps.

    Pipeline steps must inherit from this class and implement
    methods to validate input and execute the step.

    Example:
        >>> from energizados.core.base import PipelineStep
        >>> class MyStep(PipelineStep):
        ...     def validate_input(self, context):
        ...         return 'data' in context
        ...     def execute(self, context):
        ...         context['result'] = process(context['data'])
        ...         return context
    """

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the pipeline step.

        Args:
            context: Dictionary with pipeline data

        Returns:
            Dict: Context updated with step results

        Raises:
            PipelineError: If an error occurs during execution
        """
        pass

    @abstractmethod
    def validate_input(self, context: Dict[str, Any]) -> bool:
        """
        Validate that the context has the necessary data.

        Args:
            context: Dictionary with pipeline data

        Returns:
            bool: True if validation is successful, False otherwise
        """
        pass

    def get_required_keys(self) -> list:
        """
        Return the list of required keys in the context.

        This method can be overridden to specify which keys
        are necessary for the step to be able to execute.

        Returns:
            list: List of required key names
        """
        return []

    def get_output_keys(self) -> list:
        """
        Return the list of keys that this step adds to the context.

        This method can be overridden to specify which keys
        this step adds to the context.

        Returns:
            list: List of output key names
        """
        return []


__all__ = ["BaseModel", "BaseInference", "PipelineStep"]
