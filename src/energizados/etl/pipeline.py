"""
Pipeline ETL Module for Multi-Source Data Processing.

This module provides classes to orchestrate multiple source ETLs
and combine their outputs into a final dataset.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from energizados.core.exceptions import ETLError
from energizados.etl.base import BaseETL

logger = logging.getLogger(__name__)


class SourceETL(BaseETL):
    """
    ETL to process one or multiple data sources.

    This class processes data from one or several files and generates processed output.
    Supports two operating modes:

    - **concat**: Concatenates multiple dataframes vertically (default)
    - **merge**: Joins multiple dataframes horizontally using merge_config

    Args:
        name: Name of the source (e.g.: 'consumos', 'inspecciones', 'clientes')
        input_paths: List with paths to raw data files
        output_path: Path to save processed data
        mode: Processing mode ('concat' or 'merge'). Default: 'concat'
        merge_config: Configuration for merge (required if mode='merge')
            Ex: {'how': 'left', 'on': 'id_cliente'}
            Options: how ('left', 'right', 'inner', 'outer'), on (column),
                      left_on, right_on, left_index, right_index
        key_column: Key column used by default in merge_config
        **kwargs: Additional parameters

    Example:
        >>> etl = SourceETL(
        ...     name='consumos',
        ...     mode='concat',
        ...     input_paths=['data/raw/consumos.csv'],
        ...     output_path='data/consumos.parquet',
        ... )
        >>> df = etl.run('data/consumos.parquet')

    Example with merge:
        >>> etl = SourceETL(
        ...     name='merged',
        ...     mode='merge',
        ...     input_paths=['data/consumos.parquet', 'data/clientes.parquet'],
        ...     output_path='data/merged.parquet',
        ...     merge_config={'how': 'left', 'on': 'id_cliente'},
        ... )
        >>> df = etl.run('data/merged.parquet')
    """

    def __init__(
        self,
        name: str,
        input_paths: List[str],
        output_path: Optional[str] = None,
        mode: str = "concat",
        merge_config: Optional[Dict[str, Any]] = None,
        key_column: Optional[str] = None,
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self.mode = mode.lower() if mode else "concat"
        self.merge_config = merge_config
        self.key_column = key_column or "id_cliente"
        self.kwargs = kwargs

        # Validate mode
        if self.mode not in ("concat", "merge"):
            raise ValueError(f"Mode must be 'concat' or 'merge', not '{self.mode}'")

        # Validate merge_config if mode is merge
        if self.mode == "merge" and not self.merge_config:
            raise ValueError(f"SourceETL '{self.name}': mode='merge' requires merge_config " "(e.g.: {'how': 'left', 'on': 'id_cliente'})")

    def extract(self) -> pd.DataFrame:
        """
        Extracts data from specified sources.

        Processes all input_paths according to configured mode:
        - concat: Concatenates all dataframes vertically
        - merge: Joins horizontally according to merge_config

        Returns:
            pd.DataFrame: Combined raw data

        Raises:
            ETLError: If data cannot be read
        """
        if not self.input_paths:
            raise ETLError(f"SourceETL '{self.name}': input_paths is empty")

        # Read all files
        from energizados.core.utils.secure_pickle import validate_no_traversal

        dataframes = []
        for path in self.input_paths:
            validate_no_traversal(path, label=f"ETL '{self.name}' input")
            source_file = Path(path)

            if not source_file.exists():
                raise ETLError(f"File not found: {path}")

            try:
                if source_file.suffix == ".csv":
                    df = pd.read_csv(path)
                elif source_file.suffix in [".parquet", ".pq"]:
                    df = pd.read_parquet(path)
                elif source_file.suffix in [".xlsx", ".xls"]:
                    df = pd.read_excel(path)
                else:
                    raise ETLError(f"Unsupported format: {source_file.suffix}")

                dataframes.append(df)
                logger.info(f"  • Read {len(df)} records from '{source_file.name}'")

            except Exception as e:
                raise ETLError(f"Error extracting from '{path}': {str(e)}")

        # Combine according to mode
        if self.mode == "concat":
            if len(dataframes) == 1:
                result = dataframes[0]
            else:
                result = pd.concat(dataframes, axis=0, ignore_index=True)
                logger.info(f"  ✓ Concatenated {len(dataframes)} files: {len(result)} records")

        elif self.mode == "merge":
            result = self._merge_dataframes(dataframes)
            logger.info(f"  ✓ Merged {len(dataframes)} files: {len(result)} records")

        return result

    def _merge_dataframes(self, dataframes: List[pd.DataFrame]) -> pd.DataFrame:
        """
        Merges multiple dataframes according to merge_config.

        Args:
            dataframes: List of dataframes to merge

        Returns:
            pd.DataFrame: Merged dataframe

        Raises:
            ETLError: If merge fails
        """
        if not dataframes:
            raise ETLError("No dataframes to merge")

        if len(dataframes) == 1:
            return dataframes[0]

        # Prepare merge configuration
        config = self.merge_config.copy()
        how = config.pop("how", "left")
        on = config.pop("on", None)
        left_on = config.pop("left_on", None)
        right_on = config.pop("right_on", None)
        left_index = config.pop("left_index", False)
        right_index = config.pop("right_index", False)

        # If no columns specified, use key_column by default
        if on is None and left_on is None and right_on is None:
            on = self.key_column

        # Sequential merge: first with second, result with third, etc.
        result = dataframes[0]
        for i, df in enumerate(dataframes[1:], start=2):
            try:
                result = pd.merge(
                    result, df, how=how, on=on, left_on=left_on, right_on=right_on, left_index=left_index, right_index=right_index, **config
                )
                logger.info(f"  • Merge step {i-1}→{i}: {len(result)} records")
            except Exception as e:
                raise ETLError(f"Error in merge step {i-1}→{i}: {str(e)}")

        return result

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms and cleans source data.

        Args:
            df: Raw DataFrame

        Returns:
            pd.DataFrame: Clean DataFrame
        """
        df = df.copy()

        # Remove completely empty rows
        before_count = len(df)
        df = df.dropna(how="all")
        after_count = len(df)

        if before_count > after_count:
            logger.info(f"  • Removed {before_count - after_count} empty rows")

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Saves the transformed data.

        Args:
            df: Transformed DataFrame
            path: Output path

        Raises:
            ETLError: If data cannot be saved
        """
        try:
            from energizados.core.utils.secure_pickle import validate_no_traversal

            validate_no_traversal(path, label=f"ETL '{self.name}' output")
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.suffix == ".parquet" or output_path.suffix == ".pq":
                df.to_parquet(path, index=False)
            elif output_path.suffix == ".csv":
                df.to_csv(path, index=False)
            else:
                df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

            logger.info(f"  ✓ Saved {len(df)} records to '{path}'")

        except Exception as e:
            raise ETLError(f"Error saving '{self.name}': {str(e)}")
