"""
Run command implementation for Energizados CLI.

This module implements the 'run' command functionality to execute
pipelines from YAML configuration.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from energizados.core.exceptions import ConfigurationError, PipelineError
from energizados.core.pipeline import ConfigPipelineBuilder


def merge_configs(config_paths: List[str]) -> Dict[str, Any]:
    """
    Merges multiple configuration files into one.

    The strategy is "last wins": if there are duplicate keys,
    the last file overwrites the previous values.

    Args:
        config_paths: List of paths to YAML files

    Returns:
        Dict: Combined configuration

    Raises:
        ConfigurationError: If any file does not exist or has format errors
    """
    merged_config = {}

    for config_path in config_paths:
        config_file = Path(config_path)
        if not config_file.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}", config_path)

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                if config is None:
                    config = {}
                merged_config.update(config)
                logger = __import__("logging").getLogger(__name__)
                logger.debug(f"Configuration loaded from: {config_path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing YAML in {config_path}: {e}", config_path)

    return merged_config


def execute_pipeline(config_paths: List[str]) -> Dict[str, Any]:
    """
    Executes the complete pipeline from YAML configuration(s).

    Args:
        config_paths: List of paths to YAML configuration files

    Returns:
        Dict: Final context with pipeline results

    Raises:
        ConfigurationError: If there are configuration errors
        PipelineError: If there are errors during execution
    """
    # Merge configurations
    merged_config = merge_configs(config_paths)

    # Build pipeline from configuration
    builder = ConfigPipelineBuilder(config=merged_config)
    pipeline = builder.build()

    # Execute pipeline
    result = pipeline.run()

    return result


def execute_step(config_paths: List[str], step_name: str) -> Dict[str, Any]:
    """
    Executes a single step of the pipeline.

    Args:
        config_paths: List of paths to YAML configuration files
        step_name: Name of the step to execute

    Returns:
        Dict: Updated context after the step

    Raises:
        ConfigurationError: If there are configuration errors
        PipelineError: If the step does not exist or there are errors during execution
    """
    # Step name mapping
    step_map = {
        "etl": "ETLStep",
        "split": "SplitStep",
        "training": "TrainingStep",
        "evaluation": "EvaluationStep",
        "inference": "InferenceStep",
    }

    if step_name not in step_map:
        raise PipelineError(f"Unknown step: {step_name}. Available steps: {list(step_map.keys())}")

    # Merge configurations
    merged_config = merge_configs(config_paths)

    # Build complete pipeline
    builder = ConfigPipelineBuilder(config=merged_config)
    pipeline = builder.build()

    # Filter only the requested step
    step_class_name = step_map[step_name]
    filtered_steps = [s for s in pipeline.steps if s.__class__.__name__ == step_class_name]

    if not filtered_steps:
        raise PipelineError(f"The step '{step_name}' is not configured or not enabled")

    # Replace pipeline steps
    pipeline.steps = filtered_steps

    # Execute only the selected step
    result = pipeline.run()

    return result


def execute_etl(config_paths: List[str], etl_name: str = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Executes ETLs from configuration.

    Supports:
    - Execute all ETLs
    - Execute a specific ETL (and its dependencies)
    - Show execution plan without executing (dry-run)

    Args:
        config_paths: List of paths to YAML configuration files
        etl_name: Name of the specific ETL to execute (None = all)
        dry_run: If True, only shows the execution plan

    Returns:
        Dict: Results of the executed ETLs

    Raises:
        ConfigurationError: If there are configuration errors
        PipelineError: If there are errors during execution
    """
    from energizados.etl.orchestrator import ETLOrchestrator

    # Merge configurations
    merged_config = merge_configs(config_paths)

    # Verify if there is ETL configuration
    etl_configs = merged_config.get("etls")

    if not etl_configs:
        raise PipelineError("No ETLs configured. Use the 'etls:' section to configure multiple ETLs.")

    # If a specific ETL is requested, filter its dependencies
    if etl_name:
        if etl_name not in etl_configs:
            raise PipelineError(f"ETL '{etl_name}' not found. Available ETLs: {list(etl_configs.keys())}")

        # Filter only necessary ETLs (etl_name + dependencies)
        filtered_configs = _get_etl_with_dependencies(etl_configs, etl_name)
        orchestrator = ETLOrchestrator(filtered_configs)
    else:
        orchestrator = ETLOrchestrator(etl_configs)

    # Show execution plan
    print(orchestrator.get_execution_plan())

    if dry_run:
        print("\n--dry-run: ETLs were not executed --")
        return {}

    # Execute ETLs
    results = orchestrator.run()

    return results


def _get_etl_with_dependencies(etl_configs: Dict[str, Dict], etl_name: str) -> Dict[str, Dict]:
    """
    Gets an ETL and all its dependencies recursively.

    Args:
        etl_configs: Configuration of all ETLs
        etl_name: Name of the target ETL

    Returns:
        Dict with the ETL and its dependencies
    """
    result = {}
    visited = set()

    def collect_deps(name: str):
        if name in visited:
            return
        if name not in etl_configs:
            raise PipelineError(f"ETL '{name}' not found in configuration")

        visited.add(name)
        config = etl_configs[name]

        # First collect dependencies
        for dep in config.get("depends_on", []):
            collect_deps(dep)

        # Then add this ETL
        result[name] = config

    collect_deps(etl_name)
    return result


def show_etl_plan(config_paths: List[str]) -> str:
    """
    Shows the ETL execution plan without executing them.

    Args:
        config_paths: List of paths to YAML configuration files

    Returns:
        str: Formatted execution plan

    Raises:
        ConfigurationError: If there are configuration errors
    """
    return execute_etl(config_paths, dry_run=True)
