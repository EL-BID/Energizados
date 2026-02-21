"""
Tests para ETL y procesamiento de datos de {{project_name}}.
"""

import pytest
import pandas as pd
from {{project_name}}.src.data.custom_etl import CustomETL


class TestCustomETL:
    """Tests para la clase CustomETL."""

    def test_etl_initialization(self):
        """Verifica que el ETL se inicialice correctamente."""
        etl = CustomETL(
            input_paths=["data/raw/test.csv"],
            output_path="data/processed/test.parquet"
        )
        assert etl.input_paths == ["data/raw/test.csv"]
        assert etl.output_path == "data/processed/test.parquet"

    def test_extract_raises_not_implemented(self):
        """Verifica que extract() lance NotImplementedError si no está implementado."""
        etl = CustomETL()
        with pytest.raises(NotImplementedError):
            etl.extract()

    def test_transform_raises_not_implemented(self):
        """Verifica que transform() lance NotImplementedError si no está implementado."""
        etl = CustomETL()
        dummy_df = pd.DataFrame({'a': [1, 2, 3]})
        with pytest.raises(NotImplementedError):
            etl.transform(dummy_df)
