"""
Metrics Module for Energizados Framework.

Proporciona funciones para calcular métricas de evaluación de modelos.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


class Metrics:
    """
    Calculador de métricas de evaluación.

    Args:
        y_true: Valores verdaderos
        y_pred: Predicciones binarias
        y_proba: Probabilidades predichas
        threshold: Umbral para clasificación binaria

    Example:
        >>> metrics = Metrics(y_true, y_pred, y_proba)
        >>> results = metrics.calculate_all()
    """

    def __init__(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray,
        threshold: float = 0.5,
    ):
        self.y_true = y_true
        self.y_pred = y_pred
        self.y_proba = y_proba
        self.threshold = threshold

    def calculate_all(self, metrics_list: Optional[List[str]] = None) -> Dict:
        """
        Calcula todas las métricas solicitadas.

        Args:
            metrics_list: Lista de métricas a calcular.
                         Si es None, calcula todas las disponibles.

        Returns:
            Dict: Diccionario con métricas calculadas
        """
        if metrics_list is None:
            metrics_list = ["auc", "precision", "recall", "f1", "confusion_matrix", "accuracy"]

        results = {}

        for metric_name in metrics_list:
            if metric_name == "auc":
                results["auc"] = self.auc()
            elif metric_name == "precision":
                results["precision"] = self.precision()
            elif metric_name == "recall":
                results["recall"] = self.recall()
            elif metric_name == "f1":
                results["f1"] = self.f1()
            elif metric_name == "confusion_matrix":
                results["confusion_matrix"] = self.confusion_matrix()
            elif metric_name == "accuracy":
                results["accuracy"] = self.accuracy()
            elif metric_name == "cumulative_gains":
                results["cumulative_gains"] = self.cumulative_gains()

        return results

    def auc(self) -> float:
        """Calcula el AUC-ROC."""
        try:
            return roc_auc_score(self.y_true, self.y_proba)
        except ValueError as e:
            logger.warning(f"No se pudo calcular AUC: {e}")
            return 0.0

    def precision(self) -> float:
        """Calcula la precisión."""
        return precision_score(self.y_true, self.y_pred, zero_division=0)

    def recall(self) -> float:
        """Calcula el recall (sensibilidad)."""
        return recall_score(self.y_true, self.y_pred, zero_division=0)

    def f1(self) -> float:
        """Calcula el F1-score."""
        return f1_score(self.y_true, self.y_pred, zero_division=0)

    def accuracy(self) -> float:
        """Calcula la exactitud."""
        return accuracy_score(self.y_true, self.y_pred)

    def confusion_matrix(self) -> Dict:
        """
        Calcula la matriz de confusión.

        Returns:
            Dict con tp, fp, fn, tn
        """
        cm = confusion_matrix(self.y_true, self.y_pred)
        tn, fp, fn, tp = cm.ravel()
        return {
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn),
            "matrix": cm.tolist(),
        }

    def cumulative_gains(self, n_bins: int = 10) -> Dict:
        """
        Calcula la curva de ganancias acumuladas.

        Args:
            n_bins: Número de bins para deciles

        Returns:
            Dict con deciles y ganancias acumuladas
        """
        # Crear DataFrame con verdaderos y probabilidades
        df = pd.DataFrame({"y_true": self.y_true, "y_proba": self.y_proba})

        # Ordenar por probabilidad descendente
        df = df.sort_values("y_proba", ascending=False).reset_index(drop=True)

        # Calcular tamaño de cada bin
        bin_size = len(df) // n_bins

        results = {
            "deciles": [],
            "cumulative_gain": [],
            "cumulative_population": [],
        }

        total_positives = df["y_true"].sum()
        cumulative_positives = 0
        cumulative_count = 0

        for i in range(n_bins):
            start_idx = i * bin_size
            end_idx = (i + 1) * bin_size if i < n_bins - 1 else len(df)

            bin_df = df.iloc[start_idx:end_idx]
            bin_positives = bin_df["y_true"].sum()
            cumulative_positives += bin_positives
            cumulative_count += len(bin_df)

            results["deciles"].append(i + 1)
            results["cumulative_gain"].append(cumulative_positives / total_positives if total_positives > 0 else 0)
            results["cumulative_population"].append(cumulative_count / len(df))

        return results

    def get_threshold_metrics(self) -> Dict:
        """
        Calcula métricas para diferentes umbrales.

        Returns:
            Dict con listas de thresholds y sus métricas
        """
        thresholds = np.linspace(0, 1, 101)
        precisions = []
        recalls = []
        f1s = []

        for thresh in thresholds:
            y_pred_thresh = (self.y_proba >= thresh).astype(int)
            precisions.append(precision_score(self.y_true, y_pred_thresh, zero_division=0))
            recalls.append(recall_score(self.y_true, y_pred_thresh, zero_division=0))
            f1s.append(f1_score(self.y_true, y_pred_thresh, zero_division=0))

        return {
            "thresholds": thresholds.tolist(),
            "precisions": precisions,
            "recalls": recalls,
            "f1s": f1s,
        }
