"""
Internal population segmentation module for EDA.

Detects multiple distinct populations in numeric distributions
by identifying significant jumps between consecutive percentiles.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PopulationAnalyzer:
    """
    Detects multiple populations in a numeric distribution.

    Uses percentile jump detection to identify where the distribution
    has significant breaks, indicating multiple distinct populations.

    The algorithm:
    1. Calculates a dense percentile sequence (e.g., every 0.5 percentile)
    2. Identifies "jumps" where the ratio between consecutive percentiles
       exceeds a threshold (default: 5.0x)
    3. Segments data into populations based on these jump points
    4. Generates interpretations for each population

    Args:
        percentile_step: Step size for percentile calculation (0.1-1.0).
                         Lower = more sensitive to small populations.
                         Default: 0.5 (P0, P0.5, P1.0, ..., P100)
        jump_ratio_threshold: Minimum ratio between consecutive percentiles
                             to qualify as a "jump". Higher = fewer populations.
                             Default: 5.0 (5x increase)
        max_populations: Maximum number of populations to detect.
                          Prevents over-segmentation. Default: 5
        min_population_pct: Minimum percentage of rows for a population.
                             Ignores tiny populations below this threshold.
                             Default: 0.5% (0.005)

    Example:
        >>> analyzer = PopulationAnalyzer(jump_ratio_threshold=5.0)
        >>> results = analyzer.analyze(df["consumption"], target_col=df["target"])
        >>> for pop in results["populations"]:
        ...     print(f"{pop['percentile_range']}: {pop['interpretation']}")
    """

    def __init__(
        self,
        percentile_step: float = 0.5,
        jump_ratio_threshold: float = 5.0,
        max_populations: int = 5,
        min_population_pct: float = 0.5,
    ):
        self.percentile_step = percentile_step
        self.jump_ratio_threshold = jump_ratio_threshold
        self.max_populations = max_populations
        self.min_population_pct = min_population_pct

        # Validate parameters
        if not (0.1 <= percentile_step <= 1.0):
            raise ValueError("percentile_step must be between 0.1 and 1.0")
        if jump_ratio_threshold < 2.0:
            raise ValueError("jump_ratio_threshold must be at least 2.0")
        if max_populations < 2 or max_populations > 10:
            raise ValueError("max_populations must be between 2 and 10")
        if min_population_pct < 0.1 or min_population_pct > 10.0:
            raise ValueError("min_population_pct must be between 0.1 and 10.0")

    def analyze(self, series: pd.Series, target: Optional[pd.Series] = None) -> Dict:
        """
        Analyze a series for multiple populations.

        Args:
            series: pandas Series to analyze (numeric)
            target: Optional target Series (binary classification).
                    If provided, includes target_rate in population interpretation.

        Returns:
            dict with:
                - populations: List[Dict] with population details
                - jumps: List[Dict] with detected percentile jumps
                - percentiles: Dict with calculated percentile values
                - has_multiple_populations: bool, True if >1 population detected
        """
        clean = series.dropna()

        if len(clean) == 0:
            logger.warning("Series is empty after dropping NaN values")
            return {
                "populations": [],
                "jumps": [],
                "percentiles": {},
                "has_multiple_populations": False,
            }

        # Calculate dense percentile sequence
        percentiles_dict = self._calculate_percentiles(clean)

        # Detect jumps in the percentile sequence
        jumps = self._detect_jumps(percentiles_dict)

        # Segment into populations based on jumps
        populations = self._segment_populations(clean, percentiles_dict, jumps, target)

        return {
            "populations": populations,
            "jumps": jumps,
            "percentiles": percentiles_dict,
            "has_multiple_populations": len(populations) > 1,
        }

    def _calculate_percentiles(self, series: pd.Series) -> Dict[float, float]:
        """
        Calculate a dense sequence of percentiles.

        Args:
            series: pandas Series (already cleaned of NaN values)

        Returns:
            dict mapping percentile (float) to value (float)
        """
        percentiles = np.arange(0, 100 + self.percentile_step, self.percentile_step)
        values = np.percentile(series, percentiles)

        return {float(p): float(v) for p, v in zip(percentiles, values)}

    def _detect_jumps(self, percentiles_dict: Dict[float, float]) -> List[Dict]:
        """
        Detect significant jumps between consecutive percentiles.

        A jump is detected when:
        - The ratio between consecutive percentiles exceeds threshold
        - The values are not both zero (avoid division by zero)

        Args:
            percentiles_dict: dict mapping percentile to value

        Returns:
            list of dicts with jump details:
                - from_percentile: float, start percentile
                - to_percentile: float, end percentile
                - from_value: float, value at start percentile
                - to_value: float, value at end percentile
                - ratio: float, ratio to_value / from_value
        """
        jumps = []
        sorted_percentiles = sorted(percentiles_dict.keys())

        for i in range(len(sorted_percentiles) - 1):
            p1, p2 = sorted_percentiles[i], sorted_percentiles[i + 1]
            v1, v2 = percentiles_dict[p1], percentiles_dict[p2]

            # Skip if both are zero (ratio undefined)
            if v1 == 0 and v2 == 0:
                continue

            # Calculate ratio (handle v1=0)
            if v1 == 0:
                ratio = float("inf") if v2 > 0 else 1.0
            else:
                ratio = abs(v2 / v1)

            # Detect jump if ratio exceeds threshold
            if ratio >= self.jump_ratio_threshold:
                jumps.append(
                    {
                        "from_percentile": p1,
                        "to_percentile": p2,
                        "from_value": v1,
                        "to_value": v2,
                        "ratio": round(ratio, 2),
                    }
                )

        # Sort jumps by ratio (descending) and keep top N
        jumps.sort(key=lambda x: x["ratio"], reverse=True)
        return jumps[: self.max_populations - 1]  # -1 because we need at least 2 populations

    def _segment_populations(
        self,
        series: pd.Series,
        percentiles_dict: Dict[float, float],
        jumps: List[Dict],
        target: Optional[pd.Series],
    ) -> List[Dict]:
        """
        Segment the data into populations based on detected jumps.

        Args:
            series: pandas Series to segment
            percentiles_dict: dict mapping percentile to value
            jumps: list of detected jumps
            target: Optional target Series

        Returns:
            list of dicts with population details
        """
        if not jumps:
            # No jumps detected: single population
            return [self._create_single_population(series, target)]

        # Build segmentation points from jumps
        # Start from P0, then use jump points as cutoffs
        cutoff_percentiles = [0.0]
        for jump in jumps:
            cutoff_percentiles.append(jump["from_percentile"])
        cutoff_percentiles.append(100.0)

        # Sort and dedupe cutoffs
        cutoff_percentiles = sorted(set(cutoff_percentiles))

        # Create populations
        populations = []
        total_rows = len(series)

        for i in range(len(cutoff_percentiles) - 1):
            p1, p2 = cutoff_percentiles[i], cutoff_percentiles[i + 1]

            # Get value range for this population
            v1 = percentiles_dict[p1]
            v2 = percentiles_dict[p2]

            # Calculate percentage of rows in this population
            pct_rows = (p2 - p1) / 100.0 * total_rows

            # Skip if population is too small
            if pct_rows / total_rows * 100 < self.min_population_pct:
                continue

            # Interpret the population
            interpretation = self._interpret_population(
                series, target, p1, p2, v1, v2, pct_rows, total_rows
            )

            populations.append(
                {
                    "range": (v1, v2),
                    "percentile_range": f"P{p1:g}–P{p2:g}",
                    "row_count": int(pct_rows),
                    "pct_rows": round(pct_rows / total_rows * 100, 2),
                    "interpretation": interpretation,
                }
            )

            # Stop if we've reached max_populations
            if len(populations) >= self.max_populations:
                break

        # If filtering removed all populations, return single population
        if not populations:
            return [self._create_single_population(series, target)]

        return populations

    def _create_single_population(self, series: pd.Series, target: Optional[pd.Series]) -> Dict:
        """Create a single population dict when no jumps are detected."""
        total_rows = len(series)

        if target is not None:
            # Filter to only rows where series and target align
            aligned_target = target[series.index]
            target_rate = aligned_target.mean() if len(aligned_target) > 0 else 0.0
            interpretation = (
                f"Single population (no significant jumps detected). Target rate: {target_rate:.2%}"
            )
        else:
            interpretation = "Single population (no significant jumps detected)"

        return {
            "range": (float(series.min()), float(series.max())),
            "percentile_range": "P0–P100",
            "row_count": total_rows,
            "pct_rows": 100.0,
            "interpretation": interpretation,
        }

    def _interpret_population(
        self,
        series: pd.Series,
        target: Optional[pd.Series],
        p1: float,
        p2: float,
        v1: float,
        v2: float,
        pct_rows: int,
        total_rows: int,
    ) -> str:
        """
        Generate interpretation for a population.

        Interpretation logic:
        - If target provided: Include target rate for this population
        - Based on position in distribution:
          - Lowest (P0-Px): "Lower population"
          - Middle (Px-Py): "Main population"
          - Highest (Py-P100): "Upper population" or "Potential outliers"
        - Based on size:
          - Large (>50%): "Majority population"
          - Medium (10-50%): "Secondary population"
          - Small (<10%): "Minor population"

        Args:
            series: pandas Series
            target: Optional target Series
            p1, p2: Percentile range bounds
            v1, v2: Value range bounds
            pct_rows: Number of rows in this population
            total_rows: Total number of rows

        Returns:
            str: Human-readable interpretation
        """
        parts = []

        # Position in distribution
        if p1 == 0:
            parts.append("Lower tail")
        elif p2 == 100:
            parts.append("Upper tail")
        else:
            parts.append("Middle range")

        # Size
        size_pct = pct_rows / total_rows * 100
        if size_pct > 50:
            parts.append("Majority")
        elif size_pct > 10:
            parts.append("Secondary")
        else:
            parts.append("Minor")

        # Value range info
        if v1 == 0 and v2 > 0:
            parts.append("(near zero to significant)")
        elif v1 > 0 and v2 > v1 * 10:
            parts.append("(wide range)")

        # Target rate (if provided)
        if target is not None:
            # Filter rows in this percentile range
            # Align target with series index to avoid "Unalignable boolean Series" error
            mask = (series >= v1) & (series <= v2)
            aligned_target = target.reindex(series.index)[mask]
            target_rate = aligned_target.mean() if len(aligned_target) > 0 else 0.0

            if target_rate > 0.05:
                parts.append(f"High target rate ({target_rate:.2%})")
            elif target_rate < 0.01:
                parts.append(f"Low target rate ({target_rate:.2%})")
            else:
                parts.append(f"Target rate: {target_rate:.2%}")

        return " | ".join(parts)
