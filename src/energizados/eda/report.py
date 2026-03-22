"""
EDA Report Generator - Energizados EDA Framework.

Generates a comprehensive self-contained HTML report for EDA results.
All text is in English.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from energizados.evaluation._html_templates import DARK_TOGGLE_JS, SHARED_CSS

logger = logging.getLogger(__name__)

_EDA_CSS = SHARED_CSS + """
/* ── Base ─────────────────────────────────────────────────────────────── */
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    line-height: 1.6;
    color: var(--text);
    background-color: var(--bg);
    margin: 0;
    padding: 0;
}
/* ── Layout: sidebar + main ───────────────────────────────────────────── */
.layout { display: flex; min-height: 100vh; }
.sidebar {
    width: 240px; min-width: 220px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 20px 0;
    position: sticky; top: 0; height: 100vh; overflow-y: auto;
    flex-shrink: 0;
    box-shadow: 2px 0 4px var(--shadow-sm);
}
.sidebar-title {
    font-size: 0.7em; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1px; color: var(--text-faint);
    padding: 0 16px 8px 16px;
    border-bottom: 1px solid var(--border); margin-bottom: 8px;
}
.sidebar ul { list-style: none; padding: 0; margin: 0; }
.sidebar a, .sidebar ul li a {
    display: block; padding: 8px 16px;
    color: var(--text-muted); text-decoration: none;
    font-size: 0.88em; border-left: 3px solid transparent;
    transition: all 0.15s;
}
.sidebar a:hover, .sidebar ul li a:hover {
    color: var(--primary); background: var(--surface-alt);
    border-left-color: var(--primary);
}
.main { flex: 1; padding: 24px; min-width: 0; }
@media (max-width: 900px) { .sidebar { display: none; } .main { padding: 16px; } }
/* ── Header ───────────────────────────────────────────────────────────── */
.header {
    background: var(--header-gradient); color: white;
    padding: 30px; border-radius: 10px; margin-bottom: 30px;
    box-shadow: 0 4px 6px var(--shadow); position: relative;
}
.header h1 { margin: 0; font-size: 2.2em; }
.header p { margin: 6px 0 0 0; opacity: 0.9; }
/* ── Sections ─────────────────────────────────────────────────────────── */
.section {
    background: var(--surface); padding: 25px; margin-bottom: 20px;
    border-radius: 10px; box-shadow: 0 2px 4px var(--shadow);
}
.section h2 { color: var(--primary); border-bottom: 2px solid var(--primary); padding-bottom: 10px; margin-top: 0; }
.section h3 { color: var(--primary); font-size: 1em; margin: 20px 0 10px; font-weight: 600; }
.section h4 { color: var(--text-muted); font-size: 0.9em; margin: 12px 0 8px; }
/* ── Stats grid ───────────────────────────────────────────────────────── */
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 15px; }
.stat-card {
    background: var(--surface-alt); border-radius: 8px; padding: 15px;
    text-align: center; border-left: 4px solid var(--primary);
}
.stat-card .value { font-size: 1.8em; font-weight: bold; color: var(--primary); }
.stat-card .label { font-size: 12px; color: var(--text-muted); margin-top: 5px; }
/* ── Alert table ──────────────────────────────────────────────────────── */
.alert-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
.alert-table th {
    background: var(--surface-alt); padding: 10px; text-align: left;
    font-size: 13px; color: var(--text-muted); border-bottom: 1px solid var(--border);
}
.alert-table td { padding: 10px; border-bottom: 1px solid var(--border); font-size: 13px; vertical-align: top; color: var(--text); }
.severity-ERROR { background: rgba(244,67,54,0.08); border-left: 4px solid #f44336; }
.severity-WARNING { background: rgba(255,152,0,0.08); border-left: 4px solid #ff9800; }
.severity-INFO { background: rgba(33,150,243,0.08); border-left: 4px solid #2196f3; }
/* ── Badges ───────────────────────────────────────────────────────────── */
.badge { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
.badge-ERROR { background: #f44336; color: #fff; }
.badge-WARNING { background: #ff9800; color: #fff; }
.badge-INFO { background: #2196f3; color: #fff; }
.badge-success { background: var(--positive); color: #fff; }
/* ── Quality score ────────────────────────────────────────────────────── */
.quality-score { font-size: 48px; font-weight: bold; text-align: center; padding: 20px; }
.quality-score.high { color: var(--positive); }
.quality-score.medium { color: var(--warning); }
.quality-score.low { color: var(--negative); }
/* ── Data table ───────────────────────────────────────────────────────── */
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; overflow-x: auto; display: block; }
.data-table th {
    background: var(--surface-alt); color: var(--text-muted); padding: 9px 12px;
    text-align: left; white-space: nowrap; font-weight: 600; font-size: 0.8em;
    text-transform: uppercase; border-bottom: 1px solid var(--border);
}
.data-table td { padding: 8px 12px; border-bottom: 1px solid var(--border); white-space: nowrap; color: var(--text); }
.data-table tr:hover { background: var(--surface-alt); }
/* ── Chart container ──────────────────────────────────────────────────── */
.chart-container { margin: 15px 0; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 1200px) { .two-col { grid-template-columns: 1fr; } }
/* ── Pills ────────────────────────────────────────────────────────────── */
.pill {
    display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px;
    background: var(--surface-alt); color: var(--primary); border: 1px solid var(--border);
    margin: 2px;
}
/* ── Consumption bar ──────────────────────────────────────────────────── */
.consumption-bar { height: 8px; background: var(--header-gradient); border-radius: 4px; }
/* ── Column detail (collapsible) ──────────────────────────────────────── */
details.col-detail { margin: 8px 0; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
details.col-detail summary {
    padding: 10px 15px; background: var(--surface-alt); cursor: pointer;
    font-size: 13px; font-weight: 600; color: var(--primary);
    list-style: none; display: flex; align-items: center; gap: 8px;
}
details.col-detail summary::-webkit-details-marker { display: none; }
details.col-detail summary::before { content: "\\25B6"; font-size: 10px; transition: transform 0.2s; }
details.col-detail[open] summary::before { transform: rotate(90deg); }
details.col-detail .detail-body { padding: 15px; }
/* ── Tree list ────────────────────────────────────────────────────────── */
.tree-list { list-style: none; padding-left: 0; font-size: 13px; color: var(--text); }
.tree-list ul { list-style: none; padding-left: 20px; border-left: 2px solid var(--border); margin: 4px 0; }
.tree-list li { padding: 3px 0; }
.tree-badge {
    display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 11px;
    background: var(--surface-alt); color: var(--primary); margin-left: 4px;
}
/* ── Footer ───────────────────────────────────────────────────────────── */
.footer { text-align: center; padding: 20px; color: var(--text-faint); font-size: 0.9em; }
"""


class EDAReportGenerator:
    """
    Generates a comprehensive self-contained HTML EDA report.

    The report is in English and includes:
    - Sidebar navigation
    - Executive summary with data quality score
    - Alerts table with severity coloring
    - Global dataset statistics
    - Per-column analysis
    - Target variable analysis
    - Feature importance ranking

    Args:
        output_dir: Directory where to save reports

    Example:
        >>> generator = EDAReportGenerator("output/eda/")
        >>> path = generator.generate(results, alerts)
    """

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        results: Dict,
        alerts: List[Dict],
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate full HTML EDA report and save to file.

        Args:
            results: Full analysis results dict from DatasetExplorer.run()
            alerts: Consolidated list of all alerts
            output_path: Override output file path (optional)

        Returns:
            str: Path to saved HTML report file
        """
        html = self._build_html(results, alerts)

        path = output_path or str(self.output_dir / "eda_report.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("EDA report saved to: %s", path)

        # Save outlier results as JSON artifact (if outlier data exists)
        columns = results.get("columns", {})
        outliers = results.get("outliers", {})
        if self._has_outlier_data(columns, outliers):
            self._save_outlier_results_json(results, columns, outliers)

        return path

    def _save_outlier_results_json(
        self, results: Dict, columns: Dict, outliers: Optional[Dict] = None
    ) -> str:
        """
        Save outlier analysis results as JSON artifact.

        Args:
            results: Full analysis results dict from DatasetExplorer.run()
            columns: ColumnExplorer results dict containing outlier data
            outliers: Phase 2.5 outlier results from DatasetExplorer (optional)

        Returns:
            str: Path to saved JSON file
        """
        phase25_numeric = outliers.get("numeric_outliers", {}) if outliers else {}
        phase25_consumption = outliers.get("consumption_outliers", {}) if outliers else {}

        outlier_data = {
            "timestamp": datetime.now().isoformat(),
            "dataset_info": {
                "shape": results.get("global_stats", {}).get("shape", []),
                "memory_mb": results.get("global_stats", {}).get("memory_mb", 0),
            },
            "numeric_outliers": [],
            "consumption_outliers": columns.get("consumption_outliers") or phase25_consumption,
        }

        # Phase 2.5 numeric outliers (prefer these over ColumnExplorer data)
        for col_name, method_results in phase25_numeric.items():
            for method_name, method_result in method_results.items():
                outlier_entry = {
                    "column": col_name,
                    "method": method_name,
                    "outlier_count": method_result.get("outlier_count", 0),
                    "outlier_pct": method_result.get("outlier_pct", 0.0),
                    "has_alert": method_result.get("has_alert", False),
                }
                if "fences" in method_result:
                    outlier_entry["fences"] = method_result["fences"]
                if "mean" in method_result:
                    outlier_entry["mean"] = method_result["mean"]
                    outlier_entry["std"] = method_result.get("std")
                outlier_data["numeric_outliers"].append(outlier_entry)

        # ColumnExplorer numeric data (only if Phase 2.5 didn't populate)
        if not phase25_numeric:
            numeric = columns.get("numeric", [])
            for col_data in numeric:
                col_name = col_data.get("col", "")
                outlier_methods = col_data.get("outlier_methods", {})

                if outlier_methods:
                    for method_name, method_result in outlier_methods.items():
                        outlier_data["numeric_outliers"].append(
                            {
                                "column": col_name,
                                "method": method_name,
                                "outlier_count": method_result.get("outlier_count", 0),
                                "outlier_pct": method_result.get("outlier_pct", 0.0),
                                "has_alert": method_result.get("has_alert", False),
                            }
                        )
                else:
                    outlier_pct = col_data.get("outlier_pct", 0.0)
                    if outlier_pct > 0:
                        outlier_data["numeric_outliers"].append(
                            {
                                "column": col_name,
                                "method": "IQR (legacy)",
                                "outlier_count": col_data.get("outlier_count", 0),
                                "outlier_pct": outlier_pct,
                                "has_alert": outlier_pct > 10.0,
                            }
                        )

        # Save to file
        json_path = str(self.output_dir / "outlier_analysis.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(outlier_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info("Outlier analysis saved to: %s", json_path)
        return json_path

    def _build_html(self, results: Dict, alerts: List[Dict]) -> str:
        """Build complete HTML report string."""
        global_stats = results.get("global_stats", {})
        loading = results.get("loading", {})
        columns = results.get("columns", {})
        target = results.get("target", {})
        importance = results.get("importance", {})
        geo = results.get("geo", {})
        segmentation = results.get("segmentation", {})
        related_columns = results.get("related_columns", {})
        charts = results.get("charts", {})

        # Quality score
        total_null_pct = global_stats.get("total_null_pct", 0)
        quality_score = round(100 - total_null_pct, 1)
        quality_class = (
            "high" if quality_score >= 80 else ("medium" if quality_score >= 50 else "low")
        )

        # Alert counts by severity
        error_count = sum(1 for a in alerts if a.get("severity") == "ERROR")
        warning_count = sum(1 for a in alerts if a.get("severity") == "WARNING")
        info_count = sum(1 for a in alerts if a.get("severity") == "INFO")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Check if outlier data exists
        has_outliers = self._has_outlier_data(columns, results.get("outliers", {}))

        # Build sidebar links
        sidebar_links = self._build_sidebar(geo, segmentation, related_columns, has_outliers)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EDA Report - Energizados</title>
    <style>
{_EDA_CSS}
    </style>
</head>
<body>
<div class="layout">
    <!-- Sidebar -->
    <nav class="sidebar">
        <div class="sidebar-title">Energizados EDA</div>
        {sidebar_links}
    </nav>

    <!-- Main content -->
    <main class="main">
        <!-- Header -->
        <div class="header">
            <button id="dark-toggle-btn" class="dark-toggle">&#9790; Dark</button>
            <h1>Exploratory Data Analysis Report</h1>
            <p>Generated: {now}</p>
            <p>Dataset shape: {global_stats.get("shape", (0, 0))[0]:,}
            rows &times; {global_stats.get("shape", (0, 0))[1] if len(global_stats.get("shape", (0, 0))) > 1 else 0:,}
            columns &nbsp;|&nbsp; Memory: {global_stats.get("memory_mb", 0):.2f} MB</p>
        </div>

        <!-- Executive summary -->
        {self._build_executive_summary(quality_score, quality_class, error_count, warning_count, info_count, global_stats)}

        <!-- Alerts -->
        {self._build_alerts_section(alerts)}

        <!-- Phase 0: Loading validation -->
        {self._build_loading_section(loading)}

        <!-- Phase 1: Global statistics -->
        {self._build_global_stats_section(global_stats, charts)}

        <!-- Phase 2: Column analysis -->
        {self._build_columns_section(columns, charts)}

        {self.render_outlier_section(columns, charts, results.get("outliers", {})) if has_outliers else ""}

        <!-- Phase 3: Target variable -->
        {self._build_target_section(target, charts)}

        <!-- Phase 4: Geospatial -->
        {self._build_geo_section(geo, charts)}

        <!-- Phase 5: Feature importance -->
        {self._build_importance_section(importance, charts)}

        <!-- Phase 6: Segmentation -->
        {self._build_segmentation_section(segmentation, charts)}

        <!-- Phase 7: Related columns -->
        {self._build_related_columns_section(related_columns, charts)}

        <div class="footer">
            <p>Generated by Energizados Framework &nbsp;|&nbsp; {now}</p>
        </div>
    </main>
</div>
{DARK_TOGGLE_JS}
<script>
/* Resize Plotly charts inside <details> when they are opened.
   Plotly renders at zero size when the container is hidden (collapsed);
   dispatching a resize event after the element opens forces a re-render. */
document.querySelectorAll('details.col-detail').forEach(function(el) {{
    el.addEventListener('toggle', function() {{
        if (el.open && window.Plotly) {{
            el.querySelectorAll('.plotly-graph-div').forEach(function(div) {{
                Plotly.Plots.resize(div);
            }});
        }}
    }});
}});
</script>
</body>
</html>"""

    def _build_sidebar(
        self,
        geo: Dict,
        segmentation: Dict,
        related_columns: Optional[Dict] = None,
        has_outliers: bool = False,
    ) -> str:
        sections = [
            ("resumen", "Executive Summary"),
            ("alertas", "Alerts"),
            ("carga", "Phase 0: Loading Validation"),
            ("global", "Phase 1: Global Statistics"),
            ("columnas", "Phase 2: Column Analysis"),
            ("target", "Phase 3: Target Variable"),
        ]

        # Add outlier section if data exists — insert between Phase 2 and Phase 3
        if has_outliers:
            outlier_idx = next(i for i, (sid, _) in enumerate(sections) if sid == "target")
            sections.insert(outlier_idx, ("outliers", "Phase 2.5: Outlier Analysis"))

        # Add optional sections
        if geo:
            sections.append(("geo", "Phase 4: Geospatial"))
        sections.append(("importancia", "Phase 5: Feature Importance"))
        if segmentation:
            sections.append(("segmentacion", "Phase 6: Segmentation"))
        if related_columns:
            sections.append(("relacionadas", "Phase 7: Related Columns"))
            for h_name in related_columns:
                safe_id = h_name.replace(" ", "_").lower()
                sections.append((f"hier_{safe_id}", f"  → {h_name}"))

        return "".join(f'<a href="#{sid}">{label}</a>' for sid, label in sections)

    def _has_outlier_data(self, columns: Dict, outliers: Optional[Dict] = None) -> bool:
        """Check if outlier analysis data exists in columns or outliers results."""
        if not columns:
            return False

        # Check numeric columns for outlier data
        numeric = columns.get("numeric", [])
        for col_data in numeric:
            if col_data.get("outlier_methods"):
                return True
            if col_data.get("outlier_pct", 0) > 0:
                return True

        # Check Phase 2.5 numeric outliers
        if outliers and outliers.get("numeric_outliers"):
            return True

        # Check Phase 2.5 consumption column outliers (per-column results)
        if outliers and outliers.get("consumption_column_outliers"):
            return True

        # Check consumption outlier data
        consumption_outliers = columns.get("consumption_outliers", {})
        if consumption_outliers:
            return True
        if outliers and outliers.get("consumption_outliers"):
            return True

        return False

    def _merge_outlier_results(self, numeric: List[Dict], numeric_outliers: Dict) -> List[Dict]:
        """Merge Phase 2.5 outlier results into column data."""
        outlier_by_col = {}
        for col_name, method_results in numeric_outliers.items():
            outlier_by_col[col_name] = method_results

        merged = []
        for col_data in numeric:
            col_name = col_data.get("col", "")
            if col_name in outlier_by_col:
                merged_col = col_data.copy()
                merged_col["outlier_methods"] = outlier_by_col[col_name]
                merged.append(merged_col)
            else:
                merged.append(col_data)

        if not merged and outlier_by_col:
            for col_name, method_results in outlier_by_col.items():
                merged.append({"col": col_name, "outlier_methods": method_results})

        return merged

    def _build_executive_summary(
        self,
        quality_score: float,
        quality_class: str,
        error_count: int,
        warning_count: int,
        info_count: int,
        global_stats: Dict,
    ) -> str:
        shape = global_stats.get("shape", (0, 0))
        rows = shape[0] if shape else 0
        cols = shape[1] if len(shape) > 1 else 0
        dup_rows = global_stats.get("duplicate_rows", 0)
        dup_pct = global_stats.get("duplicate_rows_pct", 0)
        const_cols = global_stats.get("constant_cols", [])
        fully_null = global_stats.get("fully_null_cols", [])

        return f"""
<div class="section" id="resumen">
    <h2>Executive Summary</h2>
    <div class="two-col">
        <div>
            <h3>Dataset Quality</h3>
            <div class="quality-score {quality_class}">{quality_score:.1f}%</div>
            <p style="text-align:center;color:#666;font-size:13px;">Complete cells (no nulls)</p>
        </div>
        <div>
            <h3>Alerts by Severity</h3>
            <div class="stats-grid" style="grid-template-columns: 1fr 1fr 1fr; margin-top:10px;">
                <div class="stat-card" style="background:#ffebee;">
                    <div class="value" style="color:#f44336;">{error_count}</div>
                    <div class="label">Errors</div>
                </div>
                <div class="stat-card" style="background:#fff3e0;">
                    <div class="value" style="color:#ff9800;">{warning_count}</div>
                    <div class="label">Warnings</div>
                </div>
                <div class="stat-card" style="background:#e3f2fd;">
                    <div class="value" style="color:#2196f3;">{info_count}</div>
                    <div class="label">Info</div>
                </div>
            </div>
        </div>
    </div>
    <div class="stats-grid" style="margin-top:20px;">
        <div class="stat-card">
            <div class="value">{rows:,}</div>
            <div class="label">Rows</div>
        </div>
        <div class="stat-card">
            <div class="value">{cols:,}</div>
            <div class="label">Columns</div>
        </div>
        <div class="stat-card">
            <div class="value">{dup_rows:,}</div>
            <div class="label">Duplicate Rows ({dup_pct:.1f}%)</div>
        </div>
        <div class="stat-card">
            <div class="value">{len(const_cols)}</div>
            <div class="label">Constant Columns</div>
        </div>
        <div class="stat-card">
            <div class="value">{len(fully_null)}</div>
            <div class="label">All-Null Columns</div>
        </div>
    </div>
</div>
"""

    def _build_alerts_section(self, alerts: List[Dict]) -> str:
        if not alerts:
            return """
<div class="section" id="alertas">
    <h2>Alerts</h2>
    <p style="color:#4caf50;">&#10003; No alerts detected.</p>
</div>
"""
        rows_html = ""
        for alert in alerts:
            sev = alert.get("severity", "INFO")
            code = alert.get("code", "")
            message = alert.get("message", "")
            details = alert.get("details", {})
            details_str = ""
            if details:
                try:
                    details_str = f'<br><small style="color:#888;">{json.dumps(details, ensure_ascii=False, default=str)[:300]}</small>'
                except Exception:  # nosec B110
                    pass

            rows_html += f"""
<tr class="severity-{sev}">
    <td><span class="badge badge-{sev}">{sev}</span></td>
    <td><code>{code}</code></td>
    <td>{message}{details_str}</td>
</tr>"""

        return f"""
<div class="section" id="alertas">
    <h2>Alerts ({len(alerts)} total)</h2>
    <table class="alert-table">
        <thead>
            <tr>
                <th>Severity</th>
                <th>Code</th>
                <th>Message</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</div>
"""

    def _build_loading_section(self, loading: Dict) -> str:
        if not loading:
            return ""

        bom = loading.get("bom_detected", False)
        bom_badge = (
            '<span class="badge badge-WARNING">YES</span>'
            if bom
            else '<span class="badge badge-success">NO</span>'
        )
        numeric_as_str = loading.get("numeric_as_string", [])
        whitespace_cols = loading.get("whitespace_columns", [])

        num_str_table = ""
        if numeric_as_str:
            rows = "".join(
                f"<tr><td>{d['col']}</td><td>{d['parseable_count']:,}</td><td>{d['parseable_pct']:.1f}%</td></tr>"
                for d in numeric_as_str
            )
            num_str_table = f"""
<h3>Numeric Columns as Text ({len(numeric_as_str)})</h3>
<table class="data-table"><thead><tr><th>Column</th><th>Parseable Values</th><th>%</th></tr></thead>
<tbody>{rows}</tbody></table>"""

        ws_table = ""
        if whitespace_cols:
            rows = "".join(
                f"<tr><td>{d['col']}</td><td>{d['affected_count']:,}</td>"
                f"<td>{d['affected_pct']:.1f}%</td><td><code>{d.get('example', '')}</code></td></tr>"
                for d in whitespace_cols
            )
            ws_table = f"""
<h3>Columns with Whitespace ({len(whitespace_cols)})</h3>
<table class="data-table"><thead><tr><th>Column</th><th>Affected</th><th>%</th><th>Example</th></tr></thead>
<tbody>{rows}</tbody></table>"""

        return f"""
<div class="section" id="carga">
    <h2>Phase 0: Loading Validation</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{loading.get("rows_loaded", 0):,}</div>
            <div class="label">Rows Loaded</div>
        </div>
        <div class="stat-card">
            <div class="value">{loading.get("encoding_used", "N/A")}</div>
            <div class="label">Detected Encoding</div>
        </div>
        <div class="stat-card">
            <div class="value">{loading.get("decimal_separator", ".")}</div>
            <div class="label">Decimal Separator</div>
        </div>
        <div class="stat-card">
            <div class="value">{bom_badge}</div>
            <div class="label">BOM Detected</div>
        </div>
    </div>
    {num_str_table}
    {ws_table}
</div>
"""

    def _build_global_stats_section(self, global_stats: Dict, charts: Dict) -> str:
        if not global_stats:
            return ""

        # Nulls by column table (top 20)
        nulls_by_col = global_stats.get("nulls_by_col", [])
        top_nulls = sorted(nulls_by_col, key=lambda x: x.get("null_pct", 0), reverse=True)[:20]

        nulls_rows = "".join(
            f"<tr><td>{d['col']}</td><td>{d['null_count']:,}</td><td>{d['null_pct']:.2f}%</td>"
            f'<td><div class="consumption-bar" style="width:{min(d["null_pct"], 100):.0f}%;'
            f'background:linear-gradient(90deg,#f44336,#ffcdd2);"></div></td></tr>'
            for d in top_nulls
        )

        dtype_counts = global_stats.get("dtype_counts", {})
        dtype_html = " ".join(
            f'<span class="pill">{dtype}: {count}</span>' for dtype, count in dtype_counts.items()
        )

        const_cols = global_stats.get("constant_cols", [])
        const_html = (
            " ".join(f'<span class="pill">{c}</span>' for c in const_cols[:20])
            if const_cols
            else "<em>None</em>"
        )

        fully_null = global_stats.get("fully_null_cols", [])
        fully_null_html = (
            " ".join(f'<span class="pill">{c}</span>' for c in fully_null[:20])
            if fully_null
            else "<em>None</em>"
        )

        # Missing heatmap chart
        missing_heatmap_html = charts.get("missing_heatmap_interactive", "")
        null_corr_html = charts.get("null_correlation", "")

        return f"""
<div class="section" id="global">
    <h2>Phase 1: Global Dataset Statistics</h2>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{global_stats.get("total_nulls", 0):,}</div>
            <div class="label">Total Missing</div>
        </div>
        <div class="stat-card">
            <div class="value">{global_stats.get("total_null_pct", 0):.2f}%</div>
            <div class="label">% Null Cells</div>
        </div>
        <div class="stat-card">
            <div class="value">{global_stats.get("duplicate_rows", 0):,}</div>
            <div class="label">Duplicate Rows</div>
        </div>
        <div class="stat-card">
            <div class="value">{global_stats.get("memory_mb", 0):.1f} MB</div>
            <div class="label">Memory</div>
        </div>
    </div>

    <h3>Data Types</h3>
    <p>{dtype_html}</p>

    <h3>Constant Columns (variance = 0)</h3>
    <p>{const_html}</p>

    <h3>Completely Null Columns</h3>
    <p>{fully_null_html}</p>

    <h3>Top 20 Columns with Most Missing Values</h3>
    <table class="data-table">
        <thead><tr><th>Column</th><th>Missing</th><th>%</th><th>Bar</th></tr></thead>
        <tbody>{nulls_rows}</tbody>
    </table>

    {f'<div class="chart-container">{missing_heatmap_html}</div>' if missing_heatmap_html else ""}
    {f'<div class="chart-container">{null_corr_html}</div>' if null_corr_html else ""}
</div>
"""

    def _build_columns_section(self, columns: Dict, charts: Dict) -> str:
        if not columns:
            return ""

        numeric = columns.get("numeric", [])
        categorical = columns.get("categorical", [])
        temporal = columns.get("temporal", [])
        consumption = columns.get("consumption", {})

        # Numeric table
        numeric_html = self._build_numeric_table(numeric)
        # Categorical table
        categorical_html = self._build_categorical_table(categorical)
        # Temporal table
        temporal_html = self._build_temporal_table(temporal)
        # Consumption section
        consumption_html = self._build_consumption_block(consumption, charts)

        corr_chart = charts.get("correlation_heatmap", "")

        # Column detail charts (collapsible)
        column_details = charts.get("column_details", {})
        numeric_details = self._build_column_details(
            [d.get("col", "") for d in numeric], column_details, "Numeric"
        )
        categorical_details = self._build_column_details(
            [d.get("col", "") for d in categorical], column_details, "Categorical"
        )
        temporal_details = self._build_column_details(
            [d.get("col", "") for d in temporal], column_details, "Temporal"
        )

        return f"""
<div class="section" id="columnas">
    <h2>Phase 2: Column Analysis</h2>

    <h3>Numeric Variables ({len(numeric)})</h3>
    {numeric_html}
    {numeric_details}

    <h3>Categorical Variables ({len(categorical)})</h3>
    {categorical_html}
    {categorical_details}

    <h3>Temporal Variables ({len(temporal)})</h3>
    {temporal_html}
    {temporal_details}

    {consumption_html}

    {f'<h3>Correlation Matrix</h3><div class="chart-container">{corr_chart}</div>' if corr_chart else ""}
</div>
"""

    def _build_numeric_table(self, numeric: List[Dict]) -> str:
        if not numeric:
            return "<p><em>No numeric columns found.</em></p>"

        has_iv = any("iv" in d for d in numeric)
        header_extra = "<th>IV</th><th>KS</th>" if has_iv else ""

        rows = ""
        for d in numeric:
            iv_td = (
                f"<td>{d.get('iv', '—') if d.get('iv') is not None else '—'}</td>"
                f"<td>{d.get('ks_stat', '—') if d.get('ks_stat') is not None else '—'}</td>"
                if has_iv
                else ""
            )
            null_color = "color:#f44336;" if (d.get("null_pct", 0) or 0) > 30 else ""
            rows += f"""
<tr>
    <td><strong>{d.get("col", "")}</strong></td>
    <td>{d.get("count", 0):,}</td>
    <td style="{null_color}">{d.get("null_pct", 0):.1f}%</td>
    <td>{d.get("mean", "—")}</td>
    <td>{d.get("std", "—")}</td>
    <td>{d.get("min", "—")}</td>
    <td>{d.get("max", "—")}</td>
    <td>{d.get("p50", "—")}</td>
    <td>{d.get("outlier_pct", 0):.1f}%</td>
    <td>{d.get("skewness", "—")}</td>
    {iv_td}
</tr>"""

        return f"""
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr>
    <th>Column</th><th>Count</th><th>% Missing</th>
    <th>Mean</th><th>Std</th><th>Min</th><th>Max</th><th>Median</th>
    <th>% Outliers</th><th>Skewness</th>{header_extra}
</tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""

    def _build_categorical_table(self, categorical: List[Dict]) -> str:
        if not categorical:
            return "<p><em>No categorical columns found.</em></p>"

        has_iv = any("iv" in d for d in categorical)
        header_extra = "<th>IV</th><th>Cramér's V</th>" if has_iv else ""

        rows = ""
        for d in categorical:
            top = d.get("top_categories", [])
            top_str = ", ".join(f"{c['value']} ({c['pct']:.1f}%)" for c in top[:3])
            iv_td = (
                f"<td>{d.get('iv', '—') if d.get('iv') is not None else '—'}</td>"
                f"<td>{d.get('cramers_v', '—') if d.get('cramers_v') is not None else '—'}</td>"
                if has_iv
                else ""
            )
            null_color = "color:#f44336;" if (d.get("null_pct", 0) or 0) > 30 else ""
            rows += f"""
<tr>
    <td><strong>{d.get("col", "")}</strong></td>
    <td>{d.get("count", 0):,}</td>
    <td style="{null_color}">{d.get("null_pct", 0):.1f}%</td>
    <td>{d.get("unique_count", 0)}</td>
    <td style="max-width:300px;white-space:normal;">{top_str}</td>
    <td>{d.get("rare_pct", 0):.1f}%</td>
    <td>{d.get("entropy", 0):.2f}</td>
    {iv_td}
</tr>"""

        return f"""
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr>
    <th>Column</th><th>Count</th><th>% Missing</th>
    <th>Unique</th><th>Top Categories</th><th>% Rare</th><th>Entropy</th>{header_extra}
</tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""

    def _build_temporal_table(self, temporal: List[Dict]) -> str:
        if not temporal:
            return "<p><em>No temporal columns found.</em></p>"

        rows = ""
        for d in temporal:
            rows += f"""
<tr>
    <td><strong>{d.get("col", "")}</strong></td>
    <td>{d.get("count", 0):,}</td>
    <td>{d.get("null_pct", 0):.1f}%</td>
    <td>{d.get("min_date", "—")}</td>
    <td>{d.get("max_date", "—")}</td>
    <td>{d.get("span_days", "—")}</td>
    <td>{d.get("granularity", "—")}</td>
</tr>"""

        return f"""
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr>
    <th>Column</th><th>Count</th><th>% Missing</th>
    <th>Min Date</th><th>Max Date</th><th>Days Span</th><th>Granularity</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""

    def _build_consumption_block(self, consumption: Dict, charts: Dict) -> str:
        if not consumption or not consumption.get("periods"):
            return ""

        periods = consumption.get("periods", [])
        stats = consumption.get("stats_by_period", [])

        stats_rows = ""
        for s in stats:
            stats_rows += f"""
<tr>
    <td>{s.get("period", "")}</td>
    <td>{s.get("mean", "—")}</td>
    <td>{s.get("std", "—")}</td>
    <td>{s.get("min", "—")}</td>
    <td>{s.get("max", "—")}</td>
    <td>{s.get("zeros_pct", 0):.1f}%</td>
    <td>{s.get("nulls_pct", 0):.1f}%</td>
</tr>"""

        consumption_chart = charts.get("consumption_trend", "")
        consumption_heatmap = charts.get("consumption_heatmap", "")

        return f"""
<h3>Consumption Columns ({len(periods)} periods)</h3>
<div class="stats-grid">
    <div class="stat-card">
        <div class="value">{consumption.get("pct_rows_with_any_zero", 0):.1f}%</div>
        <div class="label">Rows with Any Zero</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get("pct_rows_all_zero", 0):.1f}%</div>
        <div class="label">Rows All Zero</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get("pct_negative", 0):.1f}%</div>
        <div class="label">% Negative Consumption</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get("pct_constant", 0):.1f}%</div>
        <div class="label">Constant Rows</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get("pct_abrupt_drop", 0):.1f}%</div>
        <div class="label">Abrupt Drops (&gt;50%)</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get("trend_slope", 0):.4f}</div>
        <div class="label">Trend Slope</div>
    </div>
</div>
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr><th>Period</th><th>Mean</th><th>Std</th><th>Min</th><th>Max</th><th>% Zeros</th><th>% Missing</th></tr></thead>
<tbody>{stats_rows}</tbody>
</table>
</div>
{f'<div class="chart-container">{consumption_chart}</div>' if consumption_chart else ""}
{f'<div class="chart-container">{consumption_heatmap}</div>' if consumption_heatmap else ""}
"""

    def _build_target_section(self, target: Dict, charts: Dict) -> str:
        if not target:
            return """
<div class="section" id="target">
    <h2>Phase 3: Target Variable</h2>
    <p><em>No target variable specified.</em></p>
</div>
"""
        class_counts = target.get("class_counts", {})
        class_pcts = target.get("class_pcts", {})
        imbalance = target.get("imbalance_ratio", 1)
        recommendation = target.get("recommendation", "none")
        temporal_rate = target.get("temporal_rate", [])

        class_rows = "".join(
            f"<tr><td>{label}</td><td>{class_counts.get(label, 0):,}</td><td>{class_pcts.get(label, 0):.2f}%</td></tr>"
            for label in class_counts
        )

        temporal_rows = ""
        if temporal_rate:
            temporal_rows = "".join(
                f"<tr><td>{d['period']}</td><td>{d['total']:,}</td><td>{d['positive']:,}</td><td>{d['rate']:.2f}%</td></tr>"
                for d in temporal_rate[:24]
            )
            temporal_table = f"""
<h3>Temporal Evolution of Fraud Rate</h3>
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr><th>Period</th><th>Total</th><th>Positives</th><th>Rate</th></tr></thead>
<tbody>{temporal_rows}</tbody>
</table>
</div>"""
        else:
            temporal_table = ""

        class_balance_chart = charts.get("class_balance", "")
        temporal_chart = charts.get("temporal_rate", "")

        rec_labels = {
            "oversample": "Oversampling (over-sampling)",
            "undersample": "Undersampling (under-sampling)",
            "none": "No resampling needed",
        }
        rec_html = rec_labels.get(recommendation, recommendation)

        return f"""
<div class="section" id="target">
    <h2>Phase 3: Target Variable</h2>
    <div class="two-col">
        <div>
            <table class="data-table">
            <thead><tr><th>Class</th><th>Count</th><th>%</th></tr></thead>
            <tbody>{class_rows}</tbody>
            </table>
            <p style="margin-top:15px;"><strong>Imbalance Ratio:</strong> {imbalance:.1f}:1</p>
            <p><strong>Recommendation:</strong> {rec_html}</p>
        </div>
        <div>
            {f'<div class="chart-container">{class_balance_chart}</div>' if class_balance_chart else ""}
        </div>
    </div>
    {temporal_table}
    {f'<div class="chart-container">{temporal_chart}</div>' if temporal_chart else ""}
</div>
"""

    def _build_importance_section(self, importance: Dict, charts: Dict) -> str:
        if not importance:
            return """
<div class="section" id="importancia">
    <h2>Phase 5: Feature Importance</h2>
    <p><em>No target variable specified. Feature importance analysis skipped.</em></p>
</div>
"""
        ranking_df = importance.get("ranking")
        top_features = importance.get("top_features", [])
        weak_features = importance.get("weak_features", [])
        leakage_candidates = importance.get("leakage_candidates", [])

        iv_chart = charts.get("iv_ranking", "")

        # Ranking table
        table_html = ""
        if isinstance(ranking_df, pd.DataFrame) and len(ranking_df) > 0:
            display_cols = [
                "feature",
                "type",
                "iv",
                "ks_stat",
                "cramers_v",
                "correlation",
                "combined_score",
            ]
            available_cols = [c for c in display_cols if c in ranking_df.columns]
            top_df = ranking_df[available_cols].head(30)

            header_cells = "".join(
                f"<th>{c.replace('_', ' ').title()}</th>" for c in available_cols
            )

            rows_html = ""
            for _, row in top_df.iterrows():
                cells = ""
                for c in available_cols:
                    val = row.get(c)
                    if isinstance(val, float):
                        cells += f"<td>{val:.4f}</td>"
                    elif val is None or (isinstance(val, float) and pd.isna(val)):
                        cells += "<td>—</td>"
                    else:
                        cells += f"<td>{val}</td>"
                rows_html += f"<tr>{cells}</tr>"

            table_html = f"""
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr>{header_cells}</tr></thead>
<tbody>{rows_html}</tbody>
</table>
</div>"""

        weak_html = (
            " ".join(f'<span class="pill">{c}</span>' for c in weak_features[:20])
            if weak_features
            else "<em>None</em>"
        )
        leakage_html = (
            " ".join(
                f'<span class="pill" style="background:#ffcdd2;color:#c62828;">{c}</span>'
                for c in leakage_candidates
            )
            if leakage_candidates
            else "<em>None</em>"
        )

        return f"""
<div class="section" id="importancia">
    <h2>Phase 5: Feature Importance</h2>

    {f'<div class="chart-container">{iv_chart}</div>' if iv_chart else ""}

    <h3>Top 20 Features (by combined score)</h3>
    <p>{" ".join(f'<span class="pill"><strong>{i + 1}.</strong> {c}</span>' for i, c in enumerate(top_features))}</p>

    <h3>Low Predictive Power Features (IV &lt; threshold)</h3>
    <p>{weak_html}</p>

    <h3>Data Leakage Candidates (very high IV)</h3>
    <p>{leakage_html}</p>

    <h3>Full Ranking (Top 30)</h3>
    {table_html}
</div>
"""

    def _build_geo_section(self, geo: Dict, charts: Dict) -> str:
        """Build Phase 4: Geospatial section."""
        if not geo:
            return ""

        coord_quality = geo.get("coord_quality", {})
        target_by_zone = geo.get("target_by_zone", {})
        clustering = geo.get("clustering", {})

        mapbox_chart = charts.get("scatter_mapbox", "")

        quality_rows = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in {
                "Valid Records": f"{coord_quality.get('valid_coords_count', 0):,}",
                "% Missing": f"{coord_quality.get('null_pct', 0):.1f}%",
                "% Coordinates (0,0)": f"{coord_quality.get('zero_coord_pct', 0):.1f}%",
                "Exact Duplicates": f"{coord_quality.get('duplicate_coords_pct', 0):.1f}%",
            }.items()
        )

        zone_rows = ""
        if target_by_zone:
            zone_rows = "".join(
                f"<tr><td>{zone}</td><td>{rate:.1%}</td></tr>"
                for zone, rate in sorted(target_by_zone.items(), key=lambda x: x[1], reverse=True)[
                    :15
                ]
            )

        clustering_info = ""
        if clustering.get("cluster_stats"):
            clustering_info = f"""
    <h3>Geographic Clustering</h3>
    <p>Method: {clustering.get("method", "N/A")}, Clusters: {clustering.get("n_clusters", 0)}</p>
    """

        return f"""
<div class="section" id="geo">
    <h2>Phase 4: Geospatial Analysis</h2>

    {f'<div class="chart-container">{mapbox_chart}</div>' if mapbox_chart else ""}

    <h3>Coordinate Quality</h3>
    <table class="data-table">
        <thead><tr><th>Metric</th><th>Value</th></tr></thead>
        <tbody>{quality_rows}</tbody>
    </table>

    {clustering_info}

    {
            f'''
    <h3>Fraud Rate by Zone</h3>
    <table class="data-table">
        <thead><tr><th>Zone</th><th>Rate</th></tr></thead>
        <tbody>{zone_rows}</tbody>
    </table>
    '''
            if zone_rows
            else ""
        }
</div>
"""

    def _build_segmentation_section(self, segmentation: Dict, charts: Dict) -> str:
        """Build Phase 6: Segmentation section."""
        if not segmentation:
            return ""

        segment_stats = segmentation.get("segment_stats", [])

        # Show top segments by z-score
        top_segments = sorted(segment_stats, key=lambda x: abs(x.get("z_score", 0)), reverse=True)[
            :15
        ]

        segment_rows = "".join(
            f"<tr><td>{s['column']}={s['segment']}</td><td>{s['size']:,}</td><td>{s['size_pct']:.1f}%</td>"
            f"<td>{s['target_rate']:.1%}</td><td>{s['z_score']:.2f}</td></tr>"
            for s in top_segments
        )

        segment_chart = charts.get("segment_barplot", "")

        return f"""
<div class="section" id="segmentacion">
    <h2>Phase 6: Segmentation Analysis</h2>

    {f'<div class="chart-container">{segment_chart}</div>' if segment_chart else ""}

    <h3>Segments with Greatest Fraud Rate Difference</h3>
    <table class="data-table">
        <thead><tr><th>Segment</th><th>Size</th><th>%</th><th>Rate</th><th>Z-Score</th></tr></thead>
        <tbody>{segment_rows}</tbody>
    </table>
</div>
"""

    # ------------------------------------------------------------------
    # Column detail collapsible blocks
    # ------------------------------------------------------------------

    def _build_column_details(
        self, col_names: List[str], column_details: Dict, type_label: str
    ) -> str:
        """Build collapsible <details> blocks for per-column charts."""
        blocks = []
        for col in col_names:
            col_charts = column_details.get(col, {})
            if not col_charts:
                continue
            charts_html = "".join(
                f'<div class="chart-container">{html}</div>' for html in col_charts.values() if html
            )
            if not charts_html:
                continue
            blocks.append(
                f'<details class="col-detail">'
                f"<summary>{col}</summary>"
                f'<div class="detail-body">{charts_html}</div>'
                f"</details>"
            )

        if not blocks:
            return ""
        return f"<h3>Column Detail ({type_label})</h3>{''.join(blocks)}"

    # ------------------------------------------------------------------
    # Related columns section
    # ------------------------------------------------------------------

    def _build_related_columns_section(self, related_columns: Dict, charts: Dict) -> str:
        """Build Phase 7: Related Columns section."""
        if not related_columns:
            return ""

        hierarchy_charts = charts.get("hierarchies", {})
        sections_html = ""

        for h_name, h_data in related_columns.items():
            safe_id = h_name.replace(" ", "_").lower()
            columns = h_data.get("columns", [])
            h_charts = hierarchy_charts.get(h_name, {})

            # Tree breakdown HTML
            tree = h_data.get("tree_breakdown", [])
            tree_html = self._build_tree_html(tree) if tree else "<em>No data</em>"

            # Cross tabulation table
            cross = h_data.get("cross_tabulation", [])
            cross_html = self._build_cross_table(cross, columns)

            # Charts
            sunburst_html = h_charts.get("sunburst", "")
            sankey_html = h_charts.get("sankey", "")
            heatmap_html = h_charts.get("target_heatmap", "")

            sections_html += f"""
<div id="hier_{safe_id}" style="margin-top:20px;">
    <h3>{h_name}</h3>
    <p><strong>Columns:</strong> {" → ".join(columns)}</p>

    <h4>Hierarchical Breakdown</h4>
    <ul class="tree-list">{tree_html}</ul>

    {f'<div class="chart-container">{sunburst_html}</div>' if sunburst_html else ""}
    {f'<div class="chart-container">{sankey_html}</div>' if sankey_html else ""}
    {f'<div class="chart-container">{heatmap_html}</div>' if heatmap_html else ""}

    {cross_html}
</div>"""

        return f"""
<div class="section" id="relacionadas">
    <h2>Phase 7: Related Columns</h2>
    {sections_html}
</div>
"""

    def _build_tree_html(self, tree: List[Dict], max_depth: int = 4) -> str:
        """Recursively render tree breakdown as nested <ul>/<li> HTML."""
        if not tree or max_depth <= 0:
            return ""

        items = ""
        for node in tree[:30]:  # limit nodes per level
            value = node.get("value", "")
            count = node.get("count", 0)
            pct_parent = node.get("pct_of_parent", 0)
            pct_total = node.get("pct_of_total", 0)

            items += (
                f"<li><strong>{value}</strong>"
                f' <span class="tree-badge">{count:,} — {pct_parent:.1f}% of parent</span>'
                f' <span class="tree-badge" style="background:#fff3e0;color:#e65100;">{pct_total:.1f}% of total</span>'
            )

            children = node.get("children", [])
            if children:
                items += f"<ul>{self._build_tree_html(children, max_depth - 1)}</ul>"

            items += "</li>"

        return items

    def _build_cross_table(self, cross: List[Dict], columns: List[str]) -> str:
        """Build HTML table from cross tabulation records."""
        if not cross:
            return ""

        header = "".join(f"<th>{c}</th>" for c in columns)
        rows = ""
        for record in cross[:50]:
            cells = "".join(f"<td>{record.get(c, '')}</td>" for c in columns)
            cells += f"<td>{record.get('count', 0):,}</td>"
            rows += f"<tr>{cells}</tr>"

        return f"""
<h4>Cross Tabulation (top 50)</h4>
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr>{header}<th>Count</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""

    # ------------------------------------------------------------------
    # Outlier analysis section (Phase 2.5)
    # ------------------------------------------------------------------

    def render_outlier_section(
        self, columns: Dict, charts: Optional[Dict] = None, outliers: Optional[Dict] = None
    ) -> str:
        """
        Render outlier analysis section in HTML.

        This method generates HTML for:
        1. Summary table of outliers by column and method
        2. Per-method breakdown for numeric columns
        3. Consumption outlier summary
        4. Alert list for high outlier percentages

        Args:
            columns: ColumnExplorer results dict containing:
                - numeric: List of numeric column analyses
                - consumption_outliers: Consumption outlier analysis results
            charts: Optional dict with outlier visualization charts:
                - outlier_boxplots: SVG boxplots by column and method
                - outlier_heatmap: Outlier detection matrix heatmap
            outliers: Phase 2.5 outlier results from DatasetExplorer (optional).
                If provided, supersedes columns' numeric outlier data.

        Returns:
            str: HTML string for outlier analysis section
        """
        if not columns:
            return ""

        numeric = columns.get("numeric", [])
        consumption_outliers = columns.get("consumption_outliers", {})
        phase25_consumption = outliers.get("consumption_outliers", {}) if outliers else {}

        if outliers and outliers.get("numeric_outliers"):
            numeric = self._merge_outlier_results(numeric, outliers["numeric_outliers"])

        # Merge consumption column outliers into numeric list for display
        if outliers and outliers.get("consumption_column_outliers"):
            consumption_col_outliers = outliers["consumption_column_outliers"]
            for col_name, method_results in consumption_col_outliers.items():
                numeric.append(
                    {"col": col_name, "outlier_methods": method_results, "_is_consumption": True}
                )

        # Use Phase 2.5 consumption outliers if available
        if phase25_consumption:
            consumption_outliers = phase25_consumption

        # Build summary table
        summary_table = self._build_outlier_summary_table(numeric)

        # Build per-method breakdown
        method_breakdown = self._build_outlier_method_breakdown(numeric)

        # Build consumption outlier summary
        consumption_summary = self._build_consumption_outlier_summary(consumption_outliers)

        # Get charts
        outlier_boxplots_html = charts.get("outlier_boxplots", "") if charts else ""
        outlier_summary_bar_html = charts.get("outlier_summary_bar", "") if charts else ""

        parts = [
            f"""<h3>Outlier Summary by Column</h3>
{summary_table}""",
        ]
        if method_breakdown:
            parts.append(method_breakdown)
        if consumption_summary:
            parts.append(consumption_summary)
        if outlier_summary_bar_html:
            parts.append(f'<div class="chart-container">{outlier_summary_bar_html}</div>')
        if outlier_boxplots_html:
            parts.append(f'<div class="chart-container">{outlier_boxplots_html}</div>')

        return f"""
<div class="section" id="outliers">
    <h2>Outlier Analysis (Phase 2.5)</h2>

    {"".join(parts)}

</div>"""

    def _build_outlier_summary_table(self, numeric: List[Dict]) -> str:
        """Build summary table of outliers by column and method."""
        if not numeric:
            return "<p><em>No numeric columns with outlier data.</em></p>"

        rows = ""
        for col_data in numeric:
            col_name = col_data.get("col", "")
            is_consumption = col_data.get("_is_consumption", False)
            col_type = (
                '<span class="badge" style="background:#e8f5e9;color:#2e7d32;">consumption</span>'
                if is_consumption
                else ""
            )
            outlier_methods = col_data.get("outlier_methods", {})

            if not outlier_methods:
                outlier_pct = col_data.get("outlier_pct", 0.0)
                outlier_count = col_data.get("outlier_count", 0)
                has_alert = outlier_pct > 10.0
                alert_badge = '<span class="badge badge-WARNING">High</span>' if has_alert else ""
                rows += f"""
<tr>
    <td><strong>{col_name}</strong>{f" {col_type}" if col_type else ""}</td>
    <td>IQR (legacy)</td>
    <td>{outlier_count:,}</td>
    <td>{outlier_pct:.2f}%</td>
    <td>{alert_badge}</td>
</tr>"""
            else:
                for method_name, method_result in outlier_methods.items():
                    outlier_pct = method_result.get("outlier_pct", 0.0)
                    outlier_count = method_result.get("outlier_count", 0)
                    has_alert = method_result.get("has_alert", outlier_pct > 10.0)
                    alert_badge = (
                        '<span class="badge badge-WARNING">High</span>' if has_alert else ""
                    )
                    rows += f"""
<tr>
    <td><strong>{col_name}</strong>{f" {col_type}" if col_type else ""}</td>
    <td>{method_name.capitalize()}</td>
    <td>{outlier_count:,}</td>
    <td>{outlier_pct:.2f}%</td>
    <td>{alert_badge}</td>
</tr>"""

        return f"""
<div style="overflow-x:auto;">
<table class="data-table">
<thead>
<tr>
    <th>Column</th>
    <th>Method</th>
    <th>Outlier Count</th>
    <th>% Outliers</th>
    <th>Alert</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>"""

    def _build_outlier_method_breakdown(self, numeric: List[Dict]) -> str:
        """Build per-method breakdown for numeric columns."""
        # Collect statistics by method
        method_stats: Dict[str, Dict] = {}

        for col_data in numeric:
            outlier_methods = col_data.get("outlier_methods", {})
            if not outlier_methods:
                # Legacy IQR method
                outlier_pct = col_data.get("outlier_pct", 0.0)
                if outlier_pct > 0:
                    if "IQR" not in method_stats:
                        method_stats["IQR"] = {"total_cols": 0, "total_outliers": 0, "avg_pct": 0.0}
                    method_stats["IQR"]["total_cols"] += 1
                    method_stats["IQR"]["total_outliers"] += col_data.get("outlier_count", 0)
                    method_stats["IQR"]["avg_pct"] += outlier_pct
            else:
                for method_name, method_result in outlier_methods.items():
                    outlier_pct = method_result.get("outlier_pct", 0.0)
                    if outlier_pct > 0:
                        if method_name not in method_stats:
                            method_stats[method_name] = {
                                "total_cols": 0,
                                "total_outliers": 0,
                                "avg_pct": 0.0,
                            }
                        method_stats[method_name]["total_cols"] += 1
                        method_stats[method_name]["total_outliers"] += method_result.get(
                            "outlier_count", 0
                        )
                        method_stats[method_name]["avg_pct"] += outlier_pct

        # Calculate averages
        for method in method_stats:
            if method_stats[method]["total_cols"] > 0:
                method_stats[method]["avg_pct"] /= method_stats[method]["total_cols"]

        if not method_stats:
            return ""

        rows = ""
        for method, stats in method_stats.items():
            rows += f"""
<tr>
    <td><strong>{method.upper()}</strong></td>
    <td>{stats["total_cols"]}</td>
    <td>{stats["total_outliers"]:,}</td>
    <td>{stats["avg_pct"]:.2f}%</td>
</tr>"""

        return f"""
<h3>Outlier Detection Method Summary</h3>
<div style="overflow-x:auto;">
<table class="data-table">
<thead>
<tr>
    <th>Method</th>
    <th>Columns with Outliers</th>
    <th>Total Outliers</th>
    <th>Avg % per Column</th>
</tr>
</thead>
<tbody>{rows}</tbody>
</table>
</div>"""

    def _build_consumption_outlier_summary(self, consumption_outliers: Dict) -> str:
        """Build consumption outlier summary section."""
        if not consumption_outliers:
            return ""

        pct_zero_variance = consumption_outliers.get("pct_zero_variance", 0.0)
        pct_range_outliers = consumption_outliers.get("pct_range_outliers", 0.0)
        mean_zscore_outlier_pct = consumption_outliers.get("mean_zscore_outlier_pct", 0.0)

        return f"""
<h3>Consumption Outlier Patterns</h3>
<div class="stats-grid">
    <div class="stat-card">
        <div class="value">{pct_zero_variance:.2f}%</div>
        <div class="label">Zero Variance Rows</div>
    </div>
    <div class="stat-card">
        <div class="value">{pct_range_outliers:.2f}%</div>
        <div class="label">Extreme Range Outliers</div>
    </div>
    <div class="stat-card">
        <div class="value">{mean_zscore_outlier_pct:.2f}%</div>
        <div class="label">Global Mean Outliers</div>
    </div>
</div>
<p style="font-size:13px;color:#666;margin-top:10px;">
    <strong>Zero Variance:</strong> Rows with suspiciously constant consumption across all periods.<br>
    <strong>Extreme Range:</strong> Rows with consumption range-to-mean ratio > 5.0.<br>
    <strong>Global Mean:</strong> Rows with mean consumption z-score > 3.0.
</p>"""

    def _build_outlier_alerts(self, numeric: List[Dict], consumption_outliers: Dict) -> str:
        """Build alert list for high outlier percentages."""
        alerts = []

        # Check numeric columns for high outlier percentages
        for col_data in numeric:
            outlier_methods = col_data.get("outlier_methods", {})
            if not outlier_methods:
                # Legacy IQR method
                outlier_pct = col_data.get("outlier_pct", 0.0)
                if outlier_pct > 10.0:
                    alerts.append(
                        f"Column <strong>{col_data.get('col', '')}</strong> has "
                        f"{outlier_pct:.2f}% outliers (IQR method)."
                    )
            else:
                for method_name, method_result in outlier_methods.items():
                    if method_result.get("has_alert", False):
                        alerts.append(
                            f"Column <strong>{col_data.get('col', '')}</strong> has "
                            f"{method_result.get('outlier_pct', 0.0):.2f}% outliers "
                            f"({method_name} method)."
                        )

        # Check consumption outliers
        if consumption_outliers:
            pct_zero_variance = consumption_outliers.get("pct_zero_variance", 0.0)
            pct_range_outliers = consumption_outliers.get("pct_range_outliers", 0.0)
            mean_zscore_outlier_pct = consumption_outliers.get("mean_zscore_outlier_pct", 0.0)

            if pct_zero_variance > 10.0:
                alerts.append(
                    f"High percentage ({pct_zero_variance:.2f}%) of rows with zero "
                    f"variance consumption (potential meter tampering)."
                )
            if pct_range_outliers > 10.0:
                alerts.append(
                    f"High percentage ({pct_range_outliers:.2f}%) of rows with extreme "
                    f"consumption range outliers (potential data quality issues)."
                )
            if mean_zscore_outlier_pct > 10.0:
                alerts.append(
                    f"High percentage ({mean_zscore_outlier_pct:.2f}%) of global consumption "
                    f"outliers (potential fraud)."
                )

        if not alerts:
            return ""

        alert_rows = "\n".join(f"<li>{alert}</li>" for alert in alerts)
        return f"""
<div style="background:#fff3e0;border-left:4px solid #ff9800;padding:15px;margin:15px 0;border-radius:4px;">
    <h4 style="margin:0 0 10px 0;color:#e65100;">Outlier Alerts</h4>
    <ul style="margin:0;padding-left:20px;color:#666;font-size:13px;">
        {alert_rows}
    </ul>
</div>"""
