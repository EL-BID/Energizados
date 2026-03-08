"""
Dataset Explorer - Energizados EDA Framework.

Main orchestrator class that runs all EDA phases and generates the HTML report.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from energizados.eda.column_explorer import ColumnExplorer
from energizados.eda.feature_importance import FeatureImportanceAnalyzer
from energizados.eda.geo_analyzer import GeospatialAnalyzer
from energizados.eda.inspection_analyzer import InspectionAnalyzer
from energizados.eda.join_analyzer import JoinAnalyzer
from energizados.eda.loading_validator import LoadingValidator
from energizados.eda.plots import EDAStaticPlots
from energizados.eda.plots_interactive import EDAInteractivePlots
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
        logger.info("INICIO - Análisis Exploratorio de Datos (EDA)")
        logger.info("=" * 60)
        logger.info("Archivo: %s", self.input_path)

        # --- Load dataset ---
        df = self._load_dataset()
        if df is None:
            raise RuntimeError(f"No se pudo cargar el dataset: {self.input_path}")

        logger.info("Dataset cargado: %d filas × %d columnas", len(df), len(df.columns))

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
            "Tipos detectados: %d numérico, %d categórico, %d temporal, %d consumo",
            len(col_types["numeric"]),
            len(col_types["categorical"]),
            len(col_types["temporal"]),
            len(col_types["consumption"]),
        )

        # --- Phase 0: Loading validator ---
        logger.info("Fase 0: Validación de carga...")
        loading_results = self._run_loading_validator(df)

        # --- Phase 1: Global dataset stats ---
        logger.info("Fase 1: Estadísticas globales...")
        global_stats = self._compute_global_stats(df)

        # --- Phase 2: Column explorer ---
        logger.info("Fase 2: Análisis de columnas...")
        columns_results = self._run_column_explorer(df, col_types)

        # --- Phase 3: Target explorer ---
        target_results = {}
        if self.target_column and self.target_column in df.columns:
            logger.info("Fase 3: Análisis de variable objetivo '%s'...", self.target_column)
            target_results = self._run_target_explorer(df)

        # --- Phase 7: Feature importance ---
        importance_results = {}
        if self.target_column and self.target_column in df.columns:
            logger.info("Fase 7: Análisis de importancia de variables...")
            importance_results = self._run_feature_importance(df, col_types)

        # --- Phase 4: Inspections analyzer (optional) ---
        inspections_results = {}
        inspections_cfg = self.sections.get("inspections", {})
        if inspections_cfg.get("enabled", False):
            logger.info("Fase 4: Análisis de inspecciones...")
            inspections_results = self._run_inspections_analyzer(df)

        # --- Phase 5: Geospatial analyzer (optional) ---
        geo_results = {}
        geo_cfg = self.sections.get("geospatial", {})
        if geo_cfg.get("enabled", False) and (self.lat_column or self.lon_column or self.zone_column):
            logger.info("Fase 5: Análisis geoespacial...")
            geo_results = self._run_geo_analyzer(df)

        # --- Phase 6: Join analyzer (optional) ---
        join_results = {}
        join_cfg = self.sections.get("joins", {})
        if join_cfg.get("enabled", False):
            logger.info("Fase 6: Análisis de joins multi-fuente...")
            join_results = self._run_join_analyzer(df)

        # --- Phase 8: Segmentation analyzer (optional) ---
        segmentation_results = {}
        seg_cfg = self.sections.get("segmentation", {})
        if seg_cfg.get("enabled", False) and self.target_column and self.target_column in df.columns:
            logger.info("Fase 8: Análisis de segmentación...")
            segmentation_results = self._run_segmentation_analyzer(df)

        # --- Generate charts ---
        logger.info("Generando gráficos...")
        charts = self._generate_charts(df, col_types, target_results, importance_results, global_stats)

        # --- Generate report ---
        logger.info("Generando reporte HTML...")
        results = {
            "loading": loading_results,
            "global_stats": global_stats,
            "columns": columns_results,
            "target": target_results,
            "importance": importance_results,
            "inspections": inspections_results,
            "geo": geo_results,
            "joins": join_results,
            "segmentation": segmentation_results,
            "col_types": col_types,
            "alerts": self._all_alerts,
            "charts": charts,
        }

        report_path = self._generate_report(results)
        results["report_path"] = report_path

        logger.info("=" * 60)
        logger.info("EDA completado. Reporte: %s", report_path)
        logger.info("Total alertas: %d", len(self._all_alerts))
        logger.info("=" * 60)

        return results

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _load_dataset(self) -> Optional[pd.DataFrame]:
        """Load the dataset from parquet or CSV."""
        path = Path(self.input_path)

        loading_cfg = self._full_config.get("loading", {})
        encoding = loading_cfg.get("file_encoding", "utf-8")
        decimal = loading_cfg.get("decimal_separator", ".")

        try:
            if path.suffix.lower() == ".parquet":
                logger.info("Cargando parquet...")
                return pd.read_parquet(str(path))
            elif path.suffix.lower() in (".csv", ".tsv"):
                logger.info("Cargando CSV con encoding='%s', decimal='%s'...", encoding, decimal)
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
            logger.error("Archivo no encontrado: %s", self.input_path)
            return None
        except Exception as e:
            logger.error("Error cargando dataset: %s", e)
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
                    message=f"La columna '{d['col']}' tiene {d['null_pct']:.1f}% de valores nulos (umbral: {missing_threshold*100:.0f}%).",
                    severity="WARNING",
                    details={"col": d["col"], "null_pct": d["null_pct"]},
                )

        for col in fully_null_cols:
            self._add_alert(
                code="ALL_MISSING",
                message=f"La columna '{col}' está completamente vacía (100% nulos). Considere eliminarla.",
                severity="ERROR",
                details={"col": col},
            )

        for col in constant_cols:
            self._add_alert(
                code="CONSTANT",
                message=f"La columna '{col}' tiene un único valor (varianza = 0). No aporta información predictiva.",
                severity="WARNING",
                details={"col": col},
            )

        if duplicate_rows_pct > 1:
            self._add_alert(
                code="DUPLICATED_ROWS",
                message=f"Se encontraron {duplicate_rows:,} filas duplicadas ({duplicate_rows_pct:.2f}%). Verifique si es esperado.",
                severity="WARNING",
                details={"duplicate_rows": duplicate_rows, "duplicate_rows_pct": duplicate_rows_pct},
            )

        return stats

    def _run_column_explorer(self, df: pd.DataFrame, col_types: Dict) -> Dict:
        """Phase 2: Run column explorer."""
        explorer = ColumnExplorer(config=self._thresholds)
        results = explorer.analyze(df, target_col=self.target_column, col_types=col_types, config=self._thresholds)
        self._all_alerts.extend(explorer.get_alerts())
        return results

    def _run_target_explorer(self, df: pd.DataFrame) -> Dict:
        """Phase 3: Run target explorer."""
        explorer = TargetExplorer(config=self._thresholds)
        results = explorer.analyze(df, target_col=self.target_column, date_col=self.date_column)
        self._all_alerts.extend(explorer.get_alerts())
        return results

    def _run_feature_importance(self, df: pd.DataFrame, col_types: Dict) -> Dict:
        """Phase 7: Run feature importance analyzer."""
        methods_cfg = self._full_config.get("sections", {}).get("feature_importance", {})
        methods = methods_cfg.get("methods", ["iv", "ks_chi2", "cramers_v", "correlation"])

        analyzer = FeatureImportanceAnalyzer(config=self._thresholds)
        results = analyzer.analyze(df, target_col=self.target_column, col_types=col_types, methods=methods)
        self._all_alerts.extend(analyzer.get_alerts())
        return results

    def _generate_charts(
        self,
        df: pd.DataFrame,
        col_types: Dict,
        target_results: Dict,
        importance_results: Dict,
        global_stats: Dict,
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
                logger.warning("Error generando gráfico de balance de clases: %s", e)

        # Temporal rate (interactive)
        if target_results and target_results.get("temporal_rate"):
            try:
                charts["temporal_rate"] = interactive_plotter.temporal_line(
                    target_results["temporal_rate"],
                    title="Evolución Temporal de la Tasa de Fraude",
                )
            except Exception as e:
                logger.warning("Error generando gráfico temporal: %s", e)

        # IV ranking (interactive)
        if importance_results and isinstance(importance_results.get("ranking"), pd.DataFrame):
            try:
                charts["iv_ranking"] = interactive_plotter.iv_ranking_chart(importance_results["ranking"])
            except Exception as e:
                logger.warning("Error generando gráfico IV ranking: %s", e)

        # Missing funnel (interactive)
        nulls_by_col = global_stats.get("nulls_by_col", [])
        if nulls_by_col:
            try:
                charts["missing_heatmap_interactive"] = interactive_plotter.missing_funnel(nulls_by_col)
            except Exception as e:
                logger.warning("Error generando funnel de nulos: %s", e)

        # Null correlation heatmap (interactive)
        null_corr = global_stats.get("null_correlation")
        if null_corr is not None and not null_corr.empty:
            try:
                charts["null_correlation"] = interactive_plotter.null_correlation_heatmap(null_corr)
            except Exception as e:
                logger.warning("Error generando correlación de nulos: %s", e)

        # Consumption charts
        consumption_cols = col_types.get("consumption", [])
        if consumption_cols:
            try:
                charts["consumption_trend"] = interactive_plotter.temporal_line(
                    [
                        {"period": s["period"], "total": 1, "positive": 0, "rate": s.get("mean", 0) or 0}
                        for s in (self._get_consumption_stats(df, consumption_cols))
                    ],
                    title="Tendencia de Consumo Promedio por Período",
                )
            except Exception as e:
                logger.warning("Error generando tendencia de consumo (fallback a static): %s", e)
                try:
                    charts["consumption_trend"] = static_plotter.consumption_trend(df, consumption_cols, target_col=self.target_column)
                except Exception as e2:
                    logger.warning("Error generando gráfico estático de consumo: %s", e2)

            try:
                charts["consumption_heatmap"] = interactive_plotter.consumption_heatmap(df, consumption_cols)
            except Exception as e:
                logger.warning("Error generando heatmap de consumo: %s", e)

        # Correlation heatmap (interactive from null correlation, static from numeric)
        numeric_cols = [c for c in col_types.get("numeric", []) if c != self.target_column and c in df.columns]
        if len(numeric_cols) > 1:
            try:
                numeric_sample = df[numeric_cols[:30]]
                corr_matrix = numeric_sample.corr(numeric_only=True)
                charts["correlation_heatmap"] = interactive_plotter.null_correlation_heatmap(corr_matrix)
            except Exception as e:
                logger.warning("Error generando heatmap de correlación: %s", e)

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

    def _add_alert(self, code: str, message: str, severity: str = "WARNING", details: Optional[Dict] = None) -> None:
        """Add an alert to the global list."""
        self._all_alerts.append({"code": code, "message": message, "severity": severity, "details": details or {}})

    def _run_inspections_analyzer(self, df: pd.DataFrame) -> Dict:
        """Phase 4: Run inspections analyzer."""
        cfg = self.sections.get("inspections", {})
        data_sources = self._full_config.get("data_sources", {})
        inspections_cfg = data_sources.get("inspections", {})

        # Try to load inspections data if path is provided
        inspections_path = inspections_cfg.get("path")
        if inspections_path and Path(inspections_path).exists():
            try:
                insp_df = pd.read_csv(inspections_path)
                analyzer = InspectionAnalyzer(config=self._thresholds)
                results = analyzer.analyze(
                    insp_df,
                    tipo_col=inspections_cfg.get("tipo_col"),
                    acao_col=inspections_cfg.get("acao_col"),
                    categoria_col=inspections_cfg.get("categoria_col"),
                    date_col=inspections_cfg.get("date_col"),
                    id_col=inspections_cfg.get("id_col"),
                )
                self._all_alerts.extend(analyzer.get_alerts())
                return results
            except Exception as e:
                logger.warning("Error loading/analyzing inspections data: %s", e)

        # Otherwise, look for inspection columns in main dataset
        tipo_col = cfg.get("tipo_col")
        acao_col = cfg.get("acao_col")
        categoria_col = cfg.get("categoria_col")

        if any([tipo_col and tipo_col in df.columns, acao_col and acao_col in df.columns, categoria_col and categoria_col in df.columns]):
            analyzer = InspectionAnalyzer(config=self._thresholds)
            results = analyzer.analyze(
                df,
                tipo_col=tipo_col,
                acao_col=acao_col,
                categoria_col=categoria_col,
                date_col=self.date_column,
                id_col=self.id_column,
            )
            self._all_alerts.extend(analyzer.get_alerts())
            return results

        return {}

    def _run_geo_analyzer(self, df: pd.DataFrame) -> Dict:
        """Phase 5: Run geospatial analyzer."""
        cfg = self.sections.get("geospatial", {})
        geo_thresholds = {
            "invalid_coord_threshold": cfg.get("invalid_coord_threshold", 0.2),
            "country_bounds": cfg.get("country_bounds"),
            "n_clusters": cfg.get("n_clusters", 10),
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

    def _run_join_analyzer(self, df: pd.DataFrame) -> Dict:
        """Phase 6: Run join analyzer."""
        cfg = self.sections.get("joins", {})
        join_thresholds = {
            "max_acceptable_loss": cfg.get("max_acceptable_loss", 0.3),
            "profile_columns": cfg.get("profile_columns", []),
        }

        # Build source indicators from config
        source_indicators = cfg.get("source_indicators", {})
        if not source_indicators:
            # Try to auto-detect from data_sources config
            data_sources = self._full_config.get("data_sources", {})
            for source_name, source_cfg in data_sources.items():
                if source_name == "primary":
                    continue
                # Look for indicator columns like {source}_present or similar
                for col in df.columns:
                    if f"{source_name}_present" in col.lower() or f"{source_name}_not_null" in col.lower():
                        source_indicators[source_name] = col
                        break

        if not source_indicators:
            logger.debug("No source indicators found for join analysis")
            return {}

        analyzer = JoinAnalyzer(config=join_thresholds)
        results = analyzer.analyze(
            df,
            target_col=self.target_column,
            id_col=self.id_column,
            source_indicators=source_indicators,
        )
        self._all_alerts.extend(analyzer.get_alerts())
        return results

    def _run_segmentation_analyzer(self, df: pd.DataFrame) -> Dict:
        """Phase 8: Run segmentation analyzer."""
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
