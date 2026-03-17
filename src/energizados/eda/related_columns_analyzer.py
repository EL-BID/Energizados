"""
Related Columns Analyzer - Energizados EDA Framework.

Generic analyzer for hierarchical column relationships.
Replaces the hardcoded InspectionAnalyzer with configurable hierarchies.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from energizados.eda.base import BaseExplorer

logger = logging.getLogger(__name__)


class RelatedColumnsAnalyzer(BaseExplorer):
    """
    Analyzes hierarchical relationships between columns.

    Given a list of hierarchies (each a named ordered list of columns),
    computes cross-tabulations, tree breakdowns, target rates, and
    generates data for sunburst/sankey visualizations.

    Args:
        config: Configuration dictionary with thresholds:
            - sparse_combination_threshold: int (default 10) - alert if combo count < N
            - dominant_path_threshold: float (default 0.8) - alert if path > 80%
            - target_disparity_zscore: float (default 2.0) - alert if z-score > N

    Example:
        >>> analyzer = RelatedColumnsAnalyzer()
        >>> results = analyzer.analyze(
        ...     df,
        ...     target_col="target",
        ...     hierarchies=[
        ...         {"name": "Inspecciones", "columns": ["TIPO", "ACAO", "CATEGORIA"]},
        ...     ],
        ... )
    """

    def analyze(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        hierarchies: Optional[List[Dict]] = None,
        **kwargs,
    ) -> Dict:
        """
        Analyze hierarchical column relationships.

        Args:
            df: Input DataFrame
            target_col: Binary target column (optional)
            hierarchies: List of dicts with keys 'name' and 'columns'
            **kwargs: Additional arguments (ignored)

        Returns:
            dict with one entry per hierarchy containing:
                - level_distributions: value_counts per level
                - cross_tabulation: counts by full combination
                - tree_breakdown: recursive tree structure
                - target_rates: target rate per combination (if target_col)
                - sunburst_data: data for sunburst chart
                - sankey_data: data for sankey chart
        """
        self.alerts = []

        if not hierarchies:
            self.results = {}
            return {}

        results = {}
        for hierarchy in hierarchies:
            name = hierarchy.get("name", "Unnamed")
            columns = hierarchy.get("columns", [])

            if not columns:
                logger.debug("Hierarchy '%s' has no columns, skipping", name)
                continue

            # Validate columns exist
            missing = [c for c in columns if c not in df.columns]
            if missing:
                logger.warning(
                    "Hierarchy '%s': columns %s not found in DataFrame, skipping",
                    name,
                    missing,
                )
                self._add_alert(
                    code="HIERARCHY_MISSING_COLUMNS",
                    message=f"Hierarchy '{name}': columns {missing} not found in dataset.",
                    severity="WARNING",
                    details={"hierarchy": name, "missing_columns": missing},
                )
                continue

            h_result = self._analyze_hierarchy(df, columns, name, target_col)
            results[name] = h_result

        self.results = results
        return results

    def _analyze_hierarchy(
        self,
        df: pd.DataFrame,
        columns: List[str],
        name: str,
        target_col: Optional[str],
    ) -> Dict:
        """Analyze a single hierarchy."""
        result: Dict[str, Any] = {"name": name, "columns": columns}

        # 1. Value counts per level
        level_distributions = {}
        for col in columns:
            vc = df[col].value_counts()
            level_distributions[col] = {
                "unique": int(vc.shape[0]),
                "top_values": [
                    {"value": str(k), "count": int(v), "pct": round(float(v / len(df) * 100), 2)}
                    for k, v in vc.head(20).items()
                ],
            }
        result["level_distributions"] = level_distributions

        # 2. Cross tabulation (full combination counts)
        sub = df[columns].dropna()
        if len(sub) == 0:
            result["cross_tabulation"] = []
            result["tree_breakdown"] = []
            return result

        cross = sub.groupby(columns).size().reset_index(name="count")
        cross = cross.sort_values("count", ascending=False)
        result["cross_tabulation"] = cross.head(200).to_dict("records")

        # 3. Tree breakdown
        result["tree_breakdown"] = self._build_tree(sub, columns, total=len(sub))

        # 4. Target rates per combination
        if target_col and target_col in df.columns:
            sub_target = df[columns + [target_col]].dropna()
            if len(sub_target) > 0:
                target_cross = sub_target.groupby(columns)[target_col].agg(["mean", "count"])
                target_cross = target_cross.reset_index()
                target_cross.columns = list(columns) + ["target_rate", "count"]
                result["target_rates"] = target_cross.head(200).to_dict("records")

                # Heatmap data: if 2+ columns, create pivot of first two
                if len(columns) >= 2:
                    try:
                        pivot = sub_target.groupby([columns[0], columns[1]])[target_col].mean()
                        result["target_heatmap"] = pivot.unstack(fill_value=0)
                    except Exception as e:
                        logger.debug("Error creating target heatmap pivot: %s", e)

                # Detect target disparity
                self._check_target_disparity(target_cross, name, columns)

        # 5. Alerts for sparse combinations and dominant paths
        self._check_sparse_combinations(cross, name, len(sub))
        self._check_dominant_path(cross, name, len(sub))

        return result

    def _build_tree(
        self,
        df: pd.DataFrame,
        columns: List[str],
        total: int,
    ) -> List[Dict]:
        """Recursively build tree breakdown structure."""
        if not columns or len(df) == 0:
            return []

        col = columns[0]
        remaining = columns[1:]
        tree = []

        vc = df[col].value_counts()
        for value, count in vc.items():
            node: Dict[str, Any] = {
                "value": str(value),
                "column": col,
                "count": int(count),
                "pct_of_parent": round(float(count / len(df) * 100), 2),
                "pct_of_total": round(float(count / total * 100), 2),
            }
            if remaining:
                subset = df[df[col] == value]
                node["children"] = self._build_tree(subset, remaining, total)
            tree.append(node)

        return tree

    def _check_sparse_combinations(self, cross: pd.DataFrame, name: str, total: int) -> None:
        """Alert for combinations with very few records."""
        threshold = self.config.get("sparse_combination_threshold", 10)
        sparse = cross[cross["count"] < threshold]
        if len(sparse) > 0:
            n_sparse = len(sparse)
            self._add_alert(
                code="HIERARCHY_SPARSE_COMBINATION",
                message=(
                    f"Hierarchy '{name}': {n_sparse} combinations have fewer than "
                    f"{threshold} records. May not be statistically significant."
                ),
                severity="WARNING",
                details={
                    "hierarchy": name,
                    "sparse_count": n_sparse,
                    "threshold": threshold,
                },
            )

    def _check_dominant_path(self, cross: pd.DataFrame, name: str, total: int) -> None:
        """Alert if a single combination concentrates too many records."""
        threshold = self.config.get("dominant_path_threshold", 0.8)
        if len(cross) == 0 or total == 0:
            return

        top_pct = float(cross.iloc[0]["count"]) / total
        if top_pct > threshold:
            self._add_alert(
                code="HIERARCHY_DOMINANT_PATH",
                message=(
                    f"Hierarchy '{name}': the most frequent combination concentrates "
                    f"{top_pct:.1%} of records (threshold: {threshold:.0%})."
                ),
                severity="WARNING",
                details={"hierarchy": name, "dominant_pct": round(top_pct, 4)},
            )

    def _check_target_disparity(
        self, target_cross: pd.DataFrame, name: str, columns: List[str]
    ) -> None:
        """Alert if target rate varies significantly across combinations."""
        zscore_threshold = self.config.get("target_disparity_zscore", 2.0)
        rates = target_cross["target_rate"]
        if len(rates) < 2:
            return

        mean_rate = rates.mean()
        std_rate = rates.std()
        if std_rate == 0:
            return

        z_scores = ((rates - mean_rate) / std_rate).abs()
        extreme = z_scores[z_scores > zscore_threshold]
        if len(extreme) > 0:
            self._add_alert(
                code="HIERARCHY_TARGET_DISPARITY",
                message=(
                    f"Hierarchy '{name}': {len(extreme)} combinations show significant "
                    f"disparity in target rate (z-score > {zscore_threshold})."
                ),
                severity="INFO",
                details={
                    "hierarchy": name,
                    "extreme_count": len(extreme),
                    "zscore_threshold": zscore_threshold,
                },
            )

    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis."""
        return self.alerts
