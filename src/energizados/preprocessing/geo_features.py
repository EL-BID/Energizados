"""
Geographic feature extraction from latitude/longitude coordinates.

Extracts geographic hierarchy (estado, município, região), distance-based features,
and optional target-encoded categorical features using IBGE shapefiles via geobr.
"""

import logging
import math
import warnings
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

logger = logging.getLogger(__name__)

# Reference cities (name, lat, lon)
REFERENCE_CITIES = {
    "sao_paulo": (-23.5505, -46.6333),
    "rio_de_janeiro": (-22.9068, -43.1729),
    "brasilia": (-15.7975, -47.8919),
    "salvador": (-12.9714, -38.5124),
    "belo_horizonte": (-19.9167, -43.9345),
    "fortaleza": (-3.7172, -38.5433),
    "recife": (-8.0476, -34.8770),
    "curitiba": (-25.4284, -49.2733),
    "manaus": (-3.1190, -60.0217),
    "porto_alegre": (-30.0346, -51.2177),
    "florianopolis": (-27.5954, -48.5480),
    "blumenau": (-26.9190, -49.0661),
    "joinville": (-26.3045, -48.8487),
    "criciuma": (-28.6775, -49.3696),
    "chapeco": (-27.1008, -52.6152),
    "itajai": (-26.9082, -48.6626),
    "lages": (-27.8161, -50.3260),
}

# State capitals (UF → (name, lat, lon))
STATE_CAPITALS = {
    "AC": (-9.9754, -67.8103),
    "AL": (-9.6658, -35.7353),
    "AM": (-3.1190, -60.0217),
    "AP": (0.0349, -51.0694),
    "BA": (-12.9714, -38.5124),
    "CE": (-3.7172, -38.5433),
    "DF": (-15.7975, -47.8919),
    "ES": (-20.3155, -40.3128),
    "GO": (-16.6869, -49.2648),
    "MA": (-2.5297, -44.3028),
    "MG": (-19.9167, -43.9345),
    "MS": (-20.4697, -54.6201),
    "MT": (-15.6014, -56.0979),
    "PA": (-1.4558, -48.5024),
    "PB": (-7.1195, -34.8450),
    "PE": (-8.0476, -34.8770),
    "PI": (-5.0892, -42.8019),
    "PR": (-25.4284, -49.2733),
    "RJ": (-22.9068, -43.1729),
    "RN": (-5.7945, -35.2110),
    "RO": (-8.7619, -63.9020),
    "RR": (2.8196, -60.6714),
    "RS": (-30.0346, -51.2177),
    "SC": (-27.5954, -48.5480),
    "SE": (-10.9091, -37.0677),
    "SP": (-23.5505, -46.6333),
    "TO": (-10.1753, -48.2982),
}

# UF → macro region mapping
UF_TO_REGIAO = {
    "AC": "Norte",
    "AM": "Norte",
    "AP": "Norte",
    "PA": "Norte",
    "RO": "Norte",
    "RR": "Norte",
    "TO": "Norte",
    "AL": "Nordeste",
    "BA": "Nordeste",
    "CE": "Nordeste",
    "MA": "Nordeste",
    "PB": "Nordeste",
    "PE": "Nordeste",
    "PI": "Nordeste",
    "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste",
    "GO": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "MT": "Centro-Oeste",
    "ES": "Sudeste",
    "MG": "Sudeste",
    "RJ": "Sudeste",
    "SP": "Sudeste",
    "PR": "Sul",
    "RS": "Sul",
    "SC": "Sul",
}


def haversine_vectorized(
    lats: np.ndarray, lons: np.ndarray, lat_ref: float, lon_ref: float
) -> np.ndarray:
    """Vectorized Haversine distance calculation.

    Args:
        lats: Array of latitudes.
        lons: Array of longitudes.
        lat_ref: Reference latitude.
        lon_ref: Reference longitude.

    Returns:
        np.ndarray: Distances in kilometers.
    """
    R = 6371.0
    lat1 = np.radians(lats)
    lon1 = np.radians(lons)
    lat2 = math.radians(lat_ref)
    lon2 = math.radians(lon_ref)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


_IBGE_YEAR = 2020


def _resolve_cache_file(cache_dir: Optional[str], filename: str) -> Optional[Path]:
    """Return a Path for ``filename`` inside ``cache_dir``, or None if no cache_dir."""
    if cache_dir is None:
        return None
    return Path(cache_dir) / filename


