"""
Unit tests for SourceETL.

Tests for the SourceETL class that supports mode concat and merge.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from energizados.core.exceptions import ETLError
from energizados.etl.pipeline import SourceETL


class TestSourceETLInit:
    """Tests for SourceETL initialization."""

    def test_init_with_default_mode(self):
        """Verify that the default mode is 'concat'."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
        )
        assert etl.mode == "concat"

    def test_init_with_concat_mode(self):
        """Verify initialization with mode='concat'."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            mode="concat",
        )
        assert etl.mode == "concat"

    def test_init_with_merge_mode_and_config(self):
        """Verify initialization with mode='merge' and merge_config."""
        config = {"how": "left", "on": "id"}
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv", "file2.csv"],
            mode="merge",
            merge_config=config,
        )
        assert etl.mode == "merge"
        assert etl.merge_config == config

    def test_init_with_invalid_mode(self):
        """Verify that invalid mode raises error."""
        with pytest.raises(ValueError, match="Mode must be 'concat', 'merge', or 'incremental'"):
            SourceETL(
                name="test",
                input_paths=["file1.csv"],
                mode="invalid",
            )

    def test_init_merge_without_config_raises_error(self):
        """Verify that mode='merge' without merge_config raises error."""
        with pytest.raises(ValueError, match="mode='merge' requires merge_config"):
            SourceETL(
                name="test",
                input_paths=["file1.csv", "file2.csv"],
                mode="merge",
            )

    def test_init_case_insensitive_mode(self):
        """Verify that mode is case-insensitive."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            mode="CONCAT",
        )
        assert etl.mode == "concat"

    def test_init_with_key_column(self):
        """Verify initialization with custom key_column."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            key_column="custom_id",
        )
        assert etl.key_column == "custom_id"


class TestSourceETLExtract:
    """Tests for the extract method."""

    @pytest.fixture
    def temp_dir_with_csv_files(self):
        """Create a temporary directory with CSV files for testing.

        Yields:
            Path: Path to temporary directory with test CSV files.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            df1 = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
            df2 = pd.DataFrame({"id": [3, 4], "value": [30, 40]})

            file1 = tmpdir_path / "file1.csv"
            file2 = tmpdir_path / "file2.csv"

            df1.to_csv(file1, index=False)
            df2.to_csv(file2, index=False)

            yield tmpdir_path

    @pytest.fixture
    def temp_dir_with_parquet_files(self):
        """Create a temporary directory with parquet files for testing.

        Yields:
            Path: Path to temporary directory with test parquet files.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            df1 = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
            df2 = pd.DataFrame({"id": [3, 4], "value": [30, 40]})

            file1 = tmpdir_path / "file1.parquet"
            file2 = tmpdir_path / "file2.parquet"

            df1.to_parquet(file1, index=False)
            df2.to_parquet(file2, index=False)

            yield tmpdir_path

    def test_extract_single_file_concat_mode(self, temp_dir_with_csv_files):
        """Verify extract with a single file in concat mode."""
        file1 = temp_dir_with_csv_files / "file1.csv"

        etl = SourceETL(
            name="test",
            input_paths=[str(file1)],
            mode="concat",
        )

        result = etl.extract()

        expected = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
        pd.testing.assert_frame_equal(result, expected)

    def test_extract_multiple_files_concat_mode(self, temp_dir_with_csv_files):
        """Verify extract with multiple files in concat mode."""
        file1 = temp_dir_with_csv_files / "file1.csv"
        file2 = temp_dir_with_csv_files / "file2.csv"

        etl = SourceETL(
            name="test",
            input_paths=[str(file1), str(file2)],
            mode="concat",
        )

        result = etl.extract()

        expected = pd.DataFrame({"id": [1, 2, 3, 4], "value": [10, 20, 30, 40]})
        pd.testing.assert_frame_equal(result, expected)

    def test_extract_parquet_files(self, temp_dir_with_parquet_files):
        """Verify extract with parquet files."""
        file1 = temp_dir_with_parquet_files / "file1.parquet"

        etl = SourceETL(
            name="test",
            input_paths=[str(file1)],
            mode="concat",
        )

        result = etl.extract()

        expected = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
        pd.testing.assert_frame_equal(result, expected)

    def test_extract_empty_input_paths_raises_error(self):
        """Verify that extract raises error with empty input_paths."""
        etl = SourceETL(
            name="test",
            input_paths=[],
            mode="concat",
        )

        with pytest.raises(ETLError, match="input_paths is empty"):
            etl.extract()

    def test_extract_nonexistent_file_raises_error(self):
        """Verify that extract raises error with nonexistent file."""
        etl = SourceETL(
            name="test",
            input_paths=["nonexistent.csv"],
            mode="concat",
        )

        with pytest.raises(ETLError, match="File not found"):
            etl.extract()

    def test_extract_unsupported_format_raises_error(self):
        """Verify that extract raises error with unsupported format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            unsupported_file = tmpdir_path / "file.txt"
            unsupported_file.write_text("data", encoding="utf-8")

            etl = SourceETL(
                name="test",
                input_paths=[str(unsupported_file)],
                mode="concat",
            )

            with pytest.raises(ETLError, match="Unsupported format"):
                etl.extract()


