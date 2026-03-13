"""
Interactive Plots Module - Energizados Evaluation Framework.

Generates interactive Plotly charts for the evaluation HTML report.
All methods return HTML strings (not file paths).

Follows the same pattern as energizados.eda.plots_interactive.EDAInteractivePlots.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Import theme colors from plots.py (same palette for static/interactive consistency)
try:
    from energizados.evaluation.plots import THEME_COLORS
except ImportError:
    THEME_COLORS = {
        "primary": "#667eea",
        "secondary": "#764ba2",
        "positive": "#28a745",
        "negative": "#dc3545",
        "warning": "#ffc107",
        "neutral": "#6c757d",
    }


class EvalInteractivePlots:
    """
    Generates interactive Plotly charts for the evaluation report.

    All methods return HTML strings of the chart (not file paths).
    Each chart includes the Plotly.js CDN (browsers cache it, no penalty).

    Args:
        output_dir: Output directory (kept for API consistency, not used for HTML charts)
        template: Plotly template name

    Example:
        >>> plotter = EvalInteractivePlots("output/evaluation/")
        >>> html = plotter.roc_curve(fpr, tpr, auc_score)
    """

    def __init__(self, output_dir: str = "output/", template: str = "plotly_white"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.template = template

    def _to_html(self, fig) -> str:
        """Convert figure to HTML, including Plotly.js CDN every time."""
        try:
            return fig.to_html(full_html=False, include_plotlyjs="cdn")
        except Exception as e:
            logger.warning("Error converting figure to HTML: %s", e)
            return ""

    def roc_curve(self, fpr: List[float], tpr: List[float], auc_score: float) -> str:
        """
        Interactive ROC curve chart.

        Args:
            fpr: False positive rates
            tpr: True positive rates
            auc_score: AUC score

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=list(fpr),
                    y=list(tpr),
                    mode="lines",
                    name=f"ROC (AUC = {auc_score:.4f})",
                    line={"color": THEME_COLORS["primary"], "width": 2},
                    hovertemplate="FPR: %{x:.3f}<br>TPR: %{y:.3f}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[0, 1],
                    y=[0, 1],
                    mode="lines",
                    name="Random",
                    line={"color": THEME_COLORS["neutral"], "dash": "dash", "width": 1},
                    hoverinfo="skip",
                )
            )
            fig.update_layout(
                title=f"ROC Curve (AUC = {auc_score:.4f})",
                xaxis_title="False Positive Rate",
                yaxis_title="True Positive Rate",
                template=self.template,
                height=420,
                xaxis={"range": [0, 1]},
                yaxis={"range": [0, 1.05]},
                legend={"x": 0.6, "y": 0.1},
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping ROC curve chart")
            return ""
        except Exception as e:
            logger.warning("Error generating ROC curve chart: %s", e)
            return ""

    def precision_recall_curve(self, precision: List[float], recall: List[float], ap_score: float) -> str:
        """
        Interactive Precision-Recall curve chart.

        Args:
            precision: Precision values
            recall: Recall values
            ap_score: Average precision score

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=list(recall),
                    y=list(precision),
                    mode="lines",
                    name=f"PR curve (AP = {ap_score:.4f})",
                    line={"color": THEME_COLORS["secondary"], "width": 2},
                    hovertemplate="Recall: %{x:.3f}<br>Precision: %{y:.3f}<extra></extra>",
                )
            )
            fig.update_layout(
                title=f"Precision-Recall Curve (AP = {ap_score:.4f})",
                xaxis_title="Recall",
                yaxis_title="Precision",
                template=self.template,
                height=420,
                xaxis={"range": [0, 1]},
                yaxis={"range": [0, 1.05]},
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping precision-recall chart")
            return ""
        except Exception as e:
            logger.warning("Error generating precision-recall chart: %s", e)
            return ""

    def confusion_matrix_heatmap(self, cm: List[List[int]], labels: Optional[List[str]] = None) -> str:
        """
        Interactive confusion matrix heatmap.

        Args:
            cm: 2D confusion matrix values (list of lists or np.ndarray)
            labels: Class labels (default: ["Negative", "Positive"])

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            labels = labels or ["Negative", "Positive"]
            z = [list(row) for row in cm]

            text = [[str(val) for val in row] for row in z]

            fig = go.Figure(
                go.Heatmap(
                    z=z,
                    x=labels,
                    y=labels,
                    text=text,
                    texttemplate="%{text}",
                    colorscale=[[0, "#ffffff"], [1, THEME_COLORS["primary"]]],
                    colorbar={"title": "Count"},
                    hovertemplate="True: %{y}<br>Predicted: %{x}<br>Count: %{z}<extra></extra>",
                )
            )
            fig.update_layout(
                title="Confusion Matrix",
                xaxis_title="Predicted",
                yaxis_title="True",
                template=self.template,
                height=380,
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping confusion matrix heatmap")
            return ""
        except Exception as e:
            logger.warning("Error generating confusion matrix heatmap: %s", e)
            return ""

    def cumulative_gains(self, gains_data: Dict) -> str:
        """
        Interactive cumulative gains chart.

        Args:
            gains_data: Dict with cumulative_gain and cumulative_population lists

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            pop = gains_data.get("cumulative_population", [])
            gain = gains_data.get("cumulative_gain", [])

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=pop,
                    y=gain,
                    mode="lines+markers",
                    name="Model",
                    line={"color": THEME_COLORS["positive"], "width": 2},
                    marker={"size": 6},
                    hovertemplate="Population: %{x:.1%}<br>Gain: %{y:.1%}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[0, 1],
                    y=[0, 1],
                    mode="lines",
                    name="Random",
                    line={"color": THEME_COLORS["neutral"], "dash": "dash"},
                    hoverinfo="skip",
                )
            )
            fig.update_layout(
                title="Cumulative Gains Curve",
                xaxis_title="Cumulative Population",
                yaxis_title="Cumulative Gain",
                template=self.template,
                height=420,
                xaxis={"tickformat": ".0%"},
                yaxis={"tickformat": ".0%"},
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping cumulative gains chart")
            return ""
        except Exception as e:
            logger.warning("Error generating cumulative gains chart: %s", e)
            return ""

    def lift_chart(self, gains_data: Dict) -> str:
        """
        Interactive lift chart derived from cumulative gains data.

        Args:
            gains_data: Dict with cumulative_gain and cumulative_population lists

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            pop = gains_data.get("cumulative_population", [])
            gain = gains_data.get("cumulative_gain", [])
            lifts = [g / p if p > 0 else 0 for g, p in zip(gain, pop)]

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=pop,
                    y=lifts,
                    mode="lines+markers",
                    name="Model Lift",
                    line={"color": THEME_COLORS["primary"], "width": 2},
                    marker={"size": 6},
                    hovertemplate="Population: %{x:.1%}<br>Lift: %{y:.2f}<extra></extra>",
                )
            )
            fig.add_hline(y=1.0, line_dash="dash", line_color=THEME_COLORS["neutral"], annotation_text="Random (lift=1)")
            fig.update_layout(
                title="Lift Chart",
                xaxis_title="Cumulative Population",
                yaxis_title="Lift",
                template=self.template,
                height=420,
                xaxis={"tickformat": ".0%"},
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping lift chart")
            return ""
        except Exception as e:
            logger.warning("Error generating lift chart: %s", e)
            return ""

    def calibration_curve(self, fraction_pos: List[float], mean_pred: List[float]) -> str:
        """
        Interactive calibration curve.

        Args:
            fraction_pos: Fraction of positives per bin
            mean_pred: Mean predicted probability per bin

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=mean_pred,
                    y=fraction_pos,
                    mode="lines+markers",
                    name="Model",
                    line={"color": THEME_COLORS["primary"], "width": 2},
                    marker={"size": 7},
                    hovertemplate="Mean predicted: %{x:.3f}<br>Fraction positive: %{y:.3f}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[0, 1],
                    y=[0, 1],
                    mode="lines",
                    name="Perfect calibration",
                    line={"color": THEME_COLORS["neutral"], "dash": "dash"},
                    hoverinfo="skip",
                )
            )
            fig.update_layout(
                title="Calibration Curve",
                xaxis_title="Mean Predicted Probability",
                yaxis_title="True Positive Rate",
                template=self.template,
                height=420,
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping calibration curve chart")
            return ""
        except Exception as e:
            logger.warning("Error generating calibration curve chart: %s", e)
            return ""

    def probability_distribution(
        self,
        y_true: List[int],
        y_prob: List[float],
        n_bins: int = 50,
    ) -> str:
        """
        Interactive probability distribution histogram split by class.

        Args:
            y_true: True binary labels
            y_prob: Predicted probabilities
            n_bins: Number of bins

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import numpy as np
            import plotly.graph_objects as go

            y_true_arr = np.asarray(y_true)
            y_prob_arr = np.asarray(y_prob)

            prob_neg = y_prob_arr[y_true_arr == 0].tolist()
            prob_pos = y_prob_arr[y_true_arr == 1].tolist()

            fig = go.Figure()
            fig.add_trace(
                go.Histogram(
                    x=prob_neg,
                    name="Negative Class",
                    opacity=0.6,
                    nbinsx=n_bins,
                    marker_color=THEME_COLORS["primary"],
                    histnorm="probability density",
                )
            )
            fig.add_trace(
                go.Histogram(
                    x=prob_pos,
                    name="Positive Class",
                    opacity=0.6,
                    nbinsx=n_bins,
                    marker_color=THEME_COLORS["negative"],
                    histnorm="probability density",
                )
            )
            fig.update_layout(
                title="Distribution of Predicted Probabilities by Class",
                xaxis_title="Predicted Probability",
                yaxis_title="Density",
                template=self.template,
                barmode="overlay",
                height=420,
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping probability distribution chart")
            return ""
        except Exception as e:
            logger.warning("Error generating probability distribution chart: %s", e)
            return ""

    def feature_importance(self, feature_names: List[str], importances: List[float], top_n: int = 20) -> str:
        """
        Interactive horizontal bar chart of feature importance.

        Args:
            feature_names: List of feature names
            importances: Importance scores
            top_n: Maximum features to show

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import numpy as np
            import plotly.graph_objects as go

            importances_arr = np.asarray(importances)
            n = min(top_n, len(feature_names), len(importances_arr))
            indices = np.argsort(importances_arr)[::-1][:n]
            top_features = [feature_names[i] for i in indices]
            top_imp = importances_arr[indices]

            fig = go.Figure(
                go.Bar(
                    x=top_imp[::-1].tolist(),
                    y=top_features[::-1],
                    orientation="h",
                    marker_color=THEME_COLORS["primary"],
                    hovertemplate="<b>%{y}</b><br>Importance: %{x:.4f}<extra></extra>",
                )
            )
            fig.update_layout(
                title=f"Feature Importance (Top {n})",
                xaxis_title="Importance",
                template=self.template,
                height=max(400, n * 22),
                yaxis={"categoryorder": "total ascending"},
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping feature importance chart")
            return ""
        except Exception as e:
            logger.warning("Error generating feature importance chart: %s", e)
            return ""

    def threshold_sweep(self, threshold_metrics: Dict, current_threshold: float = 0.5) -> str:
        """
        Interactive threshold sweep chart (precision, recall, F1 vs threshold).

        Args:
            threshold_metrics: Dict with thresholds, precisions, recalls, f1s lists
            current_threshold: The threshold currently in use (vertical line)

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            thresholds = threshold_metrics.get("thresholds", [])
            precisions = threshold_metrics.get("precisions", [])
            recalls = threshold_metrics.get("recalls", [])
            f1s = threshold_metrics.get("f1s", [])

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=thresholds,
                    y=precisions,
                    mode="lines",
                    name="Precision",
                    line={"color": THEME_COLORS["primary"], "width": 2},
                    hovertemplate="Threshold: %{x:.3f}<br>Precision: %{y:.3f}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=thresholds,
                    y=recalls,
                    mode="lines",
                    name="Recall",
                    line={"color": THEME_COLORS["secondary"], "width": 2},
                    hovertemplate="Threshold: %{x:.3f}<br>Recall: %{y:.3f}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=thresholds,
                    y=f1s,
                    mode="lines",
                    name="F1",
                    line={"color": THEME_COLORS["positive"], "width": 2, "dash": "dash"},
                    hovertemplate="Threshold: %{x:.3f}<br>F1: %{y:.3f}<extra></extra>",
                )
            )
            fig.add_vline(
                x=current_threshold,
                line_color=THEME_COLORS["negative"],
                line_dash="dot",
                line_width=2,
                annotation_text=f"Current ({current_threshold:.2f})",
                annotation_position="top right",
            )
            fig.update_layout(
                title="Metrics vs Classification Threshold",
                xaxis_title="Threshold",
                yaxis_title="Score",
                template=self.template,
                height=420,
                xaxis={"range": [0, 1]},
                yaxis={"range": [0, 1.05]},
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping threshold sweep chart")
            return ""
        except Exception as e:
            logger.warning("Error generating threshold sweep chart: %s", e)
            return ""

    def segment_metrics_chart(self, segment_data: Dict, metric: str = "f1") -> str:
        """
        Interactive bar chart of a metric broken down by segment value.

        Args:
            segment_data: Dict mapping segment_value -> metrics dict
            metric: Which metric to display (default: f1)

        Returns:
            str: HTML string of the Plotly chart
        """
        try:
            import plotly.graph_objects as go

            if not segment_data:
                return ""

            segments = list(segment_data.keys())
            values = [segment_data[s].get(metric, 0) for s in segments]

            # Color by value relative to mean
            mean_val = sum(values) / len(values) if values else 0
            colors = [THEME_COLORS["positive"] if v >= mean_val else THEME_COLORS["negative"] for v in values]

            fig = go.Figure(
                go.Bar(
                    x=segments,
                    y=values,
                    marker_color=colors,
                    text=[f"{v:.3f}" for v in values],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>" + metric.upper() + ": %{y:.4f}<extra></extra>",
                )
            )
            fig.update_layout(
                title=f"{metric.upper()} by Segment",
                xaxis_title="Segment",
                yaxis_title=metric.upper(),
                template=self.template,
                height=max(380, len(segments) * 25),
                xaxis={"tickangle": -35},
                yaxis={"range": [0, 1.1]},
            )
            return self._to_html(fig)

        except ImportError:
            logger.warning("plotly not available, skipping segment metrics chart")
            return ""
        except Exception as e:
            logger.warning("Error generating segment metrics chart: %s", e)
            return ""
