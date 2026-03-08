"""
EDA Report Generator - Energizados EDA Framework.

Generates a comprehensive self-contained HTML report for EDA results.
All text is in Spanish (latinoamericano).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_EDA_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; color: #333; }
.layout { display: flex; min-height: 100vh; }
.sidebar {
    width: 260px; min-width: 260px; background: #1a237e; color: #fff;
    padding: 20px 0; position: sticky; top: 0; height: 100vh; overflow-y: auto;
}
.sidebar h2 { padding: 0 20px 15px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #90caf9; border-bottom: 1px solid #283593; }
.sidebar ul { list-style: none; padding: 10px 0; }
.sidebar ul li a {
    display: block; padding: 10px 20px; color: #e3f2fd; text-decoration: none;
    font-size: 13px; transition: background 0.2s;
}
.sidebar ul li a:hover { background: #283593; }  # noqa: E501
.sidebar ul li a.active { background: #1565c0; border-left: 3px solid #90caf9; }
.sidebar .section-group { margin-bottom: 5px; }
.sidebar .section-group .group-title { padding: 8px 20px 4px; font-size: 11px; text-transform: uppercase; color: #7986cb; letter-spacing: 0.5px; }  # noqa: E501
.main { flex: 1; padding: 30px; max-width: calc(100vw - 260px); }
.page-header { background: linear-gradient(135deg, #1a237e, #283593); color: #fff; padding: 30px; border-radius: 12px; margin-bottom: 30px; }  # noqa: E501
.page-header h1 { font-size: 26px; margin-bottom: 8px; }
.page-header p { color: #90caf9; font-size: 14px; }
.section { background: #fff; border-radius: 10px; padding: 25px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.section h2 { font-size: 18px; color: #1a237e; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #e8eaf6; }
.section h3 { font-size: 15px; color: #283593; margin: 15px 0 10px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 15px; }
.stat-card { background: #e8eaf6; border-radius: 8px; padding: 15px; text-align: center; }
.stat-card .value { font-size: 24px; font-weight: bold; color: #1a237e; }
.stat-card .label { font-size: 12px; color: #666; margin-top: 5px; }
.alert-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
.alert-table th { background: #e8eaf6; padding: 10px; text-align: left; font-size: 13px; }
.alert-table td { padding: 10px; border-bottom: 1px solid #f0f2f5; font-size: 13px; vertical-align: top; }
.severity-ERROR { background: #ffebee; border-left: 4px solid #f44336; }
.severity-WARNING { background: #fff3e0; border-left: 4px solid #ff9800; }
.severity-INFO { background: #e3f2fd; border-left: 4px solid #2196f3; }
.badge { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
.badge-ERROR { background: #f44336; color: #fff; }
.badge-WARNING { background: #ff9800; color: #fff; }
.badge-INFO { background: #2196f3; color: #fff; }
.badge-success { background: #4caf50; color: #fff; }
.quality-score { font-size: 48px; font-weight: bold; text-align: center; padding: 20px; }
.quality-score.high { color: #4caf50; }
.quality-score.medium { color: #ff9800; }
.quality-score.low { color: #f44336; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; overflow-x: auto; display: block; }
.data-table th { background: #1a237e; color: #fff; padding: 8px 12px; text-align: left; white-space: nowrap; }
.data-table td { padding: 8px 12px; border-bottom: 1px solid #e8eaf6; white-space: nowrap; }
.data-table tr:hover { background: #f5f5f5; }
.chart-container { margin: 15px 0; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 1200px) { .two-col { grid-template-columns: 1fr; } }
.pill { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; background: #e8eaf6; color: #1a237e; margin: 2px; }
.consumption-bar { height: 8px; background: linear-gradient(90deg, #1a237e, #90caf9); border-radius: 4px; }
.footer { text-align: center; padding: 20px; color: #999; font-size: 12px; margin-top: 20px; }
"""


