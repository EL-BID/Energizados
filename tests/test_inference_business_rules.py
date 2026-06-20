"""Tests for business rules application in inference.

TDD for v4 — business_rules mechanism (Phase 0 framework prerequisite).
Tests cover the ``apply_business_rules`` utility function and the
``InferenceBuilder`` integration (``_apply_business_rules`` + ``execute()``).
"""

import json
import logging
from typing import Any, Dict
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from energizados.core.builders.inference_builder import InferenceBuilder
from energizados.inference.default import apply_business_rules

# =============================================================================
# Utility function tests (apply_business_rules in default.py)
# =============================================================================


class TestApplyBusinessRulesUtility:
    """Unit tests for the apply_business_rules utility function."""

    def _make_raw_data(self, n=4):
        """Create raw data with consumption columns and geo_region."""
        return pd.DataFrame(
            {
                "3_anterior": [0.0, 100.0, 0.0, 50.0],
                "2_anterior": [0.0, 80.0, 0.0, 40.0],
                "1_anterior": [0.0, 60.0, 0.0, 10.0],
                "12_anterior": [10.0, 90.0, 0.0, 50.0],
                "11_anterior": [10.0, 85.0, 0.0, 50.0],
                "10_anterior": [10.0, 88.0, 0.0, 50.0],
                "9_anterior": [10.0, 82.0, 0.0, 50.0],
                "8_anterior": [10.0, 80.0, 0.0, 50.0],
                "7_anterior": [10.0, 78.0, 0.0, 50.0],
                "6_anterior": [10.0, 75.0, 0.0, 50.0],
                "5_anterior": [10.0, 72.0, 0.0, 50.0],
                "4_anterior": [10.0, 70.0, 0.0, 50.0],
                "geo_region": ["VIDEIRA", "BLUMENAU", "JOACABA", "BLUMENAU"],
            }
        )

    def test_score_boost_increments_probability(self):
        """score_boost adds value to probability (clipped to [0,1])."""
        probas = np.array([0.2, 0.5, 0.3, 0.8])
        raw_data = self._make_raw_data()
        rules_config = {
            "apply_to": {"regions": ["VIDEIRA", "JOACABA"]},
            "rules": [
                {
                    "name": "consumo_cero_3m",
                    "condition": "(`3_anterior` == 0) & (`2_anterior` == 0) & (`1_anterior` == 0)",
                    "action": "score_boost",
                    "value": 0.3,
                }
            ],
            "output": {"add_rule_columns": True},
        }

        modified_probas, rules_df, probas_modified = apply_business_rules(
            probas, raw_data, rules_config
        )

        # Row 0 (VIDEIRA, all zeros): 0.2 + 0.3 = 0.5
        # Row 2 (JOACABA, all zeros): 0.3 + 0.3 = 0.6
        # Rows 1, 3 (BLUMENAU, not in apply_to): unchanged
        assert probas_modified is True
        np.testing.assert_array_almost_equal(modified_probas, np.array([0.5, 0.5, 0.6, 0.8]))
        # Rules df columns
        assert "rule_consumo_cero_3m" in rules_df.columns
        assert "rule_consumo_cero_3m_value" in rules_df.columns
        # Rows 0 and 2 triggered (VIDEIRA and JOACABA, both with zeros)
        np.testing.assert_array_equal(
            rules_df["rule_consumo_cero_3m"].values,
            np.array([True, False, True, False]),
        )

    def test_override_sets_probability_to_one(self):
        """override sets probability to 1.0 for triggered rows."""
        probas = np.array([0.2, 0.5, 0.3, 0.8])
        raw_data = self._make_raw_data()
        rules_config = {
            "apply_to": {"regions": ["VIDEIRA", "JOACABA"]},
            "rules": [
                {
                    "name": "consumo_cero_3m",
                    "condition": "(`3_anterior` == 0) & (`2_anterior` == 0) & (`1_anterior` == 0)",
                    "action": "override",
                    "value": 1.0,
                }
            ],
            "output": {"add_rule_columns": True},
        }

        modified_probas, rules_df, probas_modified = apply_business_rules(
            probas, raw_data, rules_config
        )

        # Rows 0, 2 (triggered): 1.0
        # Rows 1, 3 (not triggered / not eligible): unchanged
        assert probas_modified is True
        np.testing.assert_array_almost_equal(modified_probas, np.array([1.0, 0.5, 1.0, 0.8]))

    def test_flag_does_not_modify_probability(self):
        """flag action records the trigger but does NOT modify probas."""
        probas = np.array([0.2, 0.5, 0.3, 0.8])
        raw_data = self._make_raw_data()
        rules_config = {
            "apply_to": {"regions": ["VIDEIRA", "JOACABA"]},
            "rules": [
                {
                    "name": "consumo_cero_3m",
                    "condition": "(`3_anterior` == 0) & (`2_anterior` == 0) & (`1_anterior` == 0)",
                    "action": "flag",
                }
            ],
            "output": {"add_rule_columns": True},
        }

        modified_probas, rules_df, probas_modified = apply_business_rules(
            probas, raw_data, rules_config
        )

        # probas unchanged
        assert probas_modified is False
        np.testing.assert_array_almost_equal(modified_probas, np.array([0.2, 0.5, 0.3, 0.8]))
        # But rule columns still recorded
        np.testing.assert_array_equal(
            rules_df["rule_consumo_cero_3m"].values,
            np.array([True, False, True, False]),
        )

    def test_apply_to_regions_filters_correctly(self):
        """apply_to.regions restricts which rows the rules evaluate on."""
        probas = np.array([0.2, 0.5, 0.3, 0.8])
        # Row 1 is BLUMENAU with non-zero consumption — wouldn't trigger anyway.
        # But let's make row 1 have zeros to test that apply_to excludes it.
        raw_data = pd.DataFrame(
            {
                "3_anterior": [0.0, 0.0, 0.0, 50.0],
                "2_anterior": [0.0, 0.0, 0.0, 40.0],
                "1_anterior": [0.0, 0.0, 0.0, 10.0],
                "geo_region": ["VIDEIRA", "BLUMENAU", "JOACABA", "BLUMENAU"],
            }
        )
        rules_config = {
            "apply_to": {"regions": ["VIDEIRA", "JOACABA"]},  # excludes BLUMENAU
            "rules": [
                {
                    "name": "consumo_cero_3m",
                    "condition": "(`3_anterior` == 0) & (`2_anterior` == 0) & (`1_anterior` == 0)",
                    "action": "override",
                    "value": 1.0,
                }
            ],
            "output": {"add_rule_columns": True},
        }

        modified_probas, rules_df, _ = apply_business_rules(probas, raw_data, rules_config)

        # Row 0 (VIDEIRA, zeros): triggered → 1.0
        # Row 1 (BLUMENAU, zeros but NOT in apply_to): NOT triggered → unchanged
        # Row 2 (JOACABA, zeros): triggered → 1.0
        # Row 3 (BLUMENAU, non-zeros): NOT triggered → unchanged
        np.testing.assert_array_almost_equal(modified_probas, np.array([1.0, 0.5, 1.0, 0.8]))
        np.testing.assert_array_equal(
            rules_df["rule_consumo_cero_3m"].values,
            np.array([True, False, True, False]),
        )

    def test_stub_with_false_condition_never_triggers(self):
        """condition: 'False' (stub) never triggers regardless of data."""
        probas = np.array([0.2, 0.5, 0.3, 0.8])
        raw_data = self._make_raw_data()
        rules_config = {
            "apply_to": {"regions": ["VIDEIRA", "JOACABA", "BLUMENAU"]},
            "rules": [
                {
                    "name": "denuncia_sac",
                    "condition": "False",
                    "action": "override",
                    "value": 1.0,
                }
            ],
            "output": {"add_rule_columns": True},
        }

        modified_probas, rules_df, probas_modified = apply_business_rules(
            probas, raw_data, rules_config
        )

        # No probas modified (stub never triggers)
        assert probas_modified is False
        np.testing.assert_array_almost_equal(modified_probas, np.array([0.2, 0.5, 0.3, 0.8]))
        # Rule column is all False
        np.testing.assert_array_equal(
            rules_df["rule_denuncia_sac"].values,
            np.array([False, False, False, False]),
        )

    def test_invalid_column_logs_error_and_skips(self, caplog):
        """If condition references a non-existent column, log error and skip."""
        probas = np.array([0.2, 0.5, 0.3, 0.8])
        raw_data = self._make_raw_data()
        rules_config = {
            "apply_to": {"regions": ["VIDEIRA"]},
            "rules": [
                {
                    "name": "bad_rule",
                    "condition": "(`nonexistent_column` == 0)",
                    "action": "override",
                    "value": 1.0,
                },
                {
                    "name": "good_rule",
                    "condition": "(`1_anterior` == 0)",
                    "action": "override",
                    "value": 1.0,
                },
            ],
            "output": {"add_rule_columns": True},
        }

        with caplog.at_level(logging.ERROR):
            modified_probas, rules_df, _ = apply_business_rules(probas, raw_data, rules_config)

        # bad_rule skipped (error logged), good_rule applied
        # Row 0 (VIDEIRA, 1_anterior=0): good_rule triggers → 1.0
        np.testing.assert_array_almost_equal(modified_probas, np.array([1.0, 0.5, 0.3, 0.8]))
        # bad_rule all False (skipped), good_rule triggered on row 0
        np.testing.assert_array_equal(
            rules_df["rule_bad_rule"].values,
            np.array([False, False, False, False]),
        )
        np.testing.assert_array_equal(
            rules_df["rule_good_rule"].values,
            np.array([True, False, False, False]),
        )
        # Error was logged for bad_rule
        assert any("bad_rule" in record.message for record in caplog.records)

    def test_score_boost_rules_compose_additively(self):
        """Multiple score_boost rules accumulate (additive)."""
        probas = np.array([0.2, 0.5])
        raw_data = pd.DataFrame(
            {
                "3_anterior": [0.0, 100.0],
                "2_anterior": [0.0, 80.0],
                "1_anterior": [0.0, 10.0],
                "geo_region": ["VIDEIRA", "VIDEIRA"],
            }
        )
        rules_config = {
            "apply_to": {"regions": ["VIDEIRA"]},
            "rules": [
                {
                    "name": "rule_a",
                    "condition": "(`1_anterior` == 0)",
                    "action": "score_boost",
                    "value": 0.2,
                },
                {
                    "name": "rule_b",
                    "condition": "(`2_anterior` == 0)",
                    "action": "score_boost",
                    "value": 0.3,
                },
            ],
            "output": {"add_rule_columns": True},
        }

        modified_probas, rules_df, _ = apply_business_rules(probas, raw_data, rules_config)

        # Row 0: both rules trigger → 0.2 + 0.2 + 0.3 = 0.7
        # Row 1: neither triggers → 0.5
        np.testing.assert_array_almost_equal(modified_probas, np.array([0.7, 0.5]))

    def test_score_boost_clips_to_one(self):
        """score_boost clips probability to 1.0 (not above)."""
        probas = np.array([0.9])
        raw_data = pd.DataFrame(
            {
                "1_anterior": [0.0],
                "geo_region": ["VIDEIRA"],
            }
        )
        rules_config = {
            "apply_to": {"regions": ["VIDEIRA"]},
            "rules": [
                {
                    "name": "big_boost",
                    "condition": "(`1_anterior` == 0)",
                    "action": "score_boost",
                    "value": 0.5,
                }
            ],
            "output": {"add_rule_columns": True},
        }

        modified_probas, _, _ = apply_business_rules(probas, raw_data, rules_config)

        # 0.9 + 0.5 = 1.4 → clipped to 1.0
        np.testing.assert_array_almost_equal(modified_probas, np.array([1.0]))

    def test_apply_to_column_defaults_to_geo_region(self):
        """If apply_to.column is not specified, default to 'geo_region'."""
        probas = np.array([0.2, 0.5])
        raw_data = pd.DataFrame(
            {
                "1_anterior": [0.0, 10.0],
                "geo_region": ["VIDEIRA", "BLUMENAU"],
            }
        )
        rules_config = {
            "apply_to": {"regions": ["VIDEIRA"]},  # no 'column' key
            "rules": [
                {
                    "name": "r1",
                    "condition": "(`1_anterior` == 0)",
                    "action": "override",
                    "value": 1.0,
                }
            ],
            "output": {"add_rule_columns": True},
        }

        modified_probas, _, _ = apply_business_rules(probas, raw_data, rules_config)

        # Row 0 (VIDEIRA, 1_anterior=0): triggered → 1.0
        # Row 1 (BLUMENAU, 1_anterior=10): not eligible (BLUMENAU not in regions)
        np.testing.assert_array_almost_equal(modified_probas, np.array([1.0, 0.5]))

    def test_no_apply_to_applies_to_all_rows(self):
        """If apply_to is omitted, rules apply to ALL rows."""
        probas = np.array([0.2, 0.5])
        raw_data = pd.DataFrame(
            {
                "1_anterior": [0.0, 10.0],
                "geo_region": ["VIDEIRA", "BLUMENAU"],
            }
        )
        rules_config = {
            "rules": [
                {
                    "name": "r1",
                    "condition": "(`1_anterior` == 0)",
                    "action": "override",
                    "value": 1.0,
                }
            ],
            "output": {"add_rule_columns": True},
        }

        modified_probas, rules_df, _ = apply_business_rules(probas, raw_data, rules_config)

        # Row 0 (1_anterior=0): triggered → 1.0
        # Row 1 (1_anterior=10): not triggered → 0.5
        np.testing.assert_array_almost_equal(modified_probas, np.array([1.0, 0.5]))
        np.testing.assert_array_equal(rules_df["rule_r1"].values, np.array([True, False]))

    def test_misaligned_raw_data_and_probas_raises(self):
        """If raw_data and probas have different lengths, raise ValueError.

        Regression guard for custom FE that could drop/reorder rows. Without
        this check, rules would silently operate positionally on the wrong rows.
        """
        probas = np.array([0.2, 0.5, 0.8])  # 3 rows
        raw_data = pd.DataFrame(  # 2 rows — misaligned
            {
                "1_anterior": [0.0, 10.0],
                "geo_region": ["VIDEIRA", "BLUMENAU"],
            }
        )
        rules_config: Dict[str, Any] = {"rules": []}

        with pytest.raises(ValueError, match="misaligned"):
            apply_business_rules(probas, raw_data, rules_config)


