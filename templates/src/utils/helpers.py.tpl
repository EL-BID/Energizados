"""
Funciones auxiliares y utilidades compartidas para {{project_name}}.

Este módulo contiene funciones reutilizables que pueden ser utilizadas
por distintos componentes del proyecto.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def load_data(file_path: Union[str, Path], **kwargs) -> pd.DataFrame:
    """
    Carga datos desde un archivo soportando múltiples formatos.

    Args:
        file_path: Ruta al archivo (csv, parquet, excel)
        **kwargs: Argumentos adicionales para pd.read_csv/read_parquet

    Returns:
        pd.DataFrame: Datos cargados
    """
    file_path = Path(file_path)

    if file_path.suffix == '.csv':
        return pd.read_csv(file_path, **kwargs)
    elif file_path.suffix in ['.parquet', '.pq']:
        return pd.read_parquet(file_path, **kwargs)
    elif file_path.suffix in ['.xlsx', '.xls']:
        return pd.read_excel(file_path, **kwargs)
    else:
        raise ValueError(f"Formato no soportado: {file_path.suffix}")


def save_data(df: pd.DataFrame, file_path: Union[str, Path], **kwargs) -> None:
    """
    Guarda un DataFrame en el formato especificado.

    Args:
        df: DataFrame a guardar
        file_path: Ruta de salida
        **kwargs: Argumentos adicionales para df.to_csv/to_parquet
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
        raise ValueError(f"Formato no soportado: {file_path.suffix}")


def get_memory_usage(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calcula el uso de memoria de un DataFrame.

    Args:
        df: DataFrame a analizar

    Returns:
        Dict con uso de memoria en MB para cada tipo de dato
    """
    memory = df.memory_usage(deep=True)
    total_mb = memory.sum() / 1024 / 1024

    return {
        'total_mb': total_mb,
        'by_type': df.dtypes.value_counts().to_dict()
    }


def reduce_memory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce el uso de memoria del DataFrame optimizando tipos de datos.

    Args:
        df: DataFrame a optimizar

    Returns:
        pd.DataFrame: DataFrame optimizado
    """
    result = df.copy()

    for col in result.columns:
        col_type = result[col].dtype

        if col_type == 'object':
            # Para strings, usar category si tiene pocos valores únicos
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


# Agrega aquí más funciones auxiliares según las necesidades de tu proyecto
