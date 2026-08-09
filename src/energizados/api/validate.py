"""
Configuration validation API for Energizados.

This module provides structured configuration validation without file I/O,
ported from the CLI validate command but with programmatic return values.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from energizados.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class ConfigError:
    """Single configuration error."""

    field: str
    message: str
    location: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {"field": self.field, "message": self.message, "location": self.location}


@dataclass
class ConfigWarning:
    """Single configuration warning."""

    field: str
    message: str
    deprecation_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {
            "field": self.field,
            "message": self.message,
            "deprecation_path": self.deprecation_path,
        }


@dataclass
class ConfigInfo:
    """Single configuration info message."""

    field: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {"field": self.field, "message": self.message}


@dataclass
class ValidationResult:
    """Result of configuration validation.

    Attributes:
        is_valid: Whether the configuration is valid (no errors)
        errors: List of configuration errors
        warnings: List of configuration warnings
        info: List of informational messages
    """

    is_valid: bool = True
    errors: List[ConfigError] = field(default_factory=list)
    warnings: List[ConfigWarning] = field(default_factory=list)
    info: List[ConfigInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "info": [i.to_dict() for i in self.info],
        }


def validate_dict(config: Dict[str, Any], config_type: str) -> ValidationResult:
    """Validate configuration dict without file I/O.

    This function performs the same validation logic as the CLI validate command
    but returns structured results instead of printing to stdout.

    Args:
        config: Configuration dictionary to validate
        config_type: Type of configuration ("etl", "train", "infer", "eda")

    Returns:
        ValidationResult with errors, warnings, and info messages

    Raises:
        ConfigurationError: If config_type is unknown with error_code="CONFIG_UNKNOWN_TYPE"
    """
    result = ValidationResult(is_valid=True, errors=[], warnings=[], info=[])

    # Validate config_type
    valid_types = ["etl", "train", "infer", "eda"]
    if config_type not in valid_types:
        raise ConfigurationError(
            f"Unknown config_type: '{config_type}'. Valid types: {valid_types}",
            error_code="CONFIG_UNKNOWN_TYPE",
        )

    # Route to appropriate validation function
    if config_type == "etl":
        _validate_etl_section(config, result)
    elif config_type == "train":
        _validate_training_section(config, result)
    elif config_type == "infer":
        _validate_inference_section(config, result)
    elif config_type == "eda":
        _validate_eda_section(config, result)

    # Common validations
    _validate_project_section(config, result)

    # Update is_valid based on errors
    result.is_valid = len(result.errors) == 0

    return result


def _validate_project_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the project section of the configuration."""
    if "project" not in config:
        result.warnings.append(
            ConfigWarning(field="project", message="'project' section not found (optional)")
        )
        return

    project = config["project"]
    if "name" not in project:
        result.warnings.append(
            ConfigWarning(field="project.name", message="project.name not defined")
        )
    else:
        result.info.append(ConfigInfo(field="project", message=f"Project: {project['name']}"))


