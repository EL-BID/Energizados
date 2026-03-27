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
| `input` | string or list | Input file path(s) (parquet, CSV) or `@etl_name` references |
| `output` | string | Output file path |
| `custom_class` | string | Python class implementing `BaseETL` |
| `depends_on` | list | List of ETL names this ETL depends on |

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | `null` | Human-readable description of the ETL |
| `params` | dict | `{}` | ETL-specific parameters (includes `mode`, `sample`, `merge_config`, etc.) |

## SourceETL

The `SourceETL` class is the built-in ETL implementation that supports two modes:

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

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `"concat"` | Must be `"concat"` for vertical concatenation |

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

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `"concat"` | Must be `"merge"` for horizontal merge |
| `merge_config` | dict | `{}` | Parameters passed to `pandas.merge()` |

**`merge_config` Options:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `how` | string | `"left"` | Type of merge: `"left"`, `"right"`, `"inner"`, `"outer"` |
| `on` | string or list | `null` | Column name(s) to merge on |
| `left_on` | string or list | `null` | Column(s) in left DataFrame to use as keys |
| `right_on` | string or list | `null` | Column(s) in right DataFrame to use as keys |
| `left_index` | boolean | `false` | Use left DataFrame's index as merge key |
| `right_index` | boolean | `false` | Use right DataFrame's index as merge key |

> ⚠️ **IMPORTANT:** When `mode="merge"`, `merge_config` is required.

### Sampling

Use the `sample` parameter to read only a subset of rows from input data. Useful for development, testing, and debugging without loading full datasets.

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

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sample` | integer | `null` | Number of rows to sample from input (uses `random_state=42` for reproducibility) |

> 💡 **Tip:** If `sample` is greater than the number of available rows, pandas returns all available rows without error.

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
    lat_col: "latitude"
    lon_col: "longitude"
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

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat_col` | string | `"latitud"` | Latitude column name |
| `lon_col` | string | `"longitud"` | Longitude column name |
| `n_clusters` | int | `10` | Number of KMeans geographic clusters |
| `random_state` | int | `42` | Random seed for KMeans |
| `include_hierarchy` | bool | `true` | Add IBGE hierarchy columns |
| `include_distances` | bool | `true` | Add distance-to-city columns |
| `distance_cities` | list | top-5 | Cities for distance calculation (see available list below) |
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
