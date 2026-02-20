"""
Default ETL Implementation for Energizados.

Proporciona una implementación por defecto del proceso ETL
que funciona con el formato de datos estándar del proyecto.
"""

from pathlib import Path
from typing import List, Optional, Union

import pandas as pd


class DefaultETL:
    """
    Implementación default de ETL para el proyecto Energizados.

    Esta clase proporciona una implementación básica que puede ser
    utilizada directamente o extendida para casos personalizados.

    Args:
        sources: Lista de rutas de archivos o DataFrames de entrada
        output_path: Ruta de salida para los datos transformados
        categorical_features: Lista de nombres de variables categóricas
        consumption_columns: Lista de columnas de consumo mensual
        target_column: Nombre de la columna objetivo (opcional)

    Example:
        >>> etl = DefaultETL(
        ...     sources=["data.csv"],
        ...     output_path="data/output.parquet",
        ...     categorical_features=["actividad", "tipo_tarifa"]
        ... )
        >>> df = etl.run()
    """

    def __init__(
        self,
        sources: Optional[List[Union[str, pd.DataFrame]]] = None,
        output_path: Optional[str] = None,
        categorical_features: Optional[List[str]] = None,
        consumption_columns: Optional[List[str]] = None,
        target_column: Optional[str] = None,
    ):
        self.sources = sources or []
        self.output_path = output_path
        self.categorical_features = categorical_features or []
        self.consumption_columns = consumption_columns or [f"{i}_anterior" for i in range(12, 0, -1)]
        self.target_column = target_column

    def extract(self) -> pd.DataFrame:
        """
        Extrae datos de las fuentes especificadas.

        Returns:
            pd.DataFrame: Datos crudos combinados de todas las fuentes

        Raises:
            ETLError: Si no se pueden leer los datos
        """
        from energizados.core.exceptions import ETLError

        if not self.sources:
            raise ETLError("No se especificaron fuentes de datos")

        dfs = []
        for source in self.sources:
            try:
                if isinstance(source, str):
                    path = Path(source)
                    if path.suffix == ".csv":
                        df = pd.read_csv(source)
                    elif path.suffix in [".parquet", ".pq"]:
                        df = pd.read_parquet(source)
                    elif path.suffix in [".xlsx", ".xls"]:
                        df = pd.read_excel(source)
                    else:
                        raise ETLError(f"Formato no soportado: {path.suffix}")
                elif isinstance(source, pd.DataFrame):
                    df = source.copy()
                else:
                    raise ETLError(f"Tipo de fuente no soportado: {type(source)}")
                dfs.append(df)
            except Exception as e:
                raise ETLError(f"Error leyendo fuente {source}: {str(e)}")

        # Combinar todos los DataFrames
        if len(dfs) == 1:
            return dfs[0]
        return pd.concat(dfs, axis=1)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma y limpia los datos.

        Realiza las siguientes operaciones:
        1. Elimina filas con todos los valores NaN
        2. Convierte columnas categóricas a tipo string
        3. Valida que las columnas de consumo sean numéricas
        4. Elimina duplicados basados en un índice si existe

        Args:
            df: DataFrame crudo

        Returns:
            pd.DataFrame: DataFrame limpio
        """
        df = df.copy()

        # Eliminar filas completamente vacías
        df = df.dropna(how="all")

        # Si hay columna 'index', usarla como índice y eliminar duplicados
        if "index" in df.columns:
            df = df.drop_duplicates(subset=["index"], keep="first")

        # Convertir categóricas a string
        for col in self.categorical_features:
            if col in df.columns:
                df[col] = df[col].astype(str)

        # Validar columnas de consumo
        for col in self.consumption_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Eliminar filas sin consumo
        if self.consumption_columns:
            valid_cols = [c for c in self.consumption_columns if c in df.columns]
            if valid_cols:
                df = df.dropna(subset=valid_cols, how="all")

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Guarda los datos transformados.

        Args:
            df: DataFrame transformado
            path: Ruta de salida

        Raises:
            ETLError: Si no se pueden guardar los datos
        """
        from energizados.core.exceptions import ETLError

        try:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.suffix == ".parquet" or output_path.suffix == ".pq":
                df.to_parquet(path, index=False)
            elif output_path.suffix == ".csv":
                df.to_csv(path, index=False)
            else:
                # Default a parquet
                df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)
        except Exception as e:
            raise ETLError(f"Error guardando datos en {path}: {str(e)}")

    def run(self, output_path: Optional[str] = None) -> pd.DataFrame:
        """
        Ejecuta el pipeline completo de ETL.

        Args:
            output_path: Ruta de salida (usa self.output_path si no se especifica)

        Returns:
            pd.DataFrame: DataFrame transformado
        """
        if output_path is None:
            output_path = self.output_path

        df = self.extract()
        df = self.transform(df)

        if output_path:
            self.load(df, output_path)

        return df
