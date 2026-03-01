"""
ETL Base Module.

Defines the abstract BaseETL class that users can inherit
to implement their own custom ETL processes.
"""

from abc import ABC, abstractmethod

import pandas as pd


class BaseETL(ABC):
    """
    Base class for custom ETL.

    Users inherit and implement the abstract methods to define
    their own Extract, Transform, and Load process.

    Example:
        >>> from energizados.etl.base import BaseETL
        >>> class MyETL(BaseETL):
        ...     def __init__(self, source_path: str):
        ...         self.source_path = source_path
        ...     def extract(self):
        ...         return pd.read_csv(self.source_path)
        ...     def transform(self, df):
        ...         return df.dropna()
        ...     def load(self, df, path):
        ...         df.to_parquet(path)
    """

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """
        Extracts data from the source.

        Returns:
            pd.DataFrame: Raw data

        Raises:
            ETLError: If an error occurs during extraction
        """
        pass

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms and cleans the data.

        Args:
            df: Raw DataFrame

        Returns:
            pd.DataFrame: Clean DataFrame with expected schema

        Raises:
            ETLError: If an error occurs during transformation
        """
        pass

    @abstractmethod
    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Saves the transformed data.

        Args:
            df: Transformed DataFrame
            path: Output path

        Raises:
            ETLError: If an error occurs during loading
        """
        pass

    def run(self, output_path: str) -> pd.DataFrame:
        """
        Executes the complete ETL pipeline.

        This method can be overridden to add additional logic.

        Args:
            output_path: Path to save the transformed data

        Returns:
            pd.DataFrame: Transformed DataFrame
        """
        from energizados.core.exceptions import ETLError

        try:
            df = self.extract()
            df = self.transform(df)
            self.load(df, output_path)
            return df
        except Exception as e:
            raise ETLError(f"Error running ETL: {str(e)}")
