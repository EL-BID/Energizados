"""
Schema Validators for ETL.

Proporciona validadores para verificar que los datos cumplan
con el esquema esperado después del proceso ETL.
"""

from typing import List, Optional

import pandas as pd


class SchemaValidator:
    """
    Validador de esquema para DataFrames.

    Verifica que el DataFrame tenga las columnas esperadas y
    los tipos de datos correctos.

    Args:
        required_columns: Lista de columnas requeridas
        categorical_columns: Lista de columnas que deben ser categóricas
        numeric_columns: Lista de columnas que deben ser numéricas
        allow_missing_columns: Si es True, permite columnas faltantes
    """

    def __init__(
        self,
        required_columns: Optional[List[str]] = None,
        categorical_columns: Optional[List[str]] = None,
        numeric_columns: Optional[List[str]] = None,
        allow_missing_columns: bool = False,
    ):
        self.required_columns = required_columns or []
        self.categorical_columns = categorical_columns or []
        self.numeric_columns = numeric_columns or []
        self.allow_missing_columns = allow_missing_columns

    def validate(self, df: pd.DataFrame) -> tuple[bool, List[str]]:
        """
        Valida que el DataFrame cumpla con el esquema.

        Args:
            df: DataFrame a validar

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []

        # Verificar columnas requeridas
        missing_columns = set(self.required_columns) - set(df.columns)
        if missing_columns and not self.allow_missing_columns:
            errors.append(f"Columnas faltantes: {missing_columns}")

        # Verificar tipos de datos categóricos
        for col in self.categorical_columns:
            if col in df.columns:
                if not pd.api.types.is_string_dtype(df[col]) and not pd.api.types.is_categorical_dtype(df[col]):
                    errors.append(f"Columna '{col}' debe ser categórica (string o category)")

        # Verificar tipos de datos numéricos
        for col in self.numeric_columns:
            if col in df.columns:
                if not pd.api.types.is_numeric_dtype(df[col]):
                    errors.append(f"Columna '{col}' debe ser numérica")

        return len(errors) == 0, errors

    def validate_and_raise(self, df: pd.DataFrame) -> None:
        """
        Valida y levanta una excepción si hay errores.

        Args:
            df: DataFrame a validar

        Raises:
            ValueError: Si la validación falla
        """
        is_valid, errors = self.validate(df)
        if not is_valid:
            raise ValueError(f"Validación de esquema falló: {errors}")
