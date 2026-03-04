"""
Training Run Index Generator for Energizados Framework.

Generates an HTML index of all training runs in the output directory,
showing metrics and links to individual evaluation reports.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RunIndexGenerator:
    """
    Generates an HTML index of all training runs in the output directory.

    Scans output/train-*/ directories, reads evaluation JSON reports,
    and generates a summary table with metrics and links to reports.

    Example:
        >>> generator = RunIndexGenerator()
        >>> index_path = generator.generate_index_html(Path("output"))
    """

    def scan_runs(self, output_dir: Path) -> List[Dict]:
        """
        Scans the output directory for training run subdirectories.

        Args:
            output_dir: Path to the output directory (e.g., output/)

        Returns:
            List of dicts with run info and metrics, sorted newest first
        """
        runs = []

        for run_dir in sorted(output_dir.glob("train-*/"), reverse=True):
            if not run_dir.is_dir():
                continue

            json_path = run_dir / "reports" / "evaluation" / "evaluation_report.json"
            html_path = run_dir / "reports" / "evaluation" / "evaluation_report.html"

            if not json_path.exists():
                logger.warning(f"No evaluation report found in {run_dir.name}, skipping.")
                continue

            try:
                with open(json_path) as f:
                    report_data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Could not read report from {run_dir.name}: {e}")
                continue

            metrics = report_data.get("metrics", {})
            model_info = report_data.get("model_info", {})

            # Relative link from output/ to the evaluation report
            relative_link = None
            if html_path.exists():
                relative_link = f"{run_dir.name}/reports/evaluation/evaluation_report.html"

            runs.append(
                {
                    "run_name": run_dir.name,
                    "timestamp": report_data.get("timestamp", ""),
                    "model_type": model_info.get("model_class", model_info.get("model_type", "—")),
                    "auc": metrics.get("auc"),
                    "f1": metrics.get("f1"),
                    "precision": metrics.get("precision"),
                    "recall": metrics.get("recall"),
                    "accuracy": metrics.get("accuracy"),
                    "threshold": metrics.get("threshold"),
                    "html_link": relative_link,
                }
            )

        return runs

    def generate_index_html(self, output_dir: Path) -> Optional[Path]:
        """
        Generates output/index.html with a table of all training runs.

        Args:
            output_dir: Path to the output directory (e.g., output/)

        Returns:
            Path to the generated index.html, or None if output_dir doesn't exist
        """
        if not output_dir.exists():
            logger.warning(f"Output directory does not exist: {output_dir}")
            return None

        runs = self.scan_runs(output_dir)
        html_content = self._build_html(runs, output_dir)

        index_path = output_dir / "index.html"
        with open(index_path, "w") as f:
            f.write(html_content)

        logger.info(f"Training index generated: {index_path} ({len(runs)} runs)")
        return index_path

    def _fmt(self, value, decimals: int = 4) -> str:
        """Format a numeric metric value."""
        if value is None:
            return "—"
        try:
            return f"{float(value):.{decimals}f}"
        except (TypeError, ValueError):
            return str(value)

    def _build_html(self, runs: List[Dict], output_dir: Path) -> str:
        """Builds the full HTML content for the index page."""
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        table_rows = self._build_table_rows(runs)
        run_count = len(runs)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Training Runs Index - Energizados</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 35px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            font-size: 2em;
            margin-bottom: 5px;
        }}
        .header p {{
            opacity: 0.85;
            font-size: 0.95em;
        }}
        .summary-bar {{
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }}
        .summary-card {{
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.07);
            border-left: 4px solid #667eea;
            min-width: 140px;
        }}
        .summary-card .value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }}
        .summary-card .label {{
            font-size: 0.8em;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .section {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            overflow: hidden;
        }}
        .section-header {{
            padding: 18px 25px;
            border-bottom: 2px solid #667eea;
        }}
        .section-header h2 {{
            color: #667eea;
            font-size: 1.2em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.92em;
        }}
        thead th {{
            background: #f8f9fa;
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: #555;
            text-transform: uppercase;
            font-size: 0.78em;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #e9ecef;
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }}
        thead th:hover {{ background: #e9ecef; color: #333; }}
        thead th.sorted-asc::after {{ content: " ▲"; color: #667eea; }}
        thead th.sorted-desc::after {{ content: " ▼"; color: #667eea; }}
        tbody tr {{
            border-bottom: 1px solid #f0f0f0;
            transition: background 0.15s;
        }}
        tbody tr:hover {{ background: #f8f9ff; }}
        tbody tr:last-child {{ border-bottom: none; }}
        td {{ padding: 12px 16px; vertical-align: middle; }}
        td.run-name {{
            font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
            font-size: 0.88em;
            color: #444;
            font-weight: 500;
        }}
        td.metric {{
            text-align: right;
            font-variant-numeric: tabular-nums;
            font-weight: 500;
        }}
        td.metric.high {{ color: #28a745; }}
        td.metric.mid {{ color: #ffc107; }}
        td.metric.low {{ color: #dc3545; }}
        td.metric.na {{ color: #999; }}
        .report-link {{
            display: inline-block;
            padding: 5px 12px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.82em;
            font-weight: 500;
            transition: background 0.15s;
        }}
        .report-link:hover {{ background: #5a6fd6; }}
        .no-runs {{
            padding: 50px;
            text-align: center;
            color: #aaa;
            font-size: 1.05em;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #aaa;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Training Runs Index</h1>
        <p>Generated on {generated_at} &nbsp;·&nbsp; {run_count} run(s) found in <code>{output_dir.resolve().name}/</code></p>
    </div>

    <div class="summary-bar">
        <div class="summary-card">
            <div class="value">{run_count}</div>
            <div class="label">Total Runs</div>
        </div>
        {self._build_best_metric_card(runs, "auc", "Best AUC")}
        {self._build_best_metric_card(runs, "f1", "Best F1")}
    </div>

    <div class="section">
        <div class="section-header">
            <h2>All Training Runs</h2>
        </div>
        {self._build_table(table_rows, run_count)}
    </div>

    <div class="footer">
        Generated by Energizados Framework
    </div>

    <script>
        // Simple column sorting
        document.querySelectorAll('thead th[data-col]').forEach(function(th) {{
            th.addEventListener('click', function() {{
                var table = th.closest('table');
                var tbody = table.querySelector('tbody');
                var col = parseInt(th.getAttribute('data-col'));
                var asc = th.classList.contains('sorted-asc') ? false : true;

                table.querySelectorAll('thead th').forEach(function(h) {{
                    h.classList.remove('sorted-asc', 'sorted-desc');
                }});
                th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');

                var rows = Array.from(tbody.querySelectorAll('tr'));
                rows.sort(function(a, b) {{
                    var va = a.querySelectorAll('td')[col].getAttribute('data-val') || a.querySelectorAll('td')[col].textContent.trim();
                    var vb = b.querySelectorAll('td')[col].getAttribute('data-val') || b.querySelectorAll('td')[col].textContent.trim();
                    var na = parseFloat(va), nb = parseFloat(vb);
                    if (!isNaN(na) && !isNaN(nb)) {{ return asc ? na - nb : nb - na; }}
                    return asc ? va.localeCompare(vb) : vb.localeCompare(va);
                }});
                rows.forEach(function(r) {{ tbody.appendChild(r); }});
            }});
        }});
    </script>
</body>
</html>"""

    def _metric_class(self, value, key: str) -> str:
        """Returns CSS class based on metric value."""
        if value is None:
            return "na"
        try:
            v = float(value)
        except (TypeError, ValueError):
            return "na"
        if key in ("auc", "f1", "precision", "recall", "accuracy"):
            if v >= 0.8:
                return "high"
            if v >= 0.6:
                return "mid"
            return "low"
        return ""

    def _build_best_metric_card(self, runs: List[Dict], key: str, label: str) -> str:
        """Builds a summary card showing the best value for a metric."""
        values = [r[key] for r in runs if r.get(key) is not None]
        if not values:
            return ""
        best = max(float(v) for v in values)
        return f"""
        <div class="summary-card">
            <div class="value">{best:.4f}</div>
            <div class="label">{label}</div>
        </div>"""

    def _build_table_rows(self, runs: List[Dict]) -> List[str]:
        """Builds HTML rows for each training run."""
        rows = []
        for run in runs:
            link_html = f'<a href="{run["html_link"]}" class="report-link" target="_blank">View Report</a>' if run.get("html_link") else "—"
            auc_cls = self._metric_class(run.get("auc"), "auc")
            f1_cls = self._metric_class(run.get("f1"), "f1")
            prec_cls = self._metric_class(run.get("precision"), "precision")
            rec_cls = self._metric_class(run.get("recall"), "recall")

            rows.append(f"""
            <tr>
                <td class="run-name" data-val="{run['run_name']}">{run['run_name']}</td>
                <td data-val="{run['timestamp']}">{run['timestamp'][:19] if run['timestamp'] else '—'}</td>
                <td data-val="{run['model_type']}">{run['model_type']}</td>
                <td class="metric {auc_cls}" data-val="{run.get('auc', '')}">{self._fmt(run.get('auc'))}</td>
                <td class="metric {f1_cls}" data-val="{run.get('f1', '')}">{self._fmt(run.get('f1'))}</td>
                <td class="metric {prec_cls}" data-val="{run.get('precision', '')}">{self._fmt(run.get('precision'))}</td>
                <td class="metric {rec_cls}" data-val="{run.get('recall', '')}">{self._fmt(run.get('recall'))}</td>
                <td>{link_html}</td>
            </tr>""")
        return rows

    def _build_table(self, rows: List[str], run_count: int) -> str:
        """Builds the full table HTML."""
        if run_count == 0:
            return '<div class="no-runs">No training runs found yet. Run a training to see results here.</div>'

        rows_html = "".join(rows)
        return f"""
        <table>
            <thead>
                <tr>
                    <th data-col="0">Run</th>
                    <th data-col="1">Timestamp</th>
                    <th data-col="2">Model</th>
                    <th data-col="3">AUC</th>
                    <th data-col="4">F1</th>
                    <th data-col="5">Precision</th>
                    <th data-col="6">Recall</th>
                    <th>Report</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>"""
