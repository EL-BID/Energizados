"""
Validate command implementation for Energizados CLI.

This module implements the 'validate' command functionality to
validate YAML configuration files.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from energizados.cli.ui import console
from energizados.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ValidationResult:
    """Container for configuration validation results.

    This class stores errors, warnings, and informational messages
    generated during configuration validation. It provides methods
    to add messages and check if the configuration is valid.

    Attributes:
        errors: List of error messages that make the configuration invalid.
        warnings: List of warning messages for potential issues.
        info: List of informational messages about the configuration.

    Example:
        >>> result = ValidationResult()
        >>> result.add_info("Project name: my_project")
        >>> result.add_warning("Optional section not found")
        >>> result.is_valid()
        True
    """

    def __init__(self) -> None:
        """Initializes an empty ValidationResult."""
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def is_valid(self) -> bool:
        """Checks if the configuration is valid.

        Returns:
            True if there are no errors, False otherwise.
        """
        return len(self.errors) == 0

    def add_error(self, message: str) -> None:
        """Adds an error message to the result.

        Args:
            message: The error message to add.
        """
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """Adds a warning message to the result.

        Args:
            message: The warning message to add.
        """
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        """Adds an informational message to the result.

        Args:
            message: The informational message to add.
        """
        self.info.append(message)


def validate_config(config_paths: List[str], verbose: bool = False) -> ValidationResult:
    """
    Validates one or more YAML configuration files.

    Args:
        config_paths: List of paths to configuration files
        verbose: If True, shows complete details

    Returns:
        ValidationResult: Validation result

    Raises:
        ConfigurationError: If there are critical configuration errors
    """
    from energizados.cli.run import merge_configs

    result = ValidationResult()

    # Validate that each file exists before merging
    for config_path in config_paths:
        config_file = Path(config_path)
        if not config_file.exists():
            result.add_error(f"File not found: {config_path}")
            raise ConfigurationError(f"File not found: {config_path}", config_path)

    # Merge configurations (the function also validates YAML format)
    try:
        merged_config = merge_configs(config_paths)
    except Exception as e:
        result.add_error(f"Error merging configurations: {e}")
        raise

    if not merged_config:
        result.add_error("Combined configuration empty")
        raise ConfigurationError("Combined configuration empty", str(config_paths))

    # Validate sections
    _validate_project_section(merged_config, result)
    _validate_etl_section(merged_config, result)
    _validate_training_section(merged_config, result)
    _validate_evaluation_section(merged_config, result)
    _validate_inference_section(merged_config, result)

    # Second pass: JSON Schema validation (optional, if available)
    try:
        from energizados.core.schemas.config_validator import ConfigValidator

        validator = ConfigValidator()
        schema_errors = validator.validate_config(merged_config, str(config_paths))

        if schema_errors:
            for error in schema_errors:
                result.add_error(f"Schema validation: {error}")

        if schema_errors and not result.errors:
            # If only schema errors, log debug message
            logger.debug(f"JSON Schema validation found {len(schema_errors)} errors")

    except Exception as e:
        # If ConfigValidator fails (e.g., missing dependencies), just log debug
        logger.debug(f"JSON Schema validation skipped: {e}")

    # Show results
    if verbose:
        _print_validation_results(result, merged_config)

    if not result.is_valid():
        raise ConfigurationError(
            f"Validation failed with {len(result.errors)} errors", str(config_paths)
        )

    return result


def _validate_project_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the project section of the configuration.

    Checks for the optional 'project' section and validates its
    'name' field if present.

    Args:
        config: The full configuration dictionary.
        result: ValidationResult object to store validation messages.
    """
    if "project" not in config:
        result.add_warning("'project' section not found (optional)")
        return

    project = config["project"]
    if "name" not in project:
        result.add_warning("project.name not defined")
    else:
        result.add_info(f"Project: {project['name']}")


