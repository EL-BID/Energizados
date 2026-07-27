"""
Pipeline Director.

This module orchestrates the construction of pipeline steps using builders.
It follows the Builder pattern, delegating step construction to specialized builders.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from energizados.core.utils.yaml_utils import load_yaml_config

logger = logging.getLogger(__name__)


def _load_yaml_config(path: str) -> Dict:
    return load_yaml_config(path)


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
        overwrite: bool = False,
        run_type: Optional[str] = None,
        derived_from: Optional[str] = None,
    ):
        """
        Initialize the director.

        Args:
            config_path: Path to the YAML configuration file (optional)
            config: Configuration dictionary (optional, takes precedence over config_path)
            config_paths: List of all config files used (for copying to run dir)
            run_name: Optional custom run directory name
            overwrite: If True, overwrite existing run directory
            run_type: ADR-0001 optional explicit run type. When None (default),
                the type is computed from the config in ``build()`` by priority
                ``training > inference > eda > etl``.
            derived_from: ADR-0003 optional source run_id for retrain lineage.
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
        self._overwrite: bool = overwrite
        self._explicit_run_type: Optional[str] = run_type
        self.run_manager = RunManager(
            self.config_paths,
            run_name=run_name,
            overwrite=overwrite,
            run_type=run_type if run_type is not None else "training",
            derived_from=derived_from,
        )
        self._run_dir: Optional[Path] = None

        # Validate configuration against schema
        self._validate_config()

    def _compute_run_type(self) -> str:
        """Compute the single run type for this config (ADR-0001).

        Priority ``training > inference > eda > etl`` so a merged etl+train
        config stays a training run (preserves today's behavior). Only PURE
        non-training configs get a typed run dir.

        Returns:
            One of ``training``/``inference``/``eda``/``etl``.
        """
        train_config = self.config.get("train", {})
        eval_config = train_config.get("evaluation", {}) or self.config.get("evaluation", {})
        if train_config.get("enabled", False) or eval_config.get("enabled", False):
            return "training"
        if self.config.get("infer", {}).get("enabled", False):
            return "inference"
        if self.config.get("eda", {}).get("enabled", False):
            return "eda"
        if self.config.get("etl"):
            return "etl"
        return "training"

    def _resolve_base_output_dir(self) -> str:
        """Resolve the base output directory (ADR-0001).

        Checks ``train``/``infer``/``eda`` sections for ``output_base_dir`` in
        that order; defaults to ``output``. The worker has already chdir'd into
        the project, so relative paths resolve under the project root.
        """
        for section in ("train", "infer", "eda"):
            cfg = self.config.get(section, {})
            if isinstance(cfg, dict) and cfg.get("output_base_dir"):
                return cfg["output_base_dir"]
        return "output"

    def _has_enabled_section(self) -> bool:
        """True if any pipeline section is enabled (ADR-0001 run-dir gate)."""
        train_config = self.config.get("train", {})
        eval_config = train_config.get("evaluation", {}) or self.config.get("evaluation", {})
        if train_config.get("enabled", False) or eval_config.get("enabled", False):
            return True
        if self.config.get("infer", {}).get("enabled", False):
            return True
        if self.config.get("eda", {}).get("enabled", False):
            return True
        if self.config.get("etl"):
            return True
        return False

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

        # ADR-0001: create a typed run directory when ANY enabled section is
        # present (not just training/evaluation). Compute ONE run_type by
        # priority before generate_run_dir so the prefix is correct.
        if self._has_enabled_section():
            run_type = self._explicit_run_type or self._compute_run_type()
            self.run_manager._run_type = run_type
            base_output_dir = self._resolve_base_output_dir()
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
            split_method = split_config.get("method", "stratified")
            if split_method == "none":
                logger.warning(
                    "Evaluation is enabled but split.method is 'none' — no test set "
                    "available. Skipping evaluation step automatically."
                )
            else:
                eval_output_dir = (
                    str(self._run_dir / "reports" / "evaluation") if self._run_dir else None
                )
                experiment_description = self.config.get("train", {}).get("description")
                eval_builder = EvaluationBuilder(
                    eval_config, eval_output_dir, experiment_description=experiment_description
                )
                eval_step = eval_builder.build()
                if eval_step is not None:
                    pipeline.add_step(eval_step)


        # Step 5: Inference (ADR-0001: predictions relocate into the run dir)
        if self.config.get("infer", {}).get("enabled", False):
            inference_builder = InferenceBuilder(
                self.config.get("infer", {}), run_dir=self._run_dir
            )
            inference_step = inference_builder.build()
            if inference_step is not None:
                pipeline.add_step(inference_step)

        # Step 6: EDA (ADR-0001: report relocates into the run dir)
        if self.config.get("eda", {}).get("enabled", False):
            eda_builder = EDABuilder(self.config.get("eda", {}), run_dir=self._run_dir)
            eda_step = eda_builder.build()
            if eda_step is not None:
                pipeline.add_step(eda_step)

        return pipeline

    def run(self, progress_callback: Optional[Any] = None) -> Dict[str, Any]:
        """
        Convenience method: builds and runs the pipeline, then performs post-run tasks.

        Post-run tasks:
        - Copies config files to the run directory
        - Regenerates output/index.html

        If pipeline fails, cleans up empty run directories.

        Args:
            progress_callback: Optional callback invoked with ProgressEvent objects,
                forwarded to Pipeline.run. Used by the web worker to stream live
                job progress to the SSE endpoint.

        Returns:
            Dict: Final context with pipeline results
        """
        pipeline = self.build()

        try:
            result = pipeline.run(progress_callback=progress_callback)
        except Exception:
            # Clean up empty run directory on failure
            self._cleanup_failed_run()
            raise

        # Run post-build tasks
        self.run_manager.finalize_run(context=result)

        return result

    def _cleanup_failed_run(self) -> None:
        """
        Clean up run directory if it's empty after a failed pipeline.

        Removes the run directory only if:
        - It exists
        - It contains only empty subdirectories or no files
        - Useful outputs (models, reports, metadata) were not created

        This prevents orphaned empty directories from failed runs.
        """
        run_dir = self.run_manager.run_dir
        if run_dir is None or not run_dir.exists():
            return

        # Check if directory has any meaningful content
        has_models = (run_dir / "models").exists() and any((run_dir / "models").iterdir())
        has_reports = (run_dir / "reports").exists() and any((run_dir / "reports").rglob("*"))
        has_metadata = (run_dir / "run_metadata.json").exists()
        has_config = (run_dir / "config").exists() and any((run_dir / "config").iterdir())

        # Only clean up if NO useful content was created
        if not has_models and not has_reports and not has_metadata and not has_config:
            import shutil

            logger.warning(
                f"Pipeline failed with no output created. Removing empty run directory: {run_dir}"
            )
            shutil.rmtree(run_dir)
        else:
            # Some files exist - log what was saved before failure
            logger.warning(
                f"Pipeline failed. Run directory preserved with partial output: {run_dir}"
            )
            if has_models:
                logger.warning("  -> models/ directory contains files")
            if has_reports:
                logger.warning("  -> reports/ directory contains files")
            if has_metadata:
                logger.warning("  -> run_metadata.json exists")
            if has_config:
                logger.warning("  -> config/ directory contains files")
