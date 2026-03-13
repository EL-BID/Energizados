"""
Report Module for Energizados Framework.

Generates evaluation reports in HTML and JSON.
Phase 1-3: Self-contained (base64 images), interactive Plotly charts,
sidebar navigation, segment metrics and threshold sweep sections.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from energizados.evaluation._html_templates import DARK_TOGGLE_JS, REPORT_CSS

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Evaluation report generator.

    Args:
        output_dir: Directory where to save reports

    Example:
        >>> reporter = ReportGenerator("reports/evaluation/")
        >>> reporter.generate_html(metrics, plots)
        >>> reporter.generate_json(metrics)
    """

    def __init__(self, output_dir: str = "reports/evaluation/"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html(
        self,
        metrics: Dict,
        plots: Dict[str, str],
        model_info: Optional[Dict] = None,
        save_path: Optional[str] = None,
        calibration_result: Optional[Dict] = None,
        plots_embedded: Optional[Dict[str, str]] = None,
        plots_interactive: Optional[Dict[str, str]] = None,
        threshold_metrics: Optional[Dict] = None,
        segment_metrics: Optional[Dict] = None,
    ) -> str:
        """
        Generates HTML report with results.

        Args:
            metrics: Dictionary with calculated metrics
            plots: Dictionary with paths to plots
            model_info: Model information (optional)
            save_path: Path to save (optional)
            calibration_result: Result from ThresholdCalibrator.calibrate() (optional)
            plots_embedded: Dict of plot_name -> base64 data URI (optional, preferred over file paths)
            plots_interactive: Dict of plot_name -> HTML string of interactive Plotly chart (optional)
            threshold_metrics: Dict with threshold sweep data (optional)
            segment_metrics: Dict mapping column -> segment_value -> metrics (optional)

        Returns:
            str: Path where report was saved
        """
        html_content = self._build_html(
            metrics,
            plots,
            model_info,
            calibration_result,
            plots_embedded=plots_embedded,
            plots_interactive=plots_interactive,
            threshold_metrics=threshold_metrics,
            segment_metrics=segment_metrics,
        )

        path = save_path or str(self.output_dir / "evaluation_report.html")

        with open(path, "w") as f:
            f.write(html_content)

        logger.info(f"HTML report saved to: {path}")
        return path

    def generate_json(
        self,
        metrics: Dict,
        model_info: Optional[Dict] = None,
        save_path: Optional[str] = None,
        calibration_result: Optional[Dict] = None,
        threshold_metrics: Optional[Dict] = None,
        segment_metrics: Optional[Dict] = None,
    ) -> str:
        """
        Generates JSON report with results.

        Args:
            metrics: Dictionary with calculated metrics
            model_info: Model information (optional)
            save_path: Path to save (optional)
            calibration_result: Result from ThresholdCalibrator.calibrate() (optional)
            threshold_metrics: Threshold sweep data (optional)
            segment_metrics: Per-segment metrics (optional)

        Returns:
            str: Path where report was saved
        """
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "model_info": model_info or {},
        }

        if calibration_result is not None:
            report_data["calibration"] = {
                "enabled": True,
                "method": calibration_result.get("method"),
                "threshold_used": calibration_result.get("threshold"),
                "params": calibration_result.get("params", {}),
                "metrics_at_threshold": calibration_result.get("metrics_at_threshold", {}),
            }

        if threshold_metrics is not None:
            report_data["threshold_metrics"] = threshold_metrics

        if segment_metrics is not None:
            report_data["segment_metrics"] = segment_metrics

        path = save_path or str(self.output_dir / "evaluation_report.json")

        with open(path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        logger.info(f"JSON report saved to: {path}")
        return path

    # ------------------------------------------------------------------
    # HTML builders
    # ------------------------------------------------------------------

    def _build_html(
        self,
        metrics: Dict,
        plots: Dict[str, str],
        model_info: Optional[Dict] = None,
        calibration_result: Optional[Dict] = None,
        plots_embedded: Optional[Dict[str, str]] = None,
        plots_interactive: Optional[Dict[str, str]] = None,
        threshold_metrics: Optional[Dict] = None,
        segment_metrics: Optional[Dict] = None,
    ) -> str:
        """Builds HTML content of the report."""
        # Convert file paths to relative names so the HTML works from the report directory
        plots_rel = {k: Path(v).name for k, v in plots.items()}

        calibration_section = self._build_calibration_html(calibration_result) if calibration_result else ""

        # Determine which sections are available for the sidebar
        has_threshold_sweep = threshold_metrics is not None and "thresholds" in threshold_metrics
        has_segments = bool(segment_metrics)
        has_visualizations = bool(plots)
        has_model_info = bool(model_info)

        sidebar_html = self._build_sidebar(
            has_calibration=bool(calibration_result),
            has_threshold_sweep=has_threshold_sweep,
            has_segments=has_segments,
            has_visualizations=has_visualizations,
            has_model_info=has_model_info,
        )

        threshold_sweep_section = ""
        if has_threshold_sweep:
            threshold_sweep_section = self._build_threshold_sweep_html(
                threshold_metrics,
                metrics.get("threshold", 0.5),
                plots_interactive=plots_interactive,
                plots_embedded=plots_embedded,
            )

        segment_section = ""
        if has_segments:
            segment_section = self._build_segment_metrics_html(segment_metrics, plots_interactive=plots_interactive)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evaluation Report - Energizados</title>
    <style>
{REPORT_CSS}
    </style>
</head>
<body>
    <div class="layout">
        {sidebar_html}
        <main class="main">
            <div class="header" id="top">
                <button class="dark-toggle" id="dark-toggle-btn">☾ Dark</button>
                <h1>Model Evaluation Report</h1>
                <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>

            <div class="section" id="section-metrics">
                <h2>Performance Metrics</h2>
                <div class="metrics-grid">
                    {self._build_metrics_html(metrics)}
                </div>
            </div>

            {calibration_section}

            <div id="section-confusion">
                {self._build_confusion_matrix_html(metrics)}
            </div>

            {threshold_sweep_section}

            {segment_section}

            <div class="section" id="section-visualizations">
                <h2>Visualizations</h2>
                <div class="plots-grid">
                    {self._build_plots_html(plots_rel, plots_embedded=plots_embedded, plots_interactive=plots_interactive)}
                </div>
            </div>

            {self._build_model_info_html(model_info) if model_info else ''}

            <div class="footer">
                <p>Generated by Energizados Framework</p>
            </div>
        </main>
    </div>

    {DARK_TOGGLE_JS}
    <div class="plot-modal" id="plot-modal">
        <div class="plot-modal-content">
            <button class="plot-modal-close" id="plot-modal-close">&times;</button>
            <h2 class="plot-modal-title" id="plot-modal-title">Chart</h2>
            <div class="plot-modal-body" id="plot-modal-body"></div>
        </div>
    </div>
    <script>
    // Resize Plotly charts when inside <details> blocks that are opened
    document.querySelectorAll('details').forEach(function(det) {{
        det.addEventListener('toggle', function() {{
            if (det.open) {{
                det.querySelectorAll('.js-plotly-plot').forEach(function(el) {{
                    if (window.Plotly) window.Plotly.Plots.resize(el);
                }});
            }}
        }});
    }});

    // Maximize plot functionality
    (function() {{
        var modal = document.getElementById('plot-modal');
        var modalBody = document.getElementById('plot-modal-body');
        var modalTitle = document.getElementById('plot-modal-title');
        var closeBtn = document.getElementById('plot-modal-close');
        var _activePlotDiv = null;
        var _originalParent = null;

        function closeModal() {{
            modal.classList.remove('active');
            // Move the Plotly div back to its original container
            if (_activePlotDiv && _originalParent) {{
                _originalParent.appendChild(_activePlotDiv);
                var div = _activePlotDiv;
                setTimeout(function() {{
                    if (window.Plotly) Plotly.Plots.resize(div);
                }}, 50);
                _activePlotDiv = null;
                _originalParent = null;
            }}
            modalBody.innerHTML = '';
        }}

        document.querySelectorAll('.plot-maximize-btn').forEach(function(btn) {{
            btn.addEventListener('click', function() {{
                var container = this.closest('.plot-container');
                var plotContent = container.querySelector('.plot-content');
                var plotDiv = plotContent.querySelector('.js-plotly-plot');
                var title = container.querySelector('h3').textContent;

                modalTitle.textContent = title;
                modalBody.innerHTML = '';

                if (plotDiv && window.Plotly) {{
                    // Move the actual Plotly element — scripts won't re-run on innerHTML clone
                    _activePlotDiv = plotDiv;
                    _originalParent = plotContent;
                    modalBody.appendChild(plotDiv);
                    modal.classList.add('active');
                    setTimeout(function() {{
                        Plotly.Plots.resize(plotDiv);
                    }}, 50);
                }} else {{
                    // Static content (images)
                    modalBody.innerHTML = plotContent.innerHTML;
                    modal.classList.add('active');
                }}
            }});
        }});

        closeBtn.addEventListener('click', closeModal);
        modal.addEventListener('click', function(e) {{
            if (e.target === modal) closeModal();
        }});
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape' && modal.classList.contains('active')) closeModal();
        }});
    }})();
    </script>
