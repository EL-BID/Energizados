# ETL Configuration

Complete reference for `etl.yaml` configuration.

## Overview

The ETL configuration file defines data extraction, transformation, and loading processes. Each ETL can depend on other ETLs, creating a Directed Acyclic Graph (DAG) that executes in topological order.

## File Structure

```yaml
etl:
  etl_name:
    enabled: true                    # Whether to execute this ETL
    description: "ETL description"  # Human-readable description
    input: "path/to/input.parquet"  # Input file path or list of paths
    output: "path/to/output.parquet"# Output file path
    custom_class: "module.ETLClass"  # Python class to use
    params:                          # ETL-specific parameters
      # parameter: value
    depends_on: []                   # List of ETL names this depends on
```

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Whether to execute this ETL |
| `input` | string or list | Input file path(s) (parquet, CSV, Excel) or `@etl_name` references |
| `output` | string | Output file path (`CleanFilesETL` can omit this) |
| `custom_class` | string | Python class implementing `BaseETL` |
| `depends_on` | list | List of ETL names this ETL depends on |

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | `null` | Human-readable description of the ETL |
| `params` | dict | `{}` | ETL-specific parameters (includes `mode`, `sample`, `merge_config`, etc.) |

## SourceETL

`SourceETL` is the built-in ETL implementation. It reads CSV, Parquet (`.parquet`/`.pq`), and Excel (`.xlsx`/`.xls`) files and supports two processing modes.

> **Note:** New projects created with `energizados init` use `custom_class: "data.custom_etl.CustomETL"` for the sample ETL — this is the generated `CustomETL` class in `src/data/custom_etl.py`, which extends `BaseETL`. Use `energizados.etl.pipeline.SourceETL` when you want the built-in implementation directly without a custom class.

### Mode: Concat (Vertical Concatenation)

Concatenates multiple input files vertically (stacks rows).

```yaml
etl:
  concatenar:
    enabled: true
    description: "Concatenates multiple CSV files"
    input:
      - "data/2023.csv"
      - "data/2024.csv"
    output: "data/complete.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []
```

### Mode: Merge (Horizontal Merge)

Merges multiple input files horizontally using pandas `merge()`.

```yaml
etl:
  merge_dataset:
    enabled: true
    description: "Combines consumption and customer data"
    input:
      - "data/consumos.parquet"
      - "data/clientes.parquet"
    output: "data/merged.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "merge"
      merge_config:
        how: "left"       # 'left', 'right', 'inner', 'outer'
        on: "id_cliente"
    depends_on: []
```

**`merge_config` Options:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `how` | string | `"left"` | Type of merge: `"left"`, `"right"`, `"inner"`, `"outer"` |
| `on` | string or list | `null` | Column name(s) to merge on |
| `left_on` | string or list | `null` | Column(s) in left DataFrame to use as keys |
| `right_on` | string or list | `null` | Column(s) in right DataFrame to use as keys |
| `left_index` | boolean | `false` | Use left DataFrame's index as merge key |
| `right_index` | boolean | `false` | Use right DataFrame's index as merge key |

> **IMPORTANT:** When `mode="merge"`, `merge_config` is required. If `on`, `left_on`, and `right_on` are all omitted, `key_column` is used as the merge key.

### Mode: Incremental (Monthly Processing)

Processes only new/pending files based on state tracking. Ideal for monthly ETL workflows where you only want to process new data files.

```yaml
etl:
  consumos_monthly:
    enabled: true
    description: "Procesa solo archivos de consumos nuevos mensual"
    raw_glob: "data/raw/consumos_*.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "incremental"
      partition_by:
        - year
        - month
      overwrite: false
      state_file: "data/processed/.consumos_state.json"
    depends_on: []
```

**How it works:**
1. Discovers files matching `raw_glob` pattern
2. Compares with already processed files (via `state_file` or `processed_glob`)
3. Processes only pending files
4. Updates state file with processed files
5. Optionally writes output in Hive-partitioned structure

**Example with Hive partitioning:**

```yaml
etl:
  consumos_incremental:
    enabled: true
    raw_glob: "data/raw/consumos_*.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "incremental"
      partition_by:
        - year
        - month
      overwrite: false
      state_file: "data/processed/.consumos_state.json"
```

