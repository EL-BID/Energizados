"""Tests for DefaultEvaluator._export_segment_thresholds method.

TDD for mejoras-3 change - Task T-F2a-1
"""

import json
from unittest.mock import patch

from energizados.evaluation.evaluator import DefaultEvaluator


class TestExportSegmentThresholds:
    """Tests for the _export_segment_thresholds method."""

    def test_export_segment_thresholds_writes_json_file(self, tmp_path):
        """Test that JSON file is written to output_dir with correct name."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "Norte": {
                "threshold": 0.37,
                "threshold_mode": "youden",
                "auc": 0.82,
                "n_samples": 1500,
            }
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        result = evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="youden",
        )

        # Assert
        expected_file = output_dir / "segment_thresholds_Norte.json"
        assert expected_file.exists(), f"Expected file {expected_file} not found"
        assert len(result) == 1
        assert result[0] == expected_file

    def test_export_segment_thresholds_json_structure(self, tmp_path):
        """Test JSON structure matches expected schema."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "Sul": {
                "threshold": 0.63,
                "threshold_mode": "youden",
                "auc": 0.79,
                "n_samples": 1200,
            }
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.45,
            threshold_mode="youden",
        )

        # Assert
        json_file = output_dir / "segment_thresholds_Sul.json"
        with open(json_file) as f:
            data = json.load(f)

        # Verify schema
        assert "segment_column" in data
        assert "threshold_mode" in data
        assert "default_threshold" in data
        assert "segments" in data

        assert data["segment_column"] == "Sul"
        assert data["threshold_mode"] == "youden"
        assert data["default_threshold"] == 0.45
        assert isinstance(data["segments"], dict)

    def test_export_segment_thresholds_multiple_columns(self, tmp_path):
        """Test that multiple segment columns produce multiple JSON files."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "Norte": {
                "threshold": 0.37,
                "threshold_mode": "youden",
                "auc": 0.82,
                "n_samples": 1500,
            },
            "Sul": {
                "threshold": 0.63,
                "threshold_mode": "youden",
                "auc": 0.79,
                "n_samples": 1200,
            },
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        result = evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="youden",
        )

        # Assert
        assert len(result) == 2
        assert (output_dir / "segment_thresholds_Norte.json").exists()
        assert (output_dir / "segment_thresholds_Sul.json").exists()

    def test_export_segment_thresholds_segment_values_in_segments(self, tmp_path):
        """Test that segment values are correctly nested in segments dict."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "zona": {
                "norte": {
                    "threshold": 0.37,
                    "threshold_mode": "youden",
                    "auc": 0.82,
                    "n_samples": 1500,
                },
                "sul": {
                    "threshold": 0.63,
                    "threshold_mode": "youden",
                    "auc": 0.79,
                    "n_samples": 1200,
                },
            }
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="youden",
        )

        # Assert
        json_file = output_dir / "segment_thresholds_zona.json"
        with open(json_file) as f:
            data = json.load(f)

        assert "segments" in data
        assert "norte" in data["segments"]
        assert "sul" in data["segments"]

        norte_data = data["segments"]["norte"]
        assert norte_data["threshold"] == 0.37
        assert norte_data["threshold_mode"] == "youden"
        assert norte_data["auc"] == 0.82
        assert norte_data["n_samples"] == 1500

    def test_export_segment_thresholds_json_indent(self, tmp_path):
        """Test that JSON is written with indent=2 for human readability."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "test_col": {
                "threshold": 0.5,
                "threshold_mode": "global",
                "auc": 0.8,
                "n_samples": 100,
            }
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="global",
        )

        # Assert
        json_file = output_dir / "segment_thresholds_test_col.json"
        content = json_file.read_text()

        # Check for indentation by looking for newlines and spaces
        assert "\n" in content, "JSON should be indented (contain newlines)"
        assert "  " in content, "JSON should be indented (contain spaces)"

    def test_export_segment_thresholds_empty_metrics(self, tmp_path):
        """Test that empty segmented_metrics produces no files."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {}
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        result = evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="global",
        )

        # Assert
        assert result == []
        assert len(list(output_dir.glob("*.json"))) == 0


class TestExportSegmentThresholdsIntegration:
    """Integration tests for _export_segment_thresholds within execute()."""

    def test_execute_calls_export_when_segmented_enabled(self, tmp_path):
        """Test that _export_segment_thresholds is called when segmented_evaluation is enabled."""
        # Arrange - Create a real parquet file with enough data for segments
        import pandas as pd
        import numpy as np

        output_dir = tmp_path / "eval_output"
        output_dir.mkdir()

        # Create enough samples per segment (min_samples default is 30)
        np.random.seed(42)
        n_samples = 100
        test_data = pd.DataFrame({
            "target": np.random.randint(0, 2, n_samples),
            "feature1": np.random.random(n_samples),
            "zona": ["Norte"] * 50 + ["Sul"] * 50,
        })
        test_path = tmp_path / "test.parquet"
        test_data.to_parquet(test_path)

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            segmented_evaluation={
                "enabled": True,
                "by": ["zona"],
                "threshold_mode": "youden",
                "min_samples": 10,  # Lower threshold for test
            },
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        # Create a simple mock model with enough predictions
        class SimpleMockModel:
            def predict_proba(self, X):
                return np.random.random(len(X))

        # Patch the _load_model method
        with patch.object(evaluator, "_load_model", return_value=SimpleMockModel()):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                # Act
                context = {}
                _ = evaluator.execute(context)

        # Assert - Check that segment threshold files were created
        assert (output_dir / "segment_thresholds_zona.json").exists(), (
            "Segment threshold JSON file should be created"
        )

        # Verify the JSON content
        with open(output_dir / "segment_thresholds_zona.json") as f:
            data = json.load(f)
        assert "segment_column" in data
        assert data["segment_column"] == "zona"
        assert "segments" in data
        assert "Norte" in data["segments"] or "Sul" in data["segments"]

    def test_execute_no_export_when_segmented_disabled(self, tmp_path):
        """Test that no export happens when segmented_evaluation is disabled."""
        # Arrange - Create a real parquet file with minimal data
        import pandas as pd
        import numpy as np

        output_dir = tmp_path / "eval_output"
        output_dir.mkdir()

        test_data = pd.DataFrame({
            "target": [0, 1, 0, 1, 0, 1],
            "feature1": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            "zona": ["Norte", "Sul", "Norte", "Sul", "Norte", "Sul"],
        })
        test_path = tmp_path / "test.parquet"
        test_data.to_parquet(test_path)

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            segmented_evaluation={"enabled": False},
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        # Create a simple mock model
        class SimpleMockModel:
            def predict_proba(self, X):
                return np.array([0.3, 0.7, 0.4, 0.6, 0.5, 0.8])

        # Patch the _load_model method
        with patch.object(evaluator, "_load_model", return_value=SimpleMockModel()):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                # Act
                context = {}
                evaluator.execute(context)

        # Assert - Check that no segment threshold files were created
        json_files = list(output_dir.glob("segment_thresholds_*.json"))
        assert len(json_files) == 0, (
            "No segment threshold JSON files should be created when disabled"
        )
