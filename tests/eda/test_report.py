"""
Tests for EDA Report Generator - Outlier Analysis Section.

Tests for the outlier analysis section rendering and JSON artifact saving.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from energizados.eda.report import EDAReportGenerator


class TestRenderOutlierSection:
    """Tests for render_outlier_section() method."""

    def test_render_outlier_section_with_empty_results(self):
        """Test render_outlier_section() with empty outlier results."""
        generator = EDAReportGenerator("output/eda/")
        columns = {}

        html = generator.render_outlier_section(columns, {})

        # When columns is empty, render_outlier_section returns empty string
        # The section is only rendered when outlier data exists
        assert html == ""

    def test_render_outlier_section_with_numeric_outliers(self):
        """Test render_outlier_section() with numeric column outliers."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [
                {
                    "col": "consumption_1",
                    "outlier_count": 50,
                    "outlier_pct": 5.0,
                    "outlier_methods": {
                        "iqr": {"outlier_count": 50, "outlier_pct": 5.0, "has_alert": False},
                        "zscore": {"outlier_count": 30, "outlier_pct": 3.0, "has_alert": False},
                    },
                }
            ],
            "consumption_outliers": {},
        }

        html = generator.render_outlier_section(columns, {})

        assert "Outlier Analysis (Phase 2.5)" in html
        assert "consumption_1" in html
        assert "5.00%" in html
        assert "3.00%" in html
        assert "<th>Column</th>" in html
        assert "<th>Method</th>" in html

    def test_render_outlier_section_with_high_outlier_alerts(self):
        """Test render_outlier_section() with high outlier percentage alerts."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [
                {
                    "col": "high_outlier_col",
                    "outlier_count": 150,
                    "outlier_pct": 15.0,
                    "outlier_methods": {
                        "iqr": {"outlier_count": 150, "outlier_pct": 15.0, "has_alert": True}
                    },
                }
            ],
            "consumption_outliers": {},
        }

        html = generator.render_outlier_section(columns, {})

        assert "high_outlier_col" in html
        assert "15.00%" in html
        assert "badge-WARNING" in html

    def test_render_outlier_section_with_consumption_outliers(self):
        """Test render_outlier_section() with consumption outlier patterns."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [],
            "consumption_outliers": {
                "pct_zero_variance": 2.5,
                "pct_range_outliers": 5.0,
                "mean_zscore_outlier_pct": 3.0,
            },
        }

        html = generator.render_outlier_section(columns, {})

        assert "Consumption Outlier Patterns" in html
        assert "2.50%" in html
        assert "5.00%" in html
        assert "3.00%" in html
        assert "Zero Variance Rows" in html
        assert "Extreme Range Outliers" in html
        assert "Global Mean Outliers" in html

    def test_render_outlier_section_with_consumption_high_values(self):
        """Test render_outlier_section() shows high consumption outlier percentages."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [],
            "consumption_outliers": {
                "pct_zero_variance": 15.0,
                "pct_range_outliers": 12.0,
                "mean_zscore_outlier_pct": 8.0,
            },
        }

        html = generator.render_outlier_section(columns, {})

        assert "Consumption Outlier Patterns" in html
        assert "15.00%" in html
        assert "12.00%" in html
        assert "8.00%" in html

    def test_render_outlier_section_with_legacy_iqr_method(self):
        """Test render_outlier_section() with legacy IQR method (no outlier_methods)."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [
                {
                    "col": "legacy_col",
                    "outlier_count": 80,
                    "outlier_pct": 8.0,
                }
            ],
            "consumption_outliers": {},
        }

        html = generator.render_outlier_section(columns, {})

        assert "legacy_col" in html
        assert "8.00%" in html
        assert "IQR (legacy)" in html

    def test_render_outlier_section_method_breakdown(self):
        """Test that method breakdown statistics are calculated correctly."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [
                {
                    "col": "col1",
                    "outlier_methods": {
                        "iqr": {"outlier_count": 50, "outlier_pct": 5.0, "has_alert": False},
                        "zscore": {"outlier_count": 30, "outlier_pct": 3.0, "has_alert": False},
                    },
                },
                {
                    "col": "col2",
                    "outlier_methods": {
                        "iqr": {"outlier_count": 40, "outlier_pct": 4.0, "has_alert": False},
                    },
                },
            ],
            "consumption_outliers": {},
        }

        html = generator.render_outlier_section(columns, {})

        assert "Outlier Detection Method Summary" in html
        assert "IQR" in html
        assert "ZSCORE" in html
        assert "2" in html  # 2 columns with IQR outliers


class TestSaveOutlierResultsJson:
    """Tests for _save_outlier_results_json() method."""

    def test_save_outlier_results_json_structure(self):
        """Test that JSON artifact has correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = EDAReportGenerator(tmpdir)
            results = {
                "global_stats": {"shape": [1000, 10], "memory_mb": 5.5},
                "columns": {},
                "charts": {},
            }
            columns = {
                "numeric": [
                    {
                        "col": "test_col",
                        "outlier_methods": {
                            "iqr": {"outlier_count": 50, "outlier_pct": 5.0, "has_alert": False}
                        },
                    }
                ],
                "consumption_outliers": {"pct_zero_variance": 2.5},
            }

            json_path = generator._save_outlier_results_json(results, columns)

            assert Path(json_path).exists()
            with open(json_path, "r") as f:
                data = json.load(f)

            assert "timestamp" in data
            assert "dataset_info" in data
            assert "numeric_outliers" in data
            assert "consumption_outliers" in data
            assert data["dataset_info"]["shape"] == [1000, 10]
            assert len(data["numeric_outliers"]) == 1
            assert data["numeric_outliers"][0]["column"] == "test_col"
            assert data["consumption_outliers"]["pct_zero_variance"] == 2.5

    def test_save_outlier_results_json_with_multiple_methods(self):
        """Test JSON artifact with multiple outlier detection methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = EDAReportGenerator(tmpdir)
            results = {
                "global_stats": {"shape": [1000, 10]},
                "columns": {},
                "charts": {},
            }
            columns = {
                "numeric": [
                    {
                        "col": "multi_col",
                        "outlier_methods": {
                            "iqr": {"outlier_count": 50, "outlier_pct": 5.0, "has_alert": False},
                            "zscore": {"outlier_count": 30, "outlier_pct": 3.0, "has_alert": False},
                            "modified_zscore": {
                                "outlier_count": 20,
                                "outlier_pct": 2.0,
                                "has_alert": False,
                            },
                        },
                    }
                ],
                "consumption_outliers": {},
            }

            json_path = generator._save_outlier_results_json(results, columns)

            with open(json_path, "r") as f:
                data = json.load(f)

            assert len(data["numeric_outliers"]) == 3
            methods = [item["method"] for item in data["numeric_outliers"]]
            assert "iqr" in methods
            assert "zscore" in methods
            assert "modified_zscore" in methods

    def test_save_outlier_results_json_with_alerts(self):
        """Test JSON artifact includes alert information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = EDAReportGenerator(tmpdir)
            results = {
                "global_stats": {"shape": [1000, 10]},
                "columns": {},
                "charts": {},
            }
            columns = {
                "numeric": [
                    {
                        "col": "alert_col",
                        "outlier_methods": {
                            "iqr": {"outlier_count": 150, "outlier_pct": 15.0, "has_alert": True}
                        },
                    }
                ],
                "consumption_outliers": {},
            }

            json_path = generator._save_outlier_results_json(results, columns)

            with open(json_path, "r") as f:
                data = json.load(f)

            assert data["numeric_outliers"][0]["has_alert"] is True

    def test_save_outlier_results_json_with_legacy_method(self):
        """Test JSON artifact with legacy IQR method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = EDAReportGenerator(tmpdir)
            results = {
                "global_stats": {"shape": [1000, 10]},
                "columns": {},
                "charts": {},
            }
            columns = {
                "numeric": [
                    {
                        "col": "legacy_col",
                        "outlier_count": 80,
                        "outlier_pct": 8.0,
                    }
                ],
                "consumption_outliers": {},
            }

            json_path = generator._save_outlier_results_json(results, columns)

            with open(json_path, "r") as f:
                data = json.load(f)

            assert len(data["numeric_outliers"]) == 1
            assert data["numeric_outliers"][0]["column"] == "legacy_col"
            assert data["numeric_outliers"][0]["method"] == "IQR (legacy)"
            assert data["numeric_outliers"][0]["outlier_pct"] == 8.0

    def test_save_outlier_results_json_filename(self):
        """Test that JSON file is saved with correct filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = EDAReportGenerator(tmpdir)
            results = {
                "global_stats": {"shape": [1000, 10]},
                "columns": {},
                "charts": {},
            }
            columns = {
                "numeric": [
                    {
                        "col": "test",
                        "outlier_methods": {
                            "iqr": {"outlier_count": 10, "outlier_pct": 1.0, "has_alert": False}
                        },
                    }
                ],
                "consumption_outliers": {},
            }

            json_path = generator._save_outlier_results_json(results, columns)

            assert json_path.endswith("outlier_analysis.json")
            assert Path(json_path).parent == Path(tmpdir)


