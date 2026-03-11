"""
Segmentation Analyzer Module - Energizados EDA Framework.

Phase 8: Analyzes subpopulations to detect segments with different behavior.
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

from energizados.eda.base import BaseExplorer

logger = logging.getLogger(__name__)


class SegmentationAnalyzer(BaseExplorer):
    """
    Analyzes subpopulations for different fraud behavior.

    Identifies segments (by categorical columns) that have significantly
    different target rates, which may justify separate models or special
    handling.

    Args:
        config: Configuration dictionary with thresholds:
            - min_segment_size: int (default 100) - alert if segment < 100 records
            - segment_drift_threshold: float (default 3.0) - sigma threshold for drift alert

    Example:
        >>> analyzer = SegmentationAnalyzer()
        >>> results = analyzer.analyze(
        ...     df,
        ...     target_col="target",
        ...     segment_cols=["TIPO_CLIENTE", "TIPO_TARIFA", "ZONA"]
        ... )
    """

    def analyze(
        self,
        df: pd.DataFrame,
        target_col: str,
        segment_cols: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict:
        """
        Analyze subpopulations by categorical segments.

        Args:
            df: Input DataFrame
            target_col: Binary target column name (required)
            segment_cols: List of categorical columns to segment by
            **kwargs: Additional arguments (ignored)

        Returns:
            dict with keys:
                - segment_stats: list of per-segment statistics
                - cross_analysis: dict of multi-dimensional segment crosses
                - alerts: list of segment-related warnings
        """
        self.alerts = []

        if not target_col or target_col not in df.columns:
            logger.warning("target_col '%s' not found, skipping segmentation analysis", target_col)
            self.results = {}
            return {}

        if not segment_cols:
            segment_cols = self.config.get("segment_cols", [])

        # Filter to available segment columns
        available_segments = [c for c in segment_cols if c in df.columns]

        if not available_segments:
            logger.warning("No valid segment columns found, skipping analysis")
            self.results = {}
            return {}

        results = {}
        overall_rate = df[target_col].mean()
        overall_std = df[target_col].std() if len(df) > 0 else 0

        # --- Per-segment analysis ---
        segment_stats = []

        for col in available_segments:
            if col not in df.columns:
                continue

            for segment_value, group in df.groupby(col):
                segment_size = len(group)
                segment_rate = group[target_col].mean()

                # Skip very small segments
                min_size = self.config.get("min_segment_size", 100)
                if segment_size < min_size:
                    self._add_alert(
                        code="SEGMENT_IMBALANCE",
                        message=(
                            f"El segmento '{col}={segment_value}' tiene solo {segment_size} registros "
                            f"(threshold: {min_size}). Consider grouping rare categories."
                        ),
                        severity="INFO",
                        details={"column": col, "segment": str(segment_value), "size": segment_size},
                    )
                    continue

                # Calculate deviation from overall rate (in sigmas)
                if overall_std > 0:
                    z_score = abs(segment_rate - overall_rate) / overall_std
                else:
                    z_score = 0

                segment_stats.append(
                    {
                        "column": col,
                        "segment": str(segment_value),
                        "size": segment_size,
                        "size_pct": round(segment_size / len(df) * 100, 4),
                        "target_rate": round(float(segment_rate), 6),
                        "rate_diff_from_overall": round(float(segment_rate - overall_rate), 6),
                        "z_score": round(z_score, 4),
                    }
                )

                # Alert on significant drift
                drift_threshold = self.config.get("segment_drift_threshold", 3.0)
                if z_score > drift_threshold:
                    self._add_alert(
                        code="SEGMENT_DRIFT",
                        message=(
                            f"El segmento '{col}={segment_value}' tiene una tasa de fraude muy diferente "
                            f"({segment_rate:.1%}) vs el promedio global ({overall_rate:.1%}). "
                            f"Diferencia: {z_score:.1f}σ"
                        ),
                        severity="INFO",
                        details={
                            "column": col,
                            "segment": str(segment_value),
                            "segment_rate": segment_rate,
                            "overall_rate": overall_rate,
                            "z_score": z_score,
                        },
                    )

        # Sort by absolute z-score (most different segments first)
        segment_stats.sort(key=lambda x: abs(x["z_score"]), reverse=True)
        results["segment_stats"] = segment_stats

        # --- Cross-segment analysis (for top 2 segment columns) ---
        cross_analysis = {}
        if len(available_segments) >= 2:
            # Take top 2 columns by cardinality
            col1, col2 = available_segments[0], available_segments[1]

            try:
                cross_tab = pd.crosstab(df[col1], df[col2], values=df[target_col], aggfunc="mean")

                cross_matrix = []
                for i, row in enumerate(cross_tab.index):
                    for j, col in enumerate(cross_tab.columns):
                        val = cross_tab.iloc[i, j]
                        if not pd.isna(val):
                            cross_matrix.append(
                                {
                                    "dim1": str(row),
                                    "dim2": str(col),
                                    "target_rate": round(float(val), 6),
                                }
                            )

                cross_analysis[f"{col1}_x_{col2}"] = cross_matrix
            except Exception as e:
                logger.debug("Cross analysis failed for %s x %s: %s", col1, col2, e)

        results["cross_analysis"] = cross_analysis

        # --- Inspection coverage by segment (if relevant) ---
        # This would require knowing which records were inspected
        # Could add an `inspected_col` parameter to flag inspected records

        # Check if segments are so different they might justify separate models
        if segment_stats:
            max_z_score = max(abs(s["z_score"]) for s in segment_stats)
            if max_z_score > 5:  # Very significant difference
                top_segments = sorted(segment_stats, key=lambda x: abs(x["z_score"]), reverse=True)[:3]
                self._add_alert(
                    code="POTENTIAL_MODEL_SEPARATION",
                    message=(
                        f"Algunos segmentos tienen comportamiento muy diferente (max z={max_z_score:.1f}). "
                        "Considere modelos separados o tratamiento especial para estos segmentos."
                    ),
                    severity="INFO",
                    details={"top_segments": top_segments, "max_z_score": max_z_score},
                )

        self.results = results
        return results

    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis."""
        return self.alerts
