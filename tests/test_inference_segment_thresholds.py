"""Tests for segment threshold application in inference.

TDD for mejoras-3 change - Task T-F2b-1
"""

import json
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from energizados.core.builders.inference_builder import InferenceBuilder
from energizados.inference.default import apply_segment_thresholds


class TestApplySegmentThresholdsUtility:
    """Tests for the apply_segment_thresholds utility function in default.py."""

    def test_apply_segment_thresholds_basic_mapping(self):
        """Test basic threshold mapping per segment value."""
        # Arrange
        probas = np.array([0.2, 0.5, 0.8, 0.3, 0.6])
        segment_values = pd.Series(["Norte", "Sul", "Norte", "Este", "Sul"])
        thresholds_dict = {"Norte": 0.3, "Sul": 0.7}
        fallback_threshold = 0.5

        # Act
        predictions = apply_segment_thresholds(
            probas, segment_values, thresholds_dict, fallback_threshold
        )

        # Assert
        # Norte (0.2, 0.8) with threshold 0.3 -> [0, 1]
        # Sul (0.5, 0.6) with threshold 0.7 -> [0, 0]
        # Este (0.3) with fallback 0.5 -> [0]
        expected = np.array([0, 0, 1, 0, 0])
        np.testing.assert_array_equal(predictions, expected)

    def test_apply_segment_thresholds_all_known_segments(self):
        """Test when all segment values have defined thresholds."""
        probas = np.array([0.4, 0.6, 0.3])
        segment_values = pd.Series(["A", "B", "A"])
        thresholds_dict = {"A": 0.5, "B": 0.5}
        fallback_threshold = 0.5

        predictions = apply_segment_thresholds(
            probas, segment_values, thresholds_dict, fallback_threshold
        )

        # A: 0.4 < 0.5 -> 0, 0.3 < 0.5 -> 0
        # B: 0.6 >= 0.5 -> 1
        expected = np.array([0, 1, 0])
        np.testing.assert_array_equal(predictions, expected)

    def test_apply_segment_thresholds_all_unknown_use_fallback(self):
        """Test when all segment values are unknown - all use fallback."""
        probas = np.array([0.4, 0.6, 0.3])
        segment_values = pd.Series(["X", "Y", "Z"])
        thresholds_dict = {"A": 0.3, "B": 0.7}
        fallback_threshold = 0.5

        predictions = apply_segment_thresholds(
            probas, segment_values, thresholds_dict, fallback_threshold
        )

        # All use fallback 0.5: 0.4 < 0.5 -> 0, 0.6 >= 0.5 -> 1, 0.3 < 0.5 -> 0
        expected = np.array([0, 1, 0])
        np.testing.assert_array_equal(predictions, expected)

    def test_apply_segment_thresholds_empty_arrays(self):
        """Test with empty input arrays."""
        probas = np.array([])
        segment_values = pd.Series([], dtype=str)
        thresholds_dict = {"A": 0.5}
        fallback_threshold = 0.5

        predictions = apply_segment_thresholds(
            probas, segment_values, thresholds_dict, fallback_threshold
        )

        expected = np.array([])
        np.testing.assert_array_equal(predictions, expected)

    def test_apply_segment_thresholds_single_row(self):
        """Test with single row input."""
        probas = np.array([0.6])
        segment_values = pd.Series(["Norte"])
        thresholds_dict = {"Norte": 0.5}
        fallback_threshold = 0.5

        predictions = apply_segment_thresholds(
            probas, segment_values, thresholds_dict, fallback_threshold
        )

        expected = np.array([1])
        np.testing.assert_array_equal(predictions, expected)

    def test_apply_segment_thresholds_categorical_segment(self):
        """Categorical segment columns (common: geo_region, zona are dtype
        'category') must work. .map on a Categorical returns a Categorical of
        floats, which cannot be compared with >=. The utility must coerce to
        numeric before comparing. Regression test for inference on real data."""
        probas = np.array([0.4, 0.5, 0.25, 0.8])
        segment_values = pd.Series(pd.Categorical(["Norte", "Sul", "Norte", "Sul"]))
        thresholds_dict = {"Norte": 0.3, "Sul": 0.7}
        fallback_threshold = 0.5

        predictions = apply_segment_thresholds(
            probas, segment_values, thresholds_dict, fallback_threshold
        )

        # Norte: 0.4>=0.3->1, 0.25<0.3->0 ; Sul: 0.5<0.7->0, 0.8>=0.7->1
        expected = np.array([1, 0, 0, 1])
        np.testing.assert_array_equal(predictions, expected)


