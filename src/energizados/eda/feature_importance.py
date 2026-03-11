"""
Feature Importance Analyzer Module - Energizados EDA Framework.

Phase 7: Computes predictive power rankings using IV, KS, Cramér's V and correlation.
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

from energizados.eda.base import BaseExplorer
from energizados.eda.utils import (
    compute_iv_woe,
    cramers_v,
    ks_statistic,
    point_biserial_corr,
)

logger = logging.getLogger(__name__)

_DEFAULT_METHODS = ["iv", "ks_chi2", "cramers_v", "correlation"]


class FeatureImportanceAnalyzer(BaseExplorer):
    """
    Computes feature importance / predictive power for all features.

    Supported methods:
    - iv: Information Value (WoE-based)
    - ks_chi2: Kolmogorov-Smirnov statistic for numeric, Chi2 for categorical
    - cramers_v: Cramér's V association measure for categorical features
    - correlation: Point-biserial correlation for numeric features

    Combines scores into a normalized combined_score and ranks features.

    Args:
        config: Configuration dictionary with thresholds:
            - iv_threshold_weak: float (default 0.02)
            - iv_threshold_leakage: float (default 0.8)

    Example:
        >>> analyzer = FeatureImportanceAnalyzer()
        >>> results = analyzer.analyze(df, target_col='target', col_types=col_types)
    """

    def analyze(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        col_types: Optional[Dict] = None,
        methods: Optional[List[str]] = None,
        lgbm_config: Optional[Dict] = None,
        **kwargs,
    ) -> Dict:
        """
        Compute feature importance rankings.

        Args:
            df: Input DataFrame
            target_col: Binary target column name (required)
            col_types: Column classification dict from utils.classify_columns()
            methods: List of methods to apply. Default: ['iv', 'ks_chi2', 'cramers_v', 'correlation']
            lgbm_config: LightGBM configuration for quick importance (optional, not used by default)
            **kwargs: Additional arguments (ignored)

        Returns:
            dict with keys:
                - ranking: pd.DataFrame with columns [feature, type, iv, ks_stat, ks_pval,
                           cramers_v, correlation, combined_score]
                - top_features: list of feature names (top 20 by combined_score)
                - weak_features: list of feature names with iv < threshold_weak
                - leakage_candidates: list of feature names with iv > threshold_leakage
        """
        self.alerts = []

        if not target_col or target_col not in df.columns:
            logger.warning("target_col '%s' not found, skipping feature importance analysis", target_col)
            empty_df = pd.DataFrame(columns=["feature", "type", "iv", "ks_stat", "ks_pval", "cramers_v", "correlation", "combined_score"])
            self.results = {"ranking": empty_df, "top_features": [], "weak_features": [], "leakage_candidates": []}
            return self.results

        methods = methods or _DEFAULT_METHODS
        col_types = col_types or {}

        iv_threshold_weak = self.config.get("iv_threshold_weak", 0.02)
        iv_threshold_leakage = self.config.get("iv_threshold_leakage", 0.8)

        numeric_cols = [c for c in col_types.get("numeric", []) if c != target_col and c in df.columns]
        categorical_cols = [c for c in col_types.get("categorical", []) if c != target_col and c in df.columns]

        all_features = [(c, "numeric") for c in numeric_cols] + [(c, "categorical") for c in categorical_cols]

        rows = []
        for col, feat_type in all_features:
            row = {"feature": col, "type": feat_type}

            # Information Value
            if "iv" in methods:
                try:
                    is_cat = feat_type == "categorical"
                    iv_result = compute_iv_woe(df, col, target_col, bins=10, is_categorical=is_cat)
                    row["iv"] = round(iv_result["iv"], 6)
                except Exception as e:
                    logger.debug("IV computation failed for '%s': %s", col, e)
                    row["iv"] = None

            # KS (numeric) / Chi2 approximation via KS for categorical
            if "ks_chi2" in methods:
                try:
                    if feat_type == "numeric":
                        stat, pval = ks_statistic(df, col, target_col)
                        row["ks_stat"] = round(stat, 6)
                        row["ks_pval"] = round(pval, 6)
                    else:
                        # For categorical: compute KS after ordinal encoding by frequency
                        sub = df[[col, target_col]].dropna()
                        freq_map = sub[col].value_counts().to_dict()
                        encoded = sub[col].map(freq_map).fillna(0)
                        tmp_df = pd.DataFrame({col: encoded.values, target_col: sub[target_col].values})
                        stat, pval = ks_statistic(tmp_df, col, target_col)
                        row["ks_stat"] = round(stat, 6)
                        row["ks_pval"] = round(pval, 6)
                except Exception as e:
                    logger.debug("KS computation failed for '%s': %s", col, e)
                    row["ks_stat"] = None
                    row["ks_pval"] = None

            # Cramér's V (categorical only)
            if "cramers_v" in methods:
                if feat_type == "categorical":
                    try:
                        cv = cramers_v(df, col, target_col)
                        row["cramers_v"] = round(cv, 6)
                    except Exception as e:
                        logger.debug("Cramér's V failed for '%s': %s", col, e)
                        row["cramers_v"] = None
                else:
                    row["cramers_v"] = None

            # Point-biserial correlation (numeric only)
            if "correlation" in methods:
                if feat_type == "numeric":
                    try:
                        corr, _ = point_biserial_corr(df, col, target_col)
                        row["correlation"] = round(abs(corr), 6)
                    except Exception as e:
                        logger.debug("Correlation failed for '%s': %s", col, e)
                        row["correlation"] = None
                else:
                    row["correlation"] = None

            rows.append(row)

        # Build ranking DataFrame
        ranking_df = pd.DataFrame(rows)

        if len(ranking_df) == 0:
            self.results = {
                "ranking": ranking_df,
                "top_features": [],
                "weak_features": [],
                "leakage_candidates": [],
            }
            return self.results

        # Combined score: normalized average of available metrics
        score_cols = []
        for metric_col in ["iv", "ks_stat", "cramers_v", "correlation"]:
            if metric_col in ranking_df.columns:
                series = ranking_df[metric_col].fillna(0).infer_objects(copy=False)
                max_val = series.max()
                if max_val > 0:
                    ranking_df[f"_norm_{metric_col}"] = series / max_val
                    score_cols.append(f"_norm_{metric_col}")

        if score_cols:
            ranking_df["combined_score"] = ranking_df[score_cols].mean(axis=1)
        else:
            ranking_df["combined_score"] = 0.0

        # Drop normalization helper columns
        ranking_df = ranking_df.drop(columns=[c for c in ranking_df.columns if c.startswith("_norm_")])

        ranking_df = ranking_df.sort_values("combined_score", ascending=False).reset_index(drop=True)

        top_features = ranking_df["feature"].head(20).tolist()

        # Weak features (low IV)
        weak_features: List[str] = []
        if "iv" in ranking_df.columns:
            iv_series = ranking_df["iv"].fillna(0)
            weak_features = ranking_df.loc[iv_series < iv_threshold_weak, "feature"].tolist()

        # Potential leakage (very high IV)
        leakage_candidates: List[str] = []
        if "iv" in ranking_df.columns:
            iv_series = ranking_df["iv"].fillna(0)
            leakage_candidates = ranking_df.loc[iv_series > iv_threshold_leakage, "feature"].tolist()

        # Fire alerts
        if weak_features:
            self._add_alert(
                code="WEAK_PREDICTORS",
                message=(
                    f"{len(weak_features)} variable(s) have IV < {iv_threshold_weak} "
                    f"(very low predictive power): {weak_features[:10]}. "
                    "Consider removing them to simplify the model."
                ),
                severity="INFO",
                details={"weak_features": weak_features, "threshold": iv_threshold_weak},
            )

        if leakage_candidates:
            self._add_alert(
                code="POTENTIAL_LEAKAGE",
                message=(
                    f"{len(leakage_candidates)} variable(s) have IV > {iv_threshold_leakage} "
                    f"(possible data leakage): {leakage_candidates}. "
                    "Verify that these variables do not contain information from the future."
                ),
                severity="ERROR",
                details={"leakage_candidates": leakage_candidates, "threshold": iv_threshold_leakage},
            )

        results = {
            "ranking": ranking_df,
            "top_features": top_features,
            "weak_features": weak_features,
            "leakage_candidates": leakage_candidates,
        }

        self.results = results
        return results

    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis."""
        return self.alerts
