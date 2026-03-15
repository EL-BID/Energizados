"""
Static Plots Module - Energizados EDA Framework.

Generates static plots using matplotlib/seaborn for the EDA report.
"""

import logging
from pathlib import Path
from typing import List, Optional

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
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def missing_heatmap(self, df: pd.DataFrame) -> str:
        """
        Generate a seaborn heatmap showing null patterns across columns.

        Args:
            df: Input DataFrame

        Returns:
            str: Path to saved plot file
        """
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import seaborn as sns

            # Limit to columns with at least one null, cap at 50 columns for readability
            null_cols = df.columns[df.isna().any()].tolist()[:50]
            if not null_cols:
                logger.info("No null values found, skipping missing heatmap")
                return ""

            fig_width = min(max(12, len(null_cols) * 0.4), 24)
            fig_height = min(max(6, len(df) * 0.002), 12)

            fig, ax = plt.subplots(figsize=(fig_width, fig_height))

            null_matrix = df[null_cols].isna().astype(int)
            # Sample rows if too many
            if len(null_matrix) > 1000:
                null_matrix = null_matrix.sample(1000, random_state=42)

            sns.heatmap(
                null_matrix,
                ax=ax,
                cbar=False,
                yticklabels=False,
                cmap="Blues",
            )
            ax.set_title("Missing Values Pattern", fontsize=14, fontweight="bold")
            ax.set_xlabel("Columns")
            ax.set_ylabel("Rows (sample)")
            plt.xticks(rotation=45, ha="right", fontsize=8)
            plt.tight_layout()

            path = str(self.output_dir / "missing_heatmap.png")
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            return path

        except ImportError:
            logger.warning("seaborn/matplotlib not available, skipping missing heatmap")
            return ""
        except Exception as e:
            logger.warning("Error generating missing heatmap: %s", e)
            return ""

    def numeric_histogram(
        self,
        df: pd.DataFrame,
        col: str,
        target_col: Optional[str] = None,
    ) -> str:
        """
        Generate histogram with KDE for a numeric column, optionally split by target.

        Args:
            df: Input DataFrame
            col: Numeric column name
            target_col: Binary target column (optional, adds violin by class)

        Returns:
            str: Path to saved plot file
        """
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import seaborn as sns

            sub = df[[col] + ([target_col] if target_col and target_col in df.columns else [])].dropna()
            if len(sub) == 0:
                return ""

            if target_col and target_col in sub.columns:
                fig, axes = plt.subplots(1, 2, figsize=(14, 5))

                # Histogram by class
                for val in sub[target_col].unique():
                    subset = sub[sub[target_col] == val][col]
                    if len(subset) > 1000:
                        subset = subset.sample(1000, random_state=42)
                    axes[0].hist(subset, bins=40, alpha=0.5, label=f"Class {val}", density=True)

                axes[0].set_title(f"Histogram: {col}")
                axes[0].set_xlabel(col)
                axes[0].legend()

                # Violin by class
                sub[target_col] = sub[target_col].astype(str)
                sns.violinplot(data=sub, x=target_col, y=col, ax=axes[1], palette="muted")
                axes[1].set_title(f"Distribution by class: {col}")
            else:
                fig, ax = plt.subplots(figsize=(10, 5))
                sample = sub[col] if len(sub) <= 5000 else sub[col].sample(5000, random_state=42)
                ax.hist(sample, bins=50, color="steelblue", alpha=0.7, density=True)
                try:
                    from scipy.stats import gaussian_kde

                    kde = gaussian_kde(sample.dropna())
                    import numpy as np

                    x_range = np.linspace(sample.min(), sample.max(), 200)
                    ax.plot(x_range, kde(x_range), "r-", linewidth=2, label="KDE")
                    ax.legend()
                except Exception:  # nosec B110
                    pass
                ax.set_title(f"Histogram: {col}")
                ax.set_xlabel(col)

            plt.tight_layout()
            safe_col = col.replace("/", "_").replace("\\", "_")
            path = str(self.output_dir / f"hist_{safe_col}.png")
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            return path

        except ImportError:
            logger.warning("matplotlib/seaborn not available, skipping histogram for '%s'", col)
            return ""
        except Exception as e:
            logger.warning("Error generating histogram for '%s': %s", col, e)
            return ""

    def categorical_barplot(
        self,
        df: pd.DataFrame,
        col: str,
        target_col: Optional[str] = None,
        max_cats: int = 30,
    ) -> str:
        """
        Generate bar plot for a categorical column.

        Args:
            df: Input DataFrame
            col: Categorical column name
            target_col: Binary target column (optional, adds stacked bars by class)
            max_cats: Maximum categories to show

        Returns:
            str: Path to saved plot file
        """
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            series = df[col].dropna()
            top_cats = series.value_counts().head(max_cats)

            if len(top_cats) == 0:
                return ""

            fig, ax = plt.subplots(figsize=(12, 6))

            if target_col and target_col in df.columns:
                sub = df[[col, target_col]].dropna()
                # Compute fraud rate per category
                fraud_rate = sub[sub[col].isin(top_cats.index)].groupby(col)[target_col].mean().reindex(top_cats.index).fillna(0)
                ax.bar(range(len(top_cats)), top_cats.values, color="steelblue", alpha=0.7, label="Count")
                ax2 = ax.twinx()
                ax2.plot(range(len(top_cats)), fraud_rate.values, "ro-", markersize=6, label="Fraud Rate")
                ax2.set_ylabel("Fraud Rate", color="red")
                ax.set_title(f"Categorical distribution: {col} (with fraud rate)")
                lines2, labels2 = ax2.get_legend_handles_labels()
                lines, labels = ax.get_legend_handles_labels()
                ax.legend(lines + lines2, labels + labels2, loc="upper right")
            else:
                ax.bar(range(len(top_cats)), top_cats.values, color="steelblue", alpha=0.8)
                ax.set_title(f"Categorical distribution: {col}")

            ax.set_xticks(range(len(top_cats)))
            ax.set_xticklabels([str(c) for c in top_cats.index], rotation=45, ha="right", fontsize=9)
            ax.set_ylabel("Count")
            ax.set_xlabel(col)

            plt.tight_layout()
            safe_col = col.replace("/", "_").replace("\\", "_")
            path = str(self.output_dir / f"bar_{safe_col}.png")
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            return path

        except ImportError:
            logger.warning("matplotlib not available, skipping bar plot for '%s'", col)
            return ""
        except Exception as e:
            logger.warning("Error generating bar plot for '%s': %s", col, e)
            return ""

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

    def correlation_heatmap(self, corr_matrix: pd.DataFrame) -> str:
        """
        Generate a seaborn correlation heatmap.

        Args:
            corr_matrix: Pre-computed correlation matrix

        Returns:
            str: Path to saved plot file
        """
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import seaborn as sns

            if corr_matrix is None or corr_matrix.empty:
                return ""

            n = len(corr_matrix)
            fig_size = min(max(8, n * 0.5), 24)
            fig, ax = plt.subplots(figsize=(fig_size, fig_size))

            mask = None
            import numpy as np

            mask = np.triu(np.ones_like(corr_matrix, dtype=bool))

            sns.heatmap(
                corr_matrix,
                ax=ax,
                mask=mask,
                annot=n <= 20,
                fmt=".2f",
                cmap="coolwarm",
                center=0,
                vmin=-1,
                vmax=1,
                square=True,
                linewidths=0.5,
            )
            ax.set_title("Correlation Matrix", fontsize=14, fontweight="bold")
            plt.tight_layout()

            path = str(self.output_dir / "correlation_heatmap.png")
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            return path

        except ImportError:
            logger.warning("seaborn/matplotlib not available, skipping correlation heatmap")
            return ""
        except Exception as e:
            logger.warning("Error generating correlation heatmap: %s", e)
            return ""
