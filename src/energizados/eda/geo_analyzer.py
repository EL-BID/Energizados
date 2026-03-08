"""
Geospatial Analyzer Module - Energizados EDA Framework.

Phase 5: Analyzes geographic distribution and clustering of clients/fraud.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from energizados.eda.base import BaseExplorer

logger = logging.getLogger(__name__)


class GeospatialAnalyzer(BaseExplorer):
    """
    Analyzes geospatial distribution of clients and fraud patterns.

    Validates coordinate quality, clusters geographic data, and identifies
    geographic biases in inspection coverage.

    Args:
        config: Configuration dictionary with thresholds:
            - invalid_coord_threshold: float (default 0.2) - alert if > 20% invalid
            - country_bounds: list of [[lat_min, lon_min], [lat_max, lon_max]]

    Example:
        >>> analyzer = GeospatialAnalyzer()
        >>> results = analyzer.analyze(
        ...     df,
        ...     lat_col="LATITUDE",
        ...     lon_col="LONGITUDE",
        ...     zone_col="ZONA",
        ...     target_col="target"
        ... )
    """

    def analyze(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        lat_col: Optional[str] = None,
        lon_col: Optional[str] = None,
        zone_col: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        """
        Analyze geospatial data.

        Args:
            df: Input DataFrame
            target_col: Binary target column (optional)
            lat_col: Latitude column name
            lon_col: Longitude column name
            zone_col: Zone/region column name (alternative to lat/lon)
            **kwargs: Additional arguments (ignored)

        Returns:
            dict with keys:
                - coord_quality: dict of quality metrics
                - zone_stats: dict of per-zone statistics (if zone_col provided)
                - clustering: dict of clustering results
                - target_by_zone: dict of target rates by zone (if target_col provided)
        """
        self.alerts = []

        if not any([lat_col, lon_col, zone_col]):
            logger.warning("No geographic columns specified, skipping analysis")
            self.results = {}
            return {}

        results = {}

        # --- Coordinate quality validation ---
        coord_quality = {}
        has_lat_lon = lat_col and lat_col in df.columns and lon_col and lon_col in df.columns

        if has_lat_lon:
            lat_series = df[lat_col]
            lon_series = df[lon_col]

            total = len(df)
            null_count = lat_series.isna().sum() + lon_series.isna().sum()
            null_pct = round(null_count / (2 * total) * 100, 4) if total > 0 else 0.0

            # Check for (0, 0) placeholder values
            zero_mask = (lat_series == 0) & (lon_series == 0)
            zero_count = int(zero_mask.sum())
            zero_pct = round(zero_count / total * 100, 4) if total > 0 else 0.0

            # Check for coordinates outside country bounds
            country_bounds = self.config.get("country_bounds")
            oob_count = 0
            if country_bounds and len(country_bounds) == 2:
                lat_min, lon_min = country_bounds[0]
                lat_max, lon_max = country_bounds[1]
                oob_mask = (lat_series < lat_min) | (lat_series > lat_max) | (lon_series < lon_min) | (lon_series > lon_max)
                oob_count = int(oob_mask.sum())

            # Exact duplicates (multiple clients at same location)
            coord_df = df[[lat_col, lon_col]].dropna()
            dup_count = coord_df.duplicated().sum()
            dup_pct = round(dup_count / total * 100, 4) if total > 0 else 0.0

            coord_quality = {
                "total_records": total,
                "null_pct": null_pct,
                "zero_coord_pct": zero_pct,
                "out_of_bounds_count": oob_count,
                "duplicate_coords_pct": dup_pct,
                "valid_coords_count": int(coord_df.drop_duplicates().shape[0]),
            }

            # Alert on high percentage of invalid coordinates
            invalid_threshold = self.config.get("invalid_coord_threshold", 0.2)
            total_invalid_pct = zero_pct + null_pct
            if total_invalid_pct > invalid_threshold:
                self._add_alert(
                    code="GEO_DATA_INVALID",
                    message=(
                        f"Alta proporción de coordenadas inválidas o nulas: {total_invalid_pct:.1f}. "
                        "Verifique el proceso de carga de datos geoespaciales."
                    ),
                    severity="ERROR",
                    details={"invalid_pct": total_invalid_pct, "threshold": invalid_threshold},
                )

        results["coord_quality"] = coord_quality

        # --- Zone-based analysis (alternative or complement to lat/lon) ---
        zone_stats = {}
        target_by_zone = {}

        if zone_col and zone_col in df.columns:
            zone_dist = df[zone_col].value_counts()
            zone_stats = {
                "total_zones": int(zone_dist.count()),
                "zone_distribution": {str(k): int(v) for k, v in zone_dist.items()},
                "most_common_zone": str(zone_dist.idxmax()) if len(zone_dist) > 0 else None,
                "most_common_zone_pct": round(float(zone_dist.max()) / len(df) * 100, 2) if len(zone_dist) > 0 else 0.0,
            }

            # Target rate by zone
            if target_col and target_col in df.columns:
                zone_target_rate = df.groupby(zone_col)[target_col].mean()
                target_by_zone = {str(k): round(float(v), 6) for k, v in zone_target_rate.items() if not pd.isna(v)}

                # Check for geographic bias in target rate
                if len(target_by_zone) > 1:
                    rates = list(target_by_zone.values())
                    rate_std = np.std(rates)
                    rate_mean = np.mean(rates)
                    cv = rate_std / rate_mean if rate_mean > 0 else 0

                    if cv > 0.5:  # High variation across zones
                        self._add_alert(
                            code="GEO_BIAS",
                            message=(f"Alta variación en la tasa de fraude por zona " f"(CV={cv:.2f}). Verifique si hay sesgo geográfico."),
                            severity="WARNING",
                            details={"cv": cv, "min_rate": min(rates), "max_rate": max(rates)},
                        )

        results["zone_stats"] = zone_stats
        results["target_by_zone"] = target_by_zone

        # --- Clustering analysis (only if we have valid coordinates) ---
        if has_lat_lon and coord_quality.get("valid_coords_count", 0) > 10:
            clustering = self._perform_clustering(df, lat_col, lon_col)
            results["clustering"] = clustering

        self.results = results
        return results

    def _perform_clustering(self, df: pd.DataFrame, lat_col: str, lon_col: str) -> Dict:
        """
        Perform K-Means clustering on coordinates.

        Args:
            df: Input DataFrame
            lat_col: Latitude column
            lon_col: Longitude column

        Returns:
            dict with clustering results
        """
        result = {"method": "kmeans", "n_clusters": 0, "cluster_stats": []}

        try:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler

            # Prepare data
            coord_df = df[[lat_col, lon_col]].dropna()
            coord_df = coord_df[(coord_df[lat_col] != 0) & (coord_df[lon_col] != 0)]

            if len(coord_df) < 10:
                return result

            # Scale coordinates (important because lat/lon have different ranges)
            scaler = StandardScaler()
            coords_scaled = scaler.fit_transform(coord_df)

            # Determine number of clusters (default: sqrt(n/2))
            n_clusters = self.config.get("n_clusters", 10)
            n_clusters = min(n_clusters, max(3, int(len(coord_df) ** 0.5)))

            # Fit K-Means
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(coords_scaled)

            # Compute cluster statistics
            coord_df["_cluster"] = labels

            cluster_stats = []
            for cluster_id in sorted(coord_df["_cluster"].unique()):
                cluster_data = coord_df[coord_df["_cluster"] == cluster_id]
                cluster_stats.append(
                    {
                        "cluster_id": int(cluster_id),
                        "count": len(cluster_data),
                        "lat_center": round(float(cluster_data[lat_col].mean()), 6),
                        "lon_center": round(float(cluster_data[lon_col].mean()), 6),
                        "lat_std": round(float(cluster_data[lat_col].std()), 6),
                        "lon_std": round(float(cluster_data[lon_col].std()), 6),
                    }
                )

            result = {
                "method": "kmeans",
                "n_clusters": n_clusters,
                "inertia": round(float(kmeans.inertia_), 4),
                "cluster_stats": cluster_stats,
            }

        except ImportError:
            logger.debug("scikit-learn not available, skipping clustering")
        except Exception as e:
            logger.debug("Clustering failed: %s", e)

        return result

    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis."""
        return self.alerts
