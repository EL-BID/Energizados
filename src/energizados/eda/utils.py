"""
Utility functions for EDA (Exploratory Data Analysis) - Energizados Framework.

Provides shared helper functions for column classification and statistical computations.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def classify_columns(
    df: pd.DataFrame,
    periods_suffix: str = "_anterior",
    lat_col: Optional[str] = None,
    lon_col: Optional[str] = None,
    date_col: Optional[str] = None,
    id_col: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    Classify DataFrame columns into semantic groups.

    Args:
        df: Input DataFrame
        periods_suffix: Suffix used to identify consumption period columns
        lat_col: Name of latitude column (optional)
        lon_col: Name of longitude column (optional)
        date_col: Name of date column (optional)
        id_col: Name of id column (optional)

    Returns:
        dict with keys:
            - numeric: numeric columns (excluding consumption)
            - categorical: object/category columns
            - temporal: datetime columns
            - consumption: columns matching period suffix pattern
            - id: id columns
            - target_candidates: binary columns that could be target
    """
    result: Dict[str, List[str]] = {
        "numeric": [],
        "categorical": [],
        "temporal": [],
        "consumption": [],
        "id": [],
        "target_candidates": [],
    }

    # Identify consumption columns - pattern: {N}_anterior
    consumption_pattern = re.compile(r"^\d+" + re.escape(periods_suffix) + r"$")
    consumption_cols = [c for c in df.columns if consumption_pattern.match(c)]
    result["consumption"] = sorted(consumption_cols, key=lambda x: int(x.replace(periods_suffix, "")), reverse=True)

    # Explicitly specified columns
    if id_col and id_col in df.columns:
        result["id"].append(id_col)

    excluded = set(consumption_cols) | set(result["id"])

    for col in df.columns:
        if col in excluded:
            continue

        # Geo columns → numeric
        if col in (lat_col, lon_col):
            result["numeric"].append(col)
            continue

        dtype = df[col].dtype

        if pd.api.types.is_datetime64_any_dtype(dtype):
            result["temporal"].append(col)
            # Also match date_col if it's object but specified as date
        elif col == date_col and dtype == object:
            result["temporal"].append(col)
        elif pd.api.types.is_numeric_dtype(dtype):
            n_unique = df[col].nunique(dropna=True)
            # Binary numeric columns → target candidates
            if n_unique <= 2 and set(df[col].dropna().unique()).issubset({0, 1, 0.0, 1.0}):
                result["target_candidates"].append(col)
            else:
                result["numeric"].append(col)
        elif dtype == object or str(dtype) == "category":
            result["categorical"].append(col)

    return result


def compute_iv_woe(
    df: pd.DataFrame,
    feature_col: str,
    target_col: str,
    bins: int = 10,
    is_categorical: bool = False,
) -> Dict:
    """
    Compute Information Value (IV) and Weight of Evidence (WoE) for a feature.

    Args:
        df: Input DataFrame
        feature_col: Feature column name
        target_col: Target (binary) column name
        bins: Number of bins for numeric features (quantile-based)
        is_categorical: If True, groups by category instead of binning

    Returns:
        dict with keys:
            - iv: float, total Information Value
            - woe_table: pd.DataFrame with columns [bin, count, events, non_events,
                         event_rate, woe, iv_bin]
    """
    empty_result = {
        "iv": 0.0,
        "woe_table": pd.DataFrame(columns=["bin", "count", "events", "non_events", "event_rate", "woe", "iv_bin"]),
    }

    # Remove rows with nulls in either column
    sub = df[[feature_col, target_col]].dropna()
    if len(sub) == 0:
        return empty_result

    total_events = sub[target_col].sum()
    total_non_events = len(sub) - total_events

    if total_events == 0 or total_non_events == 0:
        return empty_result

    if is_categorical:
        grouped = sub.groupby(feature_col)[target_col].agg(["sum", "count"]).reset_index()
        grouped.columns = ["bin", "events", "count"]
    else:
        # Quantile-based binning for numeric
        try:
            sub["_bin"] = pd.qcut(sub[feature_col], q=bins, duplicates="drop")
        except Exception:
            try:
                sub["_bin"] = pd.cut(sub[feature_col], bins=bins, duplicates="drop")
            except Exception:
                return empty_result

        grouped = sub.groupby("_bin", observed=True)[target_col].agg(["sum", "count"]).reset_index()
        grouped.columns = ["bin", "events", "count"]
        grouped["bin"] = grouped["bin"].astype(str)

    grouped["non_events"] = grouped["count"] - grouped["events"]
    grouped["event_rate"] = grouped["events"] / grouped["count"]

    # Distribution rates
    grouped["dist_events"] = grouped["events"] / total_events
    grouped["dist_non_events"] = grouped["non_events"] / total_non_events

    # WoE calculation with clipping for inf values
    def safe_woe(de, dne):
        if de <= 0 or dne <= 0:
            return 0.0
        return np.log(de / dne)

    grouped["woe"] = grouped.apply(lambda r: safe_woe(r["dist_events"], r["dist_non_events"]), axis=1)
    grouped["woe"] = grouped["woe"].clip(-20, 20)

    # IV per bin
    grouped["iv_bin"] = (grouped["dist_events"] - grouped["dist_non_events"]) * grouped["woe"]

    total_iv = grouped["iv_bin"].sum()

    woe_table = grouped[["bin", "count", "events", "non_events", "event_rate", "woe", "iv_bin"]].copy()

    return {"iv": float(total_iv), "woe_table": woe_table}


