"""
Inference Step Builder.

This module constructs inference pipeline steps from configuration.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

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
                """Validate that a model is available — either from config path or context.

                Args:
                    context: Pipeline context dict.

                Returns:
                    bool: True if model is available via config path or context.
                """
                if self.config.get("model_path"):
                    return True
                return "model" in context and context["model"] is not None

            def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                """Run inference and store predictions in context.

                Uses a config-first resolution chain:
                1. Load model from config ``model_path`` via ``secure_load``
                2. Fall back to ``context["model"]``
                3. Raise ``ValueError`` if neither is available

                Same pattern for feature_engineering.

                Args:
                    context: Pipeline context dict with at minimum ``model``.

                Returns:
                    Dict: Updated context with ``predictions`` and ``prediction_probas``.
                """
                from energizados.core.utils.secure_pickle import secure_load

                # --- Model resolution: config path → context → error ---
                _model_path = self.config.get("model_path")
                if _model_path:
                    model = secure_load(_model_path)
                elif context.get("model"):
                    model = context["model"]
                else:
                    raise ValueError(
                        "No model available. Set model_path in infer.yaml or run training first."
                    )

                # --- Feature engineering resolution: config path → context → None ---
                _fe_path = self.config.get("feature_engineering_path")
                if _fe_path:
                    feature_engineering = secure_load(_fe_path)
                elif context.get("feature_engineering"):
                    feature_engineering = context["feature_engineering"]
                else:
                    feature_engineering = None
                    logger.warning("No feature engineering pipeline found. Using raw features.")

                # --- Load inference data ---
                _input_path = self.config.get("input_path")
                _output_path = self.config.get("output_path")
                if _input_path:
                    data = pd.read_parquet(_input_path)
                    # Keep original input for enrichment
                    original_data = data.copy()
                elif "inference_data" in context:
                    data = context["inference_data"]
                    original_data = data.copy()
                elif "X_test" in context:
                    data = context["X_test"]
                    original_data = data.copy()
                else:
                    raise ValueError("No inference data found")

                # --- Apply feature engineering if available ---
                if feature_engineering is not None:
                    data = feature_engineering.transform(data)

                # --- Make predictions ---
                predictions = self.inference.predict(model, data)
                probas = self.inference.predict_proba(model, data)

                # --- Save to context ---
                context["predictions"] = predictions
                context["prediction_probas"] = probas

                # --- Enriched output ---
                if _output_path:
                    _include_input = self.config.get("output_include_input", False)
                    _fmt = self.config.get("output_format", "csv")

                    self._save_output(
                        original_data,
                        predictions,
                        probas,
                        _output_path,
                        _include_input,
                        _fmt,
                    )
                    self._write_metadata_sidecar(
                        _output_path,
                        _model_path,
                        predictions,
                        _fmt,
                        _include_input,
                    )
                    logger.info(f"Predictions saved to: {_output_path}")

                return context

            def _save_output(
                self,
                original_data: pd.DataFrame,
                predictions: np.ndarray,
                probas: np.ndarray,
                output_path: str,
                include_input: bool,
                output_format: str,
            ) -> None:
                """Save predictions in enriched or minimal format.

                Args:
                    original_data: Original input DataFrame (before FE transform).
                    predictions: Binary predictions array.
                    probas: Probability predictions array.
                    output_path: File path for output.
                    include_input: If True, prepend original columns.
                    output_format: "csv" or "parquet".
                """
                result = pd.DataFrame(
                    {
                        "prediction": predictions,
                        "probability": probas,
                    }
                )

                if include_input:
                    result = pd.concat([original_data.reset_index(drop=True), result], axis=1)

                Path(output_path).parent.mkdir(parents=True, exist_ok=True)

                if output_format == "parquet":
                    result.to_parquet(output_path, index=False)
                else:
                    result.to_csv(output_path, index=False)

            def _write_metadata_sidecar(
                self,
                output_path: str,
                model_path: Optional[str],
                predictions,
                output_format: str,
                include_input: bool,
            ) -> None:
                """Write a .metadata.json sidecar next to the output file.

                Args:
                    output_path: Path to the predictions output file.
                    model_path: Path to the model file (for .sig hash lookup).
                    predictions: Predictions array (used for row count).
                    output_format: "csv" or "parquet".
                    include_input: Whether input columns were included.
                """
                # Read model hash from .sig file if available
                model_hash = None
                if model_path:
                    sig_path = Path(str(model_path) + ".sig")
                    if sig_path.exists():
                        model_hash = sig_path.read_text().strip()

                metadata = {
                    "model_hash": model_hash,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "threshold": self.inference.threshold,
                    "row_count": len(predictions),
                    "output_format": output_format,
                    "include_input": include_input,
                }

                metadata_path = Path(str(output_path) + ".metadata.json")
                metadata_path.write_text(json.dumps(metadata, indent=2))

            def get_required_keys(self) -> List[str]:
                """Return the required context keys for inference.

                Returns:
                    List[str]: ``["model"]`` (optional if model_path in config).
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
