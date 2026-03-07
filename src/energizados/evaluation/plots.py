"""
Plots Module for Energizados Framework.

Generates visualizations for model evaluation.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, roc_curve

logger = logging.getLogger(__name__)


class PlotGenerator:
    """
    Plot generator for model evaluation.

    Args:
        output_dir: Directory where to save plots

    Example:
        >>> plotter = PlotGenerator("reports/evaluation/")
        >>> plotter.roc_curve_plot(y_true, y_proba, auc_score)
        >>> plotter.confusion_matrix_plot(cm)
    """

    def __init__(self, output_dir: str = "reports/evaluation/"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        plt.style.use("default")

    # ------------------------------------------------------------------
    # Internal helper (MEJORAS P3-12)
    # ------------------------------------------------------------------

    def _save_figure(self, filename: str, save_path: Optional[str] = None) -> str:
        """Saves the current figure, closes it, and returns the path."""
        path = save_path or str(self.output_dir / filename)
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        logger.info(f"Plot saved to: {path}")
        return path

    # ------------------------------------------------------------------
    # Standard evaluation plots
    # ------------------------------------------------------------------

    def roc_curve_plot(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        auc_score: float,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates ROC curve.

        Args:
            y_true: True values
            y_proba: Predicted probabilities
            auc_score: AUC score
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        fpr, tpr, _ = roc_curve(y_true, y_proba)

        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, color="darkorange", lw=2, label=f"ROC curve (AUC = {auc_score:.4f})")
        plt.plot([0, 1], [0, 1], color="navy", lw=2, linestyle="--", label="Random")
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title("Receiver Operating Characteristic (ROC) Curve")
        plt.legend(loc="lower right")
        plt.grid(True, alpha=0.3)

        return self._save_figure("roc_curve.png", save_path)

    def precision_recall_plot(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates Precision-Recall curve.

        Args:
            y_true: True values
            y_proba: Predicted probabilities
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        precision, recall, _ = precision_recall_curve(y_true, y_proba)

        plt.figure(figsize=(8, 6))
        plt.plot(recall, precision, color="blue", lw=2)
        plt.xlabel("Recall")
        plt.ylabel("Precision")
        plt.title("Precision-Recall Curve")
        plt.grid(True, alpha=0.3)

        return self._save_figure("precision_recall_curve.png", save_path)

    def confusion_matrix_plot(
        self,
        cm: np.ndarray,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates confusion matrix heatmap.

        Args:
            cm: Confusion matrix
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        plt.figure(figsize=(8, 6))
        plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
        plt.title("Confusion Matrix")
        plt.colorbar()

        thresh = cm.max() / 2.0
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(
                    j,
                    i,
                    format(cm[i, j], "d"),
                    horizontalalignment="center",
                    color="white" if cm[i, j] > thresh else "black",
                )

        plt.ylabel("True label")
        plt.xlabel("Predicted label")
        plt.xticks([0, 1], ["Negative", "Positive"])
        plt.yticks([0, 1], ["Negative", "Positive"])

        return self._save_figure("confusion_matrix.png", save_path)

    def cumulative_gains_plot(
        self,
        gains_data: Dict,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates cumulative gains curve.

        Args:
            gains_data: Dictionary with deciles, cumulative_gain and cumulative_population
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        # _deciles removed — not used in the plot (MEJORAS P0-2)
        cumulative_gain = gains_data["cumulative_gain"]
        cumulative_population = gains_data["cumulative_population"]

        plt.figure(figsize=(8, 6))
        plt.plot(cumulative_population, cumulative_gain, marker="o", linestyle="-", color="darkgreen", lw=2)
        plt.plot([0, 1], [0, 1], linestyle="--", color="navy", label="Random")
        plt.xlabel("Cumulative Population")
        plt.ylabel("Cumulative Gain")
        plt.title("Cumulative Gains Curve")
        plt.grid(True, alpha=0.3)
        plt.legend()

        return self._save_figure("cumulative_gains.png", save_path)

    def lift_chart_plot(
        self,
        gains_data: Dict,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates lift chart from cumulative gains data (MEJORAS P4-16).

        Lift = cumulative_gain / cumulative_population for each population decile.
        A lift of 2.0 at 10% means the model finds twice as many frauds as random.

        Args:
            gains_data: Dictionary with cumulative_gain and cumulative_population
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        cumulative_gain = gains_data["cumulative_gain"]
        cumulative_population = gains_data["cumulative_population"]

        lifts = [g / p if p > 0 else 0 for g, p in zip(cumulative_gain, cumulative_population)]

        plt.figure(figsize=(8, 6))
        plt.plot(cumulative_population, lifts, marker="o", linestyle="-", color="darkblue", lw=2, label="Model")
        plt.axhline(y=1.0, linestyle="--", color="navy", label="Random (lift=1)")
        plt.xlabel("Cumulative Population")
        plt.ylabel("Lift")
        plt.title("Lift Chart")
        plt.grid(True, alpha=0.3)
        plt.legend()

        return self._save_figure("lift_chart.png", save_path)

    def calibration_plot(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        n_bins: int = 10,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates calibration plot.

        Args:
            y_true: True values
            y_proba: Predicted probabilities
            n_bins: Number of bins
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        df = pd.DataFrame({"y_true": y_true, "y_proba": y_proba})
        df["bin"] = pd.cut(df["y_proba"], bins=n_bins, labels=False)

        bin_stats = df.groupby("bin").agg({"y_true": "mean", "y_proba": "mean"}).reset_index()

        plt.figure(figsize=(8, 6))
        plt.plot(bin_stats["y_proba"], bin_stats["y_true"], marker="o", linestyle="-", color="darkorange", lw=2)
        plt.plot([0, 1], [0, 1], linestyle="--", color="navy", label="Perfect Calibration")
        plt.xlabel("Mean Predicted Probability")
        plt.ylabel("True Positive Rate")
        plt.title("Calibration Curve")
        plt.grid(True, alpha=0.3)
        plt.legend()

        return self._save_figure("calibration_curve.png", save_path)

    def probability_distribution_plot(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates probability distribution histogram.

        Args:
            y_true: True values
            y_proba: Predicted probabilities
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        plt.figure(figsize=(10, 6))

        proba_0 = y_proba[y_true == 0]
        proba_1 = y_proba[y_true == 1]

        plt.hist(proba_0, bins=50, alpha=0.5, label="Negative Class", color="blue", density=True)
        plt.hist(proba_1, bins=50, alpha=0.5, label="Positive Class", color="red", density=True)

        plt.xlabel("Predicted Probability")
        plt.ylabel("Density")
        plt.title("Distribution of Predicted Probabilities by Class")
        plt.legend()
        plt.grid(True, alpha=0.3)

        return self._save_figure("probability_distribution.png", save_path)

    def feature_importance_plot(
        self,
        feature_names: List[str],
        importances: np.ndarray,
        top_n: int = 20,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates feature importance bar chart (MEJORAS P2-8).

        Args:
            feature_names: List of feature names
            importances: Importance scores (one per feature)
            top_n: Maximum number of features to display
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        importances = np.asarray(importances)
        n = min(top_n, len(feature_names), len(importances))

        indices = np.argsort(importances)[::-1][:n]
        top_features = [feature_names[i] for i in indices]
        top_importances = importances[indices]

        fig_height = max(6, n * 0.35)
        plt.figure(figsize=(10, fig_height))
        plt.barh(range(n), top_importances[::-1], color="steelblue")
        plt.yticks(range(n), top_features[::-1])
        plt.xlabel("Importance")
        plt.title(f"Feature Importance (Top {n})")
        plt.grid(True, alpha=0.3, axis="x")
        plt.tight_layout()

        return self._save_figure("feature_importance.png", save_path)
