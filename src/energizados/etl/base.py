"""
ETL Base Module.

Define la clase abstracta BaseETL que los usuarios pueden heredar
para implementar sus propios procesos ETL personalizados.

Esta clase re-exporta BaseETL desde core.base para mayor conveniencia.
"""

from abc import ABC, abstractmethod

import pandas as pd


class BaseETL(ABC):
    """
    Clase base para ETL personalizado.

    El usuario hereda e implementa los métodos abstractos para definir
    su propio proceso de extracción, transformación y carga de datos.

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
        Extrae datos de la fuente.

        Returns:
            pd.DataFrame: Datos crudos

        Raises:
            ETLError: Si ocurre un error durante la extracción
        """
        pass

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma y limpia los datos.

        Args:
            df: DataFrame crudo

        Returns:
            pd.DataFrame: DataFrame limpio con el esquema esperado

        Raises:
            ETLError: Si ocurre un error durante la transformación
        """
        pass

    @abstractmethod
    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Guarda los datos transformados.

        Args:
            df: DataFrame transformado
            path: Ruta de salida

        Raises:
            ETLError: Si ocurre un error durante la carga
        """
        pass

    def run(self, output_path: str) -> pd.DataFrame:
        """
        Ejecuta el pipeline completo de ETL.

        Este método puede sobrescribirse para agregar lógica adicional.

        Args:
            output_path: Ruta donde guardar los datos transformados

        Returns:
            pd.DataFrame: DataFrame transformado
        """
        from energizados.core.exceptions import ETLError

        try:
            df = self.extract()
            df = self.transform(df)
            self.load(df, output_path)
            return df
        except Exception as e:
            raise ETLError(f"Error ejecutando ETL: {str(e)}")
