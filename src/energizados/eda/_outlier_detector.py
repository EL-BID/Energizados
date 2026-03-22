"""
Internal outlier detection module for EDA.

Reusable across ColumnExplorer and notebooks.
Provides multi-method outlier detection (IQR, Z-score, Modified Z-score).
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class OutlierDetector:
    """
    Multi-method outlier detection for numeric series.

    Supports three detection methods:
    - IQR (Interquartile Range): Identifies values outside Q1 - multiplier*IQR or Q3 + multiplier*IQR
    - Z-score: Identifies values with |(x - mean) / std| > threshold
    - Modified Z-score: MAD-based (Median Absolute Deviation) robust to extreme values

    Args:
        methods: List of methods to use. Options: "iqr", "zscore", "modified_zscore".
                 Default: ["iqr", "zscore"]
        iqr_multiplier: Multiplier for IQR fences. Default: 1.5 (mild outliers), 3.0 (extreme)
        zscore_threshold: Threshold for standard z-score. Default: 3.0
        modified_zscore_threshold: Threshold for modified z-score. Default: 3.5
        alert_threshold_pct: Percentage of outliers that triggers an alert. Default: 10.0
        max_sample_values: Maximum number of outlier sample values to return. Default: 20

    Example:
        >>> detector = OutlierDetector(methods=["iqr", "zscore"])
        >>> results = detector.detect(df["consumption"])
        >>> print(results["iqr"]["outlier_count"])
        >>> print(results["iqr"]["sample_values"])
    """

    def __init__(
        self,
        methods: List[str] = ["iqr", "zscore"],
        iqr_multiplier: float = 1.5,
        zscore_threshold: float = 3.0,
        modified_zscore_threshold: float = 3.5,
        alert_threshold_pct: float = 10.0,
        max_sample_values: int = 20,
    ):
        self.methods = methods
        self.iqr_multiplier = iqr_multiplier
        self.zscore_threshold = zscore_threshold
        self.modified_zscore_threshold = modified_zscore_threshold
        self.alert_threshold_pct = alert_threshold_pct
        self.max_sample_values = max_sample_values

        # Validate methods
        valid_methods = {"iqr", "zscore", "modified_zscore"}
        for method in self.methods:
            if method not in valid_methods:
                raise ValueError(f"Invalid method '{method}'. Must be one of: {valid_methods}")

    def detect(self, series: pd.Series) -> Dict:
        """
        Run all configured methods on a series.

        Args:
            series: pandas Series to analyze for outliers

        Returns:
            dict with results per method. Each method result includes:
                - method: str, method name
                - outlier_count: int, number of outliers detected
                - outlier_pct: float, percentage of outliers
                - sample_values: list, sample outlier values (max max_sample_values)
                - has_alert: bool, True if outlier_pct > alert_threshold_pct
                - fences: dict (IQR only): {"lower": float, "upper": float}
                - mean/std (Z-score only)
                - median/mad (Modified Z-score only)
        """
        results = {}
        clean = series.dropna()

        if len(clean) == 0:
            logger.warning("Series is empty after dropping NaN values")
            return results

        if "iqr" in self.methods:
            results["iqr"] = self._detect_iqr(clean)
        if "zscore" in self.methods:
            results["zscore"] = self._detect_zscore(clean)
        if "modified_zscore" in self.methods:
            results["modified_zscore"] = self._detect_modified_zscore(clean)

        return results

    def _detect_iqr(self, series: pd.Series) -> Dict:
        """
        Detect outliers using Interquartile Range (IQR) method.

        Outliers are values outside: [Q1 - multiplier*IQR, Q3 + multiplier*IQR]

        Args:
            series: pandas Series (already cleaned of NaN values)

        Returns:
            dict with outlier detection results
        """
        q1, q3 = np.percentile(series, [25, 75])
        iqr = q3 - q1
        lower = q1 - self.iqr_multiplier * iqr
        upper = q3 + self.iqr_multiplier * iqr

        mask = (series < lower) | (series > upper)
        outlier_values = series[mask]

        return self._build_result(
            mask=mask,
            method="iqr",
            outlier_values=outlier_values,
            fences={"lower": float(lower), "upper": float(upper)},
        )

    def _detect_zscore(self, series: pd.Series) -> Dict:
        """
        Detect outliers using standard z-score method.

        Outliers are values with |z-score| > threshold.
        Guards against division by zero when std = 0.

        Args:
            series: pandas Series (already cleaned of NaN values)

        Returns:
            dict with outlier detection results
        """
        mean = float(series.mean())
        std = float(series.std())

        if std > 0:
            zscores = (series - mean) / std
        else:
            # All values are identical, no outliers
            zscores = pd.Series(0.0, index=series.index)
            logger.debug("Standard deviation is 0, treating all values as non-outliers")

        mask = zscores.abs() > self.zscore_threshold
        outlier_values = series[mask]

        return self._build_result(
            mask=mask,
            method="zscore",
            outlier_values=outlier_values,
            extra={"mean": mean, "std": std, "threshold": self.zscore_threshold},
        )

    def _detect_modified_zscore(self, series: pd.Series) -> Dict:
        """
        Detect outliers using modified z-score (MAD-based) method.

        Modified z-score = 0.6745 * (x - median) / MAD
        More robust to extreme values than standard z-score.

        Args:
            series: pandas Series (already cleaned of NaN values)

        Returns:
            dict with outlier detection results
        """
        median = float(series.median())
        mad = float(np.median(np.abs(series - median)))

        if mad > 0:
            modified_z = 0.6745 * (series - median) / mad
        else:
            # All values are identical, no outliers
            modified_z = pd.Series(0.0, index=series.index)
            logger.debug("MAD is 0, treating all values as non-outliers")

        mask = modified_z.abs() > self.modified_zscore_threshold
        outlier_values = series[mask]

        return self._build_result(
            mask=mask,
            method="modified_zscore",
            outlier_values=outlier_values,
            extra={"median": median, "mad": mad},
        )

    def _build_result(
        self,
        mask: pd.Series,
        method: str,
        outlier_values: pd.Series,
        fences: Optional[Dict] = None,
        extra: Optional[Dict] = None,
    ) -> Dict:
        """
        Build a consistent result dictionary for outlier detection.

        Args:
            mask: Boolean Series indicating outliers
            method: Method name ("iqr", "zscore", "modified_zscore")
            outlier_values: Series containing outlier values
            fences: Optional dict with lower/upper fences (IQR only)
            extra: Optional dict with additional method-specific stats

        Returns:
            dict with standardized outlier detection results
        """
        count = int(mask.sum())
        total = len(mask)
        pct = (count / total * 100) if total > 0 else 0.0

        # Limit sample values to max_sample_values
        sample = (
            outlier_values.head(self.max_sample_values).tolist() if len(outlier_values) > 0 else []
        )

        result = {
            "method": method,
            "outlier_count": count,
            "outlier_pct": round(pct, 4),
            "sample_values": sample,
            "has_alert": pct > self.alert_threshold_pct,
        }

        if fences is not None:
            result["fences"] = fences

        if extra is not None:
            result.update(extra)

        return result
