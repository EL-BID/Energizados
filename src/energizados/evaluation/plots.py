"""
Plots Module for Energizados Framework.

Generates visualizations for model evaluation.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

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
        >>> plotter.roc_curve(y_true, y_proba)
        >>> plotter.confusion_matrix_plot(cm)
    """

    def __init__(self, output_dir: str = "reports/evaluation/"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Configure style
        plt.style.use("default")

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

        path = save_path or str(self.output_dir / "roc_curve.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()

        logger.info(f"ROC curve saved to: {path}")
        return path

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

        path = save_path or str(self.output_dir / "precision_recall_curve.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()

        logger.info(f"Precision-Recall curve saved to: {path}")
        return path

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
                plt.text(j, i, format(cm[i, j], "d"), horizontalalignment="center", color="white" if cm[i, j] > thresh else "black")

        plt.ylabel("True label")
        plt.xlabel("Predicted label")
        plt.xticks([0, 1], ["Negative", "Positive"])
        plt.yticks([0, 1], ["Negative", "Positive"])

        path = save_path or str(self.output_dir / "confusion_matrix.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()

        logger.info(f"Confusion matrix saved to: {path}")
        return path

    def cumulative_gains_plot(
        self,
        gains_data: Dict,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates cumulative gains curve.

        Args:
            gains_data: Dictionary with deciles and cumulative_gain
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        _deciles = gains_data["deciles"]  # noqa: F841 - reference only
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

        path = save_path or str(self.output_dir / "cumulative_gains.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()

        logger.info(f"Cumulative gains saved to: {path}")
        return path

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
        # Create bins
        df = pd.DataFrame({"y_true": y_true, "y_proba": y_proba})
        df["bin"] = pd.cut(df["y_proba"], bins=n_bins, labels=False)

        # Calculate statistics per bin
        bin_stats = df.groupby("bin").agg({"y_true": "mean", "y_proba": "mean"}).reset_index()

        plt.figure(figsize=(8, 6))
        plt.plot(bin_stats["y_proba"], bin_stats["y_true"], marker="o", linestyle="-", color="darkorange", lw=2)
        plt.plot([0, 1], [0, 1], linestyle="--", color="navy", label="Perfect Calibration")
        plt.xlabel("Mean Predicted Probability")
        plt.ylabel("True Positive Rate")
        plt.title("Calibration Curve")
        plt.grid(True, alpha=0.3)
        plt.legend()

        path = save_path or str(self.output_dir / "calibration_curve.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()

        logger.info(f"Calibration curve saved to: {path}")
        return path

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

        # Separate probabilities by class
        proba_0 = y_proba[y_true == 0]
        proba_1 = y_proba[y_true == 1]

        plt.hist(proba_0, bins=50, alpha=0.5, label="Negative Class", color="blue", density=True)
        plt.hist(proba_1, bins=50, alpha=0.5, label="Positive Class", color="red", density=True)

        plt.xlabel("Predicted Probability")
        plt.ylabel("Density")
        plt.title("Distribution of Predicted Probabilities by Class")
        plt.legend()
        plt.grid(True, alpha=0.3)

        path = save_path or str(self.output_dir / "probability_distribution.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()

        logger.info(f"Probability distribution saved to: {path}")
        return path
