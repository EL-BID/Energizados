"""
ETL Personalizado para {{project_name}}.

Este módulo extiende SourceETL para implementar lógica de procesamiento
específica para este proyecto.

Puedes sobrescribir los métodos extract(), transform() y load() según tus necesidades.
"""

import pandas as pd

from energizados.etl.pipeline import SourceETL
from energizados.preprocessing import fill_empty_values_cycle, fill_empty_values_str


class CustomETL(SourceETL):
    """
    ETL personalizado para {{project_name}}.

    Hereda de SourceETL que ya implementa:
    - Lectura de múltiples archivos (csv, parquet, xlsx)
    - Modo concat (por defecto) para concatenar archivos verticalmente
    - Modo merge para unir archivos horizontalmente

    Sobrescribe solo los métodos que necesites personalizar.
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
        Inicializa el ETL.

        Args:
            name: Nombre del ETL
            input_paths: Lista de rutas de archivos de entrada
            output_path: Ruta de salida para los datos transformados
            mode: Modo de procesamiento ('concat' o 'merge'). Default: 'concat'
            merge_config: Configuración para merge si mode='merge'
                Ej: {'how': 'left', 'on': 'id_cliente'}
            **kwargs: Parámetros adicionales desde la configuración
        """
        super().__init__(
            name=name,
            input_paths=input_paths or [],
            output_path=output_path,
            mode=mode,
            merge_config=merge_config,
            **kwargs,
        )

    # Ejemplo: Sobrescribir extract() si necesitas lógica personalizada
    # def extract(self) -> pd.DataFrame:
    #     """Extrae datos con lógica personalizada."""
    #     # Llamar al método padre para usar la lógica estándar
    #     df = super().extract()
    #
    #     # O implementar tu propia lógica
    #     # dfs = [pd.read_csv(f) for f in self.input_paths]
    #     # df = pd.concat(dfs, axis=0)
    #
    #     return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma y limpia los datos.

        Edita este método para implementar tu lógica de transformación.

        Args:
            df: DataFrame crudo

        Returns:
            pd.DataFrame: DataFrame limpio
        """
        # TODO: Implementar tu lógica de transformación

        # Fill empty values for consuming vars
        df = fill_empty_values_cycle(df, cant_ciclos_validos=12, suffix="_anterior")

        # Fill columns with 'sin_dato'
        cols_fillna_sindatos = ['zona', 'actividad', 'tipo_tarifa', 'nivel_tension']
        df = fill_empty_values_str(df, cols=cols_fillna_sindatos, str_value='sin_dato')

        # Remove index column if present
        if 'index' in df.columns:
            df.drop(columns=['index'], inplace=True)

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Guarda los datos transformados.

        Por defecto usa el método padre que guarda en formato parquet.
        Sobrescribe si necesitas formato diferente o validación de esquema.

        Args:
            df: DataFrame transformado
            path: Ruta de salida
        """
        # Ejemplo: Validar esquema antes de guardar
        # validator = SchemaValidator(
        #     required_columns=['id_cliente', 'fecha', 'consumo'],
        #     categorical_columns=['actividad', 'zona'],
        #     numeric_columns=['consumo', 'facturacion'],
        # )
        # validator.validate_and_raise(df)

        # Usar el método padre que soporta csv, parquet, xlsx
        super().load(df, path)

# EJEMPLO DE USO EN CONFIG YAML
# ================================
#
# 1. Concatenar múltiples archivos (modo por defecto):
#
#    mi_etl:
#      enabled: true
#      description: "Concatena datos de múltiples archivos CSV"
#      input:
#        - "data/raw/file1.csv"
#        - "data/raw/file2.csv"
#        - "data/raw/file3.csv"
#      output: "data/processed/concatenado.parquet"
#      custom_class: "{{package}}.data.custom_etl.CustomETL"
#      params:
#        mode: "concat"
#
# 2. Merging múltiples archivos:
#
#    merge_etl:
#      enabled: true
#      description: "Une consumos con clientes"
#      input:
#        - "data/processed/consumos.parquet"
#        - "data/processed/clientes.parquet"
#      output: "data/processed/merged.parquet"
#      custom_class: "{{package}}.data.custom_etl.CustomETL"
#      params:
#        mode: "merge"
#        merge_config:
#          how: "left"
#          on: "id_cliente"
#
# 3. Con transformación personalizada:
#
#    transform_etl:
#      enabled: true
#      description: "Procesa datos con limpieza personalizada"
#      input:
#        - "data/raw/datos.csv"
#      output: "data/processed/lmpio.parquet"
#      custom_class: "{{package}}.data.custom_etl.CustomETL"
#      params:
#        mode: "concat"