class TestSourceETLMergeDataframes:
    """Tests for the _merge_dataframes method."""

    def test_merge_with_single_dataframe(self):
        """Verify merge with a single dataframe."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            mode="merge",
            merge_config={"how": "left", "on": "id"},
        )

        df = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
        result = etl._merge_dataframes([df])

        pd.testing.assert_frame_equal(result, df)

    def test_merge_with_empty_list_raises_error(self):
        """Verify that _merge_dataframes raises error with empty list."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            mode="merge",
            merge_config={"how": "left", "on": "id"},
        )

        with pytest.raises(ETLError, match="No dataframes to merge"):
            etl._merge_dataframes([])

    def test_merge_two_dataframes_left(self):
        """Verify left merge of two dataframes."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv", "file2.csv"],
            mode="merge",
            merge_config={"how": "left", "on": "id"},
        )

        df1 = pd.DataFrame({"id": [1, 2, 3], "value1": ["a", "b", "c"]})
        df2 = pd.DataFrame({"id": [1, 2], "value2": ["x", "y"]})

        result = etl._merge_dataframes([df1, df2])

        expected = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "value1": ["a", "b", "c"],
                "value2": ["x", "y", None],
            }
        )
        pd.testing.assert_frame_equal(result, expected)

    def test_merge_two_dataframes_inner(self):
        """Verify inner merge of two dataframes."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv", "file2.csv"],
            mode="merge",
            merge_config={"how": "inner", "on": "id"},
        )

        df1 = pd.DataFrame({"id": [1, 2, 3], "value1": ["a", "b", "c"]})
        df2 = pd.DataFrame({"id": [1, 2], "value2": ["x", "y"]})

        result = etl._merge_dataframes([df1, df2])

        expected = pd.DataFrame(
            {
                "id": [1, 2],
                "value1": ["a", "b"],
                "value2": ["x", "y"],
            }
        )
        pd.testing.assert_frame_equal(result, expected)

    def test_merge_three_dataframes_sequential(self):
        """Verify sequential merge of three dataframes."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv", "file2.csv", "file3.csv"],
            mode="merge",
            merge_config={"how": "left", "on": "id"},
        )

        df1 = pd.DataFrame({"id": [1, 2, 3], "value1": ["a", "b", "c"]})
        df2 = pd.DataFrame({"id": [1, 2], "value2": ["x", "y"]})
        df3 = pd.DataFrame({"id": [1, 3], "value3": ["p", "q"]})

        result = etl._merge_dataframes([df1, df2, df3])

        # df1 + df2: id 1 (value1=a, value2=x), id 2 (value1=b, value2=y), id 3 (value1=c, value2=None)
        # result + df3: id 1 (value1=a, value2=x, value3=p), id 2 (value1=b, value2=y, value3=None),
        #                id 3 (value1=c, value2=None, value3=q)
        expected = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "value1": ["a", "b", "c"],
                "value2": ["x", "y", None],
                "value3": ["p", None, "q"],
            }
        )
        pd.testing.assert_frame_equal(result, expected)

    def test_merge_uses_key_column_by_default(self):
        """Verify that merge uses key_column by default when 'on' is not specified."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv", "file2.csv"],
            mode="merge",
            merge_config={"how": "left"},  # Without 'on'
            key_column="custom_id",
        )

        df1 = pd.DataFrame({"custom_id": [1, 2], "value1": ["a", "b"]})
        df2 = pd.DataFrame({"custom_id": [1], "value2": ["x"]})

        result = etl._merge_dataframes([df1, df2])

        expected = pd.DataFrame(
            {
                "custom_id": [1, 2],
                "value1": ["a", "b"],
                "value2": ["x", None],
            }
        )
        pd.testing.assert_frame_equal(result, expected)

    def test_merge_with_left_on_right_on(self):
        """Verify merge with different left_on and right_on."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv", "file2.csv"],
            mode="merge",
            merge_config={"how": "left", "left_on": "id1", "right_on": "id2"},
        )

        df1 = pd.DataFrame({"id1": [1, 2], "value1": ["a", "b"]})
        df2 = pd.DataFrame({"id2": [1, 3], "value2": ["x", "z"]})

        result = etl._merge_dataframes([df1, df2])

        expected = pd.DataFrame(
            {
                "id1": [1, 2],
                "value1": ["a", "b"],
                "id2": [1, None],
                "value2": ["x", None],
            }
        )
        pd.testing.assert_frame_equal(result, expected)


class TestSourceETLExtractWithMerge:
    """Tests for extract in merge mode with real files."""

    @pytest.fixture
    def temp_dir_with_merge_files(self):
        """Create a temporary directory with files for merge.

        Yields:
            Path: Path to temporary directory with test merge files.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            df1 = pd.DataFrame(
                {
                    "id_cliente": [1, 2, 3],
                    "consumo": [100, 200, 300],
                }
            )
            df2 = pd.DataFrame(
                {
                    "id_cliente": [1, 2],
                    "zona": ["Norte", "Sur"],
                }
            )

            file1 = tmpdir_path / "consumos.parquet"
            file2 = tmpdir_path / "clientes.parquet"

            df1.to_parquet(file1, index=False)
            df2.to_parquet(file2, index=False)

            yield tmpdir_path

    def test_extract_merge_mode(self, temp_dir_with_merge_files):
        """Verify extract in merge mode."""
        file1 = temp_dir_with_merge_files / "consumos.parquet"
        file2 = temp_dir_with_merge_files / "clientes.parquet"

        etl = SourceETL(
            name="test",
            input_paths=[str(file1), str(file2)],
            mode="merge",
            merge_config={"how": "left", "on": "id_cliente"},
        )

        result = etl.extract()

        expected = pd.DataFrame(
            {
                "id_cliente": [1, 2, 3],
                "consumo": [100, 200, 300],
                "zona": ["Norte", "Sur", None],
            }
        )
        pd.testing.assert_frame_equal(result, expected)


class TestSourceETLTransform:
    """Tests for the transform method."""

    def test_transform_drops_empty_rows(self):
        """Verify that transform removes completely empty rows."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
        )

        df = pd.DataFrame(
            {
                "id": [1, None, 3],
                "value": [10, None, None],
            }
        )

        result = etl.transform(df)

        expected = pd.DataFrame(
            {
                "id": [1.0, 3.0],
                "value": [10.0, None],
            },
            index=[0, 2],
        )
        pd.testing.assert_frame_equal(result, expected)

    def test_transform_returns_copy(self):
        """Verify that transform returns a copy of the dataframe."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
        )

        df = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
        result = etl.transform(df)

        # Modifying the result should not affect the original
        result.iloc[0, 0] = 999
        assert df.iloc[0, 0] == 1


class TestSourceETLLoad:
    """Tests for the load method."""

    def test_load_parquet(self):
        """Verify load in parquet format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            output_file = tmpdir_path / "output.parquet"

            etl = SourceETL(
                name="test",
                input_paths=["file1.csv"],
            )

            df = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
            etl.load(df, str(output_file))

            assert output_file.exists()
            result = pd.read_parquet(output_file)
            pd.testing.assert_frame_equal(result, df)

    def test_load_csv(self):
        """Verify load in CSV format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            output_file = tmpdir_path / "output.csv"

            etl = SourceETL(
                name="test",
                input_paths=["file1.csv"],
            )

            df = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
            etl.load(df, str(output_file))

            assert output_file.exists()
            result = pd.read_csv(output_file)
            pd.testing.assert_frame_equal(result, df)

    def test_load_creates_parent_directories(self):
        """Verify that load creates parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            output_file = tmpdir_path / "nested" / "dir" / "output.parquet"

            etl = SourceETL(
                name="test",
                input_paths=["file1.csv"],
            )

            df = pd.DataFrame({"id": [1], "value": [10]})
            etl.load(df, str(output_file))

            assert output_file.exists()

    def test_load_without_extension_defaults_to_parquet(self):
        """Verify that load saves as parquet if there's no extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            output_file = tmpdir_path / "output"  # Without extension

            etl = SourceETL(
                name="test",
                input_paths=["file1.csv"],
            )

            df = pd.DataFrame({"id": [1], "value": [10]})
            etl.load(df, str(output_file))

            # Should create .parquet file
            expected_file = tmpdir_path / "output.parquet"
            assert expected_file.exists()