class TestInferenceBuilderSegmentThresholds:
    """Tests for segment threshold loading and application in InferenceBuilder."""

    def create_segment_thresholds_json(self, tmp_path, column, segments_data):
        """Helper to create a segment_thresholds JSON file."""
        json_data = {
            "segment_column": column,
            "threshold_mode": "youden",
            "default_threshold": 0.5,
            "segments": segments_data,
        }
        json_path = tmp_path / f"segment_thresholds_{column}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        return json_path

    def test_load_segment_thresholds_reads_json(self, tmp_path):
        """Test that _load_segment_thresholds reads and parses JSON correctly."""
        # Arrange
        json_path = self.create_segment_thresholds_json(
            tmp_path,
            "zona",
            {
                "Norte": {"threshold": 0.3, "auc": 0.82},
                "Sul": {"threshold": 0.7, "auc": 0.79},
            },
        )

        # Create a builder with minimal valid config and step
        builder = InferenceBuilder({"threshold": 0.5})
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Act
        result = step._load_segment_thresholds(str(json_path))

        # Assert
        assert result["segment_column"] == "zona"
        assert result["threshold_mode"] == "youden"
        assert result["default_threshold"] == 0.5
        assert "Norte" in result["segments"]
        assert result["segments"]["Norte"]["threshold"] == 0.3

    def test_load_segment_thresholds_validates_segment_column(self, tmp_path):
        """Test that _load_segment_thresholds raises error if segment_column missing."""
        # Arrange - JSON without segment_column
        json_path = tmp_path / "invalid.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"threshold_mode": "youden", "segments": {}}, f)

        builder = InferenceBuilder({"threshold": 0.5})
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Act & Assert
        with pytest.raises(ValueError, match="segment_column"):
            step._load_segment_thresholds(str(json_path))

    def test_apply_segment_thresholds_maps_correctly(self, tmp_path):
        """Test that _apply_segment_thresholds applies correct thresholds per row."""
        # Arrange
        json_path = self.create_segment_thresholds_json(
            tmp_path,
            "zona",
            {
                "Norte": {"threshold": 0.3, "auc": 0.82, "n_samples": 100},
                "Sul": {"threshold": 0.7, "auc": 0.79, "n_samples": 100},
            },
        )

        data = pd.DataFrame(
            {
                "zona": ["Norte", "Sul", "Norte", "Sul"],
                "feature": [1, 2, 3, 4],
            }
        )
        probas = np.array([0.4, 0.5, 0.25, 0.8])  # [>=0.3, <0.7, <0.3, >=0.7]

        config = {
            "enabled": True,
            "path": str(json_path),
        }

        builder = InferenceBuilder({"threshold": 0.5})
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Act
        predictions = step._apply_segment_thresholds(probas, data, config)

        # Assert: [1, 0, 0, 1]
        expected = np.array([1, 0, 0, 1])
        np.testing.assert_array_equal(predictions, expected)

    def test_apply_segment_thresholds_unknown_segments_use_fallback(self, tmp_path):
        """Test that unknown segment values use fallback_threshold."""
        # Arrange
        json_path = self.create_segment_thresholds_json(
            tmp_path,
            "zona",
            {
                "Norte": {"threshold": 0.3, "auc": 0.82},
            },
        )

        data = pd.DataFrame(
            {
                "zona": ["Norte", "Unknown", "Este"],  # Unknown and Este not in JSON
                "feature": [1, 2, 3],
            }
        )
        probas = np.array([0.4, 0.6, 0.4])  # [>=0.3, >=0.5, <0.5]

        config = {
            "enabled": True,
            "path": str(json_path),
        }

        builder = InferenceBuilder({"threshold": 0.5})
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Act
        predictions = step._apply_segment_thresholds(probas, data, config)

        # Assert: Norte(>=0.3)->1, Unknown(>=0.5)->1, Este(<0.5)->0
        expected = np.array([1, 1, 0])
        np.testing.assert_array_equal(predictions, expected)

    def test_apply_segment_thresholds_unknown_uses_global_threshold(self, tmp_path):
        """Test that unknown segment values use the global threshold."""
        # Arrange
        json_path = self.create_segment_thresholds_json(
            tmp_path,
            "zona",
            {
                "Norte": {"threshold": 0.3},
            },
        )

        data = pd.DataFrame(
            {
                "zona": ["Norte", "Unknown"],
                "feature": [1, 2],
            }
        )
        # Unknown (0.55) uses global threshold 0.6 -> 0.55 < 0.6 -> 0
        probas = np.array([0.4, 0.55])

        config = {
            "enabled": True,
            "path": str(json_path),
        }

        builder = InferenceBuilder({"threshold": 0.6})  # global threshold
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Act
        predictions = step._apply_segment_thresholds(probas, data, config)

        # Assert: Norte(0.4>=0.3)->1, Unknown(0.55<0.6)->0
        expected = np.array([1, 0])
        np.testing.assert_array_equal(predictions, expected)

    def test_apply_segment_thresholds_fallback_key_deprecated_warns_and_ignored(
        self, tmp_path, caplog
    ):
        """The legacy fallback_threshold key is ignored; the global threshold wins."""
        import logging

        json_path = self.create_segment_thresholds_json(
            tmp_path,
            "zona",
            {"Norte": {"threshold": 0.3}},
        )

        data = pd.DataFrame({"zona": ["Norte", "Unknown"], "feature": [1, 2]})
        # Unknown (0.55) must use the global threshold 0.6, NOT the ignored
        # legacy fallback_threshold 0.2 -> 0.55 >= 0.6 is False -> 0.
        probas = np.array([0.4, 0.55])

        config = {
            "enabled": True,
            "path": str(json_path),
            "fallback_threshold": 0.2,  # deprecated — must be ignored
        }

        builder = InferenceBuilder({"threshold": 0.6})
        step = builder.build()
        assert step is not None

        with caplog.at_level(logging.WARNING):
            predictions = step._apply_segment_thresholds(probas, data, config)

        # The global threshold (0.6) is used, not the legacy 0.2.
        expected = np.array([1, 0])
        np.testing.assert_array_equal(predictions, expected)
        assert any("fallback_threshold" in r.getMessage() for r in caplog.records)

    def test_apply_segment_thresholds_missing_column_raises(self, tmp_path):
        """Test that missing segment column in data raises ValueError."""
        # Arrange
        json_path = self.create_segment_thresholds_json(
            tmp_path,
            "zona",
            {"Norte": {"threshold": 0.3}},
        )

        data = pd.DataFrame(
            {
                "other_column": [1, 2],  # Missing 'zona' column
            }
        )
        probas = np.array([0.4, 0.6])

        config = {
            "enabled": True,
            "path": str(json_path),
        }

        builder = InferenceBuilder({"threshold": 0.5})
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Act & Assert
        with pytest.raises(ValueError, match="zona"):
            step._apply_segment_thresholds(probas, data, config)

    def test_apply_segment_thresholds_logs_summary(self, tmp_path, caplog):
        """Test that _apply_segment_thresholds logs row counts."""
        import logging

        # Arrange
        json_path = self.create_segment_thresholds_json(
            tmp_path,
            "zona",
            {
                "Norte": {"threshold": 0.3},
                "Sul": {"threshold": 0.7},
            },
        )

        data = pd.DataFrame(
            {
                "zona": ["Norte", "Sul", "Norte", "Unknown"],
            }
        )
        probas = np.array([0.4, 0.5, 0.25, 0.6])

        config = {
            "enabled": True,
            "path": str(json_path),
        }

        builder = InferenceBuilder({"threshold": 0.5})
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Act
        with caplog.at_level(logging.INFO):
            step._apply_segment_thresholds(probas, data, config)

        # Assert
        assert "total rows" in caplog.text.lower() or "4" in caplog.text


