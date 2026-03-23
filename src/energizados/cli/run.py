"""
Run command implementation for Energizados CLI.

This module implements the 'run' command functionality to execute
pipelines from YAML configuration.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from rich.progress import ProgressColumn
from rich.text import Text

from energizados.cli.ui import console
from energizados.core.exceptions import ConfigurationError, PipelineError
from energizados.core.pipeline import ConfigPipelineBuilder


class TimeElapsedColumnMs(ProgressColumn):
    """Elapsed time column with millisecond precision (H:MM:SS.mmm)."""

    def render(self, task) -> Text:
        elapsed = task.elapsed
        if elapsed is None:
            return Text("-:--:--.---", style="progress.elapsed")
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)
        ms = int((elapsed % 1) * 1000)
        return Text(
            f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}.{ms:03d}",
            style="progress.elapsed",
        )


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


def _get_config_names_from_paths(config_paths: List[str]) -> List[str]:
    """
    Extract config names from file paths, preserving order.

    Example:
        ['/path/to/config/etl.yaml', '/path/to/config/eda.yaml'] -> ['etl', 'eda']

    Args:
        config_paths: List of config file paths

    Returns:
        List of config names (without .yaml extension), in order
    """
    names = []
    for path in config_paths:
        # Get the filename without extension
        name = Path(path).stem
        names.append(name)
    return names


# Mapping from config names to step class names
CONFIG_TO_STEP = {
    "etl": "ETLStep",
    "eda": "EDAStep",
    "train": "TrainingStep",  # train includes split + training + evaluation
    "split": "SplitStep",
    "evaluation": "DefaultEvaluator",
    "infer": "InferenceStep",
}

# Default order of steps in the pipeline (when user doesn't specify order)
DEFAULT_STEP_ORDER = [
    "ETLStep",
    "SplitStep",
    "TrainingStep",
    "DefaultEvaluator",
    "InferenceStep",
    "EDAStep",
]


_CONFIG_TO_STEPS = {
    "etl": ["ETLStep"],
    "eda": ["EDAStep"],
    "train": ["SplitStep", "TrainingStep", "DefaultEvaluator"],
    "split": ["SplitStep"],
    "evaluation": ["DefaultEvaluator"],
    "infer": ["InferenceStep"],
}


def _get_step_type(config_name: str) -> Optional[str]:
    """
    Return the step type for a config name, using prefix matching.

    Examples:
        "train"              -> "train"
        "train_01_baseline"  -> "train"
        "etl_raw"            -> "etl"
        "my_custom"          -> None
    """
    name = config_name.lower()
    for prefix in _CONFIG_TO_STEPS:
        if name == prefix or name.startswith(prefix + "_") or name.startswith(prefix + "-"):
            return prefix
    return None


def all_same_step_type(config_paths: List[str]) -> bool:
    """
    Return True if all configs share the same step type and there are multiple configs.

    Used to detect "run train_01,train_02" (sequential runs) vs "etl,train" (merge).
    """
    if len(config_paths) <= 1:
        return False
    types = [_get_step_type(Path(p).stem) for p in config_paths]
    return len(set(types)) == 1 and types[0] is not None


def split_configs_by_type(
    config_paths: List[str],
) -> tuple[List[str], List[List[str]]]:
    """
    Split configs into shared (one per step type) and repeated (multiple per type) groups.

    Returns (shared, repeated_runs):
    - shared: paths where the step type appears exactly once — run together once
    - repeated_runs: one [path] per config for step types that appear more than once

    Examples:
        [etl, train]                   → shared=[etl, train],  repeated=[]
        [train_01, train_02]           → shared=[],            repeated=[[train_01], [train_02]]
        [etl, eda, train_01, train_02] → shared=[etl, eda],    repeated=[[train_01], [train_02]]
        [etl, train_01, train_02]      → shared=[etl],         repeated=[[train_01], [train_02]]
    """
    groups: Dict[str, List[str]] = {}
    for path in config_paths:
        step_type = _get_step_type(Path(path).stem) or Path(path).stem
        groups.setdefault(step_type, []).append(path)

    shared: List[str] = []
    repeated_runs: List[List[str]] = []

    for paths in groups.values():
        if len(paths) == 1:
            shared.extend(paths)
        else:
            for path in paths:
                repeated_runs.append([path])

    return shared, repeated_runs


def _determine_execution_order(pipeline, config_names: List[str]) -> List[str]:
    """
    Determine the execution order based on user-specified config names.

    If user specifies multiple configs (e.g., "etl,eda,train"), execute them
    in that exact order. If only one config, execute just that config's steps.

    Uses prefix matching so "train_01_baseline" resolves to the "train" steps.

    Args:
        pipeline: The Pipeline object with steps
        config_names: List of config names in order specified by user

    Returns:
        List of step class names in execution order
    """
    # Build execution order from user's config order
    user_order = []
    for config_name in config_names:
        step_type = _get_step_type(config_name)
        steps = _CONFIG_TO_STEPS.get(step_type, []) if step_type else []
        for step in steps:
            if step not in user_order:
                user_order.append(step)

    # If we couldn't map any configs, fall back to pipeline's default order
    if not user_order:
        return [step.__class__.__name__ for step in pipeline.steps]

    return user_order


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
    )

    # Merge configurations
    merged_config = merge_configs(config_paths)

    # Get config names in order (for sequential execution order)
    # This preserves the order specified by user: "etl,eda,train" -> ["etl", "eda", "train"]
    config_names = _get_config_names_from_paths(config_paths)

    # Build pipeline (don't run yet)
    builder = ConfigPipelineBuilder(
        config=merged_config, config_paths=list(config_paths), run_name=run_name
    )
    pipeline = builder.build()

    # Determine execution order: use user-specified order if multiple configs
    # Otherwise use default pipeline order
    execution_order = _determine_execution_order(pipeline, config_names)

    # Define phases for each step type
    # Note: ETLStep uses dynamic phases based on ETL names (handled in on_step_start)
    STEP_PHASES = {
        "SplitStep": ["analyzing", "splitting", "saving"],
        "TrainingStep": ["loading", "feature_engineering", "training", "evaluation"],
        "DefaultEvaluator": ["evaluating", "generating_report"],
        "InferenceStep": ["loading_model", "predicting", "saving"],
        "EDAStep": ["analyzing_data", "generating_report"],
    }

    STEP_NAMES = {
        "SplitStep": "split",
        "TrainingStep": "train",
        "DefaultEvaluator": "evaluation",
        "InferenceStep": "inference",
        "EDAStep": "eda",
        "ETLStep": "etl",
    }

    _LABEL_WIDTH = max(len(v) for v in STEP_NAMES.values())

    def _pad(label: str) -> str:
        return label.ljust(_LABEL_WIDTH)

    STEP_SECTIONS = {
        "ETLStep": "etl",
        "SplitStep": "train",
        "TrainingStep": "train",
        "DefaultEvaluator": "train",
        "InferenceStep": "inference",
        "EDAStep": "eda",
    }

    from rich.rule import Rule

    def _make_progress() -> Progress:
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumnMs(),
            console=console,
            expand=True,
        )

    # One Progress instance per section (etl, train, …) so section Rules
    # appear between bar groups rather than above all of them.
    active_progress: list = [None]  # [Progress | None]
    current_section: list = [None]  # [str | None]
    step_task_ids: dict = {}
    step_phases: dict = {}
    etl_sub_tasks: dict = {}

    def _ensure_section(section: str) -> Progress:
        if section != current_section[0]:
            if active_progress[0] is not None:
                active_progress[0].stop()
            console.print(Rule(f"[bold cyan]{section}[/]"))
            p = _make_progress()
            p.start()
            active_progress[0] = p
            current_section[0] = section
        return active_progress[0]

    def on_step_start(name, i, total):
        section = STEP_SECTIONS.get(name, name)
        progress = _ensure_section(section)

        phases = STEP_PHASES.get(name)
        step_phases[name] = phases if phases else []

        if name == "ETLStep":
            step_task_ids[name] = None
        else:
            label = STEP_NAMES.get(name, name)
            task_id = progress.add_task(
                f"[yellow]▶ {_pad(label)}[/]",
                total=max(len(step_phases[name]), 1),
            )
            step_task_ids[name] = task_id

    def on_phase_update(step_name, phase, pct, total_phases):
        progress = active_progress[0]
        if progress is None:
            return
        try:
            if step_name == "ETLStep" and total_phases is not None:
                if pct == 0:
                    task_id = progress.add_task(f"[yellow]▶ {_pad(phase)}[/]", total=1)
                    etl_sub_tasks[phase] = task_id
                elif pct == 100:
                    task_id = etl_sub_tasks.get(phase)
                    if task_id is not None:
                        progress.update(
                            task_id, completed=1, description=f"[green]✓ {_pad(phase)}[/]"
                        )
                        progress.stop_task(task_id)
            else:
                phases = step_phases.get(step_name, [])
                phase_idx = phases.index(phase) if phase in phases else -1
                if phase_idx >= 0:
                    task_id = step_task_ids.get(step_name)
                    if task_id is not None:
                        progress.update(
                            task_id,
                            completed=phase_idx + (pct / 100),
                            description=f"[yellow]▶ {_pad(STEP_NAMES.get(step_name, step_name))}[/] — {phase}",
                        )
        except Exception:  # nosec
            pass

    def on_step_complete(name, i, total):
        progress = active_progress[0]
        if progress is None:
            return
        task_id = step_task_ids.get(name)
        if task_id is not None:
            phases = step_phases.get(name, [])
            try:
                progress.update(
                    task_id,
                    completed=max(len(phases), 1),
                    description=f"[green]✓ {_pad(STEP_NAMES.get(name, name))}[/]",
                )
                progress.stop_task(task_id)
            except Exception:  # nosec
                pass
        elif name == "ETLStep":
            for etl_task_id in etl_sub_tasks.values():
                try:
                    progress.update(etl_task_id, completed=1)
                    progress.stop_task(etl_task_id)
                except Exception:  # nosec
                    pass

    def on_step_error(name, err):
        progress = active_progress[0]
        if progress is not None:
            task_id = step_task_ids.get(name)
            if task_id is not None:
                progress.update(
                    task_id, description=f"[red]✗ {_pad(STEP_NAMES.get(name, name))}[/]"
                )

    pipeline.on_step_start = on_step_start
    pipeline.on_step_complete = on_step_complete
    pipeline.on_step_error = on_step_error
    pipeline.on_phase_update = on_phase_update

    # Filter and reorder steps based on user-specified execution order
    filtered_steps = []
    for step_class_name in execution_order:
        for step in pipeline.steps:
            if step.__class__.__name__ == step_class_name:
                filtered_steps.append(step)
                break

    # Replace pipeline steps with filtered/ordered list
    pipeline.steps = filtered_steps

    try:
        result = pipeline.run()
    finally:
        if active_progress[0] is not None:
            active_progress[0].stop()

    # Post-run tasks (config copy, index HTML) - these need to be called manually
    # since we called pipeline.run() directly instead of builder.run()
    if builder._director.run_manager._run_dir is not None:
        builder._copy_configs_to_run_dir()
        builder._generate_index_html()

    _print_metrics_summary(result)

    return result


def _print_confusion_matrix(cm: Dict) -> None:
    """Renders a 2x2 confusion matrix using a Rich table."""
    from rich import box as rich_box
    from rich.table import Table

    tn, fp, fn, tp = cm["tn"], cm["fp"], cm["fn"], cm["tp"]
    table = Table(box=rich_box.SIMPLE, padding=(0, 2), show_edge=False)
    table.add_column("", style="dim")
    table.add_column("pred 0", justify="right", style="cyan")
    table.add_column("pred 1", justify="right", style="cyan")
    table.add_row("actual 0", f"{tn:,}", f"[red]{fp:,}[/]")
    table.add_row("actual 1", f"[red]{fn:,}[/]", f"[green]{tp:,}[/]")
    console.print(table)


def _print_metrics_summary(result: Dict[str, Any]) -> None:
    """Prints a compact metrics table after pipeline completion."""
    from rich.table import Table

    # Single model: result["metrics"] is a flat dict {auc: float, precision: float, ...}
    # Ensemble: result["model_metrics"] is a dict {model_name: {auc: float, ...}}
    metrics = result.get("metrics")
    model_metrics = result.get("model_metrics")

    if not metrics and not model_metrics:
        return

    DISPLAY = ["auc", "precision", "recall", "f1", "accuracy"]

    def _fmt(v) -> str:
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)

    if metrics:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="dim")
        table.add_column(style="bold cyan")
        for key in DISPLAY:
            if key in metrics:
                table.add_row(key, _fmt(metrics[key]))
        console.print()
        console.print(table)

        cm = metrics.get("confusion_matrix")
        if cm:
            _print_confusion_matrix(cm)

    elif model_metrics:
        table = Table(box=None, padding=(0, 2))
        table.add_column("model", style="dim")
        for key in DISPLAY:
            table.add_column(key, style="bold cyan")
        for model_name, m in model_metrics.items():
            row = [model_name] + [_fmt(m.get(key, "—")) for key in DISPLAY]
            table.add_row(*row)
        console.print()
        console.print(table)


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
        "evaluation": "DefaultEvaluator",
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
    )
    from rich.rule import Rule

    config_names = ", ".join(Path(p).stem for p in config_paths)
    console.print(Rule(f"[bold cyan]{config_names}[/]"))

    results = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumnMs(),
        console=console,
    ) as progress:
        etl_tasks = {}  # etl_name -> task_id

        def on_etl_start(name, idx, total):
            task_id = progress.add_task(f"[yellow]▶ [{idx + 1}/{total}] {name}[/]", total=1)
            etl_tasks[name] = task_id

        def on_etl_complete(name, rows):
            task_id = etl_tasks.get(name)
            if task_id is not None:
                progress.update(
                    task_id,
                    completed=1,
                    description=f"[green]✓ {name}[/] [dim]({rows:,} rows)[/]",
                )
                progress.stop_task(task_id)

        def on_etl_error(name, err):
            task_id = etl_tasks.get(name)
            if task_id is not None:
                progress.update(task_id, description=f"[red]✗ {name}[/]")

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
