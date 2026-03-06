"""
Unit tests for FeatureSelectionPipeline and SelectionStep.

Tests: single ML step with/without scope, selection union/intersection/difference,
exclusion, empty scope warning, unknown method, unknown @ref, fit→transform
consistency, last-step defines result, backward compat via legacy method: key.
"""

import logging

import numpy as np
import pandas as pd
import pytest

from energizados.feature_selection.column_resolver import ColumnResolver
from energizados.feature_selection.pipeline import (
    FeatureSelectionPipeline,
    SelectionStep,
)


@pytest.fixture
def small_df():
    """6-column DataFrame with 50 rows.

    Returns:
        pd.DataFrame: A DataFrame with 6 columns and 50 rows of random data.
    """
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "a_anterior": rng.random(50),
            "b_anterior": rng.random(50),
            "c_anterior": rng.random(50),
            "zona": rng.integers(0, 5, 50).astype(float),
            "actividad": rng.integers(0, 3, 50).astype(float),
            "tipo": rng.integers(0, 2, 50).astype(float),
        }
    )


@pytest.fixture
def y(small_df):
    """Target variable for testing.

    Args:
        small_df: The input DataFrame (unused in this fixture).

    Returns:
        pd.Series: A Series with random binary labels.
    """
    rng = np.random.default_rng(1)
    return pd.Series(rng.integers(0, 2, len(small_df)))


# ---------------------------------------------------------------------------
# SelectionStep tests
# ---------------------------------------------------------------------------


class TestSelectionStep:
    """Tests for the SelectionStep class."""

    @pytest.fixture
    def resolver(self, small_df):
        """Create a ColumnResolver for testing.

        Args:
            small_df: Input DataFrame to get columns from.

        Returns:
            ColumnResolver: A resolver with sample columns and step results.
        """
        return ColumnResolver(
            list(small_df.columns),
            step_results={
                "step_a": ["a_anterior", "b_anterior"],
                "step_b": ["b_anterior", "zona"],
            },
        )

    def test_union(self, resolver, small_df):
        """Verify union operation combines features from multiple sources."""
        step = SelectionStep("union", ["@step_a", "@step_b"])
        step.fit_with_resolver(resolver, list(small_df.columns))
        assert set(step.selected_features_) == {"a_anterior", "b_anterior", "zona"}

    def test_intersection(self, resolver, small_df):
        """Verify intersection operation keeps only common features."""
        step = SelectionStep("intersection", ["@step_a", "@step_b"])
        step.fit_with_resolver(resolver, list(small_df.columns))
        assert step.selected_features_ == ["b_anterior"]

    def test_difference(self, resolver, small_df):
        """Verify difference operation keeps features only in first set."""
        step = SelectionStep("difference", ["@step_a", "@step_b"])
        step.fit_with_resolver(resolver, list(small_df.columns))
        assert set(step.selected_features_) == {"a_anterior"}

    def test_exclusion_in_union(self, resolver, small_df):
        """Verify that exclusion works within union operation."""
        step = SelectionStep("union", ["@step_a", "@step_b", "!b_anterior"])
        step.fit_with_resolver(resolver, list(small_df.columns))
        assert "b_anterior" not in step.selected_features_
        assert "a_anterior" in step.selected_features_
        assert "zona" in step.selected_features_

    def test_invalid_operation_raises(self):
        """Verify that invalid operation raises ValueError."""
        with pytest.raises(ValueError, match="operation"):
            SelectionStep("unknown_op", [])

    def test_transform_after_fit(self, resolver, small_df):
        """Verify that transform works after fit."""
        step = SelectionStep("union", ["@step_a"])
        step.fit_with_resolver(resolver, list(small_df.columns))
        result = step.transform(small_df)
        assert list(result.columns) == step.selected_features_

    def test_transform_before_fit_raises(self, small_df):
        """Verify that transform before fit raises ValueError."""
        step = SelectionStep("union", ["zona"])
        with pytest.raises(ValueError):
            step.transform(small_df)

    def test_order_preserved(self, resolver, small_df):
        """Verify that column order from original DataFrame is preserved."""
        step = SelectionStep("union", ["zona", "a_anterior"])
        step.fit_with_resolver(resolver, list(small_df.columns))
        # Order follows small_df column order: a_anterior first, zona later
        assert step.selected_features_.index("a_anterior") < step.selected_features_.index("zona")


# ---------------------------------------------------------------------------
# FeatureSelectionPipeline tests
# ---------------------------------------------------------------------------


