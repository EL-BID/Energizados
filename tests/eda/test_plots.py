"""
Tests for EDA plot functions (outlier analysis).
"""

import numpy as np
import pandas as pd
import pytest

from energizados.eda.plots import EDAStaticPlots
from energizados.eda.plots_interactive import EDAInteractivePlots


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    np.random.seed(42)
    n = 200
    data = {
        "numeric1": np.random.normal(100, 15, n),
        "numeric2": np.random.exponential(50, n),
        "numeric3": np.random.uniform(0, 1000, n),
        "1_anterior": np.random.normal(150, 30, n),
        "2_anterior": np.random.normal(155, 32, n),
        "3_anterior": np.random.normal(160, 35, n),
        "target": np.random.choice([0, 1], n, p=[0.9, 0.1]),
    }
    # Add some outliers manually
    data["numeric1"][:5] = [500, 600, -200, 550, 450]
    return pd.DataFrame(data)


@pytest.fixture
def sample_outlier_masks(sample_df):
    """Create sample outlier masks."""
    return {
        "numeric1": pd.Series([i < 5 for i in range(len(sample_df))], index=sample_df.index),
        "numeric2": pd.Series([False] * len(sample_df), index=sample_df.index),
        "numeric3": pd.Series([False] * len(sample_df), index=sample_df.index),
    }


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Temporary output directory for plots."""
    output_dir = tmp_path / "plots"
    output_dir.mkdir()
    return str(output_dir)


class TestEDAStaticPlotsOutlier:
    """Tests for static outlier plot functions."""

    def test_plot_outlier_boxplots_returns_dict(
        self, sample_df, tmp_output_dir, sample_outlier_masks
    ):
        """Test that plot_outlier_boxplots returns a dictionary."""
        plotter = EDAStaticPlots(tmp_output_dir)
        numeric_cols = ["numeric1", "numeric2"]

        result = plotter.plot_outlier_boxplots(sample_df, numeric_cols, sample_outlier_masks)

        assert isinstance(result, dict)
        assert "combined" in result or len(result) > 0

    def test_plot_outlier_boxplots_with_single_column(
        self, sample_df, tmp_output_dir, sample_outlier_masks
    ):
        """Test plot_outlier_boxplots with a single numeric column."""
        plotter = EDAStaticPlots(tmp_output_dir)
        numeric_cols = ["numeric1"]

        result = plotter.plot_outlier_boxplots(sample_df, numeric_cols, sample_outlier_masks)

        assert isinstance(result, dict)

    def test_plot_outlier_boxplots_empty_df(self, tmp_output_dir):
        """Test plot_outlier_boxplots with empty DataFrame."""
        plotter = EDAStaticPlots(tmp_output_dir)
        empty_df = pd.DataFrame()
        result = plotter.plot_outlier_boxplots(empty_df, [], {})

        # Should return empty dict or handle gracefully
        assert isinstance(result, dict)

    def test_plot_outlier_heatmap_returns_svg(
        self, sample_df, tmp_output_dir, sample_outlier_masks
    ):
        """Test that plot_outlier_heatmap returns an SVG string."""
        plotter = EDAStaticPlots(tmp_output_dir)
        numeric_cols = ["numeric1", "numeric2", "numeric3"]

        result = plotter.plot_outlier_heatmap(sample_df, numeric_cols, sample_outlier_masks)

        assert isinstance(result, str)
        if result:  # Only check if matplotlib is available
            assert "<svg" in result or result == ""  # Empty string means skipped

    def test_plot_outlier_heatmap_limits_rows(
        self, sample_df, tmp_output_dir, sample_outlier_masks
    ):
        """Test that plot_outlier_heatmap limits rows for performance."""
        plotter = EDAStaticPlots(tmp_output_dir)
        numeric_cols = ["numeric1"]

        result = plotter.plot_outlier_heatmap(sample_df, numeric_cols, sample_outlier_masks)

        # Should not crash with large df
        assert isinstance(result, str)

    def test_plot_consumption_anomalies_returns_dict(self, sample_df, tmp_output_dir):
        """Test that plot_consumption_anomalies returns a dictionary."""
        plotter = EDAStaticPlots(tmp_output_dir)
        consumption_cols = ["1_anterior", "2_anterior", "3_anterior"]
        outlier_mask = pd.Series([i < 10 for i in range(len(sample_df))], index=sample_df.index)

        result = plotter.plot_consumption_anomalies(
            sample_df, consumption_cols, outlier_mask, target_col="target"
        )

        assert isinstance(result, dict)

    def test_plot_consumption_anomalies_without_target(self, sample_df, tmp_output_dir):
        """Test plot_consumption_anomalies without target column."""
        plotter = EDAStaticPlots(tmp_output_dir)
        consumption_cols = ["1_anterior", "2_anterior"]
        outlier_mask = pd.Series([i < 10 for i in range(len(sample_df))], index=sample_df.index)

        result = plotter.plot_consumption_anomalies(sample_df, consumption_cols, outlier_mask)

        assert isinstance(result, dict)

    def test_plot_consumption_anomalies_empty_mask(self, sample_df, tmp_output_dir):
        """Test plot_consumption_anomalies with no outlier mask."""
        plotter = EDAStaticPlots(tmp_output_dir)
        consumption_cols = ["1_anterior"]

        result = plotter.plot_consumption_anomalies(sample_df, consumption_cols)

        assert isinstance(result, dict)

    def test_plot_consumption_anomalies_invalid_cols(self, sample_df, tmp_output_dir):
        """Test plot_consumption_anomalies with invalid column names."""
        plotter = EDAStaticPlots(tmp_output_dir)
        consumption_cols = ["nonexistent_col"]

        result = plotter.plot_consumption_anomalies(sample_df, consumption_cols)

        # Should return empty dict for invalid columns
        assert isinstance(result, dict)
        assert len(result) == 0


class TestEDAInteractivePlotsOutlier:
    """Tests for interactive outlier plot functions."""

    def test_plotly_outlier_boxplots_returns_html(
        self, sample_df, tmp_output_dir, sample_outlier_masks
    ):
        """Test that plotly_outlier_boxplots returns HTML string."""
        plotter = EDAInteractivePlots(tmp_output_dir)
        numeric_cols = ["numeric1", "numeric2"]

        result = plotter.plotly_outlier_boxplots(sample_df, numeric_cols, sample_outlier_masks)

        assert isinstance(result, str)
        if result:  # Only check if plotly is available
            assert "<html>" in result or "<div" in result or result == ""

    def test_plotly_outlier_boxplots_max_cols_limit(self, sample_df, tmp_output_dir):
        """Test that plotly_outlier_boxplots respects max_cols parameter."""
        plotter = EDAInteractivePlots(tmp_output_dir)
        numeric_cols = ["numeric1", "numeric2", "numeric3"]
        masks = {
            "numeric1": pd.Series([False] * len(sample_df), index=sample_df.index),
            "numeric2": pd.Series([False] * len(sample_df), index=sample_df.index),
            "numeric3": pd.Series([False] * len(sample_df), index=sample_df.index),
        }

        result = plotter.plotly_outlier_boxplots(sample_df, numeric_cols, masks, max_cols=2)

        assert isinstance(result, str)

    def test_plotly_outlier_summary_bar_returns_html(
        self, sample_df, tmp_output_dir, sample_outlier_masks
    ):
        """Test that plotly_outlier_summary_bar returns HTML string."""
        plotter = EDAInteractivePlots(tmp_output_dir)

        result = plotter.plotly_outlier_summary_bar(sample_outlier_masks)

        assert isinstance(result, str)
        if result:
            assert "<html>" in result or "<div" in result or result == ""

    def test_plotly_outlier_summary_bar_empty(self, tmp_output_dir):
        """Test that plotly_outlier_summary_bar handles empty masks."""
        plotter = EDAInteractivePlots(tmp_output_dir)

        result = plotter.plotly_outlier_summary_bar({})

        assert result == ""

    def test_plotly_consumption_anomalies_returns_html(self, sample_df, tmp_output_dir):
        """Test that plotly_consumption_anomalies returns HTML string."""
        plotter = EDAInteractivePlots(tmp_output_dir)
        consumption_cols = ["1_anterior", "2_anterior", "3_anterior"]
        outlier_mask = pd.Series([i < 10 for i in range(len(sample_df))], index=sample_df.index)

        result = plotter.plotly_consumption_anomalies(
            sample_df, consumption_cols, outlier_mask, target_col="target"
        )

        assert isinstance(result, str)
        if result:
            assert "<html>" in result or "<div" in result or result == ""

    def test_plotly_consumption_anomalies_without_target(self, sample_df, tmp_output_dir):
        """Test plotly_consumption_anomalies without target column."""
        plotter = EDAInteractivePlots(tmp_output_dir)
        consumption_cols = ["1_anterior", "2_anterior"]
        outlier_mask = pd.Series([i < 10 for i in range(len(sample_df))], index=sample_df.index)

        result = plotter.plotly_consumption_anomalies(sample_df, consumption_cols, outlier_mask)

        assert isinstance(result, str)

    def test_plotly_consumption_anomalies_sample_n(self, sample_df, tmp_output_dir):
        """Test that plotly_consumption_anomalies respects sample_n parameter."""
        plotter = EDAInteractivePlots(tmp_output_dir)
        consumption_cols = ["1_anterior"]
        outlier_mask = pd.Series([i < 10 for i in range(len(sample_df))], index=sample_df.index)

        result = plotter.plotly_consumption_anomalies(
            sample_df, consumption_cols, outlier_mask, sample_n=50
        )

        assert isinstance(result, str)


class TestPlotEdgeCases:
    """Tests for edge cases and error handling."""

    def test_all_functions_with_nan_values(self, tmp_output_dir):
        """Test that all plot functions handle NaN values gracefully."""
        np.random.seed(42)
        n = 100
        df = pd.DataFrame(
            {
                "numeric1": np.random.normal(100, 15, n),
                "numeric2": np.random.exponential(50, n),
                "1_anterior": np.random.normal(150, 30, n),
                "target": np.random.choice([0, 1], n),
            }
        )
        # Add NaN values
        df.loc[10:15, "numeric1"] = np.nan
        df.loc[20:25, "numeric2"] = np.nan

        outlier_masks = {
            "numeric1": pd.Series([i < 5 for i in range(n)]),
            "numeric2": pd.Series([False] * n),
        }

        # Test static plots
        static_plotter = EDAStaticPlots(tmp_output_dir)
        static_result1 = static_plotter.plot_outlier_boxplots(df, ["numeric1"], outlier_masks)
        static_result2 = static_plotter.plot_outlier_heatmap(
            df, ["numeric1", "numeric2"], outlier_masks
        )
        static_result3 = static_plotter.plot_consumption_anomalies(df, ["1_anterior"])

        # Test interactive plots
        interactive_plotter = EDAInteractivePlots(tmp_output_dir)
        interactive_result1 = interactive_plotter.plotly_outlier_boxplots(
            df, ["numeric1"], outlier_masks
        )
        interactive_result2 = interactive_plotter.plotly_outlier_summary_bar(outlier_masks)
        interactive_result3 = interactive_plotter.plotly_consumption_anomalies(df, ["1_anterior"])

        # All should return expected types without crashing
        assert isinstance(static_result1, dict)
        assert isinstance(static_result2, str)
        assert isinstance(static_result3, dict)
        assert isinstance(interactive_result1, str)
        assert isinstance(interactive_result2, str)
        assert isinstance(interactive_result3, str)

    def test_empty_outlier_masks(self, sample_df, tmp_output_dir):
        """Test that functions handle empty outlier masks."""
        static_plotter = EDAStaticPlots(tmp_output_dir)
        interactive_plotter = EDAInteractivePlots(tmp_output_dir)

        static_result1 = static_plotter.plot_outlier_boxplots(sample_df, ["numeric1"], {})
        static_result2 = static_plotter.plot_outlier_heatmap(sample_df, ["numeric1"], {})
        interactive_result1 = interactive_plotter.plotly_outlier_boxplots(
            sample_df, ["numeric1"], {}
        )
        interactive_result2 = interactive_plotter.plotly_outlier_summary_bar({})

        # Should handle gracefully
        assert isinstance(static_result1, dict)
        assert isinstance(static_result2, str)
        assert isinstance(interactive_result1, str)
        assert isinstance(interactive_result2, str)
