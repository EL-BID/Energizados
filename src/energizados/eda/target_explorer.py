"""
Target Explorer Module - Energizados EDA Framework.

Phase 3: Analyzes the target variable distribution and class imbalance.
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

from energizados.eda.base import BaseExplorer

logger = logging.getLogger(__name__)


class TargetExplorer(BaseExplorer):
    """
    Analyzes the target variable for binary classification.

    Computes class distribution, imbalance ratio and temporal fraud rate evolution.

    Args:
        config: Configuration dictionary with thresholds:
            - class_imbalance_ratio: float (default 10.0)

    Example:
        >>> explorer = TargetExplorer()
        >>> results = explorer.analyze(df, target_col='target', date_col='fecha')
        >>> alerts = explorer.get_alerts()
    """

    def analyze(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        date_col: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        """
        Analyze target variable distribution.

        Args:
            df: Input DataFrame
            target_col: Name of binary target column (required)
            date_col: Optional date column for temporal rate analysis
            **kwargs: Additional arguments (ignored)

        Returns:
            dict with keys:
                - class_counts: {label: count}
                - class_pcts: {label: pct}
                - imbalance_ratio: float (majority/minority)
                - recommendation: 'over', 'under', or 'none'
                - temporal_rate: list of dicts [{period, total, positive, rate}]
        """
        self.alerts = []

        if not target_col or target_col not in df.columns:
            logger.warning("target_col '%s' not found in DataFrame", target_col)
            self.results = {}
            return {}

        imbalance_threshold = self.config.get("class_imbalance_ratio", 10.0)

        target_series = df[target_col].dropna()
        value_counts = target_series.value_counts()
        total = len(target_series)

        class_counts = {str(k): int(v) for k, v in value_counts.items()}
        class_pcts = {str(k): round(float(v) / total * 100, 4) for k, v in value_counts.items()}

        # Imbalance ratio: majority / minority
        if len(value_counts) >= 2:
            majority_count = int(value_counts.iloc[0])
            minority_count = int(value_counts.iloc[-1])
            imbalance_ratio = round(majority_count / minority_count, 4) if minority_count > 0 else float("inf")
        else:
            imbalance_ratio = float("inf")
            majority_count = int(value_counts.iloc[0]) if len(value_counts) > 0 else 0
            minority_count = 0

        # Sampling recommendation based on imbalance
        recommendation = self._recommend_sampling(imbalance_ratio)

        # Fire alert if heavily imbalanced
        if imbalance_ratio > imbalance_threshold:
            minority_pct = round(minority_count / total * 100, 2) if total > 0 else 0.0
            self._add_alert(
                code="CLASS_IMBALANCE",
                message=(
                    f"Desbalance de clases detectado: ratio {imbalance_ratio:.1f}:1 "
                    f"(clase minoritaria: {minority_pct:.2f}% de los datos). "
                    f"Recommended resampling technique: '{recommendation}'."
                ),
                severity="WARNING",
                details={
                    "imbalance_ratio": imbalance_ratio,
                    "majority_count": majority_count,
                    "minority_count": minority_count,
                    "recommendation": recommendation,
                },
            )

        # Temporal analysis
        temporal_rate = []
        if date_col and date_col in df.columns:
            temporal_rate = self._compute_temporal_rate(df, target_col, date_col)

        results = {
            "class_counts": class_counts,
            "class_pcts": class_pcts,
            "imbalance_ratio": imbalance_ratio,
            "recommendation": recommendation,
            "temporal_rate": temporal_rate,
        }

        self.results = results
        return results

    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis."""
        return self.alerts

    def _recommend_sampling(self, ratio: float) -> str:
        """
        Recommend a sampling strategy based on imbalance ratio.

        Args:
            ratio: Majority to minority class ratio

        Returns:
            str: 'over', 'under', or 'none'
        """
        if ratio < 2:
            return "none"
        elif ratio < 10:
            return "over"
        else:
            return "under"

    def _compute_temporal_rate(self, df: pd.DataFrame, target_col: str, date_col: str) -> List[Dict]:
        """
        Compute target rate grouped by time period.

        Args:
            df: Input DataFrame
            target_col: Target column name
            date_col: Date column name

        Returns:
            list of dicts: [{period, total, positive, rate}]
        """
        try:
            sub = df[[date_col, target_col]].copy()

            # Parse date if needed
            if not pd.api.types.is_datetime64_any_dtype(sub[date_col]):
                sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")

            sub = sub.dropna(subset=[date_col, target_col])
            if len(sub) == 0:
                return []

            # Group by year-month
            sub["_period"] = sub[date_col].dt.to_period("M").astype(str)
            grouped = sub.groupby("_period")[target_col].agg(["sum", "count"]).reset_index()
            grouped.columns = ["period", "positive", "total"]
            grouped["rate"] = grouped.apply(
                lambda r: round(float(r["positive"]) / r["total"] * 100, 4) if r["total"] > 0 else 0.0,
                axis=1,
            )

            return [
                {
                    "period": str(row["period"]),
                    "total": int(row["total"]),
                    "positive": int(row["positive"]),
                    "rate": float(row["rate"]),
                }
                for _, row in grouped.sort_values("period").iterrows()
            ]

        except Exception as e:
            logger.warning("Error computing temporal rate: %s", e)
            return []
