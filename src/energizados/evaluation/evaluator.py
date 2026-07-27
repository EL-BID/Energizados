"""
Evaluator Module for Energizados Framework.

Evaluates ML models using metrics, visualizations and reports.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from energizados.contracts import BaseEvaluator
from energizados.evaluation.calibration import ThresholdCalibrator
from energizados.evaluation.metrics import Metrics
from energizados.evaluation.plots import PlotGenerator
from energizados.evaluation.report import ReportGenerator

logger = logging.getLogger(__name__)


class DefaultEvaluator(BaseEvaluator):
    """
    Default evaluator for framework models.

    Generates metrics, visualizations and HTML/JSON reports.

    Args:
        input_path: Path to test dataset
        model_path: Path to trained model
        feature_engineering_path: Path to feature engineering (optional)
        output_dir: Output directory for reports
        target_column: Name of target column
        threshold: Threshold for binary classification
        metrics: List of metrics to calculate
        generate_plots: If True, generates visualizations
        generate_html_report: If True, generates HTML report
        generate_json_report: If True, generates JSON report
        segment_columns: List of column names to compute per-segment metrics
        calibration_config: Dict with calibration settings (enabled, method, params)
        val_predictions_path: Path to validation predictions parquet (for calibration)

    Example:
        >>> evaluator = DefaultEvaluator(
        ...     input_path="data/temp/splits/test.parquet",
        ...     model_path="models/trained/model.pkl"
        ... )
        >>> result = evaluator.run(context)
    """

    def __init__(
        self,
        input_path: Optional[str] = None,
        model_path: str = "output/models/model.pkl",
        feature_engineering_path: Optional[str] = None,
        output_dir: str = "output/reports/evaluation/",
        target_column: str = "target",
        threshold: float = 0.5,
        metrics: Optional[List[str]] = None,
        generate_plots: bool = True,
        generate_html_report: bool = True,
        generate_json_report: bool = True,
        segment_columns: Optional[List[str]] = None,
        calibration_config: Optional[Dict] = None,
        val_predictions_path: Optional[str] = None,
        shap_config: Optional[Dict] = None,
        experiment_description: Optional[str] = None,
        segmented_evaluation: Optional[Dict] = None,
        **kwargs,
    ):
        self.input_path = input_path
        self.model_path = model_path
        self.feature_engineering_path = feature_engineering_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.target_column = target_column
        self.threshold = threshold
        self.metrics = metrics or [
            "auc",
            "precision",
            "recall",
            "f1",
            "confusion_matrix",
            "cumulative_gains",
        ]
        self.generate_plots = generate_plots
        self.generate_html_report = generate_html_report
        self.generate_json_report = generate_json_report
        self.segment_columns = segment_columns or []
        self.calibration_config = calibration_config
        self.val_predictions_path = val_predictions_path
        self._shap_config = shap_config
        self.experiment_description = experiment_description
        self.segmented_evaluation = segmented_evaluation or {}

        self.plot_generator = PlotGenerator(str(self.output_dir))
        self.report_generator = ReportGenerator(str(self.output_dir))

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the complete evaluation pipeline.

        Loads the model and optional feature engineering, applies them to the test
        set, optionally calibrates the decision threshold, computes all configured
        metrics, and generates plots and reports.

        Args:
            context: Pipeline context dict; may supply ``test_path``,
                ``model_path``, ``feature_engineering_path``, and
                ``val_predictions_path`` when those were not provided at
                construction time.

        Returns:
            Dict: Updated context with keys ``metrics``, ``plots``, ``reports``,
                and ``evaluation_dir``.

        Raises:
            ValueError: If no ``input_path`` or ``test_path`` can be resolved.
            FileNotFoundError: If the resolved test dataset does not exist.
        """
        logger.info("\n" + "=" * 50)
        logger.info("EVALUATION STEP")
        logger.info("=" * 50)

        # Resolve paths from context without mutating instance state (MEJORAS P1-5)
        ctx = context or {}
        input_path = self.input_path or ctx.get("test_path")
        model_path = self.model_path or ctx.get("model_path")
        feature_engineering_path = self.feature_engineering_path or ctx.get(
            "feature_engineering_path"
        )
        model_paths = ctx.get("model_paths")

        # Validate inputs before loading (MEJORAS P1-4)
        if not input_path:
            logger.warning(
                "No test_path available in context — skipping evaluation. "
                "(This is expected in no-holdout training mode.)"
            )
            return {
                **ctx,
                "metrics": {},
                "plots": {},
                "reports": {},
                "evaluation_dir": str(self.output_dir),
                "skipped": True,
            }
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Test dataset not found: {input_path}")

        # Detect comparison mode
        comparison_mode = model_paths is not None and len(model_paths) > 1

        # Comparison mode: evaluate each model independently
        if comparison_mode:
            return self._execute_comparison_mode(
                ctx, input_path, feature_engineering_path, model_paths
            )

        # Single model or ensemble mode (existing behavior)
        # 1. Load model and feature engineering
        model = self._load_model(model_path)
        feature_engineering = self._load_feature_engineering(feature_engineering_path)

        # 2. Load test data
        test_df = pd.read_parquet(input_path)
        logger.info(f"Test dataset shape: {test_df.shape}")

        X_test = test_df.drop(columns=[self.target_column])
        y_test = test_df[self.target_column]

        # 3. Apply feature engineering if available
        if feature_engineering is not None:
            logger.info("Applying feature engineering...")
            X_test_transformed = feature_engineering.transform(X_test)
        else:
            X_test_transformed = X_test

        # Capture feature names for importance plot (MEJORAS P2-8)
        feature_names = (
            list(X_test_transformed.columns) if hasattr(X_test_transformed, "columns") else None
        )

        # 4. Calibrate threshold if configured
        calibration_result = None
        threshold = self.threshold  # local copy — do not mutate self.threshold
        if self.calibration_config and self.calibration_config.get("enabled", False):
            val_path = self.val_predictions_path or ctx.get("val_predictions_path")
            if val_path and Path(val_path).exists():
                val_df = pd.read_parquet(val_path)
                calibrator = ThresholdCalibrator(
                    method=self.calibration_config.get("strategy", "cost_benefit"),
                    **self.calibration_config.get("params", {}),
                )
                calibration_result = calibrator.calibrate(
                    val_df["y_true"].values, val_df["y_proba"].values
                )
                threshold = calibration_result["threshold"]
                logger.info(
                    f"Calibrated threshold: {threshold:.4f} (method: {calibration_result['method']})"
                )
            else:
                logger.warning(
                    "Calibration enabled but val_predictions_path not found, using default threshold"
                )

        # 5. Get predictions
        logger.info("Generating predictions...")
        y_proba = model.predict_proba(X_test_transformed)
        y_pred = (y_proba >= threshold).astype(int)

        # 6. Calculate metrics
        logger.info("Calculating metrics...")
        metrics_calculator = Metrics(y_test, y_pred, y_proba, threshold)
        metrics_results = metrics_calculator.calculate_all(self.metrics)

        # Log main metrics
        logger.info(f"\n{'=' * 50}")
        logger.info("METRICS SUMMARY")
        logger.info(f"{'=' * 50}")
        logger.info(f"AUC:       {metrics_results.get('auc', 0):.4f}")
        logger.info(f"F1:        {metrics_results.get('f1', 0):.4f}")
        logger.info(f"Precision: {metrics_results.get('precision', 0):.4f}")
        logger.info(f"Recall:    {metrics_results.get('recall', 0):.4f}")
        if "accuracy" in metrics_results:
            logger.info(f"Accuracy:  {metrics_results['accuracy']:.4f}")
        logger.info(f"{'=' * 50}")
        metrics_results["threshold"] = threshold

        # 6b. Val AUC — read from val_predictions parquet if available
        val_pred_path = self.val_predictions_path or ctx.get("val_predictions_path")
        if val_pred_path and Path(val_pred_path).exists():
            try:
                val_pred_df = pd.read_parquet(val_pred_path)
                val_metrics_calc = Metrics(
                    val_pred_df["y_true"].values,
                    (val_pred_df["y_proba"].values >= threshold).astype(int),
                    val_pred_df["y_proba"].values,
                    threshold,
                )
                auc_val = val_metrics_calc.auc()
                metrics_results["auc_val"] = float(auc_val)
                metrics_results["auc_diff"] = float(auc_val) - float(metrics_results.get("auc", 0))
                logger.info(
                    f"AUC val: {auc_val:.4f}  |  AUC test: {metrics_results.get('auc', 0):.4f}"
                    f"  |  Diff: {metrics_results['auc_diff']:+.4f}"
                )
            except Exception as e:
                logger.warning(f"Could not compute val AUC: {e}")

        # 6d. Segment metrics (MEJORAS P4-15) + Segmented evaluation (threshold modes + column combos)
        segment_metrics = {}
        segmented_metrics = {}

        # --- Legacy segment_columns (simple per-column, global threshold) ---
        if self.segment_columns:
            logger.info(f"Calculating segment metrics for: {self.segment_columns}")
            for col in self.segment_columns:
                if col in test_df.columns:
                    segments = test_df[col].values
                    segment_metrics[col] = metrics_calculator.segment_metrics(
                        segments, threshold_mode="global"
                    )
                else:
                    logger.warning(f"Segment column '{col}' not found in test dataset, skipping.")

        # --- New segmented_evaluation (column combos + configurable threshold modes) ---
        if self.segmented_evaluation.get("enabled", False):
            seg_config = self.segmented_evaluation
            seg_by = seg_config.get("by", [])
            threshold_mode = seg_config.get("threshold_mode", "global")
            min_samples = seg_config.get("min_samples", 30)
            recall_target = seg_config.get("recall_target", 0.8)

            logger.info(
                f"Segmented evaluation: by={seg_by}, threshold_mode={threshold_mode}, "
                f"min_samples={min_samples}"
            )

            for segment_def in seg_by:
                # Handle column combinations: "zona+region" -> combined segment
                if "+" in segment_def:
                    cols = [c.strip() for c in segment_def.split("+")]
                    # Validate all columns exist
                    missing = [c for c in cols if c not in test_df.columns]
                    if missing:
                        logger.warning(
                            f"Segment '{segment_def}' has missing columns: {missing}, skipping."
                        )
                        continue

                    # Create combined segment column
                    combined = test_df[cols[0]].astype(str)
                    for c in cols[1:]:
                        combined = combined + "|" + test_df[c].astype(str)

                    display_name = f"{segment_def} (combined)"
                    segments = combined.values

                else:
                    # Simple column reference
                    col = segment_def
                    if col not in test_df.columns:
                        logger.warning(
                            f"Segment column '{col}' not found in test dataset, skipping."
                        )
                        continue
                    display_name = col
                    segments = test_df[col].values

                # Compute metrics with the specified threshold mode
                seg_results = metrics_calculator.segment_metrics(
                    segments,
                    threshold_mode=threshold_mode,
                    min_samples=min_samples,
                    recall_target=recall_target,
                )

                if seg_results:
                    segmented_metrics[display_name] = seg_results

                    # Log detailed per-segment info
                    logger.info(f"\n{'=' * 60}")
                    logger.info(f"SEGMENTED METRICS — {display_name}")
                    logger.info(f"{'=' * 60}")
                    for seg_val, seg_data in sorted(seg_results.items()):
                        n = seg_data["n_samples"]
                        pos = seg_data["n_positives"]
                        auc = seg_data["auc"]
                        thresh = seg_data["threshold"]
                        thresh_mode = seg_data["threshold_mode"]
                        logger.info(
                            f"  {seg_val:30s}  n={n:5,}  pos={pos:4}  "
                            f"AUC={auc:.4f}  thresh={thresh:.4f} ({thresh_mode})"
                        )
                else:
                    logger.warning(f"No valid segments found for '{display_name}'")

        # Merge both into metrics_results
        if segment_metrics:
            metrics_results["segment_metrics"] = segment_metrics
        if segmented_metrics:
            metrics_results["segmented_metrics"] = segmented_metrics

        # 6d2. Export segment thresholds to JSON (mejoras-3 T-F2a)
        if self.segmented_evaluation.get("enabled", False) and segmented_metrics:
            seg_config = self.segmented_evaluation
            threshold_mode = seg_config.get("threshold_mode", "global")
            self._export_segment_thresholds(
                segmented_metrics=segmented_metrics,
                output_dir=self.output_dir,
                global_threshold=threshold,
                threshold_mode=threshold_mode,
            )

            # 6d3. Reconcile headline metrics with per-segment operating point.
            #
            # When segmented_evaluation uses per-segment thresholds (youden,
            # f1_optimal, recall_target), the headline /metrics/* previously
            # reported global-threshold numbers, causing downstream docs to
            # over-report operational recall. This step replaces the headline
            # with the per-segment aggregate (each row predicted using its own
            # segment's threshold) and preserves the global numbers under
            # /metrics/global_threshold_metrics/. (evaluator-fix)
            if threshold_mode != "global":
                metrics_results = self._reconcile_headline_with_segments(
                    metrics_results=metrics_results,
                    y_true=y_test.to_numpy(),
                    y_proba=y_proba,
                    test_df=test_df,
                    seg_config=seg_config,
                    segmented_metrics=segmented_metrics,
                    global_threshold=threshold,
                )

        # 6e. Threshold sweep metrics
        logger.info("Calculating threshold sweep metrics...")
        threshold_metrics = None
        try:
            threshold_metrics = metrics_calculator.get_threshold_metrics()
        except Exception as e:
            logger.warning(f"Could not calculate threshold metrics: {e}")

        # 6f. SHAP Explainability
        shap_embedded = {}
        shap_plots = {}
        if self._shap_config and self._shap_config.get("enabled", False):
            try:
                from energizados.explainability.shap_explainer import ShapExplainer

                shap_max_samples = self._shap_config.get("max_samples", 500)
                shap_top_n = self._shap_config.get("top_n_features", 20)
                shap_plot_types = self._shap_config.get("plot_types", ["summary", "bar"])

                logger.info(
                    f"Computing SHAP values (max_samples={shap_max_samples}, top_n={shap_top_n})..."
                )

                explainer = ShapExplainer(
                    model=model,
                    X_background=X_test_transformed,
                    feature_names=feature_names,
                    max_samples=shap_max_samples,
                )

                shap_values = explainer.compute_shap_values(
                    X_test_transformed, max_samples=shap_max_samples
                )

                if shap_values is not None:
                    if "summary" in shap_plot_types:
                        path, b64 = self.plot_generator.shap_summary_plot_embedded(
                            shap_values, X_test_transformed, feature_names, top_n=shap_top_n
                        )
                        shap_plots["shap_summary"] = path
                        shap_embedded["shap_summary"] = b64

                    if "bar" in shap_plot_types:
                        path, b64 = self.plot_generator.shap_bar_plot_embedded(
                            shap_values, feature_names, top_n=shap_top_n
                        )
                        shap_plots["shap_bar"] = path
                        shap_embedded["shap_bar"] = b64

                    top_features = explainer.get_top_features(shap_values, top_n=shap_top_n)
                    metrics_results["shap_top_features"] = top_features

                    logger.info(f"SHAP analysis complete. Top features: {top_features[:5]}")
                else:
                    logger.warning("SHAP values could not be computed.")

            except ImportError:
                logger.warning(
                    "shap package not installed. Skipping SHAP analysis. "
                    "Install with: pip install shap"
                )
            except Exception as e:
                logger.error(f"SHAP analysis failed: {e}", exc_info=True)

        # 7. Generate visualizations
        plots_paths = {}
        plots_embedded = {}
        if self.generate_plots:
            logger.info("Generating plots...")
            plots_paths, plots_embedded = self._generate_plots(
                y_test,
                y_proba,
                y_pred,
                metrics_results,
                model=model,
                feature_names=feature_names,
                threshold_metrics=threshold_metrics,
                threshold=threshold,
            )

        # Merge SHAP plots into results
        if shap_plots:
            plots_paths.update(shap_plots)
        if shap_embedded:
            plots_embedded.update(shap_embedded)

        # 7b. Generate interactive plots
        plots_interactive = {}
        try:
            from sklearn.metrics import precision_recall_curve as sk_pr_curve
            from sklearn.metrics import roc_curve as sk_roc_curve

            from energizados.evaluation.plots_interactive import EvalInteractivePlots

            eval_plots = EvalInteractivePlots(str(self.output_dir))

            # ROC
            try:
                fpr, tpr, _ = sk_roc_curve(y_test, y_proba)
                plots_interactive["roc_curve"] = eval_plots.roc_curve(
                    fpr.tolist(), tpr.tolist(), metrics_results.get("auc", 0)
                )
            except Exception as e:
                logger.warning(f"Could not generate interactive ROC curve: {e}")

            # Precision-Recall
            try:
                prec_vals, rec_vals, _ = sk_pr_curve(y_test, y_proba)
                ap = float(np.trapz(prec_vals[::-1], rec_vals[::-1]))
                plots_interactive["precision_recall"] = eval_plots.precision_recall_curve(
                    prec_vals.tolist(), rec_vals.tolist(), ap
                )
            except Exception as e:
                logger.warning(f"Could not generate interactive PR curve: {e}")

            # Confusion matrix heatmap
            try:
                cm = metrics_results.get("confusion_matrix", {})
                if "matrix" in cm:
                    plots_interactive["confusion_matrix"] = eval_plots.confusion_matrix_heatmap(
                        cm["matrix"]
                    )
            except Exception as e:
                logger.warning(f"Could not generate interactive confusion matrix: {e}")

            # Cumulative gains
            try:
                if "cumulative_gains" in metrics_results:
                    plots_interactive["cumulative_gains"] = eval_plots.cumulative_gains(
                        metrics_results["cumulative_gains"]
                    )
            except Exception as e:
                logger.warning(f"Could not generate interactive cumulative gains: {e}")

            # Lift chart
            try:
                if "cumulative_gains" in metrics_results:
                    plots_interactive["lift_chart"] = eval_plots.lift_chart(
                        metrics_results["cumulative_gains"]
                    )
            except Exception as e:
                logger.warning(f"Could not generate interactive lift chart: {e}")

            # Probability distribution
            try:
                plots_interactive["probability_distribution"] = eval_plots.probability_distribution(
                    y_test.tolist(), y_proba.tolist()
                )
            except Exception as e:
                logger.warning(f"Could not generate interactive probability distribution: {e}")

            # Feature importance
            try:
                if feature_names is not None:
                    inner = getattr(model, "_model", None)
                    importances = None
                    if inner is not None:
                        if hasattr(inner, "feature_importances_"):
                            importances = inner.feature_importances_
                        elif hasattr(inner, "get_feature_importance"):
                            importances = inner.get_feature_importance()
                    if importances is not None:
                        plots_interactive["feature_importance"] = eval_plots.feature_importance(
                            feature_names, importances.tolist()
                        )
            except Exception as e:
                logger.warning(f"Could not generate interactive feature importance: {e}")

            # Threshold sweep
            try:
                if threshold_metrics is not None:
                    plots_interactive["threshold_sweep"] = eval_plots.threshold_sweep(
                        threshold_metrics, threshold
                    )
            except Exception as e:
                logger.warning(f"Could not generate interactive threshold sweep: {e}")

            # Segment metrics charts
            try:
                for col_name, col_data in segment_metrics.items():
                    chart_key = f"segment_{col_name}"
                    plots_interactive[chart_key] = eval_plots.segment_metrics_chart(
                        col_data, metric="f1"
                    )
            except Exception as e:
                logger.warning(f"Could not generate interactive segment charts: {e}")

        except ImportError:
            logger.debug("plotly not available; interactive charts skipped")
        except Exception as e:
            logger.warning(f"Could not generate interactive plots: {e}")

        # 8. Generate reports
        report_paths = {}
        if self.generate_html_report or self.generate_json_report:
            logger.info("Generating reports...")

            model_info = self._get_model_info(model)

            if self.generate_json_report:
                json_path = self.report_generator.generate_json(
                    metrics_results,
                    model_info,
                    calibration_result=calibration_result,
                    threshold_metrics=threshold_metrics,
                    segment_metrics=segment_metrics if segment_metrics else None,
                    segmented_metrics=segmented_metrics if segmented_metrics else None,
                )
                report_paths["json"] = json_path

            if self.generate_html_report:
                html_path = self.report_generator.generate_html(
                    metrics_results,
                    plots_paths,
                    model_info,
                    calibration_result=calibration_result,
                    plots_embedded=plots_embedded if plots_embedded else None,
                    plots_interactive=plots_interactive if plots_interactive else None,
                    threshold_metrics=threshold_metrics,
                    segment_metrics=segment_metrics if segment_metrics else None,
                    segmented_metrics=segmented_metrics if segmented_metrics else None,
                    experiment_description=self.experiment_description,
                )
                report_paths["html"] = html_path

        logger.info(f"\nEvaluation complete. Reports saved to: {self.output_dir}")

        return {
            **ctx,
            "metrics": metrics_results,
            "plots": plots_paths,
            "reports": report_paths,
            "evaluation_dir": str(self.output_dir),
        }

    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model: Any,
        threshold: float = 0.5,
        **kwargs: Any,
    ) -> Dict[str, float]:
        """Compute evaluation metrics.

        Args:
            X: Feature DataFrame.
            y: True target values.
            model: Trained model (must have predict_proba).
            threshold: Decision threshold for binary predictions.
            **kwargs: Additional evaluator-specific parameters.

        Returns:
            Dict[str, float]: Metric name -> value (e.g., {'auc': 0.85, 'f1': 0.82}).

        Raises:
            ValueError: If inputs are invalid.
        """
        # Get predictions
        y_proba = model.predict_proba(X)
        y_pred = (y_proba >= threshold).astype(int)

        # Calculate metrics
        metrics_calculator = Metrics(y, y_pred, y_proba, threshold)
        metrics_results = metrics_calculator.calculate_all(self.metrics)

        # Add threshold to results
        metrics_results["threshold"] = threshold

        return metrics_results

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validates that necessary inputs exist."""
        if self.model_path and not Path(self.model_path).exists():
            return False

        input_path = self.input_path or context.get("test_path")
        return input_path is not None and Path(input_path).exists()

    def get_required_keys(self) -> list:
        """Returns required context keys."""
        keys = []
        if not self.model_path:
            keys.append("model_path")
        if not self.input_path:
            keys.append("test_path")
        return keys

    def get_output_keys(self) -> list:
        """Returns keys added to context."""
        return ["metrics", "plots", "reports", "evaluation_dir"]

    def _load_model(self, model_path: Optional[str] = None):
        """Loads the trained model from the given path."""
        from energizados.core.utils.secure_pickle import secure_load

        path = model_path or self.model_path
        logger.info(f"Loading model from: {path}")
        return secure_load(path)

    def _load_feature_engineering(self, feature_engineering_path: Optional[str] = None):
        """Loads feature engineering if the path exists."""
        from energizados.core.utils.secure_pickle import secure_load

        path = feature_engineering_path or self.feature_engineering_path
        if path and Path(path).exists():
            logger.info(f"Loading feature engineering from: {path}")
            return secure_load(path)
        return None

    def _execute_comparison_mode(
        self,
        ctx: Dict[str, Any],
        input_path: str,
        feature_engineering_path: Optional[str],
        model_paths: Dict[str, str],
    ) -> Dict[str, Any]:
        """Execute evaluation in comparison mode (multiple models)."""
        from energizados.core.utils.secure_pickle import secure_load

        logger.info("Comparison mode detected - evaluating each model independently...")

        # Load feature engineering once
        feature_engineering = self._load_feature_engineering(feature_engineering_path)

        # Load test data once
        test_df = pd.read_parquet(input_path)
        logger.info(f"Test dataset shape: {test_df.shape}")

        X_test = test_df.drop(columns=[self.target_column])
        y_test = test_df[self.target_column]

        # Apply feature engineering once
        if feature_engineering is not None:
            logger.info("Applying feature engineering...")
            X_test_transformed = feature_engineering.transform(X_test)
        else:
            X_test_transformed = X_test

        # Capture feature names for importance plot
        feature_names = (
            list(X_test_transformed.columns) if hasattr(X_test_transformed, "columns") else None
        )

        # Evaluate each model
        all_metrics = {}
        all_model_info = {}
        all_plots_paths = {}
        all_plots_embedded = {}
        all_reports = {}
        all_plots_interactive = {}

        for model_name, model_path in model_paths.items():
            logger.info(f"\n{'=' * 50}")
            logger.info(f"Evaluating model: {model_name}")
            logger.info(f"{'=' * 50}")

            # Create output subdirectory for this model
            model_output_dir = self.output_dir / model_name
            model_output_dir.mkdir(parents=True, exist_ok=True)

            # Load model
            logger.info(f"Loading model from: {model_path}")
            model = secure_load(model_path)

            # Determine if model uses raw or transformed data
            model_config = getattr(model, "config", {}) or {}
            model_type = model_config.get("type", "lightgbm")

            if model_type in ["simple_trend", "simple_constant"]:
                X_test_for_pred = X_test
            else:
                X_test_for_pred = X_test_transformed

            # Get predictions
            logger.info("Generating predictions...")
            y_proba = model.predict_proba(X_test_for_pred)
            y_pred = (y_proba >= self.threshold).astype(int)

            # Calculate metrics
            logger.info("Calculating metrics...")
            metrics_calculator = Metrics(y_test, y_pred, y_proba, self.threshold)
            metrics_results = metrics_calculator.calculate_all(self.metrics)
            metrics_results["threshold"] = self.threshold

            # Log main metrics
            logger.info(f"\n{'=' * 50}")
            logger.info("METRICS SUMMARY")
            logger.info(f"{'=' * 50}")
            logger.info(f"AUC:       {metrics_results.get('auc', 0):.4f}")
            logger.info(f"F1:        {metrics_results.get('f1', 0):.4f}")
            logger.info(f"Precision: {metrics_results.get('precision', 0):.4f}")
            logger.info(f"Recall:    {metrics_results.get('recall', 0):.4f}")
            logger.info(f"{'=' * 50}")

            # Generate visualizations
            if self.generate_plots:
                logger.info("Generating plots...")
                # Use model-specific output directory
                temp_plot_gen = PlotGenerator(str(model_output_dir))
                plots_paths, plots_embedded = self._generate_plots_with_generator(
                    temp_plot_gen,
                    y_test,
                    y_proba,
                    y_pred,
                    metrics_results,
                    model=model,
                    feature_names=feature_names,
                    threshold_metrics=None,
                    threshold=self.threshold,
                )
                all_plots_paths[model_name] = plots_paths
                all_plots_embedded[model_name] = plots_embedded

            # Generate interactive plots
            plots_interactive = {}
            try:
                from sklearn.metrics import precision_recall_curve as sk_pr_curve
                from sklearn.metrics import roc_curve as sk_roc_curve

                from energizados.evaluation.plots_interactive import (
                    EvalInteractivePlots,
                )

                eval_plots = EvalInteractivePlots(str(model_output_dir))

                # ROC
                try:
                    fpr, tpr, _ = sk_roc_curve(y_test, y_proba)
                    plots_interactive["roc_curve"] = eval_plots.roc_curve(
                        fpr.tolist(), tpr.tolist(), metrics_results.get("auc", 0)
                    )
                except Exception as e:
                    logger.warning(f"Could not generate interactive ROC curve: {e}")

                # Precision-Recall
                try:
                    prec_vals, rec_vals, _ = sk_pr_curve(y_test, y_proba)
                    ap = float(np.trapz(prec_vals[::-1], rec_vals[::-1]))
                    plots_interactive["precision_recall"] = eval_plots.precision_recall_curve(
                        prec_vals.tolist(), rec_vals.tolist(), ap
                    )
                except Exception as e:
                    logger.warning(f"Could not generate interactive PR curve: {e}")

                # Confusion matrix heatmap
                try:
                    cm = metrics_results.get("confusion_matrix", {})
                    if "matrix" in cm:
                        plots_interactive["confusion_matrix"] = eval_plots.confusion_matrix_heatmap(
                            cm["matrix"]
                        )
                except Exception as e:
                    logger.warning(f"Could not generate interactive confusion matrix: {e}")

                # Cumulative gains
                try:
                    if "cumulative_gains" in metrics_results:
                        plots_interactive["cumulative_gains"] = eval_plots.cumulative_gains(
                            metrics_results["cumulative_gains"]
                        )
                except Exception as e:
                    logger.warning(f"Could not generate interactive cumulative gains: {e}")

                # Lift chart
                try:
                    if "cumulative_gains" in metrics_results:
                        plots_interactive["lift_chart"] = eval_plots.lift_chart(
                            metrics_results["cumulative_gains"]
                        )
                except Exception as e:
                    logger.warning(f"Could not generate interactive lift chart: {e}")

                # Probability distribution
                try:
                    plots_interactive["probability_distribution"] = (
                        eval_plots.probability_distribution(y_test.tolist(), y_proba.tolist())
                    )
                except Exception as e:
                    logger.warning(f"Could not generate interactive probability distribution: {e}")

                # Feature importance
                try:
                    if feature_names is not None:
                        inner = getattr(model, "_model", None)
                        importances = None
                        if inner is not None:
                            if hasattr(inner, "feature_importances_"):
                                importances = inner.feature_importances_
                            elif hasattr(inner, "get_feature_importance"):
                                importances = inner.get_feature_importance()
                        if importances is not None:
                            plots_interactive["feature_importance"] = eval_plots.feature_importance(
                                feature_names, importances.tolist()
                            )
                except Exception as e:
                    logger.warning(f"Could not generate interactive feature importance: {e}")

                all_plots_interactive[model_name] = plots_interactive

            except ImportError:
                logger.debug("plotly not available; interactive charts skipped")
            except Exception as e:
                logger.warning(f"Could not generate interactive plots: {e}")

            # Generate reports
            model_reports = {}
            if self.generate_html_report or self.generate_json_report:
                logger.info("Generating reports...")
                temp_report_gen = ReportGenerator(str(model_output_dir))
                model_info = self._get_model_info(model)

                if self.generate_json_report:
                    json_path = temp_report_gen.generate_json(
                        metrics_results,
                        model_info,
                        calibration_result=None,
                        threshold_metrics=None,
                        segment_metrics=None,
                    )
                    model_reports["json"] = json_path

                if self.generate_html_report:
                    html_path = temp_report_gen.generate_html(
                        metrics_results,
                        all_plots_paths.get(model_name, {}),
                        model_info,
                        calibration_result=None,
                        plots_embedded=all_plots_embedded.get(model_name),
                        plots_interactive=plots_interactive,
                        threshold_metrics=None,
                        segment_metrics=None,
                    )
                    model_reports["html"] = html_path

            all_reports[model_name] = model_reports
            all_metrics[model_name] = metrics_results
            all_model_info[model_name] = model_info

        # Generate comparative report
        from energizados.evaluation.comparative import ComparativeEvaluator

        comparative_evaluator = ComparativeEvaluator(str(self.output_dir))
        comparison_result = comparative_evaluator.compare(
            all_metrics=all_metrics,
            all_model_info=all_model_info,
        )

        logger.info(f"\nEvaluation complete. Reports saved to: {self.output_dir}")
        logger.info(f"Comparative report: {comparison_result['html']}")

        return {
            **ctx,
            "model_metrics": all_metrics,
            "model_reports": all_reports,
            "model_plots": all_plots_paths,
            "comparison_report": comparison_result,
            "evaluation_dir": str(self.output_dir),
        }

    def _generate_plots_with_generator(
        self,
        plot_generator: PlotGenerator,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        y_pred: np.ndarray,
        metrics: Dict,
        model=None,
        feature_names: Optional[List[str]] = None,
        threshold_metrics: Optional[Dict] = None,
        threshold: float = 0.5,
    ) -> tuple:
        """
        Generates all visualizations using a provided PlotGenerator instance.

        Returns:
            Tuple of (plots_paths dict, plots_embedded dict)
        """
        plots = {}
        embedded = {}

        # ROC Curve
        try:
            path, b64 = plot_generator.roc_curve_plot_embedded(
                y_true, y_proba, metrics.get("auc", 0)
            )
            plots["roc_curve"] = path
            embedded["roc_curve"] = b64
        except Exception as e:
            logger.warning(f"Could not generate ROC curve: {e}")

        # Precision-Recall Curve
        try:
            path, b64 = plot_generator.precision_recall_plot_embedded(y_true, y_proba)
            plots["precision_recall"] = path
            embedded["precision_recall"] = b64
        except Exception as e:
            logger.warning(f"Could not generate PR curve: {e}")

        # Confusion Matrix
        try:
            cm = metrics.get("confusion_matrix", {})
            if "matrix" in cm:
                path, b64 = plot_generator.confusion_matrix_plot_embedded(np.array(cm["matrix"]))
                plots["confusion_matrix"] = path
                embedded["confusion_matrix"] = b64
        except Exception as e:
            logger.warning(f"Could not generate confusion matrix: {e}")

        # Cumulative Gains
        try:
            if "cumulative_gains" in metrics:
                path, b64 = plot_generator.cumulative_gains_plot_embedded(
                    metrics["cumulative_gains"]
                )
                plots["cumulative_gains"] = path
                embedded["cumulative_gains"] = b64
        except Exception as e:
            logger.warning(f"Could not generate cumulative gains: {e}")

        # Lift Chart
        try:
            if "cumulative_gains" in metrics:
                path, b64 = plot_generator.lift_chart_plot_embedded(metrics["cumulative_gains"])
                plots["lift_chart"] = path
                embedded["lift_chart"] = b64
        except Exception as e:
            logger.warning(f"Could not generate lift chart: {e}")

        # Probability Distribution
        try:
            path, b64 = plot_generator.probability_distribution_plot_embedded(y_true, y_proba)
            plots["probability_distribution"] = path
            embedded["probability_distribution"] = b64
        except Exception as e:
            logger.warning(f"Could not generate probability distribution: {e}")

        # Calibration Curve
        try:
            path, b64 = plot_generator.calibration_plot_embedded(y_true, y_proba)
            plots["calibration"] = path
            embedded["calibration"] = b64
        except Exception as e:
            logger.warning(f"Could not generate calibration curve: {e}")

        # Feature Importance
        if model is not None and feature_names is not None:
            try:
                inner = getattr(model, "_model", None)
                importances = None
                if inner is not None:
                    if hasattr(inner, "feature_importances_"):
                        importances = inner.feature_importances_
                    elif hasattr(inner, "get_feature_importance"):
                        importances = inner.get_feature_importance()

                if importances is not None:
                    path, b64 = plot_generator.feature_importance_plot_embedded(
                        feature_names, importances
                    )
                    plots["feature_importance"] = path
                    embedded["feature_importance"] = b64
            except Exception as e:
                logger.warning(f"Could not generate feature importance plot: {e}")

        return plots, embedded

    def _generate_plots(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        y_pred: np.ndarray,
        metrics: Dict,
        model=None,
        feature_names: Optional[List[str]] = None,
        threshold_metrics: Optional[Dict] = None,
        threshold: float = 0.5,
    ) -> tuple:
        """
        Generates all visualizations.

        Returns:
            Tuple of (plots_paths dict, plots_embedded dict)
        """
        plots = {}
        embedded = {}

        # ROC Curve
        try:
            path, b64 = self.plot_generator.roc_curve_plot_embedded(
                y_true, y_proba, metrics.get("auc", 0)
            )
            plots["roc_curve"] = path
            embedded["roc_curve"] = b64
        except Exception as e:
            logger.warning(f"Could not generate ROC curve: {e}")

        # Precision-Recall Curve
        try:
            path, b64 = self.plot_generator.precision_recall_plot_embedded(y_true, y_proba)
            plots["precision_recall"] = path
            embedded["precision_recall"] = b64
        except Exception as e:
            logger.warning(f"Could not generate PR curve: {e}")

        # Confusion Matrix
        try:
            cm = metrics.get("confusion_matrix", {})
            if "matrix" in cm:
                path, b64 = self.plot_generator.confusion_matrix_plot_embedded(
                    np.array(cm["matrix"])
                )
                plots["confusion_matrix"] = path
                embedded["confusion_matrix"] = b64
        except Exception as e:
            logger.warning(f"Could not generate confusion matrix: {e}")

        # Cumulative Gains
        try:
            if "cumulative_gains" in metrics:
                path, b64 = self.plot_generator.cumulative_gains_plot_embedded(
                    metrics["cumulative_gains"]
                )
                plots["cumulative_gains"] = path
                embedded["cumulative_gains"] = b64
        except Exception as e:
            logger.warning(f"Could not generate cumulative gains: {e}")

        # Lift Chart
        try:
            if "cumulative_gains" in metrics:
                path, b64 = self.plot_generator.lift_chart_plot_embedded(
                    metrics["cumulative_gains"]
                )
                plots["lift_chart"] = path
                embedded["lift_chart"] = b64
        except Exception as e:
            logger.warning(f"Could not generate lift chart: {e}")

        # Probability Distribution
        try:
            path, b64 = self.plot_generator.probability_distribution_plot_embedded(y_true, y_proba)
            plots["probability_distribution"] = path
            embedded["probability_distribution"] = b64
        except Exception as e:
            logger.warning(f"Could not generate probability distribution: {e}")

        # Calibration Curve
        try:
            path, b64 = self.plot_generator.calibration_plot_embedded(y_true, y_proba)
            plots["calibration"] = path
            embedded["calibration"] = b64
        except Exception as e:
            logger.warning(f"Could not generate calibration curve: {e}")

        # Threshold Sweep (static)
        try:
            if threshold_metrics is not None:
                path, b64 = self.plot_generator.threshold_sweep_plot_embedded(
                    threshold_metrics, threshold
                )
                plots["threshold_sweep"] = path
                embedded["threshold_sweep"] = b64
        except Exception as e:
            logger.warning(f"Could not generate threshold sweep plot: {e}")

        # Feature Importance (MEJORAS P2-8)
        if model is not None and feature_names is not None:
            try:
                inner = getattr(model, "_model", None)
                importances = None
                if inner is not None:
                    if hasattr(inner, "feature_importances_"):
                        importances = inner.feature_importances_
                    elif hasattr(inner, "get_feature_importance"):
                        importances = inner.get_feature_importance()

                if importances is not None:
                    path, b64 = self.plot_generator.feature_importance_plot_embedded(
                        feature_names, importances
                    )
                    plots["feature_importance"] = path
                    embedded["feature_importance"] = b64
            except Exception as e:
                logger.warning(f"Could not generate feature importance plot: {e}")

        return plots, embedded

    def _get_model_info(self, model) -> Dict:
        """Gets model information for the report (MEJORAS P2-9)."""
        # EnsembleModel: expose ensemble description and component info
        if hasattr(model, "ensemble_description"):
            info: Dict = {
                "model_class": model.ensemble_description,
                "method": model.method,
                "base_models": model.model_types,
            }
            if model.method == "stacking" and model._meta_learner is not None:
                info["meta_learner"] = model._meta_learner.__class__.__name__
            if model.weights:
                info["weights"] = model.weights
            return info

        # Single model: use type string from config when available
        _type_map = {
            "LGBMModelAdapter": "lightgbm",
            "CATModelAdapter": "catboost",
            "NNModelAdapter": "neural_network",
            "LSTMNNModelAdapter": "lstm",
        }
        model_config = getattr(model, "config", {}) or {}
        if "type" in model_config:
            model_class_label = model_config["type"]
        else:
            model_class_label = _type_map.get(model.__class__.__name__, model.__class__.__name__)

        info = {"model_class": model_class_label}

        inner = getattr(model, "_model", None)
        if inner is not None:
            info["inner_model"] = inner.__class__.__name__

            # Hyperparameters (scikit-learn compatible API)
            if hasattr(inner, "get_params"):
                try:
                    params = inner.get_params()
                    # Filter out nested objects; keep scalar/string params
                    info["hyperparams"] = {
                        k: v
                        for k, v in params.items()
                        if isinstance(v, (int, float, str, bool, type(None)))
                    }
                except Exception as e:
                    logger.debug("Could not retrieve hyperparams from inner model: %s", e)

            # Number of features seen during fit
            if hasattr(inner, "n_features_in_"):
                info["n_features"] = int(inner.n_features_in_)

            # Number of estimators / iterations
            if hasattr(inner, "n_estimators"):
                info["n_estimators"] = inner.n_estimators
            elif hasattr(inner, "num_trees"):
                info["n_estimators"] = inner.num_trees()

        return info

    def _reconcile_headline_with_segments(
        self,
        metrics_results: Dict[str, Any],
        y_true: np.ndarray,
        y_proba: np.ndarray,
        test_df: pd.DataFrame,
        seg_config: Dict,
        segmented_metrics: Dict[str, Dict],
        global_threshold: float,
    ) -> Dict[str, Any]:
        """Reconcile headline metrics with the per-segment operating point.

        When ``segmented_evaluation`` is enabled with a per-segment threshold
        mode (youden, f1_optimal, recall_target), the headline ``/metrics/*``
        previously reported global-threshold numbers. This method replaces
        them with the per-segment aggregate (each row predicted positive iff
        ``probability >= its_own_segment_threshold``), while preserving the
        global-threshold numbers under ``/metrics/global_threshold_metrics/``.

        Uses the first segment definition in ``by`` as the primary
        segmentation (matching the deployed ``segment_thresholds_*.json``).

        Args:
            metrics_results: Current headline metrics dict (global threshold).
            y_true: True binary labels for the test set.
            y_proba: Predicted probabilities for the test set.
            test_df: Full test DataFrame (with segment columns).
            seg_config: The ``segmented_evaluation`` config dict.
            segmented_metrics: Computed per-segment metrics dict.
            global_threshold: The global threshold used for the original headline.

        Returns:
            Updated ``metrics_results`` with per-segment headline and preserved
            global-threshold metrics.
        """
        seg_by = seg_config.get("by", [])
        if not seg_by:
            return metrics_results

        # Use the first segment definition as the primary segmentation
        primary_seg = seg_by[0]

        # Build per-row segment values (same logic as in execute())
        if "+" in primary_seg:
            cols = [c.strip() for c in primary_seg.split("+")]
            missing = [c for c in cols if c not in test_df.columns]
            if missing:
                logger.warning(
                    "Primary segment '%s' has missing columns %s; "
                    "cannot reconcile headline. Keeping global-threshold metrics.",
                    primary_seg,
                    missing,
                )
                return metrics_results
            segment_values = test_df[cols[0]].astype(str).to_numpy()
            for c in cols[1:]:
                segment_values = segment_values + "|" + test_df[c].astype(str).to_numpy()
            display_name = f"{primary_seg} (combined)"
        else:
            if primary_seg not in test_df.columns:
                logger.warning(
                    "Primary segment '%s' not found in test data; "
                    "cannot reconcile headline. Keeping global-threshold metrics.",
                    primary_seg,
                )
                return metrics_results
            segment_values = test_df[primary_seg].astype(str).to_numpy()
            display_name = primary_seg

        seg_results = segmented_metrics.get(display_name)
        if not seg_results:
            logger.warning(
                "No segmented metrics found for '%s'; "
                "cannot reconcile headline. Keeping global-threshold metrics.",
                display_name,
            )
            return metrics_results

        # Build per-row threshold from segment thresholds
        threshold_map = {k: v["threshold"] for k, v in seg_results.items()}
        per_row_threshold = np.array(
            [threshold_map.get(sv, global_threshold) for sv in segment_values]
        )

        # Predict using each row's own segment threshold
        y_pred_segmented = (y_proba >= per_row_threshold).astype(int)

        # Preserve global-threshold metrics before overwriting
        global_metrics = {
            "threshold": metrics_results.get("threshold"),
            "recall": metrics_results.get("recall"),
            "precision": metrics_results.get("precision"),
            "f1": metrics_results.get("f1"),
            "confusion_matrix": metrics_results.get("confusion_matrix"),
        }

        # Compute new headline from per-segment predictions
        seg_threshold_mode = seg_config.get("threshold_mode", "youden")
        seg_calc = Metrics(y_true, y_pred_segmented, y_proba, threshold=global_threshold)
        new_metrics = seg_calc.calculate_all(self.metrics)

        metrics_results["global_threshold_metrics"] = global_metrics
        metrics_results["threshold"] = None  # no single threshold (segment-based)
        metrics_results["threshold_mode"] = f"segment_{seg_threshold_mode}"

        # Update headline operating-point metrics
        for key in ("recall", "precision", "f1", "confusion_matrix"):
            if key in new_metrics:
                metrics_results[key] = new_metrics[key]

        logger.info(
            "\n%s\nHEADLINE RECONCILED WITH SEGMENTED EVALUATION\n%s\n"
            "Headline now reflects per-segment aggregate (mode=%s).\n"
            "  Segment headline: recall=%.4f  precision=%.4f  f1=%.4f\n"
            "  Global (preserved): recall=%.4f  precision=%.4f  f1=%.4f  thr=%.4f\n%s",
            "=" * 60,
            "=" * 60,
            seg_threshold_mode,
            metrics_results.get("recall", 0),
            metrics_results.get("precision", 0),
            metrics_results.get("f1", 0),
            global_metrics.get("recall", 0),
            global_metrics.get("precision", 0),
            global_metrics.get("f1", 0),
            global_threshold,
            "=" * 60,
        )

        return metrics_results

    def _export_segment_thresholds(
        self,
        segmented_metrics: Dict,
        output_dir: Path,
        global_threshold: float,
        threshold_mode: str,
    ) -> List[Path]:
        """Export segment threshold information to JSON files.

        For each segment column in segmented_metrics, creates a JSON file with
        the threshold configuration and per-segment metrics.

        Args:
            segmented_metrics: Dict mapping segment column names to their
                segment values and metrics. Each segment value contains
                threshold, threshold_mode, auc, n_samples, etc.
            output_dir: Directory where JSON files will be written
            global_threshold: The default/global threshold used for evaluation
            threshold_mode: The threshold mode used (e.g., "youden", "global")

        Returns:
            List of Path objects for the written JSON files
        """
        written_files: List[Path] = []

        if not segmented_metrics:
            logger.debug("No segmented metrics to export")
            return written_files

        # Resolve threshold alias for export consistency
        effective_mode = "youden" if threshold_mode == "segment" else threshold_mode

        for segment_column, segment_data in segmented_metrics.items():
            # Build the export structure
            export_data = {
                "segment_column": segment_column,
                "threshold_mode": effective_mode,
                "default_threshold": global_threshold,
                "segments": segment_data,
            }

            # Write to JSON file
            json_path = output_dir / f"segment_thresholds_{segment_column}.json"
            with open(json_path, "w") as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Exported segment thresholds to: {json_path}")
            written_files.append(json_path)

        return written_files
