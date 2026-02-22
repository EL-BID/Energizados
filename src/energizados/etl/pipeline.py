"""
Pipeline ETL Module for Multi-Source Data Processing.

Este módulo proporciona clases para orquestar múltiples ETLs de fuentes
y combinar sus salidas en un dataset final.
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
    ETL para procesar una o múltiples fuentes de datos.

    Esta clase procesa datos de uno o varios archivos y genera una salida
    procesada. Soporta dos modos de operación:

    - **concat**: Concatena verticalmente múltiples dataframes (por defecto)
    - **merge**: Une horizontalmente múltiples dataframes usando merge_config

    Args:
        name: Nombre de la fuente (ej: 'consumos', 'inspecciones', 'clientes')
        input_paths: Lista con las rutas a los archivos de datos crudos
        output_path: Ruta donde guardar los datos procesados
        mode: Modo de procesamiento ('concat' o 'merge'). Default: 'concat'
        merge_config: Configuración para merge (requerido si mode='merge')
            Ej: {'how': 'left', 'on': 'id_cliente'}
            Opciones: how ('left', 'right', 'inner', 'outer'), on (columna),
                      left_on, right_on, left_index, right_index
        key_column: Columna clave usada por defecto en merge_config
        **kwargs: Parámetros adicionales

    Example:
        >>> etl = SourceETL(
        ...     name='consumos',
        ...     mode='concat',
        ...     input_paths=['data/raw/consumos.csv'],
        ...     output_path='data/consumos.parquet',
        ... )
        >>> df = etl.run('data/consumos.parquet')

    Example con merge:
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

        # Validar modo
        if self.mode not in ("concat", "merge"):
            raise ValueError(f"Mode debe ser 'concat' o 'merge', no '{self.mode}'")

        # Validar merge_config si mode es merge
        if self.mode == "merge" and not self.merge_config:
            raise ValueError(f"SourceETL '{self.name}': mode='merge' requiere merge_config " "(ej: {'how': 'left', 'on': 'id_cliente'})")

    def extract(self) -> pd.DataFrame:
        """
        Extrae datos de las fuentes especificadas.

        Procesa todos los input_paths según el modo configurado:
        - concat: Concatena verticalmente todos los dataframes
        - merge: Une horizontalmente según merge_config

        Returns:
            pd.DataFrame: Datos crudos combinados

        Raises:
            ETLError: Si no se pueden leer los datos
        """
        if not self.input_paths:
            raise ETLError(f"SourceETL '{self.name}': input_paths está vacío")

        # Leer todos los archivos
        dataframes = []
        for path in self.input_paths:
            source_file = Path(path)

            if not source_file.exists():
                raise ETLError(f"Archivo no encontrado: {path}")

            try:
                if source_file.suffix == ".csv":
                    df = pd.read_csv(path)
                elif source_file.suffix in [".parquet", ".pq"]:
                    df = pd.read_parquet(path)
                elif source_file.suffix in [".xlsx", ".xls"]:
                    df = pd.read_excel(path)
                else:
                    raise ETLError(f"Formato no soportado: {source_file.suffix}")

                dataframes.append(df)
                logger.info(f"  • Leídos {len(df)} registros de '{source_file.name}'")

            except Exception as e:
                raise ETLError(f"Error extrayendo de '{path}': {str(e)}")

        # Combinar según el modo
        if self.mode == "concat":
            if len(dataframes) == 1:
                result = dataframes[0]
            else:
                result = pd.concat(dataframes, axis=0, ignore_index=True)
                logger.info(f"  ✓ Concatenados {len(dataframes)} archivos: {len(result)} registros")

        elif self.mode == "merge":
            result = self._merge_dataframes(dataframes)
            logger.info(f"  ✓ Merged {len(dataframes)} archivos: {len(result)} registros")

        return result

    def _merge_dataframes(self, dataframes: List[pd.DataFrame]) -> pd.DataFrame:
        """
        Fusiona múltiples dataframes según merge_config.

        Args:
            dataframes: Lista de dataframes a fusionar

        Returns:
            pd.DataFrame: Dataframe fusionado

        Raises:
            ETLError: Si el merge falla
        """
        if not dataframes:
            raise ETLError("No hay dataframes para merge")

        if len(dataframes) == 1:
            return dataframes[0]

        # Preparar configuración de merge
        config = self.merge_config.copy()
        how = config.pop("how", "left")
        on = config.pop("on", None)
        left_on = config.pop("left_on", None)
        right_on = config.pop("right_on", None)
        left_index = config.pop("left_index", False)
        right_index = config.pop("right_index", False)

        # Si no se especifica columnas, usar key_column por defecto
        if on is None and left_on is None and right_on is None:
            on = self.key_column

        # Merge secuencial: primero con segundo, resultado con tercero, etc.
        result = dataframes[0]
        for i, df in enumerate(dataframes[1:], start=2):
            try:
                result = pd.merge(
                    result, df, how=how, on=on, left_on=left_on, right_on=right_on, left_index=left_index, right_index=right_index, **config
                )
                logger.info(f"  • Merge paso {i-1}→{i}: {len(result)} registros")
            except Exception as e:
                raise ETLError(f"Error en merge paso {i-1}→{i}: {str(e)}")

        return result

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma y limpia los datos de la fuente.

        Args:
            df: DataFrame crudo

        Returns:
            pd.DataFrame: DataFrame limpio
        """
        df = df.copy()

        # Eliminar filas completamente vacías
        before_count = len(df)
        df = df.dropna(how="all")
        after_count = len(df)

        if before_count > after_count:
            logger.info(f"  • Eliminadas {before_count - after_count} filas vacías")

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
        try:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.suffix == ".parquet" or output_path.suffix == ".pq":
                df.to_parquet(path, index=False)
            elif output_path.suffix == ".csv":
                df.to_csv(path, index=False)
            else:
                df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

            logger.info(f"  ✓ Guardados {len(df)} registros en '{path}'")

        except Exception as e:
            raise ETLError(f"Error guardando '{self.name}': {str(e)}")