This writes to:
- `data/processed/consumos.parquet/year=2024/month=01/data.parquet`
- `data/processed/consumos.parquet/year=2024/month=02/data.parquet`
- etc.

### SourceETL Parameters Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `"concat"` | Processing mode: `"concat"`, `"merge"`, or `"incremental"` |
| `merge_config` | dict | `null` | Merge configuration. Required when `mode="merge"`. Accepts any `pandas.merge()` parameter. |
| `key_column` | string | `"id_cliente"` | Fallback merge key used when `merge_config` does not specify `on`, `left_on`, or `right_on` |
| `input_params` | dict | `{}` | Extra keyword arguments passed to the pandas read function (e.g. `sep`, `encoding`, `engine` for CSV). Applies to all input files equally. |
| `output_params` | dict | `{}` | Extra keyword arguments passed to the pandas write function. Only used when the output file is a CSV. |
| `transform_fn` | string or callable | `null` | Custom transform applied after reading and concatenating/merging. Accepts a dotted-path string (e.g. `"src.data.transforms.clean_data"`) or a Python callable. Must have signature `(pd.DataFrame) -> pd.DataFrame`. |
| `sample` | integer | `null` | Random sample of N rows taken from the combined result. Uses `random_state=42` for reproducibility. If N exceeds the available rows, all rows are returned. |
| `partition_by` | list | `null` | List of columns for Hive-style partitioning (e.g., `["year", "month"]`). Writes to `output/year=YYYY/month=MM/` structure. |
| `overwrite` | bool | `false` | If `true`, overwrites existing output files. If `false`, skips existing files in incremental mode. |
| `state_file` | string | `null` | Path to JSON file that tracks processed files. Used in incremental mode. Default: `<output_path>.state.json` |
| `raw_glob` | string | `null` | Glob pattern to discover raw input files (e.g., `data/raw/*.csv`). Used in incremental mode. |
| `processed_glob` | string | `null` | Glob pattern to find already processed files. Used in incremental mode to detect pending files. |

### Example: CSV with custom read options

```yaml
etl:
  consumos_csv:
    enabled: true
    description: "Semicolon-delimited CSV with custom options"
    input: "data/raw/consumos.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
      input_params:
        sep: ";"
        engine: "python"
        on_bad_lines: "skip"
    depends_on: []
```

### Example: Custom transform function

```yaml
etl:
  cleaned:
    enabled: true
    description: "Apply custom cleaning logic"
    input: "data/raw/dirty.csv"
    output: "data/processed/cleaned.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
      transform_fn: "src.data.transforms.clean_data"
    depends_on: []
```

### Example: Sampling for quick iteration

```yaml
etl:
  quick_test:
    enabled: true
    description: "Quick test with sampled data"
    input: "data/raw/full_dataset.csv"
    output: "data/processed/sample.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
      sample: 1000  # Read only 1000 rows
    depends_on: []
```

## ETL Dependencies

Use the `@` prefix to reference another ETL's output as input.

### Basic Example

```yaml
etl:
  # ETL 1: No dependencies
  consumos:
    enabled: true
    description: "Processes consumption data"
    input: "data/raw/consumos.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  # ETL 2: No dependencies
  clientes:
    enabled: true
    description: "Processes customer data"
    input: "data/raw/clientes.csv"
    output: "data/processed/clientes.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  # ETL 3: Depends on both consumos and clientes
  merge_dataset:
    enabled: true
    description: "Combines consumos and clientes"
    input:
      - "@consumos"    # References consumos ETL output
      - "@clientes"    # References clientes ETL output
    output: "data/processed/dataset_final.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "merge"
      merge_config:
        how: "left"
        on: "id_cliente"
    depends_on: ["consumos", "clientes"]
```

## Dependency Patterns

### Serial Pattern

ETLs execute one after another in sequence.

```yaml
etl:
  extract:
    enabled: true
    input: "data/raw/data.csv"
    output: "data/extracted.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  clean:
    enabled: true
    input: "@extract"
    output: "data/clean.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: ["extract"]

  features:
    enabled: true
    input: "@clean"
    output: "data/features.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: ["clean"]
```

### Parallel Pattern

Independent ETLs execute simultaneously.