class TestSourceETLRun:
    """Integration tests for the run method."""

    @pytest.fixture
    def temp_dir_for_run(self):
        """Create a temporary directory for run tests.

        Yields:
            Path: Path to temporary directory with test input file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create input file
            df = pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})
            input_file = tmpdir_path / "input.csv"
            df.to_csv(input_file, index=False)

            yield tmpdir_path

    def test_run_concat_mode(self, temp_dir_for_run):
        """Verify complete run in concat mode."""
        input_file = temp_dir_for_run / "input.csv"
        output_file = temp_dir_for_run / "output.parquet"

        etl = SourceETL(
            name="test",
            input_paths=[str(input_file)],
            mode="concat",
        )

        result = etl.run(str(output_file))

        assert output_file.exists()
        assert len(result) == 3
        pd.testing.assert_frame_equal(
            result,
            pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]}),
        )


class TestIncrementalKeyFiltering:
    """Tests for _filter_by_incremental_key."""

    def _make_etl(
        self, tmp_path, incremental_key="fecha", last_processed=None, incremental_format=None
    ):
        return SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key=incremental_key,
            last_processed=last_processed,
            incremental_format=incremental_format,
        )

    def test_no_prior_state_returns_all_records(self, tmp_path):
        etl = self._make_etl(
            tmp_path,
        )
        df = pd.DataFrame(
            {"fecha": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]), "v": [1, 2, 3]}
        )
        result = etl._filter_by_incremental_key(df)
        assert len(result) == 3

    def test_filters_records_older_than_last_processed(self, tmp_path):
        etl = self._make_etl(tmp_path, last_processed="2024-01-31")
        df = pd.DataFrame(
            {"fecha": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]), "v": [1, 2, 3]}
        )
        result = etl._filter_by_incremental_key(df)
        assert list(result["v"]) == [2, 3]

    def test_updates_state_with_max_value(self, tmp_path):
        etl = self._make_etl(tmp_path, last_processed="2024-01-31")
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-02-01", "2024-03-15"]), "v": [1, 2]})
        etl._filter_by_incremental_key(df)
        assert "last_processed_value" in etl._state
        assert "2024-03-15" in etl._state["last_processed_value"]

    def test_state_takes_priority_over_constructor_param(self, tmp_path):
        etl = self._make_etl(tmp_path, last_processed="2024-01-01")
        etl._state["last_processed_value"] = "2024-02-28"
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-02-01", "2024-03-01"]), "v": [1, 2]})
        result = etl._filter_by_incremental_key(df)
        # 2024-02-01 is NOT > 2024-02-28, so only March is kept
        assert list(result["v"]) == [2]

    def test_raises_when_incremental_key_not_in_dataframe(self, tmp_path):
        etl = self._make_etl(tmp_path, incremental_key="missing_col")
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-01"]), "v": [1]})
        with pytest.raises(ETLError, match="incremental_key 'missing_col' not found"):
            etl._filter_by_incremental_key(df)

    def test_coerces_string_column_to_datetime(self, tmp_path):
        etl = self._make_etl(tmp_path, last_processed="2024-01-31")
        df = pd.DataFrame({"fecha": ["2024-01-01", "2024-02-01"], "v": [1, 2]})
        result = etl._filter_by_incremental_key(df)
        assert list(result["v"]) == [2]

    def test_empty_df_after_filter_does_not_update_state(self, tmp_path):
        etl = self._make_etl(tmp_path, last_processed="2025-01-01")
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-01"]), "v": [1]})
        result = etl._filter_by_incremental_key(df)
        assert result.empty
        assert "last_processed_value" not in etl._state

    def test_uses_incremental_format_for_parsing(self, tmp_path):
        """When incremental_format is set, parsing uses that format explicitly."""
        etl = self._make_etl(tmp_path, last_processed="2024-01-31", incremental_format="%d/%m/%Y")
        df = pd.DataFrame({"fecha": ["15/01/2024", "28/02/2024"], "v": [1, 2]})
        result = etl._filter_by_incremental_key(df)
        assert list(result["v"]) == [2]

    def test_incremental_format_auto_parse_fallback(self, tmp_path):
        """When incremental_format is None, auto-parse still works."""
        etl = self._make_etl(tmp_path, last_processed="2024-01-31", incremental_format=None)
        df = pd.DataFrame({"fecha": ["2024-01-01", "2024-02-01"], "v": [1, 2]})
        result = etl._filter_by_incremental_key(df)
        assert list(result["v"]) == [2]


class TestIncrementalInit:
    """Tests for incremental mode constructor changes (tasks 1.1-1.4)."""

    def test_incremental_format_stored(self, tmp_path):
        """incremental_format param is stored on the instance."""
        etl = SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
            incremental_format="%d/%m/%Y",
        )
        assert etl.incremental_format == "%d/%m/%Y"

    def test_incremental_format_default_is_none(self, tmp_path):
        """incremental_format defaults to None (auto-parse)."""
        etl = SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
        )
        assert etl.incremental_format is None

    def test_incremental_partition_default(self, tmp_path):
        """incremental_partition defaults to '%Y-%m'."""
        etl = SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
        )
        assert etl.incremental_partition == "%Y-%m"

    def test_incremental_partition_custom(self, tmp_path):
        """incremental_partition can be overridden."""
        etl = SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
            incremental_partition="%Y",
        )
        assert etl.incremental_partition == "%Y"

    def test_no_auto_default_partition_by(self, tmp_path):
        """partition_by is NOT auto-set to ['year', 'month'] in incremental mode."""
        etl = SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
        )
        assert etl.partition_by is None

    def test_partition_by_deprecation_warning_in_incremental(self, tmp_path, caplog):
        """partition_by in incremental mode triggers deprecation WARNING and is ignored."""
        import logging

        with caplog.at_level(logging.WARNING, logger="energizados.etl.pipeline"):
            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=["dummy.csv"],
                output_path=str(tmp_path / "out"),
                incremental_key="fecha",
                partition_by=["year", "month"],
            )
        assert etl.partition_by is None
        assert "deprecated" in caplog.text.lower() or "deprecation" in caplog.text.lower()

    def test_partition_by_works_in_concat_mode(self):
        """partition_by is NOT deprecated for concat/merge modes."""
        etl = SourceETL(
            name="test",
            input_paths=["file.csv"],
            partition_by=["year", "month"],
        )
        assert etl.partition_by == ["year", "month"]


class TestAddPartitionColumn:
    """Tests for _add_partition_column method (task 2.2)."""

    def _make_etl(self, tmp_path, incremental_partition="%Y-%m"):
        return SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
            incremental_partition=incremental_partition,
        )

    def test_default_format_creates_partition_column(self, tmp_path):
        etl = self._make_etl(
            tmp_path,
        )
        df = pd.DataFrame(
            {"fecha": pd.to_datetime(["2024-01-15", "2024-02-10", "2024-12-01"]), "v": [1, 2, 3]}
        )
        result = etl._add_partition_column(df)
        assert "partition" in result.columns
        assert list(result["partition"]) == ["2024-01", "2024-02", "2024-12"]

    def test_year_only_format(self, tmp_path):
        etl = self._make_etl(tmp_path, incremental_partition="%Y")
        df = pd.DataFrame({"fecha": pd.to_datetime(["2023-06-15", "2024-01-01"]), "v": [1, 2]})
        result = etl._add_partition_column(df)
        assert list(result["partition"]) == ["2023", "2024"]

    def test_does_not_modify_original_df(self, tmp_path):
        etl = self._make_etl(
            tmp_path,
        )
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-15"]), "v": [1]})
        result = etl._add_partition_column(df)
        assert "partition" not in df.columns
        assert "partition" in result.columns


class TestLoadIncremental:
    """Tests for _load_incremental method (task 2.3)."""

    def _make_etl(self, tmp_path, incremental_partition="%Y-%m"):
        return SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
            incremental_partition=incremental_partition,
        )

    def test_writes_partition_directories(self, tmp_path):
        """_load_incremental writes partition=<val>/data.parquet."""
        etl = self._make_etl(
            tmp_path,
        )
        df = pd.DataFrame(
            {
                "fecha": pd.to_datetime(["2024-01-15", "2024-02-10"]),
                "v": [10, 20],
                "partition": ["2024-01", "2024-02"],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            etl._load_incremental(df, tmpdir)
            jan_file = Path(tmpdir) / "partition=2024-01" / "data.parquet"
            feb_file = Path(tmpdir) / "partition=2024-02" / "data.parquet"
            assert jan_file.exists()
            assert feb_file.exists()

    def test_partition_column_dropped_from_saved_files(self, tmp_path):
        """The 'partition' column is NOT in the saved parquet files."""
        etl = self._make_etl(
            tmp_path,
        )
        df = pd.DataFrame(
            {
                "fecha": pd.to_datetime(["2024-01-15"]),
                "v": [10],
                "partition": ["2024-01"],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            etl._load_incremental(df, tmpdir)
            jan_file = Path(tmpdir) / "partition=2024-01" / "data.parquet"
            saved = pd.read_parquet(jan_file)
            assert "partition" not in saved.columns
            assert list(saved["v"]) == [10]

    def test_appends_to_existing_partition(self, tmp_path):
        """Writing to an existing partition appends rows."""
        etl = self._make_etl(
            tmp_path,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            # First write
            df1 = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-15"]),
                    "v": [10],
                    "partition": ["2024-01"],
                }
            )
            etl._load_incremental(df1, tmpdir)

            # Second write (same partition)
            df2 = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-20"]),
                    "v": [20],
                    "partition": ["2024-01"],
                }
            )
            etl._load_incremental(df2, tmpdir)

            jan_file = Path(tmpdir) / "partition=2024-01" / "data.parquet"
            saved = pd.read_parquet(jan_file)
            assert len(saved) == 2
            assert set(saved["v"]) == {10, 20}


class TestReadSingleFile:
    """Tests for _read_single_file helper (task 2.4)."""

    def _make_etl(self, tmp_path):
        return SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
        )

    def test_reads_csv(self, tmp_path):
        etl = self._make_etl(
            tmp_path,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "data.csv"
            pd.DataFrame({"a": [1, 2]}).to_csv(csv_path, index=False)
            result = etl._read_single_file(str(csv_path))
            assert len(result) == 2

    def test_reads_parquet(self, tmp_path):
        etl = self._make_etl(
            tmp_path,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            pq_path = Path(tmpdir) / "data.parquet"
            pd.DataFrame({"a": [3, 4]}).to_parquet(pq_path, index=False)
            result = etl._read_single_file(str(pq_path))
            assert len(result) == 2
            assert list(result["a"]) == [3, 4]

    def test_raises_on_missing_file(self, tmp_path):
        etl = self._make_etl(
            tmp_path,
        )
        with pytest.raises(ETLError, match="Error reading"):
            etl._read_single_file("/nonexistent/file.csv")

    def test_raises_on_unsupported_format(self, tmp_path):
        etl = self._make_etl(
            tmp_path,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = Path(tmpdir) / "data.json"
            bad_path.write_text("{}", encoding="utf-8")
            with pytest.raises(ETLError, match="Unsupported format"):
                etl._read_single_file(str(bad_path))


class TestSourceETLExtractPartitionedDirectory:
    """Tests for extract reading Hive-style partitioned directories."""

    @pytest.fixture
    def temp_dir_with_partitions(self):
        """Create a temporary directory with Hive-style partitioned parquet files.

        Yields:
            Path: Path to the base directory containing partitions.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            base = tmpdir_path / "partitioned"
            base.mkdir()

            # year=2024/month=01/
            p1 = base / "year=2024" / "month=01"
            p1.mkdir(parents=True)
            df1 = pd.DataFrame({"id": [1, 2], "valor": [10, 20]})
            df1.to_parquet(p1 / "data.parquet", index=False)

            # year=2024/month=02/
            p2 = base / "year=2024" / "month=02"
            p2.mkdir(parents=True)
            df2 = pd.DataFrame({"id": [3], "valor": [30]})
            df2.to_parquet(p2 / "data.parquet", index=False)

            yield tmpdir_path

    def test_extract_reads_partitioned_directory(self, temp_dir_with_partitions):
        """Verify concat mode reads a Hive-partitioned directory including partition columns."""
        partition_dir = temp_dir_with_partitions / "partitioned"

        etl = SourceETL(
            name="test",
            input_paths=[str(partition_dir)],
            mode="concat",
        )

        result = etl.extract()

        assert len(result) == 3
        assert "year" in result.columns
        assert "month" in result.columns
        assert set(result["year"].astype(str)) == {"2024"}
        # pyarrow parses directory values as integers, so "01" -> 1
        assert set(result["month"].astype(int)) == {1, 2}

    def test_extract_mixed_files_and_directories(self, temp_dir_with_partitions):
        """Verify concat mode works with a mix of file and directory inputs."""
        partition_dir = temp_dir_with_partitions / "partitioned"

        # Add a standalone CSV file
        extra_file = temp_dir_with_partitions / "extra.csv"
        pd.DataFrame({"id": [99], "valor": [990]}).to_csv(extra_file, index=False)

        etl = SourceETL(
            name="test",
            input_paths=[str(partition_dir), str(extra_file)],
            mode="concat",
        )

        result = etl.extract()

        # 3 from partitions + 1 from CSV
        assert len(result) == 4

    def test_extract_partitioned_via_etl_reference(self, temp_dir_with_partitions):
        """Verify reading a partitioned directory output from another ETL via @ref."""
        partition_dir = temp_dir_with_partitions / "partitioned"

        etl = SourceETL(
            name="test",
            input_paths=[str(partition_dir)],
            mode="concat",
        )

        result = etl.extract()

        # Partition columns should be present in the result
        assert "year" in result.columns
        assert "month" in result.columns
        assert set(result["year"].astype(str)) == {"2024"}
        # pyarrow parses directory values as integers
        assert set(result["month"].astype(int)) == {1, 2}