class EDAReportGenerator:
    """
    Generates a comprehensive self-contained HTML EDA report.

    The report is in Spanish (latinoamericano) and includes:
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

        logger.info("Reporte EDA guardado en: %s", path)
        return path

    def _build_html(self, results: Dict, alerts: List[Dict]) -> str:
        """Build complete HTML report string."""
        global_stats = results.get("global_stats", {})
        loading = results.get("loading", {})
        columns = results.get("columns", {})
        target = results.get("target", {})
        importance = results.get("importance", {})
        inspections = results.get("inspections", {})
        geo = results.get("geo", {})
        joins = results.get("joins", {})
        segmentation = results.get("segmentation", {})
        charts = results.get("charts", {})

        # Quality score
        total_null_pct = global_stats.get("total_null_pct", 0)
        quality_score = round(100 - total_null_pct, 1)
        quality_class = "high" if quality_score >= 80 else ("medium" if quality_score >= 50 else "low")

        # Alert counts by severity
        error_count = sum(1 for a in alerts if a.get("severity") == "ERROR")
        warning_count = sum(1 for a in alerts if a.get("severity") == "WARNING")
        info_count = sum(1 for a in alerts if a.get("severity") == "INFO")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build sidebar links
        sidebar_links = self._build_sidebar(inspections, geo, joins, segmentation)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte EDA - Energizados</title>
    <style>
{_EDA_CSS}
    </style>
</head>
<body>
<div class="layout">
    <!-- Sidebar -->
    <nav class="sidebar">
        <h2>Energizados EDA</h2>
        {sidebar_links}
    </nav>

    <!-- Main content -->
    <main class="main">
        <!-- Header -->
        <div class="page-header">
            <h1>Reporte de Análisis Exploratorio de Datos</h1>
            <p>Generado: {now}</p>
            <p>Forma del dataset: {global_stats.get('shape', (0,0))[0]:,} filas × {global_stats.get('shape', (0,0))[1] if len(global_stats.get('shape', (0,0))) > 1 else 0:,} columnas &nbsp;|&nbsp; Memoria: {global_stats.get('memory_mb', 0):.2f} MB</p>  # noqa: E501
        </div>

        <!-- Resumen ejecutivo -->
        {self._build_executive_summary(quality_score, quality_class, error_count, warning_count, info_count, global_stats)}

        <!-- Alertas -->
        {self._build_alerts_section(alerts)}

        <!-- Fase 0: Validación de carga -->
        {self._build_loading_section(loading)}

        <!-- Fase 1: Estadísticas globales -->
        {self._build_global_stats_section(global_stats, charts)}

        <!-- Fase 2: Análisis de columnas -->
        {self._build_columns_section(columns, charts)}

        <!-- Fase 3: Variable objetivo -->
        {self._build_target_section(target, charts)}

        <!-- Fase 4: Inspecciones -->
        {self._build_inspections_section(inspections, charts)}

        <!-- Fase 5: Geoespacial -->
        {self._build_geo_section(geo, charts)}

        <!-- Fase 6: Joins multi-fuente -->
        {self._build_joins_section(joins)}

        <!-- Fase 7: Importancia de variables -->
        {self._build_importance_section(importance, charts)}

        <!-- Fase 8: Segmentación -->
        {self._build_segmentation_section(segmentation, charts)}

        <div class="footer">
            <p>Generado por Energizados Framework &nbsp;|&nbsp; {now}</p>
        </div>
    </main>
</div>
</body>
</html>"""

    def _build_sidebar(self, inspections: Dict, geo: Dict, joins: Dict, segmentation: Dict) -> str:
        sections = [
            ("resumen", "Resumen Ejecutivo"),
            ("alertas", "Alertas"),
            ("carga", "Fase 0: Validación de Carga"),
            ("global", "Fase 1: Estadísticas Globales"),
            ("columnas", "Fase 2: Análisis de Columnas"),
            ("target", "Fase 3: Variable Objetivo"),
        ]

        # Add optional sections
        if inspections:
            sections.append(("inspecciones", "Fase 4: Inspecciones"))
        if geo:
            sections.append(("geo", "Fase 5: Geoespacial"))
        if joins:
            sections.append(("joins", "Fase 6: Joins Multi-fuente"))
        sections.append(("importancia", "Fase 7: Importancia de Variables"))
        if segmentation:
            sections.append(("segmentacion", "Fase 8: Segmentación"))

        items = "".join(f'<li><a href="#{sid}">{label}</a></li>' for sid, label in sections)
        return f"<ul>{items}</ul>"

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
    <h2>Resumen Ejecutivo</h2>
    <div class="two-col">
        <div>
            <h3>Calidad del Dataset</h3>
            <div class="quality-score {quality_class}">{quality_score:.1f}%</div>
            <p style="text-align:center;color:#666;font-size:13px;">Celdas completas (sin nulos)</p>
        </div>
        <div>
            <h3>Alertas por Severidad</h3>
            <div class="stats-grid" style="grid-template-columns: 1fr 1fr 1fr; margin-top:10px;">
                <div class="stat-card" style="background:#ffebee;">
                    <div class="value" style="color:#f44336;">{error_count}</div>
                    <div class="label">Errores</div>
                </div>
                <div class="stat-card" style="background:#fff3e0;">
                    <div class="value" style="color:#ff9800;">{warning_count}</div>
                    <div class="label">Advertencias</div>
                </div>
                <div class="stat-card" style="background:#e3f2fd;">
                    <div class="value" style="color:#2196f3;">{info_count}</div>
                    <div class="label">Informativas</div>
                </div>
            </div>
        </div>
    </div>
    <div class="stats-grid" style="margin-top:20px;">
        <div class="stat-card">
            <div class="value">{rows:,}</div>
            <div class="label">Filas</div>
        </div>
        <div class="stat-card">
            <div class="value">{cols:,}</div>
            <div class="label">Columnas</div>
        </div>
        <div class="stat-card">
            <div class="value">{dup_rows:,}</div>
            <div class="label">Filas Duplicadas ({dup_pct:.1f}%)</div>
        </div>
        <div class="stat-card">
            <div class="value">{len(const_cols)}</div>
            <div class="label">Columnas Constantes</div>
        </div>
        <div class="stat-card">
            <div class="value">{len(fully_null)}</div>
            <div class="label">Columnas Todo Nulo</div>
        </div>
    </div>
