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
    roc_curve,
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


def find_optimal_threshold_youden(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """
    Finds optimal threshold using Youden's J statistic (maximizes sensitivity + specificity - 1).

    Args:
        y_true: True binary labels
        y_proba: Predicted probabilities

    Returns:
        float: Optimal threshold
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_proba)
    j_scores = tpr - fpr
    best_idx = np.argmax(j_scores)
    return float(thresholds[best_idx])


def find_optimal_threshold_f1(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """
    Finds optimal threshold by maximizing F1 score.

    Args:
        y_true: True binary labels
        y_proba: Predicted probabilities

    Returns:
        float: Optimal threshold
    """
    thresholds = np.linspace(0, 1, 101)
    best_f1 = 0.0
    best_thresh = 0.5
    for thresh in thresholds:
        y_pred = (y_proba >= thresh).astype(int)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh
    return float(best_thresh)


def find_optimal_threshold_recall_target(
    y_true: np.ndarray, y_proba: np.ndarray, target_recall: float = 0.8
) -> float:
    """
    Finds threshold that achieves the target recall (approximately).

    Uses Youden's J from the point on the ROC curve closest to the target recall.

    Args:
        y_true: True binary labels
        y_proba: Predicted probabilities
        target_recall: Target recall value (default: 0.8)

    Returns:
        float: Threshold that achieves approximately the target recall
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_proba)

    # Find the threshold closest to target recall
    idx = np.argmin(np.abs(tpr - target_recall))
    return float(thresholds[idx])


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
            results["cumulative_gain"].append(
                cumulative_positives / total_positives if total_positives > 0 else 0
            )
            results["cumulative_population"].append(cumulative_count / len(df))

        return results

    def segment_metrics(
        self,
        segments: np.ndarray,
        threshold_mode: str = "global",
        min_samples: int = 1,
        recall_target: float = 0.8,
    ) -> Dict:
        """
        Calculates metrics broken down by segment (MEJORAS P4-15).

        Args:
            segments: Array with segment values, aligned with y_true
            threshold_mode: How to determine threshold per segment.
                           "global" = use self.threshold for all segments
                           "youden" = find optimal threshold per segment using Youden's J
                           "f1_optimal" = find threshold that maximizes F1 per segment
                           "recall_target" = find threshold that achieves target recall
                           "segment" = alias for "youden" (optimal per-segment threshold)
            min_samples: Minimum number of samples in a segment to compute metrics
            recall_target: Target recall when threshold_mode="recall_target"

        Returns:
            Dict mapping segment_value -> metrics dict with n_samples, n_positives,
            auc, precision, recall, f1, threshold, threshold_mode
        """
        segments = np.asarray(segments)
        results = {}

        # Resolve threshold alias BEFORE the loop to avoid parameter mutation
        # "segment" is a friendly alias for "youden" (optimal per-segment threshold)
        effective_mode = "youden" if threshold_mode == "segment" else threshold_mode

        for segment_value in np.unique(segments):
            mask = segments == segment_value
            n_samples = int(mask.sum())

            if n_samples < min_samples:
                logger.debug(
                    f"Skipping segment '{segment_value}': {n_samples} samples < {min_samples} min_samples"
                )
                continue

            y_true_seg = self.y_true[mask]
            y_proba_seg = self.y_proba[mask]

            # Determine threshold for this segment
            if effective_mode == "global":
                seg_threshold = self.threshold
            elif effective_mode == "youden":
                seg_threshold = find_optimal_threshold_youden(y_true_seg, y_proba_seg)
            elif effective_mode == "f1_optimal":
                seg_threshold = find_optimal_threshold_f1(y_true_seg, y_proba_seg)
            elif effective_mode == "recall_target":
                seg_threshold = find_optimal_threshold_recall_target(
                    y_true_seg, y_proba_seg, recall_target
                )
            else:
                logger.warning(f"Unknown threshold_mode '{effective_mode}', using global")
                seg_threshold = self.threshold

            y_pred_seg = (y_proba_seg >= seg_threshold).astype(int)

            seg_calc = Metrics(y_true_seg, y_pred_seg, y_proba_seg, seg_threshold)

            results[str(segment_value)] = {
                "n_samples": n_samples,
                "n_positives": int(y_true_seg.sum()),
                "positive_rate": float(y_true_seg.mean()),
                "auc": seg_calc.auc(),
                "precision": seg_calc.precision(),
                "recall": seg_calc.recall(),
                "f1": seg_calc.f1(),
                "threshold": seg_threshold,
                "threshold_mode": effective_mode,
            }

        return results

    def get_threshold_metrics(self) -> Dict:
        """
        Calculates metrics for different thresholds.

        Returns:
            Dict with lists of thresholds and their metrics
        """
        return compute_threshold_metrics(self.y_true, self.y_proba)
