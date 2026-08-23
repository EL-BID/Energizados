"""
Comparative Evaluation for Multi-Model Comparison.

Generates side-by-side comparison reports for multiple models.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Vendored Tailwind Play script (source URL, version and license are noted in
# the file header): inlined into self-contained comparison reports for offline use.
_TAILWIND_ASSET = Path(__file__).parent / "assets" / "tailwind-play-3.4.17.min.js"
_TAILWIND_CDN_TAG = '<script src="https://cdn.tailwindcss.com"></script>'


class ComparativeEvaluator:
    """
    Generates comparative evaluation reports for multiple models.

    Produces HTML and JSON reports with metrics tables, rankings, and
    visual comparisons across all evaluated models.

    Args:
        output_dir: Directory to save comparison reports.

    Example:
        >>> evaluator = ComparativeEvaluator("output/reports/evaluation/")
        >>> result = evaluator.compare(all_metrics, all_model_info)
        >>> print(result["html"])  # Path to comparison.html
    """

    def __init__(self, output_dir: str, self_contained: bool = False):
        """
        Initialize the comparative evaluator.

        Args:
            output_dir: Output directory for reports.
            self_contained: If True, inline the vendored Tailwind script in the
                HTML report (offline, no CDN). Default False keeps the CDN tag.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.self_contained = self_contained

    def _tailwind_script_tag(self) -> str:
        """
        Return the ``<script>`` markup that provides Tailwind for the report.

        Default: CDN reference (identical to the historical behavior).
        self_contained: inline the vendored Tailwind Play script shipped as
        package data (works fully offline, adds ~400 KB to the report).
        """
        if not self.self_contained:
            return _TAILWIND_CDN_TAG
        try:
            js = _TAILWIND_ASSET.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Could not read vendored Tailwind script (%s); using CDN", e)
            return _TAILWIND_CDN_TAG
        return f"<script>{js}</script>"

    def compare(
        self,
        all_metrics: Dict[str, Dict],
        all_model_info: Dict[str, Dict],
    ) -> Dict[str, str]:
        """
        Generate comparative report from per-model metrics and info.

        Args:
            all_metrics: Dict mapping model name to metrics dict.
            all_model_info: Dict mapping model name to model info dict.

        Returns:
            Dict with keys:
                - html: Path to comparison HTML report
                - json: Path to comparison JSON report
                - ranking: List of model names sorted by AUC descending
        """
        logger.info("Generating comparative evaluation report...")

        # Calculate ranking
        ranking = self._calculate_ranking(all_metrics)

        # Build comparison data structure
        comparison_data = {
            "ranking": ranking,
            "models": {},
        }

        for model_name in ranking:
            comparison_data["models"][model_name] = {
                "metrics": all_metrics.get(model_name, {}),
                "info": all_model_info.get(model_name, {}),
            }

        # Generate HTML report
        html_path = self.output_dir / "comparison.html"
        html_content = self._build_comparison_html(comparison_data)
        html_path.write_text(html_content, encoding="utf-8")
        logger.info(f"Comparative HTML report saved to: {html_path}")

        # Generate JSON report
        json_path = self.output_dir / "comparison.json"
        json_path.write_text(json.dumps(comparison_data, indent=2), encoding="utf-8")
        logger.info(f"Comparative JSON report saved to: {json_path}")

        return {
            "html": str(html_path),
            "json": str(json_path),
            "ranking": ranking,
        }

    def _calculate_ranking(self, all_metrics: Dict[str, Dict]) -> List[str]:
        """
        Calculate model ranking based on metrics.

        Primary key: AUC (higher is better).
        Secondary keys: F1, Precision, Recall (higher is better).

        Args:
            all_metrics: Dict mapping model name to metrics dict.

        Returns:
            List of model names sorted by ranking.
        """

        def sort_key(model_name):
            metrics = all_metrics.get(model_name, {})
            return (
                -metrics.get("auc", 0.0),  # Negative for descending
                -metrics.get("f1", 0.0),
                -metrics.get("precision", 0.0),
                -metrics.get("recall", 0.0),
            )

        return sorted(all_metrics.keys(), key=sort_key)

    def _build_comparison_html(self, comparison_data: Dict) -> str:
        """
        Build HTML comparison report.

        Args:
            comparison_data: Data structure with ranking and model metrics.

        Returns:
            HTML string for the comparison report.
        """
        models = comparison_data["models"]
        ranking = comparison_data["ranking"]

        # Find best values for each metric
        metrics_to_compare = ["auc", "f1", "precision", "recall", "accuracy"]
        best_metrics = {}
        for metric in metrics_to_compare:
            values = [
                m["metrics"].get(metric, 0.0) for m in models.values() if metric in m["metrics"]
            ]
            if values:
                best_metrics[metric] = max(values)

        # Build metrics table rows
        table_rows = []
        for idx, model_name in enumerate(ranking):
            model_data = models[model_name]
            metrics = model_data["metrics"]
            info = model_data["info"]

            # Build metric cells with highlighting
            metric_cells = []
            for metric in metrics_to_compare:
                value = metrics.get(metric)
                if value is not None:
                    formatted = f"{value:.4f}"
                    # Highlight best value
                    if metric in best_metrics and abs(value - best_metrics[metric]) < 1e-6:
                        formatted = f"<strong>{formatted} ★</strong>"
                    metric_cells.append(formatted)
                else:
                    metric_cells.append("-")

            # Model type badge
            model_class = info.get("model_class", model_name)
            badge_class = self._get_badge_class(model_class)

            table_rows.append(f"""
                <tr class="{"bg-gray-50" if idx % 2 == 0 else "bg-white"}">
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium {badge_class}">
                            {model_name}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{model_class}</td>
                    {"".join(f'<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{cell}</td>' for cell in metric_cells)}
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <a href="{model_name}/evaluation.html" class="text-blue-600 hover:text-blue-900">
                            View Report →
                        </a>
                    </td>
                </tr>
                """)

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Model Comparison Report - Energizados</title>
            {self._tailwind_script_tag()}
        </head>
        <body class="bg-gray-100 min-h-screen">
            <div class="container mx-auto px-4 py-8">
                <!-- Header -->
                <div class="bg-white shadow rounded-lg p-6 mb-6">
                    <h1 class="text-3xl font-bold text-gray-900 mb-2">Model Comparison Report</h1>
                    <p class="text-gray-600">Comparative analysis of {len(ranking)} trained models</p>
                </div>

                <!-- Summary Cards -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                    <div class="bg-white shadow rounded-lg p-6">
                        <div class="text-sm font-medium text-gray-500">Best AUC</div>
                        <div class="text-2xl font-bold text-green-600">
                            {best_metrics.get("auc", 0):.4f}
                        </div>
                        <div class="text-sm text-gray-500">{ranking[0]}</div>
                    </div>
                    <div class="bg-white shadow rounded-lg p-6">
                        <div class="text-sm font-medium text-gray-500">Best F1</div>
                        <div class="text-2xl font-bold text-blue-600">
                            {best_metrics.get("f1", 0):.4f}
                        </div>
                        <div class="text-sm text-gray-500">{self._get_best_model_for_metric(ranking, models, "f1")}</div>
                    </div>
                    <div class="bg-white shadow rounded-lg p-6">
                        <div class="text-sm font-medium text-gray-500">Best Precision</div>
                        <div class="text-2xl font-bold text-purple-600">
                            {best_metrics.get("precision", 0):.4f}
                        </div>
                        <div class="text-sm text-gray-500">{self._get_best_model_for_metric(ranking, models, "precision")}</div>
                    </div>
                    <div class="bg-white shadow rounded-lg p-6">
                        <div class="text-sm font-medium text-gray-500">Best Recall</div>
                        <div class="text-2xl font-bold text-orange-600">
                            {best_metrics.get("recall", 0):.4f}
                        </div>
                        <div class="text-sm text-gray-500">{self._get_best_model_for_metric(ranking, models, "recall")}</div>
                    </div>
                </div>

                <!-- Metrics Table -->
                <div class="bg-white shadow rounded-lg overflow-hidden mb-6">
                    <div class="px-6 py-4 border-b border-gray-200">
                        <h2 class="text-xl font-semibold text-gray-900">Metrics Comparison</h2>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">AUC</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">F1</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Precision</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Recall</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Accuracy</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200">
                                {"".join(table_rows)}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Legend -->
                <div class="bg-white shadow rounded-lg p-6">
                    <h3 class="text-lg font-semibold text-gray-900 mb-4">Legend</h3>
                    <div class="flex items-center space-x-6">
                        <div class="flex items-center">
                            <span class="text-sm text-gray-600">★ = Best value</span>
                        </div>
                    </div>
                </div>

                <!-- Footer -->
                <div class="mt-8 text-center text-gray-500 text-sm">
                    <p>Generated by Energizados ML Framework</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _get_badge_class(self, model_type: str) -> str:
        """Get Tailwind badge class based on model type."""
        badge_map = {
            "lightgbm": "bg-green-100 text-green-800",
            "catboost": "bg-blue-100 text-blue-800",
            "neural_network": "bg-purple-100 text-purple-800",
            "lstm": "bg-pink-100 text-pink-800",
            "simple_trend": "bg-yellow-100 text-yellow-800",
            "simple_constant": "bg-orange-100 text-orange-800",
        }
        return badge_map.get(model_type, "bg-gray-100 text-gray-800")

    def _get_best_model_for_metric(
        self, ranking: List[str], models: Dict[str, Dict], metric: str
    ) -> str:
        """Get the model name with the best value for a given metric."""
        best_value = -1.0
        best_model = "N/A"

        for model_name in ranking:
            value = models[model_name]["metrics"].get(metric, 0.0)
            if value > best_value:
                best_value = value
                best_model = model_name

        return best_model