</body>
</html>
"""

    def _build_sidebar(
        self,
        has_calibration: bool = False,
        has_threshold_sweep: bool = False,
        has_segments: bool = False,
        has_visualizations: bool = True,
        has_model_info: bool = True,
    ) -> str:
        """Builds the sidebar navigation."""
        links = ['<a href="#top">↑ Top</a>']
        links.append('<a href="#section-metrics">Performance Metrics</a>')
        links.append('<a href="#section-confusion">Confusion Matrix</a>')
        if has_calibration:
            links.append('<a href="#section-calibration">Threshold Calibration</a>')
        if has_threshold_sweep:
            links.append('<a href="#section-threshold-sweep">Threshold Sweep</a>')
        if has_segments:
            links.append('<a href="#section-segments">Segment Metrics</a>')
        if has_visualizations:
            links.append('<a href="#section-visualizations">Visualizations</a>')
        if has_model_info:
            links.append('<a href="#section-model-info">Model Information</a>')

        links_html = "\n".join(links)
        return f"""
        <nav class="sidebar">
            <div class="sidebar-title">Navigation</div>
            {links_html}
        </nav>"""

    def _build_metrics_html(self, metrics: Dict) -> str:
        """Builds HTML for metric cards."""
        html_parts = []

        metric_configs = [
            ("AUC", "auc", "Area Under ROC Curve"),
            ("F1 Score", "f1", "F1 Score"),
            ("Precision", "precision", "Precision"),
            ("Recall", "recall", "Recall/Sensitivity"),
            ("Accuracy", "accuracy", "Accuracy"),
            ("Threshold", "threshold", "Decision Threshold"),
        ]

        for label, key, _description in metric_configs:
            value = metrics.get(key)
            if value is None:
                continue
            display_value = f"{value:.4f}" if isinstance(value, (int, float)) else str(value)

            html_parts.append(f"""
            <div class="metric-card">
                <div class="value">{display_value}</div>
                <div class="label">{label}</div>
            </div>