class TestIncrementalEndToEnd:
    """Integration test: incremental ETL with incremental_partition and partition=YYYY-MM output."""

    def test_full_incremental_run_creates_partition_output(self):
        """Run produces partition=YYYY-MM/data.parquet structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            df = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-15", "2024-01-20", "2024-02-10"]),
                    "valor": [10, 20, 30],
                }
            )
            raw_file = tmpdir_path / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                incremental_key="fecha",
                state_file=str(state_file),
            )
            etl.run(str(output_dir))

            # Expect two partitions: partition=2024-01 and partition=2024-02
            jan = output_dir / "partition=2024-01" / "data.parquet"
            feb = output_dir / "partition=2024-02" / "data.parquet"
            assert jan.exists(), "January partition missing"
            assert feb.exists(), "February partition missing"

            jan_df = pd.read_parquet(jan)
            assert len(jan_df) == 2
            assert "partition" not in jan_df.columns

            feb_df = pd.read_parquet(feb)
            assert len(feb_df) == 1
            assert "partition" not in feb_df.columns

    def test_second_run_skips_already_processed_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            raw_file = tmpdir_path / "raw.parquet"
            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            def make_etl():
                return SourceETL(
                    name="test",
                    mode="incremental",
                    input_paths=[str(raw_file)],
                    output_path=str(output_dir),
                    incremental_key="fecha",
                    reprocess=True,
                    state_file=str(state_file),
                )

            # First run: January data
            df1 = pd.DataFrame(
                {"fecha": pd.to_datetime(["2024-01-10", "2024-01-20"]), "valor": [1, 2]}
            )
            df1.to_parquet(raw_file, index=False)
            etl1 = make_etl()
            result1 = etl1.run(str(output_dir))
            assert len(result1) == 2

            # Second run: file now includes Jan + Feb records
            df2 = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-10", "2024-01-20", "2024-02-05"]),
                    "valor": [1, 2, 3],
                }
            )
            df2.to_parquet(raw_file, index=False)
            etl2 = make_etl()
            result2 = etl2.run(str(output_dir))
            # Only the February record is newer than the stored max (2024-01-20)
            assert len(result2) == 1
            assert result2["valor"].iloc[0] == 3

    def test_file_by_file_processing(self):
        """Multiple input files processed independently, state saved once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create two separate input files
            df_a = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-15", "2024-01-20"]),
                    "valor": [10, 20],
                }
            )
            df_b = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-02-05", "2024-02-10"]),
                    "valor": [30, 40],
                }
            )
            file_a = tmpdir_path / "data_a.parquet"
            file_b = tmpdir_path / "data_b.parquet"
            df_a.to_parquet(file_a, index=False)
            df_b.to_parquet(file_b, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=[str(file_a), str(file_b)],
                output_path=str(output_dir),
                incremental_key="fecha",
                state_file=str(state_file),
            )
            result = etl.run(str(output_dir))

            assert len(result) == 4
            jan = output_dir / "partition=2024-01" / "data.parquet"
            feb = output_dir / "partition=2024-02" / "data.parquet"
            assert jan.exists()
            assert feb.exists()

            # State saved once after all files
            assert state_file.exists()
            import json

            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)
            assert "last_processed_value" in state

    def test_incremental_format_end_to_end(self):
        """End-to-end with incremental_format for non-standard date parsing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            df = pd.DataFrame(
                {
                    "fecha": ["15/01/2024", "28/02/2024"],
                    "valor": [10, 20],
                }
            )
            raw_file = tmpdir_path / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                incremental_key="fecha",
                incremental_format="%d/%m/%Y",
                state_file=str(state_file),
            )
            result = etl.run(str(output_dir))

            assert len(result) == 2
            jan = output_dir / "partition=2024-01" / "data.parquet"
            feb = output_dir / "partition=2024-02" / "data.parquet"
            assert jan.exists()
            assert feb.exists()

    def test_failing_file_does_not_corrupt_state(self):
        """A corrupted file causes the ETL to abort; state is NOT updated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Good file A: January data
            df_a = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-10", "2024-01-20"]),
                    "valor": [10, 20],
                }
            )
            file_a = tmpdir_path / "good_a.parquet"
            df_a.to_parquet(file_a, index=False)

            # BAD file: .parquet extension but garbage content
            bad_file = tmpdir_path / "corrupted.parquet"
            bad_file.write_text("THIS IS NOT A PARQUET FILE", encoding="utf-8")

            # Good file C: February data
            df_c = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-02-05", "2024-02-15"]),
                    "valor": [30, 40],
                }
            )
            file_c = tmpdir_path / "good_c.parquet"
            df_c.to_parquet(file_c, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=[str(file_a), str(bad_file), str(file_c)],
                output_path=str(output_dir),
                incremental_key="fecha",
                state_file=str(state_file),
            )

            # ETL must raise; state file must NOT be updated
            with pytest.raises(ETLError, match="Could not open"):
                etl.run(str(output_dir))

            # State must not exist (written only after _on_load_success, which never runs on error)
            assert not state_file.exists(), "State must not be written on error"

    def test_file_with_only_old_records_is_skipped(self):
        """A file whose records are all older than last_processed is marked processed but skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # File with only old records (January)
            df_old = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-10", "2024-01-20"]),
                    "valor": [1, 2],
                }
            )
            old_file = tmpdir_path / "old_data.parquet"
            df_old.to_parquet(old_file, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            # Set last_processed to AFTER all records in the file
            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=[str(old_file)],
                output_path=str(output_dir),
                incremental_key="fecha",
                last_processed="2024-03-01",
                state_file=str(state_file),
            )
            result = etl.run(str(output_dir))

            # Result is empty — no new records
            assert result.empty

            # No partition directories created
            assert not (output_dir / "partition=2024-01").exists()
            assert not output_dir.exists() or not any(output_dir.iterdir())

            # But the file IS marked as processed in state
            import json

            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)
            assert str(old_file) in state.get("processed_files", [])

    def test_partition_string_comparison_with_existing_state(self):
        """Pre-existing state filters out old partitions; only newer ones are written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Pre-populate state file simulating a previous run ending at 2024-06-30
            state_file = tmpdir_path / "state.json"
            import json

            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"last_processed_value": "2024-06-30"}, f)

            # New data spans June, July, August
            df = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(
                        [
                            "2024-06-15",  # OLD — should be filtered out
                            "2024-07-10",  # NEW
                            "2024-07-20",  # NEW
                            "2024-08-05",  # NEW
                        ]
                    ),
                    "valor": [1, 2, 3, 4],
                }
            )
            raw_file = tmpdir_path / "new_data.parquet"
            df.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"

            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                incremental_key="fecha",
                state_file=str(state_file),
            )
            result = etl.run(str(output_dir))

            # Only 3 records: July and August (June was filtered)
            assert len(result) == 3
            assert set(result["valor"]) == {2, 3, 4}

            # July and August partitions exist
            jul = output_dir / "partition=2024-07" / "data.parquet"
            aug = output_dir / "partition=2024-08" / "data.parquet"
            assert jul.exists(), "July partition should exist"
            assert aug.exists(), "August partition should exist"

            # June partition must NOT exist
            jun = output_dir / "partition=2024-06" / "data.parquet"
            assert not jun.exists(), "June partition should NOT exist (records are old)"

            # Verify partition contents
            jul_df = pd.read_parquet(jul)
            assert len(jul_df) == 2
            assert set(jul_df["valor"]) == {2, 3}

            aug_df = pd.read_parquet(aug)
            assert len(aug_df) == 1
            assert aug_df["valor"].iloc[0] == 4

            # State updated to max date of new records
            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)
            assert "2024-08-05" in state["last_processed_value"]

    def test_transform_removes_incremental_key_column_single_partition(self):
        """When transform removes incremental_key but data is one partition, it works.

        Common case: one file per period, transform pivots long-to-wide.
        Regression test: previously _load_incremental would fail because the
        incremental_key column was removed by a pivot transform.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Single-period file: all rows have same periodo (one month of data)
            df = pd.DataFrame(
                {
                    "cliente": ["A", "B", "C"],
                    "periodo": pd.to_datetime(["2024-01-01"] * 3),
                    "consumo": [100, 200, 300],
                }
            )
            raw_file = tmpdir_path / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            class PivotETL(SourceETL):
                """ETL that drops the periodo column (simulating a pivot)."""

                def transform(self, df: pd.DataFrame) -> pd.DataFrame:
                    return df.drop(columns=["periodo"])

            etl = PivotETL(
                name="test_pivot",
                mode="incremental",
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                incremental_key="periodo",
                incremental_partition="%Y-%m",
                state_file=str(state_file),
            )

            # This should NOT raise ETLError about missing incremental_key
            result = etl.run(str(output_dir))
            assert len(result) == 3

            # Partition 2024-01 should exist
            jan = output_dir / "partition=2024-01" / "data.parquet"
            assert jan.exists(), "January partition should exist"

            # Saved data should not contain internal columns
            saved = pd.read_parquet(jan)
            assert "_partition" not in saved.columns
            assert "partition" not in saved.columns
            assert len(saved) == 3

            # _partition internal column should NOT be in the final result
            assert "_partition" not in result.columns

    def test_transform_removes_incremental_key_multiple_partitions(self):
        """When transform removes incremental_key and data spans multiple periods.

        Silently assigning all rows to the latest partition would corrupt data
        from earlier periods, so an ETLError is raised instead — the user must
        either preserve the row count or return a '_partition' column explicitly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            df = pd.DataFrame(
                {
                    "cliente": ["A", "A", "B", "B"],
                    "periodo": pd.to_datetime(
                        ["2024-01-01", "2024-02-01", "2024-01-01", "2024-02-01"]
                    ),
                    "consumo": [100, 110, 200, 210],
                }
            )
            raw_file = tmpdir_path / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            class PivotETL(SourceETL):
                """ETL that pivots and removes the periodo column."""

                def transform(self, df: pd.DataFrame) -> pd.DataFrame:
                    pivoted = df.pivot_table(
                        index="cliente",
                        columns="periodo",
                        values="consumo",
                        aggfunc="first",
                    ).reset_index()
                    pivoted.columns.name = None
                    pivoted.columns = [
                        str(c.strftime("%Y-%m") if hasattr(c, "strftime") else c)
                        for c in pivoted.columns
                    ]
                    return pivoted

            etl = PivotETL(
                name="test_pivot",
                mode="incremental",
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                incremental_key="periodo",
                incremental_partition="%Y-%m",
                state_file=str(state_file),
            )

            from energizados.core.exceptions import ETLError

            with pytest.raises(ETLError, match="Cannot safely assign partition values"):
                etl.run(str(output_dir))


