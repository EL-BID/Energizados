"""
Base StepBuilder abstract class.

This module defines the interface for all pipeline step builders.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from energizados.core.base import PipelineStep


class StepBuilder(ABC):
    """
    Abstract base class for pipeline step builders.

    Builders are responsible for constructing PipelineStep instances
    from configuration dictionaries. Each builder handles a specific
    type of step (ETL, Split, Training, etc.).

    Attributes:
        config: The configuration dictionary for this builder
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the builder with configuration.

        Args:
            config: Configuration dictionary for the step
        """
        self.config = config

    @abstractmethod
    def build(self) -> Optional[PipelineStep]:
        """
        Build the pipeline step from configuration.

        Returns:
            PipelineStep: The constructed step, or None if not configured

        Raises:
            ConfigurationError: If configuration is invalid
        """
        pass

    def is_enabled(self) -> bool:
        """
        Check if this step is enabled in the configuration.

        Returns:
            bool: True if the step should be built
        """
        # Default implementation checks for 'enabled' key
        # Subclasses can override for custom logic
        return self.config.get("enabled", True)

    def get_step_name(self) -> str:
        """
        Get the name of the step being built.

        Returns:
            str: The step class name
        """
        # Default returns the class name without 'Builder' suffix
        name = self.__class__.__name__
        if name.endswith("Builder"):
            name = name[:-7]
        return name
