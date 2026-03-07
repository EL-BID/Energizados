"""
Threshold Calibration Module for Energizados Framework.

Calibrates the classification threshold using the validation set,
avoiding using the test set for hyperparameter selection.
"""

import logging
from typing import Dict

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score

from energizados.evaluation.metrics import compute_threshold_metrics

logger = logging.getLogger(__name__)


class ThresholdCalibrator:
    """
    Calibrates the classification threshold using the validation set.

    Supported methods:
    - cost_benefit: minimizes weighted total cost FP/FN (default)
    - operational: sets the number of alarms per operational capacity
    - precision_recall: highest threshold that maintains recall >= min_recall

    Args:
        method: Calibration method ('cost_benefit', 'operational', 'precision_recall')
        **params: Parameters for the selected method

    Parameters by method:
        cost_benefit:
            cost_fp (float): Cost of a false positive (default: 1)
            cost_fn (float): Cost of a false negative (default: 10)
        operational:
            capacity (int): Maximum alarms per period (default: 100)
        precision_recall:
            min_recall (float): Minimum required recall (default: 0.80)

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
        Calibrates the threshold and returns the result.

        Args:
            y_true: True labels (binary array)
            y_proba: Predicted probabilities (float array [0,1])

        Returns:
            Dict with:
              - threshold: optimal float found
              - method: str method name
              - params: dict parameters used
              - metrics_at_threshold: dict with precision/recall/f1 at threshold
              - search_results: table of explored thresholds (for plots)
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
            raise ValueError(f"Unknown calibration method: '{self.method}'. " f"Options: 'cost_benefit', 'operational', 'precision_recall'")

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _metrics_at(self, y_true: np.ndarray, y_proba: np.ndarray, threshold: float) -> Dict:
        """Calculates precision/recall/f1 for a given threshold."""
        y_pred = (y_proba >= threshold).astype(int)
        return {
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        }

    def _calibrate_operational(self, y_true: np.ndarray, y_proba: np.ndarray) -> Dict:
        """
        Sets the threshold to generate exactly `capacity` alarms.

        The calculated percentile ensures that only `capacity` samples exceed
        the threshold. If capacity >= n, threshold = 0 (alarm all).
        """
        capacity = int(self.params.get("capacity", 100))
        n = len(y_proba)

        pct = max(0.0, min(100.0, (1.0 - capacity / n) * 100.0))
        threshold = float(np.percentile(y_proba, pct))

        metrics = self._metrics_at(y_true, y_proba, threshold)
        n_alarms = int(np.sum(y_proba >= threshold))

        logger.info(f"Operational calibration: threshold={threshold:.4f}, alarms={n_alarms}/{n}")

        return {
            "threshold": threshold,
            "method": self.method,
            "params": {"capacity": capacity},
            "metrics_at_threshold": metrics,
            "search_results": None,
        }

    def _calibrate_cost_benefit(self, y_true: np.ndarray, y_proba: np.ndarray) -> Dict:
        """
        Minimizes weighted total cost: cost_fp * FP + cost_fn * FN.

        Uses compute_threshold_metrics() directly instead of instantiating Metrics
        with a dummy y_pred (MEJORAS P3-13).
        """
        cost_fp = float(self.params.get("cost_fp", 1))
        cost_fn = float(self.params.get("cost_fn", 10))

        search = compute_threshold_metrics(y_true, y_proba)

        thresholds = np.array(search["thresholds"])
        precisions = np.array(search["precisions"])
        recalls = np.array(search["recalls"])

        total_pos = float(np.sum(y_true))
        total_neg = float(len(y_true) - total_pos)

        # TP = recall * total_pos
        tp = recalls * total_pos
        # FP = TP/precision - TP  (when precision > 0, otherwise assume FP = total_neg)
        safe_prec = np.where(precisions > 0, precisions, 1.0)
        fp = np.where(precisions > 0, tp / safe_prec - tp, total_neg)
        fn = total_pos - tp

        costs = cost_fp * fp + cost_fn * fn
        best_idx = int(np.argmin(costs))
        threshold = float(thresholds[best_idx])

        metrics = self._metrics_at(y_true, y_proba, threshold)

        logger.info(
            f"Cost_benefit calibration: threshold={threshold:.4f}, " f"cost={costs[best_idx]:.1f} (cost_fp={cost_fp}, cost_fn={cost_fn})"
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
        Selects the highest threshold that maintains recall >= min_recall.

        Higher threshold → higher precision with guaranteed minimum recall.
        """
        from sklearn.metrics import precision_recall_curve

        min_recall = float(self.params.get("min_recall", 0.80))

        precisions, recalls, pr_thresholds = precision_recall_curve(y_true, y_proba)

        # precision_recall_curve: len(precisions) = len(recalls) = len(pr_thresholds) + 1
        # The last pair (precision=1, recall=0) has no associated threshold
        valid_mask = recalls[:-1] >= min_recall

        if not np.any(valid_mask):
            logger.warning(
                f"No threshold found with recall >= {min_recall}. " f"Maximum achievable recall: {recalls.max():.4f}. Using threshold=0.5."
            )
            threshold = 0.5
        else:
            # Among valid ones, choose the highest (maximizes precision)
            valid_thresholds = pr_thresholds[valid_mask]
            threshold = float(np.max(valid_thresholds))

        metrics = self._metrics_at(y_true, y_proba, threshold)

        logger.info(f"Precision_recall calibration: threshold={threshold:.4f}, " f"min_recall={min_recall}")

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
