"""
Validate command implementation for Energizados CLI.

This module implements the 'validate' command functionality to
validate YAML configuration files.
"""

from pathlib import Path
from typing import Any, Dict, List

from energizados.core.exceptions import ConfigurationError


class ValidationResult:
    """Validation result with errors and warnings."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def is_valid(self) -> bool:
        """Returns True if there are no errors."""
        return len(self.errors) == 0

    def add_error(self, message: str):
        """Adds an error."""
        self.errors.append(message)

    def add_warning(self, message: str):
        """Adds a warning."""
        self.warnings.append(message)

    def add_info(self, message: str):
        """Adds information."""
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

    # Show results
    if verbose:
        _print_validation_results(result, merged_config)

    if not result.is_valid():
        raise ConfigurationError(f"Validation failed with {len(result.errors)} errors", str(config_paths))

    return result


def _validate_project_section(config: Dict[str, Any], result: ValidationResult):
    """Validates the project section."""
    if "project" not in config:
        result.add_warning("'project' section not found (optional)")
        return

    project = config["project"]
    if "name" not in project:
        result.add_warning("project.name not defined")
    else:
        result.add_info(f"Project: {project['name']}")


def _validate_etl_section(config: Dict[str, Any], result: ValidationResult):
    """Validates the etls section (multiple ETLs with dependencies)."""
    if "etls" not in config:
        result.add_info("'etls' section not present in this config (skipping ETL validation)")
        return

    etls = config["etls"]
    if not isinstance(etls, dict):
        result.add_error("'etls' section must be a dictionary")
        return

    if not etls:
        result.add_warning("'etls' section is empty")
        return

    # Validate each ETL
    for etl_name, etl_config in etls.items():
        if not isinstance(etl_config, dict):
            result.add_error(f"ETL '{etl_name}': must be a dictionary")
            continue

        # Check required fields
        if "input" not in etl_config:
            result.add_error(f"ETL '{etl_name}': required field 'input'")

        if "output" not in etl_config:
            result.add_error(f"ETL '{etl_name}': required field 'output'")

        if "depends_on" not in etl_config:
            result.add_warning(f"ETL '{etl_name}': field 'depends_on' not found, using []")

        # custom_class is mandatory
        if "custom_class" not in etl_config:
            result.add_error(f"ETL '{etl_name}': must specify 'custom_class'")
        else:
            _validate_class_reference(etl_config["custom_class"], result)

        enabled = etl_config.get("enabled", True)
        result.add_info(f"ETL '{etl_name}': {'enabled' if enabled else 'disabled'}")


def _validate_inference_section(config: Dict[str, Any], result: ValidationResult):
    """Validates the inference section."""
    if "inference" not in config:
        result.add_warning("'inference' section not found (optional)")
        return

    inf = config["inference"]
    if not isinstance(inf, dict):
        result.add_error("'inference' section must be a dictionary")
        return

    if inf.get("enabled", False):
        if "input_path" not in inf:
            result.add_warning("inference.input_path not defined")

        if "output_path" not in inf:
            result.add_warning("inference.output_path not defined")

        if "custom_class" in inf:
            _validate_class_reference(inf["custom_class"], result)

        result.add_info("Inference: enabled")
    else:
        result.add_info("Inference: disabled")


def _validate_training_section(config: Dict[str, Any], result: ValidationResult):
    """Validates the training section."""
    if "training" not in config:
        result.add_info("'training' section not present in this config (skipping training validation)")
        return

    training = config["training"]
    if not isinstance(training, dict):
        result.add_error("'training' section must be a dictionary")
        return

    # Check model: config nests it as training.model.type
    model_config = training.get("model", {})
    has_model_type = "type" in model_config
    has_custom = "custom_class" in model_config or "custom_class" in training

    if not has_model_type and not has_custom:
        result.add_warning("training: no 'model.type' or 'model.custom_class' defined")

    if has_model_type:
        valid_models = [
            "lightgbm",
            "lgbm",
            "catboost",
            "cat",
            "neural_network",
            "nn",
            "lstm",
            "simple_trend",
            "simple_constant",
        ]
        model_type = model_config["type"]
        if model_type not in valid_models:
            result.add_warning(f"training.model.type unknown: {model_type}")
        else:
            result.add_info(f"Model: {model_type}")

    if "custom_class" in model_config:
        _validate_class_reference(model_config["custom_class"], result)
    elif "custom_class" in training:
        _validate_class_reference(training["custom_class"], result)

    # Check split parameters
    if "test_size" in training:
        test_size = training["test_size"]
        if not 0 < test_size < 1:
            result.add_warning(f"training.test_size must be between 0 and 1, got: {test_size}")

    if "val_size" in training:
        val_size = training["val_size"]
        if not 0 < val_size < 1:
            result.add_warning(f"training.val_size must be between 0 and 1, got: {val_size}")

    # Check sampling
    if "sampling" in training:
        sampling = training["sampling"]
        if isinstance(sampling, dict):
            valid_methods = ["over", "under", "none"]
            method = sampling.get("method")
            if method and method not in valid_methods:
                result.add_warning(f"training.sampling.method invalid: {method}")


def _validate_evaluation_section(config: Dict[str, Any], result: ValidationResult):
    """Validates the evaluation section."""
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

        result.add_info(f"Evaluation: {'enabled' if eval_config.get('enabled', True) else 'disabled'}")


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


def _print_validation_results(result: ValidationResult, config: Dict[str, Any]):
    """Prints the validation results."""
    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)

    if result.info:
        print("\n📋 Information:")
        for info in result.info:
            print(f"  • {info}")

    if result.warnings:
        print(f"\n⚠️  Warnings ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"  • {warning}")

    if result.errors:
        print(f"\n❌ Errors ({len(result.errors)}):")
        for error in result.errors:
            print(f"  • {error}")

    print("\n" + "=" * 60)
    if result.is_valid():
        print("✓ VALID CONFIGURATION")
    else:
        print("✗ INVALID CONFIGURATION")
    print("=" * 60)
