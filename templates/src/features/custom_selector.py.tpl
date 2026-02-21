"""
Selector de Features Personalizado para {{project_name}}.

Este módulo implementa la lógica de selección de variables
específica para este proyecto.

Edita los métodos fit() y transform() según tus necesidades.
"""

from energizados.feature_selection.base import BaseFeatureSelector
import pandas as pd


class CustomSelector(BaseFeatureSelector):
    """
    Selector de features personalizado para {{project_name}}.

    Hereda de BaseFeatureSelector e implementa los métodos abstractos
    para definir la lógica específica de este proyecto.
    """

    def __init__(self, config = None, **kwargs):
        """
        Inicializa el selector.

        Args:
            config: Diccionario de configuración (opcional)
            **kwargs: Parámetros adicionales desde la configuración YAML
        """
        super().__init__(config)
        # Agrega tus parámetros personalizados aquí
        # self.threshold = config.get('threshold', 0.01) if config else 0.01

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "CustomSelector":
        """
        Aprende qué variables seleccionar.

        Edita este método para implementar tu lógica de selección.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento

        Returns:
            self: Retorna la instancia entrenada
        """
        # TODO: Implementar tu lógica de selección
        # Ejemplo simple con varianza:
        # from sklearn.feature_selection import VarianceThreshold
        # selector = VarianceThreshold(threshold=0.01)
        # selector.fit(X)
        # self.selected_features_ = X.columns[selector.get_support()].tolist()

        # Ejemplo con correlación:
        # corr_matrix = X.corr().abs()
        # upper_triangle = corr_matrix.where(
        #     np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        # )
        # to_drop = [column for column in upper_triangle.columns if any(upper_triangle[column] > 0.95)]
        # self.selected_features_ = [col for col in X.columns if col not in to_drop]

        raise NotImplementedError("Implementa el método fit() en tu selector")

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma X dejando solo las variables seleccionadas.

        Args:
            X: DataFrame a transformar

        Returns:
            pd.DataFrame: DataFrame con variables seleccionadas
        """
        if self.selected_features_ is None:
            raise ValueError("Debes llamar a fit() antes de transform()")

        return X[self.selected_features_]
