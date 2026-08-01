"""
Geographic feature extraction from latitude/longitude coordinates.

Extracts geographic hierarchy (estado, município, região), distance-based features,
and optional target-encoded categorical features using IBGE shapefiles via geobr.
"""

import logging
import math
import unicodedata
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

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
    "concordia": (-27.2339, -52.0278),
    "jaragua_do_sul": (-26.4852, -49.0715),
    "joacaba": (-27.1728, -51.5058),
    "videira": (-27.0095, -51.1490),
    "sao_miguel_do_oeste": (-26.7280, -53.5155),
    "tubarao": (-28.4678, -49.0075),
    "rio_do_sul": (-27.2147, -49.6435),
    "mafra": (-26.1108, -49.8011),
    "sao_bento_do_sul": (-26.2499, -49.3789),
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
_VALID_HIERARCHY_LEVELS = {"estado", "municipio", "regiao"}

_HIERARCHY_ALIASES = {
    "state": "estado",
    "municipality": "municipio",
    "city": "municipio",
    "region": "regiao",
}


def _geo_column_name(level: str) -> str:
    """Return the output column name for a hierarchy level (e.g. 'estado' → 'geo_estado')."""
    return f"geo_{level}"


def _normalize_name(name: str) -> str:
    """Remove accents and uppercase — used to match IBGE municipality names to CSV city names."""
    nfkd = unicodedata.normalize("NFKD", str(name))
    return nfkd.encode("ascii", "ignore").decode("ascii").upper().strip()


def _load_regions_mapping(path: str) -> Dict[str, str]:
    """Load a ``region``/``city`` file (CSV with semicolon separator or Parquet) and return a normalized city → region dict."""
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    df.columns = [c.strip().upper() for c in df.columns]

    missing = [col for col in ["REGION", "CITY"] if col not in df.columns]
    if missing:
        raise ValueError(
            f"regions_file '{path}' is missing required column(s): {missing}. "
            f"Found columns: {df.columns.tolist()}. "
            f"Expected 'REGION' and 'CITY' (semicolon-separated CSV)."
        )

    df["CITY"] = df["CITY"].str.strip().apply(_normalize_name)
    df["REGION"] = df["REGION"].str.strip()
    return dict(zip(df["CITY"], df["REGION"]))


