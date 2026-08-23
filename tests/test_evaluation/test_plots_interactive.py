"""
Tests for EvalInteractivePlots self_contained mode.

Verifies that interactive evaluation charts can be generated without any
network reference to the Plotly.js CDN (offline / air-gapped reports).
"""

from energizados.evaluation.plots_interactive import EvalInteractivePlots


def _roc(plotter):
    return plotter.roc_curve([0.0, 0.2, 1.0], [0.0, 0.8, 1.0], 0.91)


def _pr(plotter):
    return plotter.precision_recall_curve([1.0, 0.8, 0.4], [0.1, 0.5, 0.9], 0.87)


class TestSelfContainedPlots:
    """Test suite for self_contained interactive evaluation plots."""

    def test_default_self_contained_is_false(self, tmp_path):
        """Constructor must default to self_contained=False (backwards compatible)."""
        plotter = EvalInteractivePlots(str(tmp_path))
        assert plotter.self_contained is False

    def test_default_chart_references_cdn(self, tmp_path):
        """Default charts keep the Plotly.js CDN reference (byte-identical behavior)."""
        plotter = EvalInteractivePlots(str(tmp_path))
        html = _roc(plotter)
        assert html
        assert 'src="https://cdn.plot.ly/plotly' in html

    def test_self_contained_first_chart_inlines_plotly(self, tmp_path):
        """First chart in self_contained mode inlines the full Plotly.js bundle."""
        plotter = EvalInteractivePlots(str(tmp_path), self_contained=True)
        html = _roc(plotter)
        assert html
        # Inline bundle marker emitted by plotly when the library is embedded
        assert "window.PlotlyConfig" in html
        assert 'src="https://cdn.plot.ly/plotly' not in html
        assert len(html) > 1_000_000  # full plotly.js bundle is ~4.8 MB

    def test_self_contained_single_inline_inclusion(self, tmp_path):
        """Only the first chart inlines Plotly.js; subsequent charts skip the bundle."""
        plotter = EvalInteractivePlots(str(tmp_path), self_contained=True)
        first = _roc(plotter)
        second = _pr(plotter)

        assert first
        assert second
        # First chart carries the bundle exactly once
        assert first.count("PlotlyConfig") == 1
        # Second chart still renders but does not embed the bundle again
        assert "PlotlyConfig" not in second
        assert "Plotly.newPlot" in second
        assert 'src="https://cdn.plot.ly/plotly' not in second

    def test_self_contained_reset_per_instance(self, tmp_path):
        """A new plotter instance inlines the bundle again (one per document)."""
        first_plotter = EvalInteractivePlots(str(tmp_path), self_contained=True)
        second_plotter = EvalInteractivePlots(str(tmp_path), self_contained=True)

        assert "PlotlyConfig" in _roc(first_plotter)
        assert "PlotlyConfig" in _roc(second_plotter)
