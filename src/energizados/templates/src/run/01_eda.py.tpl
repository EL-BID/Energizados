"""
EDA Script - {{project_name}}

Runs Exploratory Data Analysis on the raw dataset before preprocessing.

Usage:
    python src/run/00_eda.py

Requires:
    - config/eda.yaml configured with paths and sections
    - The primary data source file referenced in eda.yaml must exist
"""

import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

from energizados.eda.dataset_explorer import DatasetExplorer


def main():
    config_path = Path("config/eda.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Resolve input path from config
    eda_cfg = config.get("eda", config)
    data_sources = eda_cfg.get("data_sources", {})
    primary = data_sources.get("primary", {})
    input_path = primary.get("path")

    if not input_path:
        raise ValueError("No input_path found in config. Set data_sources.primary.path in eda.yaml")

    # Resolve output dir
    output_cfg = eda_cfg.get("output", {})
    output_dir = output_cfg.get("output_dir", "output/eda/")

    # Column detection config
    col_detection = eda_cfg.get("column_detection", {})

    explorer = DatasetExplorer(
        input_path=input_path,
        target_column=primary.get("target_col"),
        id_column=col_detection.get("id_col"),
        date_column=col_detection.get("date_col"),
        lat_column=col_detection.get("lat_col"),
        lon_column=col_detection.get("lon_col"),
        zone_column=col_detection.get("zone_col"),
        periods_suffix=col_detection.get("periods_suffix", "_anterior"),
        output_dir=output_dir,
        sections=eda_cfg.get("sections"),
        config=config,
    )
    results = explorer.run()

    report_path = results.get("report_path", "")
    alert_count = len(results.get("alerts", []))
    error_count = sum(1 for a in results.get("alerts", []) if a.get("severity") == "ERROR")
    warning_count = sum(1 for a in results.get("alerts", []) if a.get("severity") == "WARNING")

    logger.info("EDA completed")
    logger.info("Report: %s", report_path)
    logger.info("Alerts: %d total (%d errors, %d warnings)", alert_count, error_count, warning_count)


if __name__ == "__main__":
    main()
