"""
Default inference implementation for Energizados Framework.

Default inference implementation that allows loading models,
making predictions, and saving results.
"""

from pathlib import Path
from typing import Dict, Optional, cast

import numpy as np
import pandas as pd

from energizados.core.base import BaseInference, BaseModel


class DefaultInference(BaseInference):
    """
    Default inference implementation.

    This class provides standard functionality for:
    - Loading trained models from pickle files
    - Making binary and probability predictions
    - Saving predictions to CSV files

    Args:
        model_path: Path to the trained model file.
        threshold: Threshold for binary predictions (default: 0.5).

    Example:
        >>> from energizados.inference import DefaultInference
        >>> inference = DefaultInference(model_path="models/model.pkl")
        >>> model = inference.load_model()
        >>> predictions = inference.predict(model, data)
    """

    def __init__(self, model_path: Optional[str] = None, threshold: float = 0.5):
        """
        Initialize the inference engine.

        Args:
            model_path: Path to the trained model file.
            threshold: Threshold for binary predictions (default: 0.5).
        """
        self.model_path = model_path
        self.threshold = threshold
        self.model: Optional[BaseModel] = None

    def load_model(self, model_path: Optional[str] = None) -> BaseModel:
        """
        Load a trained model from a pickle file.

        SECURITY NOTE: Only load models from trusted sources. Pickle can execute
        arbitrary code during deserialization. This is the standard method for
        ML model serialization in the Python/scikit-learn ecosystem.

        Args:
            model_path: Path to the model file (uses self.model_path if None).

        Returns:
            BaseModel: The loaded model.

        Raises:
            ValueError: If no valid path is provided.
            FileNotFoundError: If the file does not exist.
        """
        from energizados.core.utils.secure_pickle import secure_load

        path: Optional[str] = model_path or self.model_path
        if not path:
            raise ValueError("No model path provided")

        loaded = secure_load(path)
        # ``secure_load`` is dynamically typed (untyped return); narrow it to
        # ``BaseModel`` for downstream consumers and the type checker.
        self.model = cast(BaseModel, loaded)
        return self.model

    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Make binary predictions.

        Converts probabilities to binary predictions using the configured threshold.

        Args:
            model: Trained model.
            data: Data for prediction.

        Returns:
            np.ndarray: Binary predictions (0 or 1).
        """
        proba = self.predict_proba(model, data)
        return (proba >= self.threshold).astype(int)

    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            model: Trained model.
            data: Data for prediction.

        Returns:
            np.ndarray: Probabilities of the positive class.
        """
        return model.predict_proba(data)

    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """
        Save predictions to a CSV file.

        Creates the parent directory if it does not exist.

        Args:
            predictions: Predictions to save.
            output_path: Output path.
        """
        from energizados.core.utils.secure_pickle import validate_no_traversal

        validate_no_traversal(output_path, label="inference output_path")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"prediction": predictions}).to_csv(output_path, index=False)

    def save_predictions_with_proba(
        self,
        predictions: np.ndarray,
        probas: np.ndarray,
        output_path: str,
    ) -> None:
        """
        Save binary predictions and probabilities to a CSV file.

        Args:
            predictions: Binary predictions.
            probas: Probabilities.
            output_path: Output path.
        """
        from energizados.core.utils.secure_pickle import validate_no_traversal

        validate_no_traversal(output_path, label="inference output_path")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "prediction": predictions,
                "probability": probas,
            }
        ).to_csv(output_path, index=False)


