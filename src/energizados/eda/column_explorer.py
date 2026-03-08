"""
Column Explorer Module - Energizados EDA Framework.

Phase 2: Per-column analysis for numeric, categorical, temporal and consumption columns.
"""

import logging
import math
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from energizados.eda.base import BaseExplorer
from energizados.eda.utils import compute_iv_woe, cramers_v, ks_statistic

logger = logging.getLogger(__name__)


class ColumnExplorer(BaseExplorer):
    """
    Analyzes each column in a DataFrame, adapted to its type.

    Computes summary statistics, quality indicators and predictive power
    (IV, KS, Cramér's V) for each column.

    Args:
        config: Configuration dictionary with thresholds:
            - cardinality_high: int (default 100) - alert threshold for high cardinality
            - cardinality_low: int (default 10) - alert threshold for low cardinality numeric
            - correlation_threshold: float (default 0.95) - alert threshold for high correlation

    Example:
        >>> explorer = ColumnExplorer()
        >>> results = explorer.analyze(df, target_col='target', col_types=col_types)
    """

    def analyze(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        col_types: Optional[Dict] = None,
        config: Optional[Dict] = None,
        **kwargs,
    ) -> Dict:
        """
        Analyze all columns in the DataFrame.

        Args:
            df: Input DataFrame
            target_col: Name of binary target column (optional)
            col_types: Column classification dict from utils.classify_columns()
            config: Configuration overrides (optional)
            **kwargs: Additional arguments (ignored)

        Returns:
            dict with keys: numeric, categorical, temporal, consumption
            Each key contains list of per-column analysis dicts.
        """
        self.alerts = []
        cfg = config or self.config

        cardinality_high = cfg.get("cardinality_high", 100)
        cardinality_low = cfg.get("cardinality_low", 10)
        correlation_threshold = cfg.get("correlation_threshold", 0.95)

        col_types = col_types or {}

        numeric_cols = col_types.get("numeric", []) + col_types.get("target_candidates", [])
        categorical_cols = col_types.get("categorical", [])
        temporal_cols = col_types.get("temporal", [])
        consumption_cols = col_types.get("consumption", [])

        results = {
            "numeric": [],
            "categorical": [],
            "temporal": [],
            "consumption": {},
        }

        # --- Numeric columns ---
        for col in numeric_cols:
            if col not in df.columns or col == target_col:
                continue
            try:
                analysis = self._analyze_numeric(df, col, target_col)
                results["numeric"].append(analysis)

                if analysis["unique_count"] < cardinality_low and analysis["unique_count"] > 1:
                    self._add_alert(
                        code="LOW_CARDINALITY_NUMERIC",
                        message=(
                            f"La columna numérica '{col}' tiene solo {analysis['unique_count']} "
                            "valores únicos. Considere tratarla como categórica."
                        ),
                        severity="INFO",
                        details={"col": col, "unique_count": analysis["unique_count"]},
                    )
            except Exception as e:
                logger.warning("Error analyzing numeric column '%s': %s", col, e)

        # --- Categorical columns ---
        for col in categorical_cols:
            if col not in df.columns or col == target_col:
                continue
            try:
                analysis = self._analyze_categorical(df, col, target_col)
                results["categorical"].append(analysis)

                if analysis["unique_count"] > cardinality_high:
                    self._add_alert(
                        code="HIGH_CARDINALITY",
                        message=(
                            f"La columna categórica '{col}' tiene {analysis['unique_count']} "
                            f"categorías únicas (umbral: {cardinality_high}). "
                            "Considere reducción de cardinalidad."
                        ),
                        severity="WARNING",
                        details={"col": col, "unique_count": analysis["unique_count"]},
                    )
            except Exception as e:
                logger.warning("Error analyzing categorical column '%s': %s", col, e)

        # --- Temporal columns ---
        for col in temporal_cols:
            if col not in df.columns:
                continue
            try:
                analysis = self._analyze_temporal(df, col)
                results["temporal"].append(analysis)
            except Exception as e:
                logger.warning("Error analyzing temporal column '%s': %s", col, e)

        # --- Consumption columns ---
        if consumption_cols:
            try:
                results["consumption"] = self._analyze_consumption(df, consumption_cols, target_col)

                neg_pct = results["consumption"].get("pct_negative", 0)
                if neg_pct > 0:
                    self._add_alert(
                        code="NEGATIVE_CONSUMPTION",
                        message=f"Se detectaron valores negativos de consumo en {neg_pct:.1f}% de las filas. Verifique el proceso de ETL.",
                        severity="WARNING",
                        details={"pct_negative": neg_pct},
                    )
            except Exception as e:
                logger.warning("Error analyzing consumption columns: %s", e)

        # --- Highly correlated numeric columns ---
        try:
            numeric_df = df[[c for c in numeric_cols if c in df.columns and c != target_col]]
            if len(numeric_df.columns) > 1:
                corr_matrix = numeric_df.corr(numeric_only=True).abs()
                upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
                highly_corr = [
                    (c1, c2, round(float(corr_matrix.loc[c1, c2]), 4))
                    for c1 in upper_tri.columns
                    for c2 in upper_tri.columns
                    if c1 != c2 and not pd.isna(upper_tri.loc[c1, c2]) and upper_tri.loc[c1, c2] > correlation_threshold
                ]
                if highly_corr:
                    self._add_alert(
                        code="HIGHLY_CORRELATED",
                        message=(
                            f"Se encontraron {len(highly_corr)} par(es) de variables numéricas "
                            f"con correlación > {correlation_threshold}. "
                            "Considere eliminar redundancias."
                        ),
                        severity="WARNING",
                        details={"pairs": highly_corr[:10]},
                    )
        except Exception as e:
            logger.debug("Error computing correlation matrix: %s", e)

        self.results = results
        return results

    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis."""
        return self.alerts

    def _analyze_numeric(self, df: pd.DataFrame, col: str, target_col: Optional[str]) -> Dict:
        """Compute statistics for a numeric column."""
        series = df[col].dropna()
        total = len(df)
        null_count = int(df[col].isna().sum())
        count = len(series)

        if count == 0:
            return {
                "col": col,
                "count": 0,
                "null_count": total,
                "null_pct": 100.0,
                "mean": None,
                "std": None,
                "min": None,
                "max": None,
                "p1": None,
                "p5": None,
                "p25": None,
                "p50": None,
                "p75": None,
                "p95": None,
                "p99": None,
                "skewness": None,
                "kurtosis": None,
                "zero_count": 0,
                "zero_pct": 0.0,
                "unique_count": 0,
                "outlier_count": 0,
                "outlier_pct": 0.0,
                "negative_count": 0,
                "negative_pct": 0.0,
                "cv": None,
            }

        vals = series.values.astype(float)
        mean_val = float(np.mean(vals))
        std_val = float(np.std(vals))

        q1 = float(np.percentile(vals, 25))
        q3 = float(np.percentile(vals, 75))
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr
        outlier_mask = (vals < lower_fence) | (vals > upper_fence)
        outlier_count = int(outlier_mask.sum())

        zero_count = int((vals == 0).sum())
        negative_count = int((vals < 0).sum())

        # Coefficient of variation
        cv = (std_val / mean_val) if mean_val != 0 else None

        analysis = {
            "col": col,
            "count": count,
            "null_count": null_count,
            "null_pct": round(null_count / total * 100, 4) if total > 0 else 0.0,
            "mean": round(mean_val, 6),
            "std": round(std_val, 6),
            "min": float(np.min(vals)),
            "max": float(np.max(vals)),
            "p1": float(np.percentile(vals, 1)),
            "p5": float(np.percentile(vals, 5)),
            "p25": float(q1),
            "p50": float(np.percentile(vals, 50)),
            "p75": float(q3),
            "p95": float(np.percentile(vals, 95)),
            "p99": float(np.percentile(vals, 99)),
            "skewness": round(float(series.skew()), 6),
            "kurtosis": round(float(series.kurtosis()), 6),
            "zero_count": zero_count,
            "zero_pct": round(zero_count / count * 100, 4),
            "unique_count": int(series.nunique()),
            "outlier_count": outlier_count,
            "outlier_pct": round(outlier_count / count * 100, 4),
            "negative_count": negative_count,
            "negative_pct": round(negative_count / count * 100, 4),
            "cv": round(cv, 6) if cv is not None else None,
        }

        # Predictive power metrics (only if target_col provided)
        if target_col and target_col in df.columns:
            try:
                iv_result = compute_iv_woe(df, col, target_col, bins=10, is_categorical=False)
                analysis["iv"] = round(iv_result["iv"], 6)
            except Exception as e:
                logger.debug("IV computation failed for '%s': %s", col, e)
                analysis["iv"] = None

            try:
                ks_stat, ks_pval = ks_statistic(df, col, target_col)
                analysis["ks_stat"] = round(ks_stat, 6)
                analysis["ks_pval"] = round(ks_pval, 6)
            except Exception as e:
                logger.debug("KS computation failed for '%s': %s", col, e)
                analysis["ks_stat"] = None
                analysis["ks_pval"] = None

        return analysis

    def _analyze_categorical(self, df: pd.DataFrame, col: str, target_col: Optional[str]) -> Dict:
        """Compute statistics for a categorical column."""
        series = df[col]
        total = len(df)
        null_count = int(series.isna().sum())
        count = total - null_count
        non_null = series.dropna()

        value_counts = non_null.value_counts()
        unique_count = len(value_counts)
        mode_value = str(value_counts.index[0]) if unique_count > 0 else None
        mode_pct = round(float(value_counts.iloc[0]) / count * 100, 4) if count > 0 else 0.0

        # Top 20 categories
        top_cats = [
            {
                "value": str(val),
                "count": int(cnt),
                "pct": round(cnt / count * 100, 4) if count > 0 else 0.0,
            }
            for val, cnt in value_counts.head(20).items()
        ]

        # Rare categories (freq < 1%)
        rare_mask = (value_counts / count) < 0.01 if count > 0 else pd.Series([], dtype=bool)
        rare_pct = round(float(rare_mask.sum()) / unique_count * 100, 4) if unique_count > 0 else 0.0

        # Singleton categories (appear only once)
        singleton_count = int((value_counts == 1).sum())

        # Shannon entropy
        probs = value_counts / count if count > 0 else value_counts
        entropy = float(-sum(p * math.log2(p) for p in probs if p > 0)) if len(probs) > 0 else 0.0

        analysis = {
            "col": col,
            "count": count,
            "null_count": null_count,
            "null_pct": round(null_count / total * 100, 4) if total > 0 else 0.0,
            "unique_count": unique_count,
            "top_categories": top_cats,
            "rare_pct": rare_pct,
            "mode_value": mode_value,
            "mode_pct": mode_pct,
            "entropy": round(entropy, 6),
            "singleton_count": singleton_count,
        }

        # Predictive power metrics
        if target_col and target_col in df.columns:
            try:
                iv_result = compute_iv_woe(df, col, target_col, bins=10, is_categorical=True)
                analysis["iv"] = round(iv_result["iv"], 6)
            except Exception as e:
                logger.debug("IV computation failed for '%s': %s", col, e)
                analysis["iv"] = None

            try:
                cv_val = cramers_v(df, col, target_col)
                analysis["cramers_v"] = round(cv_val, 6)
            except Exception as e:
                logger.debug("Cramér's V computation failed for '%s': %s", col, e)
                analysis["cramers_v"] = None

        return analysis

    def _analyze_temporal(self, df: pd.DataFrame, col: str) -> Dict:
        """Compute statistics for a temporal/date column."""
        series = df[col]
        total = len(df)
        null_count = int(series.isna().sum())
        count = total - null_count

        # Try to convert to datetime if not already
        try:
            if not pd.api.types.is_datetime64_any_dtype(series):
                series = pd.to_datetime(series, errors="coerce")
                null_count = int(series.isna().sum())
                count = total - null_count
        except Exception:  # nosec B110
            pass

        non_null = series.dropna()

        if len(non_null) == 0:
            return {
                "col": col,
                "count": 0,
                "null_count": null_count,
                "null_pct": round(null_count / total * 100, 4) if total > 0 else 0.0,
                "min_date": None,
                "max_date": None,
                "span_days": None,
                "granularity": "unknown",
                "dist_by_year": {},
                "dist_by_month": {},
                "dist_by_weekday": {},
            }

        min_date = non_null.min()
        max_date = non_null.max()
        span_days = (max_date - min_date).days

        # Detect granularity
        granularity = self._detect_granularity(non_null)

        # Distributions
        dist_by_year = non_null.dt.year.value_counts().sort_index().to_dict()
        dist_by_year = {int(k): int(v) for k, v in dist_by_year.items()}

        dist_by_month = non_null.dt.month.value_counts().sort_index().to_dict()
        dist_by_month = {int(k): int(v) for k, v in dist_by_month.items()}

        weekday_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        dist_by_weekday_num = non_null.dt.dayofweek.value_counts().sort_index().to_dict()
        dist_by_weekday = {weekday_names[k]: int(v) for k, v in dist_by_weekday_num.items() if 0 <= k <= 6}

        return {
            "col": col,
            "count": count,
            "null_count": null_count,
            "null_pct": round(null_count / total * 100, 4) if total > 0 else 0.0,
            "min_date": str(min_date.date()) if hasattr(min_date, "date") else str(min_date),
            "max_date": str(max_date.date()) if hasattr(max_date, "date") else str(max_date),
            "span_days": span_days,
            "granularity": granularity,
            "dist_by_year": dist_by_year,
            "dist_by_month": dist_by_month,
            "dist_by_weekday": dist_by_weekday,
        }

    def _detect_granularity(self, series: pd.Series) -> str:
        """Heuristically detect temporal granularity of a datetime series."""
        try:
            unique_days = series.dt.day.nunique()
            unique_months = series.dt.month.nunique()
            unique_years = series.dt.year.nunique()

            if unique_days > 20:
                return "daily"
            elif unique_months > 2:
                return "monthly"
            elif unique_years > 1:
                return "yearly"
            else:
                return "unknown"
        except Exception:
            return "unknown"

    def _analyze_consumption(self, df: pd.DataFrame, consumption_cols: List[str], target_col: Optional[str]) -> Dict:
        """Analyze wide-format consumption columns (N_anterior pattern)."""
        # Sort columns from oldest (highest N) to newest (lowest N)
        import re

        def period_num(col):
            match = re.match(r"^(\d+)", col)
            return int(match.group(1)) if match else 0

        periods_sorted = sorted(consumption_cols, key=period_num, reverse=True)

        cons_df = df[periods_sorted].copy()

        # Per-period stats
        stats_by_period = []
        for col in periods_sorted:
            series = cons_df[col]
            non_null = series.dropna()
            n = len(non_null)
            stats_by_period.append(
                {
                    "period": col,
                    "mean": round(float(non_null.mean()), 4) if n > 0 else None,
                    "std": round(float(non_null.std()), 4) if n > 0 else None,
                    "min": round(float(non_null.min()), 4) if n > 0 else None,
                    "max": round(float(non_null.max()), 4) if n > 0 else None,
                    "zeros_pct": round(float((non_null == 0).sum()) / n * 100, 4) if n > 0 else 0.0,
                    "nulls_pct": round(float(series.isna().sum()) / len(df) * 100, 4),
                }
            )

        total_rows = len(df)

        # Row-level aggregations
        has_any_zero = (cons_df == 0).any(axis=1)
        all_zero = (cons_df == 0).all(axis=1)
        pct_rows_with_any_zero = round(float(has_any_zero.sum()) / total_rows * 100, 4)
        pct_rows_all_zero = round(float(all_zero.sum()) / total_rows * 100, 4)

        # Negative values
        has_negative = (cons_df < 0).any(axis=1)
        pct_negative = round(float(has_negative.sum()) / total_rows * 100, 4)

        # Constant rows (same value across all periods)
        if len(periods_sorted) > 1:
            constant_mask = cons_df.nunique(axis=1) == 1
            pct_constant = round(float(constant_mask.sum()) / total_rows * 100, 4)
        else:
            pct_constant = 0.0

        # Abrupt drop: >50% drop between any consecutive periods
        pct_abrupt_drop = 0.0
        if len(periods_sorted) > 1:
            abrupt_drop_mask = pd.Series(False, index=df.index)
            for i in range(len(periods_sorted) - 1):
                col_new = periods_sorted[i + 1]  # newer = lower N
                col_old = periods_sorted[i]  # older = higher N
                old_vals = cons_df[col_old]
                new_vals = cons_df[col_new]
                # Only check where old > 0 to avoid division by zero
                valid = old_vals > 0
                drop_ratio = (old_vals - new_vals) / old_vals
                abrupt_drop_mask |= valid & (drop_ratio > 0.5)
            pct_abrupt_drop = round(float(abrupt_drop_mask.sum()) / total_rows * 100, 4)

        # Trend slope: linear regression of period means
        period_means = [s["mean"] for s in stats_by_period if s["mean"] is not None]
        trend_slope = 0.0
        if len(period_means) > 1:
            x = np.arange(len(period_means), dtype=float)
            y = np.array(period_means, dtype=float)
            if not np.isnan(y).any():
                coeffs = np.polyfit(x, y, 1)
                trend_slope = round(float(coeffs[0]), 6)

        return {
            "periods": periods_sorted,
            "stats_by_period": stats_by_period,
            "pct_rows_with_any_zero": pct_rows_with_any_zero,
            "pct_rows_all_zero": pct_rows_all_zero,
            "pct_negative": pct_negative,
            "pct_constant": pct_constant,
            "pct_abrupt_drop": pct_abrupt_drop,
            "trend_slope": trend_slope,
        }
