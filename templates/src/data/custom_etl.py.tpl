"""
ETL Personalizado para {{project_name}}.

Este módulo implementa la extracción, transformación y carga de datos
específica para este proyecto.

Edita los métodos extract(), transform() y load() según tus necesidades.
"""

from energizados.base import BaseETL
import pandas as pd


class CustomETL(BaseETL):
    """
    ETL personalizado para {{project_name}}.

    Hereda de BaseETL e implementa los métodos abstractos para definir
    el proceso específico de este proyecto.

    Soporta múltiples inputs (string o lista) según configuración YAML.
    """

    def __init__(self, input_paths: list = None, output_path: str = None, **kwargs):
        """
        Inicializa el ETL.

        Args:
            input_paths: Lista de rutas de archivos de entrada
            output_path: Ruta de salida para los datos transformados
            **kwargs: Parámetros adicionales desde la configuración
        """
        super().__init__(**kwargs)
        self.input_paths = input_paths or []
        self.output_path = output_path

    def extract(self) -> pd.DataFrame:
        """
        Extrae datos de la fuente.

        Edita este método para implementar tu lógica de extracción.
        Usa self.input_paths para acceder a los archivos configurados.

        Returns:
            pd.DataFrame: Datos crudos
        """
        # TODO: Implementar tu lógica de extracción
        # Ejemplo con un solo archivo:
        # if self.input_paths:
        #     return pd.read_csv(self.input_paths[0])

        # Ejemplo con múltiples archivos:
        # dfs = [pd.read_csv(f) for f in self.input_paths]
        # return pd.concat(dfs, axis=0)

        raise NotImplementedError("Implementa el método extract() en tu ETL")

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
        # Ejemplo:
        # df = df.dropna()
        # df['fecha'] = pd.to_datetime(df['fecha'])
        # return df

        raise NotImplementedError("Implementa el método transform() en tu ETL")

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Guarda los datos transformados.

        Por defecto guarda en formato parquet, pero puedes cambiarlo.

        Args:
            df: DataFrame transformado
            path: Ruta de salida
        """
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    def run(self, output_path: str = None) -> pd.DataFrame:
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
