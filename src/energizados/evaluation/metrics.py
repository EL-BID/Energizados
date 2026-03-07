"""
Metrics Module for Energizados Framework.

Provides functions to calculate model evaluation metrics.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
)
from sklearn.metrics import confusion_matrix as sklearn_confusion_matrix
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


def compute_threshold_metrics(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_thresholds: int = 101,
) -> Dict:
    """
    Computes precision, recall and f1 across a range of thresholds.

    Standalone function used by both Metrics.get_threshold_metrics() and
    ThresholdCalibrator to avoid coupling (MEJORAS P3-13).

    Args:
        y_true: True binary labels
        y_proba: Predicted probabilities
        n_thresholds: Number of thresholds to evaluate (default: 101)

    Returns:
        Dict with thresholds, precisions, recalls and f1s lists
    """
    thresholds = np.linspace(0, 1, n_thresholds)
    precisions, recalls, f1s = [], [], []

    for thresh in thresholds:
        y_pred_thresh = (y_proba >= thresh).astype(int)
        precisions.append(precision_score(y_true, y_pred_thresh, zero_division=0))
        recalls.append(recall_score(y_true, y_pred_thresh, zero_division=0))
        f1s.append(f1_score(y_true, y_pred_thresh, zero_division=0))

    return {
        "thresholds": thresholds.tolist(),
        "precisions": precisions,
        "recalls": recalls,
        "f1s": f1s,
    }


class Metrics:
    """
    Evaluation metrics calculator.

    Args:
        y_true: True values
        y_pred: Binary predictions
        y_proba: Predicted probabilities
        threshold: Threshold for binary classification

    Example:
        >>> metrics = Metrics(y_true, y_pred, y_proba)
        >>> results = metrics.calculate_all()
    """

    _DEFAULT_METRICS = ["auc", "precision", "recall", "f1", "confusion_matrix", "accuracy"]

    def __init__(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray,
        threshold: float = 0.5,
    ):
        self.y_true = np.asarray(y_true)
        self.y_pred = np.asarray(y_pred)
        self.y_proba = np.asarray(y_proba)
        self.threshold = threshold

    def calculate_all(self, metrics_list: Optional[List[str]] = None) -> Dict:
        """
        Calculates all requested metrics.

        Args:
            metrics_list: List of metrics to calculate.
                         If None, calculates all available.

        Returns:
            Dict: Dictionary with calculated metrics
        """
        if metrics_list is None:
            metrics_list = self._DEFAULT_METRICS

        # Dict dispatch avoids open-ended if/elif and makes adding metrics easy (MEJORAS P2-7)
        dispatch = {
            "auc": self.auc,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "accuracy": self.accuracy,
            "confusion_matrix": self.confusion_matrix,
            "cumulative_gains": self.cumulative_gains,
        }

        results = {}
        for metric_name in metrics_list:
            if metric_name in dispatch:
                results[metric_name] = dispatch[metric_name]()
            else:
                logger.warning(f"Unknown metric: '{metric_name}', skipping.")

        return results

    def auc(self) -> float:
        """Calculates AUC-ROC."""
        try:
            return roc_auc_score(self.y_true, self.y_proba)
        except ValueError as e:
            logger.warning(f"Could not calculate AUC: {e}")
            return 0.0

    def precision(self) -> float:
        """Calculates precision."""
        return precision_score(self.y_true, self.y_pred, zero_division=0)

    def recall(self) -> float:
        """Calculates recall (sensitivity)."""
        return recall_score(self.y_true, self.y_pred, zero_division=0)

    def f1(self) -> float:
        """Calculates F1-score."""
        return f1_score(self.y_true, self.y_pred, zero_division=0)

    def accuracy(self) -> float:
        """Calculates accuracy."""
        return accuracy_score(self.y_true, self.y_pred)

    def confusion_matrix(self) -> Dict:
        """
        Calculates confusion matrix.

        Returns:
            Dict with tp, fp, fn, tn and matrix
        """
        # Use aliased import to avoid name shadowing with this method (MEJORAS P0-1)
        cm = sklearn_confusion_matrix(self.y_true, self.y_pred)
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
        Calculates cumulative gains curve.

        Args:
            n_bins: Number of bins for deciles

        Returns:
            Dict with deciles and cumulative gains
        """
        df = pd.DataFrame({"y_true": self.y_true, "y_proba": self.y_proba})
        df = df.sort_values("y_proba", ascending=False).reset_index(drop=True)

        # Guard against n_bins > len(df) which would make bin_size = 0 (MEJORAS P1-6)
        n_bins = min(n_bins, len(df))
        bin_size = max(1, len(df) // n_bins)

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
            cumulative_positives += bin_df["y_true"].sum()
            cumulative_count += len(bin_df)

            results["deciles"].append(i + 1)
            results["cumulative_gain"].append(cumulative_positives / total_positives if total_positives > 0 else 0)
            results["cumulative_population"].append(cumulative_count / len(df))

        return results

    def segment_metrics(self, segments: np.ndarray) -> Dict:
        """
        Calculates metrics broken down by segment (MEJORAS P4-15).

        Args:
            segments: Array with segment values, aligned with y_true

        Returns:
            Dict mapping segment_value -> metrics dict (count, positive_rate, auc, precision, recall, f1)
        """
        segments = np.asarray(segments)
        results = {}

        for segment_value in np.unique(segments):
            mask = segments == segment_value
            if mask.sum() == 0:
                continue

            seg_calc = Metrics(
                self.y_true[mask],
                self.y_pred[mask],
                self.y_proba[mask],
                self.threshold,
            )
            results[str(segment_value)] = {
                "count": int(mask.sum()),
                "positive_rate": float(self.y_true[mask].mean()),
                "auc": seg_calc.auc(),
                "precision": seg_calc.precision(),
                "recall": seg_calc.recall(),
                "f1": seg_calc.f1(),
            }

        return results

    def get_threshold_metrics(self) -> Dict:
        """
        Calculates metrics for different thresholds.

        Returns:
            Dict with lists of thresholds and their metrics
        """
        return compute_threshold_metrics(self.y_true, self.y_proba)
