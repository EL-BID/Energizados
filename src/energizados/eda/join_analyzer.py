"""
Join Analyzer Module - Energizados EDA Framework.

Phase 6: Analyzes coverage and bias from multi-source joins.
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

from energizados.eda.base import BaseExplorer

logger = logging.getLogger(__name__)


class JoinAnalyzer(BaseExplorer):
    """
    Analyzes the impact of joining multiple data sources.

    When a dataset is created by joining multiple sources (e.g., master +
    consumption + inspections), records can be lost. This analyzer quantifies
    that loss and profiles the excluded records to detect bias.

    Args:
        config: Configuration dictionary with thresholds:
            - max_acceptable_loss: float (default 0.3) - alert if > 30% records lost

    Example:
        >>> analyzer = JoinAnalyzer()
        >>> results = analyzer.analyze(
        ...     df,
        ...     id_col="CLIENTE",
        ...     source_indicators={
        ...             "has_master": "master_not_null",
        ...             "has_consumption": "consumption_not_null",
        ...             "has_inspection": "inspection_not_null"
        ...         }
        ... )
    """

    def analyze(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        id_col: Optional[str] = None,
        source_indicators: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict:
        """
        Analyze multi-source join coverage.

        Args:
            df: Input DataFrame (already joined, with indicator columns)
            target_col: Binary target column (optional, for bias detection)
            id_col: ID column name
            source_indicators: Dict mapping source names to indicator column names.
                Indicator columns should be boolean/integer indicating presence.
                Format: {"source_name": "indicator_column_name"}
            **kwargs: Additional arguments (ignored)

        Returns:
            dict with keys:
                - coverage: dict of per-source coverage stats
                - funnel: dict showing progressive loss through joins
                - excluded_profile: dict comparing excluded vs included records
                - alerts: list of join-related warnings
        """
        self.alerts = []

        if not source_indicators:
            logger.warning("No source indicators provided, skipping join analysis")
            self.results = {}
            return {}

        results = {}
        total_records = len(df)

        # --- Coverage by source ---
        coverage = {}
        for source_name, indicator_col in source_indicators.items():
            if indicator_col not in df.columns:
                continue

            indicator = df[indicator_col]
            present_count = int(indicator.fillna(0).astype(bool).sum())
            present_pct = round(present_count / total_records * 100, 4) if total_records > 0 else 0.0

            coverage[source_name] = {
                "present_count": present_count,
                "present_pct": present_pct,
                "missing_count": total_records - present_count,
                "missing_pct": round(100 - present_pct, 4),
            }

        results["coverage"] = coverage

        # --- Funnel analysis (progressive loss) ---
        funnel = []
        cumulative_present = total_records

        # Start with total
        funnel.append(
            {
                "stage": "total",
                "count": total_records,
                "pct_of_total": 100.0,
            }
        )

        # Apply each source filter sequentially
        available_sources = [s for s in source_indicators.keys() if source_indicators[s] in df.columns]

        for source in available_sources:
            indicator_col = source_indicators[source]
            mask = df[indicator_col].fillna(0).astype(bool)
            cumulative_present = int(mask.sum())

            funnel.append(
                {
                    "stage": f"with_{source}",
                    "count": cumulative_present,
                    "pct_of_total": round(cumulative_present / total_records * 100, 4) if total_records > 0 else 0.0,
                }
            )

        results["funnel"] = funnel

        # --- Calculate total loss ---
        final_stage = funnel[-1]
        final_count = final_stage["count"]
        total_loss = total_records - final_count
        total_loss_pct = round(total_loss / total_records * 100, 4) if total_records > 0 else 0.0

        max_loss = self.config.get("max_acceptable_loss", 0.3)
        if total_loss_pct > max_loss * 100:
            self._add_alert(
                code="HIGH_JOIN_LOSS",
                message=(
                    f"High record loss in joins: {total_loss_pct:.1f}% "
                    f"({total_loss:,} of {total_records:,} records lost). "
                    "Verify that this does not introduce bias."
                ),
                severity="WARNING",
                details={"loss_pct": total_loss_pct, "loss_count": total_loss},
            )

        # --- Profile excluded vs included ---
        excluded_profile = {}
        if len(available_sources) > 0:
            # Define "included" as records present in ALL sources
            all_indicators = [source_indicators[s] for s in available_sources]
            included_mask = pd.Series(True, index=df.index)

            for ind_col in all_indicators:
                included_mask &= df[ind_col].fillna(0).astype(bool)

            excluded_mask = ~included_mask

            included_count = int(included_mask.sum())
            excluded_count = int(excluded_mask.sum())

            excluded_profile["included_count"] = included_count
            excluded_profile["excluded_count"] = excluded_count

            # Compare target rates if available
            if target_col and target_col in df.columns:
                target_included = df.loc[included_mask, target_col].mean()
                target_excluded = df.loc[excluded_mask, target_col].mean()

                excluded_profile["target_rate_included"] = round(float(target_included), 6) if not pd.isna(target_included) else None
                excluded_profile["target_rate_excluded"] = round(float(target_excluded), 6) if not pd.isna(target_excluded) else None

                # Alert if excluded have significantly different target rate
                if not pd.isna(target_included) and not pd.isna(target_excluded):
                    rate_diff = abs(target_included - target_excluded)
                    if rate_diff > 0.1:  # More than 10% difference
                        self._add_alert(
                            code="UNBALANCED_EXCLUSION",
                            message=(
                                f"Los registros excluidos tienen una tasa de fraude muy diferente "
                                f"({target_excluded:.1%}) que los incluidos ({target_included:.1%}). "
                                "El join puede estar introduciendo sesgo."
                            ),
                            severity="WARNING",
                            details={
                                "excluded_rate": target_excluded,
                                "included_rate": target_included,
                                "difference": rate_diff,
                            },
                        )

            # Profile categorical distributions for key columns
            # (This would require knowing which columns to profile - could add to config)
            profile_cols = self.config.get("profile_columns", [])
            if profile_cols:
                categorical_comparison = {}
                for col in profile_cols:
                    if col not in df.columns:
                        continue

                    # Distribution for included
                    included_dist = df.loc[included_mask, col].value_counts(normalize=True)
                    # Distribution for excluded
                    excluded_dist = df.loc[excluded_mask, col].value_counts(normalize=True)

                    categorical_comparison[col] = {
                        "included_top": {str(k): round(float(v), 4) for k, v in included_dist.head(5).items()},
                        "excluded_top": {str(k): round(float(v), 4) for k, v in excluded_dist.head(5).items()},
                    }

                excluded_profile["categorical_comparison"] = categorical_comparison

        results["excluded_profile"] = excluded_profile

        self.results = results
        return results

    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis."""
        return self.alerts
