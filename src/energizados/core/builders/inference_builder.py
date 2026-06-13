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

        # Read additional filtering configuration
        columns_filter = inference_config.get("columns_filter")
        output_columns = inference_config.get("output_columns")

        # Auto-detect model and feature engineering paths if not specified
        model_path = inference_config.get("model_path")
        feature_engineering_path = inference_config.get("feature_engineering_path")

        if not model_path:
            # Try to auto-detect from latest training run
            model_path = self._auto_detect_latest_run(
                inference_config.get("output_base_dir", "output")
            )

        if not feature_engineering_path and model_path:
            # Auto-detect feature engineering from same run directory
            fe_path = self._auto_detect_feature_engineering(model_path)
            if fe_path:
                feature_engineering_path = fe_path

        class InferenceStep(PipelineStep):
            """Pipeline step for making predictions with trained models."""

            def __init__(
                self,
                inference_engine,
                config,
                columns_filter=None,
                output_columns=None,
            ):
                """Initialize with the inference engine and its configuration.

                Args:
                    inference_engine: Inference object with ``predict`` / ``predict_proba`` methods.
                    config: Inference configuration dict from YAML.
                    columns_filter: Dict of {column_name: [values]} to filter before FE.
                    output_columns: List of column names to include in output CSV.
                """
                self.inference = inference_engine
                self.config = config
                self.columns_filter = columns_filter
                self.output_columns = output_columns

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

                Filtering priority:
                1. Apply columns_filter BEFORE feature engineering (optimization)
                2. Apply output_columns when saving to CSV

                Args:
                    context: Pipeline context dict with at minimum ``model``.

                Returns:
                    Dict: Updated context with ``predictions`` and ``prediction_probas``.
                """
                from energizados.core.utils.secure_pickle import secure_load

                # --- Model resolution: resolved → config → context → error ---
                _model_path = self.config.get("_resolved_model_path") or self.config.get(
                    "model_path"
                )
                if _model_path:
                    model = secure_load(_model_path)
                    logger.info(f"Loaded model from: {_model_path}")
                elif context.get("model"):
                    model = context["model"]
                    logger.info("Using model from context")
                else:
                    raise ValueError(
                        "No model available. Set model_path in infer.yaml or run training first."
                    )

                # --- Feature engineering resolution: resolved → config → context → None ---
                _fe_path = self.config.get("_resolved_feature_engineering_path") or self.config.get(
                    "feature_engineering_path"
                )
                if _fe_path:
                    feature_engineering = secure_load(_fe_path)
                    logger.info(f"Loaded feature engineering from: {_fe_path}")
                elif context.get("feature_engineering"):
                    feature_engineering = context["feature_engineering"]
                    logger.info("Using feature engineering from context")
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
                    logger.info(f"Loaded inference data: {len(data):,} records")
                elif "inference_data" in context:
                    data = context["inference_data"]
                    original_data = data.copy()
                    logger.info(f"Using inference_data from context: {len(data):,} records")
                elif "X_test" in context:
                    data = context["X_test"]
                    original_data = data.copy()
                    logger.info(f"Using X_test from context: {len(data):,} records")
                else:
                    raise ValueError("No inference data found")

                # --- Apply columns_filter BEFORE feature engineering (optimization) ---
                if self.columns_filter:
                    data, filtered_count = self._apply_columns_filter(data)
                    logger.info(
                        f"  • columns_filter: removed {filtered_count:,} rows, {len(data):,} remaining"
                    )

                # --- Apply feature engineering if available ---
                if feature_engineering is not None:
                    data = feature_engineering.transform(data)

                # --- Make predictions ---
                probas = self.inference.predict_proba(model, data)

                # Check if segment thresholds are enabled
                segment_thresholds_config = self.config.get("segment_thresholds", {})
                if segment_thresholds_config and segment_thresholds_config.get("enabled"):
                    # Apply per-row segment thresholds
                    predictions = self._apply_segment_thresholds(
                        probas, data, segment_thresholds_config
                    )
                else:
                    # Use global threshold (backward compatible)
                    predictions = (probas >= self.inference.threshold).astype(int)

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

            def _apply_columns_filter(self, data: pd.DataFrame) -> tuple:
                """Apply columns_filter to data before feature engineering.

                Delegates to the shared ``apply_columns_filter`` utility.

                Args:
                    data: Input DataFrame

                Returns:
                    Tuple of (filtered DataFrame, number of rows removed)
                """
                from energizados.core.utils.columns_filter import apply_columns_filter

                return apply_columns_filter(data, self.columns_filter)

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

                # Apply output_columns filter if specified
                if self.output_columns:
                    available_cols = list(result.columns)
                    valid_cols = [c for c in self.output_columns if c in available_cols]
                    if valid_cols:
                        result = result[valid_cols]
                        logger.info(
                            f"  • output_columns: selected {len(valid_cols)} columns: {valid_cols}"
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

            def _load_segment_thresholds(self, path: str) -> Dict:
                """Load and validate segment thresholds from JSON file.

                Args:
                    path: Path to the segment_thresholds JSON file.

                Returns:
                    Dict: Parsed JSON content with segment thresholds configuration.

                Raises:
                    ValueError: If the JSON file is missing required fields.
                """
                with open(path, "r") as f:
                    config = json.load(f)

                if "segment_column" not in config:
                    raise ValueError(
                        f"Segment thresholds JSON missing required field 'segment_column': {path}"
                    )

                return config

            def _apply_segment_thresholds(
                self,
                probas: np.ndarray,
                data: pd.DataFrame,
                segment_config: Dict,
            ) -> np.ndarray:
                """Apply per-row segment thresholds to probability predictions.

                Loads the segment thresholds JSON, maps each row's segment value
                to its threshold, and returns binary predictions.

                Args:
                    probas: Array of predicted probabilities.
                    data: DataFrame containing the segment column.
                    segment_config: Configuration with 'path' and 'fallback_threshold'.

                Returns:
                    np.ndarray: Binary predictions using per-row thresholds.

                Raises:
                    ValueError: If the segment column is not found in data.
                """
                from energizados.inference.default import apply_segment_thresholds

                # Load the JSON configuration
                json_path = segment_config["path"]
                thresholds_data = self._load_segment_thresholds(json_path)

                segment_column = thresholds_data["segment_column"]

                # Validate that segment column exists in data
                if segment_column not in data.columns:
                    raise ValueError(
                        f"Segment column '{segment_column}' not found in data. "
                        f"Available columns: {list(data.columns)}"
                    )

                # Extract thresholds from nested structure: segments.{value}.threshold
                segments = thresholds_data.get("segments", {})
                thresholds_dict = {
                    segment_value: segment_info.get("threshold", 0.5)
                    for segment_value, segment_info in segments.items()
                }

                # Determine fallback threshold
                fallback = segment_config.get("fallback_threshold")
                if fallback is None:
                    fallback = self.inference.threshold  # Use global threshold

                # Get segment values for each row
                segment_values = data[segment_column]

                # Count statistics for logging
                total_rows = len(data)
                matched_segments = set(segment_values.unique()) & set(thresholds_dict.keys())
                rows_with_segment_threshold = data[
                    segment_values.isin(thresholds_dict.keys())
                ].shape[0]
                rows_with_fallback = total_rows - rows_with_segment_threshold

                logger.info(
                    f"Applying segment thresholds: total={total_rows} rows, "
                    f"{len(matched_segments)} segments matched, "
                    f"{rows_with_segment_threshold} rows use segment thresholds, "
                    f"{rows_with_fallback} rows use fallback ({fallback})"
                )

                # Apply per-row thresholds
                predictions = apply_segment_thresholds(
                    probas, segment_values, thresholds_dict, fallback
                )

                return predictions

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

        # Pass filtering configuration to the step
        inference_config_filtered = inference_config.copy()
        inference_config_filtered["_resolved_model_path"] = model_path
        inference_config_filtered["_resolved_feature_engineering_path"] = feature_engineering_path

        return InferenceStep(
            inference,
            inference_config_filtered,
            columns_filter=columns_filter,
            output_columns=output_columns,
        )

    def _auto_detect_latest_run(self, output_base_dir: str = "output") -> Optional[str]:
        """
        Auto-detect the model path from the latest training run.

        Looks for directories matching 'train-YYYYMMDD_HHMM' and returns
        the most recent one.

        Args:
            output_base_dir: Base directory containing training runs

        Returns:
            Path to model.pkl, or None if no runs found
        """
        output_path = Path(output_base_dir)
        if not output_path.exists():
            logger.warning(f"Output directory not found: {output_base_dir}")
            return None

        # Find all train-* directories
        train_dirs = sorted(
            [d for d in output_path.iterdir() if d.is_dir() and d.name.startswith("train-")],
            key=lambda d: d.name,
            reverse=True,  # Most recent first
        )

        if not train_dirs:
            logger.warning(f"No training runs found in {output_base_dir}")
            return None

        latest_dir = train_dirs[0]
        model_path = latest_dir / "models" / "model.pkl"

        if not model_path.exists():
            # Try ensemble path
            model_path = latest_dir / "models" / "ensemble.pkl"

        if model_path.exists():
            logger.info(f"Auto-detected latest model: {model_path}")
            return str(model_path)

        logger.warning(f"No model found in latest run: {latest_dir}")
        return None

    def _auto_detect_feature_engineering(self, model_path: str) -> Optional[str]:
        """
        Auto-detect feature engineering path from model path.

        Assumes model is in output/train-YYYYMMDD_HHMM/models/ and
        looks for feature_engineering.pkl in the same directory.

        Args:
            model_path: Path to the model file

        Returns:
            Path to feature_engineering.pkl, or None if not found
        """
        model_dir = Path(model_path).parent
        fe_path = model_dir / "feature_engineering.pkl"

        if fe_path.exists():
            logger.info(f"Auto-detected feature engineering: {fe_path}")
            return str(fe_path)

        return None

    def is_enabled(self) -> bool:
        """Check if Inference step is enabled.

        Returns:
            bool: True if inference config exists
        """
        return bool(self.config)