class TestHasOutlierData:
    """Tests for _has_outlier_data() method."""

    def test_has_outlier_data_with_empty_columns(self):
        """Test _has_outlier_data() returns False for empty columns."""
        generator = EDAReportGenerator("output/eda/")

        assert generator._has_outlier_data({}) is False

    def test_has_outlier_data_with_multi_method_outliers(self):
        """Test _has_outlier_data() returns True for multi-method outliers."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [
                {
                    "col": "test",
                    "outlier_methods": {
                        "iqr": {"outlier_count": 10, "outlier_pct": 1.0, "has_alert": False}
                    },
                }
            ],
            "consumption_outliers": {},
        }

        assert generator._has_outlier_data(columns) is True

    def test_has_outlier_data_with_legacy_outliers(self):
        """Test _has_outlier_data() returns True for legacy IQR outliers."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [
                {
                    "col": "test",
                    "outlier_count": 10,
                    "outlier_pct": 1.0,
                }
            ],
            "consumption_outliers": {},
        }

        assert generator._has_outlier_data(columns) is True

    def test_has_outlier_data_with_consumption_outliers(self):
        """Test _has_outlier_data() returns True for consumption outliers."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [],
            "consumption_outliers": {"pct_zero_variance": 2.5},
        }

        assert generator._has_outlier_data(columns) is True

    def test_has_outlier_data_no_outliers(self):
        """Test _has_outlier_data() returns False when no outliers exist."""
        generator = EDAReportGenerator("output/eda/")
        columns = {
            "numeric": [
                {
                    "col": "test",
                    "outlier_count": 0,
                    "outlier_pct": 0.0,
                }
            ],
            "consumption_outliers": {},
        }

        assert generator._has_outlier_data(columns) is False


class TestGenerateReportIntegration:
    """Integration tests for generate() method with outlier data."""

    def test_generate_report_without_outlier_data(self):
        """Test that generate() works without outlier data (no JSON saved)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = EDAReportGenerator(tmpdir)
            results = {
                "global_stats": {"shape": [100, 5]},
                "loading": {},
                "columns": {},
                "target": {},
                "importance": {},
                "geo": {},
                "segmentation": {},
                "related_columns": {},
                "col_types": {},
                "charts": {},
            }
            alerts = []

            report_path = generator.generate(results, alerts)

            assert Path(report_path).exists()
            # Check that outlier_analysis.json was NOT created
            assert not Path(tmpdir, "outlier_analysis.json").exists()

    @patch("energizados.eda.report.logger")
    def test_generate_report_with_outlier_data(self, mock_logger):
        """Test that generate() saves JSON when outlier data exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = EDAReportGenerator(tmpdir)
            results = {
                "global_stats": {"shape": [100, 5]},
                "loading": {},
                "columns": {
                    "numeric": [
                        {
                            "col": "test",
                            "outlier_methods": {
                                "iqr": {
                                    "outlier_count": 10,
                                    "outlier_pct": 10.0,
                                    "has_alert": False,
                                }
                            },
                        }
                    ],
                    "consumption_outliers": {},
                },
                "target": {},
                "importance": {},
                "geo": {},
                "segmentation": {},
                "related_columns": {},
                "col_types": {},
                "charts": {},
            }
            alerts = []

            report_path = generator.generate(results, alerts)

            assert Path(report_path).exists()
            # Check that outlier_analysis.json WAS created
            assert Path(tmpdir, "outlier_analysis.json").exists()
            # Verify HTML report includes outlier section
            with open(report_path, "r") as f:
                html = f.read()
            assert "Outlier Analysis (Phase 2.5)" in html
            assert "Phase 2.5: Outlier Analysis" in html

    @patch("energizados.eda.report.logger")
    def test_generate_report_sidebar_includes_outliers(self, mock_logger):
        """Test that sidebar includes outlier link when outlier data exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = EDAReportGenerator(tmpdir)
            results = {
                "global_stats": {"shape": [100, 5]},
                "loading": {},
                "columns": {
                    "numeric": [
                        {
                            "col": "test",
                            "outlier_methods": {
                                "iqr": {
                                    "outlier_count": 10,
                                    "outlier_pct": 10.0,
                                    "has_alert": False,
                                }
                            },
                        }
                    ],
                    "consumption_outliers": {},
                },
                "target": {},
                "importance": {},
                "geo": {},
                "segmentation": {},
                "related_columns": {},
                "col_types": {},
                "charts": {},
            }
            alerts = []

            report_path = generator.generate(results, alerts)

            with open(report_path, "r") as f:
                html = f.read()
            assert 'href="#outliers"' in html
            assert "Phase 2.5: Outlier Analysis" in html