""")

        return "".join(html_parts)

    def _build_calibration_html(self, calibration_result: Dict) -> str:
        """Builds HTML section showing threshold calibration info."""
        method = calibration_result.get("method", "—")
        threshold = calibration_result.get("threshold", 0)
        params = calibration_result.get("params", {})
        at_threshold = calibration_result.get("metrics_at_threshold", {})

        params_str = " &nbsp;|&nbsp; ".join(f"<strong>{k}:</strong> {v}" for k, v in params.items())

        return f"""
    <div class="section" id="section-calibration">
        <h2>Threshold Calibration</h2>
        <div class="calibration-info">
            <p><strong>Method:</strong> {method} &nbsp;&nbsp; {params_str}</p>
            <p><strong>Calibrated Threshold:</strong> {threshold:.4f}</p>
            <p><strong>Precision @ threshold:</strong> {at_threshold.get('precision', 0):.4f}</p>
            <p><strong>Recall @ threshold:</strong> {at_threshold.get('recall', 0):.4f}</p>
            <p><strong>F1 @ threshold:</strong> {at_threshold.get('f1', 0):.4f}</p>
        </div>
    </div>
"""

    def _build_confusion_matrix_html(self, metrics: Dict) -> str:
        """Builds HTML for confusion matrix (numeric cells only — image is in Visualizations)."""
        cm = metrics.get("confusion_matrix", {})
        if not cm or "matrix" not in cm:
            return ""

        tp = cm.get("tp", 0)
        tn = cm.get("tn", 0)
        fp = cm.get("fp", 0)
        fn = cm.get("fn", 0)

        return f"""
    <div class="section">
        <h2>Confusion Matrix</h2>
        <div class="confusion-matrix">
            <div class="cm-cell tn">
                <div class="value">{tn}</div>
                <div class="label">True Negative</div>
            </div>
            <div class="cm-cell fp">
                <div class="value">{fp}</div>
                <div class="label">False Positive</div>
            </div>
            <div class="cm-cell fn">
                <div class="value">{fn}</div>
                <div class="label">False Negative</div>
            </div>
            <div class="cm-cell tp">
                <div class="value">{tp}</div>
                <div class="label">True Positive</div>
            </div>
        </div>
    </div>
