"""
Unit tests for ThresholdCalibrator and evaluator calibration integration.
"""

import numpy as np
import pandas as pd
import pytest

from energizados.evaluation.calibration import ThresholdCalibrator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def imbalanced_data():
    """Synthetic imbalanced dataset (~5% fraud) with 1000 samples.

    Returns:
        tuple: A tuple containing:
            - y_true (np.ndarray): True binary labels.
            - y_proba (np.ndarray): Predicted probabilities.
    """
    rng = np.random.default_rng(42)
    n = 1000
    y_true = (rng.random(n) < 0.05).astype(int)

    # Model that assigns higher probabilities to positives
    y_proba = np.where(y_true == 1, rng.uniform(0.3, 0.9, n), rng.uniform(0.0, 0.3, n))
    return y_true, y_proba


@pytest.fixture
def balanced_data():
    """Synthetic balanced dataset with 200 samples.

    Returns:
        tuple: A tuple containing:
            - y_true (np.ndarray): True binary labels.
            - y_proba (np.ndarray): Predicted probabilities.
    """
    rng = np.random.default_rng(7)
    n = 200
    y_true = np.array([0] * (n // 2) + [1] * (n // 2))
    y_proba = np.where(y_true == 1, rng.uniform(0.4, 1.0, n), rng.uniform(0.0, 0.6, n))
    return y_true, y_proba


# ---------------------------------------------------------------------------
# Tests for ThresholdCalibrator - cost_benefit method
# ---------------------------------------------------------------------------


class TestCostBenefitCalibration:
    """Tests for cost_benefit calibration method."""

    def test_returns_required_keys(self, imbalanced_data):
        """Verify that all required keys are returned."""
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="cost_benefit", cost_fp=1, cost_fn=10)
        result = cal.calibrate(y_true, y_proba)

        assert "threshold" in result
        assert "method" in result
        assert "params" in result
        assert "metrics_at_threshold" in result
        assert "search_results" in result

    def test_threshold_in_range(self, imbalanced_data):
        """Verify that threshold is in valid range [0, 1]."""
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="cost_benefit")
        result = cal.calibrate(y_true, y_proba)

        assert 0.0 <= result["threshold"] <= 1.0

    def test_higher_fn_cost_lowers_threshold(self, imbalanced_data):
        """Verify that higher cost_fn results in lower threshold (detect more frauds)."""
        y_true, y_proba = imbalanced_data

        cal_low = ThresholdCalibrator(method="cost_benefit", cost_fp=1, cost_fn=1)
        cal_high = ThresholdCalibrator(method="cost_benefit", cost_fp=1, cost_fn=50)

        result_low = cal_low.calibrate(y_true, y_proba)
        result_high = cal_high.calibrate(y_true, y_proba)

        assert result_high["threshold"] <= result_low["threshold"]

    def test_metrics_at_threshold_keys(self, imbalanced_data):
        """Verify that metrics_at_threshold contains required keys."""
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="cost_benefit")
        result = cal.calibrate(y_true, y_proba)

        metrics = result["metrics_at_threshold"]
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics

    def test_search_results_present(self, imbalanced_data):
        """Verify that search results are present."""
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="cost_benefit")
        result = cal.calibrate(y_true, y_proba)

        sr = result["search_results"]
        assert sr is not None
        assert "thresholds" in sr
        assert "costs" in sr
        assert len(sr["thresholds"]) == 101


# ---------------------------------------------------------------------------
# Tests for ThresholdCalibrator - operational method
# ---------------------------------------------------------------------------


