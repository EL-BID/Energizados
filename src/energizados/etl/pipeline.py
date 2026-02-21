"""
Pipeline ETL Module for Multi-Source Data Processing.

Este módulo proporciona clases para orquestar múltiples ETLs de fuentes
y combinar sus salidas en un dataset final.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from energizados.core.exceptions import ETLError
from energizados.etl.base import BaseETL


class SourceETL(BaseETL):
    """
    ETL para procesar una fuente individual de datos.

    Esta clase está diseñada para procesar una sola fuente de datos
    (consumos, inspecciones, clientes, etc.) y generar una salida
    procesada que será combinada posteriormente.

    Args:
        name: Nombre de la fuente (ej: 'consumos', 'inspecciones', 'clientes')
        source_path: Ruta al archivo de datos crudos
        output_path: Ruta donde guardar los datos procesados
        key_column: Columna a usar como clave para unir (default: 'id_cliente' o 'index')
        **kwargs: Parámetros adicionales

    Example:
        >>> etl = SourceETL(
        ...     name='consumos',
        ...     source_path='data/raw/consumos.csv',
        ...     output_path='data/consumos.parquet',
        ...     key_column='id_cliente'
        ... )
        >>> df = etl.run('data/consumos.parquet')
    """

    def __init__(
        self,
        name: str,
        source_path: str,
        output_path: Optional[str] = None,
        key_column: Optional[str] = None,
        **kwargs,
    ):
        self.name = name
        self.source_path = source_path
        self.output_path = output_path
        self.key_column = key_column or "id_cliente"
        self.kwargs = kwargs

    def extract(self) -> pd.DataFrame:
        """
        Extrae datos de la fuente especificada.

        Returns:
            pd.DataFrame: Datos crudos

        Raises:
            ETLError: Si no se pueden leer los datos
        """
        source_file = Path(self.source_path)

        if not source_file.exists():
            raise ETLError(f"Archivo no encontrado: {self.source_path}")

        try:
            if source_file.suffix == ".csv":
                df = pd.read_csv(self.source_path)
            elif source_file.suffix in [".parquet", ".pq"]:
                df = pd.read_parquet(self.source_path)
            elif source_file.suffix in [".xlsx", ".xls"]:
                df = pd.read_excel(self.source_path)
            else:
                raise ETLError(f"Formato no soportado: {source_file.suffix}")

            print(f"  ✓ Extraídos {len(df)} registros de '{self.name}'")
            return df

        except Exception as e:
            raise ETLError(f"Error extrayendo de '{self.name}': {str(e)}")

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
            print(f"  • Eliminadas {before_count - after_count} filas vacías")

        # Asegurar que la clave existe
        if self.key_column not in df.columns:
            # Si no existe, intentar usar el índice
            if "index" in df.columns:
                df[self.key_column] = df["index"]
            else:
                # Crear índice si no existe
                df = df.reset_index(drop=True)
                df[self.key_column] = df.index.astype(str)

        # Eliminar duplicados basados en la clave
        before_dedup = len(df)
        df = df.drop_duplicates(subset=[self.key_column], keep="first")
        after_dedup = len(df)

        if before_dedup > after_dedup:
            print(f"  • Eliminados {before_dedup - after_dedup} duplicados por clave")

        print(f"  ✓ Transformados {len(df)} registros de '{self.name}'")
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

            print(f"  ✓ Guardados {len(df)} registros en '{path}'")

        except Exception as e:
            raise ETLError(f"Error guardando '{self.name}': {str(e)}")


class MultiSourceETL(BaseETL):
    """
    ETL que orquesta múltiples fuentes de datos y las combina.

    Esta clase ejecuta múltiples ETLs de fuentes en paralelo/serie
    y luego combina sus salidas en un dataset final.

    Args:
        sources: Lista de configuraciones de fuentes
        merge_config: Configuración de cómo combinar las fuentes
        output_path: Ruta de salida del dataset final
        **kwargs: Parámetros adicionales

    Example:
        >>> etl = MultiSourceETL(
        ...     sources=[
        ...         {'name': 'consumos', 'path': 'data/raw/consumos.csv'},
        ...         {'name': 'clientes', 'path': 'data/raw/clientes.csv'},
        ...     ],
        ...     merge_config={'how': 'left', 'on': 'id_cliente'},
        ...     output_path='data/dataset_final.parquet'
        ... )
        >>> df = etl.run('data/dataset_final.parquet')
    """

    def __init__(
        self,
        sources: List[Dict[str, Any]],
        merge_config: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
        **kwargs,
    ):
        self.sources = sources
        self.merge_config = merge_config or {}
        self.output_path = output_path
        self.kwargs = kwargs

        # Almacén de DataFrames procesados
        self.processed_sources_: Dict[str, pd.DataFrame] = {}

    def extract(self) -> Dict[str, pd.DataFrame]:
        """
        Extrae datos de todas las fuentes configuradas.

        Returns:
            Dict[str, pd.DataFrame]: Diccionario con datos crudos por fuente
        """
        from energizados.core.exceptions import ETLError

        raw_data = {}

        print(f"\n{'=' * 60}")
        print(f"EXTRACT: Procesando {len(self.sources)} fuentes")
        print(f"{'=' * 60}")

        for source_config in self.sources:
            name = source_config.get("name")
            source_path = source_config.get("path")

            if not name or not source_path:
                raise ETLError("Cada fuente debe tener 'name' y 'path'")

            # Crear SourceETL para esta fuente
            etl = SourceETL(
                name=name,
                source_path=source_path,
                key_column=source_config.get("key_column"),
            )

            # Extraer
            try:
                df = etl.extract()
                raw_data[name] = df
            except Exception as e:
                raise ETLError(f"Error extrayendo fuente '{name}': {str(e)}")

        return raw_data

    def transform(self, raw_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Transforma y combina todas las fuentes.

        Args:
            raw_data: Diccionario con DataFrames crudos por fuente

        Returns:
            pd.DataFrame: DataFrame combinado y transformado
        """
        from energizados.core.exceptions import ETLError

        print(f"\n{'=' * 60}")
        print("TRANSFORM: Procesando fuentes individuales")
        print(f"{'=' * 60}")

        processed = {}

        # Transformar cada fuente individualmente
        for source_config in self.sources:
            name = source_config.get("name")

            if name not in raw_data:
                raise ETLError(f"No se encontraron datos para fuente '{name}'")

            etl = SourceETL(
                name=name,
                source_path=source_config.get("path"),
                key_column=source_config.get("key_column"),
            )

            # Transformar
            df = etl.transform(raw_data[name])
            processed[name] = df

        self.processed_sources_ = processed

        # Combinar fuentes
        print(f"\n{'=' * 60}")
        print("MERGE: Combinando fuentes procesadas")
        print(f"{'=' * 60}")

        merged_df = self._merge_sources(processed)

        return merged_df

    def _merge_sources(self, processed: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Combina múltiples DataFrames en uno solo.

        Args:
            processed: Diccionario con DataFrames procesados por fuente

        Returns:
            pd.DataFrame: DataFrame combinado
        """
        if not processed:
            raise ETLError("No hay fuentes procesadas para combinar")

        # Obtener configuración de merge
        merge_how = self.merge_config.get("how", "left")
        merge_on = self.merge_config.get("on")

        # Determinar orden de merge (primary first)
        primary_source = self.merge_config.get("primary_source")
        source_order = self.merge_config.get("source_order", [])

        # Ordenar fuentes
        if primary_source and primary_source in processed:
            # Poner primary al inicio
            ordered = {primary_source: processed[primary_source]}
            for name, df in processed.items():
                if name != primary_source:
                    ordered[name] = df
            processed = ordered
        elif source_order:
            # Usar orden especificado
            ordered = {}
            for name in source_order:
                if name in processed:
                    ordered[name] = processed[name]
            # Agregar restantes
            for name, df in processed.items():
                if name not in ordered:
                    ordered[name] = df
            processed = ordered

        # Comenzar con la primera fuente
        source_names = list(processed.keys())
        first_name = source_names[0]
        merged = processed[first_name]

        print(f"  • Fuente primaria: '{first_name}' ({len(merged)} registros)")

        # Merge con las demás fuentes
        for name in source_names[1:]:
            df = processed[name]

            # Determinar clave de unión
            if merge_on:
                on = merge_on
            else:
                # Intentar encontrar columna común
                common_cols = set(merged.columns) & set(df.columns)
                if not common_cols:
                    raise ETLError(f"No hay columnas comunes entre '{first_name}' y '{name}'")
                on = list(common_cols)[0]

            # Merge
            print(f"  • Merge con '{name}' ({len(df)} registros) on='{on}', how='{merge_how}'")
            merged = pd.merge(merged, df, on=on, how=merge_how, suffixes=("", f"_{name}"))

        print(f"\n  ✓ Dataset final: {len(merged)} registros, {len(merged.columns)} columnas")

        return merged

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Guarda el dataset combinado.

        Args:
            df: DataFrame combinado
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

            print(f"  ✓ Dataset final guardado en '{path}'")

        except Exception as e:
            raise ETLError(f"Error guardando dataset final: {str(e)}")


class MergeETL(BaseETL):
    """
    ETL que combina datasets previamente procesados.

    Esta clase lee datasets ya procesados (por otros ETLs) y los
    combina en un dataset final.

    Args:
        sources: Lista de rutas a datasets procesados
        merge_config: Configuración de cómo combinar las fuentes
        output_path: Ruta de salida del dataset final
        **kwargs: Parámetros adicionales

    Example:
        >>> etl = MergeETL(
        ...     sources=[
        ...         {'name': 'consumos', 'path': 'data/consumos.parquet'},
        ...         {'name': 'clientes', 'path': 'data/clientes.parquet'},
        ...     ],
        ...     merge_config={'how': 'left', 'on': 'id_cliente'},
        ...     output_path='data/dataset_final.parquet'
        ... )
        >>> df = etl.run('data/dataset_final.parquet')
    """

    def __init__(
        self,
        sources: List[Dict[str, Any]],
        merge_config: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
        **kwargs,
    ):
        self.sources = sources
        self.merge_config = merge_config or {}
        self.output_path = output_path
        self.kwargs = kwargs

    def extract(self) -> Dict[str, pd.DataFrame]:
        """
        Lee los datasets procesados.

        Returns:
            Dict[str, pd.DataFrame]: Diccionario con DataFrames por fuente
        """
        from energizados.core.exceptions import ETLError

        print(f"\n{'=' * 60}")
        print(f"EXTRACT: Leyendo {len(self.sources)} datasets procesados")
        print(f"{'=' * 60}")

        data = {}

        for source_config in self.sources:
            name = source_config.get("name")
            source_path = source_config.get("path")

            if not name or not source_path:
                raise ETLError("Cada fuente debe tener 'name' y 'path'")

            try:
                path = Path(source_path)
                if not path.exists():
                    raise ETLError(f"Archivo no encontrado: {source_path}")

                if path.suffix in [".parquet", ".pq"]:
                    df = pd.read_parquet(source_path)
                elif path.suffix == ".csv":
                    df = pd.read_csv(source_path)
                else:
                    raise ETLError(f"Formato no soportado: {path.suffix}")

                data[name] = df
                print(f"  ✓ Leídos {len(df)} registros de '{name}'")

            except Exception as e:
                raise ETLError(f"Error leyendo '{name}': {str(e)}")

        return data

    def transform(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Combina los datasets procesados.

        Args:
            data: Diccionario con DataFrames por fuente

        Returns:
            pd.DataFrame: DataFrame combinado
        """
        print(f"\n{'=' * 60}")
        print("MERGE: Combinando datasets procesados")
        print(f"{'=' * 60}")

        merged = self._merge_sources(data)

        return merged

    def _merge_sources(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Combina múltiples DataFrames en uno solo.

        Args:
            data: Diccionario con DataFrames por fuente

        Returns:
            pd.DataFrame: DataFrame combinado
        """
        if not data:
            raise ETLError("No hay datos para combinar")

        merge_how = self.merge_config.get("how", "left")
        merge_on = self.merge_config.get("on")

        # Determinar orden de merge
        primary_source = self.merge_config.get("primary_source")
        source_order = self.merge_config.get("source_order", [])

        # Ordenar fuentes
        if primary_source and primary_source in data:
            ordered = {primary_source: data[primary_source]}
            for name, df in data.items():
                if name != primary_source:
                    ordered[name] = df
            data = ordered
        elif source_order:
            ordered = {}
            for name in source_order:
                if name in data:
                    ordered[name] = data[name]
            for name, df in data.items():
                if name not in ordered:
                    ordered[name] = df
            data = ordered

        source_names = list(data.keys())
        first_name = source_names[0]
        merged = data[first_name]

        print(f"  • Fuente primaria: '{first_name}' ({len(merged)} registros)")

        for name in source_names[1:]:
            df = data[name]

            if merge_on:
                on = merge_on
            else:
                common_cols = set(merged.columns) & set(df.columns)
                if not common_cols:
                    raise ETLError(f"No hay columnas comunes entre '{first_name}' y '{name}'")
                on = list(common_cols)[0]

            print(f"  • Merge con '{name}' ({len(df)} registros) on='{on}', how='{merge_how}'")
            merged = pd.merge(merged, df, on=on, how=merge_how, suffixes=("", f"_{name}"))

        print(f"\n  ✓ Dataset final: {len(merged)} registros, {len(merged.columns)} columnas")

        return merged

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Guarda el dataset combinado.

        Args:
            df: DataFrame combinado
            path: Ruta de salida

        Raises:
            ETLError: Si no se pueden guardar los datos
        """
        try:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.suffix in [".parquet", ".pq"]:
                df.to_parquet(path, index=False)
            elif output_path.suffix == ".csv":
                df.to_csv(path, index=False)
            else:
                df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

            print(f"  ✓ Dataset final guardado en '{path}'")

        except Exception as e:
            raise ETLError(f"Error guardando dataset final: {str(e)}")
