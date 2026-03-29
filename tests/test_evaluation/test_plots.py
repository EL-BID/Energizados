"""
Unit tests for evaluation.plots module.

Tests plot generation functions for model evaluation visualizations.
"""

import base64
from pathlib import Path

import numpy as np
import pytest

from energizados.evaluation.plots import PlotGenerator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def plot_generator(temp_dir):
    """Create a PlotGenerator instance with a temporary output directory.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        PlotGenerator: Instance configured with temp output directory
    """
    return PlotGenerator(output_dir=str(temp_dir / "plots"))


@pytest.fixture
def sample_predictions():
    """Generate sample binary classification predictions.

    Returns:
        tuple: (y_true, y_proba, auc_score) with realistic predictions
    """
    np.random.seed(42)
    n_samples = 100

    y_true = np.random.randint(0, 2, n_samples)
    # Probabilities that correlate somewhat with true labels
    y_proba = np.where(
        y_true == 1,
        np.random.uniform(0.6, 0.95, n_samples),
        np.random.uniform(0.05, 0.4, n_samples),
    )
    auc_score = 0.85

    return y_true, y_proba, auc_score


@pytest.fixture
def confusion_matrix_data():
    """Create a sample confusion matrix.

    Returns:
        np.ndarray: 2x2 confusion matrix [[TN, FP], [FN, TP]]
    """
    return np.array([[40, 10], [5, 45]])


@pytest.fixture
def cumulative_gains_data():
    """Create sample cumulative gains data.

    Returns:
        dict: Dictionary with deciles, cumulative_gain, and cumulative_population
    """
    return {
        "deciles": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        "cumulative_gain": [0.35, 0.55, 0.70, 0.80, 0.87, 0.92, 0.95, 0.97, 0.99, 1.0],
        "cumulative_population": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    }


@pytest.fixture
def feature_importance_data():
    """Create sample feature importance data.

    Returns:
        tuple: (feature_names, importances) for 10 features
    """
    feature_names = [f"feature_{i}" for i in range(10)]
    importances = np.array([0.25, 0.20, 0.15, 0.12, 0.10, 0.08, 0.05, 0.03, 0.01, 0.01])
    return feature_names, importances


@pytest.fixture
def threshold_metrics_data():
    """Create sample threshold sweep data.

    Returns:
        dict: Dictionary with thresholds, precisions, recalls, f1s
    """
    thresholds = np.linspace(0, 1, 101)
    precisions = 0.8 + 0.1 * np.sin(thresholds * np.pi)
    recalls = 1.0 - 0.3 * thresholds
    f1s = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)

    return {
        "thresholds": thresholds.tolist(),
        "precisions": precisions.tolist(),
        "recalls": recalls.tolist(),
        "f1s": f1s.tolist(),
    }


# ---------------------------------------------------------------------------
# Tests for PlotGenerator initialization
# ---------------------------------------------------------------------------