def _validate_etl_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the etls section (multiple ETLs with dependencies).

    Validates each ETL configuration including required fields:
    - input: Input data source(s)
    - output: Output path
    - custom_class: Fully qualified class name for the ETL
    - depends_on: Optional list of ETL dependencies

    Args:
        config: The full configuration dictionary.
        result: ValidationResult object to store validation messages.
    """
    if "etl" not in config:
        result.add_info("'etl' section not present in this config (skipping ETL validation)")
        return

    etls = config["etl"]
    if not isinstance(etls, dict):
        result.add_error("'etl' section must be a dictionary")
        return

    if not etls:
        result.add_warning("'etl' section is empty")
        return

    from energizados._version import SCHEMA_VERSION_KEY

    # Validate each ETL (skip reserved metadata keys)
    for etl_name, etl_config in etls.items():
        if etl_name == SCHEMA_VERSION_KEY:
            continue
        if not isinstance(etl_config, dict):
            result.add_error(f"ETL '{etl_name}': must be a dictionary")
            continue

        # Check required fields
        if "input" not in etl_config:
            result.add_error(f"ETL '{etl_name}': required field 'input'")

        # 'output' is optional: ETL_SCHEMA only requires 'input', and cleanup
        # ETLs (e.g. CleanFilesETL) legitimately produce no output file. Warn for
        # other classes to catch accidental omissions without blocking them.
        if "output" not in etl_config:
            custom_class = etl_config.get("custom_class", "")
            if custom_class.endswith("CleanFilesETL"):
                result.add_info(f"ETL '{etl_name}': no 'output' (ok for CleanFilesETL)")
            else:
                result.add_warning(f"ETL '{etl_name}': no 'output' defined")

        if "depends_on" not in etl_config:
            result.add_warning(f"ETL '{etl_name}': field 'depends_on' not found, using []")

        # custom_class is mandatory
        if "custom_class" not in etl_config:
            result.add_error(f"ETL '{etl_name}': must specify 'custom_class'")
            result.add_info("Hint: Use 'energizados.etl.pipeline.SourceETL' or a custom class path")
        else:
            _validate_class_reference(etl_config["custom_class"], result)

        enabled = etl_config.get("enabled", True)
        result.add_info(f"ETL '{etl_name}': {'enabled' if enabled else 'disabled'}")


def _validate_inference_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the inference section of the configuration.

    Checks for required fields when inference is enabled:
    - input_path: Path to input data
    - output_predictions_path: Path for output results (output_path is a deprecated alias)
    - custom_class: Optional custom inference class

    Args:
        config: The full configuration dictionary.
        result: ValidationResult object to store validation messages.
    """
    if "infer" not in config:
        result.add_warning("'infer' section not found (optional)")
        return

    inf = config["infer"]
    if not isinstance(inf, dict):
        result.add_error("'infer' section must be a dictionary")
        return

    if inf.get("enabled", False):
        if "input_path" not in inf:
            result.add_warning("inference.input_path not defined")

        has_new = "output_predictions_path" in inf
        has_old = "output_path" in inf
        if not has_new and not has_old:
            result.add_warning("inference.output_predictions_path not defined")
        elif has_old and not has_new:
            result.add_warning("inference.output_path is deprecated; use output_predictions_path")

        if "custom_class" in inf:
            _validate_class_reference(inf["custom_class"], result)

        result.add_info("Inference: enabled")
    else:
        result.add_info("Inference: disabled")


