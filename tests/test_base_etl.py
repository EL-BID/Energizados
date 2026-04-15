"""
Unit tests for BaseETL.

Tests for the ETL base class that defines the interface
that all custom ETLs must implement.
"""

import pandas as pd
import pytest

from energizados.core.exceptions import ETLError
from energizados.etl.base import BaseETL


class TestBaseETL:
    """Tests for the BaseETL class."""

    def test_base_etl_is_abstract(self):
        """Verify that BaseETL cannot be directly instantiated."""
        with pytest.raises(TypeError):
            BaseETL()

    def test_concrete_etl_must_implement_extract(self):
        """Verify that a concrete ETL must implement extract()."""

        class IncompleteETL(BaseETL):
            def transform(self, df: pd.DataFrame) -> pd.DataFrame:
                return df

            def load(self, df: pd.DataFrame, path: str) -> None:
                pass

        with pytest.raises(TypeError):
            IncompleteETL()

    def test_concrete_etl_must_implement_transform(self):
        """Verify that a concrete ETL must implement transform()."""

        class IncompleteETL(BaseETL):
            def extract(self) -> pd.DataFrame:
                return pd.DataFrame()

            def load(self, df: pd.DataFrame, path: str) -> None:
                pass

        with pytest.raises(TypeError):
            IncompleteETL()

    def test_concrete_etl_must_implement_load(self):
        """Verify that a concrete ETL must implement load()."""

        class IncompleteETL(BaseETL):
            def extract(self) -> pd.DataFrame:
                return pd.DataFrame()

            def transform(self, df: pd.DataFrame) -> pd.DataFrame:
                return df

        with pytest.raises(TypeError):
            IncompleteETL()

    def test_complete_etl_can_be_instantiated(self):
        """Verify that a complete ETL can be instantiated."""

        class CompleteETL(BaseETL):
            def extract(self) -> pd.DataFrame:
                return pd.DataFrame({"a": [1, 2, 3]})

            def transform(self, df: pd.DataFrame) -> pd.DataFrame:
                return df

            def load(self, df: pd.DataFrame, path: str) -> None:
                pass

        # Should not raise exception
        etl = CompleteETL()
        assert etl is not None

    def test_run_method_uses_all_steps(self):
        """Verify that the run() method calls extract, transform, and load."""

        class TestETL(BaseETL):
            def __init__(self):
                self.extract_called = False
                self.transform_called = False
                self.load_called = False

            def extract(self) -> pd.DataFrame:
                self.extract_called = True
                return pd.DataFrame({"a": [1, 2, 3]})

            def transform(self, df: pd.DataFrame) -> pd.DataFrame:
                self.transform_called = True
                return df

            def load(self, df: pd.DataFrame, path: str) -> None:
                self.load_called = True

        etl = TestETL()
        result = etl.run("dummy_path.parquet")

        assert etl.extract_called
        assert etl.transform_called
        assert etl.load_called
        assert result is not None

    def test_run_returns_transformed_dataframe(self):
        """Verify that run() returns the transformed DataFrame."""

        class TestETL(BaseETL):
            def extract(self) -> pd.DataFrame:
                return pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})

            def transform(self, df: pd.DataFrame) -> pd.DataFrame:
                return df * 2

            def load(self, df: pd.DataFrame, path: str) -> None:
                pass

        etl = TestETL()
        result = etl.run("dummy_path.parquet")

        expected = pd.DataFrame({"a": [2, 4, 6], "b": [8, 10, 12]})
        pd.testing.assert_frame_equal(result, expected)

    def test_run_raises_etl_on_error(self):
        """Verify that run() raises ETLError in case of error."""

        class FailingETL(BaseETL):
            def extract(self) -> pd.DataFrame:
                raise ValueError("Extraction error")

            def transform(self, df: pd.DataFrame) -> pd.DataFrame:
                return df

            def load(self, df: pd.DataFrame, path: str) -> None:
                pass

        etl = FailingETL()

        with pytest.raises(ETLError):
            etl.run("dummy_path.parquet")
