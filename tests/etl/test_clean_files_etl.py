"""
Unit tests for CleanFilesETL.

Files to delete come from ``input_paths`` (resolved by the orchestrator from
the YAML ``input`` field — supports @refs, globs, and direct paths).

Tests cover: successful deletion, missing_ok behavior, empty input_paths,
abstract method stubs, and orchestrator integration (@ref resolution, globs).
"""

import os
from pathlib import Path

import pandas as pd
import pytest

from energizados.core.exceptions import ETLError
from energizados.etl.orchestrator import ETLOrchestrator
from energizados.etl.pipeline import CleanFilesETL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_files(tmp_path, names):
    """Create empty files at tmp_path and return their absolute string paths."""
    paths = []
    for name in names:
        p = tmp_path / name
        p.write_text("", encoding="utf-8")
        paths.append(str(p))
    return paths


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestCleanFilesETLInit:
    def test_stores_input_paths_and_defaults(self, tmp_path):
        paths = [str(tmp_path / "a.parquet"), str(tmp_path / "b.parquet")]
        etl = CleanFilesETL(name="clean", input_paths=paths)
        assert etl.input_paths == paths
        assert etl.missing_ok is True
        assert etl.output_path is None

    def test_missing_ok_false(self):
        etl = CleanFilesETL(name="clean", input_paths=[], missing_ok=False)
        assert etl.missing_ok is False

    def test_output_path_stored(self):
        etl = CleanFilesETL(name="clean", input_paths=[], output_path="data/.done")
        assert etl.output_path == "data/.done"

    def test_no_input_paths_defaults_to_empty(self):
        etl = CleanFilesETL(name="clean")
        assert etl.input_paths == []

    def test_extra_kwargs_ignored(self):
        etl = CleanFilesETL(name="clean", input_paths=[], unknown_param="whatever")
        assert etl.name == "clean"


# ---------------------------------------------------------------------------
# run() — successful deletion
# ---------------------------------------------------------------------------


class TestCleanFilesETLRun:
    def test_deletes_existing_files(self, tmp_path):
        paths = _make_files(tmp_path, ["a.parquet", "b.parquet"])
        etl = CleanFilesETL(name="clean", input_paths=paths)

        etl.run()

        for p in paths:
            assert not Path(p).exists()

    def test_returns_empty_dataframe(self, tmp_path):
        paths = _make_files(tmp_path, ["a.parquet"])
        etl = CleanFilesETL(name="clean", input_paths=paths)

        result = etl.run()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_empty_input_paths_returns_empty_dataframe(self):
        etl = CleanFilesETL(name="clean", input_paths=[])
        result = etl.run()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_output_path_argument_accepted(self, tmp_path):
        """run(output_path=...) must not raise — orchestrator passes it."""
        paths = _make_files(tmp_path, ["a.parquet"])
        etl = CleanFilesETL(name="clean", input_paths=paths)
        result = etl.run(output_path="data/processed/.clean_done")
        assert isinstance(result, pd.DataFrame)


# ---------------------------------------------------------------------------
# missing_ok behavior
# ---------------------------------------------------------------------------


class TestMissingOk:
    def test_missing_file_skipped_when_missing_ok_true(self, tmp_path):
        non_existent = str(tmp_path / "ghost.parquet")
        etl = CleanFilesETL(name="clean", input_paths=[non_existent], missing_ok=True)

        result = etl.run()  # must not raise

        assert isinstance(result, pd.DataFrame)

    def test_missing_file_raises_when_missing_ok_false(self, tmp_path):
        non_existent = str(tmp_path / "ghost.parquet")
        etl = CleanFilesETL(name="clean", input_paths=[non_existent], missing_ok=False)

        with pytest.raises(ETLError, match="file not found"):
            etl.run()

    def test_existing_file_deleted_with_missing_ok_false(self, tmp_path):
        paths = _make_files(tmp_path, ["real.parquet"])
        etl = CleanFilesETL(name="clean", input_paths=paths, missing_ok=False)

        etl.run()

        assert not Path(paths[0]).exists()

    def test_mixed_existing_and_missing_with_missing_ok_true(self, tmp_path):
        existing = _make_files(tmp_path, ["keep.parquet"])
        non_existent = str(tmp_path / "ghost.parquet")
        etl = CleanFilesETL(name="clean", input_paths=existing + [non_existent], missing_ok=True)

        result = etl.run()

        assert not Path(existing[0]).exists()
        assert isinstance(result, pd.DataFrame)


