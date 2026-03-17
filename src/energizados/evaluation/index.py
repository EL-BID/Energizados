"""
Training Run Index Generator for Energizados Framework.

Generates an HTML index of all training runs in the output directory,
showing metrics and links to individual evaluation reports.
Phase 4: Search/filter, Accuracy/Threshold columns, delta comparison, mini bar charts.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from energizados.evaluation._html_templates import DARK_TOGGLE_JS, INDEX_CSS

logger = logging.getLogger(__name__)


class RunIndexGenerator:
    """
    Generates an HTML index of all training runs in the output directory.

    Scans output/train-*/ directories, reads evaluation JSON reports,
    and generates a summary table with metrics and links to reports.
    Supports side-by-side run comparison via checkboxes.

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

        # Collect unique model types for dropdown filter
        model_types = sorted(
            {r["model_type"] for r in runs if r.get("model_type") and r["model_type"] != "—"}
        )
        model_type_options = "".join(f'<option value="{m}">{m}</option>' for m in model_types)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Training Runs Index - Energizados</title>
    <style>
{INDEX_CSS}
    </style>
</head>
<body>
    <div class="header">
        <button class="dark-toggle" id="dark-toggle-btn">☾ Dark</button>
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
        {self._build_best_metric_card(runs, "precision", "Best Precision")}
        {self._build_best_metric_card(runs, "recall", "Best Recall")}
    </div>

    <div id="comparison-panel">
        <div class="section-header">
            <h2>Run Comparison</h2>
            <button class="btn-close-compare" onclick="closeComparison()">Close ✕</button>
        </div>
        <div id="comparison-body" style="overflow-x:auto;padding:0 0 10px 0"></div>
    </div>

    <div class="section">
        <div class="section-header">
            <h2>All Training Runs</h2>
        </div>
        <div class="search-row">
            <input type="text" class="search-bar" id="search-input" placeholder="Search by run name, model…" oninput="filterTable()">
            <select class="filter-dropdown" id="model-filter" onchange="filterTable()">
                <option value="">All models</option>
                {model_type_options}
            </select>
        </div>
        {self._build_table(table_rows, run_count)}
    </div>

    <div class="footer">
        Generated by Energizados Framework
    </div>

    <div class="compare-bar" id="compare-bar">
        <span><strong id="compare-count">0</strong> runs selected</span>
        <button class="btn-compare" onclick="showComparison()">Compare</button>
        <button class="btn-clear-compare" onclick="clearComparison()">Clear</button>
    </div>

    {DARK_TOGGLE_JS}
    <script>
        // ----------------------------------------------------------------
        // Column sorting
        // ----------------------------------------------------------------
        document.querySelectorAll('thead th[data-col]').forEach(function(th) {{
            th.addEventListener('click', function() {{
                var table = th.closest('table');
                var tbody = table.querySelector('tbody');
                var col = parseInt(th.getAttribute('data-col'));
                var asc = !th.classList.contains('sorted-asc');

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

        // ----------------------------------------------------------------
        // Search & filter
        // ----------------------------------------------------------------
        function filterTable() {{
            var query = document.getElementById('search-input').value.toLowerCase();
            var modelFilter = document.getElementById('model-filter').value.toLowerCase();
            document.querySelectorAll('tbody tr').forEach(function(row) {{
                var text = row.textContent.toLowerCase();
                var modelCell = row.querySelectorAll('td')[3];
                var modelText = modelCell ? modelCell.textContent.toLowerCase() : '';
                var matchSearch = !query || text.includes(query);
                var matchModel = !modelFilter || modelText.includes(modelFilter);
                row.classList.toggle('hidden', !(matchSearch && matchModel));
            }});
        }}

        // ----------------------------------------------------------------
        // Run comparison
        // ----------------------------------------------------------------
        var selectedRuns = {{}};

        function updateCompareBar() {{
            var count = Object.keys(selectedRuns).length;
            document.getElementById('compare-count').textContent = count;
            var bar = document.getElementById('compare-bar');
            if (count >= 2) {{
                bar.classList.add('visible');
            }} else {{
                bar.classList.remove('visible');
                document.getElementById('comparison-panel').style.display = 'none';
            }}
        }}

        document.querySelectorAll('.row-select').forEach(function(cb) {{
            cb.addEventListener('change', function() {{
                var row = cb.closest('tr');
                var cells = row.querySelectorAll('td');
                // col 0=checkbox, 1=run, 2=timestamp, 3=model,
                // 4=AUC, 5=F1, 6=Precision, 7=Recall, 8=Accuracy, 9=Threshold, 10=Report
                var runName = cells[1].textContent.trim();
                if (cb.checked) {{
                    row.classList.add('selected');
                    selectedRuns[runName] = {{
                        run: runName,
                        timestamp: cells[2].textContent.trim(),
                        model: cells[3].textContent.trim(),
                        auc: cells[4].getAttribute('data-val') || cells[4].textContent.trim(),
                        f1: cells[5].getAttribute('data-val') || cells[5].textContent.trim(),
                        precision: cells[6].getAttribute('data-val') || cells[6].textContent.trim(),
                        recall: cells[7].getAttribute('data-val') || cells[7].textContent.trim(),
                        accuracy: cells[8].getAttribute('data-val') || cells[8].textContent.trim(),
                        threshold: cells[9].getAttribute('data-val') || cells[9].textContent.trim()
                    }};
                }} else {{
                    row.classList.remove('selected');
                    delete selectedRuns[runName];
                }}
                updateCompareBar();
            }});
        }});

        function showComparison() {{
            var panel = document.getElementById('comparison-panel');
            var runs = Object.values(selectedRuns);
            var isTwo = runs.length === 2;

            var headers = '<th></th>' + runs.map(function(r) {{
                return '<th style="color:var(--primary)">' + r.run + '</th>';
            }}).join('');
            if (isTwo) headers += '<th>Delta</th>';

            var metricRows = [
                ['Timestamp', runs.map(function(r) {{ return {{ val: r.timestamp, numeric: false }}; }})],
                ['Model', runs.map(function(r) {{ return {{ val: r.model, numeric: false }}; }})],
                ['AUC', runs.map(function(r) {{ return {{ val: r.auc, numeric: true }}; }})],
                ['F1', runs.map(function(r) {{ return {{ val: r.f1, numeric: true }}; }})],
                ['Precision', runs.map(function(r) {{ return {{ val: r.precision, numeric: true }}; }})],
                ['Recall', runs.map(function(r) {{ return {{ val: r.recall, numeric: true }}; }})],
                ['Accuracy', runs.map(function(r) {{ return {{ val: r.accuracy, numeric: true }}; }})],
                ['Threshold', runs.map(function(r) {{ return {{ val: r.threshold, numeric: true }}; }})]
            ];

            var rowsHtml = metricRows.map(function(row) {{
                var label = row[0];
                var cells = row[1];
                var best = null;
                if (cells[0].numeric) {{
                    var nums = cells.map(function(c) {{ return parseFloat(c.val); }});
                    if (!nums.some(isNaN)) best = Math.max.apply(null, nums);
                }}
                var cellsHtml = cells.map(function(c) {{
                    var highlight = (best !== null && parseFloat(c.val) === best) ?
                        ' style="color:var(--positive);font-weight:700"' : '';
                    // Mini bar (only for numeric metrics 0..1)
                    var barHtml = '';
                    if (cells[0].numeric && parseFloat(c.val) <= 1 && parseFloat(c.val) >= 0) {{
                        var pct = (parseFloat(c.val) * 100).toFixed(1);
                        barHtml = '<div class="mini-bar-wrap"><div class="mini-bar" style="width:' + pct + 'px"></div></div>';
                    }}
                    return '<td' + highlight + '>' + c.val + barHtml + '</td>';
                }}).join('');

                // Delta column for exactly 2 runs
                var deltaHtml = '';
                if (isTwo && cells[0].numeric) {{
                    var v0 = parseFloat(cells[0].val), v1 = parseFloat(cells[1].val);
                    if (!isNaN(v0) && !isNaN(v1)) {{
                        var delta = (v1 - v0).toFixed(4);
                        var cls = v1 > v0 ? 'delta-positive' : (v1 < v0 ? 'delta-negative' : '');
                        deltaHtml = '<td class="' + cls + '">' + (v1 > v0 ? '+' : '') + delta + '</td>';
                    }} else {{
                        deltaHtml = '<td>—</td>';
                    }}
                }}

                return '<tr><td>' + label + '</td>' + cellsHtml + deltaHtml + '</tr>';
            }}).join('');

            document.getElementById('comparison-body').innerHTML =
                '<table><thead><tr>' + headers + '</tr></thead><tbody>' + rowsHtml + '</tbody></table>';

            panel.style.display = 'block';
            panel.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
        }}

        function closeComparison() {{
            document.getElementById('comparison-panel').style.display = 'none';
        }}

        function clearComparison() {{
            document.querySelectorAll('.row-select:checked').forEach(function(cb) {{
                cb.checked = false;
                cb.closest('tr').classList.remove('selected');
            }});
            selectedRuns = {{}};
            updateCompareBar();
            closeComparison();
        }}
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
            link_html = (
                f'<a href="{run["html_link"]}" class="report-link" target="_blank">View Report</a>'
                if run.get("html_link")
                else "—"
            )
            auc_cls = self._metric_class(run.get("auc"), "auc")
            f1_cls = self._metric_class(run.get("f1"), "f1")
            prec_cls = self._metric_class(run.get("precision"), "precision")
            rec_cls = self._metric_class(run.get("recall"), "recall")
            acc_cls = self._metric_class(run.get("accuracy"), "accuracy")

            # col 0: checkbox  col 1: run  col 2: timestamp  col 3: model
            # col 4: AUC  col 5: F1  col 6: Precision  col 7: Recall
            # col 8: Accuracy  col 9: Threshold  col 10: Report
            rows.append(f"""
            <tr>
                <td style="width:30px;text-align:center"><input type="checkbox" class="row-select"></td>
                <td class="run-name" data-val="{run['run_name']}">{run['run_name']}</td>
                <td data-val="{run['timestamp']}">{run['timestamp'][:19] if run['timestamp'] else '—'}</td>
                <td data-val="{run['model_type']}">{run['model_type']}</td>
                <td class="metric {auc_cls}" data-val="{run.get('auc', '')}">{self._fmt(run.get('auc'))}</td>
                <td class="metric {f1_cls}" data-val="{run.get('f1', '')}">{self._fmt(run.get('f1'))}</td>
                <td class="metric {prec_cls}" data-val="{run.get('precision', '')}">{self._fmt(run.get('precision'))}</td>
                <td class="metric {rec_cls}" data-val="{run.get('recall', '')}">{self._fmt(run.get('recall'))}</td>
                <td class="metric {acc_cls}" data-val="{run.get('accuracy', '')}">{self._fmt(run.get('accuracy'))}</td>
                <td class="metric" data-val="{run.get('threshold', '')}">{self._fmt(run.get('threshold'))}</td>
                <td>{link_html}</td>
            </tr>""")
        return rows

    def _build_table(self, rows: List[str], run_count: int) -> str:
        """Builds the full table HTML."""
        if run_count == 0:
            return '<div class="no-runs">No training runs found yet. Run a training to see results here.</div>'

        rows_html = "".join(rows)
        # data-col values: 0=checkbox, 1=run, 2=timestamp, 3=model, 4=AUC, 5=F1,
        # 6=Precision, 7=Recall, 8=Accuracy, 9=Threshold
        return f"""
        <table>
            <thead>
                <tr>
                    <th class="no-sort" style="width:30px"></th>
                    <th data-col="1">Run</th>
                    <th data-col="2">Timestamp</th>
                    <th data-col="3">Model</th>
                    <th data-col="4">AUC</th>
                    <th data-col="5">F1</th>
                    <th data-col="6">Precision</th>
                    <th data-col="7">Recall</th>
                    <th data-col="8">Accuracy</th>
                    <th data-col="9">Threshold</th>
                    <th class="no-sort">Report</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>"""