class _IBGEGeocoder:
    """Caches IBGE municipal boundaries and performs spatial joins.

    Uses geobr to load Brazilian municipal boundaries and provides
    point-in-polygon lookups via geopandas spatial index.

    Supports two caching layers:
    - In-memory (class-level): avoids reloading within the same process.
    - Disk (optional): avoids re-downloading across executions. Controlled
      by the ``cache_dir`` parameter passed to each load method.
    """

    _municipios_cache = None
    _uf_cache = None

    @classmethod
    def _load_municipios(cls, cache_dir: Optional[str] = None):
        """Load IBGE municipal boundaries, using disk cache when available."""
        if cls._municipios_cache is not None:
            return cls._municipios_cache

        cache_file = _resolve_cache_file(cache_dir, f"ibge_municipios_{_IBGE_YEAR}.parquet")

        if cache_file is not None and cache_file.exists():
            logger.info("Loading IBGE municipal boundaries from disk cache...")
            import geopandas as gpd

            gdf = gpd.read_parquet(cache_file)
            cls._municipios_cache = gdf
            return gdf

        try:
            import geobr
        except ImportError:
            raise ImportError(
                "geobr is required for GeoFeatures. Install it with: pip install geobr"
            )

        logger.info("Downloading IBGE municipal boundaries (first time, may take a minute)...")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gdf = geobr.read_municipality(year=_IBGE_YEAR)
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        if cache_file is not None:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            import geopandas as gpd

            gdf.to_parquet(cache_file)
            logger.info(f"Saved {len(gdf)} municipalities to disk cache: {cache_file}")
        else:
            logger.info(f"Loaded {len(gdf)} municipalities")

        cls._municipios_cache = gdf
        return gdf

    @classmethod
    def _load_ufs(cls, cache_dir: Optional[str] = None):
        """Load IBGE state boundaries, using disk cache when available."""
        if cls._uf_cache is not None:
            return cls._uf_cache

        cache_file = _resolve_cache_file(cache_dir, f"ibge_states_{_IBGE_YEAR}.parquet")

        if cache_file is not None and cache_file.exists():
            logger.info("Loading IBGE state boundaries from disk cache...")
            import geopandas as gpd

            gdf = gpd.read_parquet(cache_file)
            cls._uf_cache = gdf
            return gdf

        try:
            import geobr
        except ImportError:
            raise ImportError(
                "geobr is required for GeoFeatures. Install it with: pip install geobr"
            )

        logger.info("Downloading IBGE state boundaries...")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gdf = geobr.read_state(year=_IBGE_YEAR)
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        if cache_file is not None:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            import geopandas as gpd

            gdf.to_parquet(cache_file)
            logger.info(f"Saved state boundaries to disk cache: {cache_file}")

        cls._uf_cache = gdf
        return gdf

    @classmethod
    def geocode_points(
        cls, lats: np.ndarray, lons: np.ndarray, cache_dir: Optional[str] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Geocode arrays of lat/lon points to municipal, state, and region info.

        Args:
            lats: Array of latitudes.
            lons: Array of longitudes.

        Returns:
            Tuple of (municipio_names, uf_codes, regiao_names) arrays.
            Unmatched points get "sin_dato".
        """
        import geopandas as gpd
        from shapely.geometry import Point

        gdf = cls._load_municipios(cache_dir)

        # Create GeoDataFrame of points
        points = [Point(lon, lat) for lat, lon in zip(lats, lons)]
        gdf_points = pd.DataFrame({"lat": lats, "lon": lons})
        gdf_points["geometry"] = points
        gdf_points = gpd.GeoDataFrame(gdf_points, geometry="geometry", crs="EPSG:4326")

        # Spatial join
        joined = gpd.sjoin(
            gdf_points,
            gdf[["name_muni", "abbrev_state", "geometry"]],
            how="left",
            predicate="within",
        )

        # Points on polygon borders can match multiple municipalities — keep first match only.
        joined = joined[~joined.index.duplicated(keep="first")]

        municipio = joined["name_muni"].fillna("sin_dato").values
        uf = joined["abbrev_state"].fillna("XX").values
        regiao = np.array([UF_TO_REGIAO.get(u, "sin_dato") for u in uf])

        return municipio, uf, regiao


class GeoFeatures(BaseEstimator, TransformerMixin):
    """Extracts geographic features from latitude and longitude columns.

    Global transformer that appends new columns to the DataFrame:
    - Geographic hierarchy: estado (UF), município, região (macro region)
    - Distance features: to state capital, to reference cities
    - Optional target encoding for categorical geo features
    - Optional raw normalized coordinates

    Parameters:
    -----------
    lat_col : str
        Name of the latitude column (default: "latitud").
    lon_col : str
        Name of the longitude column (default: "longitud").
    include_hierarchy : bool
        Include estado, município, região columns (default: True).
    include_target_encoding : bool
        Apply target encoding to categorical geo columns (default: True).
    te_w : int
        Smoothing weight for target encoding (default: 20).
    include_distances : bool
        Include distance-based features (default: True).
    distance_cities : list or None
        List of city names for distance calculation. If None, uses top 5.
        Available: sao_paulo, rio_de_janeiro, brasilia, salvador, belo_horizonte,
        fortaleza, recife, curitiba, manaus, porto_alegre.
    include_coords : bool
        Replace lat/lon columns with normalized versions geo_lat_norm and geo_lon_norm (default: False).
    cache_dir : str or None
        Directory to store downloaded IBGE shapefiles as parquet files. If set,
        the first run saves the files to disk and subsequent runs load from
        there instead of re-downloading via geobr. Recommended: ".cache/ibge".
        If None (default), data is only cached in memory for the current process.

    YAML configuration example:
    ---------------------------
    preprocessing:
      columns:
        # ... other columns
      global_transformers:
        - geo_features:
            lat_col: "latitud"
            lon_col: "longitud"
            include_hierarchy: true
            include_target_encoding: true
            te_w: 20
            include_distances: true
            distance_cities:
              - sao_paulo
              - rio_de_janeiro
              - brasilia
            include_coords: false
            cache_dir: ".cache/ibge"
    """

    def __init__(
        self,
        lat_col: str = "latitud",
        lon_col: str = "longitud",
        include_hierarchy: bool = True,
        include_target_encoding: bool = True,
        te_w: int = 20,
        include_distances: bool = True,
        distance_cities: Optional[List[str]] = None,
        include_coords: bool = False,
        cache_dir: Optional[str] = None,
    ):
        self.lat_col = lat_col
        self.lon_col = lon_col
        self.include_hierarchy = include_hierarchy
        self.include_target_encoding = include_target_encoding
        self.te_w = te_w
        self.include_distances = include_distances
        self.distance_cities = distance_cities or [
            "sao_paulo",
            "rio_de_janeiro",
            "brasilia",
            "salvador",
            "belo_horizonte",
        ]
        self.include_coords = include_coords
        self.cache_dir = cache_dir

    def fit(self, X: pd.DataFrame, y: pd.Series = None) -> "GeoFeatures":
        """Learn target encoding mappings from training data.

        Args:
            X: Training DataFrame with lat/lon columns.
            y: Target Series (required if include_target_encoding=True).

        Returns:
            self: The fitted transformer.
        """
        # Validate city names (here instead of __init__ to be sklearn-compatible)
        for city in self.distance_cities:
            if city not in REFERENCE_CITIES:
                raise ValueError(
                    f"Unknown city '{city}'. Available: {list(REFERENCE_CITIES.keys())}"
                )

        # Geocode all training points to learn the mapping
        lats = X[self.lat_col].values.astype(float)
        lons = X[self.lon_col].values.astype(float)

        # Handle null coordinates
        valid_mask = ~(np.isnan(lats) | np.isnan(lons))

        if self.include_hierarchy or self.include_target_encoding:
            self.municipio_names_, self.uf_codes_, self.regiao_names_ = (
                _IBGEGeocoder.geocode_points(lats[valid_mask], lons[valid_mask], self.cache_dir)
            )

            # Fit target encoding if enabled and y is provided
            if self.include_target_encoding and y is not None:
                self._fit_target_encoding(X, y, valid_mask)
            else:
                self.te_mappings_ = {}

        # Compute coordinate normalization stats
        if self.include_coords:
            self.lat_mean_ = np.nanmean(lats)
            self.lat_std_ = np.nanstd(lats)
            self.lon_mean_ = np.nanmean(lons)
            self.lon_std_ = np.nanstd(lons)

        return self

    def _fit_target_encoding(self, X: pd.DataFrame, y: pd.Series, valid_mask: np.ndarray):
        """Fit target encoding for geographic categorical features.

        Args:
            X: Training DataFrame.
            y: Target Series.
            valid_mask: Boolean mask of valid coordinates.
        """
        self.te_mappings_ = {}
        global_mean = y.mean()

        geo_columns = {
            "geo_estado": self.uf_codes_,
            "geo_municipio": self.municipio_names_,
            "geo_regiao": self.regiao_names_,
        }

        y_valid = y.values[valid_mask]

        for col_name, geo_values in geo_columns.items():
            df_te = pd.DataFrame({"geo_cat": geo_values, "target": y_valid})
            te = df_te.groupby("geo_cat")["target"].agg(["mean", "count"]).reset_index()
            te[col_name + "_prob"] = ((te["mean"] * te["count"]) + (global_mean * self.te_w)) / (
                te["count"] + self.te_w
            )
            self.te_mappings_[col_name] = te.set_index("geo_cat")[col_name + "_prob"].to_dict()
            # Store global mean for unseen categories
            self.te_mappings_[col_name + "_global_mean"] = global_mean

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Apply geographic feature extraction.

        Args:
            X: Input DataFrame with lat/lon columns.

        Returns:
            pd.DataFrame: Original DataFrame with new geographic feature columns appended.
        """
        df = X.copy()
        lats = df[self.lat_col].values.astype(float)
        lons = df[self.lon_col].values.astype(float)
        # Ensure lat/lon are float in the output (source may be object dtype)
        df[self.lat_col] = lats
        df[self.lon_col] = lons

        # Handle nulls: fill with sentinel, will be handled after geocoding
        valid_mask = ~(np.isnan(lats) | np.isnan(lons))

        # 1. Geographic hierarchy + distances (both may need estado_arr)
        if self.include_hierarchy or self.include_target_encoding or self.include_distances:
            geocoded = _IBGEGeocoder.geocode_points(
                lats[valid_mask], lons[valid_mask], self.cache_dir
            )
            geo_municipio, geo_uf, geo_regiao = geocoded

            # Build full arrays (NaN for invalid points)
            n = len(df)
            estado_arr = np.full(n, "sin_dato", dtype=object)
            municipio_arr = np.full(n, "sin_dato", dtype=object)
            regiao_arr = np.full(n, "sin_dato", dtype=object)

            estado_arr[valid_mask] = geo_uf
            municipio_arr[valid_mask] = geo_municipio
            regiao_arr[valid_mask] = geo_regiao

            if self.include_hierarchy:
                df["geo_estado"] = pd.Categorical(estado_arr)
                df["geo_municipio"] = pd.Categorical(municipio_arr)
                df["geo_regiao"] = pd.Categorical(regiao_arr)

            # 2. Target encoding
            if self.include_target_encoding and self.te_mappings_:
                for col_name, geo_values in [
                    ("geo_estado", estado_arr),
                    ("geo_municipio", municipio_arr),
                    ("geo_regiao", regiao_arr),
                ]:
                    if col_name in self.te_mappings_:
                        mapping = self.te_mappings_[col_name]
                        global_mean = self.te_mappings_[col_name + "_global_mean"]
                        te_col = col_name + "_prob"
                        df[te_col] = np.array(
                            [mapping.get(v, global_mean) for v in geo_values], dtype=float
                        )
                # Drop raw string hierarchy columns — replaced by *_prob float columns
                df = df.drop(columns=["geo_estado", "geo_municipio", "geo_regiao"], errors="ignore")

        # 3. Distance features
        if self.include_distances:
            # Distance to state capital
            df["geo_dist_capital_estado"] = self._compute_capital_distances(lats, lons, estado_arr)
            # Distance to reference cities
            for city_name in self.distance_cities:
                city_lat, city_lon = REFERENCE_CITIES[city_name]
                df[f"geo_dist_{city_name}"] = haversine_vectorized(lats, lons, city_lat, city_lon)

        # 4. Raw coordinates (normalized, drop originals)
        if self.include_coords:
            df["geo_lat_norm"] = (lats - self.lat_mean_) / self.lat_std_
            df["geo_lon_norm"] = (lons - self.lon_mean_) / self.lon_std_
            df = df.drop(columns=[self.lat_col, self.lon_col])

        return df

    def _compute_capital_distances(
        self, lats: np.ndarray, lons: np.ndarray, estados: np.ndarray
    ) -> np.ndarray:
        """Compute distance to state capital for each point.

        Args:
            lats: Latitude array.
            lons: Longitude array.
            estados: UF code array.

        Returns:
            np.ndarray: Distances in km (NaN for unknown state).
        """
        distances = np.full(len(lats), np.nan)
        for uf, (cap_lat, cap_lon) in STATE_CAPITALS.items():
            mask = estados == uf
            if mask.any():
                distances[mask] = haversine_vectorized(lats[mask], lons[mask], cap_lat, cap_lon)
        return distances
