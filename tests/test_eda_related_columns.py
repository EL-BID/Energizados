"""Tests for RelatedColumnsAnalyzer and column detail chart generation."""

import pandas as pd
import pytest

from energizados.eda.related_columns_analyzer import RelatedColumnsAnalyzer


@pytest.fixture
def sample_df():
    """Sample DataFrame with hierarchical columns and a binary target."""
    return pd.DataFrame(
        {
            "TIPO": ["A", "A", "A", "A", "B", "B", "B", "B", "C", "C"] * 10,
            "ACAO": ["x", "x", "y", "y", "x", "x", "z", "z", "x", "y"] * 10,
            "CATEGORIA": ["c1", "c2", "c1", "c2", "c1", "c1", "c3", "c3", "c1", "c2"] * 10,
            "target": [1, 0, 0, 0, 1, 1, 0, 0, 0, 1] * 10,
        }
    )


@pytest.fixture
def analyzer():
    return RelatedColumnsAnalyzer()


class TestRelatedColumnsAnalyzer:
    def test_valid_hierarchy_two_columns(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            target_col="target",
            hierarchies=[{"name": "test", "columns": ["TIPO", "ACAO"]}],
        )
        assert "test" in results
        data = results["test"]
        assert "level_distributions" in data
        assert "cross_tabulation" in data
        assert "tree_breakdown" in data
        assert len(data["tree_breakdown"]) > 0

    def test_valid_hierarchy_three_columns(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            target_col="target",
            hierarchies=[{"name": "full", "columns": ["TIPO", "ACAO", "CATEGORIA"]}],
        )
        data = results["full"]
        # Tree should have children at each level
        tree = data["tree_breakdown"]
        assert len(tree) > 0
        # First node should have children
        assert "children" in tree[0]
        # Second level should also have children
        assert any("children" in child for child in tree[0]["children"])

    def test_with_target_rates(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            target_col="target",
            hierarchies=[{"name": "tr", "columns": ["TIPO", "ACAO"]}],
        )
        assert "target_rates" in results["tr"]
        assert len(results["tr"]["target_rates"]) > 0
        # Each entry should have target_rate and count
        entry = results["tr"]["target_rates"][0]
        assert "target_rate" in entry
        assert "count" in entry

    def test_missing_columns_graceful_skip(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            hierarchies=[{"name": "bad", "columns": ["TIPO", "NONEXISTENT"]}],
        )
        assert "bad" not in results
        alerts = analyzer.get_alerts()
        assert any(a["code"] == "HIERARCHY_MISSING_COLUMNS" for a in alerts)

    def test_single_column_hierarchy(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            hierarchies=[{"name": "single", "columns": ["TIPO"]}],
        )
        data = results["single"]
        assert "level_distributions" in data
        assert len(data["tree_breakdown"]) > 0
        # No children since only one level
        assert "children" not in data["tree_breakdown"][0]

    def test_no_hierarchies_returns_empty(self, analyzer, sample_df):
        results = analyzer.analyze(sample_df, hierarchies=None)
        assert results == {}

        results2 = analyzer.analyze(sample_df, hierarchies=[])
        assert results2 == {}

    def test_empty_columns_list_skipped(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            hierarchies=[{"name": "empty", "columns": []}],
        )
        assert "empty" not in results

    def test_without_target(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            target_col=None,
            hierarchies=[{"name": "no_target", "columns": ["TIPO", "ACAO"]}],
        )
        data = results["no_target"]
        assert "target_rates" not in data
        assert "cross_tabulation" in data

    def test_sparse_combination_alert(self, sample_df):
        analyzer = RelatedColumnsAnalyzer(config={"sparse_combination_threshold": 50})
        analyzer.analyze(
            sample_df,
            hierarchies=[{"name": "sparse", "columns": ["TIPO", "ACAO", "CATEGORIA"]}],
        )
        alerts = analyzer.get_alerts()
        assert any(a["code"] == "HIERARCHY_SPARSE_COMBINATION" for a in alerts)

    def test_dominant_path_alert(self):
        # Create a dataset where one combination dominates
        df = pd.DataFrame(
            {
                "A": ["dominant"] * 90 + ["other"] * 10,
                "B": ["val1"] * 90 + ["val2"] * 10,
            }
        )
        analyzer = RelatedColumnsAnalyzer(config={"dominant_path_threshold": 0.8})
        analyzer.analyze(df, hierarchies=[{"name": "dom", "columns": ["A", "B"]}])
        alerts = analyzer.get_alerts()
        assert any(a["code"] == "HIERARCHY_DOMINANT_PATH" for a in alerts)

    def test_target_disparity_alert(self):
        # Create disparity: multiple combos with varying target rates
        df = pd.DataFrame(
            {
                "A": ["high"] * 50 + ["low"] * 50 + ["mid"] * 50,
                "B": ["x"] * 50 + ["y"] * 50 + ["z"] * 50,
                "target": [1] * 50 + [0] * 50 + [0] * 25 + [1] * 25,
            }
        )
        analyzer = RelatedColumnsAnalyzer(config={"target_disparity_zscore": 0.9})
        analyzer.analyze(
            df,
            target_col="target",
            hierarchies=[{"name": "disp", "columns": ["A", "B"]}],
        )
        alerts = analyzer.get_alerts()
        assert any(a["code"] == "HIERARCHY_TARGET_DISPARITY" for a in alerts)

    def test_tree_breakdown_pct_of_parent(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            hierarchies=[{"name": "pct", "columns": ["TIPO", "ACAO"]}],
        )
        tree = results["pct"]["tree_breakdown"]
        # Sum of pct_of_parent at root level should be ~100%
        total_pct = sum(node["pct_of_parent"] for node in tree)
        assert abs(total_pct - 100.0) < 0.1

    def test_multiple_hierarchies(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            hierarchies=[
                {"name": "h1", "columns": ["TIPO", "ACAO"]},
                {"name": "h2", "columns": ["ACAO", "CATEGORIA"]},
            ],
        )
        assert "h1" in results
        assert "h2" in results

    def test_cross_tabulation_has_count(self, analyzer, sample_df):
        results = analyzer.analyze(
            sample_df,
            hierarchies=[{"name": "ct", "columns": ["TIPO", "ACAO"]}],
        )
        cross = results["ct"]["cross_tabulation"]
        assert len(cross) > 0
        assert "count" in cross[0]
        assert "TIPO" in cross[0]
        assert "ACAO" in cross[0]