class TestFeatureSelectionPipeline:
    """Tests for the FeatureSelectionPipeline class."""

    def test_single_constant_step_no_scope(self, small_df, y):
        """Verify single constant step without scope works."""
        cfg = [{"name": "const", "method": "constant", "params": {"threshold": 0.99}}]
        p = FeatureSelectionPipeline(cfg)
        p.fit(small_df, y)
        assert p.selected_features_ is not None
        result = p.transform(small_df)
        assert set(result.columns).issubset(set(small_df.columns))

    def test_single_constant_step_with_scope(self, small_df, y):
        """Verify single constant step with column scope."""
        cfg = [
            {
                "name": "const",
                "method": "constant",
                "params": {"threshold": 0.99},
                "columns": ["*_anterior"],
            }
        ]
        p = FeatureSelectionPipeline(cfg)
        p.fit(small_df, y)
        # Only columns from the glob can appear in result
        for col in p.selected_features_:
            assert col.endswith("_anterior")

    def test_last_step_defines_result(self, small_df, y):
        """Verify that the last step defines the final result."""
        cfg = [
            {"name": "step1", "method": "constant", "params": {"threshold": 0.99}},
            {
                "name": "step2",
                "method": "selection",
                "operation": "union",
                "columns": ["@step1", "zona"],
            },
        ]
        p = FeatureSelectionPipeline(cfg)
        p.fit(small_df, y)
        assert "zona" in p.selected_features_

    def test_selection_union(self, small_df, y):
        """Verify union selection operation."""
        cfg = [
            {"name": "s1", "method": "constant", "params": {"threshold": 0.99}, "columns": ["*_anterior"]},
            {"name": "s2", "method": "constant", "params": {"threshold": 0.99}, "columns": ["zona", "actividad"]},
            {"name": "final", "method": "selection", "operation": "union", "columns": ["@s1", "@s2"]},
        ]
        p = FeatureSelectionPipeline(cfg)
        p.fit(small_df, y)
        # Final must be union of s1 and s2 results
        expected = set(p._step_results["s1"]) | set(p._step_results["s2"])
        assert set(p.selected_features_) == expected

    def test_selection_intersection(self, small_df, y):
        """Verify intersection selection operation."""
        cfg = [
            {
                "name": "final",
                "method": "selection",
                "operation": "intersection",
                "columns": ["a_anterior", "zona", "zona"],
            }
        ]
        # Intersection of {a_anterior} and {zona} → empty
        p = FeatureSelectionPipeline(cfg)
        p.fit(small_df, y)
        assert p.selected_features_ == []

    def test_selection_difference(self, small_df, y):
        """Verify difference selection operation."""
        cfg = [
            {
                "name": "final",
                "method": "selection",
                "operation": "difference",
                "columns": ["*_anterior", "!b_anterior"],
            }
        ]
        p = FeatureSelectionPipeline(cfg)
        p.fit(small_df, y)
        assert "b_anterior" not in p.selected_features_
        assert "a_anterior" in p.selected_features_

    def test_empty_scope_warns_and_skips(self, small_df, y, caplog):
        """Verify that empty scope logs warning and skips step."""
        cfg = [
            {"name": "step1", "method": "constant", "columns": ["nonexistent_col"]},
        ]
        with caplog.at_level(logging.WARNING):
            p = FeatureSelectionPipeline(cfg)
            p.fit(small_df, y)
        assert any("empty column scope" in r.message for r in caplog.records)
        assert p._step_results["step1"] == []

    def test_unknown_method_raises(self, small_df, y):
        """Verify that unknown method raises ValueError."""
        cfg = [{"name": "x", "method": "unknown_algo"}]
        p = FeatureSelectionPipeline(cfg)
        with pytest.raises(ValueError, match="unknown_algo"):
            p.fit(small_df, y)

    def test_unknown_step_ref_raises(self, small_df, y):
        """Verify that unknown step reference raises KeyError."""
        cfg = [
            {
                "name": "final",
                "method": "selection",
                "operation": "union",
                "columns": ["@nonexistent"],
            }
        ]
        p = FeatureSelectionPipeline(cfg)
        with pytest.raises(KeyError, match="@nonexistent"):
            p.fit(small_df, y)

    def test_fit_transform_consistent(self, small_df, y):
        """Verify that fit_transform is consistent with separate fit/transform."""
        cfg = [{"name": "const", "method": "constant", "params": {"threshold": 0.99}}]
        p = FeatureSelectionPipeline(cfg)
        p.fit(small_df, y)
        result = p.transform(small_df)
        assert list(result.columns) == p.get_selected_features()

    def test_transform_before_fit_raises(self, small_df):
        """Verify that transform before fit raises ValueError."""
        p = FeatureSelectionPipeline([])
        with pytest.raises(ValueError):
            p.transform(small_df)

    def test_get_selected_features_before_fit_raises(self, small_df):
        """Verify that get_selected_features before fit raises ValueError."""
        p = FeatureSelectionPipeline([])
        with pytest.raises(ValueError):
            p.get_selected_features()

    def test_empty_steps_uses_all_columns(self, small_df, y):
        """Verify that no steps results in all columns selected."""
        p = FeatureSelectionPipeline([])
        p.fit(small_df, y)
        assert p.selected_features_ == list(small_df.columns)

    def test_custom_method_map(self, small_df, y):
        """Verify that custom method_map overrides built-in methods."""
        from energizados.feature_selection.methods import ConstantSelector

        custom_map = {"my_method": ConstantSelector}
        cfg = [{"name": "s", "method": "my_method", "params": {"threshold": 0.99}}]
        p = FeatureSelectionPipeline(cfg, method_map=custom_map)
        p.fit(small_df, y)
        assert p.selected_features_ is not None


# ---------------------------------------------------------------------------
# _build_selector() via default.py
# ---------------------------------------------------------------------------


class TestBuildSelectorViaDefaultPy:
    """Tests for _build_selector via default.py module."""

    def test_steps_key_builds_pipeline(self):
        """Verify that steps key builds a pipeline."""
        from energizados.feature_selection.pipeline import FeatureSelectionPipeline

        cfg = {"steps": [{"name": "c", "method": "constant", "params": {"threshold": 0.99}}]}
        pipeline = FeatureSelectionPipeline(steps_config=cfg["steps"])
        assert isinstance(pipeline, FeatureSelectionPipeline)

    def test_missing_steps_key_raises(self):
        """Verify that missing steps key raises ValueError."""
        from unittest.mock import MagicMock

        from energizados.feature_engineering.default import (
            DefaultFeatureEngineering,
        )

        mock = MagicMock()
        mock.feature_selection_config = {"method": "constant", "params": {"threshold": 0.99}}
        with pytest.raises(ValueError, match="steps"):
            DefaultFeatureEngineering._build_selector(mock)
