"""
Evaluation Step Builder.

This module constructs evaluation pipeline steps from configuration.
"""

from typing import Any, Dict, Optional

from energizados.core.base import PipelineStep
from energizados.core.builders.base import StepBuilder
from energizados.core.utils import import_class


class EvaluationBuilder(StepBuilder):
    """
    Builder for Evaluation pipeline steps.

    Constructs a step that evaluates trained models and generates reports
    based on the 'evaluation' section of the training configuration.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        output_dir: Optional[str] = None,
        experiment_description: Optional[str] = None,
    ):
        """
        Initialize the builder with configuration.

        Args:
            config: The evaluation configuration
            output_dir: Optional output directory override
            experiment_description: Free-text description of the experiment (from train.description)
        """
        super().__init__(config)
        self.output_dir = output_dir
        self.experiment_description = experiment_description

    def build(self) -> Optional[PipelineStep]:
        """
        Build the Evaluation step from configuration.

        Returns:
            PipelineStep: The evaluation step, or None if not enabled
        """
        eval_config = self.config
        if not eval_config or not eval_config.get("enabled", False):
            return None

        # If user specified a custom class
        if "custom_class" in eval_config:
            cls = import_class(eval_config["custom_class"])
            return cls(**eval_config.get("params", {}))

        # Determine output_dir
        output_dir = self.output_dir or eval_config.get("output_dir", "output/reports/evaluation/")

        # When running inside the same pipeline as TrainingStep, don't pass model_path
        # so that DefaultEvaluator picks it up from context (avoids validate_input failure)
        model_path = eval_config.get("model_path")
        fe_path = eval_config.get("feature_engineering_path")

        # Lazy import to avoid module-level cycle
        from energizados.evaluation import DefaultEvaluator

        # Use DefaultEvaluator
        return DefaultEvaluator(
            input_path=eval_config.get("input_path"),
            model_path=model_path,
            feature_engineering_path=fe_path,
            output_dir=output_dir,
            target_column=eval_config.get("target_column", "target"),
            threshold=eval_config.get("threshold", 0.5),
            metrics=eval_config.get("metrics"),
            generate_plots=eval_config.get("generate_plots", True),
            generate_html_report=eval_config.get("generate_html_report", True),
            generate_json_report=eval_config.get("generate_json_report", True),
            calibration_config=eval_config.get("calibration"),
            shap_config=eval_config.get("shap"),
            segment_columns=eval_config.get("segment_columns"),
            experiment_description=self.experiment_description,
            segmented_evaluation=eval_config.get("segmented_evaluation"),
        )

    def is_enabled(self) -> bool:
        """Check if Evaluation step is enabled.

        Returns:
            bool: True if evaluation is enabled in config
        """
        return self.config.get("enabled", False)