"""

    def _build_threshold_sweep_html(
        self,
        threshold_metrics: Dict,
        current_threshold: float,
        plots_interactive: Optional[Dict[str, str]] = None,
        plots_embedded: Optional[Dict[str, str]] = None,
    ) -> str:
        """Builds the threshold sweep section with chart and summary table."""
        # Find optimal threshold by F1
        thresholds = threshold_metrics.get("thresholds", [])
        f1s = threshold_metrics.get("f1s", [])
        precisions = threshold_metrics.get("precisions", [])
        recalls = threshold_metrics.get("recalls", [])

        optimal_idx = int(max(range(len(f1s)), key=lambda i: f1s[i])) if f1s else 0
        optimal_threshold = thresholds[optimal_idx] if thresholds else 0.5

        # Build summary table: show rows around current and optimal
        show_steps = list(range(0, len(thresholds), max(1, len(thresholds) // 10)))
        # Always include optimal and nearest-to-current rows
        current_idx = min(range(len(thresholds)), key=lambda i: abs(thresholds[i] - current_threshold))
        show_steps = sorted(set(show_steps) | {optimal_idx, current_idx})

        rows_html = ""
        for i in show_steps:
            row_class = "optimal-row" if i == optimal_idx else ""
            t = thresholds[i] if i < len(thresholds) else 0
            p = precisions[i] if i < len(precisions) else 0
            r = recalls[i] if i < len(recalls) else 0
            f = f1s[i] if i < len(f1s) else 0
            marker = " ★ optimal" if i == optimal_idx else (" ← current" if i == current_idx and i != optimal_idx else "")
            rows_html += f"""
                <tr class="{row_class}">
                    <td>{t:.3f}{marker}</td>
                    <td>{p:.4f}</td>
                    <td>{r:.4f}</td>
                    <td>{f:.4f}</td>
                </tr>"""

        # Prefer interactive chart
        chart_html = ""
        if plots_interactive and "threshold_sweep" in plots_interactive:
            chart_html = plots_interactive["threshold_sweep"]
        elif plots_embedded and "threshold_sweep" in plots_embedded:
            chart_html = f'<img src="{plots_embedded["threshold_sweep"]}" alt="Threshold Sweep" style="max-width:100%;height:auto;">'

        optimal_f1 = f1s[optimal_idx] if f1s else 0.0
        return f"""
    <div class="section" id="section-threshold-sweep">
        <h2>Threshold Sweep</h2>
        <p>Optimal threshold by F1: <strong>{optimal_threshold:.4f}</strong> (F1 = {optimal_f1:.4f})</p>
        {chart_html}
        <div class="threshold-summary">
            <table>
                <thead>
                    <tr>
                        <th>Threshold</th>
                        <th>Precision</th>
                        <th>Recall</th>
                        <th>F1</th>
                    </tr>
                </thead>
                <tbody>{rows_html}
                </tbody>
            </table>
        </div>
    </div>
"""

    def _build_segment_metrics_html(
        self,
        segment_metrics: Dict,
        plots_interactive: Optional[Dict[str, str]] = None,
    ) -> str:
        """Builds segment metrics section with heatmap-colored table."""
        if not segment_metrics:
            return ""

        sections_html = ""
        for col_name, col_segments in segment_metrics.items():
            rows_html = self._build_segment_table_rows(col_segments)

            # Interactive chart for this segment column if available
            chart_html = ""
            chart_key = f"segment_{col_name}"
            if plots_interactive and chart_key in plots_interactive:
                chart_html = plots_interactive[chart_key]

            sections_html += f"""
            <h3 style="color:var(--primary);margin-top:20px;">{col_name}</h3>
            {chart_html}
            <div class="segment-table-wrap">
                <table class="segment-table">
                    <thead>
                        <tr>
                            <th>Segment</th>
                            <th>Count</th>
                            <th>Positive Rate</th>
                            <th>AUC</th>
                            <th>Precision</th>
                            <th>Recall</th>
                            <th>F1</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}
                    </tbody>
                </table>
            </div>"""

        return f"""
    <div class="section" id="section-segments">
        <h2>Segment Metrics</h2>
        {sections_html}
    </div>