</div>
"""

    def _build_alerts_section(self, alerts: List[Dict]) -> str:
        if not alerts:
            return """
<div class="section" id="alertas">
    <h2>Alertas</h2>
    <p style="color:#4caf50;">&#10003; No se detectaron alertas.</p>
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
    <h2>Alertas ({len(alerts)} total)</h2>
    <table class="alert-table">
        <thead>
            <tr>
                <th>Severidad</th>
                <th>Código</th>
                <th>Mensaje</th>
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
        bom_badge = '<span class="badge badge-WARNING">SÍ</span>' if bom else '<span class="badge badge-success">NO</span>'
        numeric_as_str = loading.get("numeric_as_string", [])
        whitespace_cols = loading.get("whitespace_columns", [])

        num_str_table = ""
        if numeric_as_str:
            rows = "".join(
                f'<tr><td>{d["col"]}</td><td>{d["parseable_count"]:,}</td><td>{d["parseable_pct"]:.1f}%</td></tr>' for d in numeric_as_str
            )
            num_str_table = f"""
<h3>Columnas Numéricas como Texto ({len(numeric_as_str)})</h3>
<table class="data-table"><thead><tr><th>Columna</th><th>Valores parseables</th><th>%</th></tr></thead>
<tbody>{rows}</tbody></table>"""

        ws_table = ""
        if whitespace_cols:
            rows = "".join(
                f'<tr><td>{d["col"]}</td><td>{d["affected_count"]:,}</td>'
                f'<td>{d["affected_pct"]:.1f}%</td><td><code>{d.get("example","")}</code></td></tr>'
                for d in whitespace_cols
            )
            ws_table = f"""
<h3>Columnas con Espacios en Blanco ({len(whitespace_cols)})</h3>
<table class="data-table"><thead><tr><th>Columna</th><th>Afectados</th><th>%</th><th>Ejemplo</th></tr></thead>
<tbody>{rows}</tbody></table>"""

        return f"""
<div class="section" id="carga">
    <h2>Fase 0: Validación de Carga</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{loading.get('rows_loaded', 0):,}</div>
            <div class="label">Filas Cargadas</div>
        </div>
        <div class="stat-card">
            <div class="value">{loading.get('encoding_used', 'N/A')}</div>
            <div class="label">Encoding Detectado</div>
        </div>
        <div class="stat-card">
            <div class="value">{loading.get('decimal_separator', '.')}</div>
            <div class="label">Separador Decimal</div>
        </div>
        <div class="stat-card">
            <div class="value">{bom_badge}</div>
            <div class="label">BOM Detectado</div>
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
            f'<tr><td>{d["col"]}</td><td>{d["null_count"]:,}</td><td>{d["null_pct"]:.2f}%</td>'
            f'<td><div class="consumption-bar" style="width:{min(d["null_pct"],100):.0f}%;'
            f'background:linear-gradient(90deg,#f44336,#ffcdd2);"></div></td></tr>'
            for d in top_nulls
        )

        dtype_counts = global_stats.get("dtype_counts", {})
        dtype_html = " ".join(f'<span class="pill">{dtype}: {count}</span>' for dtype, count in dtype_counts.items())

        const_cols = global_stats.get("constant_cols", [])
        const_html = " ".join(f'<span class="pill">{c}</span>' for c in const_cols[:20]) if const_cols else "<em>Ninguna</em>"

        fully_null = global_stats.get("fully_null_cols", [])
        fully_null_html = " ".join(f'<span class="pill">{c}</span>' for c in fully_null[:20]) if fully_null else "<em>Ninguna</em>"

        # Missing heatmap chart
        missing_heatmap_html = charts.get("missing_heatmap_interactive", "")
        null_corr_html = charts.get("null_correlation", "")

        return f"""
