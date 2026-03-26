"""
Helper functions and shared utilities for {{project_name}}.

This module contains reusable functions that can be used
by different project components.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def load_data(file_path: Union[str, Path], **kwargs) -> pd.DataFrame:
    """
    Load data from a file supporting multiple formats.

    Args:
        file_path: Path to the file (csv, parquet, excel)
        **kwargs: Additional arguments for pd.read_csv/read_parquet

    Returns:
        pd.DataFrame: Loaded data
    """
    file_path = Path(file_path)

    if file_path.suffix == '.csv':
        return pd.read_csv(file_path, **kwargs)
    elif file_path.suffix in ['.parquet', '.pq']:
        return pd.read_parquet(file_path, **kwargs)
    elif file_path.suffix in ['.xlsx', '.xls']:
        return pd.read_excel(file_path, **kwargs)
    else:
        raise ValueError(f"Unsupported format: {file_path.suffix}")


def save_data(df: pd.DataFrame, file_path: Union[str, Path], **kwargs) -> None:
    """
    Save a DataFrame in the specified format.

    Args:
        df: DataFrame to save
        file_path: Output path
        **kwargs: Additional arguments for df.to_csv/to_parquet
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_path.suffix == '.csv':
        df.to_csv(file_path, index=False, **kwargs)
    elif file_path.suffix in ['.parquet', '.pq']:
        df.to_parquet(file_path, index=False, **kwargs)
    elif file_path.suffix in ['.xlsx', '.xls']:
        df.to_excel(file_path, index=False, **kwargs)
    else:
        raise ValueError(f"Unsupported format: {file_path.suffix}")


def get_memory_usage(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate the memory usage of a DataFrame.

    Args:
        df: DataFrame to analyze

    Returns:
        Dict with memory usage in MB for each data type
    """
    memory = df.memory_usage(deep=True)
    total_mb = memory.sum() / 1024 / 1024

    return {
        'total_mb': total_mb,
        'by_type': df.dtypes.value_counts().to_dict()
    }


def reduce_memory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce DataFrame memory usage by optimizing data types.

    Args:
        df: DataFrame to optimize

    Returns:
        pd.DataFrame: Optimized DataFrame
    """
    result = df.copy()

    for col in result.columns:
        col_type = result[col].dtype

        if col_type == 'object':
            # For strings, use category if few unique values
            unique_ratio = result[col].nunique() / len(result[col])
            if unique_ratio < 0.5:
                result[col] = result[col].astype('category')
        elif col_type == 'float64':
            # Downcast floats
            result[col] = pd.to_numeric(result[col], downcast='float')
        elif col_type == 'int64':
            # Downcast integers
            result[col] = pd.to_numeric(result[col], downcast='integer')

    return result


# Add more helper functions here as needed for your project