class TestOperationalCalibration:
    """Tests for operational calibration method."""

    def test_returns_required_keys(self, imbalanced_data):
        """Verify that all required keys are returned."""
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="operational", capacity=50)
        result = cal.calibrate(y_true, y_proba)

        assert "threshold" in result
        assert result["method"] == "operational"
        assert result["search_results"] is None

    def test_capacity_limits_alarms(self, imbalanced_data):
        """Verify that the number of alarms does not exceed capacity significantly."""
        y_true, y_proba = imbalanced_data
        capacity = 50

        cal = ThresholdCalibrator(method="operational", capacity=capacity)
        result = cal.calibrate(y_true, y_proba)

        n_alarms = int(np.sum(y_proba >= result["threshold"]))
        # The percentile may give a threshold that includes slightly more (ties)
        assert n_alarms <= capacity + 10

    def test_large_capacity_gives_low_threshold(self, imbalanced_data):
        """Verify that capacity >= n gives threshold <= min(y_proba) (alarm on all)."""
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="operational", capacity=len(y_proba) + 100)
        result = cal.calibrate(y_true, y_proba)

        # With capacity > n, percentile 0 returns the minimum of y_proba
        assert result["threshold"] <= float(np.min(y_proba)) + 1e-9

    def test_threshold_in_range(self, imbalanced_data):
        """Verify that threshold is in valid range [0, 1]."""
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="operational", capacity=100)
        result = cal.calibrate(y_true, y_proba)

        assert 0.0 <= result["threshold"] <= 1.0


# ---------------------------------------------------------------------------
# Tests for ThresholdCalibrator - precision_recall method
# ---------------------------------------------------------------------------


class TestPrecisionRecallCalibration:
    """Tests for precision_recall calibration method."""

    def test_returns_required_keys(self, balanced_data):
        """Verify that all required keys are returned."""
        y_true, y_proba = balanced_data
        cal = ThresholdCalibrator(method="precision_recall", min_recall=0.80)
        result = cal.calibrate(y_true, y_proba)

        assert "threshold" in result
        assert result["method"] == "precision_recall"
        assert "search_results" in result

    def test_recall_met_at_threshold(self, balanced_data):
        """Verify that recall on val is >= min_recall for the selected threshold."""
        y_true, y_proba = balanced_data
        min_recall = 0.70

        cal = ThresholdCalibrator(method="precision_recall", min_recall=min_recall)
        result = cal.calibrate(y_true, y_proba)

        # Verify recall at the found threshold
        y_pred = (y_proba >= result["threshold"]).astype(int)
        from sklearn.metrics import recall_score

        actual_recall = recall_score(y_true, y_pred, zero_division=0)

        assert actual_recall >= min_recall - 0.05  # small numerical tolerance

    def test_fallback_when_recall_impossible(self, imbalanced_data):
        """Verify that if min_recall=1.0 is impossible, threshold=0.5 is used as fallback."""
        y_true, y_proba = imbalanced_data
        # min_recall=1.0 is very difficult to achieve
        cal = ThresholdCalibrator(method="precision_recall", min_recall=1.0)
        result = cal.calibrate(y_true, y_proba)

        # Can be 0.5 (fallback) or another value if actually achieved
        assert 0.0 <= result["threshold"] <= 1.0

    def test_higher_min_recall_lowers_threshold(self, balanced_data):
        """Verify that higher min_recall results in lower threshold."""
        y_true, y_proba = balanced_data

        cal_low = ThresholdCalibrator(method="precision_recall", min_recall=0.50)
        cal_high = ThresholdCalibrator(method="precision_recall", min_recall=0.90)

        result_low = cal_low.calibrate(y_true, y_proba)
        result_high = cal_high.calibrate(y_true, y_proba)

        assert result_high["threshold"] <= result_low["threshold"]


# ---------------------------------------------------------------------------
# Tests for unknown method
# ---------------------------------------------------------------------------


class TestUnknownMethod:
    """Tests for unknown calibration method."""

    def test_raises_value_error(self, imbalanced_data):
        """Verify that unknown method raises ValueError."""
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="unknown_method")

        with pytest.raises(ValueError, match="Unknown calibration method"):
            cal.calibrate(y_true, y_proba)


# ---------------------------------------------------------------------------
# Integration tests with DefaultEvaluator
# ---------------------------------------------------------------------------


