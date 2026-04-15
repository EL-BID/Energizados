"""
Training Step Builder.

This module constructs training pipeline steps from configuration.
"""

from typing import Any, Dict, Optional

from energizados.core.base import PipelineStep
from energizados.core.builders.base import StepBuilder
from energizados.core.steps.training import TrainingStep
from energizados.core.utils import import_class


class TrainingBuilder(StepBuilder):
    """
    Builder for Training pipeline steps.

    Constructs a step that performs feature engineering and model training
    based on the 'training' section of the configuration.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        output_dir: Optional[str] = None,
    ):
        """
        Initialize the builder with configuration.

        Args:
            config: The training configuration
            output_dir: Optional output directory override
        """
        super().__init__(config)
        self.output_dir = output_dir

    def build(self) -> Optional[PipelineStep]:
        """
        Build the Training step from configuration.

        Returns:
            PipelineStep: The training step, or None if not enabled
        """
        train_config = self.config
        if not train_config or not train_config.get("enabled", False):
            return None

        # If user specified a custom class
        if "custom_class" in train_config:
            cls = import_class(train_config["custom_class"])
            return cls(**train_config.get("params", {}))

        # Determine output_dir
        output_dir = self.output_dir or train_config.get("output_dir", "output/models/")

        # Use unified TrainingStep
        models_configs = train_config.get("models", [])
        ensemble_config = train_config.get("ensemble")

        return TrainingStep(
            target_column=train_config.get("target_column", "target"),
            feature_engineering_config=train_config.get("feature_engineering", {}),
            models_configs=models_configs,
            ensemble_config=ensemble_config,
            output_dir=output_dir,
        )

    def is_enabled(self) -> bool:
        """Check if Training step is enabled.

        Returns:
            bool: True if training is enabled in config
        """
        return self.config.get("enabled", False)
