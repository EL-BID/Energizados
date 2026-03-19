"""
Pipeline Director.

This module orchestrates the construction of pipeline steps using builders.
It follows the Builder pattern, delegating step construction to specialized builders.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from energizados.core.builders.eda_builder import EDABuilder
from energizados.core.builders.etl_builder import ETLBuilder
from energizados.core.builders.evaluation_builder import EvaluationBuilder
from energizados.core.builders.inference_builder import InferenceBuilder
from energizados.core.builders.run_manager import RunManager
from energizados.core.builders.split_builder import SplitBuilder
from energizados.core.builders.training_builder import TrainingBuilder
from energizados.core.exceptions import ConfigurationError
from energizados.core.pipeline import Pipeline
from energizados.core.schemas.config_validator import ConfigValidator

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


class PipelineDirector:
    """
    Orchestrates pipeline construction from YAML configuration.

    Uses specialized builders to construct each pipeline step
    and coordinates run directory management.

    Example:
        >>> director = PipelineDirector("config.yaml")
        >>> pipeline = director.build()
        >>> results = pipeline.run()
    """

    def __init__(
        self,
        config_path: str = None,
        config: Dict = None,
        config_paths: List[str] = None,
        run_name: Optional[str] = None,
    ):
        """
        Initialize the director.

        Args:
            config_path: Path to the YAML configuration file (optional)
            config: Configuration dictionary (optional, takes precedence over config_path)
            config_paths: List of all config files used (for copying to run dir)
            run_name: Optional custom run directory name
        """
        if config is not None:
            self.config = config
            self.config_path = None
        elif config_path is not None:
            self.config_path = config_path
            self.config = self._load_config(config_path)
        else:
            raise ValueError("Must provide config_path or config")

        self.config_paths: List[str] = config_paths or ([config_path] if config_path else [])
        self._run_name: Optional[str] = run_name
        self.run_manager = RunManager(self.config_paths, run_name=run_name)
        self._run_dir: Optional[Path] = None

        # Validate configuration against schema
        self._validate_config()

    def _load_config(self, path: str) -> Dict:
        """Load configuration from YAML."""
        return _load_yaml_config(path)

    def _validate_config(self):
        """Validate configuration against JSON schema."""
        validator = ConfigValidator()
        errors = validator.validate_config(self.config, self.config_path or "config")
        if errors:
            error_messages = "\n".join(f"  - {e}" for e in errors)
            raise ConfigurationError(
                f"Configuration validation failed:\n{error_messages}", self.config_path or "config"
            )

    def build(self) -> Pipeline:
        """
        Build the pipeline from the configuration.

        Returns:
            Pipeline: Configured pipeline ready to execute

        Raises:
            ConfigurationError: If required configuration is missing
        """
        pipeline = Pipeline(config=self.config)

        # Generate timestamped run directory if training or evaluation is enabled
        train_config = self.config.get("train", {})
        eval_config = train_config.get("evaluation", {}) or self.config.get("evaluation", {})
        if train_config.get("enabled", False) or eval_config.get("enabled", False):
            base_output_dir = train_config.get("output_base_dir", "output")
            self._run_dir = self.run_manager.generate_run_dir(
                base_output_dir, run_name=self._run_name
            )

        # Build and add each step
        # Step 1: ETL
        etl_builder = ETLBuilder(self.config)
        etl_step = etl_builder.build()
        if etl_step is not None:
            pipeline.add_step(etl_step)

        # Step 2: Split
        split_config = self.config.get("train", {}).get("split", {})
        if not split_config:
            split_config = self.config.get("split", {})
        split_builder = SplitBuilder(split_config, self.config)
        split_step = split_builder.build()
        if split_step is not None:
            pipeline.add_step(split_step)

        # Step 3: Training
        train_config = self.config.get("train", {})
        if train_config.get("enabled", False):
            train_output_dir = str(self._run_dir / "models") if self._run_dir else None
            train_builder = TrainingBuilder(train_config, train_output_dir)
            train_step = train_builder.build()
            if train_step is not None:
                pipeline.add_step(train_step)

        # Step 4: Evaluation
        eval_config = self.config.get("train", {}).get("evaluation", {})
        if not eval_config:
            eval_config = self.config.get("evaluation", {})
        if eval_config.get("enabled", False):
            eval_output_dir = (
                str(self._run_dir / "reports" / "evaluation") if self._run_dir else None
            )
            eval_builder = EvaluationBuilder(eval_config, eval_output_dir)
            eval_step = eval_builder.build()
            if eval_step is not None:
                pipeline.add_step(eval_step)

        # Step 5: Inference
        if self.config.get("infer", {}).get("enabled", False):
            inference_builder = InferenceBuilder(self.config.get("infer", {}))
            inference_step = inference_builder.build()
            if inference_step is not None:
                pipeline.add_step(inference_step)

        # Step 6: EDA
        if self.config.get("eda", {}).get("enabled", False):
            eda_builder = EDABuilder(self.config.get("eda", {}))
            eda_step = eda_builder.build()
            if eda_step is not None:
                pipeline.add_step(eda_step)

        return pipeline

    def run(self) -> Dict[str, Any]:
        """
        Convenience method: builds and runs the pipeline, then performs post-run tasks.

        Post-run tasks:
        - Copies config files to the run directory
        - Regenerates output/index.html

        Returns:
            Dict: Final context with pipeline results
        """
        pipeline = self.build()
        result = pipeline.run()

        # Run post-build tasks
        self.run_manager.finalize_run(context=result)

        return result
