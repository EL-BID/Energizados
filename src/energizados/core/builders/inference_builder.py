"""
Inference Step Builder.

This module constructs inference pipeline steps from configuration.
"""

import logging
from typing import Any, Dict, List, Optional

from energizados.core.base import PipelineStep
from energizados.core.builders.base import StepBuilder
from energizados.core.utils import import_class
from energizados.inference.default import DefaultInference

logger = logging.getLogger(__name__)


class InferenceBuilder(StepBuilder):
    """
    Builder for Inference pipeline steps.

    Constructs a step that makes predictions with trained models
    based on the 'inference' section of the configuration.
    """

    def build(self) -> Optional[PipelineStep]:
        """
        Build the Inference step from configuration.

        Returns:
            PipelineStep: The inference step, or None if not configured
        """
        inference_config = self.config
        if not inference_config:
            return None

        # Read configuration
        input_path = inference_config.get("input_path")
        output_path = inference_config.get("output_path")
        threshold = inference_config.get("threshold", 0.5)
        custom_class = inference_config.get("custom_class")

        # Import inference class
        if custom_class:
            InferenceClass = import_class(custom_class)
        else:
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

    def is_enabled(self) -> bool:
        """Check if Inference step is enabled.

        Returns:
            bool: True if inference config exists
        """
        return bool(self.config)