"""

    def _build_segment_table_rows(self, col_segments: Dict) -> str:
        """Builds table rows for a single segment column with heatmap coloring."""
        rows = ""
        for segment_val, seg_metrics in col_segments.items():
            count = seg_metrics.get("count", 0)
            pos_rate = seg_metrics.get("positive_rate", 0)
            auc = seg_metrics.get("auc", 0)
            prec = seg_metrics.get("precision", 0)
            rec = seg_metrics.get("recall", 0)
            f1 = seg_metrics.get("f1", 0)

            def _heat_class(v: float) -> str:
                if v >= 0.7:
                    return "heat-high"
                if v >= 0.4:
                    return "heat-mid"
                return "heat-low"

            rows += f"""
                <tr>
                    <td>{segment_val}</td>
                    <td>{count:,}</td>
                    <td>{pos_rate:.2%}</td>
                    <td class="{_heat_class(auc)}">{auc:.4f}</td>
                    <td class="{_heat_class(prec)}">{prec:.4f}</td>
                    <td class="{_heat_class(rec)}">{rec:.4f}</td>
                    <td class="{_heat_class(f1)}">{f1:.4f}</td>
                </tr>"""
        return rows

    def _build_plots_html(
        self,
        plots: Dict[str, str],
        plots_embedded: Optional[Dict[str, str]] = None,
        plots_interactive: Optional[Dict[str, str]] = None,
    ) -> str:
        """Builds HTML for plots. Priority: interactive > base64 > filename."""
        html_parts = []

        # Collect all known plot keys (union of all sources)
        all_keys: List[str] = []
        seen = set()
        for d in [plots_interactive or {}, plots_embedded or {}, plots]:
            for k in d:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)

        # Skip plots that are shown in dedicated sections
        skip_keys = {"threshold_sweep", "confusion_matrix"} | {k for k in (all_keys) if k.startswith("segment_")}

        for plot_name in all_keys:
            if plot_name in skip_keys:
                continue

            label = plot_name.replace("_", " ").title()

            # Priority: interactive > base64 > file path
            if plots_interactive and plot_name in plots_interactive:
                chart_html = plots_interactive[plot_name]
                html_parts.append(f"""
            <div class="plot-container">
                <div class="plot-header">
                    <h3>{label}</h3>
                    <button class="plot-maximize-btn" title="Maximize">⛶</button>
                </div>
                <div class="plot-content">
                    {chart_html}
                </div>
            </div>
""")
            elif plots_embedded and plot_name in plots_embedded:
                b64 = plots_embedded[plot_name]
                html_parts.append(f"""
            <div class="plot-container">
                <div class="plot-header">
                    <h3>{label}</h3>
                    <button class="plot-maximize-btn" title="Maximize">⛶</button>
                </div>
                <div class="plot-content">
                    <img src="{b64}" alt="{label}">
                </div>
            </div>
""")
            elif plot_name in plots:
                plot_path = plots[plot_name]
                html_parts.append(f"""
            <div class="plot-container">
                <div class="plot-header">
                    <h3>{label}</h3>
                    <button class="plot-maximize-btn" title="Maximize">⛶</button>
                </div>
                <div class="plot-content">
                    <img src="{plot_path}" alt="{label}">
                </div>
            </div>
""")

        return "".join(html_parts)

    def _build_model_info_html(self, model_info: Dict) -> str:
        """Builds HTML for model information with cards and collapsible hyperparams."""
        if not model_info:
            return ""

        # Key info cards
        card_keys = ["model_class", "inner_model", "n_features", "n_estimators"]
        cards_html = ""
        for k in card_keys:
            if k in model_info:
                label = k.replace("_", " ").title()
                value = model_info[k]
                cards_html += f"""
                <div class="model-info-card">
                    <div class="label">{label}</div>
                    <div class="value">{value}</div>
                </div>"""

        # Hyperparams in collapsible details
        hyperparams = model_info.get("hyperparams", {})
        hyperparams_html = ""
        if hyperparams:
            param_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in sorted(hyperparams.items()))
            hyperparams_html = f"""
            <details class="hyperparams-details">
                <summary>Hyperparameters ({len(hyperparams)} params)</summary>
                <table class="hyperparams-table">
                    <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
                    <tbody>{param_rows}</tbody>
                </table>
            </details>"""

        # Fallback: show remaining keys as simple text
        shown_keys = set(card_keys) | {"hyperparams"}
        extra_lines = [f"<strong>{k}:</strong> {v}" for k, v in model_info.items() if k not in shown_keys]
        extra_html = (
            f'<p style="font-size:0.88em;color:var(--text-muted);margin-top:8px;">{" &nbsp;|&nbsp; ".join(extra_lines)}</p>'
            if extra_lines
            else ""
        )

        return f"""
    <div class="section" id="section-model-info">
        <h2>Model Information</h2>
        <div class="model-info-cards">{cards_html}</div>
        {hyperparams_html}
        {extra_html}
    </div>
"""