```yaml
etl:
  source_a:
    enabled: true
    input: "data/a.csv"
    output: "data/a.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  source_b:
    enabled: true
    input: "data/b.csv"
    output: "data/b.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  merge:
    enabled: true
    input:
      - "@source_a"
      - "@source_b"
    output: "data/merged.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "merge"
      merge_config:
        how: "inner"
        on: "id"
    depends_on: ["source_a", "source_b"]
```

### Diamond Pattern (Convergence)

Multiple branches converge into a single ETL.

```yaml
etl:
  branch_a:
    enabled: true
    input: "data/a.csv"
    output: "data/a.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  branch_b:
    enabled: true
    input: "data/b.csv"
    output: "data/b.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  merge:
    enabled: true
    input:
      - "@branch_a"
      - "@branch_b"
    output: "data/merged.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "merge"
      merge_config:
        how: "outer"
        on: "id"
    depends_on: ["branch_a", "branch_b"]
```

## Complete Example

```yaml
etl:
  # Raw data ingestion (parallel)
  consumos_2023:
    enabled: true
    description: "Load 2023 consumption data"
    input: "data/raw/consumos_2023.csv"
    output: "data/processed/consumos_2023.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  consumos_2024:
    enabled: true
    description: "Load 2024 consumption data"
    input: "data/raw/consumos_2024.csv"
    output: "data/processed/consumos_2024.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  # Concatenate consumption data (serial)
  consumos_all:
    enabled: true
    description: "Combine 2023 and 2024 consumption data"
    input:
      - "@consumos_2023"
      - "@consumos_2024"
    output: "data/processed/consumos_all.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: ["consumos_2023", "consumos_2024"]

  # Load customer data (parallel)
  clientes:
    enabled: true
    description: "Load customer information"
    input: "data/raw/clientes.csv"
    output: "data/processed/clientes.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  # Merge with customer data (convergence)
  dataset_final:
    enabled: true
    description: "Final dataset with consumption and customer data"
    input:
      - "@consumos_all"
      - "@clientes"
    output: "data/processed/dataset_final.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "merge"
      merge_config:
        how: "left"
        on: "id_cliente"
    depends_on: ["consumos_all", "clientes"]
```

## GeoFeaturesETL

Adds geographic features from latitude/longitude coordinates. Combines KMeans geographic
clustering, IBGE administrative hierarchy, and haversine distance features in a single ETL step.
Run after the main dataset-building ETL and before training.

**Generated columns:**

| Column | Type | Description |
|--------|------|-------------|
| `geo_cluster` | int | KMeans cluster label (−1 for invalid/zero coordinates) |
| `geo_estado` | str | Brazilian state (UF) from IBGE spatial join |
| `geo_municipio` | str | Municipality from IBGE spatial join |
| `geo_regiao` | str | Macro region (Norte, Nordeste, Sudeste, Sul, Centro-Oeste) |
| `geo_dist_capital_estado` | float | Haversine distance to state capital (km) |
| `geo_dist_{city}` | float | Haversine distance to each city in `distance_cities` (km) |

> Unmatched coordinates (outside Brazil or with invalid values) get `"sin_dato"` for
> hierarchy columns and `−1` for `geo_cluster`.

```yaml
geo_features:
  enabled: true
  input: "@dataset_builder"
  output: "data/processed/dataset_with_geo.parquet"
  custom_class: "energizados.etl.pipeline.GeoFeaturesETL"
  params:
    lat_col: "latitud"     # default — Spanish spelling
    lon_col: "longitud"    # default — Spanish spelling
    n_clusters: 10
    random_state: 42
    include_hierarchy: true
    include_distances: true
    distance_cities:
      - sao_paulo
      - rio_de_janeiro
      - brasilia
    include_coords: false
    cache_dir: ".cache/ibge"
  depends_on: [dataset_builder]
```