<div class="section" id="global">
    <h2>Fase 1: Estadísticas Globales del Dataset</h2>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{global_stats.get('total_nulls', 0):,}</div>
            <div class="label">Total Nulos</div>
        </div>
        <div class="stat-card">
            <div class="value">{global_stats.get('total_null_pct', 0):.2f}%</div>
            <div class="label">% Celdas Nulas</div>
        </div>
        <div class="stat-card">
            <div class="value">{global_stats.get('duplicate_rows', 0):,}</div>
            <div class="label">Filas Duplicadas</div>
        </div>
        <div class="stat-card">
            <div class="value">{global_stats.get('memory_mb', 0):.1f} MB</div>
            <div class="label">Memoria</div>
        </div>
    </div>

    <h3>Tipos de Datos</h3>
    <p>{dtype_html}</p>

    <h3>Columnas Constantes (varianza = 0)</h3>
    <p>{const_html}</p>

    <h3>Columnas Completamente Nulas</h3>
    <p>{fully_null_html}</p>

    <h3>Top 20 Columnas con Más Nulos</h3>
    <table class="data-table">
        <thead><tr><th>Columna</th><th>Nulos</th><th>%</th><th>Barra</th></tr></thead>
        <tbody>{nulls_rows}</tbody>
    </table>

    {f'<div class="chart-container">{missing_heatmap_html}</div>' if missing_heatmap_html else ''}
    {f'<div class="chart-container">{null_corr_html}</div>' if null_corr_html else ''}
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

        return f"""
<div class="section" id="columnas">
    <h2>Fase 2: Análisis de Columnas</h2>

    <h3>Variables Numéricas ({len(numeric)})</h3>
    {numeric_html}

    <h3>Variables Categóricas ({len(categorical)})</h3>
    {categorical_html}

    <h3>Variables Temporales ({len(temporal)})</h3>
    {temporal_html}

    {consumption_html}

    {f'<h3>Matriz de Correlación</h3><div class="chart-container">{corr_chart}</div>' if corr_chart else ''}
</div>
"""

    def _build_numeric_table(self, numeric: List[Dict]) -> str:
        if not numeric:
            return "<p><em>No se encontraron columnas numéricas.</em></p>"

        has_iv = any("iv" in d for d in numeric)
        header_extra = "<th>IV</th><th>KS</th>" if has_iv else ""

        rows = ""
        for d in numeric:
            iv_td = (
                f'<td>{d.get("iv", "—") if d.get("iv") is not None else "—"}</td>'
                f'<td>{d.get("ks_stat", "—") if d.get("ks_stat") is not None else "—"}</td>'
                if has_iv
                else ""
            )
            null_color = "color:#f44336;" if (d.get("null_pct", 0) or 0) > 30 else ""
            rows += f"""
<tr>
    <td><strong>{d.get('col','')}</strong></td>
    <td>{d.get('count', 0):,}</td>
    <td style="{null_color}">{d.get('null_pct', 0):.1f}%</td>
    <td>{d.get('mean', '—')}</td>
    <td>{d.get('std', '—')}</td>
    <td>{d.get('min', '—')}</td>
    <td>{d.get('max', '—')}</td>
    <td>{d.get('p50', '—')}</td>
    <td>{d.get('outlier_pct', 0):.1f}%</td>
    <td>{d.get('skewness', '—')}</td>
    {iv_td}
</tr>"""

        return f"""
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr>
    <th>Columna</th><th>Conteo</th><th>% Nulos</th>
    <th>Media</th><th>Std</th><th>Mín</th><th>Máx</th><th>Mediana</th>
    <th>% Outliers</th><th>Asimetría</th>{header_extra}
</tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""

    def _build_categorical_table(self, categorical: List[Dict]) -> str:
        if not categorical:
            return "<p><em>No se encontraron columnas categóricas.</em></p>"

        has_iv = any("iv" in d for d in categorical)
        header_extra = "<th>IV</th><th>Cramér's V</th>" if has_iv else ""

        rows = ""
        for d in categorical:
            top = d.get("top_categories", [])
            top_str = ", ".join(f"{c['value']} ({c['pct']:.1f}%)" for c in top[:3])
            iv_td = (
                f'<td>{d.get("iv", "—") if d.get("iv") is not None else "—"}</td>'
                f'<td>{d.get("cramers_v", "—") if d.get("cramers_v") is not None else "—"}</td>'
                if has_iv
                else ""
            )
            null_color = "color:#f44336;" if (d.get("null_pct", 0) or 0) > 30 else ""
            rows += f"""
