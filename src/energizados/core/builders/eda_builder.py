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
    """

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
                    output_dir=output_cfg.get("output_dir", "output/eda/"),
                    sections=eda_config.get("sections"),
                    config=full_config,
                )
                results = explorer.run()
                context["eda_results"] = results
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