def _resolve_hierarchy_levels(
    include_hierarchy: Union[bool, List[str]],
) -> List[tuple]:
    """Normalise *include_hierarchy* to a list of (display_name, data_key) pairs.

    Each pair maps the user-facing level name (used for column naming) to the
    internal data key (used for array lookups).  When ``True`` is passed, all
    three levels are included with display names equal to data keys.

    Args:
        include_hierarchy: ``True`` → all three levels; ``False`` → empty list;
            list of strings → validated subset.  Aliases like ``"municipality"``
            resolve to ``("municipality", "municipio")`` — the original name
            is preserved for column naming.

    Returns:
        List of ``(display_name, data_key)`` tuples sorted by data_key.

    Raises:
        ValueError: If the list contains invalid level names.
    """
    if isinstance(include_hierarchy, bool):
        if not include_hierarchy:
            return []
        return [(lvl, lvl) for lvl in sorted(_VALID_HIERARCHY_LEVELS)]

    result = []
    seen_keys = set()
    for lvl in include_hierarchy:
        data_key = _HIERARCHY_ALIASES.get(lvl, lvl)
        if data_key not in _VALID_HIERARCHY_LEVELS:
            valid_display = sorted(_VALID_HIERARCHY_LEVELS) + sorted(_HIERARCHY_ALIASES)
            raise ValueError(f"Invalid hierarchy level: '{lvl}'. Valid levels: {valid_display}")
        if data_key in seen_keys:
            continue  # deduplicate
        seen_keys.add(data_key)
        result.append((lvl, data_key))

    # Sort by data_key for deterministic order
    return sorted(result, key=lambda pair: pair[1])


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
        cls,
        lats: np.ndarray,
        lons: np.ndarray,
        cache_dir: Optional[str] = None,
        chunk_size: int = 500_000,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Geocode arrays of lat/lon points to municipal, state, and region info.

        Processes in chunks of *chunk_size* to cap peak memory on large arrays
        (e.g. 3.4M inference points). The result is identical to the unchunked
        version: same spatial join and same per-point dedup, just applied block
        by block so the full points GeoDataFrame is never materialized at once.

        Args:
            lats: Array of latitudes.
            lons: Array of longitudes.
            cache_dir: Optional IBGE cache directory.
            chunk_size: Number of points per spatial-join batch (default 500k).

        Returns:
            Tuple of (municipio_names, uf_codes, regiao_names) arrays.
            Unmatched points get "sin_dato".
        """
        gdf = cls._load_municipios(cache_dir)
        n = len(lats)
        if n <= chunk_size:
            municipio, uf = cls._geocode_chunk(lats, lons, gdf)
        else:
            mun_parts, uf_parts = [], []
            for start in range(0, n, chunk_size):
                end = start + chunk_size
                m, u = cls._geocode_chunk(lats[start:end], lons[start:end], gdf)
                mun_parts.append(m)
                uf_parts.append(u)
            municipio = np.concatenate(mun_parts)
            uf = np.concatenate(uf_parts)
        regiao = np.array([UF_TO_REGIAO.get(u, "sin_dato") for u in uf])
        return municipio, uf, regiao

    @classmethod
    def _geocode_chunk(
        cls, lats: np.ndarray, lons: np.ndarray, gdf
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Spatial-join one chunk of points against the municipios gdf.

        Returns (municipio, uf) arrays. Points on polygon borders can match
        multiple polygons — keep the first match by index (local dedup).
        """
        import geopandas as gpd
        from shapely.geometry import Point

        points = [Point(lon, lat) for lat, lon in zip(lats, lons)]
        gdf_points = gpd.GeoDataFrame(
            {"lat": lats, "lon": lons, "geometry": points}, crs="EPSG:4326"
        )
        joined = gpd.sjoin(
            gdf_points,
            gdf[["name_muni", "abbrev_state", "geometry"]],
            how="left",
            predicate="within",
        )
        joined = joined[~joined.index.duplicated(keep="first")]
        municipio = joined["name_muni"].fillna("sin_dato").values
        uf = joined["abbrev_state"].fillna("XX").values
        return municipio, uf


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
    include_hierarchy : bool or list of str
        ``True`` → include all three hierarchy columns (``geo_estado``,
        ``geo_municipio``, ``geo_regiao``).  ``False`` → skip hierarchy.
        A list of level names (``"estado"``, ``"municipio"``, ``"regiao"``)
        enables only the specified levels (default: ``True``).
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
    regions_file : str or None
        Path to a CSV (semicolon separator) or Parquet file with columns
        ``REGION`` and ``CITY``. When provided, ``geo_regiao`` is assigned by matching each
        point's IBGE municipality name against the ``CITY`` column (accent- and
        case-insensitive). Takes priority over ``region_cities``. Unmatched
        municipalities get ``"sin_dato"``.
    region_cities : list of str or None
        When set (and ``regions_file`` is not provided), ``geo_regiao`` is assigned
        as the **nearest city** from this list instead of the IBGE macro-region
        (Norte/Sul/etc.). Each entry must be a key in ``REFERENCE_CITIES``.

    Attributes (set after fit):
    ---------------------------
    unmatched_municipalities_ : list of str
        Sorted list of IBGE municipality names (normalized) that were NOT found
        in ``regions_file``. Empty when ``regions_file`` is not provided.
        Useful for debugging missing matches.
    matched_municipalities_ : list of str
        Sorted list of IBGE municipality names (normalized) that WERE found
        in ``regions_file``. Empty when ``regions_file`` is not provided.

    YAML configuration example:
    ---------------------------
    preprocessing:
      columns:
        # ... other columns
      global_transformers:
        - geo_features:
            lat_col: "latitud"
            lon_col: "longitud"
            include_hierarchy: true                # all three levels
            # include_hierarchy:                   # or pick specific levels
            #   - estado
            #   - municipio
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
        include_hierarchy: Union[bool, List[str]] = True,
        include_target_encoding: bool = True,
        te_w: int = 20,
        include_distances: bool = True,
        distance_cities: Optional[List[str]] = None,
        include_coords: bool = False,
        cache_dir: Optional[str] = None,
        region_cities: Optional[List[str]] = None,
        regions_file: Optional[str] = None,
        include_cluster: bool = False,
        n_clusters: int = 10,
        random_state: int = 42,
        geo_model_path: Optional[str] = None,
    ):
        # ADR-0001: GeoFeatures owns geographic clustering. include_cluster defaults to
        # False so existing global_transformers usage (hierarchy/distances only) is
        # unchanged; GeoFeaturesETL and dataset builders pass True explicitly.
        self.include_cluster = include_cluster
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.geo_model_path = geo_model_path
        # Set True by load() so a later fit() skips refitting clustering.
        self._cluster_loaded_ = False
        self.lat_col = lat_col
        self.lon_col = lon_col
        self.include_hierarchy = include_hierarchy
        self.hierarchy_levels_ = _resolve_hierarchy_levels(include_hierarchy)
        # Convenience sets for internal checks (data_key only)
        self._hierarchy_data_keys_ = {dk for _, dk in self.hierarchy_levels_}
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
        self.region_cities = region_cities
        self.regions_file = regions_file

    def _apply_regions_mapping(self, municipio_arr: np.ndarray, log: bool = False) -> np.ndarray:
        """Map municipality names to regions using *regions_mapping_*.

        Both the mapping keys and the municipality names are normalised with
        :func:`_normalize_name` (NFKD + strip accents + upper + strip) so the
        comparison is accent- and case-insensitive.

        Parameters
        ----------
        municipio_arr : np.ndarray
            Array of raw IBGE municipality names (may contain accents,
            mixed case, etc.).
        log : bool
            If True, log matched and unmatched municipalities at INFO level.
            Typically True on ``fit()`` and False on ``transform()``.

        Returns
        -------
        np.ndarray
            Array of region names (or ``"sin_dato"`` for unmatched).
        """
        result = np.array(
            [self.regions_mapping_.get(_normalize_name(m), "sin_dato") for m in municipio_arr],
            dtype=object,
        )

        if log and self.regions_mapping_:
            normalized_munis = {_normalize_name(m) for m in municipio_arr if m != "sin_dato"}
            mapping_keys = set(self.regions_mapping_.keys())
            matched = sorted(normalized_munis & mapping_keys)
            unmatched = sorted(normalized_munis - mapping_keys)
            total = len(normalized_munis)
            n_matched = len(matched)
            n_unmatched = len(unmatched)

            logger.info(
                "regions_file match: %d/%d municipalities resolved (%d matched, %d unmatched)",
                n_matched,
                total,
                n_matched,
                n_unmatched,
            )
            if matched:
                logger.info("Matched municipalities: %s", matched)
            if unmatched:
                logger.warning(
                    "Unmatched municipalities (not found in regions_file): %s — "
                    "these will get 'sin_dato'. "
                    "Tip: check that your regions_file CITY column contains these "
                    "names (accent/case does not matter, but spelling must match after "
                    "removing accents and normalizing).",
                    unmatched,
                )

        return result

    def _compute_nearest_city(
        self, lats: np.ndarray, lons: np.ndarray, valid_mask: np.ndarray
    ) -> np.ndarray:
        """Assign each valid point the name of its nearest city in ``region_cities``.

        Args:
            lats: Full latitude array (all rows).
            lons: Full longitude array (all rows).
            valid_mask: Boolean mask indicating valid coordinates.

        Returns:
            Object array of city names; invalid points get ``"sin_dato"``.
        """
        result = np.full(len(lats), "sin_dato", dtype=object)
        if not valid_mask.any():
            return result
        valid_lats = lats[valid_mask]
        valid_lons = lons[valid_mask]
        city_names = self.region_cities
        distances = np.column_stack(
            [haversine_vectorized(valid_lats, valid_lons, *REFERENCE_CITIES[c]) for c in city_names]
        )
        nearest = np.argmin(distances, axis=1)
        result[valid_mask] = [city_names[i] for i in nearest]
        return result

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
        if self.region_cities:
            for city in self.region_cities:
                if city not in REFERENCE_CITIES:
                    raise ValueError(
                        f"Unknown region_city '{city}'. Available: {list(REFERENCE_CITIES.keys())}"
                    )

        # Geocode all training points to learn the mapping
        lats = X[self.lat_col].values.astype(float)
        lons = X[self.lon_col].values.astype(float)

        # Handle null coordinates
        valid_mask = ~(np.isnan(lats) | np.isnan(lons))

        self.regions_mapping_: Dict[str, str] = (
            _load_regions_mapping(self.regions_file) if self.regions_file else {}
        )

        # Track unmatched municipalities for diagnostics (empty list when no regions_file)
        self.unmatched_municipalities_: List[str] = []
        self.matched_municipalities_: List[str] = []

        if self.hierarchy_levels_ or self.include_target_encoding:
            self.municipio_names_, self.uf_codes_, self.regiao_names_ = (
                _IBGEGeocoder.geocode_points(lats[valid_mask], lons[valid_mask], self.cache_dir)
            )
            if self.regions_mapping_ and "regiao" in self._hierarchy_data_keys_:
                self.regiao_names_ = self._apply_regions_mapping(self.municipio_names_, log=True)
                # Populate diagnostics attributes
                normalized_munis = {
                    _normalize_name(m) for m in self.municipio_names_ if m != "sin_dato"
                }
                mapping_keys = set(self.regions_mapping_.keys())
                self.unmatched_municipalities_ = sorted(normalized_munis - mapping_keys)
                self.matched_municipalities_ = sorted(normalized_munis & mapping_keys)
            elif self.region_cities and "regiao" in self._hierarchy_data_keys_:
                self.regiao_names_ = self._compute_nearest_city(lats, lons, valid_mask)[valid_mask]

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

        # --- Geographic clustering (KMeans) - ADR-0001: owned by the transformer ---
        # fit() is pure (no disk). The load-or-fit decision is the caller's: if load()
        # ran first, _cluster_loaded_ is True and we skip refitting so the trained model
        # is preserved (only hierarchy refits from data).
        if self.include_cluster and not self._cluster_loaded_:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler

            cluster_valid = ~(np.isnan(lats) | np.isnan(lons) | ((lats == 0) & (lons == 0)))
            n_valid = int(cluster_valid.sum())
            if n_valid < 10:
                raise ValueError(
                    f"GeoFeatures: only {n_valid} valid coordinates for clustering. "
                    "Need at least 10."
                )
            coords = np.column_stack([lats[cluster_valid], lons[cluster_valid]])
            n_clusters = min(self.n_clusters, n_valid)
            scaler = StandardScaler()
            coords_scaled = scaler.fit_transform(coords)
            kmeans = KMeans(n_clusters=n_clusters, random_state=self.random_state, n_init=10)
            kmeans.fit(coords_scaled)
            self.scaler_ = scaler
            self.kmeans_ = kmeans
            self.n_clusters_ = n_clusters
            logger.info(
                "  GeoFeatures: %d clusters fitted on %d valid coordinates",
                n_clusters,
                n_valid,
            )

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

        geo_arrays = {
            "estado": self.uf_codes_,
            "municipio": self.municipio_names_,
            "regiao": self.regiao_names_,
        }

        geo_columns = {
            _geo_column_name(display): geo_arrays[data_key]
            for display, data_key in self.hierarchy_levels_
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

        # --- Geographic clustering (KMeans) - ADR-0001 ---
        if self.include_cluster:
            if not hasattr(self, "kmeans_"):
                raise ValueError(
                    "GeoFeatures: include_cluster=True but the transformer is not "
                    "fitted (no kmeans_). Call fit(include_cluster=True) or load() first."
                )
            cluster_valid = ~(np.isnan(lats) | np.isnan(lons) | ((lats == 0) & (lons == 0)))
            labels = np.full(len(df), -1, dtype=int)
            if cluster_valid.any():
                coords = np.column_stack([lats[cluster_valid], lons[cluster_valid]])
                labels[cluster_valid] = self.kmeans_.predict(self.scaler_.transform(coords))
            df["geo_cluster"] = labels

        # 1. Geographic hierarchy + distances (both may need estado_arr)
        if self.hierarchy_levels_ or self.include_target_encoding or self.include_distances:
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
            if self.regions_mapping_ and "regiao" in self._hierarchy_data_keys_:
                regiao_arr = self._apply_regions_mapping(municipio_arr, log=False)
            elif self.region_cities and "regiao" in self._hierarchy_data_keys_:
                regiao_arr = self._compute_nearest_city(lats, lons, valid_mask)
            else:
                regiao_arr[valid_mask] = geo_regiao

            if self.hierarchy_levels_:
                for display, data_key in self.hierarchy_levels_:
                    col_name = _geo_column_name(display)
                    arr = {"estado": estado_arr, "municipio": municipio_arr, "regiao": regiao_arr}[
                        data_key
                    ]
                    df[col_name] = pd.Categorical(arr)

            # 2. Target encoding
            if self.include_target_encoding and self.te_mappings_:
                te_cols_to_drop = []
                for display, data_key in self.hierarchy_levels_:
                    col_name = _geo_column_name(display)
                    if col_name not in self.te_mappings_:
                        continue
                    arr = {"estado": estado_arr, "municipio": municipio_arr, "regiao": regiao_arr}[
                        data_key
                    ]
                    mapping = self.te_mappings_[col_name]
                    global_mean = self.te_mappings_[col_name + "_global_mean"]
                    te_col = col_name + "_prob"
                    df[te_col] = np.array([mapping.get(v, global_mean) for v in arr], dtype=float)
                    te_cols_to_drop.append(col_name)
                # Drop raw string hierarchy columns — replaced by *_prob float columns
                df = df.drop(columns=te_cols_to_drop, errors="ignore")

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

    def save(self, path: Optional[str] = None) -> "GeoFeatures":
        """Persist the fitted clustering model ({scaler, kmeans, n_clusters}).

        ADR-0001: fit does NOT persist; persistence is explicit here, mirroring
        BaseFeatureEngineering.save. Only the clustering model is carried across
        train->infer - hierarchy is refit from data every run.
        """
        from energizados.core.utils.integrity_pickle import dump

        target = path or self.geo_model_path
        if not target:
            raise ValueError("GeoFeatures.save: no path given and geo_model_path is unset")
        if not hasattr(self, "kmeans_"):
            raise ValueError(
                "GeoFeatures.save: nothing to persist - fit(include_cluster=True) first"
            )
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        dump(
            {"scaler": self.scaler_, "kmeans": self.kmeans_, "n_clusters": self.n_clusters_},
            target,
        )
        logger.info("  GeoFeatures: saved geo model to '%s'", target)
        return self

    def load(self, path: Optional[str] = None) -> "GeoFeatures":
        """Load a persisted clustering model and mark clustering as pre-loaded.

        After load, a subsequent fit SKIPS refitting clustering (it keeps the loaded
        model) but still fits hierarchy from data. The load-or-fit decision (does the
        file exist?) belongs to the caller.
        """
        from energizados.core.utils.integrity_pickle import load

        target = path or self.geo_model_path
        if not target:
            raise ValueError("GeoFeatures.load: no path given and geo_model_path is unset")
        model = load(target)
        self.scaler_ = model["scaler"]
        self.kmeans_ = model["kmeans"]
        self.n_clusters_ = model["n_clusters"]
        self.include_cluster = True
        self._cluster_loaded_ = True
        logger.info("  GeoFeatures: loaded geo model from '%s'", target)
        return self

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