<tr>
    <td><strong>{d.get('col','')}</strong></td>
    <td>{d.get('count', 0):,}</td>
    <td style="{null_color}">{d.get('null_pct', 0):.1f}%</td>
    <td>{d.get('unique_count', 0)}</td>
    <td style="max-width:300px;white-space:normal;">{top_str}</td>
    <td>{d.get('rare_pct', 0):.1f}%</td>
    <td>{d.get('entropy', 0):.2f}</td>
    {iv_td}
</tr>"""

        return f"""
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr>
    <th>Columna</th><th>Conteo</th><th>% Nulos</th>
    <th>Únicos</th><th>Top Categorías</th><th>% Raras</th><th>Entropía</th>{header_extra}
</tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""

    def _build_temporal_table(self, temporal: List[Dict]) -> str:
        if not temporal:
            return "<p><em>No se encontraron columnas temporales.</em></p>"

        rows = ""
        for d in temporal:
            rows += f"""
<tr>
    <td><strong>{d.get('col','')}</strong></td>
    <td>{d.get('count', 0):,}</td>
    <td>{d.get('null_pct', 0):.1f}%</td>
    <td>{d.get('min_date', '—')}</td>
    <td>{d.get('max_date', '—')}</td>
    <td>{d.get('span_days', '—')}</td>
    <td>{d.get('granularity', '—')}</td>
</tr>"""

        return f"""
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr>
    <th>Columna</th><th>Conteo</th><th>% Nulos</th>
    <th>Fecha Mín</th><th>Fecha Máx</th><th>Días span</th><th>Granularidad</th>
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
    <td>{s.get('period','')}</td>
    <td>{s.get('mean', '—')}</td>
    <td>{s.get('std', '—')}</td>
    <td>{s.get('min', '—')}</td>
    <td>{s.get('max', '—')}</td>
    <td>{s.get('zeros_pct', 0):.1f}%</td>
    <td>{s.get('nulls_pct', 0):.1f}%</td>
</tr>"""

        consumption_chart = charts.get("consumption_trend", "")
        consumption_heatmap = charts.get("consumption_heatmap", "")

        return f"""
<h3>Columnas de Consumo ({len(periods)} períodos)</h3>
<div class="stats-grid">
    <div class="stat-card">
        <div class="value">{consumption.get('pct_rows_with_any_zero', 0):.1f}%</div>
        <div class="label">Filas con Algún Cero</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get('pct_rows_all_zero', 0):.1f}%</div>
        <div class="label">Filas Todo Cero</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get('pct_negative', 0):.1f}%</div>
        <div class="label">% Consumo Negativo</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get('pct_constant', 0):.1f}%</div>
        <div class="label">Filas Constantes</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get('pct_abrupt_drop', 0):.1f}%</div>
        <div class="label">Caídas Abruptas (&gt;50%)</div>
    </div>
    <div class="stat-card">
        <div class="value">{consumption.get('trend_slope', 0):.4f}</div>
        <div class="label">Pendiente de Tendencia</div>
    </div>
</div>
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr><th>Período</th><th>Media</th><th>Std</th><th>Mín</th><th>Máx</th><th>% Ceros</th><th>% Nulos</th></tr></thead>
<tbody>{stats_rows}</tbody>
</table>
</div>
{f'<div class="chart-container">{consumption_chart}</div>' if consumption_chart else ''}
{f'<div class="chart-container">{consumption_heatmap}</div>' if consumption_heatmap else ''}
"""

    def _build_target_section(self, target: Dict, charts: Dict) -> str:
        if not target:
            return """
<div class="section" id="target">
    <h2>Fase 3: Variable Objetivo</h2>
    <p><em>No se especificó variable objetivo.</em></p>
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
                f'<tr><td>{d["period"]}</td><td>{d["total"]:,}</td><td>{d["positive"]:,}</td><td>{d["rate"]:.2f}%</td></tr>'
                for d in temporal_rate[:24]
            )
            temporal_table = f"""
