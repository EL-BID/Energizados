"""
Run command implementation for Energizados CLI.

This module implements the 'run' command functionality to execute
pipelines from YAML configuration.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from rich.progress import ProgressColumn
from rich.text import Text

from energizados.cli.ui import console
from energizados.core.exceptions import ConfigurationError, PipelineError
from energizados.core.pipeline import ConfigPipelineBuilder
from energizados.core.utils.memory_sampler import format_bytes

logger = logging.getLogger(__name__)


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


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dicts. Dict values are merged; all others use override."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def merge_configs(config_paths: List[str]) -> Dict[str, Any]:
    """
    Merges multiple configuration files into one.

    Uses deep merge so that dict-typed sections (e.g. ``etl:``, ``train:``)
    are merged key-by-key rather than replaced wholesale. Scalar and list
    values still follow "last wins" semantics.

    Example: two files each with an ``etl:`` section will produce a combined
    ``etl:`` containing all ETL entries from both files.

    Args:
        config_paths: List of paths to YAML files

    Returns:
        Dict: Combined configuration

    Raises:
        ConfigurationError: If any file does not exist or has format errors
    """
    merged_config: Dict[str, Any] = {}

    for config_path in config_paths:
        config_file = Path(config_path)
        if not config_file.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}", config_path)

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                if config is None:
                    config = {}
                merged_config = _deep_merge(merged_config, config)
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


def build_ordered_runs(config_paths: List[str]) -> List[List[str]]:
    """
    Group config paths into ordered execution runs, preserving the user's order.

    Each returned run is a list of paths executed together in ONE merged pipeline.
    Runs are returned in the exact order the user passed the configs, so
    ``energizados run 'etl*','train*','infer'`` always runs all ETLs first, then
    all trains, then inference — regardless of how many files each wildcard
    expands to.

    Grouping rules (applied left-to-right over ``config_paths``):
    - A step type that appears MORE than once globally runs once per config,
      each in its own single-path run, in user order.
    - A step type that appears ONCE can be merged with adjacent unique types into
      a single run (consecutive unique types coalesce into one merged pipeline).
    - The relative order of every config is always preserved.

    Examples:
        [etl, train, infer]             → [[etl, train, infer]]
        [train_01, train_02]            → [[train_01], [train_02]]
        [etl, eda, train_01, train_02]  → [[etl, eda], [train_01], [train_02]]
        [etl, train_01, train_02]       → [[etl], [train_01], [train_02]]
        [etl, train_01, train_02, infer]→ [[etl], [train_01], [train_02], [infer]]
        [etl_a, etl_b, train, infer]    → [[etl_a], [etl_b], [train, infer]]

    Args:
        config_paths: Resolved config file paths in user-specified order.

    Returns:
        Ordered list of runs; each run is a list of paths for one merged pipeline.
        Always returns at least one run when ``config_paths`` is non-empty.
    """
    from collections import Counter

    # Count occurrences of each step type across ALL paths (global view)
    type_counts: Counter = Counter()
    for path in config_paths:
        key = _step_type_key(path)
        type_counts[key] += 1

    runs: List[List[str]] = []
    current_run: List[str] = []
    current_types: set = set()

    for path in config_paths:
        key = _step_type_key(path)
        is_multi = type_counts[key] > 1

        # A repeated type, or a type already accumulated in the current run,
        # must flush the current run and start its own.
        if is_multi or key in current_types:
            if current_run:
                runs.append(current_run)
                current_run = []
                current_types = set()
            runs.append([path])
        else:
            current_run.append(path)
            current_types.add(key)

    if current_run:
        runs.append(current_run)

    return runs


def _step_type_key(path: str) -> str:
    """Return the dispatch key for a config path: its step type, or the stem if unknown."""
    stem = Path(path).stem
    step_type = _get_step_type(stem)
    return step_type if step_type is not None else stem


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

    # Supplement with any steps the director built from additional sections present in
    # the same config file (e.g., ETLStep from an etl: block inside infer.yaml).
    # Re-order everything by DEFAULT_STEP_ORDER so ETL always precedes Inference, etc.
    built_step_names = {step.__class__.__name__ for step in pipeline.steps}
    extra = [s for s in DEFAULT_STEP_ORDER if s in built_step_names and s not in user_order]
    if extra:
        all_requested = set(user_order) | set(extra)
        return [s for s in DEFAULT_STEP_ORDER if s in all_requested]

    return user_order


def execute_pipeline(
    config_paths: List[str],
    run_name: Optional[str] = None,
    overwrite: bool = False,
    profile_memory: bool = False,
) -> Dict[str, Any]:
    """
    Executes the complete pipeline from YAML configuration(s).

    Args:
        config_paths: List of paths to YAML configuration files
        run_name: Optional custom run directory name
        overwrite: If True, overwrite existing output directory

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
        config=merged_config,
        config_paths=list(config_paths),
        run_name=run_name,
        overwrite=overwrite,
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

    # Use the first config name as the section label for training steps
    # so the Rule shows "train_01_baseline" instead of just "train"
    training_section = config_names[0] if config_names else "train"
    STEP_SECTIONS = {
        "ETLStep": "etl",
        "SplitStep": training_section,
        "TrainingStep": training_section,
        "DefaultEvaluator": training_section,
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
    profile_rows: list = []  # (name, metrics) tuples for the -vv memory table

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

    def on_step_start(name: str, i: int, total: int) -> None:
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

    def on_phase_update(
        step_name: str,
        phase: str,
        pct: int,
        total_phases: Optional[int],
        metrics: Optional[Dict[str, int]] = None,
    ) -> None:
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
                        mem = _format_mem_inline(metrics)
                        progress.update(
                            task_id, completed=1, description=f"[green]✓ {_pad(phase)}[/]{mem}"
                        )
                        progress.stop_task(task_id)
                        if metrics:
                            profile_rows.append((phase, metrics))
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

    def on_step_complete(
        name: str, i: int, total: int, metrics: Optional[Dict[str, int]] = None
    ) -> None:
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

        if metrics:
            profile_rows.append((STEP_NAMES.get(name, name), metrics))

    def on_step_error(name: str, err: BaseException) -> None:
        progress = active_progress[0]
        if progress is not None:
            task_id = step_task_ids.get(name)
            if task_id is not None:
                progress.update(
                    task_id, description=f"[red]✗ {_pad(STEP_NAMES.get(name, name))}[/]"
                )

    pipeline.profile_memory = profile_memory
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
    if builder.run_dir is not None:
        builder.copy_configs_to_run_dir()
        index_path = builder.generate_index_html()
        if index_path is not None and index_path.exists():
            console.print(f"\n[dim]Index updated → {index_path}[/]")

    _print_metrics_summary(result)
    if profile_rows:
        _print_profiling_table(profile_rows)

    return result


def _format_mem_inline(metrics: Optional[Dict[str, int]]) -> str:
    """Compact Rich-formatted memory suffix for the progress bar.

    Renders as `` Δ+2.7GB peak 9.2GB ⚠`` (dim, red warning when the retained
    delta exceeds 1 GB). Empty string when ``metrics`` is falsy, so normal
    (non ``-vv``) runs are unaffected.
    """
    if not metrics:
        return ""
    delta = metrics.get("delta", 0)
    peak = metrics.get("peak", 0)
    warn = " [red]⚠[/]" if delta > 1024**3 else ""
    return f" [dim]Δ{format_bytes(delta)} peak {format_bytes(peak)}[/]{warn}"


def _print_profiling_table(rows: List[tuple]) -> None:
    """Print a Rich table of per-step / per-ETL memory usage, sorted by peak.

    Rendered after a ``-vv`` run once all steps complete. ``rows`` is a list of
    ``(label, metrics_dict)`` tuples accumulated by the progress callbacks.
    """
    from rich import box as rich_box
    from rich.table import Table

    table = Table(
        title="Memory profile (-vv)",
        box=rich_box.SIMPLE,
        padding=(0, 2),
        show_edge=False,
        title_style="bold cyan",
    )
    table.add_column("step / etl", style="dim", no_wrap=True)
    table.add_column("RSS start", justify="right")
    table.add_column("RSS end", justify="right")
    table.add_column("\u0394 retained", justify="right", style="cyan")
    table.add_column("peak", justify="right", style="yellow")
    for label, metrics in sorted(rows, key=lambda r: r[1].get("peak", 0), reverse=True):
        table.add_row(
            label,
            format_bytes(metrics.get("rss_start")),
            format_bytes(metrics.get("rss_end")),
            format_bytes(metrics.get("delta")),
            format_bytes(metrics.get("peak")),
        )
    console.print()
    console.print(table)


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
    config_paths: List[str],
    step_name: str,
    run_name: Optional[str] = None,
    overwrite: bool = False,
    profile_memory: bool = False,
) -> Dict[str, Any]:
    """
        Executes a single step of the pipeline.

        Args:
            config_paths: List of paths to YAML configuration files
            step_name: Name of the step to execute
            run_name: Optional custom run directory name
            overwrite: If True, overwrite existing run directory
            profile_memory: When True, sample RSS around the step's execution
    (enabled by the CLI under ``-vv``).

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
        config=merged_config,
        config_paths=list(config_paths),
        run_name=run_name,
        overwrite=overwrite,
    )
    pipeline = builder.build()

    # Filter only the requested step
    step_class_name = step_map[step_name]
    filtered_steps = [s for s in pipeline.steps if s.__class__.__name__ == step_class_name]

    if not filtered_steps:
        raise PipelineError(f"The step '{step_name}' is not configured or not enabled")

    # Replace pipeline steps
    pipeline.steps = filtered_steps

    # Enable memory profiling when requested (consistent with execute_pipeline)
    pipeline.profile_memory = profile_memory

    # Execute only the selected step
    result = pipeline.run()

    # Post-run tasks if a run dir was generated
    if builder.run_dir is not None:
        builder.copy_configs_to_run_dir()
        builder.generate_index_html()

    return result


def execute_etl(
    config_paths: List[str], etl_name: Optional[str] = None, dry_run: bool = False
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

    from energizados._version import SCHEMA_VERSION_KEY

    # Verify if there is ETL configuration
    etl_configs = merged_config.get("etl")

    if not etl_configs:
        raise PipelineError(
            "No ETLs configured. Use the 'etl:' section to configure multiple ETLs."
        )

    # If a specific ETL is requested, filter its dependencies
    if etl_name:
        available = [k for k in etl_configs if k != SCHEMA_VERSION_KEY]
        if etl_name not in etl_configs:
            raise PipelineError(f"ETL '{etl_name}' not found. Available ETLs: {available}")

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


def show_etl_plan(config_paths: List[str]) -> Dict[str, Any]:
    """Shows the ETL execution plan without executing them.

    Prints the plan to the console and returns an empty dict (the dry-run
    contract of :func:`execute_etl`).

    Args:
        config_paths: List of paths to YAML configuration files.

    Returns:
        Empty dict (the plan is emitted to the console as a side effect).

    Raises:
        ConfigurationError: If there are configuration errors.
    """
    return execute_etl(config_paths, dry_run=True)
