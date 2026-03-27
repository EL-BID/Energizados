"""Pipeline ETL Module for Multi-Source Data Processing.

This module provides ETL classes for data processing:
- SourceETL: Concatenation and merge operations on multiple sources.
- ClipOutliersETL: Clips extreme values in numeric columns (data reading errors).
- GeoClusterETL: Adds a geo_cluster column via KMeans on lat/lon coordinates.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from energizados.core.exceptions import ETLError
from energizados.core.utils.import_utils import import_class
from energizados.etl.base import BaseETL

logger = logging.getLogger(__name__)


class SourceETL(BaseETL):
    """ETL to process one or multiple data sources.

    This class processes data from one or several files and generates processed output.
    Supports two operating modes:

    - **concat**: Concatenates multiple dataframes vertically (default)
    - **merge**: Joins multiple dataframes horizontally using merge_config

    Args:
        name: Name of the source (e.g.: 'consumos', 'inspecciones', 'clientes').
        input_paths: List with paths to raw data files.
        output_path: Path to save processed data.
        mode: Processing mode ('concat' or 'merge'). Default: 'concat'.
        merge_config: Configuration for merge (required if mode='merge').
            Ex: {'how': 'left', 'on': 'id_cliente'}
            Options: how ('left', 'right', 'inner', 'outer'), on (column),
                      left_on, right_on, left_index, right_index.
        key_column: Key column used by default in merge_config.
        transform_fn: Optional custom transform function. Can be:
            - None (default): No custom transform
            - str: Dotted path to a function (e.g., 'src.data.transforms.clean_data')
            - Callable: A function with signature (pd.DataFrame) -> pd.DataFrame
        sample: Optional number of rows to sample from input data.
            If specified, reads only this many rows (uses random_state=42 for reproducibility).
            If None (default), reads all data.
        **kwargs: Additional parameters.

    Example:
        >>> etl = SourceETL(
        ...     name='consumos',
        ...     mode='concat',
        ...     input_paths=['data/raw/consumos.csv'],
        ...     output_path='data/consumos.parquet',
        ... )
        >>> df = etl.run('data/consumos.parquet')

    Example with merge:
        >>> etl = SourceETL(
        ...     name='merged',
        ...     mode='merge',
        ...     input_paths=['data/consumos.parquet', 'data/clientes.parquet'],
        ...     output_path='data/merged.parquet',
        ...     merge_config={'how': 'left', 'on': 'id_cliente'},
        ... )
        >>> df = etl.run('data/merged.parquet')

    Example with custom transform:
        >>> etl = SourceETL(
        ...     name='cleaned',
        ...     input_paths=['data/raw/dirty.csv'],
        ...     output_path='data/cleaned.parquet',
        ...     transform_fn='src.data.transforms.clean_data',
        ... )
        >>> df = etl.run('data/cleaned.parquet')

    Example with sampling:
        >>> etl = SourceETL(
        ...     name='sample_data',
        ...     input_paths=['data/raw/full_dataset.csv'],
        ...     output_path='data/sample.parquet',
        ...     sample=1000,  # Read only 1000 rows for quick testing
        ... )
        >>> df = etl.run('data/sample.parquet')
    """

    def __init__(
        self,
        name: str,
        input_paths: List[str],
        output_path: Optional[str] = None,
        mode: str = "concat",
        merge_config: Optional[Dict[str, Any]] = None,
        key_column: Optional[str] = None,
        input_params: Optional[Dict[str, Any]] = None,
        output_params: Optional[Dict[str, Any]] = None,
        transform_fn: Optional[Any] = None,
        sample: Optional[int] = None,
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self.mode = mode.lower() if mode else "concat"
        self.merge_config = merge_config
        self.key_column = key_column or "id_cliente"
        self.input_params = input_params or {}
        self.output_params = output_params or {}
        self.sample = sample
        self.kwargs = kwargs

        # Load transform_fn if provided
        self._transform_fn: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None
        if transform_fn is not None:
            if isinstance(transform_fn, str):
                # Load from dotted path
                self._transform_fn = import_class(transform_fn)
                logger.info(f"  • Loaded transform function: {transform_fn}")
            elif callable(transform_fn):
                # Use callable directly
                self._transform_fn = transform_fn
                logger.info("  • Using callable transform function")
            else:
                raise ValueError(
                    f"transform_fn must be a string path or callable, got {type(transform_fn)}"
                )

        # Validate mode
        if self.mode not in ("concat", "merge"):
            raise ValueError(f"Mode must be 'concat' or 'merge', not '{self.mode}'")

        # Validate merge_config if mode is merge
        if self.mode == "merge" and not self.merge_config:
            raise ValueError(
                f"SourceETL '{self.name}': mode='merge' requires merge_config "
                "(e.g.: {'how': 'left', 'on': 'id_cliente'})"
            )

    def extract(self) -> pd.DataFrame:
        """
        Extracts data from specified sources.

        Processes all input_paths according to configured mode:
        - concat: Concatenates all dataframes vertically
        - merge: Joins horizontally according to merge_config

        Returns:
            pd.DataFrame: Combined raw data

        Raises:
            ETLError: If data cannot be read
        """
        if not self.input_paths:
            raise ETLError(f"SourceETL '{self.name}': input_paths is empty")

        # Read all files
        from energizados.core.utils.secure_pickle import validate_no_traversal

        dataframes = []
        for path in self.input_paths:
            validate_no_traversal(path, label=f"ETL '{self.name}' input")
            source_file = Path(path)

            if not source_file.exists():
                raise ETLError(f"File not found: {path}")

            try:
                if source_file.suffix == ".csv":
                    df = pd.read_csv(path, **self.input_params)
                elif source_file.suffix in [".parquet", ".pq"]:
                    df = pd.read_parquet(path)
                elif source_file.suffix in [".xlsx", ".xls"]:
                    df = pd.read_excel(path)
                else:
                    raise ETLError(f"Unsupported format: {source_file.suffix}")

                dataframes.append(df)
                logger.info(f"  • Read {len(df)} records from '{source_file.name}'")

            except Exception as e:
                raise ETLError(f"Error extracting from '{path}': {str(e)}") from e

        # Combine according to mode
        if self.mode == "concat":
            if len(dataframes) == 1:
                result = dataframes[0]
            else:
                result = pd.concat(dataframes, axis=0, ignore_index=True)
                logger.info(f"  ✓ Concatenated {len(dataframes)} files: {len(result)} records")

        elif self.mode == "merge":
            result = self._merge_dataframes(dataframes)
            logger.info(f"  ✓ Merged {len(dataframes)} files: {len(result)} records")

        return result

    def _merge_dataframes(self, dataframes: List[pd.DataFrame]) -> pd.DataFrame:
        """
        Merges multiple dataframes according to merge_config.

        Args:
            dataframes: List of dataframes to merge

        Returns:
            pd.DataFrame: Merged dataframe

        Raises:
            ETLError: If merge fails
        """
        if not dataframes:
            raise ETLError("No dataframes to merge")

        if len(dataframes) == 1:
            return dataframes[0]

        # Prepare merge configuration
        config = self.merge_config.copy()
        how = config.pop("how", "left")
        on = config.pop("on", None)
        left_on = config.pop("left_on", None)
        right_on = config.pop("right_on", None)
        left_index = config.pop("left_index", False)
        right_index = config.pop("right_index", False)

        # If no columns specified, use key_column by default
        if on is None and left_on is None and right_on is None:
            on = self.key_column

        # Sequential merge: first with second, result with third, etc.
        result = dataframes[0]
        for i, df in enumerate(dataframes[1:], start=2):
            try:
                result = pd.merge(
                    result,
                    df,
                    how=how,
                    on=on,
                    left_on=left_on,
                    right_on=right_on,
                    left_index=left_index,
                    right_index=right_index,
                    **config,
                )
                logger.info(f"  • Merge step {i - 1}→{i}: {len(result)} records")
            except Exception as e:
                raise ETLError(f"Error in merge step {i - 1}→{i}: {str(e)}") from e

        return result

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms and cleans source data.

        Args:
            df: Raw DataFrame

        Returns:
            pd.DataFrame: Clean DataFrame

        Raises:
            ETLError: If transform_fn returns invalid type
        """
        df = df.copy()

        # Remove completely empty rows
        before_count = len(df)
        df = df.dropna(how="all")
        after_count = len(df)

        if before_count > after_count:
            logger.info(f"  • Removed {before_count - after_count} empty rows")

        # Apply custom transform function if provided
        if self._transform_fn is not None:
            logger.info("  • Applying custom transform function")
            df = self._transform_fn(df)

            # Validate return type
            if not isinstance(df, pd.DataFrame):
                raise ETLError(f"transform_fn must return pd.DataFrame, got {type(df).__name__}")

            logger.info(f"  ✓ Custom transform applied: {len(df)} records")

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Saves the transformed data.

        Args:
            df: Transformed DataFrame
            path: Output path

        Raises:
            ETLError: If data cannot be saved
        """
        try:
            from energizados.core.utils.secure_pickle import validate_no_traversal

            validate_no_traversal(path, label=f"ETL '{self.name}' output")
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.suffix == ".parquet" or output_path.suffix == ".pq":
                df.to_parquet(path, index=False)
            elif output_path.suffix == ".csv":
                df.to_csv(path, index=False, **self.output_params)
            else:
                df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

            logger.info(f"  ✓ Saved {len(df)} records to '{path}'")

        except Exception as e:
            raise ETLError(f"Error saving '{self.name}': {str(e)}")


class ClipOutliersETL(BaseETL):
    """ETL that clips extreme values in numeric columns.

    Reads a dataset, clips values above a threshold in specified columns
    (or auto-detected consumption columns), and saves the result.
    Designed to remove data reading errors before feature engineering.

    Args:
        name: ETL name.
        input_paths: List with path(s) to input file(s).
        output_path: Path to save clipped dataset.
        threshold: Maximum allowed value (default: 100_000).
        columns: Explicit list of columns to clip. If None, auto-detects
            columns matching ``*{periods_suffix}``.
        periods_suffix: Suffix for auto-detection (default: "_anterior").
        **kwargs: Additional parameters.

    Example YAML:
        .. code-block:: yaml

            clip_outliers:
              enabled: true
              input: "data/processed/dataset.parquet"
              output: "data/processed/dataset_clipped.parquet"
              custom_class: "energizados.etl.pipeline.ClipOutliersETL"
              params:
                threshold: 100000
                periods_suffix: "_anterior"
    """

    def __init__(
        self,
        name: str,
        input_paths: List[str],
        output_path: Optional[str] = None,
        threshold: float = 100_000,
        columns: Optional[List[str]] = None,
        periods_suffix: str = "_anterior",
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self.threshold = threshold
        self.columns = columns
        self.periods_suffix = periods_suffix
        self.kwargs = kwargs

    def _resolve_columns(self, df: pd.DataFrame) -> List[str]:
        """Return columns to clip: explicit list or auto-detected by suffix."""
        if self.columns is not None:
            return [c for c in self.columns if c in df.columns]
        return [c for c in df.columns if c.endswith(self.periods_suffix)]

    def extract(self) -> pd.DataFrame:
        """Read input file."""
        if not self.input_paths:
            raise ETLError(f"ClipOutliersETL '{self.name}': input_paths is empty")

        from energizados.core.utils.secure_pickle import validate_no_traversal

        path = self.input_paths[0]
        validate_no_traversal(path, label=f"ETL '{self.name}' input")
        source_file = Path(path)

        if not source_file.exists():
            raise ETLError(f"File not found: {path}")

        if source_file.suffix in [".parquet", ".pq"]:
            df = pd.read_parquet(path)
        elif source_file.suffix == ".csv":
            df = pd.read_csv(path)
        else:
            raise ETLError(f"Unsupported format: {source_file.suffix}")

        logger.info(f"  • Read {len(df)} records from '{source_file.name}'")
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clip values above threshold in target columns."""
        df = df.copy()
        cols = self._resolve_columns(df)

        if not cols:
            logger.warning(
                f"ClipOutliersETL '{self.name}': no columns matched — " "returning data unchanged"
            )
            return df

        # Log per-column stats before clipping
        for col in cols:
            n = (df[col] > self.threshold).sum()
            if n > 0:
                logger.info(
                    f"  • {col}: {n:,} values exceed {self.threshold:,.0f} "
                    f"(max: {df[col].max():,.0f})"
                )

        n_total = (df[cols] > self.threshold).sum().sum()
        df[cols] = df[cols].clip(upper=self.threshold)
        logger.info(
            f"  ✓ Clipped {n_total:,} values to {self.threshold:,.0f} " f"in {len(cols)} columns"
        )

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save clipped dataset."""
        from energizados.core.utils.secure_pickle import validate_no_traversal

        validate_no_traversal(path, label=f"ETL '{self.name}' output")
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix in [".parquet", ".pq"]:
            df.to_parquet(path, index=False)
        elif output_path.suffix == ".csv":
            df.to_csv(path, index=False)
        else:
            df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

        logger.info(f"  ✓ Saved {len(df)} records to '{path}'")


class GeoClusterETL(BaseETL):
    """ETL that assigns geographic cluster labels via KMeans on lat/lon coordinates.

    Reads a dataset, fits a KMeans model on valid coordinates, appends a
    ``geo_cluster`` integer column, and saves the result. Run this ETL after
    the main dataset-building ETL and before training, so that the cluster
    column is available for ``stratified_time`` splits.

    Points with missing or zero coordinates are assigned label ``-1``.

    Args:
        name: ETL name.
        input_paths: List with path to the input file (single file).
        output_path: Path to save the enriched dataset.
        n_clusters: Number of geographic clusters (default: 10).
        lat_col: Name of the latitude column (default: "latitud").
        lon_col: Name of the longitude column (default: "longitud").
        random_state: Random seed for KMeans (default: 42).
        **kwargs: Additional parameters.

    Example YAML:
        .. code-block:: yaml

            geo_cluster:
              enabled: true
              input: "@sample"
              output: "data/processed/dataset_with_clusters.parquet"
              custom_class: "energizados.etl.pipeline.GeoClusterETL"
              params:
                n_clusters: 10
                lat_col: "latitud"
                lon_col: "longitud"
              depends_on: [sample]
    """

    def __init__(
        self,
        name: str,
        input_paths: List[str],
        output_path: Optional[str] = None,
        n_clusters: int = 10,
        lat_col: str = "latitud",
        lon_col: str = "longitud",
        random_state: int = 42,
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self.n_clusters = n_clusters
        self.lat_col = lat_col
        self.lon_col = lon_col
        self.random_state = random_state
        self.kwargs = kwargs

    def extract(self) -> pd.DataFrame:
        """Read input file."""
        if not self.input_paths:
            raise ETLError(f"GeoClusterETL '{self.name}': input_paths is empty")

        from energizados.core.utils.secure_pickle import validate_no_traversal

        path = self.input_paths[0]
        validate_no_traversal(path, label=f"ETL '{self.name}' input")
        source_file = Path(path)

        if not source_file.exists():
            raise ETLError(f"File not found: {path}")

        if source_file.suffix in [".parquet", ".pq"]:
            df = pd.read_parquet(path)
        elif source_file.suffix == ".csv":
            df = pd.read_csv(path)
        else:
            raise ETLError(f"Unsupported format: {source_file.suffix}")

        logger.info(f"  • Read {len(df)} records from '{source_file.name}'")
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit KMeans on lat/lon and append ``geo_cluster`` column."""
        import numpy as np
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        df = df.copy()

        if self.lat_col not in df.columns or self.lon_col not in df.columns:
            raise ETLError(
                f"GeoClusterETL '{self.name}': columns '{self.lat_col}' or "
                f"'{self.lon_col}' not found. Available: {list(df.columns)}"
            )

        lats = pd.to_numeric(df[self.lat_col], errors="coerce").values
        lons = pd.to_numeric(df[self.lon_col], errors="coerce").values
        valid_mask = ~(np.isnan(lats) | np.isnan(lons) | ((lats == 0) & (lons == 0)))

        n_valid = int(valid_mask.sum())
        if n_valid < 10:
            raise ETLError(
                f"GeoClusterETL '{self.name}': only {n_valid} valid coordinates found. "
                "Need at least 10 to fit clusters."
            )

        coords = np.column_stack([lats[valid_mask], lons[valid_mask]])
        n_clusters = min(self.n_clusters, n_valid)

        scaler = StandardScaler()
        coords_scaled = scaler.fit_transform(coords)

        kmeans = KMeans(n_clusters=n_clusters, random_state=self.random_state, n_init=10)
        kmeans.fit(coords_scaled)

        labels = np.full(len(df), -1, dtype=int)
        labels[valid_mask] = kmeans.predict(coords_scaled)
        df["geo_cluster"] = labels

        invalid_count = int((~valid_mask).sum())
        logger.info(
            "  ✓ GeoCluster: %d clusters fitted on %d valid coordinates (%d assigned label -1)",
            n_clusters,
            n_valid,
            invalid_count,
        )
        for cluster_id in sorted(set(labels[valid_mask])):
            count = int((labels == cluster_id).sum())
            logger.info(
                "    Cluster %d: %d records (%.1f%%)", cluster_id, count, count / len(df) * 100
            )

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save enriched dataset."""
        from energizados.core.utils.secure_pickle import validate_no_traversal

        validate_no_traversal(path, label=f"ETL '{self.name}' output")
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix in [".parquet", ".pq"]:
            df.to_parquet(path, index=False)
        elif output_path.suffix == ".csv":
            df.to_csv(path, index=False)
        else:
            df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

        logger.info(f"  ✓ Saved {len(df)} records to '{path}'")


class GeoFeaturesETL(BaseETL):
    """ETL that adds geographic features and cluster labels from lat/lon coordinates.

    Combines geographic clustering (KMeans → ``geo_cluster`` column) with IBGE
    geographic hierarchy (``geo_estado``, ``geo_municipio``, ``geo_regiao``) and
    optional distance features. Target encoding is intentionally excluded — run it
    in feature engineering where the train/val/test split is already in place.

    Run this ETL after the main dataset-building ETL and before training.

    Args:
        name: ETL name.
        input_paths: List with one path to the input file.
        output_path: Path to save the enriched dataset.
        lat_col: Latitude column name (default: ``"latitud"``).
        lon_col: Longitude column name (default: ``"longitud"``).
        n_clusters: Number of geographic KMeans clusters (default: ``10``).
        random_state: Random seed for KMeans (default: ``42``).
        include_hierarchy: Add ``geo_estado``, ``geo_municipio``, ``geo_regiao``
            columns via IBGE spatial join (default: ``True``).
        include_distances: Add haversine distance columns to reference cities
            (default: ``True``).
        distance_cities: List of city names for distance calculation. If ``None``,
            uses the top-5 default. Available cities: sao_paulo, rio_de_janeiro,
            brasilia, salvador, belo_horizonte, fortaleza, recife, curitiba,
            manaus, porto_alegre, florianopolis, blumenau, joinville, criciuma,
            chapeco, itajai, lages.
        include_coords: Keep original lat/lon columns in output (default: ``False``).
        cache_dir: Directory to persist IBGE shapefiles on disk (default: ``None``).
        **kwargs: Additional parameters (ignored).

    Example YAML:

    .. code-block:: yaml

        geo_features:
          enabled: true
          input: "@dataset_builder"
          output: "data/processed/dataset_with_geo.parquet"
          custom_class: "energizados.etl.pipeline.GeoFeaturesETL"
          params:
            lat_col: "latitude"
            lon_col: "longitude"
            n_clusters: 10
            include_hierarchy: true
            include_distances: true
            distance_cities:
              - sao_paulo
              - rio_de_janeiro
              - brasilia
            include_coords: false
            cache_dir: ".cache/ibge"
          depends_on: [dataset_builder]
    """

    def __init__(
        self,
        name: str,
        input_paths: List[str],
        output_path: Optional[str] = None,
        lat_col: str = "latitud",
        lon_col: str = "longitud",
        n_clusters: int = 10,
        random_state: int = 42,
        include_hierarchy: bool = True,
        include_distances: bool = True,
        distance_cities: Optional[List[str]] = None,
        include_coords: bool = False,
        cache_dir: Optional[str] = None,
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self.lat_col = lat_col
        self.lon_col = lon_col
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.include_hierarchy = include_hierarchy
        self.include_distances = include_distances
        self.distance_cities = distance_cities
        self.include_coords = include_coords
        self.cache_dir = cache_dir

    def extract(self) -> pd.DataFrame:
        """Read input file."""
        if not self.input_paths:
            raise ETLError(f"GeoFeaturesETL '{self.name}': input_paths is empty")

        from energizados.core.utils.secure_pickle import validate_no_traversal

        path = self.input_paths[0]
        validate_no_traversal(path, label=f"ETL '{self.name}' input")
        source_file = Path(path)

        if not source_file.exists():
            raise ETLError(f"File not found: {path}")

        if source_file.suffix in [".parquet", ".pq"]:
            df = pd.read_parquet(path)
        elif source_file.suffix == ".csv":
            df = pd.read_csv(path)
        else:
            raise ETLError(f"Unsupported format: {source_file.suffix}")

        logger.info("  • Read %d records from '%s'", len(df), source_file.name)
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append geo_cluster and optional geographic feature columns."""
        import numpy as np
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        df = df.copy()

        if self.lat_col not in df.columns or self.lon_col not in df.columns:
            raise ETLError(
                f"GeoFeaturesETL '{self.name}': columns '{self.lat_col}' or "
                f"'{self.lon_col}' not found. Available: {list(df.columns)}"
            )

        lats = pd.to_numeric(df[self.lat_col], errors="coerce").values
        lons = pd.to_numeric(df[self.lon_col], errors="coerce").values
        valid_mask = ~(np.isnan(lats) | np.isnan(lons) | ((lats == 0) & (lons == 0)))

        n_valid = int(valid_mask.sum())
        if n_valid < 10:
            raise ETLError(
                f"GeoFeaturesETL '{self.name}': only {n_valid} valid coordinates found. "
                "Need at least 10 to fit clusters."
            )

        # --- Geographic clustering ---
        coords = np.column_stack([lats[valid_mask], lons[valid_mask]])
        n_clusters = min(self.n_clusters, n_valid)

        scaler = StandardScaler()
        coords_scaled = scaler.fit_transform(coords)

        kmeans = KMeans(n_clusters=n_clusters, random_state=self.random_state, n_init=10)
        kmeans.fit(coords_scaled)

        labels = np.full(len(df), -1, dtype=int)
        labels[valid_mask] = kmeans.predict(coords_scaled)
        df["geo_cluster"] = labels

        invalid_count = int((~valid_mask).sum())
        logger.info(
            "  ✓ GeoFeaturesETL: %d clusters fitted on %d valid coordinates (%d → label -1)",
            n_clusters,
            n_valid,
            invalid_count,
        )

        # --- Geographic hierarchy and distances ---
        if self.include_hierarchy or self.include_distances:
            from energizados.preprocessing.geo_features import GeoFeatures

            transformer = GeoFeatures(
                lat_col=self.lat_col,
                lon_col=self.lon_col,
                include_hierarchy=self.include_hierarchy,
                include_target_encoding=False,
                include_distances=self.include_distances,
                distance_cities=self.distance_cities,
                include_coords=self.include_coords,
                cache_dir=self.cache_dir,
            )
            df = transformer.fit_transform(df)
            logger.info("  ✓ GeoFeaturesETL: geographic features added")

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save enriched dataset."""
        from energizados.core.utils.secure_pickle import validate_no_traversal

        validate_no_traversal(path, label=f"ETL '{self.name}' output")
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix in [".parquet", ".pq"]:
            df.to_parquet(path, index=False)
        elif output_path.suffix == ".csv":
            df.to_csv(path, index=False)
        else:
            df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

        logger.info("  ✓ Saved %d records to '%s'", len(df), path)
