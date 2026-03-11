"""
Pipeline Orchestrator for the Energizados Framework.

This module contains the classes that orchestrate the execution of the ML workflow,
coordinating the different pipeline steps.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from energizados.core.base import PipelineStep
from energizados.core.exceptions import (
    ConfigurationError,
    PipelineError,
    StepValidationError,
)
from energizados.core.utils import import_class

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
        raise ConfigurationError(f"Error parsing YAML: {e}", path)


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

            # Validate input
            if not step.validate_input(self.context):
                missing_keys = step.get_required_keys()
                raise StepValidationError(f"Validation failed in step {step_name}", step=step_name, missing_keys=missing_keys)

            # Execute step
            try:
                self.context = step.execute(self.context)
                logger.info(f"✓ Step {step_name} completed")
            except Exception as e:
                raise PipelineError(f"Error executing step {step_name}: {e}", step=step_name)

        logger.info(f"\n{'=' * 60}")
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info(f"{'=' * 60}")

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


class ConfigPipelineBuilder:
    """
    Pipeline builder from YAML configuration.

    This class reads a YAML configuration file and automatically
    builds the pipeline with the corresponding steps.

    Args:
        config_path: Path to the YAML configuration file

    Example:
        >>> builder = ConfigPipelineBuilder("config.yaml")
        >>> pipeline = builder.build()
        >>> results = pipeline.run()
    """

    # Registries will be populated dynamically
    MODEL_REGISTRY = {}
    SELECTOR_REGISTRY = {}
    ETL_REGISTRY = {}
    PREPROCESSOR_REGISTRY = {}
    INFERENCE_REGISTRY = {}

    def __init__(self, config_path: str = None, config: Dict = None, config_paths: List[str] = None):
        """
        Initialize the builder.

        Args:
            config_path: Path to the YAML configuration file (optional)
            config: Configuration dictionary (optional, takes precedence over config_path)
            config_paths: List of all config files used (for copying to run dir)
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
        self._run_dir: Optional[Path] = None

    def _load_config(self, path: str) -> Dict:
        """
        Load configuration from YAML.

        Args:
            path: Path to the YAML file

        Returns:
            Dict: Loaded configuration
        """
        return _load_yaml_config(path)

    def _generate_run_dir(self, base_output_dir: str = "output") -> Path:
        """
        Creates a timestamped run directory inside the output base directory.

        Args:
            base_output_dir: Base output directory (default: "output")

        Returns:
            Path to the created run directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        run_name = f"train-{timestamp}"
        base = Path(base_output_dir)
        run_dir = base / run_name

        # Handle timestamp collisions atomically (avoid TOCTOU race)
        import os

        suffix = 0
        while True:
            candidate = run_dir if suffix == 0 else base / f"{run_name}_{suffix}"
            try:
                os.makedirs(candidate)
                run_dir = candidate
                break
            except FileExistsError:
                suffix += 1

        (run_dir / "models").mkdir(parents=True, exist_ok=True)
        (run_dir / "reports" / "evaluation").mkdir(parents=True, exist_ok=True)
        (run_dir / "config").mkdir(parents=True, exist_ok=True)

        logger.info(f"Training run directory: {run_dir}")
        return run_dir

    def _copy_configs_to_run_dir(self):
        """Copies the config files used for this run into the run directory."""
        if self._run_dir is None:
            return
        config_target = self._run_dir / "config"
        for config_path in self.config_paths:
            src = Path(config_path)
            if src.exists():
                shutil.copy(src, config_target / src.name)
                logger.info(f"Config copied to run dir: {src.name}")

    def _generate_index_html(self):
        """Regenerates output/index.html with all training runs."""
        if self._run_dir is None:
            return
        from energizados.evaluation.index import RunIndexGenerator

        output_dir = self._run_dir.parent
        generator = RunIndexGenerator()
        index_path = generator.generate_index_html(output_dir)
        if index_path:
            logger.info(f"Index HTML updated: {index_path}")

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

        if self._run_dir is not None:
            self._copy_configs_to_run_dir()
            self._generate_index_html()

        return result

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
        train_config = self.config.get("training", {})
        eval_config = train_config.get("evaluation", {}) or self.config.get("evaluation", {})
        if train_config.get("enabled", False) or eval_config.get("enabled", False):
            base_output_dir = train_config.get("output_base_dir", "output")
            self._run_dir = self._generate_run_dir(base_output_dir)

        # Step 1: ETL (multiple ETLs with dependencies)
        if "etls" in self.config:
            etl_step = self._build_etl_step()
            if etl_step is not None:
                pipeline.add_step(etl_step)

        # Step 2: Split (divide data into train/val/test)
        # Look for configuration in training.split or split (legacy)
        split_config = self.config.get("training", {}).get("split", {})
        if not split_config:
            split_config = self.config.get("split", {})
        if split_config:
            split_step = self._build_split_step()
            if split_step is not None:
                pipeline.add_step(split_step)

        # Step 3: Training (unified: feature_engineering + model)
        train_config = self.config.get("training", {})
        if train_config.get("enabled", False):
            train_step = self._build_training_step()
            if train_step is not None:
                pipeline.add_step(train_step)

        # Step 4: Evaluation
        eval_config = self.config.get("training", {}).get("evaluation", {})
        if not eval_config:
            eval_config = self.config.get("evaluation", {})
        if eval_config.get("enabled", False):
            eval_step = self._build_evaluation_step()
            if eval_step is not None:
                pipeline.add_step(eval_step)

        # Step 6: Inference
        if self.config.get("inference", {}).get("enabled", False):
            inference_step = self._build_inference_step()
            if inference_step is not None:
                pipeline.add_step(inference_step)

        # Step EDA: Exploratory Data Analysis
        if self.config.get("eda", {}).get("enabled", False):
            eda_step = self._build_eda_step()
            if eda_step is not None:
                pipeline.add_step(eda_step)

        return pipeline

    def _build_etl_step(self) -> Optional[PipelineStep]:
        """
        Build the ETL step from the configuration.

        Uses multiple ETLs with dependencies (section 'etls:').

        Returns:
            PipelineStep: ETL step or None if not configured
        """
        if "etls" in self.config:
            return self._build_multi_etl_step()
        return None

    def _build_multi_etl_step(self) -> Optional[PipelineStep]:
        """
        Build a step that orchestrates multiple ETLs with dependencies.

        Returns:
            PipelineStep: ETLStep or None if no ETLs are configured
        """
        from energizados.core.base import PipelineStep
        from energizados.etl.orchestrator import ETLOrchestrator

        etl_configs = self.config.get("etls", {})
        if not etl_configs:
            return None

        orchestrator = ETLOrchestrator(etl_configs)

        class ETLStep(PipelineStep):
            """Pipeline step that executes multiple ETLs."""

            def __init__(self, orchestrator: ETLOrchestrator):
                self.orchestrator = orchestrator

            def validate_input(self, context: Dict[str, Any]) -> bool:
                """Return True; ETLs read from disk and require no prior context.

                Args:
                    context: Pipeline context dict (unused).

                Returns:
                    bool: Always True.
                """
                # ETLs do not require previous input from context
                return True

            def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                """Run all ETLs via the orchestrator and populate context.

                Args:
                    context: Pipeline context dict.

                Returns:
                    Dict: Updated context with ``data`` (last ETL output) and
                        ``etl_results`` (all ETL outputs).
                """
                # Execute all ETLs in topological order
                results = self.orchestrator.run()

                # Pass the output of the last ETL to context
                if self.orchestrator.execution_order:
                    last_etl = self.orchestrator.execution_order[-1]
                    context["data"] = results[last_etl]

                context["etl_results"] = results
                return context

            def get_required_keys(self) -> List[str]:
                """Return empty list; ETLStep has no required context keys.

                Returns:
                    List[str]: Empty list.
                """
                return []

        return ETLStep(orchestrator)

    def _build_split_step(self) -> Optional[PipelineStep]:
        """
        Build the split step from the configuration.

        Returns:
            PipelineStep: Split step or None if not configured
        """
        from energizados.core.steps.split import SplitStep

        # Look for configuration in training.split or split (legacy)
        split_config = self.config.get("training", {}).get("split", {})
        if not split_config:
            split_config = self.config.get("split", {})

        if not split_config:
            return None

        # Determine input_path
        input_path = split_config.get("input_path")
        if not input_path:
            # Also look at training level (global)
            input_path = self.config.get("training", {}).get("input_path")
        if not input_path and "etls" in self.config:
            # Use last ETL output if it exists
            etl_configs = self.config.get("etls", {})
            if etl_configs:
                last_etl = list(etl_configs.keys())[-1]
                # input_path will be @etl_name
                input_path = f"@{last_etl}"

        # If it's a reference @etl_name, we process it later
        # For now, return the split_step with the input_path

        target_column = split_config.get("target_column") or self.config.get("training", {}).get("target_column", "target")

        return SplitStep(
            input_path=input_path,
            target_column=target_column,
            test_size=split_config.get("test_size", 0.2),
            val_size=split_config.get("val_size", 0.1),
            random_state=split_config.get("random_state", 42),
            splits_dir=split_config.get("splits_dir", "data/splits/"),
            method=split_config.get("method", "stratified"),
            date_column=split_config.get("date_column"),
            train_period=split_config.get("train_period"),
            val_period=split_config.get("val_period"),
            test_period=split_config.get("test_period"),
            save_splits=split_config.get("save_splits", True),
        )

    def _build_training_step(self) -> Optional[PipelineStep]:
        """
        Build the training step from the configuration.

        Returns:
            PipelineStep: Training step or None if not configured
        """
        from energizados.core.steps.training import TrainingStep

        train_config = self.config.get("training", {})
        if not train_config or not train_config.get("enabled", False):
            return None

        # If user specified a custom class
        if "custom_class" in train_config:
            cls = import_class(train_config["custom_class"])
            return cls(**train_config.get("params", {}))

        # Determine output_dir: use run dir if available, else config value
        if self._run_dir is not None:
            output_dir = str(self._run_dir / "models")
        else:
            output_dir = train_config.get("output_dir", "output/models/")

        # Use unified TrainingStep
        return TrainingStep(
            target_column=train_config.get("target_column", "target"),
            feature_engineering_config=train_config.get("feature_engineering", {}),
            model_config=train_config.get("model", {}),
            output_dir=output_dir,
        )

    def _build_evaluation_step(self) -> Optional[PipelineStep]:
        """
        Build the evaluation step from the configuration.

        Returns:
            PipelineStep: Evaluation step or None if not configured
        """
        from energizados.evaluation import DefaultEvaluator

        # Look for configuration in training.evaluation or evaluation (legacy)
        eval_config = self.config.get("training", {}).get("evaluation", {})
        if not eval_config:
            eval_config = self.config.get("evaluation", {})

        if not eval_config or not eval_config.get("enabled", False):
            return None

        # If user specified a custom class
        if "custom_class" in eval_config:
            cls = import_class(eval_config["custom_class"])
            return cls(**eval_config.get("params", {}))

        # Determine output_dir: use run dir if available, else config value
        if self._run_dir is not None:
            eval_output_dir = str(self._run_dir / "reports" / "evaluation")
        else:
            eval_output_dir = eval_config.get("output_dir", "output/reports/evaluation/")

        # When running inside the same pipeline as TrainingStep, don't pass model_path
        # so that DefaultEvaluator picks it up from context (avoids validate_input failure)
        model_path = eval_config.get("model_path")
        fe_path = eval_config.get("feature_engineering_path")

        # Use DefaultEvaluator
        return DefaultEvaluator(
            input_path=eval_config.get("input_path"),
            model_path=model_path,
            feature_engineering_path=fe_path,
            output_dir=eval_output_dir,
            target_column=eval_config.get("target_column", "target"),
            threshold=eval_config.get("threshold", 0.5),
            metrics=eval_config.get("metrics"),
            generate_plots=eval_config.get("generate_plots", True),
            generate_html_report=eval_config.get("generate_html_report", True),
            generate_json_report=eval_config.get("generate_json_report", True),
            calibration_config=eval_config.get("calibration"),
        )

    def _build_inference_step(self) -> Optional[PipelineStep]:
        """
        Build the inference step from the configuration.

        Returns:
            PipelineStep: Inference step or None if not configured
        """
        from energizados.core.base import PipelineStep

        inference_config = self.config.get("inference", {})
        if not inference_config:
            return None

        # Read configuration
        input_path = inference_config.get("input_path")
        output_path = inference_config.get("output_path")
        threshold = inference_config.get("threshold", 0.5)
        custom_class = inference_config.get("custom_class")

        # Import inference class
        if custom_class:
            from energizados.core.utils import import_class

            InferenceClass = import_class(custom_class)
        else:
            from energizados.inference.default import DefaultInference

            InferenceClass = DefaultInference

        inference = InferenceClass(threshold=threshold)

        class InferenceStep(PipelineStep):
            """Pipeline step for making predictions with trained models."""

            def __init__(self, inference_engine, config):
                """Initialize with the inference engine and its configuration.

                Args:
                    inference_engine: Inference object with ``predict`` / ``predict_proba`` methods.
                    config: Inference configuration dict from YAML.
                """
                self.inference = inference_engine
                self.config = config

            def validate_input(self, context: Dict[str, Any]) -> bool:
                """Validate that a trained model is present in context.

                Args:
                    context: Pipeline context dict.

                Returns:
                    bool: True if ``model`` key is present and non-None.
                """
                return "model" in context and context["model"] is not None

            def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                """Run inference and store predictions in context.

                Args:
                    context: Pipeline context dict with at minimum ``model``.

                Returns:
                    Dict: Updated context with ``predictions`` and ``prediction_probas``.
                """
                model = context.get("model")

                # Get inference data
                if input_path:
                    import pandas as pd

                    data = pd.read_parquet(input_path)
                elif "inference_data" in context:
                    data = context["inference_data"]
                elif "X_test" in context:
                    data = context["X_test"]
                else:
                    raise ValueError("No inference data found")

                # Apply feature engineering if available
                feature_engineering = context.get("feature_engineering")
                if feature_engineering is not None:
                    data = feature_engineering.transform(data)

                # Make predictions
                predictions = self.inference.predict(model, data)
                probas = self.inference.predict_proba(model, data)

                # Save to context
                context["predictions"] = predictions
                context["prediction_probas"] = probas

                # Save to file if output_path specified
                if output_path:
                    self.inference.save_predictions(predictions, output_path)
                    logger.info(f"Predictions saved to: {output_path}")

                return context

            def get_required_keys(self) -> List[str]:
                """Return the required context keys for inference.

                Returns:
                    List[str]: ``["model"]``.
                """
                return ["model"]

            def get_output_keys(self) -> List[str]:
                """Return the context keys produced by this step.

                Returns:
                    List[str]: ``["predictions", "prediction_probas"]``.
                """
                return ["predictions", "prediction_probas"]

        return InferenceStep(inference, inference_config)

    def _build_eda_step(self) -> Optional[PipelineStep]:
        """
        Build the EDA step from the configuration.

        Returns:
            PipelineStep: EDA step or None if not configured
        """
        from energizados.core.base import PipelineStep

        eda_config = self.config.get("eda", {})
        if not eda_config:
            return None

        full_config = self.config

        class EDAStep(PipelineStep):
            """Pipeline step that runs Exploratory Data Analysis."""

            def validate_input(self, context: Dict[str, Any]) -> bool:
                return True

            def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                from energizados.eda.dataset_explorer import DatasetExplorer

                col_detection = eda_config.get("column_detection", {})
                data_sources = eda_config.get("data_sources", {})
                primary = data_sources.get("primary", {})
                output_cfg = eda_config.get("output", {})

                explorer = DatasetExplorer(
                    input_path=primary.get("path", ""),
                    target_column=primary.get("target_col"),
                    id_column=col_detection.get("id_col"),
                    date_column=col_detection.get("date_col"),
                    lat_column=col_detection.get("lat_col"),
                    lon_column=col_detection.get("lon_col"),
                    zone_column=col_detection.get("zone_col"),
                    periods_suffix=col_detection.get("periods_suffix", "_anterior"),
                    output_dir=output_cfg.get("output_dir", "output/eda/"),
                    sections=eda_config.get("sections"),
                    config=full_config,
                )
                results = explorer.run()
                context["eda_results"] = results
                return context

            def get_required_keys(self) -> List[str]:
                return []

        return EDAStep()

    @classmethod
    def register_model(cls, name: str, model_class: type):
        """
        Register a model in the registry.

        Args:
            name: Model name
            model_class: Model class
        """
        cls.MODEL_REGISTRY[name] = model_class

    @classmethod
    def register_selector(cls, name: str, selector_class: type):
        """
        Register a selector in the registry.

        Args:
            name: Selector name
            selector_class: Selector class
        """
        cls.SELECTOR_REGISTRY[name] = selector_class

    @classmethod
    def register_etl(cls, name: str, etl_class: type):
        """
        Register an ETL in the registry.

        Args:
            name: ETL name
            etl_class: ETL class
        """
        cls.ETL_REGISTRY[name] = etl_class

    @classmethod
    def register_preprocessor(cls, name: str, preprocessor_class: type):
        """
        Register a preprocessor in the registry.

        Args:
            name: Preprocessor name
            preprocessor_class: Preprocessor class
        """
        cls.PREPROCESSOR_REGISTRY[name] = preprocessor_class

    @classmethod
    def register_inference(cls, name: str, inference_class: type):
        """
        Register an inference class in the registry.

        Args:
            name: Inference class name
            inference_class: Inference class
        """
        cls.INFERENCE_REGISTRY[name] = inference_class