# =============================================================================
# Builder integration tests (_apply_business_rules + execute())
# =============================================================================


class TestInferenceBuilderBusinessRules:
    """Integration tests for business rules in InferenceBuilder."""

    @pytest.fixture
    def mock_model(self):
        """Mock model returning predictable probabilities."""
        model = MagicMock()
        model.predict_proba.return_value = np.array([0.2, 0.5, 0.3, 0.8])
        return model

    def test_execute_applies_business_rules_after_segment_thresholds(self, tmp_path, mock_model):
        """execute() should apply business_rules after segment_thresholds."""
        # Arrange: segment thresholds + business_rules
        seg_json = tmp_path / "segment_thresholds_geo_region.json"
        seg_json.write_text(
            json.dumps(
                {
                    "segment_column": "geo_region",
                    "segments": {
                        "VIDEIRA": {"threshold": 0.5},
                        "BLUMENAU": {"threshold": 0.5},
                        "JOACABA": {"threshold": 0.5},
                    },
                }
            )
        )

        data = pd.DataFrame(
            {
                "3_anterior": [0.0, 100.0, 0.0, 50.0],
                "2_anterior": [0.0, 80.0, 0.0, 40.0],
                "1_anterior": [0.0, 60.0, 0.0, 10.0],
                "geo_region": ["VIDEIRA", "BLUMENAU", "JOACABA", "BLUMENAU"],
            }
        )
        data_path = tmp_path / "test_data.parquet"
        data.to_parquet(data_path, index=False)

        output_path = tmp_path / "predictions.csv"

        config = {
            "threshold": 0.5,
            "input_path": str(data_path),
            "output_path": str(output_path),
            "segment_thresholds": {
                "enabled": True,
                "path": str(seg_json),
                "fallback_threshold": 0.5,
            },
            "business_rules": {
                "enabled": True,
                "apply_to": {"regions": ["VIDEIRA", "JOACABA"]},
                "rules": [
                    {
                        "name": "consumo_cero_3m",
                        "condition": "(`3_anterior` == 0) & (`2_anterior` == 0) & (`1_anterior` == 0)",
                        "action": "override",
                        "value": 1.0,
                    }
                ],
                "output": {"add_rule_columns": True},
            },
            "output_include_input": True,
            "output_format": "csv",
        }

        builder = InferenceBuilder(config)
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"
        step.config["model_path"] = None  # use context model

        context = {"model": mock_model}
        result = step.execute(context)

        # Without rules: probas [0.2, 0.5, 0.3, 0.8] → threshold 0.5 → [0, 1, 0, 1]
        # With override on rows 0, 2 (VIDEIRA/JOACABA, all zeros): probas → [1.0, 0.5, 1.0, 0.8]
        # Re-derived: [1, 1, 1, 1]
        predictions = result["predictions"]
        np.testing.assert_array_equal(predictions, np.array([1, 1, 1, 1]))

        # probas modified
        probas = result["prediction_probas"]
        np.testing.assert_array_almost_equal(probas, np.array([1.0, 0.5, 1.0, 0.8]))

        # Output CSV includes rule columns
        assert output_path.exists()
        output_df = pd.read_csv(output_path)
        assert "rule_consumo_cero_3m" in output_df.columns
        assert "rule_consumo_cero_3m_value" in output_df.columns

    def test_execute_with_business_rules_disabled_is_backward_compatible(
        self, tmp_path, mock_model
    ):
        """When business_rules.enabled=False, predictions are unchanged."""
        data = pd.DataFrame(
            {
                "1_anterior": [0.0, 100.0, 0.0, 50.0],
                "geo_region": ["VIDEIRA", "BLUMENAU", "JOACABA", "BLUMENAU"],
            }
        )
        data_path = tmp_path / "test_data.parquet"
        data.to_parquet(data_path, index=False)

        config = {
            "threshold": 0.5,
            "input_path": str(data_path),
            "output_path": str(tmp_path / "preds.csv"),
            "business_rules": {
                "enabled": False,
            },
            "output_include_input": False,
            "output_format": "csv",
        }

        builder = InferenceBuilder(config)
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"
        step.config["model_path"] = None

        context = {"model": mock_model}
        result = step.execute(context)

        # probas [0.2, 0.5, 0.3, 0.8] → threshold 0.5 → [0, 1, 0, 1]
        np.testing.assert_array_equal(result["predictions"], np.array([0, 1, 0, 1]))
        np.testing.assert_array_almost_equal(
            result["prediction_probas"], np.array([0.2, 0.5, 0.3, 0.8])
        )

    def test_execute_with_no_business_rules_key_is_backward_compatible(self, tmp_path, mock_model):
        """When business_rules key is absent entirely, backward compatible."""
        data = pd.DataFrame(
            {
                "1_anterior": [0.0, 100.0, 0.0, 50.0],
                "geo_region": ["VIDEIRA", "BLUMENAU", "JOACABA", "BLUMENAU"],
            }
        )
        data_path = tmp_path / "test_data.parquet"
        data.to_parquet(data_path, index=False)

        config = {
            "threshold": 0.5,
            "input_path": str(data_path),
            "output_path": str(tmp_path / "preds.csv"),
            "output_format": "csv",
        }

        builder = InferenceBuilder(config)
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"
        step.config["model_path"] = None

        context = {"model": mock_model}
        result = step.execute(context)

        np.testing.assert_array_equal(result["predictions"], np.array([0, 1, 0, 1]))
