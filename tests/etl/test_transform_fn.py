"""
Unit tests for SourceETL transform_fn feature.

Tests for the custom transform function support in SourceETL.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from energizados.core.exceptions import ETLError
from energizados.core.utils.import_utils import register_allowed_prefix
from energizados.etl.pipeline import SourceETL

# Register tests prefix for test imports
register_allowed_prefix("tests")


def mock_add_column(df: pd.DataFrame) -> pd.DataFrame:
    """Mock transform function that adds a test column.

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with added test_col column
    """
    return df.assign(test_col=1)


def mock_add_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    """Mock transform function that adds a timestamp column.

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with added timestamp column
    """
    return df.assign(timestamp=pd.Timestamp.now())


def invalid_transform(df: pd.DataFrame) -> list:
    """Mock transform function that returns invalid type.

    Args:
        df: Input DataFrame (ignored)

    Returns:
        List instead of DataFrame (invalid)
    """
    return [1, 2, 3]


class TestSourceETLTransformFnInit:
    """Tests for SourceETL initialization with transform_fn."""

    def test_init_with_transform_fn_none(self):
        """Verify that transform_fn=None works (default behavior)."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            transform_fn=None,
        )
        assert etl._transform_fn is None

    def test_init_with_transform_fn_callable(self):
        """Verify that transform_fn can be a callable."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            transform_fn=mock_add_column,
        )
        assert etl._transform_fn is mock_add_column

    def test_init_with_transform_fn_string_valid(self):
        """Verify that transform_fn can be a string path to a function."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            transform_fn="tests.etl.test_transform_fn.mock_add_column",
        )
        assert callable(etl._transform_fn)

    def test_init_with_transform_fn_string_invalid(self):
        """Verify that invalid transform_fn string raises ConfigurationError."""
        from energizados.core.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            SourceETL(
                name="test",
                input_paths=["file1.csv"],
                transform_fn="nonexistent.module.fn",
            )

    def test_init_with_transform_fn_invalid_type(self):
        """Verify that invalid transform_fn type raises ValueError."""
        with pytest.raises(ValueError, match="transform_fn must be a string path or callable"):
            SourceETL(
                name="test",
                input_paths=["file1.csv"],
                transform_fn=123,  # Invalid type
            )

    def test_init_with_transform_fn_string_not_in_allowlist(self):
        """Verify that transform_fn outside allowlist raises ConfigurationError."""
        from energizados.core.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError, match="not in the allowed module prefixes"):
            SourceETL(
                name="test",
                input_paths=["file1.csv"],
                transform_fn="os.system",  # Not in allowlist
            )


class TestSourceETLTransformFnTransform:
    """Tests for transform method with transform_fn."""

    def test_transform_with_callable_adds_column(self):
        """Verify that callable transform_fn adds column."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            transform_fn=mock_add_column,
        )

        df = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
        result = etl.transform(df)

        assert "test_col" in result.columns
        assert (result["test_col"] == 1).all()
        assert len(result) == 2

    def test_transform_with_string_path_adds_column(self):
        """Verify that string path transform_fn adds column."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            transform_fn="tests.etl.test_transform_fn.mock_add_column",
        )

        df = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
        result = etl.transform(df)

        assert "test_col" in result.columns
        assert (result["test_col"] == 1).all()

    def test_transform_with_none_preserves_behavior(self):
        """Verify that transform_fn=None preserves current behavior."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            transform_fn=None,
        )

        df = pd.DataFrame(
            {
                "id": [1, None, 3],
                "value": [10, None, None],
            }
        )
        result = etl.transform(df)

        # Should only drop empty rows
        expected = pd.DataFrame(
            {
                "id": [1.0, 3.0],
                "value": [10.0, None],
            },
            index=[0, 2],
        )
        pd.testing.assert_frame_equal(result, expected)

    def test_transform_invalid_return_type_raises_error(self):
        """Verify that transform_fn returning invalid type raises ETLError."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            transform_fn=invalid_transform,
        )

        df = pd.DataFrame({"id": [1, 2], "value": [10, 20]})

        with pytest.raises(ETLError, match="transform_fn must return pd.DataFrame"):
            etl.transform(df)

    def test_transform_applied_after_dropna(self):
        """Verify that transform_fn is applied after dropna."""
        etl = SourceETL(
            name="test",
            input_paths=["file1.csv"],
            transform_fn=mock_add_column,
        )

        df = pd.DataFrame(
            {
                "id": [1, None, 3],
                "value": [10, None, None],
            }
        )
        result = etl.transform(df)

        # Empty row should be dropped, then transform_fn applied
        assert len(result) == 2  # Row with all NaN dropped
        assert "test_col" in result.columns
        assert list(result["id"]) == [1.0, 3.0]


class TestSourceETLTransformFnIntegration:
    """Integration tests for transform_fn feature."""

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

    def test_run_with_transform_fn(self, temp_dir_for_run):
        """Verify complete run with transform_fn."""
        input_file = temp_dir_for_run / "input.csv"
        output_file = temp_dir_for_run / "output.parquet"

        etl = SourceETL(
            name="test",
            input_paths=[str(input_file)],
            mode="concat",
            transform_fn=mock_add_column,
        )

        result = etl.run(str(output_file))

        assert output_file.exists()
        assert len(result) == 3
        assert "test_col" in result.columns
        assert (result["test_col"] == 1).all()

    def test_run_without_transform_fn_baseline(self, temp_dir_for_run):
        """Verify complete run without transform_fn (baseline)."""
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
