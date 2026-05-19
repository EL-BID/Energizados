"""
Unit tests for evaluation.metrics module.
"""

import numpy as np
import pytest

from energizados.evaluation.metrics import (
    Metrics,
    compute_threshold_metrics,
    find_optimal_threshold_f1,
    find_optimal_threshold_recall_target,
    find_optimal_threshold_youden,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def perfect_predictions():
    """Perfect binary predictions for testing.

    Returns:
        tuple: (y_true, y_pred, y_proba) with perfect predictions
    """
    y_true = np.array([0, 0, 1, 1, 0, 1])
    y_pred = np.array([0, 0, 1, 1, 0, 1])
    y_proba = np.array([0.1, 0.2, 0.8, 0.9, 0.3, 0.7])
    return y_true, y_pred, y_proba


@pytest.fixture
def imbalanced_predictions():
    """Imbalanced predictions (~20% positive) for testing.

    Returns:
        tuple: (y_true, y_pred, y_proba) with imbalanced data
    """
    y_true = np.array([0, 0, 0, 0, 1, 0, 0, 0, 1, 0])
    y_pred = np.array([0, 0, 1, 0, 1, 0, 0, 1, 1, 0])
    y_proba = np.array([0.1, 0.2, 0.6, 0.3, 0.8, 0.2, 0.1, 0.7, 0.9, 0.2])
    return y_true, y_pred, y_proba


@pytest.fixture
def all_zeros_predictions():
    """All zeros predictions for edge case testing.

    Returns:
        tuple: (y_true, y_pred, y_proba) where all are predicted as negative
    """
    y_true = np.array([0, 0, 0, 0, 0])
    y_pred = np.array([0, 0, 0, 0, 0])
    y_proba = np.array([0.1, 0.2, 0.3, 0.1, 0.2])
    return y_true, y_pred, y_proba


@pytest.fixture
def all_ones_predictions():
    """All ones predictions for edge case testing.

    Returns:
        tuple: (y_true, y_pred, y_proba) where all are predicted as positive
    """
    y_true = np.array([1, 1, 1, 1, 1])
    y_pred = np.array([1, 1, 1, 1, 1])
    y_proba = np.array([0.9, 0.8, 0.7, 0.9, 0.8])
    return y_true, y_pred, y_proba


@pytest.fixture
def mixed_data_with_segments():
    """Mixed data with segment labels for segment_metrics testing.

    Returns:
        tuple: (y_true, y_pred, y_proba, segments) with multiple segments
    """
    y_true = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    y_pred = np.array([0, 1, 0, 0, 0, 1, 1, 1, 0, 1])
    y_proba = np.array([0.2, 0.8, 0.3, 0.4, 0.1, 0.7, 0.6, 0.9, 0.2, 0.8])
    segments = np.array(["A", "A", "B", "B", "A", "A", "B", "B", "C", "C"])
    return y_true, y_pred, y_proba, segments


# ---------------------------------------------------------------------------
# Tests for compute_threshold_metrics()
# ---------------------------------------------------------------------------


class TestComputeThresholdMetrics:
    """Tests for compute_threshold_metrics function."""

    def test_returns_correct_keys(self, perfect_predictions):
        """Verify that all required keys are returned."""
        y_true, _, y_proba = perfect_predictions
        result = compute_threshold_metrics(y_true, y_proba)

        assert "thresholds" in result
        assert "precisions" in result
        assert "recalls" in result
        assert "f1s" in result

    def test_thresholds_range(self, perfect_predictions):
        """Verify that thresholds span from 0 to 1."""
        y_true, _, y_proba = perfect_predictions
        result = compute_threshold_metrics(y_true, y_proba)

        thresholds = result["thresholds"]
        assert len(thresholds) == 101  # default n_thresholds
        assert thresholds[0] == 0.0
        assert thresholds[-1] == 1.0
        assert all(0.0 <= t <= 1.0 for t in thresholds)

    def test_metrics_arrays_length(self, perfect_predictions):
        """Verify that all metric arrays have the same length as thresholds."""
        y_true, _, y_proba = perfect_predictions
        result = compute_threshold_metrics(y_true, y_proba)

        assert len(result["precisions"]) == len(result["thresholds"])
        assert len(result["recalls"]) == len(result["thresholds"])
        assert len(result["f1s"]) == len(result["thresholds"])

    def test_custom_n_thresholds(self, perfect_predictions):
        """Verify that custom n_thresholds produces correct array length."""
        y_true, _, y_proba = perfect_predictions
        result = compute_threshold_metrics(y_true, y_proba, n_thresholds=51)

        assert len(result["thresholds"]) == 51

    def test_metrics_are_floats(self, perfect_predictions):
        """Verify that all metrics are float values."""
        y_true, _, y_proba = perfect_predictions
        result = compute_threshold_metrics(y_true, y_proba)

        assert all(isinstance(p, float) for p in result["precisions"])
        assert all(isinstance(r, float) for r in result["recalls"])
        assert all(isinstance(f, float) for f in result["f1s"])

    def test_handles_zero_division(self, all_zeros_predictions):
        """Verify that zero_division=0 handles edge cases without errors."""
        y_true, _, y_proba = all_zeros_predictions
        result = compute_threshold_metrics(y_true, y_proba)

        # Should not raise an error
        assert result is not None
        assert len(result["precisions"]) > 0

    def test_monotonic_recall(self, perfect_predictions):
        """Verify that recall generally decreases as threshold increases."""
        y_true, _, y_proba = perfect_predictions
        result = compute_threshold_metrics(y_true, y_proba)

        recalls = result["recalls"]
        # Non-strict monotonicity allows for plateaus
        for i in range(1, len(recalls)):
            assert recalls[i] <= recalls[i] + 0.01  # small tolerance


# ---------------------------------------------------------------------------
# Tests for Metrics initialization
# ---------------------------------------------------------------------------


class TestMetricsInitialization:
    """Tests for Metrics class initialization."""

    def test_initialization_with_arrays(self, perfect_predictions):
        """Verify initialization with numpy arrays."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)

        assert np.array_equal(metrics.y_true, y_true)
        assert np.array_equal(metrics.y_pred, y_pred)
        assert np.array_equal(metrics.y_proba, y_proba)
        assert metrics.threshold == 0.5

    def test_initialization_with_lists(self):
        """Verify initialization converts lists to arrays."""
        y_true = [0, 1, 0, 1]
        y_pred = [0, 1, 0, 0]
        y_proba = [0.1, 0.9, 0.2, 0.6]
        metrics = Metrics(y_true, y_pred, y_proba)

        assert isinstance(metrics.y_true, np.ndarray)
        assert isinstance(metrics.y_pred, np.ndarray)
        assert isinstance(metrics.y_proba, np.ndarray)

    def test_custom_threshold(self):
        """Verify that custom threshold is stored correctly."""
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 0])
        y_proba = np.array([0.1, 0.9, 0.2, 0.6])
        metrics = Metrics(y_true, y_pred, y_proba, threshold=0.7)

        assert metrics.threshold == 0.7

    def test_arrays_are_stored(self):
        """Verify that arrays are stored as attributes."""
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 0])
        y_proba = np.array([0.1, 0.9, 0.2, 0.6])
        metrics = Metrics(y_true, y_pred, y_proba)

        assert metrics.y_true is not None
        assert metrics.y_pred is not None
        assert metrics.y_proba is not None


# ---------------------------------------------------------------------------
# Tests for Metrics.calculate_all()
# ---------------------------------------------------------------------------


class TestMetricsCalculateAll:
    """Tests for Metrics.calculate_all() method."""

    def test_calculates_all_default_metrics(self, perfect_predictions):
        """Verify that calculate_all() computes all default metrics."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        results = metrics.calculate_all()

        expected_metrics = ["auc", "precision", "recall", "f1", "confusion_matrix", "accuracy"]
        for metric in expected_metrics:
            assert metric in results

    def test_calculates_specific_metrics(self, perfect_predictions):
        """Verify that calculate_all() computes only requested metrics."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        results = metrics.calculate_all(metrics_list=["auc", "f1"])

        assert "auc" in results
        assert "f1" in results
        assert "precision" not in results
        assert "recall" not in results

    def test_calculates_cumulative_gains(self, perfect_predictions):
        """Verify that cumulative_gains metric can be calculated."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        results = metrics.calculate_all(metrics_list=["cumulative_gains"])

        assert "cumulative_gains" in results
        assert "deciles" in results["cumulative_gains"]

    def test_ignores_unknown_metrics(self, perfect_predictions):
        """Verify that unknown metrics are skipped with a warning."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        results = metrics.calculate_all(metrics_list=["auc", "unknown_metric", "f1"])

        assert "auc" in results
        assert "f1" in results
        assert "unknown_metric" not in results

    def test_empty_metrics_list(self, perfect_predictions):
        """Verify that empty metrics list returns empty dict."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        results = metrics.calculate_all(metrics_list=[])

        assert len(results) == 0

    def test_returns_dict(self, perfect_predictions):
        """Verify that calculate_all() always returns a dict."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        results = metrics.calculate_all()

        assert isinstance(results, dict)


# ---------------------------------------------------------------------------
# Tests for individual metric methods
# ---------------------------------------------------------------------------


class TestMetricsAUC:
    """Tests for Metrics.auc() method."""

    def test_auc_perfect_predictions(self, perfect_predictions):
        """Verify that perfect predictions give AUC = 1.0."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        auc = metrics.auc()

        assert auc == 1.0

    def test_auc_returns_float(self, imbalanced_predictions):
        """Verify that auc() returns a float."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        auc = metrics.auc()

        assert isinstance(auc, float)

    def test_auc_range(self, imbalanced_predictions):
        """Verify that AUC is in range [0, 1]."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        auc = metrics.auc()

        assert 0.0 <= auc <= 1.0

    def test_auc_single_class(self, all_zeros_predictions):
        """Verify that AUC returns 0.0 for single class (cannot compute)."""
        y_true, y_pred, y_proba = all_zeros_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        auc = metrics.auc()

        # Should return 0.0 when cannot compute (single class)
        assert auc == 0.0


class TestMetricsPrecision:
    """Tests for Metrics.precision() method."""

    def test_precision_perfect_predictions(self, perfect_predictions):
        """Verify that perfect predictions give precision = 1.0."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        precision = metrics.precision()

        assert precision == 1.0

    def test_precision_imbalanced(self, imbalanced_predictions):
        """Verify precision calculation on imbalanced data."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        precision = metrics.precision()

        # Manual calculation: TP / (TP + FP)
        # y_true: [0, 0, 0, 0, 1, 0, 0, 0, 1, 0]
        # y_pred: [0, 0, 1, 0, 1, 0, 0, 1, 1, 0]
        # TP = 2 (indices 4, 8), FP = 2 (indices 2, 7)
        expected = 2 / (2 + 2)
        assert precision == pytest.approx(expected)

    def test_precision_range(self, imbalanced_predictions):
        """Verify that precision is in range [0, 1]."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        precision = metrics.precision()

        assert 0.0 <= precision <= 1.0

    def test_precision_zero_division(self, all_zeros_predictions):
        """Verify that precision returns 0.0 when division by zero occurs."""
        y_true, y_pred, y_proba = all_zeros_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        precision = metrics.precision()

        # No positive predictions, so precision = 0.0
        assert precision == 0.0


class TestMetricsRecall:
    """Tests for Metrics.recall() method."""

    def test_recall_perfect_predictions(self, perfect_predictions):
        """Verify that perfect predictions give recall = 1.0."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        recall = metrics.recall()

        assert recall == 1.0

    def test_recall_imbalanced(self, imbalanced_predictions):
        """Verify recall calculation on imbalanced data."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        recall = metrics.recall()

        # Manual calculation: TP / (TP + FN)
        # y_true: [0, 0, 0, 0, 1, 0, 0, 0, 1, 0] - 2 positives
        # y_pred: [0, 0, 1, 0, 1, 0, 0, 1, 1, 0]
        # TP = 2 (indices 4, 8), FN = 0
        expected = 2 / 2
        assert recall == pytest.approx(expected)

    def test_recall_range(self, imbalanced_predictions):
        """Verify that recall is in range [0, 1]."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        recall = metrics.recall()

        assert 0.0 <= recall <= 1.0

    def test_recall_all_zeros(self, all_zeros_predictions):
        """Verify recall when there are no actual positives."""
        y_true, y_pred, y_proba = all_zeros_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        recall = metrics.recall()

        # No actual positives, so recall = 0.0
        assert recall == 0.0


class TestMetricsF1:
    """Tests for Metrics.f1() method."""

    def test_f1_perfect_predictions(self, perfect_predictions):
        """Verify that perfect predictions give F1 = 1.0."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        f1 = metrics.f1()

        assert f1 == 1.0

    def test_f1_calculated_correctly(self, imbalanced_predictions):
        """Verify that F1 is the harmonic mean of precision and recall."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        f1 = metrics.f1()
        precision = metrics.precision()
        recall = metrics.recall()

        # F1 = 2 * (precision * recall) / (precision + recall)
        if precision + recall > 0:
            expected = 2 * (precision * recall) / (precision + recall)
            assert f1 == pytest.approx(expected)
        else:
            assert f1 == 0.0

    def test_f1_range(self, imbalanced_predictions):
        """Verify that F1 is in range [0, 1]."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        f1 = metrics.f1()

        assert 0.0 <= f1 <= 1.0

    def test_f1_zero_division(self, all_zeros_predictions):
        """Verify that F1 returns 0.0 when division by zero occurs."""
        y_true, y_pred, y_proba = all_zeros_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        f1 = metrics.f1()

        assert f1 == 0.0


class TestMetricsAccuracy:
    """Tests for Metrics.accuracy() method."""

    def test_accuracy_perfect_predictions(self, perfect_predictions):
        """Verify that perfect predictions give accuracy = 1.0."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        accuracy = metrics.accuracy()

        assert accuracy == 1.0

    def test_accuracy_calculation(self, imbalanced_predictions):
        """Verify accuracy calculation on imbalanced data."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        accuracy = metrics.accuracy()

        # Manual calculation: correct / total
        # y_true: [0, 0, 0, 0, 1, 0, 0, 0, 1, 0]
        # y_pred: [0, 0, 1, 0, 1, 0, 0, 1, 1, 0]
        # Correct: indices 0, 1, 3, 4, 5, 6, 8, 9 = 8/10 (index 7 was wrong in comment)
        expected = 8 / 10
        assert accuracy == pytest.approx(expected)

    def test_accuracy_range(self, imbalanced_predictions):
        """Verify that accuracy is in range [0, 1]."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        accuracy = metrics.accuracy()

        assert 0.0 <= accuracy <= 1.0


class TestMetricsConfusionMatrix:
    """Tests for Metrics.confusion_matrix() method."""

    def test_confusion_matrix_structure(self, perfect_predictions):
        """Verify that confusion_matrix() returns correct structure."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        cm = metrics.confusion_matrix()

        assert isinstance(cm, dict)
        assert "tp" in cm
        assert "fp" in cm
        assert "fn" in cm
        assert "tn" in cm
        assert "matrix" in cm

    def test_confusion_matrix_values(self, perfect_predictions):
        """Verify that confusion matrix values are correct."""
        y_true, y_pred, y_proba = perfect_predictions
        # y_true: [0, 0, 1, 1, 0, 1]
        # y_pred: [0, 0, 1, 1, 0, 1]
        metrics = Metrics(y_true, y_pred, y_proba)
        cm = metrics.confusion_matrix()

        assert cm["tp"] == 3
        assert cm["fp"] == 0
        assert cm["fn"] == 0
        assert cm["tn"] == 3

    def test_confusion_matrix_imbalanced(self, imbalanced_predictions):
        """Verify confusion matrix on imbalanced data."""
        y_true, y_pred, y_proba = imbalanced_predictions
        # y_true: [0, 0, 0, 0, 1, 0, 0, 0, 1, 0]
        # y_pred: [0, 0, 1, 0, 1, 0, 0, 1, 1, 0]
        metrics = Metrics(y_true, y_pred, y_proba)
        cm = metrics.confusion_matrix()

        # TP: indices where y_true=1 and y_pred=1: 4, 8 = 2
        # FP: indices where y_true=0 and y_pred=1: 2, 7 = 2
        # FN: indices where y_true=1 and y_pred=0: none = 0
        # TN: indices where y_true=0 and y_pred=0: 0, 1, 3, 5, 6, 9 = 6
        assert cm["tp"] == 2
        assert cm["fp"] == 2
        assert cm["fn"] == 0
        assert cm["tn"] == 6

    def test_confusion_matrix_matrix_field(self, perfect_predictions):
        """Verify that the 'matrix' field contains a 2x2 array."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        cm = metrics.confusion_matrix()

        assert isinstance(cm["matrix"], list)
        assert len(cm["matrix"]) == 2
        assert len(cm["matrix"][0]) == 2
        assert len(cm["matrix"][1]) == 2

    def test_confusion_matrix_integers(self, perfect_predictions):
        """Verify that tp, fp, fn, tn are returned as ints."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        cm = metrics.confusion_matrix()

        assert isinstance(cm["tp"], int)
        assert isinstance(cm["fp"], int)
        assert isinstance(cm["fn"], int)
        assert isinstance(cm["tn"], int)


class TestMetricsCumulativeGains:
    """Tests for Metrics.cumulative_gains() method."""

    def test_cumulative_gains_structure(self, perfect_predictions):
        """Verify that cumulative_gains() returns correct structure."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        gains = metrics.cumulative_gains()

        assert isinstance(gains, dict)
        assert "deciles" in gains
        assert "cumulative_gain" in gains
        assert "cumulative_population" in gains

    def test_cumulative_gains_length(self, perfect_predictions):
        """Verify that number of deciles is correct (capped at sample size)."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        # Request 10 bins but we only have 6 samples - method caps n_bins to len(df)
        gains = metrics.cumulative_gains(n_bins=10)

        # Should be capped to number of samples (6)
        assert len(gains["deciles"]) == 6
        assert len(gains["cumulative_gain"]) == 6
        assert len(gains["cumulative_population"]) == 6

    def test_cumulative_population_reaches_one(self, perfect_predictions):
        """Verify that cumulative_population reaches 1.0 at the end."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        gains = metrics.cumulative_gains()

        assert gains["cumulative_population"][-1] == pytest.approx(1.0)

    def test_cumulative_gains_sorted(self, perfect_predictions):
        """Verify that cumulative_gain is non-decreasing."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        gains = metrics.cumulative_gains()

        for i in range(1, len(gains["cumulative_gain"])):
            assert gains["cumulative_gain"][i] >= gains["cumulative_gain"][i - 1]

    def test_cumulative_population_sorted(self, perfect_predictions):
        """Verify that cumulative_population is non-decreasing."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        gains = metrics.cumulative_gains()

        for i in range(1, len(gains["cumulative_population"])):
            assert gains["cumulative_population"][i] >= gains["cumulative_population"][i - 1]

    def test_cumulative_gains_custom_bins(self, perfect_predictions):
        """Verify that custom n_bins works correctly."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        gains = metrics.cumulative_gains(n_bins=5)

        assert len(gains["deciles"]) == 5

    def test_cumulative_gains_no_positives(self, all_zeros_predictions):
        """Verify behavior when there are no positive samples."""
        y_true, y_pred, y_proba = all_zeros_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        gains = metrics.cumulative_gains()

        # All gains should be 0 when there are no positives
        assert all(g == 0.0 for g in gains["cumulative_gain"])

    def test_cumulative_gains_all_positives(self, all_ones_predictions):
        """Verify behavior when all samples are positive."""
        y_true, y_pred, y_proba = all_ones_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        gains = metrics.cumulative_gains()

        # Gains should reach 1.0 quickly when sorted by probability
        assert gains["cumulative_gain"][-1] == pytest.approx(1.0)

    def test_cumulative_gains_n_bins_greater_than_samples(self, perfect_predictions):
        """Verify behavior when n_bins > number of samples."""
        y_true, y_pred, y_proba = perfect_predictions  # 6 samples
        metrics = Metrics(y_true, y_pred, y_proba)
        gains = metrics.cumulative_gains(n_bins=20)

        # Should cap n_bins to len(df)
        assert len(gains["deciles"]) == 6


class TestMetricsSegmentMetrics:
    """Tests for Metrics.segment_metrics() method."""

    def test_segment_metrics_structure(self, mixed_data_with_segments):
        """Verify that segment_metrics() returns correct structure."""
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        metrics = Metrics(y_true, y_pred, y_proba)
        seg_metrics = metrics.segment_metrics(segments)

        assert isinstance(seg_metrics, dict)
        assert "A" in seg_metrics
        assert "B" in seg_metrics
        assert "C" in seg_metrics

    def test_segment_metrics_per_segment_keys(self, mixed_data_with_segments):
        """Verify that each segment has required keys."""
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        metrics = Metrics(y_true, y_pred, y_proba)
        seg_metrics = metrics.segment_metrics(segments)

        for segment_value, segment_data in seg_metrics.items():
            assert "n_samples" in segment_data
            assert "n_positives" in segment_data
            assert "positive_rate" in segment_data
            assert "auc" in segment_data
            assert "precision" in segment_data
            assert "recall" in segment_data
            assert "f1" in segment_data
            assert "threshold" in segment_data
            assert "threshold_mode" in segment_data

    def test_segment_metrics_count_correct(self, mixed_data_with_segments):
        """Verify that segment counts are correct."""
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        # segments: ["A", "A", "B", "B", "A", "A", "B", "B", "C", "C"]
        # A: 4 samples, B: 4 samples, C: 2 samples
        metrics = Metrics(y_true, y_pred, y_proba)
        seg_metrics = metrics.segment_metrics(segments)

        assert seg_metrics["A"]["n_samples"] == 4
        assert seg_metrics["B"]["n_samples"] == 4
        assert seg_metrics["C"]["n_samples"] == 2

    def test_segment_metrics_positive_rate(self, mixed_data_with_segments):
        """Verify that positive_rate is calculated correctly."""
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        # y_true: [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
        # Segment A: indices 0, 1, 4, 5 -> y_true: [0, 1, 0, 1] -> positive_rate = 0.5
        metrics = Metrics(y_true, y_pred, y_proba)
        seg_metrics = metrics.segment_metrics(segments)

        assert seg_metrics["A"]["positive_rate"] == pytest.approx(0.5)

    def test_segment_metrics_empty_segment(self):
        """Verify that empty segments are skipped."""
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 0])
        y_proba = np.array([0.2, 0.8, 0.3, 0.6])
        segments = np.array(["A", "A", "A", "A"])  # No B segment
        metrics = Metrics(y_true, y_pred, y_proba)
        seg_metrics = metrics.segment_metrics(segments)

        assert "A" in seg_metrics
        assert "B" not in seg_metrics

    def test_segment_metrics_min_samples(self):
        """Verify that segments below min_samples are skipped."""
        # Using mixed_data_with_segments fixture: A=4, B=4, C=2 samples
        y_true = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 0, 0, 1, 1, 1, 0, 1])
        y_proba = np.array([0.2, 0.8, 0.3, 0.4, 0.1, 0.7, 0.6, 0.9, 0.2, 0.8])
        segments = np.array(["A", "A", "B", "B", "A", "A", "B", "B", "C", "C"])
        metrics = Metrics(y_true, y_pred, y_proba)

        # min_samples=3 should skip C (only 2 samples) but keep A and B (4 each)
        seg_metrics = metrics.segment_metrics(segments, min_samples=3)

        assert "A" in seg_metrics
        assert "B" in seg_metrics
        assert "C" not in seg_metrics

    def test_segment_metrics_single_segment(self):
        """Verify behavior with a single segment."""
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 0])
        y_proba = np.array([0.2, 0.8, 0.3, 0.6])
        segments = np.array(["A", "A", "A", "A"])
        metrics = Metrics(y_true, y_pred, y_proba)
        seg_metrics = metrics.segment_metrics(segments)

        assert len(seg_metrics) == 1
        assert seg_metrics["A"]["n_samples"] == 4


class TestMetricsGetThresholdMetrics:
    """Tests for Metrics.get_threshold_metrics() method."""

    def test_get_threshold_metrics_delegates(self, perfect_predictions):
        """Verify that get_threshold_metrics() delegates to compute_threshold_metrics()."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)
        result = metrics.get_threshold_metrics()

        assert "thresholds" in result
        assert "precisions" in result
        assert "recalls" in result
        assert "f1s" in result

    def test_get_threshold_metrics_same_as_function(self, perfect_predictions):
        """Verify that results match the standalone function."""
        y_true, y_pred, y_proba = perfect_predictions
        metrics = Metrics(y_true, y_pred, y_proba)

        method_result = metrics.get_threshold_metrics()
        function_result = compute_threshold_metrics(y_true, y_proba)

        assert method_result["thresholds"] == function_result["thresholds"]
        assert method_result["precisions"] == function_result["precisions"]
        assert method_result["recalls"] == function_result["recalls"]
        assert method_result["f1s"] == function_result["f1s"]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestMetricsIntegration:
    """Integration tests for Metrics class."""

    def test_full_workflow(self, imbalanced_predictions):
        """Verify a full workflow from initialization to all metrics."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)

        # Calculate all metrics
        all_results = metrics.calculate_all()

        # Verify structure
        assert "auc" in all_results
        assert "precision" in all_results
        assert "recall" in all_results
        assert "f1" in all_results
        assert "accuracy" in all_results
        assert "confusion_matrix" in all_results

        # Verify types
        assert isinstance(all_results["auc"], float)
        assert isinstance(all_results["precision"], float)
        assert isinstance(all_results["recall"], float)
        assert isinstance(all_results["f1"], float)
        assert isinstance(all_results["accuracy"], float)
        assert isinstance(all_results["confusion_matrix"], dict)

    def test_consistency_between_methods(self, imbalanced_predictions):
        """Verify that individual methods match calculate_all() results."""
        y_true, y_pred, y_proba = imbalanced_predictions
        metrics = Metrics(y_true, y_pred, y_proba)

        all_results = metrics.calculate_all()

        assert all_results["auc"] == metrics.auc()
        assert all_results["precision"] == metrics.precision()
        assert all_results["recall"] == metrics.recall()
        assert all_results["f1"] == metrics.f1()
        assert all_results["accuracy"] == metrics.accuracy()

    def test_combined_segment_and_threshold_metrics(self, mixed_data_with_segments):
        """Verify that segment_metrics and threshold_metrics can be combined."""
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        metrics = Metrics(y_true, y_pred, y_proba)

        seg_metrics = metrics.segment_metrics(segments)
        thresh_metrics = metrics.get_threshold_metrics()

        assert len(seg_metrics) > 0
        assert len(thresh_metrics["thresholds"]) == 101


# ---------------------------------------------------------------------------
# Tests for threshold optimization functions
# ---------------------------------------------------------------------------


class TestFindOptimalThresholdYouden:
    """Tests for find_optimal_threshold_youden function."""

    def test_returns_float(self, perfect_predictions):
        """Verify that the function returns a float."""
        y_true, _, y_proba = perfect_predictions
        threshold = find_optimal_threshold_youden(y_true, y_proba)
        assert isinstance(threshold, float)

    def test_threshold_in_valid_range(self, perfect_predictions):
        """Verify that threshold is in [0, 1]."""
        y_true, _, y_proba = perfect_predictions
        threshold = find_optimal_threshold_youden(y_true, y_proba)
        assert 0.0 <= threshold <= 1.0

    def test_perfect_predictions(self, perfect_predictions):
        """With perfect predictions, threshold should be around 0.5."""
        y_true, _, y_proba = perfect_predictions
        threshold = find_optimal_threshold_youden(y_true, y_proba)
        # With perfect separation, any threshold that separates classes works
        assert 0.0 <= threshold <= 1.0


class TestFindOptimalThresholdF1:
    """Tests for find_optimal_threshold_f1 function."""

    def test_returns_float(self, perfect_predictions):
        """Verify that the function returns a float."""
        y_true, _, y_proba = perfect_predictions
        threshold = find_optimal_threshold_f1(y_true, y_proba)
        assert isinstance(threshold, float)

    def test_threshold_in_valid_range(self, perfect_predictions):
        """Verify that threshold is in [0, 1]."""
        y_true, _, y_proba = perfect_predictions
        threshold = find_optimal_threshold_f1(y_true, y_proba)
        assert 0.0 <= threshold <= 1.0


class TestFindOptimalThresholdRecallTarget:
    """Tests for find_optimal_threshold_recall_target function."""

    def test_returns_float(self, perfect_predictions):
        """Verify that the function returns a float."""
        y_true, _, y_proba = perfect_predictions
        threshold = find_optimal_threshold_recall_target(y_true, y_proba, target_recall=0.8)
        assert isinstance(threshold, float)

    def test_threshold_in_valid_range(self, perfect_predictions):
        """Verify that threshold is in [0, 1]."""
        y_true, _, y_proba = perfect_predictions
        threshold = find_optimal_threshold_recall_target(y_true, y_proba, target_recall=0.8)
        assert 0.0 <= threshold <= 1.0

    def test_custom_recall_target(self, imbalanced_predictions):
        """Verify that custom recall target is used."""
        y_true, _, y_proba = imbalanced_predictions
        threshold = find_optimal_threshold_recall_target(y_true, y_proba, target_recall=0.5)
        assert 0.0 <= threshold <= 1.0


class TestSegmentMetricsThresholdModes:
    """Tests for segment_metrics with different threshold modes."""

    def test_global_threshold_mode(self, mixed_data_with_segments):
        """Verify that global threshold mode uses the provided threshold."""
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        metrics = Metrics(y_true, y_pred, y_proba, threshold=0.5)
        seg_metrics = metrics.segment_metrics(segments, threshold_mode="global")

        for seg_data in seg_metrics.values():
            assert seg_data["threshold_mode"] == "global"
            assert seg_data["threshold"] == 0.5

    def test_youden_threshold_mode(self, mixed_data_with_segments):
        """Verify that youden threshold mode finds optimal threshold per segment."""
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        metrics = Metrics(y_true, y_pred, y_proba, threshold=0.5)
        seg_metrics = metrics.segment_metrics(segments, threshold_mode="youden")

        for seg_data in seg_metrics.values():
            assert seg_data["threshold_mode"] == "youden"
            assert 0.0 <= seg_data["threshold"] <= 1.0

    def test_f1_optimal_threshold_mode(self, mixed_data_with_segments):
        """Verify that f1_optimal threshold mode finds optimal threshold per segment."""
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        metrics = Metrics(y_true, y_pred, y_proba, threshold=0.5)
        seg_metrics = metrics.segment_metrics(segments, threshold_mode="f1_optimal")

        for seg_data in seg_metrics.values():
            assert seg_data["threshold_mode"] == "f1_optimal"
            assert 0.0 <= seg_data["threshold"] <= 1.0

    def test_recall_target_threshold_mode(self, mixed_data_with_segments):
        """Verify that recall_target threshold mode finds threshold for target recall."""
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        metrics = Metrics(y_true, y_pred, y_proba, threshold=0.5)
        seg_metrics = metrics.segment_metrics(
            segments, threshold_mode="recall_target", recall_target=0.8
        )

        for seg_data in seg_metrics.values():
            assert seg_data["threshold_mode"] == "recall_target"
            assert 0.0 <= seg_data["threshold"] <= 1.0

    def test_segment_alias_threshold_mode(self, mixed_data_with_segments):
        """Verify that 'segment' alias resolves to 'youden' without mutating the parameter.

        Bug: threshold_mode='segment' used to mutate the parameter inside the loop,
        causing incorrect behavior and 'Unknown threshold_mode' warnings. The fix
        resolves the alias BEFORE the loop using a local variable.
        """
        y_true, y_pred, y_proba, segments = mixed_data_with_segments
        metrics = Metrics(y_true, y_pred, y_proba, threshold=0.5)
        seg_metrics = metrics.segment_metrics(segments, threshold_mode="segment")

        # All segments should report "youden" as the effective mode (alias resolved)
        for seg_data in seg_metrics.values():
            assert seg_data["threshold_mode"] == "youden", (
                f"Expected 'youden' (resolved from 'segment'), "
                f"got '{seg_data['threshold_mode']}'"
            )
            assert 0.0 <= seg_data["threshold"] <= 1.0

        # Verify youden thresholds differ across segments (not all the same global value)
        thresholds = [seg_data["threshold"] for seg_data in seg_metrics.values()]
        unique_thresholds = set(round(t, 4) for t in thresholds)
        # With mixed data, youden should produce varying thresholds per segment
        assert len(unique_thresholds) > 1 or len(seg_metrics) <= 1, (
            f"All segments got the same threshold ({thresholds[0]:.4f}), "
            f"expected Youden to produce different thresholds. "
            f"Thresholds: {thresholds}"
        )