<h3>Evolución Temporal de la Tasa de Fraude</h3>
<div style="overflow-x:auto;">
<table class="data-table">
<thead><tr><th>Período</th><th>Total</th><th>Positivos</th><th>Tasa</th></tr></thead>
<tbody>{temporal_rows}</tbody>
</table>
</div>"""
        else:
            temporal_table = ""

        class_balance_chart = charts.get("class_balance", "")
        temporal_chart = charts.get("temporal_rate", "")

        rec_labels = {"over": "Sobremuestreo (over-sampling)", "under": "Submuestreo (under-sampling)", "none": "Sin remuestreo necesario"}
        rec_html = rec_labels.get(recommendation, recommendation)

        return f"""
<div class="section" id="target">
    <h2>Fase 3: Variable Objetivo</h2>
    <div class="two-col">
        <div>
            <table class="data-table">
            <thead><tr><th>Clase</th><th>Conteo</th><th>%</th></tr></thead>
            <tbody>{class_rows}</tbody>
            </table>
            <p style="margin-top:15px;"><strong>Ratio de desbalance:</strong> {imbalance:.1f}:1</p>
            <p><strong>Recomendación:</strong> {rec_html}</p>
        </div>
        <div>
            {f'<div class="chart-container">{class_balance_chart}</div>' if class_balance_chart else ''}
        </div>
    </div>
    {temporal_table}
    {f'<div class="chart-container">{temporal_chart}</div>' if temporal_chart else ''}
</div>
"""

    def _build_importance_section(self, importance: Dict, charts: Dict) -> str:
        if not importance:
            return """
