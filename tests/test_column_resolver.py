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
    return ColumnResolver(COLS, step_results={"prev": ["zona", "actividad"]})


class TestLiteralMatch:
    def test_existing_column(self, resolver):
        assert resolver.resolve(["zona"]) == ["zona"]

    def test_missing_column_is_empty(self, resolver):
        assert resolver.resolve(["nonexistent"]) == []

    def test_multiple_literals(self, resolver):
        result = resolver.resolve(["zona", "actividad"])
        assert result == ["zona", "actividad"]


class TestGlobMatch:
    def test_star_suffix(self, resolver):
        result = resolver.resolve(["*_anterior"])
        assert result == ["a_anterior", "b_anterior", "c_anterior"]

    def test_star_prefix(self, resolver):
        result = resolver.resolve(["a_*"])
        assert result == ["a_anterior"]

    def test_no_match_glob(self, resolver):
        assert resolver.resolve(["z_*"]) == []

    def test_question_mark(self, resolver):
        result = resolver.resolve(["?_anterior"])
        assert result == ["a_anterior", "b_anterior", "c_anterior"]


class TestRegexMatch:
    def test_regex_prefix(self, resolver):
        result = resolver.resolve(["re:^zona"])
        assert result == ["zona"]

    def test_regex_search(self, resolver):
        result = resolver.resolve(["re:anterior$"])
        assert result == ["a_anterior", "b_anterior", "c_anterior"]

    def test_bad_regex_raises(self, resolver):
        with pytest.raises(re.error):
            resolver.resolve(["re:[invalid"])

    def test_no_match_regex(self, resolver):
        assert resolver.resolve(["re:^xyz"]) == []


class TestStepRef:
    def test_known_step(self, resolver):
        result = resolver.resolve(["@prev"])
        assert result == ["zona", "actividad"]

    def test_unknown_step_raises(self, resolver):
        with pytest.raises(KeyError, match="@unknown"):
            resolver.resolve(["@unknown"])


class TestExclusion:
    def test_exclude_literal(self, resolver):
        result = resolver.resolve(["*_anterior", "!b_anterior"])
        assert "b_anterior" not in result
        assert "a_anterior" in result
        assert "c_anterior" in result

    def test_exclude_glob(self, resolver):
        result = resolver.resolve(["*_anterior", "zona", "!*_anterior"])
        assert result == ["zona"]

    def test_exclude_step_ref(self, resolver):
        # Include everything, then exclude step ref (zona, actividad)
        result = resolver.resolve(list(COLS) + ["!@prev"])
        assert "zona" not in result
        assert "actividad" not in result
        assert "tipo" in result

    def test_exclude_regex(self, resolver):
        result = resolver.resolve(["*_anterior", "!re:^b_"])
        assert "b_anterior" not in result
        assert "a_anterior" in result

    def test_only_exclusion_returns_empty(self, resolver):
        assert resolver.resolve(["!zona"]) == []


class TestOrderAndDeduplication:
    def test_order_preserved(self, resolver):
        # Provide patterns in reverse order but result must follow COLS order
        result = resolver.resolve(["c_anterior", "a_anterior"])
        assert result == ["a_anterior", "c_anterior"]

    def test_deduplication(self, resolver):
        result = resolver.resolve(["zona", "zona", "*_anterior", "a_anterior"])
        assert result.count("a_anterior") == 1
        assert result.count("zona") == 1
