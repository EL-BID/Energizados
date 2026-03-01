"""
Energizados Core Module

This module contains the abstract base classes and pipeline orchestrator
that form the core of the framework.
"""

from energizados.core.base import (
    BaseModel,
    PipelineStep,
)
from energizados.core.exceptions import (
    PipelineError,
    StepValidationError,
)
from energizados.core.pipeline import (
    ConfigPipelineBuilder,
    Pipeline,
)
from energizados.core.plots.utils import plot_roc
from energizados.etl.base import BaseETL

__all__ = [
    # Base classes
    "BaseETL",
    "BaseModel",
    "PipelineStep",
    # Exceptions
    "PipelineError",
    "StepValidationError",
    # Pipeline
    "Pipeline",
    "ConfigPipelineBuilder",
    # Plotting utilities
    "plot_roc",
]