<div class="section" id="importancia">
    <h2>Fase 7: Importancia de Variables</h2>
    <p><em>No se especificó variable objetivo. Análisis de importancia omitido.</em></p>
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
            display_cols = ["feature", "type", "iv", "ks_stat", "cramers_v", "correlation", "combined_score"]
            available_cols = [c for c in display_cols if c in ranking_df.columns]
            top_df = ranking_df[available_cols].head(30)

            header_cells = "".join(f'<th>{c.replace("_", " ").title()}</th>' for c in available_cols)

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

        weak_html = " ".join(f'<span class="pill">{c}</span>' for c in weak_features[:20]) if weak_features else "<em>Ninguna</em>"
        leakage_html = (
            " ".join(f'<span class="pill" style="background:#ffcdd2;color:#c62828;">{c}</span>' for c in leakage_candidates)
            if leakage_candidates
            else "<em>Ninguna</em>"
        )

        return f"""
<div class="section" id="importancia">
    <h2>Fase 7: Importancia de Variables</h2>

    {f'<div class="chart-container">{iv_chart}</div>' if iv_chart else ''}

    <h3>Top 20 Variables (por puntuación combinada)</h3>
    <p>{" ".join(f'<span class="pill"><strong>{i+1}.</strong> {c}</span>' for i, c in enumerate(top_features))}</p>

    <h3>Variables con Bajo Poder Predictivo (IV &lt; umbral)</h3>
    <p>{weak_html}</p>

    <h3>Candidatos a Data Leakage (IV muy alto)</h3>
    <p>{leakage_html}</p>

    <h3>Ranking Completo (Top 30)</h3>
    {table_html}
</div>
"""

    def _build_inspections_section(self, inspections: Dict, charts: Dict) -> str:
        """Build Phase 4: Inspections section."""
        if not inspections:
            return ""

        tipo_dist = inspections.get("tipo_distribution", {})
        detection_rate = inspections.get("detection_rate", 0)
        temporal = inspections.get("temporal_distribution", [])

        tipo_rows = "".join(f"<tr><td>{tipo}</td><td>{count:,}</td></tr>" for tipo, count in tipo_dist.items())

        temporal_rows = "".join(f'<tr><td>{d["period"]}</td><td>{d["count"]:,}</td></tr>' for d in temporal[:12])

        sunburst_chart = charts.get("inspection_sunburst", "")
        funnel_chart = charts.get("inspection_funnel", "")

        return f"""
<div class="section" id="inspecciones">
    <h2>Fase 4: Análisis de Inspecciones</h2>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{detection_rate:.1%}</div>
            <div class="label">Tasa de Detección</div>
        </div>
        <div class="stat-card">
            <div class="value">{len(tipo_dist)}</div>
            <div class="label">Tipos de Servicio</div>
        </div>
    </div>

    {f'<div class="chart-container">{sunburst_chart}</div>' if sunburst_chart else ''}
    {f'<div class="chart-container">{funnel_chart}</div>' if funnel_chart else ''}

    <h3>Distribución por Tipo de Servicio</h3>
    <table class="data-table">
        <thead><tr><th>Tipo</th><th>Conteo</th></tr></thead>
        <tbody>{tipo_rows}</tbody>
    </table>

    {f'''
    <h3>Distribución Temporal</h3>
    <table class="data-table">
        <thead><tr><th>Período</th><th>Conteo</th></tr></thead>
        <tbody>{temporal_rows}</tbody>
    </table>
    ''' if temporal_rows else ''}
</div>
"""

    def _build_geo_section(self, geo: Dict, charts: Dict) -> str:
        """Build Phase 5: Geospatial section."""
        if not geo:
            return ""

        coord_quality = geo.get("coord_quality", {})
        target_by_zone = geo.get("target_by_zone", {})
        clustering = geo.get("clustering", {})

        mapbox_chart = charts.get("scatter_mapbox", "")

        quality_rows = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in {
                "Registros válidos": f"{coord_quality.get('valid_coords_count', 0):,}",
                "% Nulos": f"{coord_quality.get('null_pct', 0):.1f}%",
                "% Coordenadas (0,0)": f"{coord_quality.get('zero_coord_pct', 0):.1f}%",
                "Duplicados exactos": f"{coord_quality.get('duplicate_coords_pct', 0):.1f}%",
            }.items()
        )

        zone_rows = ""
        if target_by_zone:
            zone_rows = "".join(
                f"<tr><td>{zone}</td><td>{rate:.1%}</td></tr>"
                for zone, rate in sorted(target_by_zone.items(), key=lambda x: x[1], reverse=True)[:15]
            )

        clustering_info = ""
        if clustering.get("cluster_stats"):
            clustering_info = f"""
    <h3>Clustering Geográfico</h3>
    <p>Método: {clustering.get("method", "N/A")}, Clusters: {clustering.get("n_clusters", 0)}</p>
    """

        return f"""
<div class="section" id="geo">
    <h2>Fase 5: Análisis Geoespacial</h2>

    {f'<div class="chart-container">{mapbox_chart}</div>' if mapbox_chart else ''}

    <h3>Calidad de Coordenadas</h3>
    <table class="data-table">
        <thead><tr><th>Métrica</th><th>Valor</th></tr></thead>
        <tbody>{quality_rows}</tbody>
    </table>

    {clustering_info}

    {f'''
    <h3>Tasa de Fraude por Zona</h3>
    <table class="data-table">
        <thead><tr><th>Zona</th><th>Tasa</th></tr></thead>
        <tbody>{zone_rows}</tbody>
    </table>
    ''' if zone_rows else ''}
</div>
"""

    def _build_joins_section(self, joins: Dict) -> str:
        """Build Phase 6: Joins section."""
        if not joins:
            return ""

        coverage = joins.get("coverage", {})
        funnel = joins.get("funnel", [])
        excluded_profile = joins.get("excluded_profile", {})

        coverage_rows = "".join(
            f'<tr><td>{source}</td><td>{cov.get("present_count", 0):,}</td><td>{cov.get("present_pct", 0):.1f}%</td></tr>'
            for source, cov in coverage.items()
        )

        funnel_rows = "".join(
            f'<tr><td>{f.get("stage", "")}</td><td>{f.get("count", 0):,}</td><td>{f.get("pct_of_total", 0):.1f}%</td></tr>' for f in funnel
        )

        excluded_rows = ""
        if excluded_profile:
            target_inc = excluded_profile.get("target_rate_included")
            target_exc = excluded_profile.get("target_rate_excluded")
            if target_inc is not None and target_exc is not None:
                excluded_rows = f"""
    <h3>Perfil de Excluidos vs Incluidos</h3>
    <p>Tasa de fraude en incluidos: {target_inc:.1%}</p>
    <p>Tasa de fraude en excluidos: {target_exc:.1%}</p>
    """

        return f"""
<div class="section" id="joins">
    <h2>Fase 6: Análisis de Joins Multi-fuente</h2>

    <h3>Cobertura por Fuente</h3>
    <table class="data-table">
        <thead><tr><th>Fuente</th><th>Presentes</th><th>%</th></tr></thead>
        <tbody>{coverage_rows}</tbody>
    </table>

    <h3>Embudo de Join</h3>
    <table class="data-table">
        <thead><tr><th>Etapa</th><th>Conteo</th><th>% del Total</th></tr></thead>
        <tbody>{funnel_rows}</tbody>
    </table>

    {excluded_rows}
</div>
"""

    def _build_segmentation_section(self, segmentation: Dict, charts: Dict) -> str:
        """Build Phase 8: Segmentation section."""
        if not segmentation:
            return ""

        segment_stats = segmentation.get("segment_stats", [])

        # Show top segments by z-score
        top_segments = sorted(segment_stats, key=lambda x: abs(x.get("z_score", 0)), reverse=True)[:15]

        segment_rows = "".join(
            f'<tr><td>{s["column"]}={s["segment"]}</td><td>{s["size"]:,}</td><td>{s["size_pct"]:.1f}%</td>'
            f'<td>{s["target_rate"]:.1%}</td><td>{s["z_score"]:.2f}</td></tr>'
            for s in top_segments
        )

        segment_chart = charts.get("segment_barplot", "")

        return f"""
<div class="section" id="segmentacion">
    <h2>Fase 8: Análisis de Segmentación</h2>

    {f'<div class="chart-container">{segment_chart}</div>' if segment_chart else ''}

    <h3>Segmentos con Mayor Diferencia de Tasa de Fraude</h3>
    <table class="data-table">
        <thead><tr><th>Segmento</th><th>Tamaño</th><th>%</th><th>Tasa</th><th>Z-Score</th></tr></thead>
        <tbody>{segment_rows}</tbody>
    </table>
</div>
"""
