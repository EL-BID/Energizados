"""
Static Plots Module - Energizados EDA Framework.

Generates static plots using matplotlib/seaborn for the EDA report.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class EDAStaticPlots:
    """
    Generates static EDA plots using matplotlib/seaborn.

    All methods save the plot to output_dir and return the file path.
    Each method wraps its body in try/except to avoid failing the full analysis.

    Args:
        output_dir: Directory where plot images will be saved

    Example:
        >>> plotter = EDAStaticPlots("output/eda/plots/")
        >>> path = plotter.missing_heatmap(df)
    """

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def consumption_trend(
        self,
        df: pd.DataFrame,
        consumption_cols: List[str],
        target_col: Optional[str] = None,
    ) -> str:
        """
        Generate trend line plot of consumption across periods.

        Args:
            df: Input DataFrame
            consumption_cols: List of consumption column names (ordered oldest to newest)
            target_col: Binary target column (optional)

        Returns:
            str: Path to saved plot file
        """
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            if not consumption_cols:
                return ""

            fig, ax = plt.subplots(figsize=(12, 6))

            x = range(len(consumption_cols))

            if target_col and target_col in df.columns:
                for class_val, label, color in [(0, "No Fraud", "steelblue"), (1, "Fraud", "red")]:
                    sub = df[df[target_col] == class_val][consumption_cols]
                    means = sub.mean().values
                    stds = sub.std().values
                    ax.plot(x, means, marker="o", label=label, color=color, linewidth=2)
                    ax.fill_between(
                        x,
                        means - stds,
                        means + stds,
                        alpha=0.2,
                        color=color,
                    )
            else:
                means = df[consumption_cols].mean().values
                ax.plot(x, means, marker="o", color="steelblue", linewidth=2, label="Mean")

            ax.set_xticks(list(x))
            ax.set_xticklabels(consumption_cols, rotation=45, ha="right", fontsize=8)
            ax.set_title("Consumption Trend by Period", fontsize=14, fontweight="bold")
            ax.set_xlabel("Period")
            ax.set_ylabel("Consumption (mean)")
            ax.legend()
            plt.tight_layout()

            path = str(self.output_dir / "consumption_trend.png")
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            return path

        except ImportError:
            logger.warning("matplotlib not available, skipping consumption trend plot")
            return ""
        except Exception as e:
            logger.warning("Error generating consumption trend plot: %s", e)
            return ""

    # ------------------------------------------------------------------
    # Outlier Analysis Plots
    # ------------------------------------------------------------------

    def plot_outlier_boxplots(
        self,
        df: pd.DataFrame,
        numeric_cols: List[str],
        outlier_masks: Dict[str, pd.Series],
        figsize: tuple = (15, 10),
    ) -> Dict[str, str]:
        """
        Generate boxplot for each numeric column with outliers highlighted.

        Args:
            df: Input DataFrame
            numeric_cols: List of numeric column names
            outlier_masks: Dict of {col: pd.Series(boolean)} indicating outliers
            figsize: Figure size tuple

        Returns:
            Dict[str, str]: Dictionary mapping column names to SVG strings
        """
        # Handle empty numeric_cols to avoid NameError on loop variable
        if not numeric_cols:
            logger.debug("No numeric columns provided for outlier boxplots")
            return {}

        try:
            import io

            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            n_cols = len(numeric_cols)
            n_rows = (n_cols + 2) // 3  # ~3 columns per row

            fig, axes = plt.subplots(n_rows, 3, figsize=figsize)
            # Always flatten to 1D array of axes
            axes = axes.flatten()

            for i, col in enumerate(numeric_cols):
                if col not in df.columns:
                    continue

                ax = axes[i]
                outlier_mask = outlier_masks.get(col, pd.Series(False, index=df.index))
                clean_data = df[col].dropna()

                # Split data into normal and outliers
                normal_mask = ~outlier_mask.reindex(clean_data.index).fillna(False)
                normal = clean_data[normal_mask]
                outliers = clean_data[~normal_mask]

                # Create boxplot with two boxes: normal and outliers
                data_to_plot = []
                labels = []

                if len(normal) > 0:
                    data_to_plot.append(normal.values)
                    labels.append("Normal")

                if len(outliers) > 0:
                    data_to_plot.append(outliers.values)
                    labels.append("Outliers")

                if data_to_plot:
                    bp = ax.boxplot(data_to_plot, tick_labels=labels, patch_artist=True)

                    # Color the boxes
                    colors = ["#2196F3", "#F44336"]
                    for patch, color in zip(bp["boxes"], colors):
                        patch.set_facecolor(color)
                        patch.set_alpha(0.7)

                # Calculate outlier percentage
                outlier_pct = (
                    (outlier_mask.sum() / len(outlier_mask) * 100) if len(outlier_mask) > 0 else 0
                )
                ax.set_title(f"{col}\nOutliers: {outlier_pct:.1f}%", fontsize=10)
                ax.set_ylabel("Value")

            # Hide unused subplots
            for j in range(i + 1, len(axes)):
                axes[j].set_visible(False)

            plt.tight_layout()

            # Convert to SVG
            buf = io.BytesIO()
            fig.savefig(buf, format="svg", bbox_inches="tight")
            buf.seek(0)
            svg = buf.read().decode("utf-8")
            buf.close()
            plt.close(fig)

            # For now, return the combined SVG for all columns
            # Individual column SVGs would require separate plots
            return {"combined": svg}

        except ImportError:
            logger.warning("matplotlib not available, skipping outlier boxplots")
            return {}
        except Exception as e:
            logger.warning("Error generating outlier boxplots: %s", e)
            return {}

    def plot_outlier_heatmap(
        self,
        df: pd.DataFrame,
        numeric_cols: List[str],
        outlier_masks: Dict[str, pd.Series],
        figsize: tuple = (12, 8),
    ) -> str:
        """
        Generate binary heatmap showing outliers across numeric columns.

        Args:
            df: Input DataFrame
            numeric_cols: List of numeric column names
            outlier_masks: Dict of {col: pd.Series(boolean)} indicating outliers
            figsize: Figure size tuple

        Returns:
            str: SVG string of the heatmap
        """
        try:
            import io

            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np

            # Limit to top 100 rows for performance
            max_rows = min(100, len(df))

            # Create binary matrix: 1 = outlier, 0 = normal
            outlier_matrix = np.zeros((max_rows, len(numeric_cols)))

            for j, col in enumerate(numeric_cols):
                if col in outlier_masks:
                    mask = outlier_masks[col].iloc[:max_rows].values
                    outlier_matrix[:, j] = mask.astype(int)

            fig, ax = plt.subplots(figsize=figsize)

            # Create heatmap: red=outlier, white=normal
            from matplotlib.colors import ListedColormap

            cmap = ListedColormap(["white", "#F44336"])
            im = ax.imshow(
                outlier_matrix,
                cmap=cmap,
                aspect="auto",
                interpolation="nearest",
            )

            ax.set_xticks(range(len(numeric_cols)))
            ax.set_xticklabels(numeric_cols, rotation=45, ha="right", fontsize=8)
            ax.set_yticks(range(max_rows))
            ax.set_yticklabels([f"Row {i}" for i in range(max_rows)], fontsize=8)

            ax.set_title(f"Outlier Heatmap (Top {max_rows} rows)", fontsize=14, fontweight="bold")
            ax.set_xlabel("Numeric Columns")
            ax.set_ylabel("Rows")

            # Add colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_ticks([0.25, 0.75])
            cbar.set_ticklabels(["Normal", "Outlier"])

            plt.tight_layout()

            # Convert to SVG
            buf = io.BytesIO()
            fig.savefig(buf, format="svg", bbox_inches="tight")
            buf.seek(0)
            svg = buf.read().decode("utf-8")
            buf.close()
            plt.close(fig)

            return svg

        except ImportError:
            logger.warning("matplotlib not available, skipping outlier heatmap")
            return ""
        except Exception as e:
            logger.warning("Error generating outlier heatmap: %s", e)
            return ""

    def plot_consumption_anomalies(
        self,
        df: pd.DataFrame,
        consumption_cols: List[str],
        outlier_mask: Optional[pd.Series] = None,
        target_col: Optional[str] = None,
        figsize: tuple = (14, 6),
    ) -> Dict[str, str]:
        """
        Generate scatter plots of consumption anomalies by period.

        Args:
            df: Input DataFrame
            consumption_cols: List of consumption column names (ordered)
            outlier_mask: Boolean series indicating outlier rows (optional)
            target_col: Binary target column for coloring (optional)
            figsize: Figure size tuple

        Returns:
            Dict[str, str]: Dictionary mapping period names to SVG strings
        """
        try:
            import io

            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            results = {}

            for col in consumption_cols:
                if col not in df.columns:
                    continue

                fig, ax = plt.subplots(figsize=figsize)

                x = df[col].values

                # Determine color based on target or outlier status
                if target_col and target_col in df.columns:
                    colors = df[target_col].map({0: "#2196F3", 1: "#F44336"}).values
                    label = "Target Class"
                elif outlier_mask is not None:
                    colors = outlier_mask.map({False: "#2196F3", True: "#F44336"}).values
                    label = "Outlier Status"
                else:
                    colors = "#2196F3"
                    label = None

                ax.scatter(
                    range(len(x)),
                    x,
                    c=colors,
                    alpha=0.6,
                    s=20,
                )

                ax.set_title(f"Consumption Anomalies: {col}", fontsize=14, fontweight="bold")
                ax.set_xlabel("Row Index")
                ax.set_ylabel("Consumption Value")

                if label:
                    # Add legend
                    from matplotlib.patches import Patch

                    legend_elements = [
                        Patch(facecolor="#2196F3", label=f"{label}: Normal/0"),
                        Patch(facecolor="#F44336", label=f"{label}: Anomaly/1"),
                    ]
                    ax.legend(handles=legend_elements)

                # Calculate and display statistics
                if outlier_mask is not None:
                    n_outliers = outlier_mask.sum()
                    pct = (n_outliers / len(outlier_mask) * 100) if len(outlier_mask) > 0 else 0
                    ax.text(
                        0.02,
                        0.98,
                        f"Outliers: {n_outliers} ({pct:.1f}%)",
                        transform=ax.transAxes,
                        verticalalignment="top",
                        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
                    )

                plt.tight_layout()

                # Convert to SVG
                buf = io.BytesIO()
                fig.savefig(buf, format="svg", bbox_inches="tight")
                buf.seek(0)
                svg = buf.read().decode("utf-8")
                buf.close()
                plt.close(fig)

                results[col] = svg

            return results

        except ImportError:
            logger.warning("matplotlib not available, skipping consumption anomalies plot")
            return {}
        except Exception as e:
            logger.warning("Error generating consumption anomalies plot: %s", e)
            return {}