def _validate_training_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the training section of the configuration.

    Validates model type, custom classes, split parameters,
    and sampling configuration.

    Args:
        config: The full configuration dictionary.
        result: ValidationResult object to store validation messages.
    """
    if "train" not in config:
        result.add_info("'train' section not present in this config (skipping training validation)")
        return

    training = config["train"]
    if not isinstance(training, dict):
        result.add_error("'train' section must be a dictionary")
        return

    # Check for legacy model: format (deprecated)
    if "model" in training:
        result.add_warning("train: 'model:' key is deprecated. Use 'models:' list format instead.")

    # Check for legacy train.sampling (moved to train.models[].sampling)
    if "sampling" in training:
        result.add_warning(
            "train: 'sampling' at train root is ignored. "
            "Move it under 'train.models[].sampling' to apply to each model."
        )

    # Check models list (new format)
    models = training.get("models", [])
    if not models:
        result.add_warning(
            "train: 'models:' list is empty or not defined. At least one model is required."
        )
    else:
        if not isinstance(models, list):
            result.add_error("training: 'models' must be a list")
            return

        # Derive canonical model types from the JSON schema enum so this list
        # cannot drift from ModelRegistry / MODEL_CONFIG_SCHEMA (previously a
        # hardcoded literal that was missing "xgboost"/"xgb"). Aliases accepted
        # by the training step are added explicitly (they are not in the enum).
        from energizados.core.schemas.schemas import MODEL_CONFIG_SCHEMA

        valid_models = list(MODEL_CONFIG_SCHEMA["properties"]["type"]["enum"])
        valid_models.extend(["lgbm", "cat", "xgb", "nn"])

        for i, model_config in enumerate(models):
            if not isinstance(model_config, dict):
                result.add_error(f"training.models[{i}]: must be a dictionary")
                continue

            has_model_type = "type" in model_config
            has_custom = "custom_class" in model_config

            if not has_model_type and not has_custom:
                result.add_warning(f"training.models[{i}]: no 'type' or 'custom_class' defined")

            if has_model_type:
                model_type = model_config["type"]
                if model_type not in valid_models:
                    result.add_warning(f"training.models[{i}].type unknown: {model_type}")
                else:
                    result.add_info(f"Model {i}: {model_type}")

            if has_custom:
                _validate_class_reference(model_config["custom_class"], result)

    # Check split parameters (test_size/val_size live under train.split, not train)
    split_config = training.get("split", {})
    if isinstance(split_config, dict):
        if "test_size" in split_config:
            test_size = split_config["test_size"]
            if not 0 < test_size < 1:
                result.add_warning(
                    f"train.split.test_size must be between 0 and 1, got: {test_size}"
                )

        if "val_size" in split_config:
            val_size = split_config["val_size"]
            if not 0 < val_size < 1:
                result.add_warning(f"train.split.val_size must be between 0 and 1, got: {val_size}")

    # Warn about unknown keys inside unlabeled_negatives (typo guard).
    # Checks train.split and the legacy top-level split section (mirrors the
    # PipelineDirector fallback).
    from energizados.core.schemas.schemas import SPLIT_SCHEMA

    known_unlabeled_keys = set(
        SPLIT_SCHEMA["properties"]["unlabeled_negatives"]["properties"].keys()
    )
    for split_name, split_cfg in [
        ("train.split", training.get("split")),
        ("split", config.get("split")),
    ]:
        if not isinstance(split_cfg, dict):
            continue
        unlabeled = split_cfg.get("unlabeled_negatives")
        if not isinstance(unlabeled, dict):
            continue
        unknown_keys = [k for k in unlabeled if k not in known_unlabeled_keys]
        if unknown_keys:
            result.add_warning(
                f"{split_name}.unlabeled_negatives: unknown key(s) {unknown_keys}. "
                f"Known keys: {sorted(known_unlabeled_keys)}. "
                "Check for typos (e.g. 'soruce_path' instead of 'source_path')."
            )

    # Check sampling (lives under train.models[].sampling, not train.sampling)
    if isinstance(models, list):
        valid_methods = ["oversample", "undersample", "smotetomek", "none"]
        for i, model_config in enumerate(models):
            if not isinstance(model_config, dict):
                continue
            sampling = model_config.get("sampling")
            if isinstance(sampling, dict):
                method = sampling.get("method")
                if method and method not in valid_methods:
                    result.add_warning(f"training.models[{i}].sampling.method invalid: {method}")


def _validate_evaluation_section(config: Dict[str, Any], result: ValidationResult) -> None:
    """Validates the evaluation section of the configuration.

    Checks for valid metric names and evaluation settings.

    Args:
        config: The full configuration dictionary.
        result: ValidationResult object to store validation messages.
    """
    if "evaluation" not in config:
        result.add_warning("'evaluation' section not found (optional)")
        return

    eval_config = config["evaluation"]
    if not isinstance(eval_config, dict):
        result.add_error("'evaluation' section must be a dictionary")
        return

    if eval_config.get("enabled", True):
        if "metrics" in eval_config:
            metrics = eval_config["metrics"]
            if not isinstance(metrics, list):
                result.add_error("evaluation.metrics must be a list")
            else:
                valid_metrics = [
                    "auc",
                    "precision",
                    "recall",
                    "f1",
                    "confusion_matrix",
                    "cumulative_gains",
                ]
                for metric in metrics:
                    if metric not in valid_metrics:
                        result.add_warning(f"Unknown metric: {metric}")

        result.add_info(
            f"Evaluation: {'enabled' if eval_config.get('enabled', True) else 'disabled'}"
        )


def _validate_class_reference(class_path: str, result: ValidationResult):
    """
    Validates a class reference by format and allowlist only (no import).

    Importing during validation is avoided because it executes arbitrary
    module-level code from user-defined classes. Format and prefix checks
    are sufficient to catch configuration typos at validate time.

    Args:
        class_path: Full path of the class (eg: "module.submodule.ClassName")
        result: Validation result to add errors
    """
    from energizados.core.utils.import_utils import ALLOWED_PREFIXES

    if not class_path or "." not in class_path:
        result.add_error(f"Invalid class reference (expected 'module.ClassName'): {class_path}")
        return

    parts = class_path.rsplit(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        result.add_error(f"Invalid class reference format: {class_path}")
        return

    if not any(class_path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        result.add_warning(
            f"Class '{class_path}' does not match allowed prefixes {ALLOWED_PREFIXES}. "
            "Custom local classes are fine if running from the project directory."
        )
    else:
        result.add_info(f"Class reference format valid: {class_path}")


def _print_validation_results(result: ValidationResult, config: Dict[str, Any]) -> None:
    """Prints the validation results to stdout.

    Displays information, warnings, and errors in a formatted
    output with visual indicators using Rich Table and Panel.

    Args:
        result: ValidationResult object containing messages.
        config: The configuration dictionary (for context).
    """
    from rich.panel import Panel
    from rich.table import Table

    # Create the results table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Status", style="", width=8)
    table.add_column("Category", style="cyan", width=12)
    table.add_column("Message", style="white")

    # Add info messages
    if result.info:
        for info in result.info:
            table.add_row("[bold cyan]⚡[/]", "Info", info)

    # Add warnings
    if result.warnings:
        for warning in result.warnings:
            table.add_row("[bold yellow]⚠[/]", "Warning", warning)

    # Add errors
    if result.errors:
        for error in result.errors:
            table.add_row("[bold red]✗[/]", "Error", error)

    # Create the summary message
    if result.is_valid():
        summary_message = "[bold green]✓ VALID CONFIGURATION[/]"
    else:
        summary_message = "[bold red]✗ INVALID CONFIGURATION[/]"

    # Wrap in a panel and print
    panel = Panel(
        table,
        title="[bold]Validation Results[/]",
        title_align="left",
        border_style="cyan",
    )
    console.print("\n")
    console.print(panel)
    console.print(f"\n{summary_message}\n")
