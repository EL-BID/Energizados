"""Tests for declarative row filtering in SourceETL."""

import json
import logging

import pandas as pd
import pytest

from energizados.core.exceptions import ETLError
from energizados.core.utils.columns_filter import apply_columns_filter
from energizados.etl.pipeline import SourceETL


def _write_parquet(tmp_path, name, data):
    path = tmp_path / name
    pd.DataFrame(data).to_parquet(path, index=False)
    return path


class TestColumnsFilterStrictMode:
    def test_default_mode_preserves_warn_and_skip_behavior(self, caplog):
        data = pd.DataFrame({"value": [1, 2]})

        with caplog.at_level(logging.WARNING):
            filtered, removed = apply_columns_filter(data, {"missing": 1})

        pd.testing.assert_frame_equal(filtered, data)
        assert removed == 0
        assert "column 'missing' not found, skipping" in caplog.text

    @pytest.mark.parametrize(
        ("columns_filter", "match"),
        [
            ({"missing": 1}, "column 'missing' not found"),
            ({"value": {"~": 1}}, "unknown operator '~'"),
            ({"_expr": "value >"}, "invalid expression"),
        ],
    )
    def test_strict_mode_raises_on_invalid_runtime_filters(self, columns_filter, match):
        data = pd.DataFrame({"value": [1, 2]})

        with pytest.raises(ValueError, match=match):
            apply_columns_filter(data, columns_filter, strict=True)


class TestSourceETLFilter:
    def test_concat_filter_supports_shared_grammar(self, tmp_path):
        source = _write_parquet(
            tmp_path,
            "consumos.parquet",
            {
                "id": [1, 2, 3, 4],
                "zona": ["NORTE", "SUL", "NORTE", "OESTE"],
                "consumo": [10, 12, 30, 5],
                "tipo": ["Servicio A", "Servicio B", "Servicio C", "Servicio D"],
            },
        )
        output = tmp_path / "filtered.parquet"
        etl = SourceETL(
            name="consumos",
            input_paths=[str(source)],
            output_path=str(output),
            filter={
                "zona": ["NORTE", "SUL"],
                "consumo": {">": 0, "<=": 15},
                "tipo": {"like": "servicio"},
                "_expr": "id != 2",
            },
        )

        result = etl.run()

        assert result["id"].tolist() == [1]
        pd.testing.assert_frame_equal(pd.read_parquet(output), result)

    def test_global_filter_runs_before_custom_transform(self, tmp_path):
        source = _write_parquet(
            tmp_path,
            "raw.parquet",
            {"id": [1, 2], "raw_value": [0, 10]},
        )

        def rename_column(data):
            return data.rename(columns={"raw_value": "renamed_value"})

        etl = SourceETL(
            name="transform_order",
            input_paths=[str(source)],
            output_path=str(tmp_path / "out.parquet"),
            filter={"raw_value": {">": 0}},
            transform_fn=rename_column,
        )

        result = etl.run()

        assert result.to_dict("list") == {"id": [2], "renamed_value": [10]}

    def test_merge_filter_runs_after_merge(self, tmp_path):
        clients = _write_parquet(
            tmp_path,
            "clients.parquet",
            {"id": [1, 2], "zona": ["NORTE", "SUL"]},
        )
        consumption = _write_parquet(
            tmp_path,
            "consumption.parquet",
            {"id": [1, 2], "consumo": [100, 200]},
        )
        etl = SourceETL(
            name="merged",
            input_paths=[str(clients), str(consumption)],
            output_path=str(tmp_path / "merged.parquet"),
            mode="merge",
            merge_config={"how": "inner", "on": "id"},
            filter={"zona": "NORTE", "consumo": {">": 50}},
        )

        result = etl.run()

        assert result["id"].tolist() == [1]
        assert list(result.columns) == ["id", "zona", "consumo"]

    def test_global_filter_empty_result_writes_zero_row_output(self, tmp_path, caplog):
        source = _write_parquet(tmp_path, "raw.parquet", {"id": [1], "value": [0]})
        output = tmp_path / "empty.parquet"
        etl = SourceETL(
            name="empty_filter",
            input_paths=[str(source)],
            output_path=str(output),
            filter={"value": {">": 10}},
        )

        with caplog.at_level(logging.WARNING):
            result = etl.run()

        assert result.empty
        assert output.exists()
        written = pd.read_parquet(output)
        assert written.empty
        assert list(written.columns) == ["id", "value"]
        assert "empty_filter" in caplog.text

    @pytest.mark.parametrize(
        ("filter_config", "match"),
        [
            ([], "filter must be a mapping"),
            ({"_expr": 123}, "_expr must be a string"),
            ({"value": {"~": 1}}, "unknown operator '~'"),
        ],
    )
    def test_invalid_filter_structure_fails_at_construction(self, filter_config, match):
        with pytest.raises(ValueError, match=match):
            SourceETL(name="invalid", input_paths=["unused.parquet"], filter=filter_config)

    def test_missing_column_raises_etl_error_and_does_not_write(self, tmp_path):
        source = _write_parquet(tmp_path, "raw.parquet", {"id": [1]})
        output = tmp_path / "out.parquet"
        etl = SourceETL(
            name="strict_source",
            input_paths=[str(source)],
            output_path=str(output),
            filter={"missing": 1},
        )

        with pytest.raises(ETLError, match="strict_source.*ETL-level filter.*missing"):
            etl.run()

        assert not output.exists()

    def test_incremental_filter_preserves_watermark_and_filtered_counts(self, tmp_path):
        source = _write_parquet(
            tmp_path,
            "incremental.parquet",
            {
                "fecha": pd.to_datetime(["2024-01-01", "2024-01-03"]),
                "id": [1, 2],
                "consumo": [0, 10],
            },
        )
        output = tmp_path / "processed"
        state_file = tmp_path / "state.json"
        etl = SourceETL(
            name="incremental_filter",
            input_paths=[str(source)],
            output_path=str(output),
            mode="incremental",
            incremental_key="fecha",
            state_file=str(state_file),
            stream_result=True,
            filter={"consumo": {">": 0}},
        )

        result = etl.run()

        assert result.to_dict("list") == {"file": ["incremental.parquet"], "rows": [1]}
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert "2024-01-03" in state["last_processed_value"]
        written = pd.read_parquet(output / "partition=2024-01" / "data.parquet")
        assert written["id"].tolist() == [2]

    def test_incremental_filter_error_leaves_state_unwritten(self, tmp_path):
        source = _write_parquet(
            tmp_path,
            "incremental.parquet",
            {"fecha": pd.to_datetime(["2024-01-01"]), "id": [1]},
        )
        output = tmp_path / "processed"
        state_file = tmp_path / "state.json"
        etl = SourceETL(
            name="incremental_strict",
            input_paths=[str(source)],
            output_path=str(output),
            mode="incremental",
            incremental_key="fecha",
            state_file=str(state_file),
            filter={"missing": 1},
        )

        with pytest.raises(ETLError, match="incremental_strict.*ETL-level filter.*missing"):
            etl.run()

        assert not state_file.exists()
        assert not output.exists()
