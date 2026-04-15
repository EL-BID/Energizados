"""
Plots Module for Energizados Framework.

Generates visualizations for model evaluation.
"""

import base64
import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, roc_curve

matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# ── Theme palette ──────────────────────────────────────────────────────────────
THEME_COLORS = {
    "primary": "#667eea",
    "secondary": "#764ba2",
    "positive": "#28a745",
    "negative": "#dc3545",
    "warning": "#ffc107",
    "neutral": "#6c757d",
}


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

        # Consistent font and grid defaults for all charts
        plt.rcParams.update(
            {
                "font.family": "sans-serif",
                "axes.grid": True,
                "grid.alpha": 0.3,
                "axes.spines.top": False,
                "axes.spines.right": False,
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_figure(self, filename: str, save_path: Optional[str] = None) -> str:
        """Saves the current figure, closes it, and returns the path."""
        path = save_path or str(self.output_dir / filename)
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        logger.info(f"Plot saved to: {path}")
        return path

    def _figure_to_base64(self) -> str:
        """Converts the current matplotlib figure to a base64 PNG data URI."""
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        buf.close()
        return f"data:image/png;base64,{b64}"

    def _save_figure_embedded(
        self, filename: str, save_path: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Saves the current figure to disk AND returns a base64 data URI.

        Returns:
            Tuple of (file_path, base64_data_uri)
        """
        b64_uri = self._figure_to_base64()
        path = save_path or str(self.output_dir / filename)
        # Write the PNG file as well (for backwards compatibility)
        with open(path, "wb") as f:
            # Decode b64 back to bytes
            _, b64data = b64_uri.split(",", 1)
            f.write(base64.b64decode(b64data))
        plt.close()
        logger.info(f"Plot saved to: {path}")
        return path, b64_uri

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
        plt.plot(
            fpr,
            tpr,
            color=THEME_COLORS["primary"],
            lw=2,
            label=f"ROC curve (AUC = {auc_score:.4f})",
        )
        plt.plot(
            [0, 1], [0, 1], color=THEME_COLORS["neutral"], lw=2, linestyle="--", label="Random"
        )
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title("Receiver Operating Characteristic (ROC) Curve")
        plt.legend(loc="lower right")

        return self._save_figure("roc_curve.png", save_path)

    def roc_curve_plot_embedded(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        auc_score: float,
        save_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generates ROC curve, saves to disk and returns (path, base64_uri)."""
        fpr, tpr, _ = roc_curve(y_true, y_proba)

        plt.figure(figsize=(8, 6))
        plt.plot(
            fpr,
            tpr,
            color=THEME_COLORS["primary"],
            lw=2,
            label=f"ROC curve (AUC = {auc_score:.4f})",
        )
        plt.plot(
            [0, 1], [0, 1], color=THEME_COLORS["neutral"], lw=2, linestyle="--", label="Random"
        )
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title("Receiver Operating Characteristic (ROC) Curve")
        plt.legend(loc="lower right")

        return self._save_figure_embedded("roc_curve.png", save_path)

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
        plt.plot(recall, precision, color=THEME_COLORS["secondary"], lw=2)
        plt.xlabel("Recall")
        plt.ylabel("Precision")
        plt.title("Precision-Recall Curve")

        return self._save_figure("precision_recall_curve.png", save_path)

    def precision_recall_plot_embedded(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        save_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generates PR curve, saves to disk and returns (path, base64_uri)."""
        precision, recall, _ = precision_recall_curve(y_true, y_proba)

        plt.figure(figsize=(8, 6))
        plt.plot(recall, precision, color=THEME_COLORS["secondary"], lw=2)
        plt.xlabel("Recall")
        plt.ylabel("Precision")
        plt.title("Precision-Recall Curve")

        return self._save_figure_embedded("precision_recall_curve.png", save_path)

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
        import matplotlib.colors as mcolors

        plt.figure(figsize=(8, 6))
        # Use primary color as base for colormap
        cmap = mcolors.LinearSegmentedColormap.from_list(
            "primary_cmap", ["#ffffff", THEME_COLORS["primary"]]
        )
        plt.imshow(cm, interpolation="nearest", cmap=cmap)
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

    def confusion_matrix_plot_embedded(
        self,
        cm: np.ndarray,
        save_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generates confusion matrix heatmap, saves and returns (path, base64_uri)."""
        import matplotlib.colors as mcolors

        plt.figure(figsize=(8, 6))
        cmap = mcolors.LinearSegmentedColormap.from_list(
            "primary_cmap", ["#ffffff", THEME_COLORS["primary"]]
        )
        plt.imshow(cm, interpolation="nearest", cmap=cmap)
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

        return self._save_figure_embedded("confusion_matrix.png", save_path)

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
        cumulative_gain = gains_data["cumulative_gain"]
        cumulative_population = gains_data["cumulative_population"]

        plt.figure(figsize=(8, 6))
        plt.plot(
            cumulative_population,
            cumulative_gain,
            marker="o",
            linestyle="-",
            color=THEME_COLORS["positive"],
            lw=2,
        )
        plt.plot([0, 1], [0, 1], linestyle="--", color=THEME_COLORS["neutral"], label="Random")
        plt.xlabel("Cumulative Population")
        plt.ylabel("Cumulative Gain")
        plt.title("Cumulative Gains Curve")
        plt.legend()

        return self._save_figure("cumulative_gains.png", save_path)

    def cumulative_gains_plot_embedded(
        self,
        gains_data: Dict,
        save_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generates cumulative gains curve, saves and returns (path, base64_uri)."""
        cumulative_gain = gains_data["cumulative_gain"]
        cumulative_population = gains_data["cumulative_population"]

        plt.figure(figsize=(8, 6))
        plt.plot(
            cumulative_population,
            cumulative_gain,
            marker="o",
            linestyle="-",
            color=THEME_COLORS["positive"],
            lw=2,
        )
        plt.plot([0, 1], [0, 1], linestyle="--", color=THEME_COLORS["neutral"], label="Random")
        plt.xlabel("Cumulative Population")
        plt.ylabel("Cumulative Gain")
        plt.title("Cumulative Gains Curve")
        plt.legend()

        return self._save_figure_embedded("cumulative_gains.png", save_path)

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
        plt.plot(
            cumulative_population,
            lifts,
            marker="o",
            linestyle="-",
            color=THEME_COLORS["primary"],
            lw=2,
            label="Model",
        )
        plt.axhline(y=1.0, linestyle="--", color=THEME_COLORS["neutral"], label="Random (lift=1)")
        plt.xlabel("Cumulative Population")
        plt.ylabel("Lift")
        plt.title("Lift Chart")
        plt.legend()

        return self._save_figure("lift_chart.png", save_path)

    def lift_chart_plot_embedded(
        self,
        gains_data: Dict,
        save_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generates lift chart, saves and returns (path, base64_uri)."""
        cumulative_gain = gains_data["cumulative_gain"]
        cumulative_population = gains_data["cumulative_population"]

        lifts = [g / p if p > 0 else 0 for g, p in zip(cumulative_gain, cumulative_population)]

        plt.figure(figsize=(8, 6))
        plt.plot(
            cumulative_population,
            lifts,
            marker="o",
            linestyle="-",
            color=THEME_COLORS["primary"],
            lw=2,
            label="Model",
        )
        plt.axhline(y=1.0, linestyle="--", color=THEME_COLORS["neutral"], label="Random (lift=1)")
        plt.xlabel("Cumulative Population")
        plt.ylabel("Lift")
        plt.title("Lift Chart")
        plt.legend()

        return self._save_figure_embedded("lift_chart.png", save_path)

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
        plt.plot(
            bin_stats["y_proba"],
            bin_stats["y_true"],
            marker="o",
            linestyle="-",
            color=THEME_COLORS["primary"],
            lw=2,
        )
        plt.plot(
            [0, 1],
            [0, 1],
            linestyle="--",
            color=THEME_COLORS["neutral"],
            label="Perfect Calibration",
        )
        plt.xlabel("Mean Predicted Probability")
        plt.ylabel("True Positive Rate")
        plt.title("Calibration Curve")
        plt.legend()

        return self._save_figure("calibration_curve.png", save_path)

    def calibration_plot_embedded(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        n_bins: int = 10,
        save_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generates calibration plot, saves and returns (path, base64_uri)."""
        df = pd.DataFrame({"y_true": y_true, "y_proba": y_proba})
        df["bin"] = pd.cut(df["y_proba"], bins=n_bins, labels=False)
        bin_stats = df.groupby("bin").agg({"y_true": "mean", "y_proba": "mean"}).reset_index()

        plt.figure(figsize=(8, 6))
        plt.plot(
            bin_stats["y_proba"],
            bin_stats["y_true"],
            marker="o",
            linestyle="-",
            color=THEME_COLORS["primary"],
            lw=2,
        )
        plt.plot(
            [0, 1],
            [0, 1],
            linestyle="--",
            color=THEME_COLORS["neutral"],
            label="Perfect Calibration",
        )
        plt.xlabel("Mean Predicted Probability")
        plt.ylabel("True Positive Rate")
        plt.title("Calibration Curve")
        plt.legend()

        return self._save_figure_embedded("calibration_curve.png", save_path)

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

        plt.hist(
            proba_0,
            bins=50,
            alpha=0.5,
            label="Negative Class",
            color=THEME_COLORS["primary"],
            density=True,
        )
        plt.hist(
            proba_1,
            bins=50,
            alpha=0.5,
            label="Positive Class",
            color=THEME_COLORS["negative"],
            density=True,
        )

        plt.xlabel("Predicted Probability")
        plt.ylabel("Density")
        plt.title("Distribution of Predicted Probabilities by Class")
        plt.legend()

        return self._save_figure("probability_distribution.png", save_path)

    def probability_distribution_plot_embedded(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        save_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generates probability distribution, saves and returns (path, base64_uri)."""
        plt.figure(figsize=(10, 6))

        proba_0 = y_proba[y_true == 0]
        proba_1 = y_proba[y_true == 1]

        plt.hist(
            proba_0,
            bins=50,
            alpha=0.5,
            label="Negative Class",
            color=THEME_COLORS["primary"],
            density=True,
        )
        plt.hist(
            proba_1,
            bins=50,
            alpha=0.5,
            label="Positive Class",
            color=THEME_COLORS["negative"],
            density=True,
        )

        plt.xlabel("Predicted Probability")
        plt.ylabel("Density")
        plt.title("Distribution of Predicted Probabilities by Class")
        plt.legend()

        return self._save_figure_embedded("probability_distribution.png", save_path)

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
        plt.barh(range(n), top_importances[::-1], color=THEME_COLORS["primary"])
        plt.yticks(range(n), top_features[::-1])
        plt.xlabel("Importance")
        plt.title(f"Feature Importance (Top {n})")
        plt.tight_layout()

        return self._save_figure("feature_importance.png", save_path)

    def feature_importance_plot_embedded(
        self,
        feature_names: List[str],
        importances: np.ndarray,
        top_n: int = 20,
        save_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generates feature importance chart, saves and returns (path, base64_uri)."""
        importances = np.asarray(importances)
        n = min(top_n, len(feature_names), len(importances))

        indices = np.argsort(importances)[::-1][:n]
        top_features = [feature_names[i] for i in indices]
        top_importances = importances[indices]

        fig_height = max(6, n * 0.35)
        plt.figure(figsize=(10, fig_height))
        plt.barh(range(n), top_importances[::-1], color=THEME_COLORS["primary"])
        plt.yticks(range(n), top_features[::-1])
        plt.xlabel("Importance")
        plt.title(f"Feature Importance (Top {n})")
        plt.tight_layout()

        return self._save_figure_embedded("feature_importance.png", save_path)

    def threshold_sweep_plot(
        self,
        threshold_metrics: Dict,
        current_threshold: float = 0.5,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generates threshold sweep chart showing precision, recall, F1 vs threshold.

        Args:
            threshold_metrics: Dict with thresholds, precisions, recalls, f1s lists
            current_threshold: The threshold currently in use (vertical line)
            save_path: Path to save (optional)

        Returns:
            str: Path where plot was saved
        """
        thresholds = threshold_metrics.get("thresholds", [])
        precisions = threshold_metrics.get("precisions", [])
        recalls = threshold_metrics.get("recalls", [])
        f1s = threshold_metrics.get("f1s", [])

        plt.figure(figsize=(10, 6))
        plt.plot(thresholds, precisions, label="Precision", color=THEME_COLORS["primary"], lw=2)
        plt.plot(thresholds, recalls, label="Recall", color=THEME_COLORS["secondary"], lw=2)
        plt.plot(thresholds, f1s, label="F1", color=THEME_COLORS["positive"], lw=2, linestyle="--")
        plt.axvline(
            x=current_threshold,
            color=THEME_COLORS["negative"],
            linestyle=":",
            lw=2,
            label=f"Current ({current_threshold:.2f})",
        )
        plt.xlabel("Threshold")
        plt.ylabel("Score")
        plt.title("Metrics vs Classification Threshold")
        plt.legend()
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])

        return self._save_figure("threshold_sweep.png", save_path)

    def threshold_sweep_plot_embedded(
        self,
        threshold_metrics: Dict,
        current_threshold: float = 0.5,
        save_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generates threshold sweep chart, saves and returns (path, base64_uri)."""
        thresholds = threshold_metrics.get("thresholds", [])
        precisions = threshold_metrics.get("precisions", [])
        recalls = threshold_metrics.get("recalls", [])
        f1s = threshold_metrics.get("f1s", [])

        plt.figure(figsize=(10, 6))
        plt.plot(thresholds, precisions, label="Precision", color=THEME_COLORS["primary"], lw=2)
        plt.plot(thresholds, recalls, label="Recall", color=THEME_COLORS["secondary"], lw=2)
        plt.plot(thresholds, f1s, label="F1", color=THEME_COLORS["positive"], lw=2, linestyle="--")
        plt.axvline(
            x=current_threshold,
            color=THEME_COLORS["negative"],
            linestyle=":",
            lw=2,
            label=f"Current ({current_threshold:.2f})",
        )
        plt.xlabel("Threshold")
        plt.ylabel("Score")
        plt.title("Metrics vs Classification Threshold")
        plt.legend()
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])

        return self._save_figure_embedded("threshold_sweep.png", save_path)

    # ------------------------------------------------------------------
    # SHAP explainability plots
    # ------------------------------------------------------------------

    def shap_summary_plot_embedded(
        self,
        shap_values: np.ndarray,
        X: pd.DataFrame,
        feature_names: List[str],
        top_n: int = 20,
    ) -> Tuple[str, str]:
        """Generate SHAP summary (beeswarm) plot.

        Args:
            shap_values: SHAP values array
            X: Feature data used for SHAP
            feature_names: List of feature names
            top_n: Number of top features to show

        Returns:
            Tuple of (file_path, base64_data_uri)
        """
        import shap

        mean_abs = np.abs(shap_values).mean(axis=0)
        top_idx = np.argsort(mean_abs)[-top_n:][::-1]

        shap_sub = shap_values[:, top_idx]
        X_sub = X.iloc[:, top_idx] if hasattr(X, "iloc") else X[:, top_idx]

        shap.summary_plot(
            shap_sub,
            features=X_sub,
            feature_names=[feature_names[i] for i in top_idx],
            show=False,
            max_display=top_n,
        )

        plt.title(f"SHAP Summary Plot (Top {top_n} Features)")
        plt.tight_layout()

        return self._save_figure_embedded("shap_summary.png")

    def shap_bar_plot_embedded(
        self,
        shap_values: np.ndarray,
        feature_names: List[str],
        top_n: int = 20,
    ) -> Tuple[str, str]:
        """Generate SHAP bar plot (mean absolute SHAP values).

        Args:
            shap_values: SHAP values array
            feature_names: List of feature names
            top_n: Number of top features to show

        Returns:
            Tuple of (file_path, base64_data_uri)
        """
        import shap

        shap.summary_plot(
            shap_values,
            features=None,
            feature_names=feature_names,
            plot_type="bar",
            show=False,
            max_display=top_n,
        )

        plt.title(f"SHAP Feature Importance (Top {top_n} Features)")
        plt.tight_layout()

        return self._save_figure_embedded("shap_bar.png")