def cramers_v(df: pd.DataFrame, col1: str, col2: str) -> float:
    """
    Compute Cramér's V statistic for association between two categorical columns.

    Args:
        df: Input DataFrame
        col1: First categorical column name
        col2: Second categorical column name

    Returns:
        float: Cramér's V statistic [0, 1]
    """
    try:
        sub = df[[col1, col2]].dropna()
        if len(sub) == 0:
            return 0.0

        contingency = pd.crosstab(sub[col1], sub[col2])
        n = contingency.sum().sum()
        if n == 0:
            return 0.0

        try:
            from scipy.stats import chi2_contingency

            chi2, _, _, _ = chi2_contingency(contingency)
        except ImportError:
            # Manual chi2 calculation
            expected = np.outer(contingency.sum(axis=1), contingency.sum(axis=0)) / n
            chi2 = float(((contingency.values - expected) ** 2 / np.where(expected == 0, 1, expected)).sum())

        r, k = contingency.shape
        phi2 = chi2 / n
        phi2_corr = max(0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
        r_corr = r - (r - 1) ** 2 / (n - 1)
        k_corr = k - (k - 1) ** 2 / (n - 1)

        denom = min(r_corr - 1, k_corr - 1)
        if denom <= 0:
            return 0.0

        return float(np.sqrt(phi2_corr / denom))

    except Exception as e:
        logger.debug("cramers_v error for (%s, %s): %s", col1, col2, e)
        return 0.0


def ks_statistic(df: pd.DataFrame, feature_col: str, target_col: str) -> Tuple[float, float]:
    """
    Compute Kolmogorov-Smirnov statistic between distributions of feature for each class.

    Args:
        df: Input DataFrame
        feature_col: Feature column name (numeric)
        target_col: Binary target column name

    Returns:
        tuple: (ks_stat, p_value)
    """
    try:
        sub = df[[feature_col, target_col]].dropna()
        if len(sub) == 0:
            return 0.0, 1.0

        group0 = sub[sub[target_col] == 0][feature_col].values
        group1 = sub[sub[target_col] == 1][feature_col].values

        if len(group0) == 0 or len(group1) == 0:
            return 0.0, 1.0

        try:
            from scipy.stats import ks_2samp

            stat, pval = ks_2samp(group0, group1)
            return float(stat), float(pval)
        except ImportError:
            # Fallback: approximate KS statistic manually
            all_vals = np.sort(np.concatenate([group0, group1]))
            cdf0 = np.searchsorted(np.sort(group0), all_vals, side="right") / len(group0)
            cdf1 = np.searchsorted(np.sort(group1), all_vals, side="right") / len(group1)
            stat = float(np.max(np.abs(cdf0 - cdf1)))
            return stat, 1.0

    except Exception as e:
        logger.debug("ks_statistic error for %s: %s", feature_col, e)
        return 0.0, 1.0


def point_biserial_corr(df: pd.DataFrame, feature_col: str, target_col: str) -> Tuple[float, float]:
    """
    Compute point-biserial correlation between a numeric feature and a binary target.

    Args:
        df: Input DataFrame
        feature_col: Numeric feature column name
        target_col: Binary target column name

    Returns:
        tuple: (correlation, p_value)
    """
    try:
        sub = df[[feature_col, target_col]].dropna()
        if len(sub) < 3:
            return 0.0, 1.0

        try:
            from scipy.stats import pointbiserialr

            corr, pval = pointbiserialr(sub[target_col].values, sub[feature_col].values)
            return float(corr), float(pval)
        except ImportError:
            # Fallback: manual calculation
            x = sub[feature_col].values.astype(float)
            y = sub[target_col].values.astype(float)
            n = len(x)
            n1 = y.sum()
            n0 = n - n1
            if n1 == 0 or n0 == 0:
                return 0.0, 1.0
            m1 = x[y == 1].mean()
            m0 = x[y == 0].mean()
            std = x.std()
            if std == 0:
                return 0.0, 1.0
            corr = (m1 - m0) / std * np.sqrt(n1 * n0 / n**2)
            return float(corr), 1.0

    except Exception as e:
        logger.debug("point_biserial_corr error for %s: %s", feature_col, e)
        return 0.0, 1.0
