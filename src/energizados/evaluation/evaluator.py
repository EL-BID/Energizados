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
        self.calibration_config = calibration_config
        self.val_predictions_path = val_predictions_path

        # Initialize generators
        self.plot_generator = PlotGenerator(str(self.output_dir))
        self.report_generator = ReportGenerator(str(self.output_dir))

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executes complete evaluation."""
        logger.info("\n" + "=" * 50)
        logger.info("EVALUATION STEP")
        logger.info("=" * 50)

        # Get paths from context if not provided
        if context:
            self.input_path = self.input_path or context.get("test_path")
            self.model_path = self.model_path or context.get("model_path")
            self.feature_engineering_path = self.feature_engineering_path or context.get("feature_engineering_path")

        # 1. Load model and feature engineering
        model = self._load_model()
        feature_engineering = self._load_feature_engineering()

        # 2. Load test data
        test_df = pd.read_parquet(self.input_path)
        logger.info(f"Test dataset shape: {test_df.shape}")

        X_test = test_df.drop(columns=[self.target_column])
        y_test = test_df[self.target_column]

        # 3. Apply feature engineering if it exists
        if feature_engineering is not None:
            logger.info("Applying feature engineering...")
            X_test_transformed = feature_engineering.transform(X_test)
        else:
            X_test_transformed = X_test

        # 4. Calibrate threshold if configured
        calibration_result = None
        if self.calibration_config and self.calibration_config.get("enabled", False):
            val_path = self.val_predictions_path or (context.get("val_predictions_path") if context else None)
            if val_path and Path(val_path).exists():
                val_df = pd.read_parquet(val_path)
                calibrator = ThresholdCalibrator(
                    method=self.calibration_config.get("method", "cost_benefit"),
                    **self.calibration_config.get("params", {}),
                )
                calibration_result = calibrator.calibrate(val_df["y_true"].values, val_df["y_proba"].values)
                self.threshold = calibration_result["threshold"]
                logger.info(f"Calibrated threshold: {self.threshold:.4f} " f"(method: {calibration_result['method']})")
            else:
                logger.warning("Calibration enabled but val_predictions_path not found, " "using default threshold")

        # 5. Get predictions
        logger.info("Generating predictions...")
        y_proba = model.predict_proba(X_test_transformed)
        y_pred = (y_proba >= self.threshold).astype(int)

        # 6. Calculate metrics
        logger.info("Calculating metrics...")
        metrics_calculator = Metrics(y_test, y_pred, y_proba, self.threshold)
        metrics_results = metrics_calculator.calculate_all(self.metrics)

        # Log main metrics
        logger.info(f"\n{'='*50}")
        logger.info("METRICS SUMMARY")
        logger.info(f"{'='*50}")
        logger.info(f"AUC:       {metrics_results.get('auc', 0):.4f}")
        logger.info(f"F1:        {metrics_results.get('f1', 0):.4f}")
        logger.info(f"Precision: {metrics_results.get('precision', 0):.4f}")
        logger.info(f"Recall:    {metrics_results.get('recall', 0):.4f}")
        if "accuracy" in metrics_results:
            logger.info(f"Accuracy:  {metrics_results['accuracy']:.4f}")
        logger.info(f"{'='*50}")
        metrics_results["threshold"] = self.threshold

        # 7. Generate visualizations
        plots_paths = {}
        if self.generate_plots:
            logger.info("Generating plots...")
            plots_paths = self._generate_plots(y_test, y_proba, y_pred, metrics_results)

        # 8. Generate reports
        report_paths = {}
        if self.generate_html_report or self.generate_json_report:
            logger.info("Generating reports...")

            model_info = self._get_model_info(model)

            if self.generate_json_report:
                json_path = self.report_generator.generate_json(metrics_results, model_info, calibration_result=calibration_result)
                report_paths["json"] = json_path

            if self.generate_html_report:
                html_path = self.report_generator.generate_html(metrics_results, plots_paths, model_info)
                report_paths["html"] = html_path

        logger.info(f"\nEvaluation complete. Reports saved to: {self.output_dir}")

        return {
            **context,
            "metrics": metrics_results,
            "plots": plots_paths,
            "reports": report_paths,
            "evaluation_dir": str(self.output_dir),
        }

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validates that necessary inputs exist."""
        # Check model
        if self.model_path and not Path(self.model_path).exists():
            return False

        # Check that input_path was provided or exists in context
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

    def _load_model(self):
        """Loads the trained model."""
        from energizados.core.utils.secure_pickle import secure_load

        logger.info(f"Loading model from: {self.model_path}")
        return secure_load(self.model_path)

    def _load_feature_engineering(self):
        """Loads feature engineering if it exists."""
        from energizados.core.utils.secure_pickle import secure_load

        if self.feature_engineering_path and Path(self.feature_engineering_path).exists():
            logger.info(f"Loading feature engineering from: {self.feature_engineering_path}")
            return secure_load(self.feature_engineering_path)
        return None

    def _generate_plots(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        y_pred: np.ndarray,
        metrics: Dict,
    ) -> Dict[str, str]:
        """Generates all visualizations."""
        plots = {}

        # ROC Curve
        try:
            plots["roc_curve"] = self.plot_generator.roc_curve_plot(y_true, y_proba, metrics.get("auc", 0))
        except Exception as e:
            logger.warning(f"Could not generate ROC curve: {e}")

        # Precision-Recall Curve
        try:
            plots["precision_recall"] = self.plot_generator.precision_recall_plot(y_true, y_proba)
        except Exception as e:
            logger.warning(f"Could not generate PR curve: {e}")

        # Confusion Matrix
        try:
            cm = metrics.get("confusion_matrix", {})
            if "matrix" in cm:
                plots["confusion_matrix"] = self.plot_generator.confusion_matrix_plot(np.array(cm["matrix"]))
        except Exception as e:
            logger.warning(f"Could not generate confusion matrix: {e}")

        # Cumulative Gains
        try:
            if "cumulative_gains" in metrics:
                plots["cumulative_gains"] = self.plot_generator.cumulative_gains_plot(metrics["cumulative_gains"])
        except Exception as e:
            logger.warning(f"Could not generate cumulative gains: {e}")

        # Probability Distribution
        try:
            plots["probability_distribution"] = self.plot_generator.probability_distribution_plot(y_true, y_proba)
        except Exception as e:
            logger.warning(f"Could not generate probability distribution: {e}")

        # Calibration Curve
        try:
            plots["calibration"] = self.plot_generator.calibration_plot(y_true, y_proba)
        except Exception as e:
            logger.warning(f"Could not generate calibration curve: {e}")

        return plots

    def _get_model_info(self, model) -> Dict:
        """Gets model information for the report."""
        info = {
            "model_class": model.__class__.__name__,
        }

        # Try to get additional information
        if hasattr(model, "config"):
            info["config"] = str(model.config)

        if hasattr(model, "_model"):
            info["inner_model"] = model._model.__class__.__name__

        return info
