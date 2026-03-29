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