> **Note:** At least 10 valid (non-zero, non-null) coordinate pairs are required to fit the KMeans clusters. Points with invalid or zero coordinates receive `geo_cluster=-1` and `"sin_dato"` for all IBGE hierarchy columns.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat_col` | string | `"latitud"` | Latitude column name (Spanish spelling by default) |
| `lon_col` | string | `"longitud"` | Longitude column name (Spanish spelling by default) |
| `n_clusters` | int | `10` | Number of KMeans geographic clusters |
| `random_state` | int | `42` | Random seed for KMeans |
| `include_hierarchy` | bool | `true` | Add `geo_estado`, `geo_municipio`, `geo_regiao` columns via IBGE spatial join |
| `include_distances` | bool | `true` | Add haversine distance columns to reference cities |
| `distance_cities` | list | `null` (top-5) | Cities for distance calculation (see available list below). If `null`, defaults to the top 5. |
| `include_coords` | bool | `false` | Keep original lat/lon columns in output |
| `cache_dir` | string | `null` | Directory to persist IBGE shapefiles on disk |

**Available cities for `distance_cities`:**

`sao_paulo`, `rio_de_janeiro`, `brasilia`, `salvador`, `belo_horizonte`, `fortaleza`,
`recife`, `curitiba`, `manaus`, `porto_alegre`, `florianopolis`, `blumenau`, `joinville`,
`criciuma`, `chapeco`, `itajai`, `lages`

> **Note:** `include_hierarchy` and `include_distances` require the `geobr` package.
> Set `cache_dir` to avoid re-downloading IBGE shapefiles on every run (recommended).

**Relationship with `stratified_time` split:** the `geo_cluster` column produced by this ETL
is required when using `method: stratified_time` in `train.yaml`.

## ClipOutliersETL

Clips extreme values in numeric columns. Designed to remove data reading errors (e.g., meter malfunctions recording values in the order of 10^16 kWh) before feature engineering. Run this ETL after the main dataset-building ETL and before training.

```yaml
etl:
  clip_outliers:
    enabled: true
    description: "Clip extreme consumption values (data reading errors)"
    input: "data/processed/dataset.parquet"
    output: "data/processed/dataset_clipped.parquet"
    custom_class: "energizados.etl.pipeline.ClipOutliersETL"
    params:
      threshold: 100000           # values above this are clipped to this value
      periods_suffix: "_anterior" # auto-detects columns ending in this suffix
    depends_on: []
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | float | `100000` | Maximum allowed value. Values above this are clipped to this value. |
| `columns` | list | `null` | Explicit list of column names to clip. If `null`, auto-detects all columns whose name ends with `periods_suffix`. |
| `periods_suffix` | string | `"_anterior"` | Suffix used for auto-detection when `columns` is not specified. |

## CleanFilesETL

Deletes files after the pipeline completes. Useful for removing intermediate outputs and freeing disk space. This ETL does not produce a dataset — it returns an empty DataFrame so the orchestrator can track it normally in the DAG.

The files to delete are specified in the `input` field, which supports:
- Direct paths: `"data/processed/consumos.parquet"`
- References to other ETL outputs: `"@consumos"` (resolved by the orchestrator)
- Glob patterns: `"data/processed/tmp_*.parquet"`

The `output` field is optional — no file is written.

```yaml
etl:
  clean_files:
    enabled: true
    description: "Remove intermediate outputs after pipeline completes"
    input:
      - "@consumos"                                    # reference to another ETL's output
      - "@clientes"
      - "data/processed/dataset_mergeado.parquet"      # direct path
      # - "data/processed/tmp_*.parquet"               # glob pattern also supported
    output: "data/processed/.clean_done"               # optional placeholder; no file written
    custom_class: "energizados.etl.pipeline.CleanFilesETL"
    params:
      missing_ok: true   # silently skip files that don't exist
    depends_on:
      - merge_dataset    # run last — after all ETLs that produce the files above
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `missing_ok` | boolean | `true` | If `true`, silently skip files that do not exist. If `false`, raise an error for any missing file. |

## Custom ETL Classes

To create a custom ETL, implement the `BaseETL` interface in `src/data/custom_etl.py`:

```python
from energizados.etl.base import BaseETL
import pandas as pd

class CustomETL(BaseETL):
    def __init__(self, name: str, input_paths: list, output_path: str, **kwargs):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        # Add any custom parameters from params section

    def extract(self) -> pd.DataFrame:
        # Read input data
        return pd.read_parquet(self.input_paths[0])

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        # Your custom logic here
        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        # Save output
        df.to_parquet(path)
```

Then reference it in `etl.yaml`:

```yaml
etl:
  custom_etl:
    enabled: true
    input: "data/raw/input.parquet"
    output: "data/processed/output.parquet"
    custom_class: "src.data.custom_etl.CustomETL"
    params:
      # Custom parameters
    depends_on: []
```

---

← [CLI Reference](../cli-reference.md) | [Configuration: Training](train.md) →