class TestWrittenPartitions:
    """Tests for _written_partitions tracking (task 4.2)."""

    def _make_etl(self, tmp_path, **kwargs):
        defaults = dict(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
            incremental_partition="%Y-%m",
        )
        defaults.update(kwargs)
        return SourceETL(**defaults)

    def test_written_partitions_populated_after_load_incremental(self, tmp_path):
        """_written_partitions is populated after _load_incremental()."""
        etl = self._make_etl(
            tmp_path,
        )
        df = pd.DataFrame(
            {
                "fecha": pd.to_datetime(["2024-01-15"]),
                "v": [10],
                "_partition": ["2024-01"],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            etl._load_incremental(df, tmpdir)
            assert etl._written_partitions == ["2024-01"]

    def test_multiple_partitions_from_single_file(self, tmp_path):
        """A single file that spans multiple partitions populates all of them."""
        etl = self._make_etl(
            tmp_path,
        )
        df = pd.DataFrame(
            {
                "fecha": pd.to_datetime(["2024-01-15", "2024-02-10", "2024-03-05"]),
                "v": [10, 20, 30],
                "_partition": ["2024-01", "2024-02", "2024-03"],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            etl._load_incremental(df, tmpdir)
            assert etl._written_partitions == ["2024-01", "2024-02", "2024-03"]

    def test_reset_at_start_of_run(self, tmp_path):
        """_written_partitions is reset to [] at the start of run()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            raw_file = tmpdir_path / "raw.parquet"
            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            df = pd.DataFrame({"fecha": pd.to_datetime(["2024-03-01"]), "v": [99]})
            df.to_parquet(raw_file, index=False)

            etl = self._make_etl(
                tmp_path,
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                state_file=str(state_file),
            )
            # Pre-populate with stale data
            etl._written_partitions = ["old-stale"]
            etl.run(str(output_dir))

            # After run, only the new partition should be present
            assert "old-stale" not in etl._written_partitions
            assert etl._written_partitions == ["2024-03"]

    def test_accumulates_across_multiple_load_calls(self, tmp_path):
        """_written_partitions accumulates across successive _load_incremental calls."""
        etl = self._make_etl(
            tmp_path,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            df1 = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-15"]),
                    "v": [10],
                    "_partition": ["2024-01"],
                }
            )
            etl._load_incremental(df1, tmpdir)
            assert etl._written_partitions == ["2024-01"]

            df2 = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-02-10"]),
                    "v": [20],
                    "_partition": ["2024-02"],
                }
            )
            etl._load_incremental(df2, tmpdir)
            assert etl._written_partitions == ["2024-01", "2024-02"]


class TestAutoInferredStateFile:
    """Tests for auto-inferred state_file path (unified state change)."""

    def test_auto_inferred_state_file_path(self):
        """When state_file is None and mode=incremental, auto-infer as
        {output_path}/.etl_state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "processed"
            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=["dummy.csv"],
                output_path=str(output_dir),
                incremental_key="fecha",
            )
            assert etl.state_file == str(output_dir / ".etl_state.json")

    def test_explicit_state_file_preserved(self, tmp_path):
        """When state_file is explicitly provided, it is used unchanged."""
        etl = SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
            state_file=".cache/custom_state.json",
        )
        assert etl.state_file == ".cache/custom_state.json"

    def test_auto_inferred_loads_state_unconditionally(self):
        """When mode=incremental and state_file auto-inferred, _load_state()
        is called (even without explicit state_file)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "processed"
            output_dir.mkdir()
            state_file = output_dir / ".etl_state.json"

            # Pre-create state file
            import json

            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"processed_files": ["a.csv"], "last_processed_value": "2024-01-01"}, f)

            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=["dummy.csv"],
                output_path=str(output_dir),
                incremental_key="fecha",
            )
            # State should be loaded from auto-inferred file
            assert etl._state.get("processed_files") == ["a.csv"]


class TestUnifiedState:
    """Tests for unified state file (manifest fields inside state file)."""

    def _run_incremental_etl(self, tmpdir):
        """Helper: create and run an incremental ETL that writes partitions."""
        df = pd.DataFrame(
            {
                "fecha": pd.to_datetime(["2024-01-15", "2024-02-10"]),
                "valor": [10, 20],
            }
        )
        raw_file = Path(tmpdir) / "raw.parquet"
        df.to_parquet(raw_file, index=False)

        output_dir = Path(tmpdir) / "processed"
        state_file = Path(tmpdir) / "state.json"

        etl = SourceETL(
            name="test",
            mode="incremental",
            input_paths=[str(raw_file)],
            output_path=str(output_dir),
            incremental_key="fecha",
            state_file=str(state_file),
        )
        etl.run(str(output_dir))
        return etl, output_dir, state_file

    def test_unified_state_contains_manifest_fields_after_run(self):
        """After incremental run, state file contains all 5 keys:
        processed_files, last_processed_value, run_id, new_partitions, all_partitions."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            etl, output_dir, state_file = self._run_incremental_etl(tmpdir)

            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)

            assert "processed_files" in state
            assert "last_processed_value" in state
            assert "run_id" in state
            assert "new_partitions" in state
            assert "all_partitions" in state
            # run_id should be ISO 8601 with T
            assert "T" in state["run_id"]

    def test_no_separate_manifest_json_created(self):
        """After incremental run, no manifest.json exists in the state dir or output dir.
        All manifest fields are stored inside the unified state file (.etl_state.json),
        and the orchestrator reads them directly from there."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etl, output_dir, state_file = self._run_incremental_etl(tmpdir)

            # Check state dir — no separate manifest.json (fields are in state file)
            assert not (state_file.parent / "manifest.json").exists()
            # Check output dir
            assert not (output_dir / "manifest.json").exists()

    def test_atomic_write_no_tmp_left(self):
        """After successful run, no .tmp files remain in the state dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            etl, output_dir, state_file = self._run_incremental_etl(tmpdir)

            tmp_files = list(state_file.parent.glob("*.tmp"))
            assert tmp_files == [], f"No .tmp files should remain, found: {tmp_files}"

    def test_empty_run_does_not_rewrite_state(self):
        """When no new records are found, state file is NOT rewritten."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # First run: write some data
            df1 = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-15"]), "valor": [10]})
            raw_file = tmpdir_path / "raw.parquet"
            df1.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            etl1 = SourceETL(
                name="test",
                mode="incremental",
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                incremental_key="fecha",
                state_file=str(state_file),
                reprocess=True,
            )
            etl1.run(str(output_dir))

            # Record state file mtime
            mtime_before = state_file.stat().st_mtime

            # Second run: same data, all records filtered (not new)
            etl2 = SourceETL(
                name="test",
                mode="incremental",
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                incremental_key="fecha",
                state_file=str(state_file),
                reprocess=True,
            )
            result = etl2.run(str(output_dir))
            assert result.empty

            # State file should not have been rewritten
            mtime_after = state_file.stat().st_mtime
            assert mtime_after == mtime_before, "State file should not be rewritten on empty run"


class TestManifestWrite:
    """Tests for manifest fields in unified state file (task 4.1)."""

    def _make_etl(self, tmp_path, **kwargs):
        defaults = dict(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
            incremental_partition="%Y-%m",
        )
        defaults.update(kwargs)
        return SourceETL(**defaults)

    def test_manifest_json_content_after_run(self, tmp_path):
        """Unified state file contains manifest fields after a successful run."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            df = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-15", "2024-02-10"]),
                    "valor": [10, 20],
                }
            )
            raw_file = tmpdir_path / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            etl = self._make_etl(
                tmp_path,
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                state_file=str(state_file),
            )
            etl.run(str(output_dir))

            # Manifest fields are now inside the unified state file
            assert state_file.exists(), "state file must be written"

            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)

            assert "run_id" in state
            # run_id is ISO 8601
            assert "T" in state["run_id"]

            assert "new_partitions" in state
            assert set(state["new_partitions"]) == {"2024-01", "2024-02"}

            assert "all_partitions" in state
            assert set(state["all_partitions"]) == {"2024-01", "2024-02"}

            assert "last_processed_value" in state
            assert "2024-02-10" in state["last_processed_value"]

            assert "processed_files" in state

    def test_manifest_not_written_on_empty_run(self, tmp_path):
        """Unified state file is NOT rewritten when no new data is processed (empty run)."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Pre-create state with last_processed far in the future
            state_file = tmpdir_path / "state.json"
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"last_processed_value": "2099-12-31"}, f)

            # All data is older than last_processed
            df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-15"]), "valor": [10]})
            raw_file = tmpdir_path / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"

            etl = self._make_etl(
                tmp_path,
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                state_file=str(state_file),
            )
            etl.run(str(output_dir))

            # State file should not have been rewritten with manifest fields
            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)
            assert "run_id" not in state, "state must NOT contain manifest fields on empty run"
            assert "new_partitions" not in state

    def test_manifest_path_derived_from_state_file_dir(self, tmp_path):
        """Manifest fields are in the unified state file (same path as state_file)."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            nested_dir = tmpdir_path / "cache" / "etl_states"
            nested_dir.mkdir(parents=True)
            state_file = nested_dir / "state.json"

            df = pd.DataFrame({"fecha": pd.to_datetime(["2024-05-01"]), "valor": [42]})
            raw_file = tmpdir_path / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"

            etl = self._make_etl(
                tmp_path,
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                state_file=str(state_file),
            )
            etl.run(str(output_dir))

            # Manifest fields are inside the unified state file
            assert state_file.exists(), "state file must be written"

            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)

            assert state["new_partitions"] == ["2024-05"]

    def test_manifest_atomic_write_no_tmp_left(self, tmp_path):
        """After successful write, no .tmp file is left behind."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-15"]), "valor": [10]})
            raw_file = tmpdir_path / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            etl = self._make_etl(
                tmp_path,
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                state_file=str(state_file),
            )
            etl.run(str(output_dir))

            # No .tmp file should remain
            tmp_files = list(tmpdir_path.glob("*.tmp"))
            assert tmp_files == [], f"No .tmp files should remain, found: {tmp_files}"

    def test_no_manifest_when_state_file_is_none(self):
        """When state_file is None, no state file is created at the output path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "processed"
            output_dir.mkdir()

            df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-15"]), "valor": [10]})
            raw_file = Path(tmpdir) / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            # Explicitly pass state_file=None to prevent auto-inference
            etl = SourceETL(
                name="test",
                mode="incremental",
                input_paths=[str(raw_file)],
                output_path=str(output_dir),
                incremental_key="fecha",
                state_file=None,
            )
            # Override auto-inference by re-setting to None
            etl.state_file = None
            etl.run(str(output_dir))

            # No .etl_state.json in the output directory
            assert not (
                output_dir / ".etl_state.json"
            ).exists(), "no state file should be created when state_file is None"