def apply_segment_thresholds(
    probas: np.ndarray,
    segment_values: pd.Series,
    thresholds_dict: Dict[str, float],
    fallback_threshold: float,
) -> np.ndarray:
    """Apply per-segment thresholds to probability predictions.

    Maps each row's segment value to its specific threshold from thresholds_dict.
    Rows with unknown segment values use the fallback_threshold.

    Args:
        probas: Array of predicted probabilities (positive class).
        segment_values: Series containing segment value for each row.
        thresholds_dict: Dictionary mapping segment values to their thresholds.
        fallback_threshold: Threshold to use for segment values not in thresholds_dict.

    Returns:
        np.ndarray: Binary predictions (0 or 1) based on per-row thresholds.

    Example:
        >>> probas = np.array([0.4, 0.6, 0.3])
        >>> segments = pd.Series(["Norte", "Sul", "Norte"])
        >>> thresholds = {"Norte": 0.3, "Sul": 0.7}
        >>> apply_segment_thresholds(probas, segments, thresholds, 0.5)
        array([1, 0, 0])  # Norte: 0.4>=0.3->1, 0.3<0.3->0; Sul: 0.6<0.7->0
    """
    # Map each row's segment value to its threshold
    row_thresholds = segment_values.map(lambda x: thresholds_dict.get(x, fallback_threshold))

    # Coerce to a plain float ndarray. When ``segment_values`` is a pandas
    # ``Categorical`` (common for columns like ``geo_region`` / ``zona`` read
    # from parquet), ``Series.map`` preserves the Categorical dtype, and
    # ``np.ndarray >= Categorical`` raises "Unordered Categoricals can only
    # compare equality or not" inside the ufunc dispatch. Forcing a float
    # array sidesteps the Categorical comparison path while keeping the
    # original behaviour for object/string segments.
    row_thresholds_arr = np.asarray(row_thresholds, dtype=float)

    # Apply per-row thresholds to get binary predictions
    predictions = (probas >= row_thresholds_arr).astype(int)

    return predictions


