"""
Threshold Calibration Module for Energizados Framework.

Calibra el threshold de clasificación usando el validation set,
evitando usar el test set para selección de hiperparámetros.
"""

import logging
from typing import Dict

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score

logger = logging.getLogger(__name__)


class ThresholdCalibrator:
    """
    Calibra el threshold de clasificación usando el validation set.

    Métodos soportados:
    - cost_benefit: minimiza costo total ponderado FP/FN (default)
    - operational: fija la cantidad de alarmas por capacidad operativa
    - precision_recall: threshold más alto que mantiene recall >= min_recall

    Args:
        method: Método de calibración ('cost_benefit', 'operational', 'precision_recall')
        **params: Parámetros del método seleccionado

    Params por método:
        cost_benefit:
            cost_fp (float): Costo de un falso positivo (default: 1)
            cost_fn (float): Costo de un falso negativo (default: 10)
        operational:
            capacity (int): Máximo de alarmas por período (default: 100)
        precision_recall:
            min_recall (float): Recall mínimo requerido (default: 0.80)

    Example:
        >>> calibrator = ThresholdCalibrator(method="cost_benefit", cost_fp=1, cost_fn=10)
        >>> result = calibrator.calibrate(y_true, y_proba)
        >>> threshold = result["threshold"]
    """

    def __init__(self, method: str = "cost_benefit", **params):
        self.method = method
        self.params = params

    def calibrate(self, y_true: np.ndarray, y_proba: np.ndarray) -> Dict:
        """
        Calibra el threshold y retorna el resultado.

        Args:
            y_true: Etiquetas verdaderas (array binario)
            y_proba: Probabilidades predichas (array float [0,1])

        Returns:
            Dict con:
              - threshold: float óptimo encontrado
              - method: str nombre del método
              - params: dict parámetros usados
              - metrics_at_threshold: dict con precision/recall/f1 en val
              - search_results: tabla de thresholds explorados (para plots)
        """
        y_true = np.asarray(y_true)
        y_proba = np.asarray(y_proba)

        if self.method == "operational":
            return self._calibrate_operational(y_true, y_proba)
        elif self.method == "cost_benefit":
            return self._calibrate_cost_benefit(y_true, y_proba)
        elif self.method == "precision_recall":
            return self._calibrate_precision_recall(y_true, y_proba)
        else:
            raise ValueError(
                f"Método de calibración desconocido: '{self.method}'. " f"Opciones: 'cost_benefit', 'operational', 'precision_recall'"
            )

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    def _metrics_at(self, y_true: np.ndarray, y_proba: np.ndarray, threshold: float) -> Dict:
        """Calcula precision/recall/f1 para un threshold dado."""
        y_pred = (y_proba >= threshold).astype(int)
        return {
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        }

    def _calibrate_operational(self, y_true: np.ndarray, y_proba: np.ndarray) -> Dict:
        """
        Fija el threshold para generar exactamente `capacity` alarmas.

        El percentil calculado asegura que solo `capacity` muestras superen
        el threshold. Si capacity >= n, threshold = 0 (alarma en todos).
        """
        capacity = int(self.params.get("capacity", 100))
        n = len(y_proba)

        pct = max(0.0, min(100.0, (1.0 - capacity / n) * 100.0))
        threshold = float(np.percentile(y_proba, pct))

        metrics = self._metrics_at(y_true, y_proba, threshold)
        n_alarms = int(np.sum(y_proba >= threshold))

        logger.info(f"Calibración operational: threshold={threshold:.4f}, alarmas={n_alarms}/{n}")

        return {
            "threshold": threshold,
            "method": self.method,
            "params": {"capacity": capacity},
            "metrics_at_threshold": metrics,
            "search_results": None,
        }

    def _calibrate_cost_benefit(self, y_true: np.ndarray, y_proba: np.ndarray) -> Dict:
        """
        Minimiza el costo total ponderado: cost_fp * FP + cost_fn * FN.

        Reutiliza Metrics.get_threshold_metrics() para explorar 101 thresholds.
        """
        from energizados.evaluation.metrics import Metrics

        cost_fp = float(self.params.get("cost_fp", 1))
        cost_fn = float(self.params.get("cost_fn", 10))

        # Instanciar Metrics con y_pred dummy (no usado por get_threshold_metrics)
        dummy_pred = np.zeros_like(y_true, dtype=int)
        metrics_calc = Metrics(y_true, dummy_pred, y_proba)
        search = metrics_calc.get_threshold_metrics()

        thresholds = np.array(search["thresholds"])
        precisions = np.array(search["precisions"])
        recalls = np.array(search["recalls"])

        total_pos = float(np.sum(y_true))
        total_neg = float(len(y_true) - total_pos)

        # TP = recall * total_pos
        tp = recalls * total_pos
        # FP = TP/precision - TP  (cuando precision > 0, sino asumir FP = total_neg)
        safe_prec = np.where(precisions > 0, precisions, 1.0)
        fp = np.where(precisions > 0, tp / safe_prec - tp, total_neg)
        fn = total_pos - tp

        costs = cost_fp * fp + cost_fn * fn
        best_idx = int(np.argmin(costs))
        threshold = float(thresholds[best_idx])

        metrics = self._metrics_at(y_true, y_proba, threshold)

        logger.info(
            f"Calibración cost_benefit: threshold={threshold:.4f}, " f"costo={costs[best_idx]:.1f} (cost_fp={cost_fp}, cost_fn={cost_fn})"
        )

        return {
            "threshold": threshold,
            "method": self.method,
            "params": {"cost_fp": cost_fp, "cost_fn": cost_fn},
            "metrics_at_threshold": metrics,
            "search_results": {
                "thresholds": search["thresholds"],
                "costs": costs.tolist(),
                "precisions": search["precisions"],
                "recalls": search["recalls"],
                "f1s": search["f1s"],
            },
        }

    def _calibrate_precision_recall(self, y_true: np.ndarray, y_proba: np.ndarray) -> Dict:
        """
        Selecciona el threshold más alto que mantiene recall >= min_recall.

        Threshold más alto → mayor precisión con recall mínimo garantizado.
        """
        from sklearn.metrics import precision_recall_curve

        min_recall = float(self.params.get("min_recall", 0.80))

        precisions, recalls, pr_thresholds = precision_recall_curve(y_true, y_proba)

        # precision_recall_curve: len(precisions) = len(recalls) = len(pr_thresholds) + 1
        # El último par (precision=1, recall=0) no tiene threshold asociado
        valid_mask = recalls[:-1] >= min_recall

        if not np.any(valid_mask):
            logger.warning(
                f"No se encontró threshold con recall >= {min_recall}. "
                f"Recall máximo alcanzable: {recalls.max():.4f}. Usando threshold=0.5."
            )
            threshold = 0.5
        else:
            # Entre los válidos, elegir el más alto (maximiza precisión)
            valid_thresholds = pr_thresholds[valid_mask]
            threshold = float(np.max(valid_thresholds))

        metrics = self._metrics_at(y_true, y_proba, threshold)

        logger.info(f"Calibración precision_recall: threshold={threshold:.4f}, " f"min_recall={min_recall}")

        return {
            "threshold": threshold,
            "method": self.method,
            "params": {"min_recall": min_recall},
            "metrics_at_threshold": metrics,
            "search_results": {
                "thresholds": pr_thresholds.tolist(),
                "precisions": precisions[:-1].tolist(),
                "recalls": recalls[:-1].tolist(),
            },
        }
