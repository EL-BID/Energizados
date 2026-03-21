"""
Run command implementation for Energizados CLI.

This module implements the 'run' command functionality to execute
pipelines from YAML configuration.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from rich.panel import Panel

from energizados.cli.ui import console
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
            raise ConfigurationError(
                f"Error parsing YAML in {config_path}: {e}", config_path
            ) from e

    return merged_config


def execute_pipeline(config_paths: List[str], run_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes the complete pipeline from YAML configuration(s).

    Args:
        config_paths: List of paths to YAML configuration files
        run_name: Optional custom run directory name

    Returns:
        Dict: Final context with pipeline results

    Raises:
        ConfigurationError: If there are configuration errors
        PipelineError: If there are errors during execution
    """
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    # Merge configurations
    merged_config = merge_configs(config_paths)

    # Build pipeline (don't run yet)
    builder = ConfigPipelineBuilder(
        config=merged_config, config_paths=list(config_paths), run_name=run_name
    )
    pipeline = builder.build()

    # Define phases for each step type
    # Note: ETLStep uses dynamic phases based on ETL names (handled in on_step_start)
    STEP_PHASES = {
        "SplitStep": ["analyzing", "splitting", "saving"],
        "TrainingStep": ["loading", "feature_engineering", "training", "evaluation"],
        "EvaluationStep": ["evaluating", "generating_report"],
        "InferenceStep": ["loading_model", "predicting", "saving"],
        "EDAStep": ["analyzing_data", "generating_report"],
    }

    # Execute with Rich progress display
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        expand=True,
    ) as progress:
        total_steps = len(pipeline.steps)
        config_names = ",".join(Path(p).stem for p in config_paths)
        main_task = progress.add_task(f"Running: {config_names}", total=total_steps)

        # Track step start time for elapsed time calculation
        step_start_time = None
        # Track current sub-task for phase updates
        current_sub_task = None
        step_task_ids = {}  # Map step_name -> task_id
        step_phases = {}  # Map step_name -> list of phases
        # For dynamic steps (like ETL), track the total_phases passed in callback
        step_total_phases = {}  # Map step_name -> total_phases from callback

        def on_step_start(name, i, total):
            nonlocal step_start_time, current_sub_task
            step_start_time = time.time()

            # Remove previous sub-task if exists
            if current_sub_task is not None:
                try:
                    progress.remove_task(current_sub_task)
                except Exception:  # nosec: Silently ignore cleanup errors
                    pass

            # Get phases for this step type (None for ETLStep - handled dynamically)
            phases = STEP_PHASES.get(name)
            step_phases[name] = phases if phases else []
            step_total_phases[name] = None  # Will be set by first phase callback
            # Only mark as created if we actually create the sub-task
            # For dynamic steps, sub-task is created by first phase_update
            step_task_ids[name] = None  # None means not created yet

            # For non-ETL steps, create sub-task immediately with known phases
            if phases:
                current_sub_task = progress.add_task(
                    f"[yellow]▶ {name}[/]",
                    total=len(phases),
                    parent=main_task,
                )
                step_task_ids[name] = current_sub_task
                current_sub_task = current_sub_task

            progress.update(
                main_task,
                description=f"[cyan][{i}/{total}] {name}[/]",
                completed=i - 1,
            )

        def on_phase_update(step_name, phase, pct, total_phases):
            # For ETLStep with dynamic phases, create/update sub-task dynamically
            try:
                if step_name == "ETLStep" and total_phases is not None:
                    # ETLStep: phase is the ETL name, total_phases tells us total count
                    task_id = step_task_ids.get(step_name)
                    if task_id is None:
                        # First ETL - create sub-task
                        new_task = progress.add_task(
                            f"[yellow]▶ {phase}[/]",
                            total=total_phases,
                            parent=main_task,
                        )
                        step_task_ids[step_name] = new_task
                        step_total_phases[step_name] = total_phases

                    # Find current ETL index
                    task_id = step_task_ids.get(step_name)
                    if task_id is not None:
                        # Get all phases for this step to find current index
                        phases = step_phases.get(step_name, [])
                        # Track ETL indices dynamically
                        if phase not in phases:
                            phases.append(phase)
                            step_phases[step_name] = phases

                        phase_idx = len(phases) - 1  # Current ETL is at this index
                        completed = phase_idx + (pct / 100)

                        progress.update(
                            task_id,
                            completed=completed,
                            description=f"[yellow]▶ {phase}[/]",
                        )
                else:
                    # Standard step with predefined phases
                    phases = step_phases.get(step_name, [])
                    phase_idx = phases.index(phase) if phase in phases else -1
                    if phase_idx >= 0:
                        completed = phase_idx + (pct / 100)
                        task_id = step_task_ids.get(step_name)
                        if task_id is not None:
                            progress.update(
                                task_id,
                                completed=completed,
                                description=f"[yellow]▶ {step_name}[/] — {phase} ({pct}%)",
                            )
            except Exception:  # nosec: Silently ignore callback errors
                pass

        def on_step_complete(name, i, total):
            nonlocal current_sub_task
            elapsed = time.time() - step_start_time if step_start_time else 0

            # Mark sub-task as complete (if it was created)
            task_id = step_task_ids.get(name)
            if task_id is not None:
                phases = step_phases.get(name, [])
                try:
                    progress.update(
                        task_id, completed=len(phases), description=f"[green]✓ {name}[/]"
                    )
                except Exception:  # nosec: Silently ignore cleanup errors
                    pass

            progress.update(
                main_task,
                description=f"[green][{i}/{total}] {name}[/]",
                completed=i,
            )

            # Print summary panel after step completes
            console.print(
                Panel(
                    f"[bold]{name}[/]\n\n[green]✓[/] Completed in {elapsed:.2f}s",
                    border_style="green",
                )
            )

            current_sub_task = None

        def on_step_error(name, err):
            progress.update(main_task, description=f"[red][✗] {name}[/]")

        pipeline.on_step_start = on_step_start
        pipeline.on_step_complete = on_step_complete
        pipeline.on_step_error = on_step_error
        pipeline.on_phase_update = on_phase_update

        # Run the pipeline
        result = pipeline.run()

    # Post-run tasks (config copy, index HTML) - these need to be called manually
    # since we called pipeline.run() directly instead of builder.run()
    if builder._director.run_manager._run_dir is not None:
        builder._copy_configs_to_run_dir()
        builder._generate_index_html()

    return result


