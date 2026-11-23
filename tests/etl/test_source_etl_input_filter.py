"""Tests for per-input SourceETL filters and their composition with ETL filters."""

import json
import logging

import pandas as pd
import pytest

from energizados.core.exceptions import ETLError
from energizados.etl.pipeline import SourceETL


def _write_parquet(tmp_path, name, data):
    path = tmp_path / name
    pd.DataFrame(data).to_parquet(path, index=False)
    return path


def _spec(path, filter_config=None):
    return {"path": str(path), "filter": filter_config}


class TestSourceETLInputFilter:
    def test_concat_applies_each_filter_to_its_own_input(self, tmp_path):
        first = _write_parquet(tmp_path, "first.parquet", {"id": [1, 2], "value": [0, 5]})
        second = _write_parquet(tmp_path, "second.parquet", {"id": [3, 4], "value": [6, 20]})
        etl = SourceETL(
            name="dual_concat",
            input_paths=[str(first), str(second)],
            input_specs=[
                _spec(first, {"value": {">": 0}}),
                _spec(second, {"value": {"<": 10}}),
            ],
            output_path=str(tmp_path / "out.parquet"),
            filter={"value": {"<=": 6}},
        )

        result = etl.run()

        assert result["id"].tolist() == [2, 3]

    def test_duplicate_paths_keep_positional_filters(self, tmp_path):
        source = _write_parquet(tmp_path, "raw.parquet", {"id": [1, 2], "value": [-1, 1]})
        etl = SourceETL(
            name="duplicate_paths",
            input_paths=[str(source), str(source)],
            input_specs=[
                _spec(source, {"value": {"<": 0}}),
                _spec(source, {"value": {">": 0}}),
            ],
            output_path=str(tmp_path / "out.parquet"),
        )

        result = etl.run()

        assert result["id"].tolist() == [1, 2]

    def test_merge_filters_inputs_before_join_and_global_after_join(self, tmp_path):
        clients = _write_parquet(
            tmp_path,
            "clients.parquet",
            {"id": [1, 2], "zona": ["NORTE", "NORTE"], "active": [True, False]},
        )
        consumption = _write_parquet(
            tmp_path,
            "consumption.parquet",
            {"id": [1, 2], "consumo": [100, 100]},
        )
        etl = SourceETL(
            name="dual_merge",
            input_paths=[str(clients), str(consumption)],
            input_specs=[
                _spec(clients, {"active": True}),
                _spec(consumption, {"consumo": {">": 50}}),
            ],
            output_path=str(tmp_path / "out.parquet"),
            mode="merge",
            merge_config={"how": "inner", "on": "id"},
            filter={"zona": "NORTE"},
        )

        result = etl.run()

        assert result["id"].tolist() == [1]
        assert result["consumo"].tolist() == [100]

    def test_all_inputs_filtered_empty_writes_zero_row_output(self, tmp_path, caplog):
        source = _write_parquet(tmp_path, "raw.parquet", {"id": [1], "value": [0]})
        output = tmp_path / "empty.parquet"
        etl = SourceETL(
            name="empty_inputs",
            input_paths=[str(source)],
            input_specs=[_spec(source, {"value": {">": 10}})],
            output_path=str(output),
        )

        with caplog.at_level(logging.WARNING):
            result = etl.run()

        assert result.empty
        written = pd.read_parquet(output)
        assert written.empty
        assert list(written.columns) == ["id", "value"]
        assert "empty_inputs" in caplog.text

    def test_empty_extract_without_filters_keeps_legacy_no_output_behavior(self, tmp_path):
        source = _write_parquet(tmp_path, "raw.parquet", {"id": [], "value": []})
        output = tmp_path / "legacy.parquet"
        etl = SourceETL(
            name="legacy_empty",
            input_paths=[str(source)],
            output_path=str(output),
        )

        result = etl.run()

        assert result.empty
        assert not output.exists()

    def test_input_filter_error_identifies_path_and_leaves_output_unwritten(self, tmp_path):
        source = _write_parquet(tmp_path, "raw.parquet", {"id": [1]})
        output = tmp_path / "out.parquet"
        etl = SourceETL(
            name="strict_input",
            input_paths=[str(source)],
            input_specs=[_spec(source, {"missing": 1})],
            output_path=str(output),
        )

        with pytest.raises(ETLError, match="strict_input.*input filter.*raw.parquet.*missing"):
            etl.run()

        assert not output.exists()

    def test_incremental_both_levels_preserve_watermark_and_counts(self, tmp_path):
        first = _write_parquet(
            tmp_path,
            "first.parquet",
            {
                "fecha": pd.to_datetime(["2024-01-01", "2024-01-03"]),
                "id": [1, 2],
                "consumo": [0, 10],
            },
        )
        second = _write_parquet(
            tmp_path,
            "second.parquet",
            {
                "fecha": pd.to_datetime(["2024-01-04"]),
                "id": [3],
                "consumo": [20],
            },
        )
        output = tmp_path / "processed"
        state_file = tmp_path / "state.json"
        etl = SourceETL(
            name="dual_incremental",
            input_paths=[str(first), str(second)],
            input_specs=[
                _spec(first, {"consumo": {">": 0}}),
                _spec(second, {"consumo": {">": 25}}),
            ],
            output_path=str(output),
            mode="incremental",
            incremental_key="fecha",
            state_file=str(state_file),
            stream_result=True,
            filter={"consumo": {"<": 15}},
        )

        result = etl.run()

        assert result.to_dict("list") == {"file": ["first.parquet"], "rows": [1]}
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert "2024-01-04" in state["last_processed_value"]
        assert str(second) in state["processed_files"]
        written = pd.read_parquet(output / "partition=2024-01" / "data.parquet")
        assert written["id"].tolist() == [2]

    def test_incremental_input_filter_error_leaves_state_unwritten(self, tmp_path):
        source = _write_parquet(
            tmp_path,
            "raw.parquet",
            {"fecha": pd.to_datetime(["2024-01-01"]), "id": [1]},
        )
        state_file = tmp_path / "state.json"
        etl = SourceETL(
            name="incremental_input_strict",
            input_paths=[str(source)],
            input_specs=[_spec(source, {"missing": 1})],
            output_path=str(tmp_path / "processed"),
            mode="incremental",
            incremental_key="fecha",
            state_file=str(state_file),
        )

        with pytest.raises(ETLError, match="incremental_input_strict.*input filter.*missing"):
            etl.run()

        assert not state_file.exists()

    def test_extract_incremental_filters_after_watermark(self, tmp_path):
        """Direct incremental extract: input filter runs after the key cutoff."""
        source = _write_parquet(
            tmp_path,
            "raw.parquet",
            {
                "fecha": pd.to_datetime(["2024-01-01", "2024-01-03"]),
                "id": [1, 2],
                "consumo": [10, 0],
            },
        )
        etl = SourceETL(
            name="direct_incremental",
            input_paths=[str(source)],
            input_specs=[_spec(source, {"consumo": {">": 5}})],
            output_path=str(tmp_path / "processed"),
            mode="incremental",
            incremental_key="fecha",
        )

        result = etl.extract()

        # 2024-01-03 is filtered out by the input filter but its fecha still
        # sets the high-water mark (watermark is computed before any filter).
        assert result["id"].tolist() == [1]
        assert "2024-01-03" in etl._state["last_processed_value"]

    def test_extract_incremental_without_filters_is_unchanged(self, tmp_path):
        source = _write_parquet(
            tmp_path,
            "raw.parquet",
            {
                "fecha": pd.to_datetime(["2024-01-01", "2024-01-02"]),
                "id": [1, 2],
            },
        )
        etl = SourceETL(
            name="legacy_direct",
            input_paths=[str(source)],
            output_path=str(tmp_path / "processed"),
            mode="incremental",
            incremental_key="fecha",
        )

        result = etl.extract()

        assert result["id"].tolist() == [1, 2]

    def test_incremental_second_run_after_watermark_is_noop(self, tmp_path):
        """Filtered-out rows do not hold back the watermark; the next run is a no-op."""
        source = _write_parquet(
            tmp_path,
            "raw.parquet",
            {
                "fecha": pd.to_datetime(["2024-01-01", "2024-01-03"]),
                "id": [1, 2],
                "consumo": [10, 0],
            },
        )
        output = tmp_path / "processed"
        state_file = tmp_path / "state.json"
        etl = SourceETL(
            name="noop_next_run",
            input_paths=[str(source)],
            input_specs=[_spec(source, {"consumo": {">": 5}})],
            output_path=str(output),
            mode="incremental",
            incremental_key="fecha",
            state_file=str(state_file),
        )

        first = etl.run(str(output))
        assert first["id"].tolist() == [1]
        assert (
            "2024-01-03"
            in json.loads(state_file.read_text(encoding="utf-8"))["last_processed_value"]
        )

        second = etl.run(str(output))

        assert second.empty

    def test_failed_filtered_run_leaves_previous_output_untouched(self, tmp_path):
        """A failing filter must not corrupt an already-written output file."""
        source = _write_parquet(tmp_path, "raw.parquet", {"id": [1], "value": [5]})
        output = tmp_path / "out.parquet"
        good = SourceETL(
            name="write_then_fail",
            input_paths=[str(source)],
            output_path=str(output),
        )
        good.run()
        original_bytes = output.read_bytes()

        bad = SourceETL(
            name="write_then_fail",
            input_paths=[str(source)],
            input_specs=[_spec(source, {"missing": 1})],
            output_path=str(output),
        )

        with pytest.raises(ETLError, match="input filter"):
            bad.run()

        assert output.read_bytes() == original_bytes

    def test_merge_side_emptied_by_input_filter_writes_zero_rows(self, tmp_path, caplog):
        """S4: one merge side emptied by its input filter still writes a 0-row output."""
        clients = _write_parquet(
            tmp_path, "clients.parquet", {"id": [1, 2], "zona": ["NORTE", "SUL"]}
        )
        consumption = _write_parquet(
            tmp_path, "consumption.parquet", {"id": [1, 2], "consumo": [100, 200]}
        )
        output = tmp_path / "merged.parquet"
        etl = SourceETL(
            name="merge_side_empty",
            input_paths=[str(clients), str(consumption)],
            input_specs=[
                _spec(clients, {"zona": "INEXISTENTE"}),
                _spec(consumption, None),
            ],
            output_path=str(output),
            mode="merge",
            merge_config={"how": "inner", "on": "id"},
        )

        with caplog.at_level(logging.WARNING):
            result = etl.run()

        assert result.empty
        written = pd.read_parquet(output)
        assert written.empty
        assert list(written.columns) == ["id", "zona", "consumo"]
        assert "merge_side_empty" in caplog.text

    def test_input_specs_must_align_with_input_paths(self, tmp_path):
        source = _write_parquet(tmp_path, "raw.parquet", {"id": [1]})

        with pytest.raises(ValueError, match="same number of entries"):
            SourceETL(name="misaligned", input_paths=[str(source)], input_specs=[])

        with pytest.raises(ValueError, match="does not match input_paths"):
            SourceETL(
                name="wrong_path",
                input_paths=[str(source)],
                input_specs=[{"path": "other.parquet", "filter": None}],
            )
