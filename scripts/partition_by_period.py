#!/usr/bin/env python3
"""
Partition files by year-month extracted from a date column.

Takes a glob pattern of input files, concatenates them, and optionally
generates one output file per year-month period found in the specified
date column.

Usage examples:
    # Partition by date column (generates one file per year-month)
    python partition_by_period.py "data/raw/consumos_*.csv" fecha_actualizacion output/
    python partition_by_period.py "data/*.csv" fecha_proceso output/ -s ";"
    python partition_by_period.py "data/raw/*.parquet" fecha_inspeccion output/
    python partition_by_period.py "data/*.xlsx" fecha_registro output/

    # Just concatenate files (no partition column)
    python partition_by_period.py "data/*.csv" "" output/
    python partition_by_period.py "data/raw/*.parquet" output/    # alternative syntax

    # With custom CSV params (same as framework)
    python partition_by_period.py "data/*.csv" fecha output/ --csv-params "encoding=utf-8,sep=;"

    # With custom date format
    python partition_by_period.py "data/*.csv" DAT_OCORRENCIA output/ --date-format "%d/%m/%Y"
    python partition_by_period.py "data/*.csv" fecha output/ --date-format "mixed" --dayfirst

    python scripts/partition_by_period.py "data/raw/inspecciones*.csv" DAT_OCORRENCIA output/inspecciones --csv-params "encoding=utf-8,sep=;" --date-format "%d/%m/%Y"
    python scripts/partition_by_period.py "data/raw/consumos*.csv" PERIODO output/consumos --csv-params "encoding=utf-8,sep=;" --date-format "%Y%m"
    python scripts/partition_by_period.py "data/raw/maestros*.csv" "" output/maestros --csv-params "encoding=utf-8,sep=;"

Output (with date_column):
    output/
    ├── data_2018_01.csv
    ├── data_2018_02.csv
    └── ...

Output (without date_column):
    output/
    └── data_concatenated.csv
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_csv_params(params_str: Optional[str]) -> dict:
    """
    Parse CSV parameters from string format.

    Supports two formats:
    1. JSON-like: '{"encoding": "utf-8", "sep": ";"}'
    2. Key=value comma-separated: "encoding=utf-8,sep=;"
    """
    if not params_str:
        return {}

    params_str = params_str.strip()

    # Try JSON format first
    if params_str.startswith("{") or params_str.startswith("["):
        try:
            return json.loads(params_str)
        except json.JSONDecodeError:
            pass

    # Try key=value format
    result = {}
    for part in params_str.split(","):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
            # Try to parse as number
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
            result[key] = value

    return result


def read_file(
    file_path: Path, separator: str = ",", csv_params: Optional[dict] = None
) -> pd.DataFrame:
    """Read file based on its extension."""
    suffix = file_path.suffix.lower()
    csv_params = csv_params or {}

    if suffix == ".csv":
        # Merge default separator with custom params (custom params take precedence)
        params = {"sep": separator}
        params.update(csv_params)
        return pd.read_csv(file_path, **params)
    elif suffix == ".parquet":
        return pd.read_parquet(file_path)
    elif suffix in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported format: {suffix}")


def write_file(
    df: pd.DataFrame, file_path: Path, separator: str = ",", csv_params: Optional[dict] = None
) -> None:
    """Write file based on its extension."""
    suffix = file_path.suffix.lower()
    csv_params = csv_params or {}

    if suffix == ".csv":
        write_params = {"sep": separator, "index": False}
        # Propagate encoding from csv_params if present
        if "encoding" in csv_params:
            write_params["encoding"] = csv_params["encoding"]
        df.to_csv(file_path, **write_params)
    elif suffix == ".parquet":
        df.to_parquet(file_path, index=False)
    elif suffix in [".xlsx", ".xls"]:
        df.to_excel(file_path, index=False)
    else:
        raise ValueError(f"Unsupported format: {suffix}")


def partition_files(
    input_pattern: str,
    date_column: Optional[str],
    output_dir: str,
    separator: str = ",",
    csv_params: Optional[dict] = None,
    date_format: Optional[str] = None,
    dayfirst: bool = False,
) -> dict:
    """
    Partition files by year-month extracted from date_column.

    If date_column is None or empty, simply concatenates all files.

    Args:
        input_pattern: Glob pattern (e.g., "data/raw/*.csv")
        date_column: Column name containing the date/period. If None or empty,
                     files are just concatenated.
        output_dir: Output directory (created if not exists)
        separator: CSV separator (default: ",")
        csv_params: Additional parameters for pd.read_csv (same as framework)
        date_format: Format string for pd.to_datetime (e.g., "%d/%m/%Y")
        dayfirst: Treat dates as day-first (dd/mm/yyyy) format

    Returns:
        Dict mapping period to output file path
    """
    input_path = Path(input_pattern)
    base_dir = input_path.parent

    # Find all matching files
    files = sorted(base_dir.glob(input_path.name))

    if not files:
        logger.warning(f"No files found matching pattern: {input_pattern}")
        return {}

    logger.info(f"Found {len(files)} files matching pattern")

    # Read and concatenate all files
    dfs = []
    failed_files = []
    for f in files:
        logger.info(f"Reading {f}")
        try:
            df = read_file(f, separator, csv_params)
            dfs.append(df)
        except Exception as e:
            failed_files.append((f, str(e)))
            logger.error(f"FAILED to read {f}: {e}")

    if failed_files:
        logger.error(
            f"{len(failed_files)} file(s) failed to read: " f"{[str(f) for f, _ in failed_files]}"
        )
        raise RuntimeError(
            f"Aborting: {len(failed_files)} file(s) could not be read. "
            f"Fix the files or remove them from the glob pattern."
        )

    if not dfs:
        logger.error("No data to process")
        return {}

    df = pd.concat(dfs, ignore_index=True)
    logger.info(f"Total rows: {len(df)}")

    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    # Get output format from first input file
    output_ext = files[0].suffix
    result = {}

    total_input = len(df)

    # If no date_column specified, just concatenate
    if not date_column:
        output_filename = f"data_concatenated{output_ext}"
        output_path = output_dir / output_filename
        write_file(df, output_path, separator, csv_params)
        result["concatenated"] = str(output_path)
        logger.info(f"Written {len(df)} rows to {output_path}")
        return result

    # Parse date column into a separate helper column (preserve original)
    try:
        df["_parsed_date"] = pd.to_datetime(
            df[date_column], format=date_format, dayfirst=dayfirst, errors="coerce"
        )
    except Exception as e:
        logger.error(f"Could not parse column '{date_column}' as datetime: {e}")
        raise

    # Separate rows with invalid dates — save to file instead of dropping
    invalid_mask = df["_parsed_date"].isna()
    null_dates = invalid_mask.sum()
    if null_dates > 0:
        invalid_df = df.loc[invalid_mask].drop(columns=["_parsed_date"])
        invalid_path = output_dir / f"data_invalid_dates{output_ext}"
        write_file(invalid_df, invalid_path, separator, csv_params)
        logger.warning(f"Found {null_dates} rows with unparseable dates → saved to {invalid_path}")
        result["_invalid_dates"] = str(invalid_path)
        df = df.loc[~invalid_mask]

    df["_year"] = df["_parsed_date"].dt.year
    df["_month"] = df["_parsed_date"].dt.month

    total_output = 0
    for (year, month), group in df.groupby(["_year", "_month"]):
        period = f"{year}_{month:02d}"

        # Output filename: same name as input + period prefix
        output_filename = f"data_{period}{output_ext}"
        output_path = output_dir / output_filename

        # Drop helper columns from output (original date_column is preserved)
        output_df = group.drop(columns=["_year", "_month", "_parsed_date"])

        # Write
        write_file(output_df, output_path, separator, csv_params)

        total_output += len(output_df)
        result[period] = str(output_path)
        logger.info(f"Written {len(output_df)} rows to {output_path}")

    # Integrity check: all rows accounted for
    total_accounted = total_output + null_dates
    if total_accounted != total_input:
        raise RuntimeError(
            f"DATA INTEGRITY ERROR: input={total_input}, "
            f"output={total_output}, invalid={null_dates}, "
            f"accounted={total_accounted}"
        )
    logger.info(
        f"Integrity OK: {total_input} input rows = "
        f"{total_output} partitioned + {null_dates} invalid"
    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Partition or concatenate files by year-month from date column"
    )
    parser.add_argument(
        "input_pattern", help="Glob pattern for input files (e.g., 'data/raw/*.csv')"
    )
    parser.add_argument(
        "date_column",
        nargs="?",
        default=None,
        help="Column with date/period. If empty, files are just concatenated.",
    )
    parser.add_argument("output_dir", help="Output directory (created if not exists)")
    parser.add_argument("--separator", "-s", default=",", help="CSV separator (default: ',')")
    parser.add_argument(
        "--csv-params",
        "-p",
        default=None,
        help="CSV params as JSON or key=value pairs (e.g., '{\"encoding\": \"utf-8\"}' or 'encoding=utf-8,sep=;')",
    )
    parser.add_argument(
        "--date-format",
        "-f",
        default=None,
        help="Date format for pd.to_datetime (e.g., '%%d/%%m/%%Y', 'mixed', 'ISO8601')",
    )
    parser.add_argument(
        "--dayfirst",
        action="store_true",
        help="Treat dates as day-first (dd/mm/yyyy) format",
    )

    args = parser.parse_args()

    csv_params = parse_csv_params(args.csv_params)
    if csv_params:
        logger.info(f"CSV params: {csv_params}")

    if args.date_format:
        logger.info(f"Date format: {args.date_format}, dayfirst: {args.dayfirst}")

    result = partition_files(
        args.input_pattern,
        args.date_column,
        args.output_dir,
        args.separator,
        csv_params,
        args.date_format,
        args.dayfirst,
    )

    logger.info(f"Generated {len(result)} files")

    logger.info("Archivos generados:")
    for period, path in result.items():
        logger.info(f"  {period}: {path}")


if __name__ == "__main__":
    main()