class TestDirectoryInputIncremental:
    """Tests for directory input handling in incremental mode (task 4.3)."""

    def _make_etl(self, tmp_path, **kwargs):
        defaults = dict(
            name="test",
            mode="incremental",
            input_paths=["dummy"],
            output_path=str(tmp_path / "out"),
            incremental_key="fecha",
            incremental_partition="%Y-%m",
        )
        defaults.update(kwargs)
        return SourceETL(**defaults)

    def test_read_single_file_reads_parquet_directory(self, tmp_path):
        """_read_single_file() reads a Hive-style partitioned parquet directory."""
        etl = self._make_etl(
            tmp_path,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "partitioned"
            base.mkdir()

            # Create Hive-style partitions
            p1 = base / "partition=2024-01"
            p1.mkdir()
            pd.DataFrame({"fecha": pd.to_datetime(["2024-01-15"]), "v": [10]}).to_parquet(
                p1 / "data.parquet", index=False
            )

            p2 = base / "partition=2024-02"
            p2.mkdir()
            pd.DataFrame({"fecha": pd.to_datetime(["2024-02-10"]), "v": [20]}).to_parquet(
                p2 / "data.parquet", index=False
            )

            result = etl._read_single_file(str(base))
            assert len(result) == 2
            assert set(result["v"]) == {10, 20}

    def test_extract_incremental_processes_directory_input(self, tmp_path):
        """_extract_incremental() accepts a directory path (from @ref)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a directory with a parquet file (simulating @ref output)
            input_dir = tmpdir_path / "upstream_output"
            input_dir.mkdir()
            df = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-03-15", "2024-04-01"]),
                    "valor": [100, 200],
                }
            )
            df.to_parquet(input_dir / "data.parquet", index=False)

            etl = self._make_etl(
                tmp_path,
                input_paths=[str(input_dir)],
                output_path=str(tmpdir_path / "processed"),
            )
            result = etl._extract_incremental()

            assert len(result) == 2
            assert set(result["valor"]) == {100, 200}

    def test_run_incremental_with_directory_from_ref(self):
        """Full run() in incremental mode processes a directory input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Upstream writes a partitioned directory
            upstream_dir = tmpdir_path / "upstream"
            upstream_dir.mkdir()
            p1 = upstream_dir / "partition=2024-06"
            p1.mkdir()
            pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-06-01", "2024-06-15"]),
                    "valor": [50, 60],
                }
            ).to_parquet(p1 / "data.parquet", index=False)

            output_dir = tmpdir_path / "processed"
            state_file = tmpdir_path / "state.json"

            etl = SourceETL(
                name="test_downstream",
                mode="incremental",
                input_paths=[str(upstream_dir)],
                output_path=str(output_dir),
                incremental_key="fecha",
                state_file=str(state_file),
            )
            result = etl.run(str(output_dir))

            assert len(result) == 2
            assert set(result["valor"]) == {50, 60}

            # Output partition should be created
            out_part = output_dir / "partition=2024-06" / "data.parquet"
            assert out_part.exists()