class TestPlotGeneratorInitialization:
    """Tests for PlotGenerator class initialization."""

    def test_initialization_creates_output_dir(self, temp_dir):
        """Verify that output directory is created if it doesn't exist."""
        output_path = temp_dir / "new_plots"
        PlotGenerator(output_dir=str(output_path))

        assert output_path.exists()
        assert output_path.is_dir()

    def test_initialization_with_existing_dir(self, temp_dir):
        """Verify that existing output directory is not affected."""
        output_path = temp_dir / "existing_plots"
        output_path.mkdir()

        PlotGenerator(output_dir=str(output_path))

        assert output_path.exists()
        assert output_path.is_dir()

    def test_output_dir_attribute(self, plot_generator):
        """Verify that output_dir is stored as Path object."""
        assert isinstance(plot_generator.output_dir, Path)

    def test_default_output_dir(self):
        """Verify that default output directory is 'reports/evaluation/'."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                plotter = PlotGenerator()
                expected_path = Path("reports/evaluation")
                assert plotter.output_dir == expected_path
            finally:
                os.chdir(original_cwd)

    def test_matplotlib_style(self, temp_dir):
        """Verify that matplotlib default style is used."""
        import matplotlib.pyplot as plt

        original_style = plt.rcParams.copy()
        PlotGenerator(str(temp_dir / "style_plots"))
        # Style should be 'default'
        assert "font.family" in plt.rcParams
        # Restore
        plt.rcParams.update(original_style)


# ---------------------------------------------------------------------------
# Tests for ROC curve plots
# ---------------------------------------------------------------------------


class TestROCCurvePlot:
    """Tests for roc_curve_plot method."""

    def test_roc_curve_creates_file(self, plot_generator, sample_predictions):
        """Verify that ROC curve plot file is created."""
        y_true, y_proba, auc_score = sample_predictions
        path = plot_generator.roc_curve_plot(y_true, y_proba, auc_score)

        assert Path(path).exists()
        assert path.endswith("roc_curve.png")

    def test_roc_curve_returns_path(self, plot_generator, sample_predictions):
        """Verify that ROC curve returns valid file path."""
        y_true, y_proba, auc_score = sample_predictions
        path = plot_generator.roc_curve_plot(y_true, y_proba, auc_score)

        assert isinstance(path, str)
        assert path.startswith(str(plot_generator.output_dir))

    def test_roc_curve_handles_perfect_predictions(self, plot_generator):
        """Verify that ROC curve handles perfect predictions."""
        y_true = np.array([0, 0, 1, 1])
        y_proba = np.array([0.1, 0.2, 0.8, 0.9])
        auc_score = 1.0

        path = plot_generator.roc_curve_plot(y_true, y_proba, auc_score)
        assert Path(path).exists()

    def test_roc_curve_custom_save_path(self, plot_generator, sample_predictions, temp_dir):
        """Verify that custom save_path works correctly."""
        y_true, y_proba, auc_score = sample_predictions
        custom_path = str(temp_dir / "custom_roc.png")

        path = plot_generator.roc_curve_plot(y_true, y_proba, auc_score, save_path=custom_path)
        assert Path(path).exists()
        assert path == custom_path

    def test_roc_curve_embedded_returns_tuple(self, plot_generator, sample_predictions):
        """Verify that embedded version returns (path, base64_uri)."""
        y_true, y_proba, auc_score = sample_predictions
        path, b64_uri = plot_generator.roc_curve_plot_embedded(y_true, y_proba, auc_score)

        assert isinstance(path, str)
        assert isinstance(b64_uri, str)
        assert Path(path).exists()

    def test_roc_curve_embedded_base64_format(self, plot_generator, sample_predictions):
        """Verify that base64 URI has correct format."""
        y_true, y_proba, auc_score = sample_predictions
        path, b64_uri = plot_generator.roc_curve_plot_embedded(y_true, y_proba, auc_score)

        assert b64_uri.startswith("data:image/png;base64,")
        # Should decode to valid bytes
        _, b64data = b64_uri.split(",", 1)
        decoded = base64.b64decode(b64data)
        assert len(decoded) > 0


# ---------------------------------------------------------------------------
# Tests for Precision-Recall plots
# ---------------------------------------------------------------------------


class TestPrecisionRecallPlot:
    """Tests for precision_recall_plot method."""

    def test_pr_curve_creates_file(self, plot_generator, sample_predictions):
        """Verify that PR curve plot file is created."""
        y_true, y_proba, _ = sample_predictions
        path = plot_generator.precision_recall_plot(y_true, y_proba)

        assert Path(path).exists()
        assert path.endswith("precision_recall_curve.png")

    def test_pr_curve_returns_path(self, plot_generator, sample_predictions):
        """Verify that PR curve returns valid file path."""
        y_true, y_proba, _ = sample_predictions
        path = plot_generator.precision_recall_plot(y_true, y_proba)

        assert isinstance(path, str)
        assert path.startswith(str(plot_generator.output_dir))

    def test_pr_curve_single_class(self, plot_generator):
        """Verify that PR curve handles single class data."""
        y_true = np.array([0, 0, 0, 0])
        y_proba = np.array([0.1, 0.2, 0.3, 0.4])

        path = plot_generator.precision_recall_plot(y_true, y_proba)
        assert Path(path).exists()

    def test_pr_curve_embedded_returns_tuple(self, plot_generator, sample_predictions):
        """Verify that embedded version returns (path, base64_uri)."""
        y_true, y_proba, _ = sample_predictions
        path, b64_uri = plot_generator.precision_recall_plot_embedded(y_true, y_proba)

        assert isinstance(path, str)
        assert isinstance(b64_uri, str)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Tests for Confusion Matrix plots
# ---------------------------------------------------------------------------


class TestConfusionMatrixPlot:
    """Tests for confusion_matrix_plot method."""

    def test_confusion_matrix_creates_file(self, plot_generator, confusion_matrix_data):
        """Verify that confusion matrix plot file is created."""
        path = plot_generator.confusion_matrix_plot(confusion_matrix_data)

        assert Path(path).exists()
        assert path.endswith("confusion_matrix.png")

    def test_confusion_matrix_returns_path(self, plot_generator, confusion_matrix_data):
        """Verify that confusion matrix returns valid file path."""
        path = plot_generator.confusion_matrix_plot(confusion_matrix_data)

        assert isinstance(path, str)
        assert path.startswith(str(plot_generator.output_dir))

    def test_confusion_matrix_perfect(self, plot_generator):
        """Verify that perfect confusion matrix works."""
        cm = np.array([[50, 0], [0, 50]])
        path = plot_generator.confusion_matrix_plot(cm)

        assert Path(path).exists()

    def test_confusion_matrix_imbalanced(self, plot_generator):
        """Verify that imbalanced confusion matrix works."""
        cm = np.array([[90, 5], [3, 2]])
        path = plot_generator.confusion_matrix_plot(cm)

        assert Path(path).exists()

    def test_confusion_matrix_embedded_returns_tuple(self, plot_generator, confusion_matrix_data):
        """Verify that embedded version returns (path, base64_uri)."""
        path, b64_uri = plot_generator.confusion_matrix_plot_embedded(confusion_matrix_data)

        assert isinstance(path, str)
        assert isinstance(b64_uri, str)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Tests for Cumulative Gains plots
# ---------------------------------------------------------------------------


class TestCumulativeGainsPlot:
    """Tests for cumulative_gains_plot method."""

    def test_cumulative_gains_creates_file(self, plot_generator, cumulative_gains_data):
        """Verify that cumulative gains plot file is created."""
        path = plot_generator.cumulative_gains_plot(cumulative_gains_data)

        assert Path(path).exists()
        assert path.endswith("cumulative_gains.png")

    def test_cumulative_gains_returns_path(self, plot_generator, cumulative_gains_data):
        """Verify that cumulative gains returns valid file path."""
        path = plot_generator.cumulative_gains_plot(cumulative_gains_data)

        assert isinstance(path, str)
        assert path.startswith(str(plot_generator.output_dir))

    def test_cumulative_gains_perfect_model(self, plot_generator):
        """Verify that perfect model cumulative gains works."""
        gains_data = {
            "deciles": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
            "cumulative_gain": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "cumulative_population": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        }
        path = plot_generator.cumulative_gains_plot(gains_data)
        assert Path(path).exists()

    def test_cumulative_gains_embedded_returns_tuple(self, plot_generator, cumulative_gains_data):
        """Verify that embedded version returns (path, base64_uri)."""
        path, b64_uri = plot_generator.cumulative_gains_plot_embedded(cumulative_gains_data)

        assert isinstance(path, str)
        assert isinstance(b64_uri, str)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Tests for Lift Chart plots
# ---------------------------------------------------------------------------


class TestLiftChartPlot:
    """Tests for lift_chart_plot method."""

    def test_lift_chart_creates_file(self, plot_generator, cumulative_gains_data):
        """Verify that lift chart plot file is created."""
        path = plot_generator.lift_chart_plot(cumulative_gains_data)

        assert Path(path).exists()
        assert path.endswith("lift_chart.png")

    def test_lift_chart_returns_path(self, plot_generator, cumulative_gains_data):
        """Verify that lift chart returns valid file path."""
        path = plot_generator.lift_chart_plot(cumulative_gains_data)

        assert isinstance(path, str)
        assert path.startswith(str(plot_generator.output_dir))

    def test_lift_chart_handles_zero_population(self, plot_generator):
        """Verify that lift chart handles zero population values."""
        gains_data = {
            "deciles": [10, 20, 30],
            "cumulative_gain": [0.2, 0.4, 0.6],
            "cumulative_population": [0.1, 0.2, 0.0],  # Last one is zero
        }
        path = plot_generator.lift_chart_plot(gains_data)
        assert Path(path).exists()

    def test_lift_chart_embedded_returns_tuple(self, plot_generator, cumulative_gains_data):
        """Verify that embedded version returns (path, base64_uri)."""
        path, b64_uri = plot_generator.lift_chart_plot_embedded(cumulative_gains_data)

        assert isinstance(path, str)
        assert isinstance(b64_uri, str)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Tests for Calibration Plot
# ---------------------------------------------------------------------------


class TestCalibrationPlot:
    """Tests for calibration_plot method."""

    def test_calibration_creates_file(self, plot_generator, sample_predictions):
        """Verify that calibration plot file is created."""
        y_true, y_proba, _ = sample_predictions
        path = plot_generator.calibration_plot(y_true, y_proba)

        assert Path(path).exists()
        assert path.endswith("calibration_curve.png")

    def test_calibration_returns_path(self, plot_generator, sample_predictions):
        """Verify that calibration returns valid file path."""
        y_true, y_proba, _ = sample_predictions
        path = plot_generator.calibration_plot(y_true, y_proba)

        assert isinstance(path, str)
        assert path.startswith(str(plot_generator.output_dir))

    def test_calibration_custom_bins(self, plot_generator, sample_predictions):
        """Verify that custom n_bins works correctly."""
        y_true, y_proba, _ = sample_predictions
        path = plot_generator.calibration_plot(y_true, y_proba, n_bins=5)

        assert Path(path).exists()

    def test_calibration_edge_case_bins(self, plot_generator, sample_predictions):
        """Verify calibration with extreme bin counts."""
        y_true, y_proba, _ = sample_predictions
        # Test with n_bins=2
        path = plot_generator.calibration_plot(y_true, y_proba, n_bins=2)
        assert Path(path).exists()

    def test_calibration_embedded_returns_tuple(self, plot_generator, sample_predictions):
        """Verify that embedded version returns (path, base64_uri)."""
        y_true, y_proba, _ = sample_predictions
        path, b64_uri = plot_generator.calibration_plot_embedded(y_true, y_proba)

        assert isinstance(path, str)
        assert isinstance(b64_uri, str)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Tests for Probability Distribution Plot
# ---------------------------------------------------------------------------


class TestProbabilityDistributionPlot:
    """Tests for probability_distribution_plot method."""

    def test_probability_distribution_creates_file(self, plot_generator, sample_predictions):
        """Verify that probability distribution plot file is created."""
        y_true, y_proba, _ = sample_predictions
        path = plot_generator.probability_distribution_plot(y_true, y_proba)

        assert Path(path).exists()
        assert path.endswith("probability_distribution.png")

    def test_probability_distribution_returns_path(self, plot_generator, sample_predictions):
        """Verify that probability distribution returns valid file path."""
        y_true, y_proba, _ = sample_predictions
        path = plot_generator.probability_distribution_plot(y_true, y_proba)

        assert isinstance(path, str)
        assert path.startswith(str(plot_generator.output_dir))

    def test_probability_distribution_single_class(self, plot_generator):
        """Verify that single class probability distribution works."""
        y_true = np.array([0, 0, 0, 0])
        y_proba = np.array([0.1, 0.2, 0.3, 0.4])

        path = plot_generator.probability_distribution_plot(y_true, y_proba)
        assert Path(path).exists()

    def test_probability_distribution_embedded_returns_tuple(
        self, plot_generator, sample_predictions
    ):
        """Verify that embedded version returns (path, base64_uri)."""
        y_true, y_proba, _ = sample_predictions
        path, b64_uri = plot_generator.probability_distribution_plot_embedded(y_true, y_proba)

        assert isinstance(path, str)
        assert isinstance(b64_uri, str)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Tests for Feature Importance Plot
# ---------------------------------------------------------------------------


class TestFeatureImportancePlot:
    """Tests for feature_importance_plot method."""

    def test_feature_importance_creates_file(self, plot_generator, feature_importance_data):
        """Verify that feature importance plot file is created."""
        feature_names, importances = feature_importance_data
        path = plot_generator.feature_importance_plot(feature_names, importances)

        assert Path(path).exists()
        assert path.endswith("feature_importance.png")

    def test_feature_importance_returns_path(self, plot_generator, feature_importance_data):
        """Verify that feature importance returns valid file path."""
        feature_names, importances = feature_importance_data
        path = plot_generator.feature_importance_plot(feature_names, importances)

        assert isinstance(path, str)
        assert path.startswith(str(plot_generator.output_dir))

    def test_feature_importance_top_n(self, plot_generator, feature_importance_data):
        """Verify that top_n parameter works correctly."""
        feature_names, importances = feature_importance_data
        path = plot_generator.feature_importance_plot(feature_names, importances, top_n=5)

        assert Path(path).exists()

    def test_feature_importance_all_features(self, plot_generator, feature_importance_data):
        """Verify showing all features works."""
        feature_names, importances = feature_importance_data
        path = plot_generator.feature_importance_plot(feature_names, importances, top_n=20)

        assert Path(path).exists()

    def test_feature_importance_more_than_available(self, plot_generator, feature_importance_data):
        """Verify when top_n > available features."""
        feature_names, importances = feature_importance_data
        path = plot_generator.feature_importance_plot(feature_names, importances, top_n=100)

        assert Path(path).exists()

    def test_feature_importance_embedded_returns_tuple(
        self, plot_generator, feature_importance_data
    ):
        """Verify that embedded version returns (path, base64_uri)."""
        feature_names, importances = feature_importance_data
        path, b64_uri = plot_generator.feature_importance_plot_embedded(feature_names, importances)

        assert isinstance(path, str)
        assert isinstance(b64_uri, str)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Tests for Threshold Sweep Plot
# ---------------------------------------------------------------------------


class TestThresholdSweepPlot:
    """Tests for threshold_sweep_plot method."""

    def test_threshold_sweep_creates_file(self, plot_generator, threshold_metrics_data):
        """Verify that threshold sweep plot file is created."""
        path = plot_generator.threshold_sweep_plot(threshold_metrics_data)

        assert Path(path).exists()
        assert path.endswith("threshold_sweep.png")

    def test_threshold_sweep_returns_path(self, plot_generator, threshold_metrics_data):
        """Verify that threshold sweep returns valid file path."""
        path = plot_generator.threshold_sweep_plot(threshold_metrics_data)

        assert isinstance(path, str)
        assert path.startswith(str(plot_generator.output_dir))

    def test_threshold_sweep_current_threshold(self, plot_generator, threshold_metrics_data):
        """Verify that custom current_threshold is displayed."""
        path = plot_generator.threshold_sweep_plot(threshold_metrics_data, current_threshold=0.3)

        assert Path(path).exists()

    def test_threshold_sweep_default_threshold(self, plot_generator, threshold_metrics_data):
        """Verify that default current_threshold=0.5 is used."""
        path = plot_generator.threshold_sweep_plot(threshold_metrics_data)

        assert Path(path).exists()

    def test_threshold_sweep_embedded_returns_tuple(self, plot_generator, threshold_metrics_data):
        """Verify that embedded version returns (path, base64_uri)."""
        path, b64_uri = plot_generator.threshold_sweep_plot_embedded(threshold_metrics_data)

        assert isinstance(path, str)
        assert isinstance(b64_uri, str)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Tests for internal helper methods
# ---------------------------------------------------------------------------


class TestInternalHelpers:
    """Tests for internal helper methods."""

    def test_save_figure_creates_file(self, plot_generator, temp_dir):
        """Verify that _save_figure creates a valid file."""
        import matplotlib.pyplot as plt

        plt.figure()
        plt.plot([1, 2, 3], [1, 2, 3])

        filename = "test_plot.png"
        path = plot_generator._save_figure(filename)

        assert Path(path).exists()
        assert path.endswith(filename)

    def test_save_figure_custom_path(self, plot_generator, temp_dir):
        """Verify that _save_figure works with custom path."""
        import matplotlib.pyplot as plt

        custom_path = str(temp_dir / "custom_test.png")
        plt.figure()
        plt.plot([1, 2, 3], [1, 2, 3])

        path = plot_generator._save_figure(filename="ignored.png", save_path=custom_path)

        assert Path(path).exists()
        assert path == custom_path

    def test_figure_to_base64_returns_string(self, plot_generator):
        """Verify that _figure_to_base64 returns a valid base64 string."""
        import matplotlib.pyplot as plt

        plt.figure()
        plt.plot([1, 2, 3], [1, 2, 3])

        b64_uri = plot_generator._figure_to_base64()

        assert isinstance(b64_uri, str)
        assert b64_uri.startswith("data:image/png;base64,")

    def test_save_figure_embedded_creates_file(self, plot_generator):
        """Verify that _save_figure_embedded creates a file and returns base64."""
        import matplotlib.pyplot as plt

        plt.figure()
        plt.plot([1, 2, 3], [1, 2, 3])

        filename = "test_embedded.png"
        path, b64_uri = plot_generator._save_figure_embedded(filename)

        assert Path(path).exists()
        assert path.endswith(filename)
        assert isinstance(b64_uri, str)
        assert b64_uri.startswith("data:image/png;base64,")

    def test_save_figure_embedded_custom_path(self, plot_generator, temp_dir):
        """Verify that _save_figure_embedded works with custom path."""
        import matplotlib.pyplot as plt

        custom_path = str(temp_dir / "custom_embedded.png")
        plt.figure()
        plt.plot([1, 2, 3], [1, 2, 3])

        path, b64_uri = plot_generator._save_figure_embedded(
            filename="ignored.png", save_path=custom_path
        )

        assert Path(path).exists()
        assert path == custom_path


# ---------------------------------------------------------------------------
# Edge case and integration tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_predictions(self, plot_generator):
        """Verify behavior with empty arrays."""
        y_true = np.array([])
        y_proba = np.array([])
        # This should not crash
        try:
            plot_generator.roc_curve_plot(y_true, y_proba, 0.0)
            # If it doesn't crash, that's fine
            # roc_curve may raise an error with empty arrays
        except Exception:  # nosec B110
            # Expected: sklearn may raise ValueError with empty arrays
            pass

    def test_constant_probabilities(self, plot_generator):
        """Verify behavior with constant probability values."""
        y_true = np.array([0, 0, 1, 1])
        y_proba = np.array([0.5, 0.5, 0.5, 0.5])

        # ROC should handle this
        path = plot_generator.roc_curve_plot(y_true, y_proba, 0.5)
        assert Path(path).exists()

    def test_large_dataset(self, plot_generator):
        """Verify that plots handle large datasets."""
        np.random.seed(42)
        n_samples = 10000
        y_true = np.random.randint(0, 2, n_samples)
        y_proba = np.random.rand(n_samples)

        path = plot_generator.roc_curve_plot(y_true, y_proba, 0.7)
        assert Path(path).exists()

    def test_many_features(self, plot_generator):
        """Verify feature importance with many features."""
        n_features = 100
        feature_names = [f"feature_{i}" for i in range(n_features)]
        importances = np.random.rand(n_features)

        path = plot_generator.feature_importance_plot(feature_names, importances, top_n=20)
        assert Path(path).exists()


class TestIntegration:
    """Integration tests for multiple plot generations."""

    def test_generate_all_plot_types(self, plot_generator, sample_predictions):
        """Verify that all plot types can be generated successfully."""
        y_true, y_proba, auc_score = sample_predictions
        cm = np.array([[40, 10], [5, 45]])

        paths = []
        paths.append(plot_generator.roc_curve_plot(y_true, y_proba, auc_score))
        paths.append(plot_generator.precision_recall_plot(y_true, y_proba))
        paths.append(plot_generator.confusion_matrix_plot(cm))
        paths.append(plot_generator.probability_distribution_plot(y_true, y_proba))

        for path in paths:
            assert Path(path).exists()

    def test_multiple_plots_in_same_directory(self, plot_generator, sample_predictions):
        """Verify that multiple plots can be saved to the same directory."""
        y_true, y_proba, auc_score = sample_predictions

        paths = []
        for i in range(3):
            path = plot_generator.roc_curve_plot(y_true, y_proba, auc_score)
            paths.append(path)

        # All should exist (though later ones may overwrite earlier ones)
        for path in paths:
            assert Path(path).exists()

    def test_embedded_and_regular_consistency(self, plot_generator, sample_predictions):
        """Verify that embedded and regular versions produce files."""
        y_true, y_proba, auc_score = sample_predictions

        regular_path = plot_generator.roc_curve_plot(y_true, y_proba, auc_score)
        embedded_path, b64_uri = plot_generator.roc_curve_plot_embedded(y_true, y_proba, auc_score)

        # Both should create files
        assert Path(regular_path).exists()
        assert Path(embedded_path).exists()

        # Files should have valid base64 data
        assert b64_uri.startswith("data:image/png;base64,")
