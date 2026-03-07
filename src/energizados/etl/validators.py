"""
Schema Validators for ETL.

Provides validators to verify that data complies
with the expected schema after the ETL process.
"""

from typing import List, Optional

import pandas as pd


class SchemaValidator:
    """
    Schema validator for DataFrames.

    Verifies that the DataFrame has the expected columns and
    correct data types.

    Args:
        required_columns: List of required columns
        categorical_columns: List of columns that should be categorical
        numeric_columns: List of columns that should be numeric
        allow_missing_columns: If True, allows missing columns
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
        Validates that the DataFrame complies with the schema.

        Args:
            df: DataFrame to validate

        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []

        # Check required columns
        missing_columns = set(self.required_columns) - set(df.columns)
        if missing_columns and not self.allow_missing_columns:
            errors.append(f"Missing columns: {missing_columns}")

        # Check categorical data types
        for col in self.categorical_columns:
            if col in df.columns:
                if not pd.api.types.is_string_dtype(df[col]) and not isinstance(df[col].dtype, pd.CategoricalDtype):
                    errors.append(f"Column '{col}' must be categorical (string or category)")

        # Check numeric data types
        for col in self.numeric_columns:
            if col in df.columns:
                if not pd.api.types.is_numeric_dtype(df[col]):
                    errors.append(f"Column '{col}' must be numeric")

        return len(errors) == 0, errors

    def validate_and_raise(self, df: pd.DataFrame) -> None:
        """
        Validates and raises an exception if there are errors.

        Args:
            df: DataFrame to validate

        Raises:
            ValueError: If validation fails
        """
        is_valid, errors = self.validate(df)
        if not is_valid:
            raise ValueError(f"Schema validation failed: {errors}")
