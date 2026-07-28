"""
Configuration Validator using JSON Schema.

This module provides validation of YAML configuration files
against JSON Schema definitions.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from energizados.core.exceptions import ConfigurationError
from energizados.core.schemas.schemas import PIPELINE_CONFIG_SCHEMA

logger = logging.getLogger(__name__)


class ValidationError:
    """Represents a configuration validation error."""

    def __init__(self, path: str, message: str):
        """
        Initialize a validation error.

        Args:
            path: JSON path to the invalid field
            message: Error message
        """
        self.path = path
        self.message = message

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class ConfigValidator:
    """
    Validates YAML configuration files against JSON Schemas.

    Provides early detection of configuration errors with clear
    error messages and paths.

    Example:
        >>> validator = ConfigValidator()
        >>> errors = validator.validate("config.yaml")
        >>> if errors:
        ...     for error in errors:
        ...         print(f"Error: {error}")
    """

    def __init__(self, use_default_schema: bool = True):
        """
        Initialize the validator.

        Args:
            use_default_schema: If True, validate against full pipeline schema.
                               If False, validate individual sections.
        """
        self.use_default_schema = use_default_schema

    def validate_file(self, path: str) -> List[ValidationError]:
        """
        Validate a configuration file.

        Args:
            path: Path to the YAML configuration file

        Returns:
            List[ValidationError]: List of validation errors (empty if valid)
        """
        config_file = Path(path)
        if not config_file.exists():
            raise ConfigurationError(f"Configuration file not found: {path}", path)

        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing YAML: {e}", path) from e

        return self.validate_config(config, path)

    def validate_config(
        self, config: Dict[str, Any], source: str = "config"
    ) -> List[ValidationError]:
        """
        Validate a configuration dictionary.

        Args:
            config: Configuration dictionary
            source: Source identifier (file path or "config")

        Returns:
            List[ValidationError]: List of validation errors (empty if valid)
        """
        errors = []

        # Use jsonschema if available, otherwise do basic validation
        try:
            import jsonschema

            schema = PIPELINE_CONFIG_SCHEMA
            validator = jsonschema.Draft7Validator(schema)

            # Collect all errors with proper path formatting
            for error in validator.iter_errors(config):
                path = ".".join(str(p) for p in error.path) or "root"
                errors.append(ValidationError(path, error.message))

        except ImportError:
            # Fallback to basic validation if jsonschema not installed
            logger.warning("jsonschema not installed, using basic validation")
            errors.extend(self._basic_validate(config))

        return errors

    def _basic_validate(self, config: Dict[str, Any]) -> List[ValidationError]:
        """
        Basic validation without jsonschema.

        Performs structural checks on the configuration.

        Args:
            config: Configuration dictionary

        Returns:
            List[ValidationError]: List of validation errors
        """
        errors = []

        # Validate ETL section
        if "etl" in config:
            errors.extend(self._validate_etl(config["etl"]))

        # Validate training section
        if "train" in config:
            errors.extend(self._validate_training(config["train"]))

        # Validate evaluation section
        if "evaluation" in config:
            errors.extend(self._validate_evaluation(config["evaluation"]))

        # Validate inference section
        if "infer" in config:
            errors.extend(self._validate_inference(config["infer"]))

        # Validate EDA section
        if "eda" in config:
            errors.extend(self._validate_eda(config["eda"]))

        return errors

    def _validate_etl(self, etl_config: Any) -> List[ValidationError]:
        """Validate ETL configuration."""
        errors = []

        if not isinstance(etl_config, dict):
            return [ValidationError("etl", "ETL config must be a dictionary")]

        for name, config in etl_config.items():
            if not isinstance(config, dict):
                errors.append(ValidationError(f"etl.{name}", "ETL config must be a dictionary"))
                continue

            # Check required fields
            if "input" not in config:
                errors.append(
                    ValidationError(f"etl.{name}.input", "Missing required field 'input'")
                )
            if "output" not in config:
                errors.append(
                    ValidationError(f"etl.{name}.output", "Missing required field 'output'")
                )

            # Validate depends_on is a list
            if "depends_on" in config and not isinstance(config["depends_on"], list):
                errors.append(ValidationError(f"etl.{name}.depends_on", "must be a list"))

        return errors

    def _validate_training(self, training_config: Any) -> List[ValidationError]:
        """Validate training configuration."""
        errors = []

        if not isinstance(training_config, dict):
            return [ValidationError("train", "Training config must be a dictionary")]

        # Validate models if present
        if "models" in training_config:
            models = training_config["models"]
            if not isinstance(models, list):
                errors.append(ValidationError("train.models", "must be a list"))
            else:
                for i, model in enumerate(models):
                    if not isinstance(model, dict):
                        errors.append(ValidationError(f"train.models[{i}]", "must be a dictionary"))
                    elif "type" not in model:
                        errors.append(
                            ValidationError(
                                f"train.models[{i}].type", "Missing required field 'type'"
                            )
                        )

        # Validate ensemble if present
        if "ensemble" in training_config:
            ensemble = training_config["ensemble"]
            if isinstance(ensemble, dict):
                if "method" not in ensemble:
                    errors.append(
                        ValidationError("train.ensemble.method", "Missing required field 'method'")
                    )

        # Warning for comparison mode (multiple models without ensemble)
        if "models" in training_config and isinstance(training_config["models"], list):
            num_models = len(training_config["models"])
            if num_models > 1 and "ensemble" not in training_config:
                logger.warning(
                    f"Multiple models ({num_models}) configured without ensemble section. "
                    "Comparison mode will be activated - each model will be trained and "
                    "evaluated independently. Add an 'ensemble' section to enable ensemble mode."
                )

        return errors

    def _validate_evaluation(self, eval_config: Any) -> List[ValidationError]:
        """Validate evaluation configuration."""
        errors = []

        if not isinstance(eval_config, dict):
            return [ValidationError("evaluation", "Evaluation config must be a dictionary")]

        # Validate threshold if present
        if "threshold" in eval_config:
            threshold = eval_config["threshold"]
            if not isinstance(threshold, (int, float)):
                errors.append(ValidationError("evaluation.threshold", "must be a number"))
            elif not 0 <= threshold <= 1:
                errors.append(ValidationError("evaluation.threshold", "must be between 0 and 1"))

        return errors

    def _validate_inference(self, inf_config: Any) -> List[ValidationError]:
        """Validate inference configuration."""
        errors = []

        if not isinstance(inf_config, dict):
            return [ValidationError("infer", "Inference config must be a dictionary")]

        # Validate threshold if present
        if "threshold" in inf_config:
            threshold = inf_config["threshold"]
            if not isinstance(threshold, (int, float)):
                errors.append(ValidationError("infer.threshold", "must be a number"))
            elif not 0 <= threshold <= 1:
                errors.append(ValidationError("infer.threshold", "must be between 0 and 1"))

        # Validate output_format if present
        if "output_format" in inf_config:
            fmt = inf_config["output_format"]
            if not isinstance(fmt, str) or fmt not in ("csv", "parquet"):
                errors.append(
                    ValidationError(
                        "infer.output_format", "output_format must be 'csv' or 'parquet'"
                    )
                )

        # Validate output_include_input if present
        if "output_include_input" in inf_config:
            val = inf_config["output_include_input"]
            if not isinstance(val, bool):
                errors.append(
                    ValidationError(
                        "infer.output_include_input", "output_include_input must be a boolean"
                    )
                )

        # Validate output_columns if present (must be a list of strings)
        if "output_columns" in inf_config:
            cols = inf_config["output_columns"]
            if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
                errors.append(
                    ValidationError(
                        "infer.output_columns", "output_columns must be a list of strings"
                    )
                )

        return errors

    def _validate_eda(self, eda_config: Any) -> List[ValidationError]:
        """Validate EDA configuration."""
        errors = []

        if not isinstance(eda_config, dict):
            return [ValidationError("eda", "EDA config must be a dictionary")]

        return errors


def validate_config_file(path: str) -> Tuple[bool, List[ValidationError]]:
    """
    Convenience function to validate a configuration file.

    Args:
        path: Path to the YAML configuration file

    Returns:
        Tuple[bool, List[ValidationError]]: (is_valid, errors)
    """
    validator = ConfigValidator()
    try:
        errors = validator.validate_file(path)
        return len(errors) == 0, errors
    except ConfigurationError as e:
        return False, [ValidationError("file", str(e))]
