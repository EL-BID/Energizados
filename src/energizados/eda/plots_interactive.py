"""
Interactive Plots Module - Energizados EDA Framework.

Generates interactive Plotly charts for the EDA HTML report.
All methods return HTML strings (not file paths).
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Track if plotlyjs CDN has already been included
_PLOTLY_JS_INCLUDED = False


def _get_plotly_js_args(first: bool = False) -> Dict:
    """Return Plotly to_html arguments based on whether this is the first chart."""
    if first:
        return {"full_html": False, "include_plotlyjs": "cdn"}
    return {"full_html": False, "include_plotlyjs": False}


class EDAInteractivePlots:
    """
    Generates interactive Plotly charts for the EDA report.

    All methods return HTML string of the chart (not file paths).
    The first chart call should include the Plotly.js CDN; subsequent calls should not.

    Args:
        output_dir: Output directory (kept for API consistency, not used for HTML charts)
        template: Plotly template name

    Example:
        >>> plotter = EDAInteractivePlots("output/eda/")
        >>> html = plotter.class_balance_chart(class_counts, class_pcts)
    """

    def __init__(self, output_dir: str, template: str = "plotly_white"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.template = template
        self._first_chart = True

    def _to_html(self, fig) -> str:
        """Convert figure to HTML, managing Plotly.js inclusion."""
        args = _get_plotly_js_args(self._first_chart)
        self._first_chart = False
        try:
            return fig.to_html(**args)
        except Exception as e:
            logger.warning("Error converting figure to HTML: %s", e)
            return ""

    def class_balance_chart(self, class_counts: Dict, class_pcts: Dict) -> str:
        """
        Bar chart showing class distribution.

        Args:
            class_counts: {label: count}
            class_pcts: {label: percentage}

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            labels = list(class_counts.keys())
            counts = [class_counts[label] for label in labels]
            pcts = [class_pcts.get(label, 0) for label in labels]

            colors = ["#2196F3", "#F44336", "#FF9800", "#4CAF50"]

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=counts,
                    text=[f"{c:,}<br>({p:.1f}%)" for c, p in zip(counts, pcts)],
                    textposition="outside",
                    marker_color=colors[: len(labels)],
                    name="Count",
                )
            )

            fig.update_layout(
                title="Class Distribution (Target Variable)",
                xaxis_title="Class",
                yaxis_title="Number of Records",
                template=self.template,
                showlegend=False,
                height=400,
            )

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping class balance chart")
            return ""
        except Exception as e:
            logger.warning("Error generating class balance chart: %s", e)
            return ""

    def iv_ranking_chart(self, ranking_df: pd.DataFrame) -> str:
        """
        Horizontal bar chart of feature IV ranking with threshold lines.

        Args:
            ranking_df: DataFrame with columns [feature, iv, type]

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            if ranking_df is None or "iv" not in ranking_df.columns or len(ranking_df) == 0:
                return ""

            top = ranking_df.dropna(subset=["iv"]).nlargest(30, "iv")

            colors = {"numeric": "#2196F3", "categorical": "#FF9800"}
            bar_colors = [colors.get(t, "#9C27B0") for t in top.get("type", ["numeric"] * len(top))]

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    y=top["feature"],
                    x=top["iv"],
                    orientation="h",
                    marker_color=bar_colors,
                    text=[f"{v:.4f}" for v in top["iv"]],
                    textposition="outside",
                    name="IV",
                )
            )

            # Threshold lines
            iv_thresholds = {
                "No power (< 0.02)": 0.02,
                "Weak (0.1)": 0.1,
                "Moderate (0.3)": 0.3,
                "Strong (0.5)": 0.5,
            }
            for label, val in iv_thresholds.items():
                fig.add_vline(
                    x=val,
                    line_dash="dash",
                    line_color="red",
                    annotation_text=label,
                    annotation_position="top",
                    annotation_font_size=9,
                )

            fig.update_layout(
                title="Variable Ranking by Information Value (IV)",
                xaxis_title="Information Value",
                yaxis_title="Variable",
                template=self.template,
                height=max(400, len(top) * 22),
                yaxis={"categoryorder": "total ascending"},
            )

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping IV ranking chart")
            return ""
        except Exception as e:
            logger.warning("Error generating IV ranking chart: %s", e)
            return ""

    def woe_chart(self, woe_table: pd.DataFrame, col: str) -> str:
        """
        Bar chart of WoE by bin.

        Args:
            woe_table: DataFrame with columns [bin, woe, event_rate]
            col: Feature column name (for title)

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            if woe_table is None or len(woe_table) == 0:
                return ""

            fig = make_subplots(specs=[[{"secondary_y": True}]])

            colors = ["#2196F3" if w >= 0 else "#F44336" for w in woe_table["woe"]]

            fig.add_trace(
                go.Bar(
                    x=woe_table["bin"].astype(str),
                    y=woe_table["woe"],
                    name="WoE",
                    marker_color=colors,
                ),
                secondary_y=False,
            )

            if "event_rate" in woe_table.columns:
                fig.add_trace(
                    go.Scatter(
                        x=woe_table["bin"].astype(str),
                        y=woe_table["event_rate"],
                        name="Event Rate",
                        mode="lines+markers",
                        line={"color": "orange", "width": 2},
                    ),
                    secondary_y=True,
                )

            fig.update_layout(
                title=f"Weight of Evidence (WoE): {col}",
                xaxis_title="Bin",
                template=self.template,
                height=400,
            )
            fig.update_yaxes(title_text="WoE", secondary_y=False)
            fig.update_yaxes(title_text="Event Rate", secondary_y=True)

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping WoE chart")
            return ""
        except Exception as e:
            logger.warning("Error generating WoE chart for '%s': %s", col, e)
            return ""

    def missing_funnel(self, nulls_by_col: List[Dict]) -> str:
        """
        Funnel chart showing data loss progression from 100% to complete cases.

        Args:
            nulls_by_col: List of dicts [{col, null_count, null_pct}]

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            if not nulls_by_col:
                return ""

            # Sort by null_pct descending (most missing first)
            sorted_cols = sorted(nulls_by_col, key=lambda x: x.get("null_pct", 0), reverse=True)
            top_cols = sorted_cols[:20]

            labels = [d["col"] for d in top_cols]
            values = [100.0 - d.get("null_pct", 0) for d in top_cols]

            fig = go.Figure(
                go.Funnel(
                    y=labels,
                    x=values,
                    textinfo="label+value+percent initial",
                    hovertemplate="<b>%{y}</b><br>Complete: %{x:.1f}%<extra></extra>",
                )
            )

            fig.update_layout(
                title="Complete Data Funnel by Column",
                template=self.template,
                height=max(400, len(top_cols) * 30),
            )

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping missing funnel")
            return ""
        except Exception as e:
            logger.warning("Error generating missing funnel: %s", e)
            return ""

    def null_correlation_heatmap(self, corr_matrix: pd.DataFrame) -> str:
        """
        Interactive heatmap of null indicator correlations.

        Args:
            corr_matrix: Pre-computed correlation matrix of null indicators

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            if corr_matrix is None or corr_matrix.empty:
                return ""

            fig = go.Figure(
                go.Heatmap(
                    z=corr_matrix.values,
                    x=list(corr_matrix.columns),
                    y=list(corr_matrix.index),
                    colorscale="RdBu",
                    zmid=0,
                    zmin=-1,
                    zmax=1,
                    colorbar={"title": "Correlation"},
                    hovertemplate="<b>%{x}</b> × <b>%{y}</b><br>Correlation: %{z:.3f}<extra></extra>",
                )
            )

            fig.update_layout(
                title="Correlation between Missing Indicators",
                template=self.template,
                height=max(400, len(corr_matrix) * 30),
                xaxis={"tickangle": -45},
            )

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping null correlation heatmap")
            return ""
        except Exception as e:
            logger.warning("Error generating null correlation heatmap: %s", e)
            return ""

    def consumption_heatmap(
        self,
        df: pd.DataFrame,
        consumption_cols: List[str],
        sample_n: int = 200,
    ) -> str:
        """
        Heatmap of sampled consumption patterns across periods.

        Args:
            df: Input DataFrame
            consumption_cols: Ordered list of consumption column names
            sample_n: Number of rows to sample for display

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            if not consumption_cols:
                return ""

            sub = df[consumption_cols].dropna()
            if len(sub) > sample_n:
                sub = sub.sample(sample_n, random_state=42)

            fig = go.Figure(
                go.Heatmap(
                    z=sub.values,
                    x=consumption_cols,
                    y=[f"Row {i}" for i in range(len(sub))],
                    colorscale="Blues",
                    colorbar={"title": "Consumption"},
                    hovertemplate="Period: <b>%{x}</b><br>Consumption: %{z:.2f}<extra></extra>",
                )
            )

            fig.update_layout(
                title=f"Consumption Heatmap ({len(sub)} customer sample)",
                xaxis_title="Period",
                yaxis_title="Customer (sample)",
                template=self.template,
                height=max(400, min(sample_n * 4, 800)),
            )

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping consumption heatmap")
            return ""
        except Exception as e:
            logger.warning("Error generating consumption heatmap: %s", e)
            return ""

    def temporal_line(self, temporal_data: List[Dict], title: str = "") -> str:
        """
        Line chart of temporal data (e.g., fraud rate over time).

        Args:
            temporal_data: List of dicts with keys: period, total, positive, rate
            title: Chart title

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            if not temporal_data:
                return ""

            periods = [d["period"] for d in temporal_data]
            rates = [d.get("rate", 0) for d in temporal_data]
            totals = [d.get("total", 0) for d in temporal_data]

            fig = make_subplots(specs=[[{"secondary_y": True}]])

            fig.add_trace(
                go.Scatter(
                    x=periods,
                    y=rates,
                    mode="lines+markers",
                    name="Fraud Rate (%)",
                    line={"color": "#F44336", "width": 2},
                    marker={"size": 6},
                ),
                secondary_y=False,
            )

            fig.add_trace(
                go.Bar(
                    x=periods,
                    y=totals,
                    name="Total Records",
                    marker_color="rgba(33, 150, 243, 0.4)",
                    opacity=0.6,
                ),
                secondary_y=True,
            )

            fig.update_layout(
                title=title or "Temporal Evolution of Fraud Rate",
                template=self.template,
                height=400,
                xaxis={"tickangle": -45},
            )
            fig.update_yaxes(title_text="Fraud Rate (%)", secondary_y=False)
            fig.update_yaxes(title_text="Total Records", secondary_y=True)

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping temporal line chart")
            return ""
        except Exception as e:
            logger.warning("Error generating temporal line chart: %s", e)
            return ""

    def categorical_treemap(self, df: pd.DataFrame, col: str) -> str:
        """Horizontal bar chart showing top 50 category distribution (replaces treemap)."""
        try:
            series = df[col].dropna()
            if len(series) == 0:
                return ""
            vc = series.value_counts().head(50)
            return self.categorical_bar_chart(vc, col, top_n=50)
        except Exception as e:
            logger.warning("Error generating categorical treemap for '%s': %s", col, e)
            return ""

    def inspection_sunburst(self, hierarchy: Dict, title: str = "Inspection Hierarchy") -> str:
        """
        Sunburst chart showing inspection process hierarchy.

        Args:
            hierarchy: Nested dict structure {tipo: {acao: {categories...}}}
            title: Chart title

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            if not hierarchy:
                return ""

            # Flatten hierarchy into sunburst format
            labels = ["Total"]
            parents = [""]
            values = [
                sum(
                    sum(
                        (
                            sum(c.values())
                            if isinstance(c, dict) and "categories" in c
                            else (c.get("count", 0) if isinstance(c, dict) else 0)
                        )
                        for c in acao.values()
                        if isinstance(acao, dict)
                    )
                    for acao in tipo.values()
                )
                for tipo in hierarchy.values()
            ]

            for tipo, acao_dict in hierarchy.items():
                labels.append(str(tipo))
                parents.append("Total")

                tipo_count = 0
                for acao, acao_data in acao_dict.items():
                    if isinstance(acao_data, dict):
                        count = acao_data.get("count", 0)
                        categories = acao_data.get("categories", {})
                        tipo_count += count

                        labels.append(str(acao))
                        parents.append(str(tipo))

                        for cat, cat_count in categories.items():
                            labels.append(str(cat))
                            parents.append(str(acao))
                            values.append(cat_count)

                    if isinstance(acao_data, dict):
                        values.append(acao_data.get("count", 0))

            fig = go.Figure(
                go.Sunburst(
                    labels=labels,
                    parents=parents,
                    values=values,
                    branchvalues="total",
                    hovertemplate="<b>%{label}</b><br>Count: %{value}<extra></extra>",
                )
            )

            fig.update_layout(
                title=title,
                template=self.template,
                height=600,
            )

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping inspection sunburst")
            return ""
        except Exception as e:
            logger.warning("Error generating inspection sunburst: %s", e)
            return ""

    def inspection_funnel(self, funnel_data: List[Dict], title: str = "Inspection Funnel") -> str:
        """
        Funnel chart showing inspection process progression.

        Args:
            funnel_data: List of dicts [{stage, count, pct_of_total}]
            title: Chart title

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            if not funnel_data:
                return ""

            fig = go.Figure(
                go.Funnel(
                    y=[d.get("stage", "") for d in funnel_data],
                    x=[d.get("count", 0) for d in funnel_data],
                    textinfo="label+value+percent initial",
                    hovertemplate="<b>%{y}</b><br>Count: %{x}<br>Initial percentage: %{percentInitial:.1%}<extra></extra>",
                )
            )

            fig.update_layout(
                title=title,
                template=self.template,
                height=max(400, len(funnel_data) * 50),
            )

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping inspection funnel")
            return ""
        except Exception as e:
            logger.warning("Error generating inspection funnel: %s", e)
            return ""

    def scatter_mapbox(
        self,
        df: pd.DataFrame,
        lat_col: str,
        lon_col: str,
        color_col: Optional[str] = None,
        title: str = "Geographic Distribution",
    ) -> str:
        """
        Scatter mapbox chart of geographic data.

        Args:
            df: Input DataFrame
            lat_col: Latitude column
            lon_col: Longitude column
            color_col: Column to use for color (optional, e.g., target or zone)
            title: Chart title

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.express as px

            sub = df[[lat_col, lon_col]].copy()
            if color_col and color_col in df.columns:
                sub[color_col] = df[color_col]

            sub = sub.dropna(subset=[lat_col, lon_col])
            sub = sub[(sub[lat_col] != 0) & (sub[lon_col] != 0)]

            if len(sub) == 0:
                return ""

            # Sample if too many points
            if len(sub) > 5000:
                sub = sub.sample(5000, random_state=42)

            fig = px.scatter_mapbox(
                sub,
                lat=lat_col,
                lon=lon_col,
                color=color_col if color_col else None,
                color_discrete_sequence=px.colors.qualitative.Bold,
                mapbox_style="open-street-map",
                title=title,
                height=600,
            )

            fig.update_layout(
                template=self.template,
                margin={"r": 0, "t": 50, "l": 0, "b": 0},
            )

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping scatter mapbox")
            return ""
        except Exception as e:
            logger.warning("Error generating scatter mapbox: %s", e)
            return ""

    # ------------------------------------------------------------------
    # Column detail charts (matplotlib/seaborn — embedded as base64 PNG)
    # ------------------------------------------------------------------

    @staticmethod
    def _fig_to_html(fig, alt: str = "") -> str:
        """Convert a matplotlib Figure to an <img> HTML tag with base64 PNG."""
        import base64
        import io

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        buf.close()
        import matplotlib.pyplot as plt

        plt.close(fig)
        return f'<img src="data:image/png;base64,{b64}" alt="{alt}" style="max-width:100%;height:auto;"/>'

    def histogram_interactive(
        self,
        series: pd.Series,
        col_name: str,
        target_series: Optional[pd.Series] = None,
    ) -> str:
        """Histogram with KDE, split by binary target when available."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            data = series.dropna()
            if len(data) == 0:
                return ""

            fig, ax = plt.subplots(figsize=(7, 4))
            colors = ["#2196F3", "#F44336"]

            if target_series is not None:
                mask = target_series.reindex(data.index).dropna()
                common = data.index.intersection(mask.index)
                for i, v in enumerate(sorted(mask.unique())):
                    subset = data.loc[common[mask.loc[common] == v]]
                    if len(subset) > 0:
                        ax.hist(
                            subset,
                            bins=30,
                            alpha=0.5,
                            color=colors[i % len(colors)],
                            label=f"Class {int(v)}",
                            density=True,
                        )
                ax.legend()
            else:
                ax.hist(data, bins=30, color="#2196F3", alpha=0.7, density=True)

            ax.set_title(f"Distribution: {col_name}", fontsize=12)
            ax.set_xlabel(col_name)
            ax.set_ylabel("Density")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout()
            return self._fig_to_html(fig, alt=f"histogram {col_name}")
        except Exception as e:
            logger.warning("Error generating histogram for '%s': %s", col_name, e)
            return ""

    def boxplot_interactive(
        self,
        series: pd.Series,
        col_name: str,
        target_series: Optional[pd.Series] = None,
    ) -> str:
        """Boxplot split by binary target when available."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            data = series.dropna()
            if len(data) == 0:
                return ""

            fig, ax = plt.subplots(figsize=(5, 4))

            if target_series is not None:
                mask = target_series.reindex(data.index).dropna()
                common = data.index.intersection(mask.index)
                groups = [
                    data.loc[common[mask.loc[common] == v]].values for v in sorted(mask.unique())
                ]
                labels = [f"Class {int(v)}" for v in sorted(mask.unique())]
                groups = [g for g in groups if len(g) > 0]
                ax.boxplot(
                    groups,
                    labels=labels[: len(groups)],
                    patch_artist=True,
                    boxprops={"facecolor": "#bbdefb"},
                )
            else:
                ax.boxplot(
                    data.values,
                    labels=[col_name],
                    patch_artist=True,
                    boxprops={"facecolor": "#bbdefb"},
                )

            ax.set_title(f"Boxplot: {col_name}", fontsize=12)
            ax.set_ylabel(col_name)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout()
            return self._fig_to_html(fig, alt=f"boxplot {col_name}")
        except Exception as e:
            logger.warning("Error generating boxplot for '%s': %s", col_name, e)
            return ""

    def categorical_bar_chart(self, value_counts: pd.Series, col_name: str, top_n: int = 30) -> str:
        """Horizontal bar chart of top N category frequencies."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            if value_counts is None or len(value_counts) == 0:
                return ""

            top = value_counts.head(top_n)
            total = value_counts.sum()
            pcts = (top / total * 100).round(1)

            height = max(4, len(top) * 0.35)
            fig, ax = plt.subplots(figsize=(8, height))
            y_pos = range(len(top))
            bars = ax.barh(list(y_pos), top.values, color="#2196F3", alpha=0.8)
            ax.set_yticks(list(y_pos))
            ax.set_yticklabels([str(v)[:40] for v in top.index], fontsize=9)
            for bar, pct in zip(bars, pcts):
                ax.text(
                    bar.get_width() * 1.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{pct:.1f}%",
                    va="center",
                    fontsize=8,
                )
            ax.set_title(f"Frequencies: {col_name} (top {len(top)})", fontsize=12)
            ax.set_xlabel("Count")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout()
            return self._fig_to_html(fig, alt=f"bar chart {col_name}")
        except Exception as e:
            logger.warning("Error generating bar chart for '%s': %s", col_name, e)
            return ""

    def target_rate_by_category(
        self,
        df: pd.DataFrame,
        col: str,
        target_col: str,
        top_n: int = 30,
    ) -> str:
        """Bar chart of target rate per category value."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            if col not in df.columns or target_col not in df.columns:
                return ""

            sub = df[[col, target_col]].dropna()
            if len(sub) == 0:
                return ""

            grouped = sub.groupby(col)[target_col].agg(["mean", "count"])
            grouped = grouped.sort_values("mean", ascending=False).head(top_n)
            rates = (grouped["mean"] * 100).round(2)
            median_rate = float(rates.median())
            colors = ["#F44336" if r > median_rate else "#2196F3" for r in rates.values]

            fig, ax = plt.subplots(figsize=(8, 4))
            ax.bar(range(len(rates)), rates.values, color=colors, alpha=0.85)
            ax.set_xticks(range(len(rates)))
            ax.set_xticklabels(
                [str(v)[:20] for v in grouped.index], rotation=45, ha="right", fontsize=8
            )
            ax.set_title(f"Target Rate by: {col}", fontsize=12)
            ax.set_ylabel("Target Rate (%)")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout()
            return self._fig_to_html(fig, alt=f"target rate {col}")
        except Exception as e:
            logger.warning("Error generating target rate chart for '%s': %s", col, e)
            return ""

    def woe_by_bins_chart(self, woe_table: pd.DataFrame, col: str) -> str:
        """WoE chart for numeric column bins (delegates to existing woe_chart)."""
        return self.woe_chart(woe_table, col)

    def temporal_distribution_chart(self, series: pd.Series, col_name: str) -> str:
        """Line chart showing record count over time (monthly)."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            data = pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=True).dropna()
            if len(data) == 0:
                return ""

            counts = data.dt.to_period("M").value_counts().sort_index()
            periods = [str(p) for p in counts.index]

            fig, ax = plt.subplots(figsize=(9, 4))
            ax.plot(
                range(len(periods)),
                counts.values,
                color="#1a237e",
                linewidth=2,
                marker="o",
                markersize=4,
            )
            step = max(1, len(periods) // 12)
            ax.set_xticks(range(0, len(periods), step))
            ax.set_xticklabels(periods[::step], rotation=45, ha="right", fontsize=8)
            ax.set_title(f"Temporal Distribution: {col_name}", fontsize=12)
            ax.set_xlabel("Period")
            ax.set_ylabel("Records")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout()
            return self._fig_to_html(fig, alt=f"temporal {col_name}")
        except Exception as e:
            logger.warning("Error generating temporal distribution for '%s': %s", col_name, e)
            return ""

    # ------------------------------------------------------------------
    # Hierarchy / Related columns charts
    # ------------------------------------------------------------------

    def sunburst_hierarchy(
        self,
        df: pd.DataFrame,
        columns: List[str],
        title: str = "Hierarchy",
    ) -> str:
        """Generic sunburst chart from a DataFrame and ordered list of hierarchy columns."""
        try:
            import plotly.express as px

            sub = df[columns].dropna().copy()
            if len(sub) == 0:
                return ""

            # Add prefixes to avoid label collision between levels
            renamed_cols = []
            for i, col in enumerate(columns):
                new_col = f"_lvl{i}_{col}"
                sub[new_col] = sub[col].astype(str)
                renamed_cols.append(new_col)

            sub["_count"] = 1
            grouped = sub.groupby(renamed_cols, as_index=False)["_count"].sum()

            fig = px.sunburst(
                grouped,
                path=renamed_cols,
                values="_count",
                title=title,
                template=self.template,
            )
            # Clean labels: remove prefix
            fig.update_traces(
                textinfo="label+percent parent",
                hovertemplate="<b>%{label}</b><br>Count: %{value}<br>% of parent: %{percentParent:.1%}<extra></extra>",
            )
            fig.update_layout(height=600)
            # Remove prefixes from displayed labels
            fig.for_each_trace(
                lambda t: t.update(
                    labels=[
                        lbl.split("_", 2)[-1] if lbl.startswith("_lvl") else lbl
                        for lbl in (t.labels if t.labels is not None else [])
                    ]
                )
            )
            return self._to_html(fig)
        except Exception as e:
            logger.warning("Error generating sunburst: %s", e)
            return ""

    def sankey_hierarchy(
        self,
        df: pd.DataFrame,
        columns: List[str],
        title: str = "Flow between Levels",
    ) -> str:
        """Sankey diagram showing flow between adjacent hierarchy levels."""
        try:
            import plotly.graph_objects as go

            if len(columns) < 2:
                return ""

            sub = df[columns].dropna().copy()
            if len(sub) == 0:
                return ""

            # Build per-adjacent-pair flows, aggregate small categories as "Otros"
            all_labels: List[str] = []
            sources: List[int] = []
            targets: List[int] = []
            values: List[int] = []
            label_index: Dict[str, int] = {}

            def _get_idx(label: str) -> int:
                if label not in label_index:
                    label_index[label] = len(all_labels)
                    all_labels.append(label)
                return label_index[label]

            for i in range(len(columns) - 1):
                src_col, tgt_col = columns[i], columns[i + 1]
                pair = sub.groupby([src_col, tgt_col]).size().reset_index(name="count")
                total = pair["count"].sum()

                # Aggregate categories < 1% into "Otros"
                threshold = total * 0.01
                for col_name in [src_col, tgt_col]:
                    col_totals = pair.groupby(col_name)["count"].sum()
                    small = col_totals[col_totals < threshold].index
                    if len(small) > 0:
                        pair[col_name] = pair[col_name].apply(
                            lambda x, s=small, cn=col_name: f"Others ({cn})" if x in s else x
                        )
                        pair = pair.groupby([src_col, tgt_col], as_index=False)["count"].sum()

                for _, row in pair.iterrows():
                    src_label = f"{src_col}: {row[src_col]}"
                    tgt_label = f"{tgt_col}: {row[tgt_col]}"
                    sources.append(_get_idx(src_label))
                    targets.append(_get_idx(tgt_label))
                    values.append(int(row["count"]))

            if not values:
                return ""

            fig = go.Figure(
                go.Sankey(
                    node={"label": all_labels, "pad": 15, "thickness": 20},
                    link={"source": sources, "target": targets, "value": values},
                )
            )
            fig.update_layout(
                title=title, template=self.template, height=max(500, len(all_labels) * 20)
            )
            return self._to_html(fig)
        except Exception as e:
            logger.warning("Error generating sankey: %s", e)
            return ""

    def hierarchy_target_heatmap(
        self,
        cross_target: pd.DataFrame,
        title: str = "Target Rate by Combination",
    ) -> str:
        """Heatmap of target rate by hierarchy combination (2D crosstab)."""
        try:
            import plotly.graph_objects as go

            if cross_target is None or cross_target.empty:
                return ""

            fig = go.Figure(
                go.Heatmap(
                    z=cross_target.values,
                    x=[str(c) for c in cross_target.columns],
                    y=[str(i) for i in cross_target.index],
                    colorscale="RdYlGn_r",
                    colorbar={"title": "Target Rate"},
                    hovertemplate="<b>%{y}</b> × <b>%{x}</b><br>Rate: %{z:.2%}<extra></extra>",
                )
            )
            fig.update_layout(
                title=title,
                template=self.template,
                height=max(400, len(cross_target) * 25),
                xaxis={"tickangle": -45},
            )
            return self._to_html(fig)
        except Exception as e:
            logger.warning("Error generating hierarchy target heatmap: %s", e)
            return ""

    def segment_barplot(
        self, segment_stats: List[Dict], title: str = "Fraud Rate by Segment"
    ) -> str:
        """
        Bar chart showing fraud rate by segment.

        Args:
            segment_stats: List of dicts [{segment, size, target_rate, z_score}]
            title: Chart title

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            if not segment_stats:
                return ""

            top_segments = sorted(
                segment_stats, key=lambda x: abs(x.get("z_score", 0)), reverse=True
            )[:20]

            segments = [s["segment"] for s in top_segments]
            rates = [s.get("target_rate", 0) * 100 for s in top_segments]
            sizes = [s.get("size", 0) for s in top_segments]

            fig = go.Figure()

            fig.add_trace(
                go.Bar(
                    x=segments,
                    y=rates,
                    text=[f"{r:.1f}%<br>(n={s:,})" for r, s in zip(rates, sizes)],
                    textposition="outside",
                    marker_color=["#F44336" if r > 5 else "#2196F3" for r in rates],
                )
            )

            fig.update_layout(
                title=title,
                xaxis_title="Segment",
                yaxis_title="Fraud Rate (%)",
                template=self.template,
                height=max(400, len(segments) * 25),
                xaxis={"tickangle": -45},
            )

            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping segment barplot")
            return ""
        except Exception as e:
            logger.warning("Error generating segment barplot: %s", e)
            return ""
