"""
Evaluator Module for Energizados Framework.

Evaluates ML models using metrics, visualizations and reports.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from energizados.core.base import PipelineStep
from energizados.evaluation.calibration import ThresholdCalibrator
from energizados.evaluation.metrics import Metrics
from energizados.evaluation.plots import PlotGenerator
from energizados.evaluation.report import ReportGenerator

logger = logging.getLogger(__name__)


class DefaultEvaluator(PipelineStep):
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
        ...     input_path="data/splits/test.parquet",
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
        **kwargs,
    ):
        self.input_path = input_path
        self.model_path = model_path
        self.feature_engineering_path = feature_engineering_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.target_column = target_column
        self.threshold = threshold
        self.metrics = metrics or ["auc", "precision", "recall", "f1", "confusion_matrix", "cumulative_gains"]
        self.generate_plots = generate_plots
        self.generate_html_report = generate_html_report
        self.generate_json_report = generate_json_report
        self.segment_columns = segment_columns or []
        self.calibration_config = calibration_config
        self.val_predictions_path = val_predictions_path

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
        feature_engineering_path = self.feature_engineering_path or ctx.get("feature_engineering_path")

        # Validate inputs before loading (MEJORAS P1-4)
        if not input_path:
            raise ValueError("No input_path provided and 'test_path' not found in context.")
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Test dataset not found: {input_path}")

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
        feature_names = list(X_test_transformed.columns) if hasattr(X_test_transformed, "columns") else None

        # 4. Calibrate threshold if configured
        calibration_result = None
        threshold = self.threshold  # local copy — do not mutate self.threshold
        if self.calibration_config and self.calibration_config.get("enabled", False):
            val_path = self.val_predictions_path or ctx.get("val_predictions_path")
            if val_path and Path(val_path).exists():
                val_df = pd.read_parquet(val_path)
                calibrator = ThresholdCalibrator(
                    method=self.calibration_config.get("method", "cost_benefit"),
                    **self.calibration_config.get("params", {}),
                )
                calibration_result = calibrator.calibrate(val_df["y_true"].values, val_df["y_proba"].values)
                threshold = calibration_result["threshold"]
                logger.info(f"Calibrated threshold: {threshold:.4f} (method: {calibration_result['method']})")
            else:
                logger.warning("Calibration enabled but val_predictions_path not found, using default threshold")

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

        # 6b. Segment metrics (MEJORAS P4-15)
        segment_metrics = {}
        if self.segment_columns:
            logger.info(f"Calculating segment metrics for: {self.segment_columns}")
            for col in self.segment_columns:
                if col in test_df.columns:
                    segments = test_df[col].values
                    segment_metrics[col] = metrics_calculator.segment_metrics(segments)
                else:
                    logger.warning(f"Segment column '{col}' not found in test dataset, skipping.")
            if segment_metrics:
                metrics_results["segment_metrics"] = segment_metrics

        # 6c. Threshold sweep metrics
        logger.info("Calculating threshold sweep metrics...")
        threshold_metrics = None
        try:
            threshold_metrics = metrics_calculator.get_threshold_metrics()
        except Exception as e:
            logger.warning(f"Could not calculate threshold metrics: {e}")

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
                plots_interactive["roc_curve"] = eval_plots.roc_curve(fpr.tolist(), tpr.tolist(), metrics_results.get("auc", 0))
            except Exception as e:
                logger.warning(f"Could not generate interactive ROC curve: {e}")

            # Precision-Recall
            try:
                prec_vals, rec_vals, _ = sk_pr_curve(y_test, y_proba)
                ap = float(np.trapz(prec_vals[::-1], rec_vals[::-1]))
                plots_interactive["precision_recall"] = eval_plots.precision_recall_curve(prec_vals.tolist(), rec_vals.tolist(), ap)
            except Exception as e:
                logger.warning(f"Could not generate interactive PR curve: {e}")

            # Confusion matrix heatmap
            try:
                cm = metrics_results.get("confusion_matrix", {})
                if "matrix" in cm:
                    plots_interactive["confusion_matrix"] = eval_plots.confusion_matrix_heatmap(cm["matrix"])
            except Exception as e:
                logger.warning(f"Could not generate interactive confusion matrix: {e}")

            # Cumulative gains
            try:
                if "cumulative_gains" in metrics_results:
                    plots_interactive["cumulative_gains"] = eval_plots.cumulative_gains(metrics_results["cumulative_gains"])
            except Exception as e:
                logger.warning(f"Could not generate interactive cumulative gains: {e}")

            # Lift chart
            try:
                if "cumulative_gains" in metrics_results:
                    plots_interactive["lift_chart"] = eval_plots.lift_chart(metrics_results["cumulative_gains"])
            except Exception as e:
                logger.warning(f"Could not generate interactive lift chart: {e}")

            # Probability distribution
            try:
                plots_interactive["probability_distribution"] = eval_plots.probability_distribution(y_test.tolist(), y_proba.tolist())
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
                        plots_interactive["feature_importance"] = eval_plots.feature_importance(feature_names, importances.tolist())
            except Exception as e:
                logger.warning(f"Could not generate interactive feature importance: {e}")

            # Threshold sweep
            try:
                if threshold_metrics is not None:
                    plots_interactive["threshold_sweep"] = eval_plots.threshold_sweep(threshold_metrics, threshold)
            except Exception as e:
                logger.warning(f"Could not generate interactive threshold sweep: {e}")

            # Segment metrics charts
            try:
                for col_name, col_data in segment_metrics.items():
                    chart_key = f"segment_{col_name}"
                    plots_interactive[chart_key] = eval_plots.segment_metrics_chart(col_data, metric="f1")
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
            path, b64 = self.plot_generator.roc_curve_plot_embedded(y_true, y_proba, metrics.get("auc", 0))
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
                path, b64 = self.plot_generator.confusion_matrix_plot_embedded(np.array(cm["matrix"]))
                plots["confusion_matrix"] = path
                embedded["confusion_matrix"] = b64
        except Exception as e:
            logger.warning(f"Could not generate confusion matrix: {e}")

        # Cumulative Gains
        try:
            if "cumulative_gains" in metrics:
                path, b64 = self.plot_generator.cumulative_gains_plot_embedded(metrics["cumulative_gains"])
                plots["cumulative_gains"] = path
                embedded["cumulative_gains"] = b64
        except Exception as e:
            logger.warning(f"Could not generate cumulative gains: {e}")

        # Lift Chart
        try:
            if "cumulative_gains" in metrics:
                path, b64 = self.plot_generator.lift_chart_plot_embedded(metrics["cumulative_gains"])
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
                path, b64 = self.plot_generator.threshold_sweep_plot_embedded(threshold_metrics, threshold)
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
                    path, b64 = self.plot_generator.feature_importance_plot_embedded(feature_names, importances)
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
                    info["hyperparams"] = {k: v for k, v in params.items() if isinstance(v, (int, float, str, bool, type(None)))}
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
