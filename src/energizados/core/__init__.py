"""
Energizados Core Module

Este módulo contiene las clases base abstractas y el orquestador del pipeline
que forman el núcleo del framework.
"""

from energizados.core.base import (
    BaseETL,
    BaseFeatureSelector,
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

__all__ = [
    # Base classes
    "BaseETL",
    "BaseFeatureSelector",
    "BaseModel",
    "PipelineStep",
    # Exceptions
    "PipelineError",
    "StepValidationError",
    # Pipeline
    "Pipeline",
    "ConfigPipelineBuilder",
]
