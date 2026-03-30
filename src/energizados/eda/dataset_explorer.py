"""
Dataset Explorer - Energizados EDA Framework.

Main orchestrator class that runs all EDA phases and generates the HTML report.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from energizados.eda._outlier_detector import OutlierDetector
from energizados.eda._population_segmenter import PopulationAnalyzer
from energizados.eda.column_explorer import ColumnExplorer
from energizados.eda.feature_importance import FeatureImportanceAnalyzer
from energizados.eda.geo_analyzer import GeospatialAnalyzer
from energizados.eda.loading_validator import LoadingValidator
from energizados.eda.plots import EDAStaticPlots
from energizados.eda.plots_interactive import EDAInteractivePlots
from energizados.eda.related_columns_analyzer import RelatedColumnsAnalyzer
from energizados.eda.report import EDAReportGenerator
from energizados.eda.segmentation_analyzer import SegmentationAnalyzer
from energizados.eda.target_explorer import TargetExplorer
from energizados.eda.utils import classify_columns

logger = logging.getLogger(__name__)


class DatasetExplorer:
    """
    Main EDA orchestrator for the Energizados Framework.

    Loads a dataset, runs all exploratory analysis phases, and generates
    a comprehensive HTML report.

    Args:
        input_path: Path to parquet or CSV dataset
        target_column: Name of binary target column (optional)
        id_column: Name of ID column (optional)
        date_column: Name of date column (optional)
        lat_column: Name of latitude column (optional)
        lon_column: Name of longitude column (optional)
        zone_column: Name of zone/geographic column (optional)
        periods_suffix: Suffix for consumption period columns (default '_anterior')
        output_dir: Output directory for report and plots
        sections: Dict of section enable/disable overrides
        config: Full config dict (overrides individual params when provided)

    Example:
        >>> explorer = DatasetExplorer(
        ...     input_path="data/processed/dataset.parquet",
        ...     target_column="target",
        ...     output_dir="output/eda/",
        ... )
        >>> results = explorer.run()
    """

    def __init__(
        self,
        input_path: str,
        target_column: Optional[str] = None,
        id_column: Optional[str] = None,
        date_column: Optional[str] = None,
        lat_column: Optional[str] = None,
        lon_column: Optional[str] = None,
        zone_column: Optional[str] = None,
        periods_suffix: str = "_anterior",
        output_dir: str = "output/eda/",
        sections: Optional[Dict] = None,
        config: Optional[Dict] = None,
    ):
        # Allow full config dict to override individual params
        if config:
            eda_cfg = config.get("eda", config)
            col_detection = eda_cfg.get("column_detection", {})
            data_sources = eda_cfg.get("data_sources", {})
            primary = data_sources.get("primary", {})

            self.input_path = primary.get("path", input_path)
            self.target_column = primary.get("target_col", target_column)
            self.id_column = col_detection.get("id_col", id_column)
            self.date_column = col_detection.get("date_col", date_column)
            self.lat_column = col_detection.get("lat_col", lat_column)
            self.lon_column = col_detection.get("lon_col", lon_column)
            self.zone_column = col_detection.get("zone_col", zone_column)
            self.periods_suffix = col_detection.get("periods_suffix", periods_suffix)
            output_cfg = eda_cfg.get("output", {})
            self.output_dir = output_cfg.get("output_dir", output_dir)
            self.sections = sections or eda_cfg.get("sections", {})
            self._full_config = eda_cfg
        else:
            self.input_path = input_path
            self.target_column = target_column
            self.id_column = id_column
            self.date_column = date_column
            self.lat_column = lat_column
            self.lon_column = lon_column
            self.zone_column = zone_column
            self.periods_suffix = periods_suffix
            self.output_dir = output_dir
            self.sections = sections or {}
            self._full_config = {}

        self.output_dir_path = Path(self.output_dir)
        self.output_dir_path.mkdir(parents=True, exist_ok=True)

        # Normalize section key aliases so both old and new config names work:
        #   "target_analysis" -> "target"
        #   "data_quality"    -> "global_stats"  (features already in global_stats)
        #   "missing_values"  -> merged into "global_stats"
        #   "duplicates"      -> merged into "global_stats"
        self.sections = self._normalize_section_keys(self.sections)

        # Threshold configuration
        thresholds = self._full_config.get("thresholds", {})
        self._thresholds = {
            "missing_threshold": thresholds.get("missing_threshold", 0.5),
            "correlation_threshold": thresholds.get("correlation_threshold", 0.95),
            "cardinality_high": thresholds.get("cardinality_high", 100),
            "cardinality_low": thresholds.get("cardinality_low", 10),
            "class_imbalance_ratio": thresholds.get("class_imbalance_ratio", 10),
            "iv_threshold_weak": thresholds.get("iv_threshold_weak", 0.02),
            "iv_threshold_leakage": thresholds.get("iv_threshold_leakage", 0.8),
        }

        # All collected alerts
        self._all_alerts: List[Dict] = []

    def run(self) -> Dict:
        """
        Execute all EDA phases and generate HTML report.

        Returns:
            dict with keys:
                - loading: LoadingValidator results
                - global_stats: Global dataset statistics
                - columns: ColumnExplorer results
                - target: TargetExplorer results
                - importance: FeatureImportanceAnalyzer results
                - col_types: classify_columns output
                - alerts: All alerts from all phases
                - report_path: Path to generated HTML report
        """
        logger.info("=" * 60)
        logger.info("START - Exploratory Data Analysis (EDA)")
        logger.info("=" * 60)
        logger.info("File: %s", self.input_path)

        # --- Load dataset ---
        df = self._load_dataset()
        if df is None:
            raise RuntimeError(f"Could not load dataset: {self.input_path}")

        logger.info("Dataset loaded: %d rows × %d columns", len(df), len(df.columns))

        # --- Classify columns ---
        col_types = classify_columns(
            df,
            periods_suffix=self.periods_suffix,
            lat_col=self.lat_column,
            lon_col=self.lon_column,
            date_col=self.date_column,
            id_col=self.id_column,
        )
        logger.info(
            "Types detected: %d numeric, %d categorical, %d temporal, %d consumption",
            len(col_types["numeric"]),
            len(col_types["categorical"]),
            len(col_types["temporal"]),
            len(col_types["consumption"]),
        )

        # --- Alert when no target column ---
        if not self.target_column or self.target_column not in df.columns:
            missing_reason = (
                "not configured"
                if not self.target_column
                else f"'{self.target_column}' not found in dataset"
            )
            self._add_alert(
                code="NO_TARGET_COLUMN",
                message=(
                    f"Target column {missing_reason}. Running unsupervised EDA. "
                    "Phases skipped: 3 (target analysis), 7 (feature importance), 8 (segmentation)."
                ),
                severity="INFO",
            )

        # --- Phase 0: Loading validator ---
        loading_results = {}
        loading_cfg = self.sections.get("loading", {})
        if loading_cfg.get("enabled", True):
            logger.info("Phase 0: Loading validation...")
            loading_results = self._run_loading_validator(df)

        # --- Phase 1: Global dataset stats ---
        global_stats = {}
        global_stats_cfg = self.sections.get("global_stats", {})
        if global_stats_cfg.get("enabled", True):
            logger.info("Phase 1: Global statistics...")
            global_stats = self._compute_global_stats(df)

        # --- Phase 2: Column explorer ---
        columns_results = {}
        columns_cfg = self.sections.get("columns", {})
        if columns_cfg.get("enabled", True):
            logger.info("Phase 2: Column analysis...")
            columns_results = self._run_column_explorer(df, col_types)

        # --- Phase 2.5: Outlier Analysis (optional) ---
        outliers_results = {}
        outliers_cfg = self.sections.get("outliers", {})
        if outliers_cfg.get("enabled", True):
            logger.info("Phase 2.5: Outlier analysis...")
            outliers_results = self._run_outlier_analysis(df, col_types)

        # --- Phase 3: Target explorer ---
        target_results = {}
        target_cfg = self.sections.get("target", {})
        if (
            target_cfg.get("enabled", True)
            and self.target_column
            and self.target_column in df.columns
        ):
            logger.info("Phase 3: Target variable analysis '%s'...", self.target_column)
            target_results = self._run_target_explorer(df)

        # --- Phase 4: Geospatial analyzer (optional) ---
        geo_results = {}
        geo_cfg = self.sections.get("geospatial", {})
        if geo_cfg.get("enabled", False) and (
            self.lat_column or self.lon_column or self.zone_column
        ):
            logger.info("Phase 4: Geospatial analysis...")
            geo_results = self._run_geo_analyzer(df)

        # --- Phase 5: Feature importance ---
        importance_results = {}
        importance_cfg = self.sections.get("feature_importance", {})
        if (
            importance_cfg.get("enabled", True)
            and self.target_column
            and self.target_column in df.columns
        ):
            logger.info("Phase 5: Feature importance analysis...")
            importance_results = self._run_feature_importance(df, col_types)

        # --- Phase 6: Segmentation analyzer (optional) ---
        segmentation_results = {}
        seg_cfg = self.sections.get("segmentation", {})
        if (
            seg_cfg.get("enabled", False)
            and self.target_column
            and self.target_column in df.columns
        ):
            logger.info("Phase 6: Segmentation analysis...")
            segmentation_results = self._run_segmentation_analyzer(df)

        # --- Phase 7: Related columns analyzer (optional) ---
        related_columns_results = {}
        rc_cfg = self.sections.get("related_columns", {})
        if rc_cfg.get("enabled", False):
            hierarchies = rc_cfg.get("hierarchies", [])
            if hierarchies:
                logger.info(
                    "Phase 7: Related columns analysis (%d hierarchies)...", len(hierarchies)
                )
                related_columns_results = self._run_related_columns_analyzer(df, hierarchies)

        # --- Generate charts ---
        logger.info("Generating charts...")
        charts = self._generate_charts(
            df,
            col_types,
            target_results,
            importance_results,
            global_stats,
            outliers_results,
            related_columns_results,
            geo_results,
        )

        # --- Generate report ---
        logger.info("Generating HTML report...")
        results = {
            "loading": loading_results,
            "global_stats": global_stats,
            "columns": columns_results,
            "outliers": outliers_results,
            "target": target_results,
            "importance": importance_results,
            "geo": geo_results,
            "segmentation": segmentation_results,
            "related_columns": related_columns_results,
            "col_types": col_types,
            "alerts": self._all_alerts,
            "charts": charts,
        }

        report_path = self._generate_report(results)
        results["report_path"] = report_path

        logger.info("=" * 60)
        logger.info("EDA completed. Report: %s", report_path)
        logger.info("Total alerts: %d", len(self._all_alerts))
        logger.info("=" * 60)

        return results

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_section_keys(sections: Dict) -> Dict:
        """
        Normalize section key aliases for backward compatibility.

        Supports config keys used in YAML templates that differ from internal keys:
            "target_analysis" -> "target"
            "data_quality"    -> "global_stats" (data quality is computed inside global_stats)
            "missing_values"  -> "global_stats" (missing value stats are part of global_stats)
            "duplicates"      -> "global_stats" (duplicate counts are part of global_stats)

        The alias is only applied when the canonical key is absent.
        """
        normalized = dict(sections)

        # target_analysis -> target
        if "target_analysis" in normalized and "target" not in normalized:
            normalized["target"] = normalized.pop("target_analysis")
        elif "target_analysis" in normalized:
            normalized.pop("target_analysis")

        # data_quality / missing_values / duplicates -> global_stats
        for alias in ("data_quality", "missing_values", "duplicates"):
            if alias in normalized and "global_stats" not in normalized:
                # Use the first alias found as the global_stats config
                normalized["global_stats"] = normalized.pop(alias)
            elif alias in normalized:
                # Canonical key already exists — merge sub-options, don't overwrite enabled flag
                alias_cfg = normalized.pop(alias)
                for k, v in alias_cfg.items():
                    if k not in normalized["global_stats"]:
                        normalized["global_stats"][k] = v

        return normalized

    def _load_dataset(self) -> Optional[pd.DataFrame]:
        """Load the dataset from parquet or CSV."""
        path = Path(self.input_path)

        loading_cfg = self._full_config.get("loading", {})
        encoding = loading_cfg.get("file_encoding", "utf-8")
        decimal = loading_cfg.get("decimal_separator", ".")

        try:
            if path.suffix.lower() == ".parquet":
                logger.info("Loading parquet...")
                return pd.read_parquet(str(path))
            elif path.suffix.lower() in (".csv", ".tsv"):
                logger.info("Loading CSV with encoding='%s', decimal='%s'...", encoding, decimal)
                sep = "\t" if path.suffix.lower() == ".tsv" else ","
                return pd.read_csv(
                    str(path),
                    encoding=encoding,
                    decimal=decimal,
                    sep=sep,
                    on_bad_lines=loading_cfg.get("on_bad_lines", "warn"),
                )
            else:
                # Try parquet first, then CSV
                try:
                    return pd.read_parquet(str(path))
                except Exception:
                    return pd.read_csv(str(path), encoding=encoding, decimal=decimal)
        except FileNotFoundError:
            logger.error("File not found: %s", self.input_path)
            return None
        except Exception as e:
            logger.error("Error loading dataset: %s", e)
            return None

    def _run_loading_validator(self, df: pd.DataFrame) -> Dict:
        """Run Phase 0: loading validator."""
        loading_cfg = self._full_config.get("loading", {})
        validator = LoadingValidator(config=self._thresholds)
        results = validator.analyze(
            df,
            raw_path=self.input_path,
            encoding_used=loading_cfg.get("file_encoding", "utf-8"),
            decimal_used=loading_cfg.get("decimal_separator", "."),
        )
        self._all_alerts.extend(validator.get_alerts())
        return results

    def _compute_global_stats(self, df: pd.DataFrame) -> Dict:
        """Phase 1: Compute global dataset statistics."""
        total_cells = df.shape[0] * df.shape[1]
        total_nulls = int(df.isna().sum().sum())
        total_null_pct = round(total_nulls / total_cells * 100, 4) if total_cells > 0 else 0.0

        # Missing values per column
        null_by_col = df.isna().sum()
        nulls_by_col = [
            {
                "col": col,
                "null_count": int(null_by_col[col]),
                "null_pct": round(float(null_by_col[col]) / len(df) * 100, 4),
            }
            for col in df.columns
            if null_by_col[col] > 0
        ]
        nulls_by_col = sorted(nulls_by_col, key=lambda x: x["null_pct"], reverse=True)

        fully_null_cols = [d["col"] for d in nulls_by_col if d["null_pct"] >= 100.0]

        # Constant columns
        constant_cols = [col for col in df.columns if df[col].nunique(dropna=False) <= 1]

        # Duplicate rows
        dup_mask = df.duplicated()
        duplicate_rows = int(dup_mask.sum())
        duplicate_rows_pct = round(duplicate_rows / len(df) * 100, 4) if len(df) > 0 else 0.0

        # Memory usage
        memory_mb = round(df.memory_usage(deep=True).sum() / 1024 / 1024, 4)

        # Dtype counts
        dtype_counts = {}
        for col in df.columns:
            dtype_str = str(df[col].dtype)
            dtype_counts[dtype_str] = dtype_counts.get(dtype_str, 0) + 1

        # Null correlation matrix (only for columns with nulls)
        null_corr = pd.DataFrame()
        null_cols_list = [d["col"] for d in nulls_by_col[:20]]
        if len(null_cols_list) > 1:
            try:
                null_indicators = df[null_cols_list].isna().astype(int)
                null_corr = null_indicators.corr()
            except Exception as e:
                logger.debug("Error computing null correlation: %s", e)

        stats = {
            "shape": df.shape,
            "memory_mb": memory_mb,
            "dtype_counts": dtype_counts,
            "total_nulls": total_nulls,
            "total_null_pct": total_null_pct,
            "nulls_by_col": nulls_by_col,
            "fully_null_cols": fully_null_cols,
            "constant_cols": constant_cols,
            "duplicate_rows": duplicate_rows,
            "duplicate_rows_pct": duplicate_rows_pct,
            "null_correlation": null_corr,
        }

        # Fire alerts
        missing_threshold = self._thresholds.get("missing_threshold", 0.5)
        for d in nulls_by_col:
            if d["null_pct"] / 100 > missing_threshold:
                self._add_alert(
                    code="HIGH_MISSING",
                    message=f"Column '{d['col']}' has {d['null_pct']:.1f}% missing values (threshold: {missing_threshold * 100:.0f}%).",
                    severity="WARNING",
                    details={"col": d["col"], "null_pct": d["null_pct"]},
                )

        for col in fully_null_cols:
            self._add_alert(
                code="ALL_MISSING",
                message=f"Column '{col}' is completely empty (100% missing). Consider removing it.",
                severity="ERROR",
                details={"col": col},
            )

        for col in constant_cols:
            self._add_alert(
                code="CONSTANT",
                message=f"Column '{col}' has a single value (variance = 0). Does not provide predictive information.",
                severity="WARNING",
                details={"col": col},
            )

        if duplicate_rows_pct > 1:
            self._add_alert(
                code="DUPLICATED_ROWS",
                message=f"Found {duplicate_rows:,} duplicate rows ({duplicate_rows_pct:.2f}%). Verify if this is expected.",
                severity="WARNING",
                details={
                    "duplicate_rows": duplicate_rows,
                    "duplicate_rows_pct": duplicate_rows_pct,
                },
            )

        return stats

    def _run_column_explorer(self, df: pd.DataFrame, col_types: Dict) -> Dict:
        """Phase 2: Run column explorer."""
        # Merge section-level flags into the config passed to ColumnExplorer so
        # that sub-options like iv_woe_calculation, ks_test, cramers_v, etc.
        # are respected when set to False in the config.
        numeric_cfg = self.sections.get("numeric", {})
        categorical_cfg = self.sections.get("categorical", {})

        column_config = dict(self._thresholds)
        column_config["numeric_iv_woe"] = numeric_cfg.get("iv_woe_binned", True)
        column_config["numeric_ks_test"] = numeric_cfg.get("ks_test", True)
        column_config["numeric_outliers_by_iqr"] = numeric_cfg.get("outliers_by_iqr", True)
        column_config["categorical_iv_woe"] = categorical_cfg.get("iv_woe_calculation", True)
        column_config["categorical_cramers_v"] = categorical_cfg.get("cramers_v", True)

        explorer = ColumnExplorer(config=column_config)
        results = explorer.analyze(
            df, target_col=self.target_column, col_types=col_types, config=column_config
        )
        self._all_alerts.extend(explorer.get_alerts())
        return results

    def _run_outlier_analysis(self, df: pd.DataFrame, col_types: Dict) -> Dict:
        """Phase 2.5: Run outlier analysis."""
        outliers_cfg = self.sections.get("outliers", {})
        methods = outliers_cfg.get("methods", ["iqr", "zscore"])
        thresholds_cfg = outliers_cfg.get("thresholds", {})
        consumption_patterns = outliers_cfg.get("consumption_patterns", True)
        alert_threshold = outliers_cfg.get("alert_threshold", 10.0)
        store_masks = outliers_cfg.get("detailed_charts", True)

        # Initialize OutlierDetector with config
        detector = OutlierDetector(
            methods=methods,
            iqr_multiplier=thresholds_cfg.get("iqr", 1.5),
            zscore_threshold=thresholds_cfg.get("zscore", 3.0),
            modified_zscore_threshold=thresholds_cfg.get("modified_zscore", 3.5),
            alert_threshold_pct=alert_threshold,
            store_mask=store_masks,
        )

        results = {
            "numeric_outliers": {},
            "consumption_outliers": {},
            "consumption_column_outliers": {},
            "alerts": [],
        }

        # Run outlier detection on all numeric columns
        numeric_cols = col_types.get("numeric", [])
        for col in numeric_cols:
            if col not in df.columns or col == self.target_column:
                continue
            try:
                col_results = detector.detect(df[col])
                results["numeric_outliers"][col] = col_results

                # Generate alerts for high outlier percentages
                for method_name, method_result in col_results.items():
                    if method_result.get("has_alert", False):
                        alert_msg = (
                            f"Column '{col}' has {method_result['outlier_pct']:.2f}% outliers "
                            f"(method: {method_name}, threshold: {alert_threshold}%)"
                        )
                        self._add_alert(
                            code="HIGH_OUTLIER_PCT",
                            message=alert_msg,
                            severity="WARNING",
                            details={
                                "col": col,
                                "method": method_name,
                                "outlier_pct": method_result["outlier_pct"],
                            },
                        )
                        results["alerts"].append(alert_msg)
            except Exception as e:
                logger.warning("Error detecting outliers in column '%s': %s", col, e)

        # Run outlier detection on consumption period columns
        consumption_cols = col_types.get("consumption", [])
        for col in consumption_cols:
            if col not in df.columns:
                continue
            try:
                col_results = detector.detect(df[col])
                results["consumption_column_outliers"][col] = col_results

                for method_name, method_result in col_results.items():
                    if method_result.get("has_alert", False):
                        alert_msg = (
                            f"Consumption column '{col}' has {method_result['outlier_pct']:.2f}% outliers "
                            f"(method: {method_name}, threshold: {alert_threshold}%)"
                        )
                        self._add_alert(
                            code="HIGH_OUTLIER_PCT",
                            message=alert_msg,
                            severity="WARNING",
                            details={
                                "col": col,
                                "method": method_name,
                                "outlier_pct": method_result["outlier_pct"],
                            },
                        )
                        results["alerts"].append(alert_msg)
            except Exception as e:
                logger.warning("Error detecting consumption outliers in column '%s': %s", col, e)

        # Run consumption outlier patterns detection
        if consumption_patterns:
            consumption_cols = col_types.get("consumption", [])
            if consumption_cols:
                try:
                    consumption_results = self._analyze_consumption_outliers(
                        df, consumption_cols, alert_threshold
                    )
                    results["consumption_outliers"] = consumption_results

                    # Generate alerts for consumption anomalies
                    if consumption_results.get("pct_zero_variance", 0) > alert_threshold:
                        alert_msg = (
                            f"{consumption_results['pct_zero_variance']:.2f}% of rows have zero variance "
                            f"consumption (suspiciously constant, potential meter tampering)"
                        )
                        self._add_alert(
                            code="HIGH_ZERO_VARIANCE_CONSUMPTION",
                            message=alert_msg,
                            severity="WARNING",
                            details={"pct": consumption_results["pct_zero_variance"]},
                        )
                        results["alerts"].append(alert_msg)

                    if consumption_results.get("pct_range_outliers", 0) > alert_threshold:
                        alert_msg = (
                            f"{consumption_results['pct_range_outliers']:.2f}% of rows have extreme "
                            f"consumption range swings (potential data quality issues)"
                        )
                        self._add_alert(
                            code="HIGH_RANGE_OUTLIERS_CONSUMPTION",
                            message=alert_msg,
                            severity="WARNING",
                            details={"pct": consumption_results["pct_range_outliers"]},
                        )
                        results["alerts"].append(alert_msg)

                    if consumption_results.get("mean_zscore_outlier_pct", 0) > alert_threshold:
                        alert_msg = (
                            f"{consumption_results['mean_zscore_outlier_pct']:.2f}% of rows have "
                            f"outlier mean consumption (potential fraud)"
                        )
                        self._add_alert(
                            code="HIGH_MEAN_ZSCORE_OUTLIERS_CONSUMPTION",
                            message=alert_msg,
                            severity="WARNING",
                            details={"pct": consumption_results["mean_zscore_outlier_pct"]},
                        )
                        results["alerts"].append(alert_msg)

                except Exception as e:
                    logger.warning("Error analyzing consumption outliers: %s", e)

        # Run population segmentation analysis
        population_cfg = outliers_cfg.get("population_analysis", {})
        if population_cfg.get("enabled", False):
            try:
                population_results = self._analyze_populations(df, col_types, population_cfg)
                results["population_analysis"] = population_results

                # Generate alerts for multiple populations
                for col_name, pop_data in population_results.items():
                    if pop_data.get("has_multiple_populations", False):
                        n_pops = len(pop_data.get("populations", []))
                        alert_msg = (
                            f"Column '{col_name}' has {n_pops} distinct populations. "
                            f"This may indicate multiple data sources or data quality issues."
                        )
                        self._add_alert(
                            code="MULTIPLE_POPULATIONS",
                            message=alert_msg,
                            severity="INFO",
                            details={
                                "col": col_name,
                                "n_populations": n_pops,
                            },
                        )
                        results["alerts"].append(alert_msg)
            except Exception as e:
                logger.warning("Error analyzing populations: %s", e)

        return results

    def _analyze_consumption_outliers(
        self, df: pd.DataFrame, consumption_cols: List, alert_threshold: float
    ) -> Dict:
        """
        Detect consumption-specific anomaly patterns.

        Detects:
        - Zero variance: rows with std=0 across all periods
        - Range outliers: rows with extreme range-to-mean ratio
        - Mean z-score: rows with mean consumption far from global average
        - Consecutive zeros: rows with 3+ consecutive zero consumption periods
        - Abrupt drops: rows with >50% drop between consecutive periods
        """
        import re

        def period_num(col):
            match = re.match(r"^(\d+)", col)
            return int(match.group(1)) if match else 0

        periods_sorted = sorted(consumption_cols, key=period_num, reverse=True)
        cons_df = df[periods_sorted].copy()
        total = len(df)

        row_means = cons_df.mean(axis=1)
        global_mean = row_means.mean()
        global_std = row_means.std()
        if global_std > 0:
            mean_zscore = (row_means - global_mean) / global_std
        else:
            mean_zscore = pd.Series(0, index=row_means.index)
        mean_zscore_outliers = (mean_zscore.abs() > 3.0).sum()

        row_stds = cons_df.std(axis=1)
        zero_variance_mask = row_stds == 0
        pct_zero_variance = round(float(zero_variance_mask.sum()) / total * 100, 4)

        row_ranges = cons_df.max(axis=1) - cons_df.min(axis=1)
        row_means_safe = row_means.replace(0, np.nan)
        range_to_mean = row_ranges / row_means_safe
        range_outliers = (range_to_mean > 5.0).sum()
        pct_range_outliers = round(float(range_outliers) / total * 100, 4)

        # Consecutive zeros: 3+ consecutive periods with zero consumption
        # Fill NaN with a sentinel value first, then check for exact zeros
        cons_filled = cons_df.fillna(-999)  # sentinel to treat NaN as non-zero
        is_zero = (cons_filled == 0).astype(int).values
        n_cols = is_zero.shape[1]
        max_run = np.zeros(is_zero.shape[0], dtype=int)
        current_run = np.zeros(is_zero.shape[0], dtype=int)
        for j in range(n_cols):
            # Increment run when current value is zero, reset otherwise
            current_run = np.where(is_zero[:, j] == 1, current_run + 1, 0)
            max_run = np.maximum(max_run, current_run)
        consec_zeros_mask = pd.Series(max_run >= 3, index=df.index)
        pct_consec_zeros = round(float(consec_zeros_mask.sum()) / total * 100, 4)

        # Abrupt drops: >50% drop between consecutive periods
        abrupt_drop_mask = pd.Series(False, index=df.index)
        for i in range(len(periods_sorted) - 1):
            curr = cons_df[periods_sorted[i]].fillna(0)
            prev = cons_df[periods_sorted[i + 1]].fillna(0)
            valid = (prev > 0) & (curr >= 0)
            drop_ratio = (prev - curr) / prev
            abrupt_drop_mask |= valid & (drop_ratio > 0.5)
        pct_abrupt_drop = round(float(abrupt_drop_mask.sum()) / total * 100, 4)

        return {
            "pct_zero_variance": pct_zero_variance,
            "pct_range_outliers": pct_range_outliers,
            "mean_zscore_outlier_count": int(mean_zscore_outliers),
            "mean_zscore_outlier_pct": round(float(mean_zscore_outliers) / total * 100, 4),
            "pct_consec_zeros": pct_consec_zeros,
            "pct_abrupt_drop": pct_abrupt_drop,
        }

    def _analyze_populations(self, df: pd.DataFrame, col_types: Dict, population_cfg: Dict) -> Dict:
        """
        Analyze numeric columns for multiple distinct populations.

        Detects significant jumps in the percentile distribution to identify
        multiple populations (e.g., normal, high-value outliers, data errors).

        Args:
            df: DataFrame to analyze
            col_types: Column type classification dict
            population_cfg: Population analysis configuration from YAML

        Returns:
            dict mapping column name to population analysis results
        """
        # Get configuration
        percentile_step = population_cfg.get("percentile_step", 0.5)
        jump_ratio_threshold = population_cfg.get("jump_ratio_threshold", 5.0)
        max_populations = population_cfg.get("max_populations", 5)
        min_population_pct = population_cfg.get("min_population_pct", 0.5)

        # Columns to analyze (consumption + optional additional columns)
        consumption_cols = col_types.get("consumption", [])
        additional_cols = population_cfg.get("additional_columns", [])

        # Dedupe and filter to existing columns
        cols_to_analyze = list(set(consumption_cols + additional_cols))
        cols_to_analyze = [col for col in cols_to_analyze if col in df.columns]

        if not cols_to_analyze:
            logger.info("No columns configured for population analysis")
            return {}

        # Initialize PopulationAnalyzer
        analyzer = PopulationAnalyzer(
            percentile_step=percentile_step,
            jump_ratio_threshold=jump_ratio_threshold,
            max_populations=max_populations,
            min_population_pct=min_population_pct,
        )

        results = {}
        target = df[self.target_column] if self.target_column else None

        for col in cols_to_analyze:
            try:
                col_results = analyzer.analyze(df[col], target=target)

                # Store clean results (remove large internal data structures)
                results[col] = {
                    "populations": col_results.get("populations", []),
                    "jumps": col_results.get("jumps", []),
                    "has_multiple_populations": col_results.get("has_multiple_populations", False),
                }

                # Log summary
                n_pops = len(col_results.get("populations", []))
                if n_pops > 1:
                    logger.info(
                        "Column '%s': %d populations detected (jump_threshold=%.1fx)",
                        col,
                        n_pops,
                        jump_ratio_threshold,
                    )
            except Exception as e:
                logger.warning("Error analyzing populations in column '%s': %s", col, e)

        return results

    def _run_target_explorer(self, df: pd.DataFrame) -> Dict:
        """Phase 3: Run target explorer."""
        explorer = TargetExplorer(config=self._thresholds)
        results = explorer.analyze(df, target_col=self.target_column, date_col=self.date_column)
        self._all_alerts.extend(explorer.get_alerts())
        return results

    def _run_feature_importance(self, df: pd.DataFrame, col_types: Dict) -> Dict:
        """Phase 5: Run feature importance analyzer."""
        methods_cfg = self._full_config.get("sections", {}).get("feature_importance", {})
        methods = methods_cfg.get("methods", ["iv", "ks_chi2", "cramers_v", "correlation"])

        analyzer = FeatureImportanceAnalyzer(config=self._thresholds)
        results = analyzer.analyze(
            df, target_col=self.target_column, col_types=col_types, methods=methods
        )
        self._all_alerts.extend(analyzer.get_alerts())
        return results

    def _generate_charts(
        self,
        df: pd.DataFrame,
        col_types: Dict,
        target_results: Dict,
        importance_results: Dict,
        global_stats: Dict,
        outliers_results: Optional[Dict] = None,
        related_columns_results: Optional[Dict] = None,
        geo_results: Optional[Dict] = None,
    ) -> Dict:
        """Generate all charts (static and interactive)."""
        plots_dir = str(self.output_dir_path / "plots")
        static_plotter = EDAStaticPlots(plots_dir)
        interactive_plotter = EDAInteractivePlots(plots_dir)

        charts = {}

        # Class balance (interactive)
        if target_results:
            try:
                charts["class_balance"] = interactive_plotter.class_balance_chart(
                    target_results.get("class_counts", {}),
                    target_results.get("class_pcts", {}),
                )
            except Exception as e:
                logger.warning("Error generating class balance chart: %s", e)

        # Temporal rate (interactive)
        if target_results and target_results.get("temporal_rate"):
            try:
                charts["temporal_rate"] = interactive_plotter.temporal_line(
                    target_results["temporal_rate"],
                    title="Temporal Evolution of Fraud Rate",
                )
            except Exception as e:
                logger.warning("Error generating temporal chart: %s", e)

        # IV ranking (interactive)
        if importance_results and isinstance(importance_results.get("ranking"), pd.DataFrame):
            try:
                charts["iv_ranking"] = interactive_plotter.iv_ranking_chart(
                    importance_results["ranking"]
                )
            except Exception as e:
                logger.warning("Error generating IV ranking chart: %s", e)

        # Missing funnel (interactive)
        nulls_by_col = global_stats.get("nulls_by_col", [])
        if nulls_by_col:
            try:
                charts["missing_heatmap_interactive"] = interactive_plotter.missing_funnel(
                    nulls_by_col
                )
            except Exception as e:
                logger.warning("Error generating missing values funnel: %s", e)

        # Null correlation heatmap (interactive)
        null_corr = global_stats.get("null_correlation")
        if null_corr is not None and not null_corr.empty:
            try:
                charts["null_correlation"] = interactive_plotter.null_correlation_heatmap(null_corr)
            except Exception as e:
                logger.warning("Error generating null correlation heatmap: %s", e)

        # Consumption charts
        consumption_cols = col_types.get("consumption", [])
        if consumption_cols:
            try:
                charts["consumption_trend"] = interactive_plotter.temporal_line(
                    [
                        {
                            "period": s["period"],
                            "total": 1,
                            "positive": 0,
                            "rate": s.get("mean", 0) or 0,
                        }
                        for s in (self._get_consumption_stats(df, consumption_cols))
                    ],
                    title="Average Consumption Trend by Period",
                )
            except Exception as e:
                logger.warning("Error generating consumption trend (fallback to static): %s", e)
                try:
                    charts["consumption_trend"] = static_plotter.consumption_trend(
                        df, consumption_cols, target_col=self.target_column
                    )
                except Exception as e2:
                    logger.warning("Error generating static consumption chart: %s", e2)

            try:
                charts["consumption_heatmap"] = interactive_plotter.consumption_heatmap(
                    df, consumption_cols
                )
            except Exception as e:
                logger.warning("Error generating consumption heatmap: %s", e)

        # Correlation heatmap (interactive from null correlation, static from numeric)
        numeric_cols = [
            c for c in col_types.get("numeric", []) if c != self.target_column and c in df.columns
        ]
        if len(numeric_cols) > 1:
            try:
                if len(numeric_cols) > 30:
                    logger.warning(
                        "Correlation matrix truncated to 30 columns (out of %d). "
                        "Some correlations may be missed.",
                        len(numeric_cols),
                    )
                numeric_sample = df[numeric_cols[:30]]
                corr_matrix = numeric_sample.corr(numeric_only=True)
                charts["correlation_heatmap"] = interactive_plotter.null_correlation_heatmap(
                    corr_matrix
                )
            except Exception as e:
                logger.warning("Error generating correlation heatmap: %s", e)

        # --- Outlier charts ---
        outlier_cfg = self.sections.get("outliers", {})
        if outliers_results and outlier_cfg.get("detailed_charts", True):
            try:
                methods = outlier_cfg.get("methods", ["iqr"])

                # Collect masks — numeric cols first, then consumption cols
                all_outlier_masks: Dict[str, pd.Series] = {}
                multi_method_masks: Dict[str, Dict[str, pd.Series]] = {}
                for source_key in ("numeric_outliers", "consumption_column_outliers"):
                    for col, method_results in outliers_results.get(source_key, {}).items():
                        if col in df.columns:
                            col_masks = {}
                            for method_name in methods:
                                method_data = method_results.get(method_name, {})
                                if "mask" in method_data:
                                    col_masks[method_name] = method_data["mask"]
                                    if method_name == methods[0]:
                                        all_outlier_masks[col] = method_data["mask"]
                            if col_masks:
                                multi_method_masks[col] = col_masks

                if all_outlier_masks:
                    col_list = list(all_outlier_masks.keys())
                    charts["outlier_boxplots"] = interactive_plotter.plotly_outlier_boxplots(
                        df, col_list, all_outlier_masks
                    )
                    charts["outlier_summary_bar"] = interactive_plotter.plotly_outlier_summary_bar(
                        multi_method_masks
                    )
                    charts["outlier_heatmap"] = interactive_plotter.outlier_heatmap(
                        all_outlier_masks, max_rows=500, max_cols=20
                    )

                # Consumption anomalies scatter chart
                consumption_cols = col_types.get("consumption", [])
                if consumption_cols:
                    import re

                    def period_num(c):
                        m = re.match(r"^(\d+)", c)
                        return int(m.group(1)) if m else 0

                    periods_sorted = sorted(consumption_cols, key=period_num, reverse=True)
                    cons_df = df[periods_sorted].copy()

                    # Detect outlier mask for zero variance rows (potential tampering)
                    consumption_anomalies_data = outliers_results.get("consumption_outliers", {})
                    outlier_mask = None
                    if consumption_anomalies_data.get("pct_zero_variance", 0) > 0:
                        row_stds = cons_df.std(axis=1)
                        outlier_mask = row_stds == 0

                    charts["consumption_anomalies"] = (
                        interactive_plotter.plotly_consumption_anomalies(
                            df,
                            consumption_cols,
                            outlier_mask=outlier_mask,
                            target_col=self.target_column,
                            sample_n=1000,
                            id_col=self.id_column,
                        )
                    )
            except Exception as e:
                logger.warning("Error generating outlier charts: %s", e)

        # --- Column detail charts ---
        max_detail = self._full_config.get("visualization", {}).get("max_detail_columns", 30)
        target_series = (
            df[self.target_column]
            if self.target_column and self.target_column in df.columns
            else None
        )
        column_details: Dict[str, Dict[str, str]] = {}

        # Numeric column details
        num_cfg = self.sections.get("numeric", {})
        if num_cfg.get("detailed_charts", False):
            for col in numeric_cols[:max_detail]:
                col_charts: Dict[str, str] = {}
                try:
                    col_charts["histogram"] = interactive_plotter.histogram_interactive(
                        df[col], col, target_series=target_series
                    )
                except Exception as e:
                    logger.debug("Error generating histogram for '%s': %s", col, e)
                try:
                    col_charts["boxplot"] = interactive_plotter.boxplot_interactive(
                        df[col], col, target_series=target_series
                    )
                except Exception as e:
                    logger.debug("Error generating boxplot for '%s': %s", col, e)
                if col_charts:
                    column_details[col] = col_charts

        # Categorical column details
        cat_cfg = self.sections.get("categorical", {})
        cat_cols = [
            c
            for c in col_types.get("categorical", [])
            if c != self.target_column and c in df.columns
        ]
        if cat_cfg.get("detailed_charts", False):
            for col in cat_cols[:max_detail]:
                col_charts = {}
                try:
                    vc = df[col].value_counts()
                    if len(vc) > 30:
                        try:
                            col_charts["treemap"] = interactive_plotter.categorical_treemap(df, col)
                        except Exception as e:
                            logger.debug("Error generating treemap for '%s': %s", col, e)
                    try:
                        col_charts["bar"] = interactive_plotter.categorical_bar_chart(vc, col)
                    except Exception as e:
                        logger.debug("Error generating bar chart for '%s': %s", col, e)
                except Exception as e:
                    logger.debug("Error computing value_counts for '%s': %s", col, e)
                if target_series is not None:
                    try:
                        col_charts["target_rate"] = interactive_plotter.target_rate_by_category(
                            df, col, self.target_column
                        )
                    except Exception as e:
                        logger.debug("Error generating target rate chart for '%s': %s", col, e)
                if col_charts:
                    column_details[col] = col_charts

        # Temporal column details
        temporal_cols = [c for c in col_types.get("temporal", []) if c in df.columns]
        for col in temporal_cols[:max_detail]:
            col_charts = {}
            try:
                col_charts["temporal_dist"] = interactive_plotter.temporal_distribution_chart(
                    df[col], col
                )
            except Exception as e:
                logger.debug("Error generating temporal chart for '%s': %s", col, e)
            if col_charts:
                column_details[col] = col_charts

        charts["column_details"] = column_details

        # --- Hierarchy charts ---
        hierarchy_charts: Dict[str, Dict[str, str]] = {}
        if related_columns_results:
            for h_name, h_data in related_columns_results.items():
                h_charts: Dict[str, str] = {}
                columns = h_data.get("columns", [])
                if not columns:
                    continue
                try:
                    h_charts["sunburst"] = interactive_plotter.sunburst_hierarchy(
                        df, columns, title=f"Sunburst: {h_name}"
                    )
                except Exception as e:
                    logger.debug("Error generating sunburst for '%s': %s", h_name, e)
                try:
                    h_charts["sankey"] = interactive_plotter.sankey_hierarchy(
                        df, columns, title=f"Flow: {h_name}"
                    )
                except Exception as e:
                    logger.debug("Error generating sankey for '%s': %s", h_name, e)

                target_heatmap = h_data.get("target_heatmap")
                if target_heatmap is not None:
                    try:
                        h_charts["target_heatmap"] = interactive_plotter.hierarchy_target_heatmap(
                            target_heatmap, title=f"Target Rate: {h_name}"
                        )
                    except Exception as e:
                        logger.debug("Error generating target heatmap for '%s': %s", h_name, e)

                hierarchy_charts[h_name] = h_charts
        charts["hierarchies"] = hierarchy_charts

        # --- Geospatial map ---
        geo_cfg = self.sections.get("geospatial", {})
        if (
            geo_cfg.get("enabled", False)
            and geo_results
            and self.lat_column
            and self.lon_column
            and self.lat_column in df.columns
            and self.lon_column in df.columns
        ):
            try:
                color_col = (
                    self.target_column
                    if self.target_column and self.target_column in df.columns
                    else self.zone_column
                )
                charts["scatter_mapbox"] = interactive_plotter.scatter_mapbox(
                    df,
                    lat_col=self.lat_column,
                    lon_col=self.lon_column,
                    color_col=color_col,
                    id_col=self.id_column,
                    clustering=geo_results.get("clustering", {}),
                    title="Geographic Distribution of Clients",
                )
            except Exception as e:
                logger.warning("Error generating scatter mapbox: %s", e)

        return charts

    def _get_consumption_stats(self, df: pd.DataFrame, consumption_cols: List) -> List[Dict]:
        """Helper to get per-period mean stats for the consumption trend chart."""
        stats = []
        for col in consumption_cols:
            mean_val = df[col].mean()
            stats.append({"period": col, "mean": float(mean_val) if not pd.isna(mean_val) else 0.0})
        return stats

    def _generate_report(self, results: Dict) -> str:
        """Generate HTML report."""
        generator = EDAReportGenerator(self.output_dir)
        return generator.generate(results, self._all_alerts)

    def _add_alert(
        self, code: str, message: str, severity: str = "WARNING", details: Optional[Dict] = None
    ) -> None:
        """Add an alert to the global list."""
        self._all_alerts.append(
            {"code": code, "message": message, "severity": severity, "details": details or {}}
        )

    def _run_geo_analyzer(self, df: pd.DataFrame) -> Dict:
        """Phase 4: Run geospatial analyzer."""
        cfg = self.sections.get("geospatial", {})
        geo_thresholds = {
            "invalid_coord_threshold": cfg.get("invalid_coord_threshold", 0.2),
            "country_bounds": cfg.get("country_bounds"),
            "n_clusters": cfg.get("clustering", {}).get("n_clusters", 10),
        }
        analyzer = GeospatialAnalyzer(config=geo_thresholds)
        results = analyzer.analyze(
            df,
            target_col=self.target_column,
            lat_col=self.lat_column,
            lon_col=self.lon_column,
            zone_col=self.zone_column,
        )
        self._all_alerts.extend(analyzer.get_alerts())
        return results

    def _run_related_columns_analyzer(self, df: pd.DataFrame, hierarchies: List[Dict]) -> Dict:
        """Phase 7: Run related columns analyzer."""
        rc_cfg = self.sections.get("related_columns", {})
        rc_thresholds = {
            "sparse_combination_threshold": rc_cfg.get("sparse_combination_threshold", 10),
            "dominant_path_threshold": rc_cfg.get("dominant_path_threshold", 0.8),
            "target_disparity_zscore": rc_cfg.get("target_disparity_zscore", 2.0),
        }
        analyzer = RelatedColumnsAnalyzer(config=rc_thresholds)
        results = analyzer.analyze(
            df,
            target_col=self.target_column,
            hierarchies=hierarchies,
        )
        self._all_alerts.extend(analyzer.get_alerts())
        return results

    def _run_segmentation_analyzer(self, df: pd.DataFrame) -> Dict:
        """Phase 6: Run segmentation analyzer."""
        cfg = self.sections.get("segmentation", {})
        seg_thresholds = {
            "min_segment_size": cfg.get("min_segment_size", 100),
            "segment_drift_threshold": cfg.get("segment_drift_threshold", 3.0),
        }

        segment_cols = cfg.get("segment_cols", [])
        if not segment_cols:
            # Auto-detect potential segment columns (categorical with moderate cardinality)
            col_types = classify_columns(df, periods_suffix=self.periods_suffix)
            candidate_cols = col_types.get("categorical", [])
            for col in candidate_cols:
                if col == self.target_column:
                    continue
                n_unique = df[col].nunique()
                if 2 < n_unique < 50:  # Reasonable for segmentation
                    segment_cols.append(col)

        if not segment_cols:
            logger.debug("No segment columns found for segmentation analysis")
            return {}

        analyzer = SegmentationAnalyzer(config=seg_thresholds)
        results = analyzer.analyze(
            df,
            target_col=self.target_column,
            segment_cols=segment_cols,
        )
        self._all_alerts.extend(analyzer.get_alerts())
        return results
