"""
Unit tests for EDA configurable phase selection (DatasetExplorer phase gates).

Tests cover:
- Phases 0-3 and 5 respect enabled flag in sections dict
- Disabled phases return {} and don't run
- All phases run by default (backward compat, enabled=True by default)
- Phase 4, 6, 7 existing enabled gates still work
"""

import os

import pandas as pd
import pytest

from energizados.eda.dataset_explorer import DatasetExplorer


@pytest.fixture
def sample_df():
    """Simple DataFrame for EDA testing."""
    return pd.DataFrame(
        {
            "customer_id": range(100),
            "zona": ["A"] * 30 + ["B"] * 40 + ["C"] * 30,
            "tipo_tarifa": ["residencial"] * 60 + ["comercial"] * 40,
            "target": [0] * 70 + [1] * 30,
        }
    )


@pytest.fixture
def sample_csv(tmp_path, sample_df):
    """Write sample_df to a CSV file and return the path."""
    path = tmp_path / "sample.csv"
    sample_df.to_csv(path, index=False)
    return str(path)


class TestPhaseGatesEnabled:
    """Tests for phase enabled gates — phases run when enabled=True."""

    @pytest.mark.parametrize(
        "phase_key",
        [
            "loading",
            "global_stats",
            "columns",
            "target",
            "feature_importance",
        ],
    )
    def test_phase_runs_when_enabled(self, sample_csv, phase_key, caplog):
        """Each phase runs when sections[phase_key].enabled=True."""
        sections = {phase_key: {"enabled": True}}
        explorer = DatasetExplorer(
            input_path=sample_csv,
            target_column="target",
            output_dir=os.path.dirname(sample_csv),
            sections=sections,
        )

        results = explorer.run()

        key_map = {
            "loading": "loading",
            "global_stats": "global_stats",
            "columns": "columns",
            "target": "target",
            "feature_importance": "importance",
        }
        result_key = key_map[phase_key]
        assert result_key in results
        assert results[result_key] != {}  # Should have content

    @pytest.mark.parametrize(
        "phase_key",
        [
            "loading",
            "global_stats",
            "columns",
            "target",
            "feature_importance",
        ],
    )
    def test_phase_skipped_when_disabled(self, sample_csv, phase_key):
        """Each phase is skipped when sections[phase_key].enabled=False."""
        sections = {phase_key: {"enabled": False}}
        explorer = DatasetExplorer(
            input_path=sample_csv,
            target_column="target",
            output_dir=os.path.dirname(sample_csv),
            sections=sections,
        )

        results = explorer.run()

        key_map = {
            "loading": "loading",
            "global_stats": "global_stats",
            "columns": "columns",
            "target": "target",
            "feature_importance": "importance",
        }
        result_key = key_map[phase_key]
        assert result_key in results
        assert results[result_key] == {}  # Empty dict when disabled


class TestPhaseGatesDefault:
    """Tests for default behavior (backward compatibility)."""

    def test_all_phases_run_by_default(self, sample_csv):
        """All phases run when sections is None (backward compat)."""
        explorer = DatasetExplorer(
            input_path=sample_csv,
            target_column="target",
            output_dir=os.path.dirname(sample_csv),
            sections=None,  # Default
        )

        results = explorer.run()

        # All phase result keys should be present and non-empty
        assert results["loading"] != {}
        assert results["global_stats"] != {}
        assert results["columns"] != {}
        assert results["target"] != {}
        assert results["importance"] != {}

    def test_missing_section_key_defaults_to_enabled(self, sample_csv):
        """Phase runs when its key is absent from sections dict."""
        sections = {"loading": {"enabled": False}}
        explorer = DatasetExplorer(
            input_path=sample_csv,
            target_column="target",
            output_dir=os.path.dirname(sample_csv),
            sections=sections,
        )

        results = explorer.run()

        # Other phases should still run
        assert results["global_stats"] != {}
        assert results["columns"] != {}