def _validate_etl_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the ETL section of the configuration."""
    if "etl" not in config:
        result.info.append(
            ConfigInfo(
                field="etl",
                message="'etl' section not present in this config (skipping ETL validation)",
            )
        )
        return

    etl_config = config["etl"]
    if not isinstance(etl_config, dict):
        result.errors.append(
            ConfigError(field="etl", message="'etl' section must be a dictionary", location="etl")
        )
        return

    if not etl_config:
        result.warnings.append(ConfigWarning(field="etl", message="'etl' section is empty"))
        return

    from energizados._version import SCHEMA_VERSION_KEY

    # Validate each ETL (skip reserved metadata keys)
    for etl_name, etl_config_item in etl_config.items():
        if etl_name == SCHEMA_VERSION_KEY:
            continue
        if not isinstance(etl_config_item, dict):
            result.errors.append(
                ConfigError(
                    field=f"etl.{etl_name}",
                    message=f"ETL '{etl_name}': must be a dictionary",
                    location=f"etl.{etl_name}",
                )
            )
            continue

        # Check required fields
        if "input" not in etl_config_item:
            result.errors.append(
                ConfigError(
                    field=f"etl.{etl_name}.input",
                    message=f"ETL '{etl_name}': required field 'input'",
                    location=f"etl.{etl_name}",
                )
            )

        # Check custom_class (mandatory)
        if "custom_class" not in etl_config_item:
            result.errors.append(
                ConfigError(
                    field=f"etl.{etl_name}.custom_class",
                    message=f"ETL '{etl_name}': must specify 'custom_class'",
                    location=f"etl.{etl_name}",
                )
            )
        else:
            _validate_class_reference(etl_config_item["custom_class"], result, f"etl.{etl_name}")

        enabled = etl_config_item.get("enabled", True)
        result.info.append(
            ConfigInfo(
                field=f"etl.{etl_name}",
                message=f"ETL '{etl_name}': {'enabled' if enabled else 'disabled'}",
            )
        )


def _validate_training_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the training section of the configuration."""
    if "train" not in config:
        result.info.append(
            ConfigInfo(
                field="train",
                message="'train' section not present in this config (skipping training validation)",
            )
        )
        return

    training = config["train"]
    if not isinstance(training, dict):
        result.errors.append(
            ConfigError(
                field="train", message="'train' section must be a dictionary", location="train"
            )
        )
        return

    # Check for legacy model: format (deprecated)
    if "model" in training:
        result.warnings.append(
            ConfigWarning(
                field="train.model",
                message="train: 'model:' key is deprecated. Use 'models:' list format instead.",
            )
        )

    # Check models list
    if "models" in training:
        models = training["models"]
        if not isinstance(models, list):
            result.errors.append(
                ConfigError(
                    field="train.models",
                    message="train.models must be a list",
                    location="train.models",
                )
            )
    else:
        result.warnings.append(
            ConfigWarning(
                field="train.models",
                message="train.models not found (training will have no models)",
            )
        )


def _validate_inference_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the inference section of the configuration."""
    if "infer" not in config:
        result.warnings.append(
            ConfigWarning(field="infer", message="'infer' section not found (optional)")
        )
        return

    inf = config["infer"]
    if not isinstance(inf, dict):
        result.errors.append(
            ConfigError(
                field="infer", message="'infer' section must be a dictionary", location="infer"
            )
        )
        return

    if inf.get("enabled", False):
        if "input_path" not in inf:
            result.warnings.append(
                ConfigWarning(field="infer.input_path", message="inference.input_path not defined")
            )

        if "output_path" not in inf:
            result.warnings.append(
                ConfigWarning(
                    field="infer.output_path", message="inference.output_path not defined"
                )
            )

        if "custom_class" in inf:
            _validate_class_reference(inf["custom_class"], result, "infer")

        result.info.append(ConfigInfo(field="infer", message="Inference: enabled"))
    else:
        result.info.append(ConfigInfo(field="infer", message="Inference: disabled"))


def _validate_eda_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the EDA section of the configuration."""
    if "eda" not in config:
        result.info.append(
            ConfigInfo(
                field="eda",
                message="'eda' section not present in this config (skipping EDA validation)",
            )
        )
        return

    eda = config["eda"]
    if not isinstance(eda, dict):
        result.errors.append(
            ConfigError(field="eda", message="'eda' section must be a dictionary", location="eda")
        )
        return

    if eda.get("enabled", False):
        if "input_path" not in eda:
            result.warnings.append(
                ConfigWarning(field="eda.input_path", message="EDA input_path not defined")
            )

        result.info.append(ConfigInfo(field="eda", message="EDA: enabled"))
    else:
        result.info.append(ConfigInfo(field="eda", message="EDA: disabled"))


def _validate_class_reference(
    class_path: str, result: ValidationResult, location: str = ""
) -> None:
    """Validate a class reference string.

    Checks if the class path looks valid (basic format check).
    Actual import is not attempted to avoid side effects.
    """
    if not class_path:
        result.errors.append(
            ConfigError(
                field="custom_class", message="Custom class path is empty", location=location
            )
        )
        return

    parts = class_path.split(".")
    if len(parts) < 2:
        result.errors.append(
            ConfigError(
                field="custom_class",
                message=f"Invalid class path format: '{class_path}'. Expected 'module.ClassName'",
                location=location,
            )
        )