# ---------------------------------------------------------------------------
# Abstract method stubs
# ---------------------------------------------------------------------------


class TestAbstractStubs:
    def test_extract_raises_not_implemented(self):
        etl = CleanFilesETL(name="clean")
        with pytest.raises(NotImplementedError):
            etl.extract()

    def test_transform_raises_not_implemented(self):
        etl = CleanFilesETL(name="clean")
        with pytest.raises(NotImplementedError):
            etl.transform(pd.DataFrame())

    def test_load_raises_not_implemented(self):
        etl = CleanFilesETL(name="clean")
        with pytest.raises(NotImplementedError):
            etl.load(pd.DataFrame(), "out.parquet")


# ---------------------------------------------------------------------------
# Orchestrator integration — @ref resolution and glob
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    """Verify that the orchestrator resolves @refs and globs before passing
    input_paths to CleanFilesETL — the class itself only sees resolved paths."""

    def _clean_config(self, tmp_path, input_spec, depends_on=None):
        return {
            "enabled": True,
            "input": input_spec,
            "output": str(tmp_path / ".done"),
            "custom_class": "energizados.etl.pipeline.CleanFilesETL",
            "depends_on": depends_on or [],
        }

    def test_ref_resolves_to_producer_output(self, tmp_path):
        """@producer reference must resolve to the producer's output path."""
        producer_output = str(tmp_path / "intermediate.parquet")

        configs = {
            "producer": {
                "enabled": True,
                "input": [],
                "output": producer_output,
                "custom_class": "energizados.etl.pipeline.CleanFilesETL",
                "depends_on": [],
            },
            "clean": self._clean_config(tmp_path, ["@producer"], ["producer"]),
        }

        paths = ETLOrchestrator(configs).resolve_input_paths("clean")

        assert paths == [producer_output]

    def test_multiple_refs_resolve_to_all_outputs(self, tmp_path):
        """Multiple @refs must each resolve to the corresponding ETL output."""
        out_a = str(tmp_path / "a.parquet")
        out_b = str(tmp_path / "b.parquet")

        configs = {
            "a": {
                "enabled": True,
                "input": [],
                "output": out_a,
                "custom_class": "energizados.etl.pipeline.CleanFilesETL",
                "depends_on": [],
            },
            "b": {
                "enabled": True,
                "input": [],
                "output": out_b,
                "custom_class": "energizados.etl.pipeline.CleanFilesETL",
                "depends_on": [],
            },
            "clean": self._clean_config(tmp_path, ["@a", "@b"], ["a", "b"]),
        }

        paths = ETLOrchestrator(configs).resolve_input_paths("clean")

        assert paths == [out_a, out_b]

    def test_empty_input_resolves_to_empty_list(self, tmp_path):
        """input: [] must resolve to an empty list without raising."""
        configs = {"clean": self._clean_config(tmp_path, [])}

        paths = ETLOrchestrator(configs).resolve_input_paths("clean")

        assert paths == []

    def test_glob_resolves_to_matched_files(self, tmp_path):
        """Glob patterns in input must expand to matching file paths."""
        for name in ["tmp_a.parquet", "tmp_b.parquet", "keep.parquet"]:
            (tmp_path / name).write_text("", encoding="utf-8")

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            configs = {"clean": self._clean_config(tmp_path, ["tmp_*.parquet"])}
            paths = ETLOrchestrator(configs).resolve_input_paths("clean")
        finally:
            os.chdir(original)

        assert sorted(paths) == ["tmp_a.parquet", "tmp_b.parquet"]
        assert "keep.parquet" not in paths

    def test_ref_to_disabled_etl_is_skipped(self, tmp_path):
        """@ref to a disabled ETL must be silently skipped."""
        configs = {
            "disabled_etl": {
                "enabled": False,
                "input": [],
                "output": str(tmp_path / "disabled_output.parquet"),
                "custom_class": "energizados.etl.pipeline.CleanFilesETL",
                "depends_on": [],
            },
            "clean": self._clean_config(tmp_path, ["@disabled_etl"]),
        }

        paths = ETLOrchestrator(configs).resolve_input_paths("clean")

        assert paths == []


# ---------------------------------------------------------------------------
# Module-level sanity
# ---------------------------------------------------------------------------


def test_clean_files_etl_exported_from_pipeline():
    import energizados.etl.pipeline as m

    assert hasattr(m, "CleanFilesETL"), "CleanFilesETL must be importable from etl.pipeline"
