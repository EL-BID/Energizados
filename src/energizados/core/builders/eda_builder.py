"""
EDA Step Builder.

This module constructs Exploratory Data Analysis pipeline steps from configuration.
"""

from typing import Any, Dict, List, Optional

from energizados.core.base import PipelineStep
from energizados.core.builders.base import StepBuilder
from energizados.eda.dataset_explorer import DatasetExplorer


class EDABuilder(StepBuilder):
    """
    Builder for EDA pipeline steps.

    Constructs a step that performs exploratory data analysis
    based on the 'eda' section of the configuration.

    ADR-0001: when ``run_dir`` is provided (typed EDA run), the HTML report is
    written into the run dir (``<run_dir>/eda_report.html``) instead of the
    fixed ``output/eda/`` location, and the report path is pushed to context as
    ``eda_report_path`` for run-metadata bookkeeping.
    """

    def __init__(self, config: Dict[str, Any], run_dir: Optional[Any] = None):
        super().__init__(config)
        # ``run_dir`` may be a Path or None; kept as-is (DatasetExplorer wants a str).
        self._run_dir = run_dir

    def build(self) -> Optional[PipelineStep]:
        """
        Build the EDA step from configuration.

        Returns:
            PipelineStep: The EDA step, or None if not configured
        """
        eda_config = self.config
        if not eda_config:
            return None

        full_config = self.config
        run_dir = self._run_dir

        # ADR-0001: relocate the report into the run dir for typed EDA runs.
        if run_dir is not None:
            default_output_dir = str(run_dir)
        else:
            default_output_dir = "output/eda/"

        class EDAStep(PipelineStep):
            """Pipeline step that runs Exploratory Data Analysis."""

            def validate_input(self, context: Dict[str, Any]) -> bool:
                return True

            def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                col_detection = eda_config.get("column_detection", {})
                data_sources = eda_config.get("data_sources", {})
                primary = data_sources.get("primary", {})
                output_cfg = eda_config.get("output", {})

                explorer = DatasetExplorer(
                    input_path=primary.get("path", ""),
                    target_column=primary.get("target_col"),
                    id_column=col_detection.get("id_col"),
                    date_column=col_detection.get("date_col"),
                    lat_column=col_detection.get("lat_col"),
                    lon_column=col_detection.get("lon_col"),
                    zone_column=col_detection.get("zone_col"),
                    periods_suffix=col_detection.get("periods_suffix", "_anterior"),
                    output_dir=output_cfg.get("output_dir", default_output_dir),
                    sections=eda_config.get("sections"),
                    config=full_config,
                )
                results = explorer.run()
                context["eda_results"] = results
                # ADR-0001: surface the report path for run-metadata output_paths.
                if isinstance(results, dict) and results.get("report_path"):
                    context["eda_report_path"] = results["report_path"]
                return context

            def get_required_keys(self) -> List[str]:
                return []

            def get_output_keys(self) -> List[str]:
                return ["eda_results"]

        return EDAStep()

    def is_enabled(self) -> bool:
        """Check if EDA step is enabled.

        Returns:
            bool: True if EDA config exists
        """
        return bool(self.config)