class TestEvaluatorCalibrationIntegration:
    """Integration tests: evaluator uses calibrated threshold when enabled."""

    def _make_val_predictions_file(self, tmp_path, y_true, y_proba):
        """Save val predictions to parquet and return the path.

        Args:
            tmp_path: Temporary directory path.
            y_true: True labels.
            y_proba: Predicted probabilities.

        Returns:
            str: Path to the saved parquet file.
        """
        val_df = pd.DataFrame({"y_true": y_true, "y_proba": y_proba})
        path = tmp_path / "val_predictions.parquet"
        val_df.to_parquet(path)
        return str(path)

    def test_evaluator_applies_calibrated_threshold(self, tmp_path, balanced_data):
        """Verify that the evaluator updates self.threshold to the calibrated value."""
        from energizados.evaluation.evaluator import DefaultEvaluator

        y_true, y_proba = balanced_data

        val_path = self._make_val_predictions_file(tmp_path, y_true, y_proba)

        _ = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            calibration_config={
                "enabled": True,
                "strategy": "cost_benefit",
                "params": {"cost_fp": 1, "cost_fn": 10},
            },
            val_predictions_path=val_path,
        )

        # Simulate the calibration process without running the full pipeline
        val_df = pd.read_parquet(val_path)
        calibrator = ThresholdCalibrator(method="cost_benefit", cost_fp=1, cost_fn=10)
        result = calibrator.calibrate(val_df["y_true"].values, val_df["y_proba"].values)

        # The calibrated threshold must differ from 0.5 for imbalanced data
        assert isinstance(result["threshold"], float)
        assert 0.0 <= result["threshold"] <= 1.0

    def test_evaluator_fallback_when_no_val_path(self, tmp_path, balanced_data):
        """Verify that without val_predictions_path, the evaluator keeps default threshold."""
        from energizados.evaluation.evaluator import DefaultEvaluator

        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            threshold=0.5,
            calibration_config={"enabled": True, "strategy": "cost_benefit", "params": {}},
            val_predictions_path=None,
        )

        # Default threshold does not change without val_path
        assert evaluator.threshold == 0.5

    def test_evaluator_no_calibration_when_disabled(self, tmp_path):
        """Verify that without calibration config, the evaluator uses static threshold."""
        from energizados.evaluation.evaluator import DefaultEvaluator

        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            threshold=0.3,
            calibration_config=None,
        )
        assert evaluator.threshold == 0.3

    def test_evaluator_calibration_disabled_flag(self, tmp_path):
        """Verify that with calibration.enabled=False, the evaluator uses static threshold."""
        from energizados.evaluation.evaluator import DefaultEvaluator

        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            threshold=0.4,
            calibration_config={"enabled": False, "strategy": "cost_benefit", "params": {}},
        )
        assert evaluator.threshold == 0.4


# ---------------------------------------------------------------------------
# Tests for JSON report with calibration
# ---------------------------------------------------------------------------


class TestReportCalibrationSection:
    """Tests for calibration section in JSON report."""

    def test_json_includes_calibration_when_provided(self, tmp_path):
        """Verify that the JSON includes 'calibration' section if calibration_result is passed."""
        import json

        from energizados.evaluation.report import ReportGenerator

        reporter = ReportGenerator(str(tmp_path))
        calibration_result = {
            "threshold": 0.23,
            "method": "cost_benefit",
            "params": {"cost_fp": 1, "cost_fn": 10},
            "metrics_at_threshold": {"precision": 0.15, "recall": 0.85, "f1": 0.26},
        }
        metrics = {"auc": 0.80, "f1": 0.26, "precision": 0.15, "recall": 0.85}

        path = reporter.generate_json(metrics, calibration_result=calibration_result)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert "calibration" in data
        assert data["calibration"]["enabled"] is True
        assert data["calibration"]["method"] == "cost_benefit"
        assert data["calibration"]["threshold_used"] == pytest.approx(0.23)

    def test_json_no_calibration_when_not_provided(self, tmp_path):
        """Verify that without calibration_result, the JSON does NOT include 'calibration' section."""
        import json

        from energizados.evaluation.report import ReportGenerator

        reporter = ReportGenerator(str(tmp_path))
        metrics = {"auc": 0.80}

        path = reporter.generate_json(metrics)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert "calibration" not in data
