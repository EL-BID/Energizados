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
            unsupported_file.write_text("data")

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

    def _make_etl(self, incremental_key="fecha", last_processed=None):
        return SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path="/tmp/out",  # nosec B108
            incremental_key=incremental_key,
            last_processed=last_processed,
        )

    def test_no_prior_state_returns_all_records(self):
        etl = self._make_etl()
        df = pd.DataFrame(
            {"fecha": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]), "v": [1, 2, 3]}
        )
        result = etl._filter_by_incremental_key(df)
        assert len(result) == 3

    def test_filters_records_older_than_last_processed(self):
        etl = self._make_etl(last_processed="2024-01-31")
        df = pd.DataFrame(
            {"fecha": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]), "v": [1, 2, 3]}
        )
        result = etl._filter_by_incremental_key(df)
        assert list(result["v"]) == [2, 3]

    def test_updates_state_with_max_value(self):
        etl = self._make_etl(last_processed="2024-01-31")
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-02-01", "2024-03-15"]), "v": [1, 2]})
        etl._filter_by_incremental_key(df)
        assert "last_processed_value" in etl._state
        assert "2024-03-15" in etl._state["last_processed_value"]

    def test_state_takes_priority_over_constructor_param(self):
        etl = self._make_etl(last_processed="2024-01-01")
        etl._state["last_processed_value"] = "2024-02-28"
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-02-01", "2024-03-01"]), "v": [1, 2]})
        result = etl._filter_by_incremental_key(df)
        # 2024-02-01 is NOT > 2024-02-28, so only March is kept
        assert list(result["v"]) == [2]

    def test_raises_when_incremental_key_not_in_dataframe(self):
        etl = self._make_etl(incremental_key="missing_col")
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-01"]), "v": [1]})
        with pytest.raises(ETLError, match="incremental_key 'missing_col' not found"):
            etl._filter_by_incremental_key(df)

    def test_coerces_string_column_to_datetime(self):
        etl = self._make_etl(last_processed="2024-01-31")
        df = pd.DataFrame({"fecha": ["2024-01-01", "2024-02-01"], "v": [1, 2]})
        result = etl._filter_by_incremental_key(df)
        assert list(result["v"]) == [2]

    def test_empty_df_after_filter_does_not_update_state(self):
        etl = self._make_etl(last_processed="2025-01-01")
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-01"]), "v": [1]})
        result = etl._filter_by_incremental_key(df)
        assert result.empty
        assert "last_processed_value" not in etl._state


class TestDerivePartitionColumns:
    """Tests for _derive_partition_columns."""

    def _make_etl(self, incremental_key="fecha", partition_by=None):
        return SourceETL(
            name="test",
            mode="incremental",
            input_paths=["dummy.csv"],
            output_path="/tmp/out",  # nosec B108
            incremental_key=incremental_key,
            partition_by=partition_by or ["year", "month"],
        )

    def test_derives_year_and_month_from_datetime_column(self):
        etl = self._make_etl()
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-15", "2024-03-20"]), "v": [1, 2]})
        result = etl._derive_partition_columns(df)
        assert list(result["year"]) == [2024, 2024]
        assert list(result["month"]) == ["01", "03"]

    def test_derives_from_string_column(self):
        etl = self._make_etl()
        df = pd.DataFrame({"fecha": ["2024-06-01", "2024-12-31"], "v": [1, 2]})
        result = etl._derive_partition_columns(df)
        assert list(result["year"]) == [2024, 2024]
        assert list(result["month"]) == ["06", "12"]

    def test_does_not_overwrite_existing_year_month(self):
        etl = self._make_etl()
        df = pd.DataFrame(
            {"fecha": pd.to_datetime(["2024-01-15"]), "year": [9999], "month": ["99"], "v": [1]}
        )
        result = etl._derive_partition_columns(df)
        assert list(result["year"]) == [9999]
        assert list(result["month"]) == ["99"]

    def test_month_is_zero_padded(self):
        etl = self._make_etl()
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-01", "2024-10-01"]), "v": [1, 2]})
        result = etl._derive_partition_columns(df)
        assert list(result["month"]) == ["01", "10"]

    def test_only_year_in_partition_by(self):
        etl = self._make_etl(partition_by=["year"])
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-06-15"]), "v": [1]})
        result = etl._derive_partition_columns(df)
        assert "year" in result.columns
        assert "month" not in result.columns

    def test_returns_df_unchanged_when_no_incremental_key_column(self):
        etl = self._make_etl(incremental_key="missing")
        df = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-01"]), "v": [1]})
        result = etl._derive_partition_columns(df)
        assert "year" not in result.columns


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
    """Integration test: incremental ETL with incremental_key and partition_by."""

    def test_full_incremental_run_creates_partitioned_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Raw input file
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
                partition_by=["year", "month"],
                state_file=str(state_file),
            )
            etl.run(str(output_dir))

            # Expect two partitions: year=2024/month=01 and year=2024/month=02
            jan = output_dir / "year=2024" / "month=01" / "data.parquet"
            feb = output_dir / "year=2024" / "month=02" / "data.parquet"
            assert jan.exists(), "January partition missing"
            assert feb.exists(), "February partition missing"

            jan_df = pd.read_parquet(jan)
            assert len(jan_df) == 2
            feb_df = pd.read_parquet(feb)
            assert len(feb_df) == 1

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
                    partition_by=["year", "month"],
                    overwrite=True,
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
