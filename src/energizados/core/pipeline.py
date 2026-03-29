"""
Pipeline Orchestrator for the Energizados Framework.

This module contains the classes that orchestrate the execution of the ML workflow,
coordinating the different pipeline steps.

Note: The ConfigPipelineBuilder class has been refactored into the builders module.
This file now contains only the core Pipeline class and a backwards-compatible
ConfigPipelineBuilder that delegates to the new PipelineDirector.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from energizados.core.base import PipelineStep
from energizados.core.exceptions import (
    ConfigurationError,
    PipelineError,
    StepValidationError,
)

logger = logging.getLogger(__name__)


def _load_yaml_config(path: str) -> Dict:
    """
    Load configuration from YAML.

    Args:
        path: Path to the YAML file

    Returns:
        Dict: Loaded configuration

    Raises:
        ConfigurationError: If the file does not exist or has format errors
    """
    config_file = Path(path)
    if not config_file.exists():
        raise ConfigurationError(f"Configuration file not found: {path}", path)

    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Error parsing YAML: {e}", path) from e


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

    def run(self) -> Dict[str, Any]:
        """
        Execute all pipeline steps.

        Returns:
            Dict: Final context with results

        Raises:
            PipelineError: If an error occurs during execution
            StepValidationError: If step validation fails
        """
        if not self.steps:
            raise PipelineError("No steps configured in the pipeline")

        total_steps = len(self.steps)

        for i, step in enumerate(self.steps, 1):
            step_name = step.__class__.__name__

            logger.info(f"\n{'=' * 60}")
            logger.info(f"STEP {i}/{total_steps}: {step_name}")
            logger.info(f"{'=' * 60}")

            # Notify step start
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
                # Pass phase update callback via context if step supports it
                # The callback signature is: (step_name, phase, pct, total_phases)
                # Steps can call with 3 args (total_phases defaults to None) or 4 args
                if self.on_phase_update:
                    self.context["_on_phase_update"] = lambda step, phase, pct, total_phases=None: (
                        self.on_phase_update(step, phase, pct, total_phases)
                    )
                self.context = step.execute(self.context)
                logger.info(f"✓ Step {step_name} completed")

                # Notify step complete
                if self.on_step_complete:
                    self.on_step_complete(step_name, i, total_steps)
            except Exception as e:
                # Notify step error
                if self.on_step_error:
                    self.on_step_error(step_name, e)
                raise PipelineError(f"Error executing step {step_name}: {e}", step=step_name)

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


# Backwards-compatible ConfigPipelineBuilder that uses the new PipelineDirector
# This class is kept for backwards compatibility but delegates to the new architecture
class ConfigPipelineBuilder:
    """
    Pipeline builder from YAML configuration.

    DEPRECATED: This class is maintained for backwards compatibility.
    New code should use PipelineDirector from energizados.core.builders.

    This class now delegates to PipelineDirector internally.

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
    ):
        """
        Initialize the builder.

        Args:
            config_path: Path to the YAML configuration file (optional)
            config: Configuration dictionary (optional, takes precedence over config_path)
            config_paths: List of all config files used (for copying to run dir)
            run_name: Optional custom run directory name
            overwrite: If True, overwrite existing run directory
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
        )

    def _load_config(self, path: str) -> Dict:
        """Load configuration from YAML (backwards compatibility)."""
        return _load_yaml_config(path)

    @property
    def run_dir(self) -> Optional[Path]:
        """Return the run directory after pipeline execution."""
        return self._director.run_manager.run_dir

    def _generate_run_dir(self, base_output_dir: str = "output") -> Path:
        """Generate run directory (delegated to director)."""
        return self._director.run_manager.generate_run_dir(base_output_dir)

    def _copy_configs_to_run_dir(self):
        """Copy configs to run directory (delegated to director)."""
        self._director.run_manager.copy_configs_to_run_dir()

    def _generate_index_html(self):
        """Generate index HTML (delegated to director)."""
        self._director.run_manager.generate_index_html()

    def run(self) -> Dict[str, Any]:
        """
        Convenience method: builds and runs the pipeline, then performs post-run tasks.

        Returns:
            Dict: Final context with pipeline results
        """
        return self._director.run()

    def build(self) -> Pipeline:
        """
        Build the pipeline from the configuration.

        Returns:
            Pipeline: Configured pipeline ready to execute
        """
        return self._director.build()

    # Legacy class methods removed - registries were empty and unused
    # Use ModelRegistry from energizados.modeling.registry instead
