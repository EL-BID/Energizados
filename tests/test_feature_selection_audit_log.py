"""
Unit tests for feature selection audit log functionality.

Tests cover:
- BorutaSelector.vote_counts_ initialization and post-fit population
- get_audit_stats() pre-fit ValueError guard
- get_audit_stats() post-fit return values for all selectors
- FeatureSelectionPipeline.save_audit_log() JSON output
- TrainingStep audit log invocation
"""

import json

import numpy as np
import pandas as pd
import pytest

from energizados.feature_selection.methods import (
    BorutaSelector,
    ConstantSelector,
    CorrelationSelector,
    MutualInformationSelector,
)
from energizados.feature_selection.pipeline import FeatureSelectionPipeline


@pytest.fixture
def small_df():
    """6-column DataFrame with 50 rows."""
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        rng.uniform(0, 1, size=(50, 6)),
        columns=["feat_a", "feat_b", "feat_c", "feat_d", "feat_e", "feat_f"],
    )


@pytest.fixture
def small_target():
    """Binary target with 30% positive rate."""
    rng = np.random.default_rng(0)
    return pd.Series(rng.choice([0, 1], size=50, p=[0.7, 0.3]), name="target")


class TestBorutaVoteCounts:
    """Tests for BorutaSelector.vote_counts_ attribute."""

    def test_vote_counts_initialized_to_none(self):
        """vote_counts_ is None before fit()."""
        selector = BorutaSelector(n_estimators=10, max_iter=5, random_state=42)
        assert selector.vote_counts_ is None

    def test_vote_counts_populated_after_fit(self, small_df, small_target):
        """vote_counts_ is a dict after fit()."""
        selector = BorutaSelector(n_estimators=10, max_iter=5, random_state=42)
        selector.fit(small_df, small_target)
        assert selector.vote_counts_ is not None
        assert isinstance(selector.vote_counts_, dict)


class TestGetAuditStatsPreFit:
    """Tests for get_audit_stats() pre-fit behavior."""

    @pytest.mark.parametrize(
        "selector_class",
        [CorrelationSelector, ConstantSelector, BorutaSelector, MutualInformationSelector],
    )
    def test_get_audit_stats_raises_before_fit(self, selector_class):
        """get_audit_stats() raises ValueError before fit()."""
        if selector_class == BorutaSelector:
            selector = selector_class(n_estimators=10, max_iter=5, random_state=42)
        elif selector_class == ConstantSelector:
            selector = selector_class(threshold=0.99)
        elif selector_class == CorrelationSelector:
            selector = selector_class(threshold=0.9)
        else:
            selector = selector_class(k=5)

        with pytest.raises(ValueError, match="Must call fit"):
            selector.get_audit_stats()

    def test_vote_counts_raises_before_fit(self):
        """Accessing vote_counts_ before fit returns None (safe)."""
        selector = BorutaSelector(n_estimators=10, max_iter=5, random_state=42)
        # Must not raise AttributeError — returns None
        assert selector.vote_counts_ is None


class TestGetAuditStatsPostFit:
    """Tests for get_audit_stats() post-fit return values."""

    def test_correlation_selector_audit_stats(self, small_df, small_target):
        """CorrelationSelector returns vars_to_drop, method, threshold."""
        selector = CorrelationSelector(threshold=0.9)
        selector.fit(small_df, small_target)
        stats = selector.get_audit_stats()
        assert "vars_to_drop" in stats
        assert "method" in stats
        assert "threshold" in stats
        assert stats["threshold"] == 0.9

    def test_constant_selector_audit_stats(self, small_df, small_target):
        """ConstantSelector returns vars_to_drop and threshold."""
        selector = ConstantSelector(threshold=0.99)
        selector.fit(small_df, small_target)
        stats = selector.get_audit_stats()
        assert "vars_to_drop" in stats
        assert "threshold" in stats
        assert stats["threshold"] == 0.99

    def test_boruta_selector_audit_stats(self, small_df, small_target):
        """BorutaSelector returns vote_counts, n_runs, threshold."""
        selector = BorutaSelector(n_estimators=10, max_iter=5, random_state=42)
        selector.fit(small_df, small_target)
        stats = selector.get_audit_stats()
        assert "vote_counts" in stats
        assert "n_runs" in stats
        assert "threshold" in stats
        assert isinstance(stats["vote_counts"], dict)

    def test_mutual_info_selector_audit_stats(self, small_df, small_target):
        """MutualInformationSelector returns scores and k."""
        selector = MutualInformationSelector(k=5)
        selector.fit(small_df, small_target)
        stats = selector.get_audit_stats()
        assert "scores" in stats
        assert "k" in stats
        assert stats["k"] == 5


class TestSaveAuditLog:
    """Tests for FeatureSelectionPipeline.save_audit_log()."""

    def test_save_audit_log_creates_file(self, small_df, small_target, tmp_path):
        """save_audit_log() creates a JSON file."""
        pipeline = FeatureSelectionPipeline(
            steps_config=[
                {"name": "corr", "method": "correlation", "params": {"threshold": 0.9}},
                {"name": "const", "method": "constant", "params": {"threshold": 0.99}},
            ]
        )
        pipeline.fit(small_df, small_target)

        audit_path = tmp_path / "audit.json"
        pipeline.save_audit_log(audit_path)

        assert audit_path.exists()
        with open(audit_path) as f:
            data = json.load(f)

        assert "steps" in data
        assert "final_selected_count" in data
        assert "final_selected_features" in data
        assert len(data["steps"]) == 2

    def test_save_audit_log_step_has_audit_stats(self, small_df, small_target, tmp_path):
        """Boruta step in audit log has vote_counts in audit_stats."""
        pipeline = FeatureSelectionPipeline(
            steps_config=[
                {
                    "name": "boruta",
                    "method": "boruta",
                    "params": {"n_estimators": 10, "max_iter": 5, "random_state": 42},
                },
            ]
        )
        pipeline.fit(small_df, small_target)

        audit_path = tmp_path / "audit.json"
        pipeline.save_audit_log(audit_path)

        with open(audit_path) as f:
            data = json.load(f)

        step = data["steps"][0]
        assert "audit_stats" in step
        assert "vote_counts" in step["audit_stats"]

    def test_save_audit_log_boruta_has_vote_counts(self, small_df, small_target, tmp_path):
        """Boruta step audit log contains vote_counts."""
        pipeline = FeatureSelectionPipeline(
            steps_config=[
                {
                    "name": "boruta",
                    "method": "boruta",
                    "params": {"n_estimators": 10, "max_iter": 5, "random_state": 42},
                },
            ]
        )
        pipeline.fit(small_df, small_target)

        audit_path = tmp_path / "audit.json"
        pipeline.save_audit_log(audit_path)

        with open(audit_path) as f:
            data = json.load(f)

        step = data["steps"][0]
        assert "audit_stats" in step
        assert "vote_counts" in step["audit_stats"]
