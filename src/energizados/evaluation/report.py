"""
Report Module for Energizados Framework.

Genera reportes de evaluación en HTML y JSON.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generador de reportes de evaluación.

    Args:
        output_dir: Directorio donde guardar los reportes

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
    ) -> str:
        """
        Genera un reporte HTML con los resultados.

        Args:
            metrics: Diccionario con métricas calculadas
            plots: Diccionario con rutas a los gráficos
            model_info: Información del modelo (opcional)
            save_path: Ruta para guardar (opcional)

        Returns:
            str: Ruta donde se guardó el reporte
        """
        html_content = self._build_html(metrics, plots, model_info)

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
    ) -> str:
        """
        Genera un reporte JSON con los resultados.

        Args:
            metrics: Diccionario con métricas calculadas
            model_info: Información del modelo (opcional)
            save_path: Ruta para guardar (opcional)

        Returns:
            str: Ruta donde se guardó el reporte
        """
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "model_info": model_info or {},
        }

        path = save_path or str(self.output_dir / "evaluation_report.json")

        with open(path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        logger.info(f"JSON report saved to: {path}")
        return path

    def _build_html(
        self,
        metrics: Dict,
        plots: Dict[str, str],
        model_info: Optional[Dict] = None,
    ) -> str:
        """Construye el contenido HTML del reporte."""
        # Convertir rutas de archivos a relativas
        plots_rel = {k: Path(v).name for k, v in plots.items()}

        html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evaluation Report - Energizados</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .section {{
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #667eea;
        }}
        .metric-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}
        .metric-card .label {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .plots-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .plot-container {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .plot-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 5px;
        }}
        .plot-container h3 {{
            margin-top: 0;
            color: #667eea;
        }}
        .confusion-matrix {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            max-width: 300px;
            margin: 20px auto;
        }}
        .cm-cell {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            border-radius: 8px;
        }}
        .cm-cell.tp {{ border-left: 4px solid #28a745; }}
        .cm-cell.tn {{ border-left: 4px solid #6c757d; }}
        .cm-cell.fp {{ border-left: 4px solid #dc3545; }}
        .cm-cell.fn {{ border-left: 4px solid #ffc107; }}
        .cm-cell .value {{
            font-size: 2em;
            font-weight: bold;
        }}
        .cm-cell .label {{
            font-size: 0.8em;
            color: #666;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Model Evaluation Report</h1>
        <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        {self._build_model_info_html(model_info) if model_info else ''}
    </div>

    <div class="section">
        <h2>Performance Metrics</h2>
        <div class="metrics-grid">
            {self._build_metrics_html(metrics)}
        </div>
    </div>

    {self._build_confusion_matrix_html(metrics)}

    <div class="section">
        <h2>Visualizations</h2>
        <div class="plots-grid">
            {self._build_plots_html(plots_rel)}
        </div>
    </div>

    <div class="footer">
        <p>Generated by Energizados Framework</p>
    </div>
</body>
</html>
"""
        return html

    def _build_metrics_html(self, metrics: Dict) -> str:
        """Construye el HTML para las tarjetas de métricas."""
        html_parts = []

        # Métricas principales
        metric_configs = [
            ("AUC", "auc", "Area Under ROC Curve"),
            ("F1 Score", "f1", "F1 Score"),
            ("Precision", "precision", "Precision"),
            ("Recall", "recall", "Recall/Sensitivity"),
            ("Accuracy", "accuracy", "Accuracy"),
        ]

        for label, key, description in metric_configs:
            value = metrics.get(key, 0)
            if isinstance(value, (int, float)):
                display_value = f"{value:.4f}"
            else:
                display_value = str(value)

            html_parts.append(f"""
            <div class="metric-card">
                <div class="value">{display_value}</div>
                <div class="label">{label}</div>
            </div>
""")

        return "".join(html_parts)

    def _build_confusion_matrix_html(self, metrics: Dict) -> str:
        """Construye el HTML para la matriz de confusión."""
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
            <div class="cm-cell tp">
                <div class="value">{tp}</div>
                <div class="label">True Positive</div>
            </div>
            <div class="cm-cell fp">
                <div class="value">{fp}</div>
                <div class="label">False Positive</div>
            </div>
            <div class="cm-cell fn">
                <div class="value">{fn}</div>
                <div class="label">False Negative</div>
            </div>
            <div class="cm-cell tn">
                <div class="value">{tn}</div>
                <div class="label">True Negative</div>
            </div>
        </div>
        <p style="text-align: center; color: #666;">
            <img src="confusion_matrix.png" alt="Confusion Matrix" style="max-width: 400px;">
        </p>
    </div>
"""

    def _build_plots_html(self, plots: Dict[str, str]) -> str:
        """Construye el HTML para los gráficos."""
        html_parts = []

        for plot_name, plot_path in plots.items():
            label = plot_name.replace("_", " ").title()
            html_parts.append(f"""
            <div class="plot-container">
                <h3>{label}</h3>
                <img src="{plot_path}" alt="{label}">
            </div>
""")

        return "".join(html_parts)

    def _build_model_info_html(self, model_info: Dict) -> str:
        """Construye el HTML para la información del modelo."""
        if not model_info:
            return ""

        info_lines = []
        for key, value in model_info.items():
            info_lines.append(f"<strong>{key}:</strong> {value}")

        return f'<p>{" | ".join(info_lines)}</p>'