def execute_step(
    config_paths: List[str], step_name: str, run_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a single step of the pipeline.

    Args:
        config_paths: List of paths to YAML configuration files
        step_name: Name of the step to execute
        run_name: Optional custom run directory name

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
        "train": "TrainingStep",
        "evaluation": "EvaluationStep",
        "infer": "InferenceStep",
    }

    if step_name not in step_map:
        raise PipelineError(f"Unknown step: {step_name}. Available steps: {list(step_map.keys())}")

    # Merge configurations
    merged_config = merge_configs(config_paths)

    # Build complete pipeline
    builder = ConfigPipelineBuilder(
        config=merged_config, config_paths=list(config_paths), run_name=run_name
    )
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

    # Post-run tasks if a run dir was generated
    if builder._run_dir is not None:
        builder._copy_configs_to_run_dir()
        builder._generate_index_html()

    return result


def execute_etl(
    config_paths: List[str], etl_name: str = None, dry_run: bool = False
) -> Dict[str, Any]:
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
    etl_configs = merged_config.get("etl")

    if not etl_configs:
        raise PipelineError(
            "No ETLs configured. Use the 'etl:' section to configure multiple ETLs."
        )

    # If a specific ETL is requested, filter its dependencies
    if etl_name:
        if etl_name not in etl_configs:
            raise PipelineError(
                f"ETL '{etl_name}' not found. Available ETLs: {list(etl_configs.keys())}"
            )

        # Filter only necessary ETLs (etl_name + dependencies)
        filtered_configs = _get_etl_with_dependencies(etl_configs, etl_name)
        orchestrator = ETLOrchestrator(filtered_configs)
    else:
        orchestrator = ETLOrchestrator(etl_configs)

    if dry_run:
        console.print(orchestrator.get_execution_plan())
        console.print("\n[dim]--dry-run: ETLs were not executed --[/]")
        return {}

    # Execute ETLs with Rich progress display
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    results = {}
    completed_etls = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        total_etls = len(orchestrator.etl_configs)
        main_task = progress.add_task("ETL Pipeline", total=total_etls)

        # Track ETL start time for elapsed time calculation
        etl_start_time = None

        def on_etl_start(name, idx, total):
            nonlocal etl_start_time
            etl_start_time = time.time()
            progress.update(main_task, description=f"ETL Pipeline — [yellow]{name}[/]")

        def on_etl_complete(name, rows):
            elapsed = time.time() - etl_start_time if etl_start_time else 0
            completed_etls.append((name, rows))
            progress.advance(main_task)
            progress.update(
                main_task, description=f"ETL Pipeline — [green]✓ {name}[/] ({rows:,} rows)"
            )
            # Print summary panel after ETL completes
            # Get output path from ETL config if available
            output_path = "N/A"
            if name in orchestrator.etl_configs:
                output_path = orchestrator.etl_configs[name].get("output", "N/A")
            console.print(
                Panel(
                    f"[bold]{name}[/]\n\n"
                    f"[green]✓[/] Completed in {elapsed:.2f}s\n"
                    f"[cyan]Rows:[/] {rows:,}\n"
                    f"[cyan]Output:[/] {output_path}",
                    border_style="cyan",
                )
            )

        def on_etl_error(name, err):
            progress.update(main_task, description=f"ETL Pipeline — [red]✗ {name}[/]")

        orchestrator.on_etl_start = on_etl_start
        orchestrator.on_etl_complete = on_etl_complete
        orchestrator.on_etl_error = on_etl_error

        results = orchestrator.run()

    return results


def _get_etl_with_dependencies(etl_configs: Dict[str, Dict], etl_name: str) -> Dict[str, Dict]:
    """Gets an ETL and all its dependencies recursively.

    Args:
        etl_configs: Configuration of all ETLs.
        etl_name: Name of the target ETL.

    Returns:
        Dictionary containing the ETL and all its dependencies.

    Raises:
        PipelineError: If an ETL in the dependency chain is not found.
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
    """Shows the ETL execution plan without executing them.

    Args:
        config_paths: List of paths to YAML configuration files.

    Returns:
        Formatted execution plan as a string.

    Raises:
        ConfigurationError: If there are configuration errors.
    """
    return execute_etl(config_paths, dry_run=True)
