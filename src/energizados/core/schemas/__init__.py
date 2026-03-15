"""
JSON Schemas for configuration validation.

This module contains JSON Schema definitions for validating
YAML configuration files used in the Energizados framework.
"""

from energizados.core.schemas.config_validator import ConfigValidator

__all__ = [
    "ConfigValidator",
    "ETL_SCHEMA",
    "TRAINING_SCHEMA",
    "EVALUATION_SCHEMA",
    "INFERENCE_SCHEMA",
    "EDA_SCHEMA",
]
