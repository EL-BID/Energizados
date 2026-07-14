"""
Pipeline Orchestrator for the Energizados Framework.

This module contains the classes that orchestrate the execution of the ML workflow,
coordinating the different pipeline steps.

Note: ConfigPipelineBuilder is the primary pipeline entry point (used by the CLI
and the generated run scripts). It delegates to PipelineDirector internally;
this file holds the core Pipeline class plus that entry-point builder.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from energizados.core.base import PipelineStep
from energizados.core.exceptions import (
    EnergizadosError,
    ETLDependencyError,
    PipelineError,
    StepValidationError,
)
from energizados.core.utils.yaml_utils import load_yaml_config

logger = logging.getLogger(__name__)


def _load_yaml_config(path: str) -> Dict:
    return load_yaml_config(path)


@dataclass
class ExecutionPlan:
    """Execution plan returned by Pipeline.plan()."""

    steps: List[str]
    dependencies: Dict[str, List[str]]
    estimated_duration: Optional[float] = None


class Pipeline:
    """
    ML workflow orchestrator.

    Executes steps in order and manages shared context between steps.

    Args:
        config_path: Path to the YAML configuration file
        config: Configuration dictionary (optional, if passed, config_path is ignored)

    Attributes:
        config: Dictionary with the pipeline configuration
        context: Dictionary with data shared between steps
        steps: List of steps to execute

    Example:
        >>> pipeline = Pipeline("config.yaml")
        >>> pipeline.add_step(ETLStep())
        >>> pipeline.add_step(TrainingStep())
        >>> results = pipeline.run()
    """

    def __init__(self, config_path: str = None, config: Dict = None):
        """
        Initialize the pipeline.

        Args:
            config_path: Path to the YAML configuration file
            config: Configuration dictionary (optional)
        """
        if config is not None:
            self.config = config
        elif config_path is not None:
            self.config = self._load_config(config_path)
        else:
            self.config = {}

        self.context: Dict[str, Any] = {}
        self.steps: List[PipelineStep] = []

        # Optional callbacks for progress tracking
        self.on_step_start = None  # callable(name, index, total)
        self.on_step_complete = None  # callable(name, index, total)
        self.on_step_error = None  # callable(name, error)
        self.on_phase_update = None  # callable(step_name, phase_name, progress_pct, total_phases)

    @classmethod
    def from_dict(
        cls, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> "Pipeline":
        """Create Pipeline from dict config (explicit factory).

        This is the programmatic API entry point. Equivalent to:
            Pipeline(config=config_dict)

        Args:
            config: Configuration dictionary
            context: Optional initial context (not used in Pipeline, reserved for future)

        Returns:
            Configured Pipeline instance
        """
        return cls(config=config)

    def plan(self) -> ExecutionPlan:
        """Return execution plan without running.

        Builds step list from config and validates ETL dependencies using
        existing ETLOrchestrator cycle detection.

        Returns:
            ExecutionPlan with steps, dependencies, and estimated_duration

        Raises:
            ETLDependencyError: If circular dependencies are detected
        """
        from energizados.etl.orchestrator import ETLOrchestrator

        # Extract ETL config if present
        etl_config = self.config.get("etl", {})

        if etl_config:
            # Build dependencies dict from config for enabled ETLs only
            enabled_etls = {}
            for etl_name, etl_config_item in etl_config.items():
                if etl_config_item.get("enabled", True):
                    enabled_etls[etl_name] = etl_config_item

            # Use ETLOrchestrator to validate dependencies and detect cycles
            try:
                orchestrator = ETLOrchestrator(enabled_etls)
                # Explicitly validate dependencies (includes cycle detection)
                orchestrator.validate_dependencies()
                # Get execution order
                execution_order = orchestrator.get_execution_order()

                # Build dependencies dict from config
                dependencies = {
                    etl_name: etl_config_item.get("depends_on", [])
                    for etl_name, etl_config_item in enabled_etls.items()
                }

                return ExecutionPlan(
                    steps=execution_order,  # Use the validated execution order
                    dependencies=dependencies,
                    estimated_duration=None,  # Could be estimated based on historical runs
                )

            except ETLDependencyError:
                # Re-raise with proper error code
                raise
            except Exception:
                # If there's any other error, return a basic plan
                dependencies = {
                    etl_name: etl_config_item.get("depends_on", [])
                    for etl_name, etl_config_item in enabled_etls.items()
                }
                return ExecutionPlan(
                    steps=list(enabled_etls.keys()),
                    dependencies=dependencies,
                    estimated_duration=None,
                )
        else:
            # No ETL config - return empty plan
            return ExecutionPlan(steps=[], dependencies={}, estimated_duration=None)

    def _load_config(self, path: str) -> Dict:
        """
        Load configuration from YAML.

        Args:
            path: Path to the YAML file

        Returns:
            Dict: Loaded configuration

        Raises:
            ConfigurationError: If the file does not exist or has format errors
        """
        return _load_yaml_config(path)

    def add_step(self, step: PipelineStep) -> "Pipeline":
        """
        Add a step to the pipeline.

        Args:
            step: Step to add

        Returns:
            self: Allows chaining calls
        """
        self.steps.append(step)
        return self

    def run(self, progress_callback: Optional[Any] = None) -> Dict[str, Any]:
        """
        Execute all pipeline steps.

        Args:
            progress_callback: Optional callback for progress events.
                            Receives ProgressEvent objects.

        Returns:
            Dict: Final context with results

        Raises:
            PipelineError: If an error occurs during execution
            StepValidationError: If step validation fails
        """
        if not self.steps:
            raise PipelineError("No steps configured in the pipeline")

        total_steps = len(self.steps)

        # Lazy import to avoid circular dependency
        try:
            from energizados.api.progress import ProgressEvent
        except ImportError:
            ProgressEvent = None

        def safe_emit(event):
            """Emit progress event with error isolation."""
            if progress_callback and ProgressEvent:
                try:
                    progress_callback(event)
                except Exception:
                    logger.exception("Progress callback error (ignored)")

        for i, step in enumerate(self.steps, 1):
            step_name = step.__class__.__name__

            logger.info(f"\n{'=' * 60}")
            logger.info(f"STEP {i}/{total_steps}: {step_name}")
            logger.info(f"{'=' * 60}")

            # Emit start event
            safe_emit(
                ProgressEvent(
                    run_id="unknown",
                    step_name=step_name,
                    phase="start",
                    message=f"Starting step {step_name}",
                )
                if ProgressEvent
                else None
            )

            # Notify step start (legacy callback)
            if self.on_step_start:
                self.on_step_start(step_name, i, total_steps)

            # Validate input
            if not step.validate_input(self.context):
                missing_keys = step.get_required_keys()
                raise StepValidationError(
                    f"Validation failed in step {step_name}",
                    step=step_name,
                    missing_keys=missing_keys,
                )

            # Execute step
            try:
                if self.on_phase_update:
                    callback = self.on_phase_update

                    def _phase_adapter(step, phase, pct, total_phases=None):
                        callback(step, phase, pct, total_phases)

                    self.context["_on_phase_update"] = _phase_adapter
                self.context = step.execute(self.context)
                logger.info(f"✓ Step {step_name} completed")

                # Emit complete event
                safe_emit(
                    ProgressEvent(
                        run_id="unknown",
                        step_name=step_name,
                        phase="complete",
                        message=f"Completed step {step_name}",
                    )
                    if ProgressEvent
                    else None
                )

                # Notify step complete (legacy callback)
                if self.on_step_complete:
                    self.on_step_complete(step_name, i, total_steps)
            except Exception as e:
                # Emit error event
                safe_emit(
                    ProgressEvent(
                        run_id="unknown",
                        step_name=step_name,
                        phase="error",
                        message=f"Error in step {step_name}: {e}",
                    )
                    if ProgressEvent
                    else None
                )

                # Notify step error — callback fires for BOTH paths
                if self.on_step_error:
                    self.on_step_error(step_name, e)
                # Framework exceptions propagate unchanged (type/attributes
                # preserved); only unexpected errors are wrapped as PipelineError.
                if isinstance(e, EnergizadosError):
                    raise
                raise PipelineError(f"Error executing step {step_name}: {e}", step=step_name) from e

        return self.context

    def get_context(self) -> Dict[str, Any]:
        """
        Return the current pipeline context.

        Returns:
            Dict: Current context
        """
        return self.context.copy()

    def reset(self):
        """Reset the context and steps of the pipeline."""
        self.context = {}
        self.steps = []


# ConfigPipelineBuilder is the primary pipeline entry point used by the CLI
# (cli/run.py) and the generated src/run/*.py scripts. It delegates to
# PipelineDirector internally.
class ConfigPipelineBuilder:
    """
    Pipeline builder from YAML configuration.

    This is the main entry point for building and running a pipeline from YAML
    configuration. It is used directly by the CLI (``energizados run``) and by
    the generated ``src/run/*.py`` scripts. Internally it delegates to
    ``PipelineDirector`` (``energizados.core.builders``).

    Args:
        config_path: Path to the YAML configuration file

    Example:
        >>> builder = ConfigPipelineBuilder("config.yaml")
        >>> pipeline = builder.build()
        >>> results = pipeline.run()
    """

    def __init__(
        self,
        config_path: str = None,
        config: Dict = None,
        config_paths: List[str] = None,
        run_name: Optional[str] = None,
        overwrite: bool = False,
        derived_from: Optional[str] = None,
    ):
        """
        Initialize the builder.

        Args:
            config_path: Path to the YAML configuration file (optional)
            config: Configuration dictionary (optional, takes precedence over config_path)
            config_paths: List of all config files used (for copying to run dir)
            run_name: Optional custom run directory name
            overwrite: If True, overwrite existing run directory
            derived_from: ADR-0003 optional source run_id for retrain lineage.
                ``run_type`` is NOT a constructor param — it is derived from the
                config by the director.
        """
        # Store config paths for backwards compatibility
        self.config_paths: List[str] = config_paths or ([config_path] if config_path else [])

        # Initialize the new director
        from energizados.core.builders.director import PipelineDirector

        self._director = PipelineDirector(
            config_path=config_path,
            config=config,
            config_paths=self.config_paths,
            run_name=run_name,
            overwrite=overwrite,
            derived_from=derived_from,
        )

    def _load_config(self, path: str) -> Dict:
        """Load configuration from YAML (backwards compatibility)."""
        return _load_yaml_config(path)

    @property
    def run_dir(self) -> Optional[Path]:
        """Return the run directory after pipeline execution."""
        return self._director.run_manager.run_dir

    def copy_configs_to_run_dir(self):
        """Copy configs to run directory."""
        self._director.run_manager.copy_configs_to_run_dir()

    def generate_index_html(self):
        """Generate index HTML."""
        self._director.run_manager.generate_index_html()

    def run(self, progress_callback: Optional[Any] = None) -> Dict[str, Any]:
        """
        Convenience method: builds and runs the pipeline, then performs post-run tasks.

        Args:
            progress_callback: Optional callback invoked with ProgressEvent objects,
                forwarded to PipelineDirector.run → Pipeline.run. Used by the web
                worker to stream live job progress to the SSE endpoint.

        Returns:
            Dict: Final context with pipeline results
        """
        return self._director.run(progress_callback=progress_callback)

    def build(self) -> Pipeline:
        """
        Build the pipeline from the configuration.

        Returns:
            Pipeline: Configured pipeline ready to execute
        """
        return self._director.build()

    # Legacy class methods removed - registries were empty and unused
    # Use ModelRegistry from energizados.modeling.registry instead