def apply_business_rules(
    probas: np.ndarray,
    raw_data: pd.DataFrame,
    rules_config: Dict,
) -> tuple:
    """Apply business rules to probability predictions.

    Evaluates each rule's ``condition`` (a pandas eval expression) against
    ``raw_data`` (the pre-FE DataFrame with original column names), then applies
    the rule's ``action`` to the probabilities.

    Pipeline position: called **after** ``segment_thresholds`` (or global
    threshold) in ``InferenceBuilder.execute()``. The caller re-derives binary
    predictions from the returned (possibly modified) probas.

    Args:
        probas: Array of predicted probabilities (positive class). A copy is
            made; the input array is not modified.
        raw_data: Pre-FE DataFrame with the raw columns the rules reference
            (e.g. ``1_anterior``, ``geo_region``). Must be aligned with
            ``probas`` (same row count and order).
        rules_config: ``business_rules`` config dict with keys:
            - ``apply_to`` (optional): ``{"column": str, "regions": [str]}``.
              If ``column`` is omitted, defaults to ``"geo_region"``. If
              ``regions`` is omitted, rules apply to ALL rows.
            - ``rules``: list of ``{name, condition, action, value}`` dicts.
            - ``output.add_rule_columns`` (optional, default True): whether to
              return a DataFrame with ``rule_<name>`` and ``rule_<name>_value``
              columns.

    Returns:
        tuple: ``(modified_probas, rules_df, probas_modified)`` where:
            - ``modified_probas``: float ndarray, possibly boosted/overridden.
            - ``rules_df``: DataFrame with rule trigger columns (or None if
              ``add_rule_columns`` is False or no rules).
            - ``probas_modified``: bool, True if any rule had action
              ``override`` or ``score_boost`` and triggered at least once.
              The caller uses this to decide whether to re-derive predictions.

    Rule actions:
        - ``flag``: records the trigger in ``rule_<name>`` but does NOT modify
          probas. Useful for analysis / downstream overlay.
        - ``override``: sets ``probas[triggered] = 1.0``. When the caller
          re-derives predictions, these rows become ``prediction=1`` (since
          1.0 >= any threshold <= 1.0).
        - ``score_boost``: adds ``value`` to ``probas[triggered]`` (clipped to
          [0, 1]). The caller re-derives predictions, so the boost respects
          segment_thresholds if enabled.

    Error handling:
        - If ``condition`` references a non-existent column or fails to parse,
          the rule is skipped (error logged) and its trigger column is all
          False. Other rules continue.
        - ``value`` is clipped to [0, 1].
        - ``condition: "False"`` (stub) short-circuits to all-False without
          invoking the eval engine.

    Example:
        >>> probas = np.array([0.2, 0.5])
        >>> raw = pd.DataFrame({"1_anterior": [0, 10], "geo_region": ["A", "B"]})
        >>> cfg = {"apply_to": {"regions": ["A"]},
        ...        "rules": [{"name": "r1", "condition": "(`1_anterior` == 0)",
        ...                  "action": "override", "value": 1.0}]}
        >>> mod_probas, rules_df, modified = apply_business_rules(probas, raw, cfg)
        >>> mod_probas
        array([1., 0.5])
    """
    import logging as _logging

    _logger = _logging.getLogger(__name__)

    rules = rules_config.get("rules", [])
    apply_to = rules_config.get("apply_to", {}) or {}
    filter_column = apply_to.get("column", "geo_region")
    filter_values = apply_to.get("regions")
    add_columns = rules_config.get("output", {}).get("add_rule_columns", True)

    n_rows = len(raw_data)

    # --- Defensive length guard ---
    # ``raw_data`` is captured post-filter/pre-FE; ``probas`` come from
    # post-FE data. All built-in FE transformers preserve row count and order,
    # but the framework supports ``feature_engineering.custom_class`` which
    # could drop or reorder rows (e.g. internal dropna) and silently misalign
    # rules vs probabilities. Fail loudly rather than emit misaligned output.
    if len(probas) != n_rows:
        raise ValueError(
            f"business_rules: raw_data ({n_rows} rows) and probas "
            f"({len(probas)} rows) are misaligned. This indicates the feature "
            "engineering transform changed the row count or order. business_rules "
            "requires a row-preserving FE."
        )

    # --- Build eligibility mask (which rows can rules evaluate on) ---
    if filter_values is not None:
        if filter_column in raw_data.columns:
            eligible = raw_data[filter_column].isin(filter_values).values
        else:
            _logger.warning(
                f"business_rules: apply_to.column '{filter_column}' not found "
                "in data; rules will apply to ALL rows."
            )
            eligible = np.ones(n_rows, dtype=bool)
    else:
        # No apply_to filter → all rows eligible
        eligible = np.ones(n_rows, dtype=bool)

    # --- Work on a mutable float copy of probas ---
    final_probas = np.array(probas, dtype=float, copy=True)

    rule_columns: Dict[str, np.ndarray] = {}
    probas_modified = False

    for rule in rules:
        name = rule.get("name", "unnamed")
        condition = str(rule.get("condition", "False")).strip()
        action = rule.get("action", "flag")
        value = float(rule.get("value", 0.0) or 0.0)
        value = max(0.0, min(1.0, value))  # clip to [0, 1]

        # --- Evaluate condition ---
        # Short-circuit stubs without invoking the eval engine.
        if condition == "False":
            triggered_all = pd.Series(False, index=raw_data.index)
        elif condition == "True":
            triggered_all = pd.Series(True, index=raw_data.index)
        else:
            try:
                result = raw_data.eval(condition)
                # raw_data.eval may return a scalar for constant expressions.
                if isinstance(result, pd.Series):
                    triggered_all = result.astype(bool)
                else:
                    triggered_all = pd.Series(bool(result), index=raw_data.index)
            except Exception as exc:
                _logger.error(
                    f"business_rules: rule '{name}' failed to evaluate "
                    f"condition '{condition}': {exc}. Skipping rule."
                )
                if add_columns:
                    rule_columns[f"rule_{name}"] = np.zeros(n_rows, dtype=bool)
                    rule_columns[f"rule_{name}_value"] = np.zeros(n_rows, dtype=float)
                continue

        # Combine condition result with eligibility mask
        triggered = triggered_all.values & eligible
        n_triggered = int(triggered.sum())

        # --- Record output columns ---
        if add_columns:
            rule_columns[f"rule_{name}"] = triggered.copy()
            rule_columns[f"rule_{name}_value"] = np.where(triggered, value, 0.0).astype(float)

        # --- Apply action ---
        if action == "override":
            if n_triggered > 0:
                final_probas[triggered] = 1.0
                probas_modified = True
        elif action == "score_boost":
            if n_triggered > 0 and value > 0:
                final_probas[triggered] = np.clip(final_probas[triggered] + value, 0.0, 1.0)
                probas_modified = True
        elif action == "flag":
            pass  # no change to probas
        else:
            _logger.warning(
                f"business_rules: rule '{name}' has unknown action '{action}'. "
                "Treating as 'flag' (no effect on probas/predictions)."
            )

        _logger.info(f"  • Rule '{name}' ({action}): {n_triggered} rows triggered")

    rules_df = pd.DataFrame(rule_columns) if rule_columns else None

    return final_probas, rules_df, probas_modified
