"""Pipeline ETL Module for Multi-Source Data Processing.

This module provides ETL classes for data processing:
- SourceETL: Concatenation and merge operations on multiple sources.
- ClipOutliersETL: Clips extreme values in numeric columns (data reading errors).
- GeoFeaturesETL: Adds geo_cluster + geographic hierarchy and distance features.
- CleanFilesETL: Deletes specified files (e.g. intermediate outputs after pipeline).
- AssumedNegativesETL: Derives assumed negatives via anti-join (uninspected clients).
"""

import glob
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd

from energizados.core.exceptions import ETLError
from energizados.core.utils.import_utils import import_class
from energizados.etl.base import BaseETL

logger = logging.getLogger(__name__)


class SourceETL(BaseETL):
    """ETL to process one or multiple data sources.

    This class processes data from one or several files and generates processed output.
    Supports three operating modes:

    - **concat**: Concatenates multiple dataframes vertically (default)
    - **merge**: Joins multiple dataframes horizontally using merge_config
    - **incremental**: Processes only new/pending records based on a key column value

    Input paths can be individual files, globs, ``@etl_name`` references, or
    **Hive-style partitioned directories** (e.g. ``year=2024/month=03/``).
    When a directory is detected, it is read with ``pd.read_parquet()`` which
    automatically discovers all parquet files and parses partition columns.

    Args:
        name: Name of the source (e.g.: 'consumos', 'inspecciones', 'clientes').
        input_paths: List with paths to raw data files.
        output_path: Path to save processed data.
        mode: Processing mode ('concat', 'merge', or 'incremental'). Default: 'concat'.
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
        partition_by: Optional list of columns for Hive-style partitioning.
            Example: ['year', 'month'] → writes to output_path/year=YYYY/month=MM/
            If the DataFrame does not contain these columns but ``incremental_key`` is
            a datetime column, ``year`` and ``month`` are derived automatically.
            **Deprecated in incremental mode**: use ``incremental_partition`` instead.
            If passed with ``mode='incremental'``, a deprecation warning is logged and
            the parameter is ignored.
        reprocess: If False (default), only processes files not yet in the state file.
            If True, re-reads all files regardless of processing history (the
            ``incremental_key`` filter still applies to individual records).
            Only relevant in incremental mode.
        write_mode: How to handle existing partition files in incremental mode.
            ``"append"`` (default) concatenates new records to existing partitions.
            ``"replace"`` overwrites existing partition files with new data only.
            Only relevant in incremental mode.
        state_file: Path to JSON file that tracks processed files and last processed value.
            Used in incremental mode to detect pending files.
            If None (default), auto-inferred as ``{output_path}/.etl_state.json``
            for incremental mode. Explicit value still honored for backward compat.
        raw_glob: Glob pattern to find raw input files (e.g., 'data/raw/*.csv').
            Used in incremental mode to discover new files.
            If specified, input_paths is ignored in incremental mode.
        processed_glob: Glob pattern to find already processed files.
            Used in incremental mode to detect what's already done.
            If specified alongside raw_glob, compares both to find pending files.
        incremental_key: Column name used to filter new records (e.g. 'fecha_actualizacion').
            In incremental mode, only records where ``incremental_key > last_processed_value``
            are kept. After processing, the max value is stored in the state file so the next
            run continues from where this one left off.
        last_processed: Initial value for ``incremental_key`` comparison when no state exists.
            Accepts any value comparable to the column (ISO date string, int, float, etc.).
            If None and no state exists, all records are processed on the first run.
        incremental_format: Optional strftime format string for parsing the ``incremental_key``
            column. When set, ``pd.to_datetime(col, format=incremental_format)`` is used
            instead of auto-parsing. Useful for ambiguous date formats like ``"15/01/2024"``.
            Default: None (auto-parse).
        incremental_partition: strftime format string for partition column generation.
            Applied to the parsed ``incremental_key`` datetime to create a ``"partition"``
            column. Output is written as ``output_path/partition=<value>/data.parquet``.
            Default: ``"%Y-%m"`` (monthly partitions like ``"2024-01"``).
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

    Example with incremental mode (monthly processing):
        >>> etl = SourceETL(
        ...     name='consumos_monthly',
        ...     mode='incremental',
        ...     raw_glob='data/raw/consumos_*.csv',
        ...     output_path='data/processed/consumos/',
        ...     incremental_key='fecha_actualizacion',
        ...     incremental_partition='%Y-%m',  # monthly: partition=2024-01/
        ...     reprocess=False,
        ...     write_mode='append',
        ...     # state_file is auto-inferred as data/processed/consumos/.etl_state.json
        ... )
        >>> df = etl.run()

    Example with incremental mode (custom date format):
        >>> etl = SourceETL(
        ...     name='consumos_ddmmyyyy',
        ...     mode='incremental',
        ...     raw_glob='data/raw/consumos_*.csv',
        ...     output_path='data/processed/consumos/',
        ...     incremental_key='fecha_actualizacion',
        ...     incremental_format='%d/%m/%Y',  # parse DD/MM/YYYY dates
        ...     incremental_partition='%Y-%m',
        ...     # state_file is auto-inferred as data/processed/consumos/.etl_state.json
        ... )
        >>> df = etl.run()

    Example YAML configuration:
        .. code-block:: yaml

            consumos_incremental:
              enabled: true
              description: "Procesa solo registros nuevos de consumos (incremental por fecha)"
              raw_glob: "data/raw/consumos_*.csv"
              output: "data/processed/consumos/"
              custom_class: "energizados.etl.pipeline.SourceETL"
              params:
                mode: "incremental"
                incremental_key: "fecha_actualizacion"
                incremental_format: null  # optional: explicit strftime for date parsing
                incremental_partition: "%Y-%m"  # strftime for partition values
                reprocess: false
                write_mode: "append"
                # state is auto-managed at {output}/.etl_state.json
                # last_processed: "2024-01-01"  # optional: initial cutoff if no state exists
    """

    def __init__(
        self,
        name: str,
        input_paths: Optional[List[str]] = None,
        output_path: Optional[str] = None,
        mode: str = "concat",
        merge_config: Optional[Dict[str, Any]] = None,
        key_column: Optional[str] = None,
        input_params: Optional[Dict[str, Any]] = None,
        output_params: Optional[Dict[str, Any]] = None,
        transform_fn: Optional[Any] = None,
        sample: Optional[int] = None,
        partition_by: Optional[List[str]] = None,
        reprocess: bool = False,
        write_mode: str = "append",
        state_file: Optional[str] = None,
        raw_glob: Optional[str] = None,
        processed_glob: Optional[str] = None,
        incremental_key: Optional[str] = None,
        last_processed: Optional[str] = None,
        incremental_format: Optional[str] = None,
        incremental_partition: str = "%Y-%m",
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths or []
        self.output_path = output_path
        self.mode = mode.lower() if mode else "concat"
        self.merge_config = merge_config
        self.key_column = key_column or "id_cliente"
        self.input_params = input_params or {}
        self.output_params = output_params or {}
        self.sample = sample
        self.reprocess = reprocess
        self.write_mode = write_mode.lower() if write_mode else "append"
        self.state_file = state_file
        self.raw_glob = raw_glob
        self.processed_glob = processed_glob
        self.incremental_key = incremental_key
        self.last_processed = last_processed
        self.incremental_format = incremental_format
        self.incremental_partition = incremental_partition
        self._written_partitions: List[str] = []
        self._state_dirty: bool = False
        self.kwargs = kwargs

        # partition_by deprecation in incremental mode
        if self.mode == "incremental" and partition_by is not None:
            logger.warning(
                f"SourceETL '{self.name}': partition_by is deprecated in incremental mode. "
                f"Use incremental_partition (default '%Y-%m') instead. "
                f"Ignoring partition_by={partition_by}."
            )
            self.partition_by = None
        else:
            self.partition_by = partition_by

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
        if self.mode not in ("concat", "merge", "incremental"):
            raise ValueError(f"Mode must be 'concat', 'merge', or 'incremental', not '{self.mode}'")

        # Validate write_mode
        if self.write_mode not in ("append", "replace"):
            raise ValueError(
                f"SourceETL '{self.name}': write_mode must be 'append' or 'replace', "
                f"not '{self.write_mode}'"
            )

        # Validate merge_config if mode is merge
        if self.mode == "merge" and not self.merge_config:
            raise ValueError(
                f"SourceETL '{self.name}': mode='merge' requires merge_config "
                "(e.g.: {'how': 'left', 'on': 'id_cliente'})"
            )

        # Validate incremental mode requirements
        if self.mode == "incremental":
            if not self.raw_glob and not self.input_paths:
                raise ValueError(
                    f"SourceETL '{self.name}': mode='incremental' requires "
                    "either 'raw_glob' or 'input_paths'"
                )
            if not self.output_path:
                raise ValueError(
                    f"SourceETL '{self.name}': mode='incremental' requires 'output_path'"
                )

        # Initialize state for incremental mode
        self._state: Dict[str, Any] = {}
        if self.mode == "incremental":
            # Auto-infer state_file when not explicitly configured
            if self.state_file is None and self.output_path:
                self.state_file = str(Path(self.output_path) / ".etl_state.json")
                logger.info(f"  • Auto-inferred state_file: {self.state_file}")
            if self.state_file:
                self._load_state()

    def extract(self) -> pd.DataFrame:
        """
        Extracts data from specified sources.

        Processes all input_paths according to configured mode:
        - concat: Concatenates all dataframes vertically
        - merge: Joins horizontally according to merge_config
        - incremental: Processes only pending files based on state tracking

        Supports reading Hive-style partitioned directories (year=2024/month=03/)
        in concat and merge modes via ``pd.read_parquet()``.

        Returns:
            pd.DataFrame: Combined raw data

        Raises:
            ETLError: If data cannot be read
        """
        # Handle incremental mode separately
        if self.mode == "incremental":
            return self._extract_incremental()

        # Original logic for concat/merge modes
        if not self.input_paths:
            raise ETLError(f"SourceETL '{self.name}': input_paths is empty")

        # Read all files
        from energizados.core.utils.integrity_pickle import validate_no_traversal

        dataframes = []
        for path in self.input_paths:
            validate_no_traversal(path, label=f"ETL '{self.name}' input")
            source_file = Path(path)

            if not source_file.exists():
                raise ETLError(f"File not found: {path}")

            try:
                # Directory with Hive-style partitions (e.g. year=2024/month=03/)
                if source_file.is_dir():
                    df = pd.read_parquet(str(source_file))
                elif source_file.suffix == ".csv":
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

    def _extract_incremental(self) -> pd.DataFrame:
        """Extract data in incremental mode - only process pending files."""
        import re

        from energizados.core.utils.integrity_pickle import validate_no_traversal

        # Validate glob pattern to prevent directory traversal
        # Only allow safe patterns: alphanumeric, _, -, /, *, ?, and []
        if self.raw_glob:
            safe_pattern = re.compile(r"^[\w\-./\*?\[\]]+$")
            if not safe_pattern.match(self.raw_glob):
                raise ETLError(
                    f"SourceETL '{self.name}': raw_glob contains unsafe characters. "
                    f"Allowed: alphanumeric, _, -, /, *, ?, []. Got: '{self.raw_glob}'"
                )

        # Determine input files to process
        if self.raw_glob:
            # Use glob pattern to discover raw files
            raw_files = sorted(glob.glob(self.raw_glob))
            if not raw_files:
                logger.info(f"  • No files found matching glob: '{self.raw_glob}'")
                return pd.DataFrame()
            logger.info(f"  • Found {len(raw_files)} files matching raw_glob")

            # Validate each resolved file path to prevent traversal
            for f in raw_files:
                validate_no_traversal(f, label=f"ETL '{self.name}' incremental glob result")

            # Determine which files are pending
            pending_files = self._get_pending_files(raw_files)

            if not pending_files:
                logger.info("  ✓ All files already processed (no pending files)")
                return pd.DataFrame()

            logger.info(f"  • Processing {len(pending_files)} pending file(s)")
            input_paths = pending_files
        else:
            # Use input_paths directly (backward compatibility)
            input_paths = self.input_paths

        # Read pending files
        dataframes = []
        processed_files = []

        for path in input_paths:
            validate_no_traversal(path, label=f"ETL '{self.name}' incremental input")
            source_file = Path(path)

            if not source_file.exists():
                logger.warning(f"  • Skipping (not found): '{path}'")
                continue

            # Check if already processed (unless reprocess is True)
            if not self.reprocess and self._is_file_processed(path):
                logger.info(f"  • Skipping (already processed): '{source_file.name}'")
                continue

            if source_file.is_dir():
                # Directory (e.g. partitioned output from @ref) — read as parquet dataset
                pass
            elif source_file.suffix not in [".csv", ".parquet", ".pq", ".xlsx", ".xls"]:
                logger.warning(f"  • Skipping (unsupported format): '{source_file.suffix}'")
                continue

            df = self._read_single_file(path)

            dataframes.append(df)
            processed_files.append(path)
            logger.info(f"  • Read {len(df)} records from '{source_file.name}'")

        if not dataframes:
            logger.info("  ✓ No new data to process")
            return pd.DataFrame()

        # Concatenate all pending data
        result = pd.concat(dataframes, axis=0, ignore_index=True)
        logger.info(f"  ✓ Incremental extract: {len(result)} records from {len(dataframes)} files")

        # Filter by incremental_key if configured
        if self.incremental_key:
            result = self._filter_by_incremental_key(result)

        # Update state with processed files (flushed to disk only after load succeeds)
        for path in processed_files:
            self._mark_file_processed(path)

        return result

    def _filter_by_incremental_key(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter DataFrame to only records newer than the last processed value.

        Reads ``last_processed_value`` from state (falling back to ``self.last_processed``).
        Keeps only rows where ``incremental_key > last_processed_value``.
        After filtering, updates state with the new max value so the next run
        continues from where this one left off.

        If ``incremental_format`` is set, uses it for explicit date parsing.
        Otherwise, if the column is not datetime but can be parsed as one, it is
        coerced automatically. Numeric and string comparisons are also supported.
        """
        col = self.incremental_key

        if col not in df.columns:
            raise ETLError(
                f"SourceETL '{self.name}': incremental_key '{col}' not found in DataFrame. "
                f"Available columns: {list(df.columns)}"
            )

        # Get last processed value: state takes priority over constructor param
        last_val = self._state.get("last_processed_value") or self.last_processed

        # Coerce column to datetime if possible (and not already)
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                df = df.copy()
                if self.incremental_format:
                    df[col] = pd.to_datetime(df[col], format=self.incremental_format)
                    logger.debug(
                        f"  • Parsed '{col}' as datetime with format '{self.incremental_format}'"
                    )
                else:
                    df[col] = pd.to_datetime(df[col])
                    logger.debug(f"  • Parsed '{col}' as datetime for incremental filtering")
            except Exception as e:  # noqa: BLE001
                logger.debug("Could not parse '%s' as datetime: %s", col, e)

        before = len(df)
        if last_val is not None:
            # Coerce last_val to match column dtype for comparison
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                last_val_cmp = pd.Timestamp(last_val)
            else:
                last_val_cmp = last_val

            df = df[df[col] > last_val_cmp].copy()
            logger.info(
                f"  • Filtered by '{col}' > {last_val}: "
                f"{before - len(df)} records skipped, {len(df)} kept"
            )
        else:
            logger.info(f"  • No prior state for '{col}' — processing all {before} records")

        if df.empty:
            return df

        # Persist the new high-water mark
        new_max = df[col].max()
        self._state["last_processed_value"] = str(new_max)
        logger.info(f"  • Updated last_processed_value → {new_max}")

        return df

    def _add_partition_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add a ``partition`` column derived from incremental_key via strftime.

        .. deprecated::
            This method is no longer called by ``run()`` — partitioning is handled
            internally by ``_load_incremental()`` so that ETL transforms never see
            the ``partition`` column. Kept for backward compatibility and unit tests.

        Args:
            df: DataFrame with a parsed datetime ``incremental_key`` column.

        Returns:
            DataFrame with an added ``"partition"`` column.
        """
        col = self.incremental_key
        df = df.copy()

        # Ensure datetime dtype
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            if self.incremental_format:
                df[col] = pd.to_datetime(df[col], format=self.incremental_format)
            else:
                df[col] = pd.to_datetime(df[col])

        df["partition"] = df[col].dt.strftime(self.incremental_partition)
        return df

    def _precompute_partition(self, df: pd.DataFrame) -> dict:
        """Pre-compute partition values from ``incremental_key`` BEFORE transform.

        This must be called before ``transform()`` because the transform may remove
        the ``incremental_key`` column (e.g. a pivot from long to wide format).

        Returns a dict with:
        - ``per_row``: Series of partition values (index-aligned with ``df``) for
          row-preserving transforms.
        - ``unique``: set of unique partition values — used when the transform changes
          row count (e.g. pivot/aggregation).

        Args:
            df: DataFrame with the ``incremental_key`` column still present.

        Returns:
            Dict with ``per_row`` (Series) and ``unique`` (set) partition values.
        """
        col = self.incremental_key

        if col not in df.columns:
            raise ETLError(
                f"SourceETL '{self.name}': incremental_key '{col}' not found in DataFrame. "
                f"Available columns: {list(df.columns)}"
            )

        dt_col = df[col]
        if not pd.api.types.is_datetime64_any_dtype(dt_col):
            if self.incremental_format:
                dt_col = pd.to_datetime(dt_col, format=self.incremental_format)
            else:
                dt_col = pd.to_datetime(dt_col)

        partition_values = dt_col.dt.strftime(self.incremental_partition)
        return {
            "per_row": partition_values,
            "unique": set(partition_values.unique()),
        }

    def _attach_partition(self, df: pd.DataFrame, partition_map: dict) -> None:
        """Attach ``_partition`` column to a (possibly transformed) DataFrame.

        If the transform preserved the row count, uses per-row partition values.
        If the transform changed the row count (e.g. pivot), assigns all rows to
        each unique partition value. When there is a single unique value (common
        case: one file = one period), all rows go to that partition.
        When multiple unique values exist, all rows are replicated across partitions
        — this is the correct behavior for aggregated/pivoted data that spans
        multiple periods.

        Modifies ``df`` in place.

        Args:
            df: DataFrame after transform (may have different row count).
            partition_map: Dict from ``_precompute_partition``.
        """
        if "_partition" in df.columns:
            # Transform preserved it (unlikely but possible) — nothing to do
            return

        per_row = partition_map["per_row"]
        unique = partition_map["unique"]

        if len(df) == len(per_row):
            # Row count preserved — direct assignment
            df["_partition"] = per_row.values
        elif len(unique) == 1:
            # Transform changed row count but all data belongs to one partition
            df["_partition"] = next(iter(unique))
        else:
            # Multiple partitions + row count changed (e.g. pivot across periods).
            # Silently assigning all rows to the latest partition would corrupt data
            # from earlier periods — raise instead and force the user to be explicit.
            raise ETLError(
                f"Transform changed row count and data spans {len(unique)} partitions "
                f"({sorted(unique)}). Cannot safely assign partition values. "
                "Return a '_partition' column from your transform(), or ensure the "
                "transform preserves the original row count."
            )

    def _load_incremental(self, df: pd.DataFrame, output_path: str) -> None:
        """Write DataFrame in partitioned format for incremental mode.

        Uses the pre-computed ``_partition`` column if present (set by
        ``_precompute_partition`` before ``transform()``). Falls back to deriving
        the partition from ``incremental_key`` for backward compatibility.

        Groups by partition and writes to ``output_path/partition=<val>/data.parquet``.
        If a partition file already exists, new rows are appended.

        Args:
            df: DataFrame with ``_partition`` column (preferred) or ``incremental_key``.
            output_path: Base output directory.
        """
        base = Path(output_path)
        base.mkdir(parents=True, exist_ok=True)

        df = df.copy()

        # Use pre-computed _partition if available; otherwise derive from incremental_key
        if "_partition" not in df.columns:
            col = self.incremental_key
            if col not in df.columns:
                raise ETLError(
                    f"SourceETL '{self.name}': incremental_key '{col}' not found in "
                    f"DataFrame after transform. If your transform removes this column "
                    f"(e.g. pivot), this is handled automatically — please report this "
                    f"as a bug. Available columns: {list(df.columns)}"
                )

            if not pd.api.types.is_datetime64_any_dtype(df[col]):
                if self.incremental_format:
                    df[col] = pd.to_datetime(df[col], format=self.incremental_format)
                else:
                    df[col] = pd.to_datetime(df[col])

            df["_partition"] = df[col].dt.strftime(self.incremental_partition)

        for partition_val, group_df in df.groupby("_partition", sort=False):
            partition_dir = base / f"partition={partition_val}"
            partition_dir.mkdir(parents=True, exist_ok=True)
            output_file = partition_dir / "data.parquet"

            # Drop internal partition column(s) from saved data
            save_df = group_df.drop(columns=["_partition", "partition"], errors="ignore")

            # Handle existing partition file based on write_mode setting
            if output_file.exists():
                if self.write_mode == "replace":
                    # Replace the partition file
                    logger.info(f"  • Replacing partition: '{output_file}'")
                else:
                    # Append to existing partition file
                    existing = pd.read_parquet(output_file)
                    save_df = pd.concat([existing, save_df], ignore_index=True)

            save_df.to_parquet(output_file, index=False)
            self._written_partitions.append(str(partition_val))
            logger.info(f"  • Saved {len(group_df)} records to partition={partition_val}/")

    def _read_single_file(self, path: str) -> pd.DataFrame:
        """Read a single file and return a DataFrame.

        Supports CSV, Parquet, and Excel formats. Raises ETLError on failure.

        Args:
            path: Path to the file.

        Returns:
            DataFrame with the file contents.

        Raises:
            ETLError: If the file cannot be read or has an unsupported format.
        """
        source_file = Path(path)

        if not source_file.exists():
            raise ETLError(f"Error reading '{path}': file not found")

        try:
            if source_file.is_dir():
                return pd.read_parquet(str(source_file))
            elif source_file.suffix == ".csv":
                return pd.read_csv(path, **self.input_params)
            elif source_file.suffix in [".parquet", ".pq"]:
                return pd.read_parquet(path)
            elif source_file.suffix in [".xlsx", ".xls"]:
                return pd.read_excel(path)
            else:
                raise ETLError(f"Unsupported format: {source_file.suffix}")
        except ETLError:
            raise
        except Exception as e:
            raise ETLError(f"Error reading '{path}': {str(e)}") from e

    def run(self, output_path: Optional[str] = None) -> pd.DataFrame:  # type: ignore[override]
        """Execute the ETL pipeline.

        For incremental mode, processes files one-by-one: extract → filter →
        add partition → transform → load. State is saved ONCE after all files
        complete. Falls back to ``super().run()`` for concat/merge modes.

        Args:
            output_path: Path to save output. Falls back to ``self.output_path``.

        Returns:
            Concatenated DataFrame of all processed records.
        """
        if self.mode != "incremental":
            return super().run(output_path or self.output_path or "")

        # Incremental mode: file-by-file processing
        actual_output = output_path or self.output_path or ""
        import re

        from energizados.core.utils.integrity_pickle import validate_no_traversal

        # Determine input files
        if self.raw_glob:
            safe_pattern = re.compile(r"^[\w\-./\*?\[\]]+$")
            if not safe_pattern.match(self.raw_glob):
                raise ETLError(
                    f"SourceETL '{self.name}': raw_glob contains unsafe characters. "
                    f"Allowed: alphanumeric, _, -, /, *, ?, []. Got: '{self.raw_glob}'"
                )
            raw_files = sorted(glob.glob(self.raw_glob))
            if not raw_files:
                logger.info(f"  • No files found matching glob: '{self.raw_glob}'")
                return pd.DataFrame()
            for f in raw_files:
                validate_no_traversal(f, label=f"ETL '{self.name}' incremental glob result")
            input_paths = self._get_pending_files(raw_files)
        else:
            input_paths = self.input_paths

        if not input_paths:
            logger.info("  ✓ All files already processed (no pending files)")
            return pd.DataFrame()

        # Reset partition tracking for this run
        self._written_partitions = []

        all_results = []

        for path in input_paths:
            validate_no_traversal(path, label=f"ETL '{self.name}' incremental input")
            source_file = Path(path)

            if not source_file.exists():
                logger.warning(f"  • Skipping (not found): '{path}'")
                continue

            if not self.reprocess and self._is_file_processed(path):
                logger.info(f"  • Skipping (already processed): '{source_file.name}'")
                continue

            # Extract single file
            df = self._read_single_file(path)

            # Filter by incremental_key
            if self.incremental_key:
                df = self._filter_by_incremental_key(df)

            if df.empty:
                logger.info(f"  • No new records in '{source_file.name}'")
                self._mark_file_processed(path)
                continue

            # Pre-compute partition value BEFORE transform — the transform may
            # remove the incremental_key column (e.g. pivot long-to-wide).
            partition_map = self._precompute_partition(df)

            # Transform (partition column is NOT present — internal detail of the pipeline)
            df = self.transform(df)

            if df.empty:
                logger.info(f"  • No records after transform in '{source_file.name}'")
                self._mark_file_processed(path)
                continue

            # Restore partition info after transform
            self._attach_partition(df, partition_map)

            # Load incremental (uses pre-computed _partition column).
            # Mark file processed AFTER a successful write so a mid-write failure
            # (e.g. disk full) does not suppress the file on the next run.
            try:
                self._load_incremental(df, actual_output)
            except Exception as e:
                raise ETLError(
                    f"Failed to write incremental output for '{source_file.name}': {e}"
                ) from e

            all_results.append(df)
            self._mark_file_processed(path)
            logger.info(f"  • Processed {len(df)} records from '{source_file.name}'")

        # Save state ONCE after all files
        self._on_load_success()

        if not all_results:
            logger.info("  ✓ No new data to process")
            return pd.DataFrame()

        result = pd.concat(all_results, axis=0, ignore_index=True)
        # Drop internal partition column from returned result
        result = result.drop(columns=["_partition"], errors="ignore")
        logger.info(
            f"  ✓ Incremental run complete: {len(result)} records from {len(all_results)} files"
        )
        return result

    def _get_pending_files(self, raw_files: List[str]) -> List[str]:
        """Determine which files are pending based on state and processed_glob."""
        if self.processed_glob:
            # Use processed_glob to find already processed files
            processed_files = set(glob.glob(self.processed_glob))
            # Also include files from state
            state_files = set(self._state.get("processed_files", []))
            all_processed = processed_files | state_files

            pending = [f for f in raw_files if f not in all_processed]
            logger.info(f"  • Found {len(all_processed)} already processed, {len(pending)} pending")
            return pending
        else:
            # Use state file only
            pending = []
            for f in raw_files:
                if not self._is_file_processed(f):
                    pending.append(f)
            return pending

    def _is_file_processed(self, file_path: str) -> bool:
        """Check if a file has been processed according to state."""
        processed = self._state.get("processed_files", [])
        # Check by exact path or by filename
        return file_path in processed or Path(file_path).name in processed

    def _mark_file_processed(self, file_path: str) -> None:
        """Mark a file as processed in state."""
        if "processed_files" not in self._state:
            self._state["processed_files"] = []

        if file_path not in self._state["processed_files"]:
            self._state["processed_files"].append(file_path)
            self._state_dirty = True

    def _acquire_lock(self, lock_path: Path) -> bool:
        """Acquire file lock for concurrent access safety.

        Writes the current PID to the lock file so a dead-process lock is
        detected immediately instead of waiting 5 minutes for a mtime timeout.
        Returns True if lock acquired.
        """
        import json
        import os
        import time

        max_retries = 10
        retry_delay = 0.5

        def _is_stale(path: Path) -> bool:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if pid is None:
                    # Old-style empty lock file — treat as stale
                    return True
                # Check if the owning process is still alive
                os.kill(pid, 0)
                return False  # Process exists → lock is live
            except (ProcessLookupError, PermissionError):
                return True  # Process is dead → stale
            except (OSError, ValueError, KeyError):
                # Can't read/parse the file — fall back to mtime check
                try:
                    return time.time() - path.stat().st_mtime > 300
                except OSError:
                    return True

        for attempt in range(max_retries):
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, json.dumps({"pid": os.getpid()}).encode())
                finally:
                    os.close(fd)
                return True
            except FileExistsError:
                if _is_stale(lock_path):
                    try:
                        lock_path.unlink()
                        logger.warning(f"  • Removed stale lock file: {lock_path}")
                    except OSError:
                        pass
                    continue
                time.sleep(retry_delay)

        logger.warning(f"  • Could not acquire lock after {max_retries} attempts")
        return False

    def _release_lock(self, lock_path: Path) -> None:
        """Release file lock."""
        try:
            if lock_path.exists():
                lock_path.unlink()
        except OSError:
            pass

    def _on_load_success(self) -> None:
        """Persist state to disk only after load() completes successfully."""
        self._save_state()

    def _load_state(self) -> None:
        """Load state from state_file."""
        import json

        from energizados.core.utils.integrity_pickle import validate_no_traversal

        if not self.state_file:
            return

        validate_no_traversal(self.state_file, label=f"ETL '{self.name}' state file")
        state_path = Path(self.state_file)

        # Acquire lock for safe concurrent access.
        # Stored as self._lock_path so _save_state always releases it,
        # even when the run produces no new data (early-return path).
        lock_path = state_path.with_suffix(".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = lock_path
        if not self._acquire_lock(lock_path):
            logger.warning("  • Proceeding without lock (concurrent access may cause issues)")

        if state_path.exists():
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
                processed_count = len(self._state.get("processed_files", []))
                last_val = self._state.get("last_processed_value")
                logger.info(
                    f"  • Loaded state: {processed_count} processed files tracked"
                    + (f", last_processed_value={last_val}" if last_val else "")
                )
            except Exception as e:
                logger.warning(f"  • Could not load state file: {e}")
                self._state = {}
        else:
            self._state = {}

    def _save_state(self) -> None:
        """Save unified state to state_file.

        Writes both incremental state fields (processed_files,
        last_processed_value) and manifest fields (run_id, new_partitions,
        all_partitions) into a single JSON file.

        Uses atomic write (write to ``.tmp`` then ``os.replace()``) to
        prevent corruption from crashes.

        Skips the write entirely when no new partitions were written
        (empty run — preserves existing state file unchanged).
        """
        import os
        from datetime import datetime, timezone

        if not self.state_file:
            return

        # Use the lock acquired in _load_state.  The finally block below ALWAYS
        # releases it — including the early-return path when there is nothing to
        # write (fix for lock leak when incremental run finds no new data).
        lock_path = getattr(self, "_lock_path", None)

        try:
            # Skip write entirely when no new partitions AND no state changes
            # (empty run — preserves existing state file unchanged)
            if not self._written_partitions and not self._state_dirty:
                return

            state_path = Path(self.state_file)
            state_path.parent.mkdir(parents=True, exist_ok=True)

            # Build unified state dict
            state_data = dict(self._state)

            # Initialize before conditional so the logger.info below is always valid
            # (fix for UnboundLocalError when _state_dirty is True but no partitions written)
            all_partitions: List[str] = []

            # Add manifest fields ONLY when partitions were actually written
            if self._written_partitions:
                state_data["run_id"] = datetime.now(timezone.utc).isoformat()
                state_data["new_partitions"] = list(self._written_partitions)

                # Scan output directory for all existing partitions
                if self.output_path and Path(self.output_path).exists():
                    output_dir = Path(self.output_path)
                    for p in sorted(output_dir.iterdir()):
                        if p.is_dir() and p.name.startswith("partition="):
                            all_partitions.append(p.name.replace("partition=", ""))
                state_data["all_partitions"] = all_partitions

            # Atomic write: write to .tmp then rename
            tmp_path = state_path.with_suffix(".json.tmp")
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(state_data, f, indent=2)
                os.replace(tmp_path, state_path)
                logger.debug(f"  • State saved to '{self.state_file}'")
                if self._written_partitions:
                    logger.info(
                        f"  • Unified state written: {len(self._written_partitions)} new "
                        f"partitions, {len(all_partitions)} total"
                    )
                else:
                    logger.debug("  • State updated (processed files only)")
            except Exception as e:
                logger.warning(f"  • Could not save state file: {e}")
                # Clean up tmp file if rename failed
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
        finally:
            # Always release lock, even on early return or exception
            if lock_path:
                self._release_lock(lock_path)
            self._lock_path = None

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

    def _derive_partition_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Derive 'year' and/or 'month' columns from incremental_key if missing.

        Only acts on columns listed in ``partition_by`` that are absent from the
        DataFrame AND can be derived from the ``incremental_key`` datetime column.
        """
        col = self.incremental_key
        needs_year = "year" in self.partition_by and "year" not in df.columns
        needs_month = "month" in self.partition_by and "month" not in df.columns

        if not (needs_year or needs_month):
            return df

        if col not in df.columns:
            return df

        # Ensure datetime dtype
        series = df[col]
        if not pd.api.types.is_datetime64_any_dtype(series):
            try:
                series = pd.to_datetime(series)
            except Exception:
                logger.warning(
                    f"  • Could not parse '{col}' as datetime — "
                    "year/month columns will not be derived"
                )
                return df

        df = df.copy()
        if needs_year:
            df["year"] = series.dt.year
            logger.info(f"  • Derived 'year' from '{col}'")
        if needs_month:
            df["month"] = series.dt.month.astype(str).str.zfill(2)
            logger.info(f"  • Derived 'month' from '{col}'")

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Saves the transformed data.

        Supports Hive-style partitioned output when partition_by is configured.
        In incremental mode with partition_by, writes each unique partition
        combination to its own subdirectory (e.g., year=2024/month=03/).

        Args:
            df: Transformed DataFrame
            path: Output path

        Raises:
            ETLError: If data cannot be saved
        """
        try:
            from energizados.core.utils.integrity_pickle import validate_no_traversal

            validate_no_traversal(path, label=f"ETL '{self.name}' output")
            output_path = Path(path)

            # Derive year/month partition columns from incremental_key if needed
            if self.incremental_key and self.partition_by and not df.empty:
                df = self._derive_partition_columns(df)

            # Handle incremental mode without incremental_key: skip if already exists
            # and write_mode is "append"
            if self.mode == "incremental" and not self.reprocess and not self.incremental_key:
                if output_path.exists():
                    logger.info(f"  • Skipping save (already exists and reprocess=False): '{path}'")
                    return

            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle Hive-style partitioned output
            if self.partition_by:
                self._save_partitioned(df, path)
            else:
                # Standard single-file output
                if output_path.suffix == ".parquet" or output_path.suffix == ".pq":
                    df.to_parquet(path, index=False)
                elif output_path.suffix == ".csv":
                    df.to_csv(path, index=False, **self.output_params)
                else:
                    df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

                logger.info(f"  ✓ Saved {len(df)} records to '{path}'")

        except Exception as e:
            raise ETLError(f"Error saving '{self.name}': {str(e)}")

    def _save_partitioned(self, df: pd.DataFrame, base_path: str) -> None:
        """
        Save DataFrame with Hive-style partitioning.

        Writes each unique combination of partition columns to its own
        subdirectory (e.g., base_path/year=2024/month=03/file.parquet).

        Args:
            df: DataFrame to save
            base_path: Base output path
        """
        import pandas.api.types as pdt

        # Validate partition columns exist
        missing_cols = [c for c in self.partition_by if c not in df.columns]
        if missing_cols:
            raise ETLError(
                f"SourceETL '{self.name}': partition_by columns not found in DataFrame: {missing_cols}"
            )

        # Convert partition columns to string (required for Hive partitioning)
        df_partitioned = df.copy()
        for col in self.partition_by:
            # Convert to string representation
            if pdt.is_integer_dtype(df_partitioned[col]):
                df_partitioned[col] = df_partitioned[col].astype(str)
            else:
                df_partitioned[col] = (
                    df_partitioned[col].astype(str).str.replace("/", "-", regex=False)
                )

        # Get unique partition combinations
        partition_groups = df_partitioned.groupby(self.partition_by, sort=False)

        total_records = 0
        for partition_values, group_df in partition_groups:
            # Build partition path (e.g., base_path/year=2024/month=03/)
            if isinstance(partition_values, tuple):
                partition_parts = [
                    f"{col}={val}" for col, val in zip(self.partition_by, partition_values)
                ]
            else:
                partition_parts = [f"{self.partition_by[0]}={partition_values}"]

            # Use pathlib for cross-platform path joining (handles Windows backslashes)
            partition_dir = Path(base_path).joinpath(*partition_parts)
            partition_dir.mkdir(parents=True, exist_ok=True)

            # Determine output file within partition
            output_file = partition_dir / "data.parquet"
            group_df.drop(columns=self.partition_by, inplace=True)

            # Handle existing partition file based on write_mode setting
            if output_file.exists():
                if self.write_mode == "replace":
                    logger.info(f"  • Replacing partition: '{output_file}'")
                else:
                    existing = pd.read_parquet(output_file)
                    group_df = pd.concat([existing, group_df], ignore_index=True)

            # Determine format
            base_path_obj = Path(base_path)
            if base_path_obj.suffix == ".csv":
                output_file = output_file.with_suffix(".csv")
                group_df.to_csv(output_file, index=False, **self.output_params)
            else:
                group_df.to_parquet(output_file, index=False)

            total_records += len(group_df)
            logger.info(
                f"  • Saved {len(group_df)} records to '{output_file}' "
                f"({'/'.join(partition_parts)})"
            )

        logger.info(f"  ✓ Saved {total_records} records partitioned by {self.partition_by}")


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

        from energizados.core.utils.integrity_pickle import validate_no_traversal

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
                f"ClipOutliersETL '{self.name}': no columns matched — returning data unchanged"
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
            f"  ✓ Clipped {n_total:,} values to {self.threshold:,.0f} in {len(cols)} columns"
        )

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save clipped dataset."""
        from energizados.core.utils.integrity_pickle import validate_no_traversal

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


class CleanFilesETL(BaseETL):
    """ETL that deletes files listed in ``input``.

    The files to delete are specified in the YAML ``input`` field — the same
    field used by every other ETL. This means you can use:

    - Direct paths: ``"data/processed/consumos.parquet"``
    - References to other ETL outputs: ``"@consumos"`` (resolved by the orchestrator)
    - Glob patterns: ``"data/processed/intermediates/*.parquet"``

    This ETL does not read or produce a dataset — it overrides ``run()``
    directly and returns an empty DataFrame so the orchestrator can track
    it normally in the DAG.

    Args:
        name: ETL name.
        input_paths: Resolved list of file paths to delete (injected by the
            orchestrator from the ``input`` field after resolving ``@refs`` and globs).
        missing_ok: If True (default), silently skip files that don't exist.
            If False, raise an error for missing files.
        output_path: Optional — no file is written. Can be omitted from YAML.
        **kwargs: Additional parameters (ignored).

    Example YAML:

    .. code-block:: yaml

        clean_files:
          enabled: true
          description: "Elimina archivos intermedios después del pipeline"
          input:
            - "@maestros"
            - "@consumos"
            - "@inspecciones"
            - "data/processed/dataset.parquet"
          custom_class: "energizados.etl.pipeline.CleanFilesETL"
          params:
            missing_ok: true
          depends_on:
            - geo_features
    """

    def __init__(
        self,
        name: str,
        input_paths: Optional[List[str]] = None,
        output_path: Optional[str] = None,
        missing_ok: bool = True,
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths or []
        self.output_path = output_path
        self.missing_ok = missing_ok
        self.kwargs = kwargs

    def run(self, output_path: Optional[str] = None) -> pd.DataFrame:  # type: ignore[override]
        """Delete all files in input_paths and return an empty DataFrame."""
        # Delegate to noop_load which contains the deletion logic.
        return self.noop_load()

    def noop_load(self) -> pd.DataFrame:
        """Delete files and return empty DataFrame (BaseETL noop override)."""
        from energizados.core.utils.integrity_pickle import validate_no_traversal

        deleted, skipped, failed = 0, 0, []

        for file_path in self.input_paths:
            # Validate path to prevent directory traversal attacks
            validate_no_traversal(file_path, label=f"CleanFilesETL '{self.name}' input")
            path = Path(file_path)
            if not path.exists():
                if self.missing_ok:
                    logger.info(f"  • Skipped (not found): '{file_path}'")
                    skipped += 1
                else:
                    raise ETLError(f"CleanFilesETL '{self.name}': file not found: '{file_path}'")
                continue

            try:
                path.unlink()
                logger.info(f"  • Deleted: '{file_path}'")
                deleted += 1
            except OSError as e:
                failed.append(file_path)
                logger.error(f"  ✗ Could not delete '{file_path}': {e}")

        if failed:
            raise ETLError(
                f"CleanFilesETL '{self.name}': failed to delete {len(failed)} file(s): {failed}"
            )

        logger.info(f"  ✓ CleanFilesETL: {deleted} deleted, {skipped} skipped")
        return pd.DataFrame()

    # --- BaseETL abstract method stubs (never called — run() is overridden) ---

    def extract(self) -> pd.DataFrame:
        raise NotImplementedError("CleanFilesETL does not use extract()")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError("CleanFilesETL does not use transform()")

    def load(self, df: pd.DataFrame, path: str) -> None:
        raise NotImplementedError("CleanFilesETL does not use load()")


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
        include_cluster: Add ``geo_cluster`` column via KMeans clustering (default: ``True``).
            Set to ``False`` to skip clustering and keep only hierarchy/distances features.
        random_state: Random seed for KMeans (default: ``42``).
        include_hierarchy: Add hierarchy columns via IBGE spatial join (default: ``True``).
            Accepts a bool (``True`` = all three levels, ``False`` = none) or a list
            of level names to include only specific levels. Level names accept
            Portuguese (``"estado"``, ``"municipio"``, ``"regiao"``) and English
            aliases (``"state"``, ``"municipality"``/``"city"``, ``"region"``).
            Output columns are named ``geo_{level}`` using the name as specified
            in config — e.g. ``["municipality", "region"]`` produces
            ``geo_municipality`` and ``geo_region``.
        include_distances: Add haversine distance columns to reference cities
            (default: ``True``).
        distance_cities: List of city names for distance calculation. If ``None``,
            uses the top-5 default. Available cities: sao_paulo, rio_de_janeiro,
            brasilia, salvador, belo_horizonte, fortaleza, recife, curitiba,
            manaus, porto_alegre, florianopolis, blumenau, joinville, criciuma,
            chapeco, itajai, lages.
        include_coords: Keep original lat/lon columns in output (default: ``False``).
        cache_dir: Directory to persist IBGE shapefiles on disk (default: ``None``).
        regions_file: Path to a CSV (semicolon separator) or Parquet file with ``REGION``/``CITY`` columns. When
            provided, ``geo_regiao`` is assigned by matching each point's IBGE
            municipality name to the ``CITY`` column (accent- and
            case-insensitive). Takes priority over ``region_cities``.
            On ``fit()``, logs matched/unmatched municipalities and stores
            ``unmatched_municipalities_`` and ``matched_municipalities_``
            attributes on the underlying ``GeoFeatures`` transformer for
            diagnostics.
        region_cities: When set (and ``regions_file`` is not provided),
            ``geo_regiao`` is assigned as the nearest city from this list instead
            of the IBGE macro-region. Each entry must be a key in
            ``REFERENCE_CITIES``.
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
            include_cluster: true   # set to false to skip geo_cluster (KMeans)
            include_hierarchy: true
            # include_hierarchy:               # or pick specific levels
            #   - estado
            #   - municipio
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
        include_cluster: bool = True,
        random_state: int = 42,
        include_hierarchy: Union[bool, List[str]] = True,
        include_distances: bool = True,
        distance_cities: Optional[List[str]] = None,
        include_coords: bool = False,
        cache_dir: Optional[str] = None,
        region_cities: Optional[List[str]] = None,
        regions_file: Optional[str] = None,
        geo_model_path: Optional[str] = None,
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self.lat_col = lat_col
        self.lon_col = lon_col
        self.n_clusters = n_clusters
        self.include_cluster = include_cluster
        self.random_state = random_state
        self.include_hierarchy = include_hierarchy
        self.include_distances = include_distances
        self.distance_cities = distance_cities
        self.include_coords = include_coords
        self.cache_dir = cache_dir
        self.region_cities = region_cities
        self.regions_file = regions_file
        self.geo_model_path = geo_model_path
        self.kwargs = kwargs

    def extract(self) -> pd.DataFrame:
        """Read input file."""
        if not self.input_paths:
            raise ETLError(f"GeoFeaturesETL '{self.name}': input_paths is empty")

        from energizados.core.utils.integrity_pickle import validate_no_traversal

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
        """Append geo features by delegating to the GeoFeatures transformer.

        ADR-0001: clustering + hierarchy both live in the GeoFeatures transformer now.
        This ETL is a thin file-I/O wrapper: read a parquet, hand the in-memory frame
        to one GeoFeatures instance, write the result back. The load-or-fit decision
        (train fits + persists, infer loads + predicts) is driven by whether
        ``geo_model_path`` exists on disk.
        """
        from energizados.preprocessing.geo_features import GeoFeatures

        df = df.copy()

        # R4: cast object columns to category to cut DataFrame-copy memory ~4x.
        _obj_cols = df.select_dtypes(include="object").columns
        if len(_obj_cols):
            df[_obj_cols] = df[_obj_cols].astype("category")
            logger.info("  \u2022 R4: cast %d object columns to category", len(_obj_cols))

        if self.lat_col not in df.columns or self.lon_col not in df.columns:
            raise ETLError(
                f"GeoFeaturesETL '{self.name}': columns '{self.lat_col}' or "
                f"'{self.lon_col}' not found. Available: {list(df.columns)}"
            )

        transformer = GeoFeatures(
            lat_col=self.lat_col,
            lon_col=self.lon_col,
            include_cluster=self.include_cluster,
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            include_hierarchy=self.include_hierarchy,
            include_target_encoding=False,
            include_distances=self.include_distances,
            distance_cities=self.distance_cities,
            include_coords=self.include_coords,
            cache_dir=self.cache_dir,
            region_cities=self.region_cities,
            regions_file=self.regions_file,
            geo_model_path=self.geo_model_path,
        )

        # load-or-fit branch (ADR-0001): train fits + persists; infer loads + predicts.
        # The transformer raises ValueError/TransformerError; the ETL owns the ETLError
        # contract at its boundary (mirrors DatasetBuilderETL.run).
        try:
            if self.geo_model_path and Path(self.geo_model_path).exists():
                transformer.load()
                transformer.fit(df)
            else:
                transformer.fit(df)
                if self.geo_model_path:
                    transformer.save()
            return transformer.transform(df)
        except ETLError:
            raise
        except Exception as e:
            raise ETLError(
                f"GeoFeaturesETL '{self.name}': geo feature extraction failed: {e}"
            ) from e

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save enriched dataset."""
        from energizados.core.utils.integrity_pickle import validate_no_traversal

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


class AssumedNegativesETL(BaseETL):
    """ETL that derives **Assumed Negatives** via an anti-join.

    An Assumed Negative is a consumption row whose client id has no inspection
    record — downstream, ``split.unlabeled_negatives`` labels these rows
    ``target=0`` by assumption. This ETL materializes them as a standalone,
    inspectable parquet. It never modifies either input source or the main
    training dataset.

    Input roles are positional and each may be a literal path or an
    ``@etl_name`` reference (resolved by the orchestrator):

    - ``input_paths[0]``: **consumption** source (columns are preserved as-is)
    - ``input_paths[1]``: **inspections** source (only ``id_column`` is used)

    Exactly 2 inputs are required. The orchestrator silently drops ``@refs``
    to disabled ETLs during resolution, so a shrunk input list fails loudly
    here instead of silently joining against the wrong role.

    The anti-join runs in ``transform()`` (not ``extract()``) on purpose:
    ``BaseETL.run`` short-circuits when ``extract()`` returns 0 rows, which
    would skip ``load()``. Keeping the anti-join in ``transform()`` guarantees
    an empty result still writes a 0-row parquet.

    Args:
        name: ETL name.
        input_paths: Exactly 2 paths — [consumption, inspections].
        output_path: Path to save the assumed negatives parquet.
        id_column: Join column present in both sources (required).
        **kwargs: Additional parameters (ignored).

    Example YAML:
        .. code-block:: yaml

            negatives:
              enabled: true
              description: "Consumption rows with no inspection record"
              input:
                - "data/processed/dataset.parquet"   # consumption
                - "@inspecciones"                     # inspections
              output: "data/processed/assumed_negatives.parquet"
              custom_class: "energizados.etl.pipeline.AssumedNegativesETL"
              params:
                id_column: "contract_id"
              depends_on: [inspecciones]
    """

    def __init__(
        self,
        name: str,
        input_paths: Optional[List[str]] = None,
        output_path: Optional[str] = None,
        id_column: Optional[str] = None,
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths or []
        self.output_path = output_path
        self.id_column = id_column
        self.kwargs = kwargs
        self._inspection_ids: set = set()

        if not id_column:
            raise ValueError(
                f"AssumedNegativesETL '{self.name}': params.id_column is required. "
                "Set it to the join column present in both sources "
                "(e.g. id_column: 'contract_id')."
            )

        if len(self.input_paths) != 2:
            raise ValueError(
                f"AssumedNegativesETL '{self.name}': expected exactly 2 inputs "
                f"[consumption, inspections], got {len(self.input_paths)}. "
                "Note: an '@etl_name' reference to a disabled ETL is silently "
                "dropped during resolution — enable the referenced ETL or use a "
                "literal path."
            )

    def _read_source(self, role: str, path: str) -> pd.DataFrame:
        """Read one input source and validate id_column presence.

        Args:
            role: Role name ("consumption" or "inspections") for error messages.
            path: Path to the source file.

        Returns:
            DataFrame with the file contents.

        Raises:
            ETLError: If the file is missing, unreadable, or lacks id_column.
        """
        from energizados.core.utils.integrity_pickle import validate_no_traversal

        validate_no_traversal(path, label=f"ETL '{self.name}' {role} input")
        source_file = Path(path)

        if not source_file.exists():
            raise ETLError(f"File not found ({role}): {path}")

        if source_file.suffix in [".parquet", ".pq"]:
            df = pd.read_parquet(path)
        elif source_file.suffix == ".csv":
            df = pd.read_csv(path)
        else:
            raise ETLError(f"Unsupported format for {role} source: {source_file.suffix}")

        logger.info(f"  • Read {len(df)} records from {role} source '{source_file.name}'")

        if self.id_column not in df.columns:
            raise ETLError(
                f"AssumedNegativesETL '{self.name}': id_column '{self.id_column}' not "
                f"found in the {role} source '{path}'. "
                f"Available columns: {list(df.columns)}"
            )

        return df

    def extract(self) -> pd.DataFrame:
        """Read both sources and return the consumption frame.

        The inspections id set is cached on the instance for the anti-join in
        ``transform()``.
        """
        consumption = self._read_source("consumption", self.input_paths[0])
        inspections = self._read_source("inspections", self.input_paths[1])

        self._inspection_ids = set(inspections[self.id_column])
        logger.info(
            f"  • {len(self._inspection_ids)} distinct inspected ids " f"('{self.id_column}')"
        )
        return consumption

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Anti-join: keep consumption rows whose id has no inspection record.

        Rows are never collapsed or deduplicated — duplicate consumption ids
        are emitted as-is and counted in the join-stats log.
        """
        rows_in = len(df)
        mask = ~df[self.id_column].isin(self._inspection_ids)
        matched = int((~mask).sum())
        emitted = df[mask].copy()

        duplicated_rows = int(df[self.id_column].duplicated(keep=False).sum())

        logger.info(
            f"  ✓ Anti-join stats: consumption_in={rows_in}, matched={matched}, "
            f"emitted={len(emitted)}, duplicated_id_rows={duplicated_rows}"
        )

        if len(emitted) == 0:
            logger.warning(
                f"AssumedNegativesETL '{self.name}': no assumed negatives were "
                "identified (every consumption id has an inspection record). "
                "A 0-row parquet will be written."
            )

        return emitted

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save the assumed negatives parquet (0-row result included)."""
        from energizados.core.utils.integrity_pickle import validate_no_traversal

        validate_no_traversal(path, label=f"ETL '{self.name}' output")
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix in [".parquet", ".pq"]:
            df.to_parquet(path, index=False)
        elif output_path.suffix == ".csv":
            df.to_csv(path, index=False)
        else:
            df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

        logger.info(f"  ✓ Saved {len(df)} assumed negatives to '{path}'")