class TestInferenceStepExecuteWithSegmentThresholds:
    """Integration tests for segment thresholds in execute() method."""

    def create_segment_thresholds_json(self, tmp_path, column, segments_data):
        """Helper to create a segment_thresholds JSON file."""
        json_data = {
            "segment_column": column,
            "threshold_mode": "youden",
            "default_threshold": 0.5,
            "segments": segments_data,
        }
        json_path = tmp_path / f"segment_thresholds_{column}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        return json_path

    @pytest.fixture
    def mock_model(self):
        """Create a mock model that returns predictable probabilities."""
        model = MagicMock()
        model.predict.return_value = np.array([0, 0, 0, 0])  # Would use global threshold
        # [Norte=0.4, Sul=0.6, Norte=0.25, Sul=0.8]
        model.predict_proba.return_value = np.array([0.4, 0.6, 0.25, 0.8])
        return model

    def test_execute_uses_segment_thresholds_when_enabled(self, tmp_path, mock_model):
        """Test that execute() uses segment thresholds when enabled."""
        # Arrange
        json_path = self.create_segment_thresholds_json(
            tmp_path,
            "zona",
            {
                "Norte": {"threshold": 0.3},  # 0.4>=0.3->1, 0.25<0.3->0
                "Sul": {"threshold": 0.7},  # 0.6<0.7->0, 0.8>=0.7->1
            },
        )

        config = {
            "threshold": 0.5,  # Global threshold
            "segment_thresholds": {
                "enabled": True,
                "path": str(json_path),
                "fallback_threshold": 0.5,
            },
        }

        builder = InferenceBuilder(config)
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Create test data
        data = pd.DataFrame(
            {
                "zona": ["Norte", "Sul", "Norte", "Sul"],
            }
        )
        data_path = tmp_path / "test_data.parquet"
        data.to_parquet(data_path, index=False)

        # Update config with input path
        step.config["input_path"] = str(data_path)

        context = {"model": mock_model}

        # Act
        result_context = step.execute(context)

        # Assert - predictions should use per-segment thresholds, not global
        predictions = result_context["predictions"]
        # With segment thresholds: Norte(0.4>=0.3, 0.25<0.3)->[1,0], Sul(0.6<0.7, 0.8>=0.7)->[0,1]
        expected = np.array([1, 0, 0, 1])
        np.testing.assert_array_equal(predictions, expected)

    def test_execute_uses_global_threshold_when_disabled(self, tmp_path, mock_model):
        """Test that execute() uses global threshold when segment_thresholds disabled."""
        # Arrange
        config = {
            "threshold": 0.5,  # Global threshold
            "segment_thresholds": {
                "enabled": False,  # Disabled
                "path": None,
                "fallback_threshold": None,
            },
        }

        builder = InferenceBuilder(config)
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Create test data
        data = pd.DataFrame(
            {
                "zona": ["Norte", "Sul", "Norte", "Sul"],
            }
        )
        data_path = tmp_path / "test_data.parquet"
        data.to_parquet(data_path, index=False)

        step.config["input_path"] = str(data_path)

        context = {"model": mock_model}

        # Act
        result_context = step.execute(context)

        # Assert - should use global threshold (0.5)
        predictions = result_context["predictions"]
        # With global threshold 0.5: [0.4<0.5, 0.6>=0.5, 0.25<0.5, 0.8>=0.5] -> [0, 1, 0, 1]
        expected = np.array([0, 1, 0, 1])
        np.testing.assert_array_equal(predictions, expected)

    def test_execute_segment_thresholds_match_raw_values_when_fe_encodes_column(
        self, tmp_path, mock_model
    ):
        """FE may encode the segment column (e.g. ordinal/target encoding) before
        thresholds are applied. Segment thresholds must match on the RAW pre-FE
        values (strings), not the encoded floats — otherwise every row falls to
        the fallback threshold. Regression test for inference_builder bug."""
        # Arrange
        json_path = self.create_segment_thresholds_json(
            tmp_path,
            "zona",
            {
                "Norte": {"threshold": 0.3},  # 0.4>=0.3->1, 0.25<0.3->0
                "Sul": {"threshold": 0.7},  # 0.6<0.7->0, 0.8>=0.7->1
            },
        )

        config = {
            "threshold": 0.5,
            "segment_thresholds": {
                "enabled": True,
                "path": str(json_path),
                "fallback_threshold": 0.5,
            },
        }

        builder = InferenceBuilder(config)
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Raw data with string segment values
        data = pd.DataFrame({"zona": ["Norte", "Sul", "Norte", "Sul"]})
        data_path = tmp_path / "test_data.parquet"
        data.to_parquet(data_path, index=False)
        step.config["input_path"] = str(data_path)

        # Mock FE that ORDINAL-ENCODES zona (mimics real FE behavior).
        # This is the bug trigger: post-FE zona is float, not the string keys.
        fe = MagicMock()

        def _encode(df):
            out = df.copy()
            out["zona"] = out["zona"].map({"Norte": 0.0, "Sul": 1.0}).astype(float)
            return out

        fe.transform.side_effect = _encode

        context = {"model": mock_model, "feature_engineering": fe}

        # Act
        result_context = step.execute(context)

        # Assert — thresholds matched on RAW strings, not encoded floats.
        # Norte(0.4>=0.3, 0.25<0.3)->[1,0], Sul(0.6<0.7, 0.8>=0.7)->[0,1]
        # (If the bug is present, everything falls to fallback 0.5 -> [0,1,0,1])
        predictions = result_context["predictions"]
        expected = np.array([1, 0, 0, 1])
        np.testing.assert_array_equal(predictions, expected)

    def test_execute_uses_global_threshold_when_segment_config_missing(self, tmp_path, mock_model):
        """Test backward compatibility - no segment_thresholds key uses global."""
        # Arrange
        config = {
            "threshold": 0.5,  # Global threshold
            # No segment_thresholds key at all
        }

        builder = InferenceBuilder(config)
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"

        # Create test data
        data = pd.DataFrame(
            {
                "zona": ["Norte", "Sul", "Norte", "Sul"],
            }
        )
        data_path = tmp_path / "test_data.parquet"
        data.to_parquet(data_path, index=False)

        step.config["input_path"] = str(data_path)

        context = {"model": mock_model}

        # Act
        result_context = step.execute(context)

        # Assert - should use global threshold (0.5)
        predictions = result_context["predictions"]
        expected = np.array([0, 1, 0, 1])
        np.testing.assert_array_equal(predictions, expected)
