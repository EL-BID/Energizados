"""
Unit tests for ColumnResolver.

Tests pattern resolution: literal, glob, regex, @step_ref, ! exclusion,
order preservation, and deduplication.
"""

import re

import pytest

from energizados.feature_selection.column_resolver import ColumnResolver

COLS = ["a_anterior", "b_anterior", "c_anterior", "zona", "actividad", "tipo"]


@pytest.fixture
def resolver():
    """Fixture that creates a ColumnResolver with sample data.

    Returns:
        ColumnResolver: A resolver with sample columns and step results.
    """
    return ColumnResolver(COLS, step_results={"prev": ["zona", "actividad"]})


class TestLiteralMatch:
    """Tests for literal column name matching."""

    def test_existing_column(self, resolver):
        """Verify that an existing column is resolved correctly."""
        assert resolver.resolve(["zona"]) == ["zona"]

    def test_missing_column_is_empty(self, resolver):
        """Verify that a missing column returns empty list."""
        assert resolver.resolve(["nonexistent"]) == []

    def test_multiple_literals(self, resolver):
        """Verify that multiple literal columns are resolved correctly."""
        result = resolver.resolve(["zona", "actividad"])
        assert result == ["zona", "actividad"]


class TestGlobMatch:
    """Tests for glob pattern matching."""

    def test_star_suffix(self, resolver):
        """Verify glob pattern with star suffix."""
        result = resolver.resolve(["*_anterior"])
        assert result == ["a_anterior", "b_anterior", "c_anterior"]

    def test_star_prefix(self, resolver):
        """Verify glob pattern with star prefix."""
        result = resolver.resolve(["a_*"])
        assert result == ["a_anterior"]

    def test_no_match_glob(self, resolver):
        """Verify glob pattern with no matches returns empty list."""
        assert resolver.resolve(["z_*"]) == []

    def test_question_mark(self, resolver):
        """Verify glob pattern with question mark wildcard."""
        result = resolver.resolve(["?_anterior"])
        assert result == ["a_anterior", "b_anterior", "c_anterior"]


class TestRegexMatch:
    """Tests for regex pattern matching."""

    def test_regex_prefix(self, resolver):
        """Verify regex pattern matching prefix."""
        result = resolver.resolve(["re:^zona"])
        assert result == ["zona"]

    def test_regex_search(self, resolver):
        """Verify regex pattern searching within string."""
        result = resolver.resolve(["re:anterior$"])
        assert result == ["a_anterior", "b_anterior", "c_anterior"]

    def test_bad_regex_raises(self, resolver):
        """Verify that invalid regex raises error."""
        with pytest.raises(re.error):
            resolver.resolve(["re:[invalid"])

    def test_no_match_regex(self, resolver):
        """Verify regex pattern with no matches returns empty list."""
        assert resolver.resolve(["re:^xyz"]) == []


class TestStepRef:
    """Tests for step reference (@step_name) resolution."""

    def test_known_step(self, resolver):
        """Verify that known step reference is resolved correctly."""
        result = resolver.resolve(["@prev"])
        assert result == ["zona", "actividad"]

    def test_unknown_step_raises(self, resolver):
        """Verify that unknown step reference raises KeyError."""
        with pytest.raises(KeyError, match="@unknown"):
            resolver.resolve(["@unknown"])


class TestExclusion:
    """Tests for column exclusion (!pattern) functionality."""

    def test_exclude_literal(self, resolver):
        """Verify exclusion of a literal column."""
        result = resolver.resolve(["*_anterior", "!b_anterior"])
        assert "b_anterior" not in result
        assert "a_anterior" in result
        assert "c_anterior" in result

    def test_exclude_glob(self, resolver):
        """Verify exclusion using glob pattern."""
        result = resolver.resolve(["*_anterior", "zona", "!*_anterior"])
        assert result == ["zona"]

    def test_exclude_step_ref(self, resolver):
        """Verify exclusion of step reference results."""
        # Include everything, then exclude step ref (zona, actividad)
        result = resolver.resolve(list(COLS) + ["!@prev"])
        assert "zona" not in result
        assert "actividad" not in result
        assert "tipo" in result

    def test_exclude_regex(self, resolver):
        """Verify exclusion using regex pattern."""
        result = resolver.resolve(["*_anterior", "!re:^b_"])
        assert "b_anterior" not in result
        assert "a_anterior" in result

    def test_only_exclusion_returns_empty(self, resolver):
        """Verify that only exclusion pattern returns empty list."""
        assert resolver.resolve(["!zona"]) == []


class TestOrderAndDeduplication:
    """Tests for order preservation and deduplication."""

    def test_order_preserved(self, resolver):
        """Verify that result order follows original column order."""
        # Provide patterns in reverse order but result must follow COLS order
        result = resolver.resolve(["c_anterior", "a_anterior"])
        assert result == ["a_anterior", "c_anterior"]

    def test_deduplication(self, resolver):
        """Verify that duplicate columns are removed."""
        result = resolver.resolve(["zona", "zona", "*_anterior", "a_anterior"])
        assert result.count("a_anterior") == 1
        assert result.count("zona") == 1
