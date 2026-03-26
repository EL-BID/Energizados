"""
Custom ETL for {{project_name}}.

This module extends SourceETL to implement specific processing logic
for this project.

You can override the extract(), transform() and load() methods as needed.
"""

import pandas as pd

from energizados.etl.pipeline import SourceETL
from energizados.preprocessing import fill_empty_values_cycle, fill_empty_values_str


class CustomETL(SourceETL):
    """
    Custom ETL for {{project_name}}.

    Inherits from SourceETL which already implements:
    - Reading multiple files (csv, parquet, xlsx)
    - Concat mode (default) to vertically concatenate files
    - Merge mode to horizontally join files

    Override only the methods you need to customize.
    """

    def __init__(
            self,
            name: str,
            input_paths: list = None,
            output_path: str = None,
            mode: str = "concat",
            merge_config: dict = None,
            **kwargs,
    ):
        """
        Initialize the ETL.

        Args:
            name: Name of the ETL
            input_paths: List of input file paths
            output_path: Output path for transformed data
            mode: Processing mode ('concat' or 'merge'). Default: 'concat'
            merge_config: Configuration for merge if mode='merge'
                Ex: {'how': 'left', 'on': 'customer_id'}
            **kwargs: Additional parameters from configuration
        """
        super().__init__(
            name=name,
            input_paths=input_paths or [],
            output_path=output_path,
            mode=mode,
            merge_config=merge_config,
            **kwargs,
        )

    # Example: Override extract() if you need custom logic
    # def extract(self) -> pd.DataFrame:
    #     """Extract data with custom logic."""
    #     # Call parent method to use standard logic
    #     df = super().extract()
    #
    #     # Or implement your own logic
    #     # dfs = [pd.read_csv(f) for f in self.input_paths]
    #     # df = pd.concat(dfs, axis=0)
    #
    #     return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform and clean the data.

        Edit this method to implement your transformation logic.

        Args:
            df: Raw DataFrame

        Returns:
            pd.DataFrame: Cleaned DataFrame
        """
        # TODO: Implement your transformation logic

        # Fill empty values for consuming vars
        df = fill_empty_values_cycle(df, cant_ciclos_validos=12, suffix="_anterior")

        # Fill columns with 'sin_dato'
        cols_fillna_sindatos = ['zona', 'actividad', 'tipo_tarifa', 'nivel_tension']
        df = fill_empty_values_str(df, cols=cols_fillna_sindatos, str_value='sin_dato')

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Save the transformed data.

        By default uses the parent method which saves in parquet format.
        Override if you need a different format or schema validation.

        Args:
            df: Transformed DataFrame
            path: Output path
        """
        # Example: Validate schema before saving
        # validator = SchemaValidator(
        #     required_columns=['customer_id', 'date', 'consumption'],
        #     categorical_columns=['activity', 'zone'],
        #     numeric_columns=['consumption', 'billing'],
        # )
        # validator.validate_and_raise(df)

        # Use parent method which supports csv, parquet, xlsx
        super().load(df, path)

# YAML CONFIG USAGE EXAMPLE
# ================================
#
# 1. Concatenate multiple files (default mode):
#
#    my_etl:
#      enabled: true
#      description: "Concatenates data from multiple CSV files"
#      input:
#        - "data/raw/file1.csv"
#        - "data/raw/file2.csv"
#        - "data/raw/file3.csv"
#      output: "data/processed/concatenated.parquet"
#      custom_class: "{{package}}.data.custom_etl.CustomETL"
#      params:
#        mode: "concat"
#
# 2. Merge multiple files:
#
#    merge_etl:
#      enabled: true
#      description: "Merges consumption with customers"
#      input:
#        - "data/processed/consumption.parquet"
#        - "data/processed/customers.parquet"
#      output: "data/processed/merged.parquet"
#      custom_class: "{{package}}.data.custom_etl.CustomETL"
#      params:
#        mode: "merge"
#        merge_config:
#          how: "left"
#          on: "customer_id"
#
# 3. With custom transformation:
#
#    transform_etl:
#      enabled: true
#      description: "Processes data with custom cleaning"
#      input:
#        - "data/raw/data.csv"
#      output: "data/processed/clean.parquet"
#      custom_class: "{{package}}.data.custom_etl.CustomETL"
#      params:
#        mode: "concat"
