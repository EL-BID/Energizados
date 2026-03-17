# CLI Reference

Complete reference for all Energizados CLI commands.

## `energizados init <name>`

Creates a new project from a template or copies an existing one.

### Options

- `--template, -t`: Template to use (default: `default`)
- `--path, -p`: Directory where to create the project (default: `.`)
- `--copy, -c`: Copy from an existing project (takes precedence over `--template`)
- `--force, -f`: Force creation, removing existing directory if necessary

### Examples

```bash
# Create from default template
energizados init my_project

# Create from a specific template
energizados init my_project --template advanced

# Copy from existing project
energizados init new --copy existing

# Force replace if exists
energizados init my_project --force
```

---

## `energizados run --config <file> [options]`

Executes a pipeline from a YAML configuration file.

### Required Options

- `--config, -c`: Path to YAML file (can be specified multiple times)

### Optional Options

- `--step, -s`: Execute only a specific pipeline step (`etl`, `split`, `training`, `evaluation`, `inference`)
- `--etl, -e`: Execute a specific ETL (and its dependencies). Valid only with multiple ETLs.
- `--dry-run, -d`: Show execution plan without executing anything

### Examples

```bash
# Run full pipeline with multiple config files
energizados run --config config/etls.yaml --config config/training.yaml

# Run only one step
energizados run --config config/training.yaml --step split
energizados run --config config/training.yaml --step training

# Run a specific ETL
energizados run --config config/etls.yaml --etl sample

# Dry run (see plan without executing)
energizados run --config config/etls.yaml --dry-run
```

---

## `energizados validate --config <file>`

Validates YAML configuration files.

### Options

- `--config, -c`: Path to YAML file (can be specified multiple times)
- `--verbose, -v`: Show detailed validation information

### Examples

```bash
# Validate single config
energizados validate --config config/etls.yaml

# Validate multiple configs with detailed output
energizados validate --config config/etls.yaml --config config/training.yaml --verbose
```

---

## `energizados eda [options]`

Runs exploratory data analysis (EDA) on a dataset.

### Options

- `--input, -i`: Path to input dataset (parquet or CSV). Overrides the config file.
- `--target, -t`: Name of binary target column.
- `--config, -c`: Path to `eda.yaml` configuration file.
- `--output, -o`: Output directory for report and plots.
- `--lat-col`: Latitude column name (enables geospatial analysis).
- `--lon-col`: Longitude column name (enables geospatial analysis).
- `--etl, -e`: Name of an ETL defined in `etls.yaml` whose output to analyze.
- `--skip-sections`: Comma-separated list of sections to skip (e.g., `geo,join,segmentation`).
- `--dry-run, -d`: Show configuration that would be used without executing analysis.

### Examples

```bash
# Basic analysis with input and target
energizados eda --input data/raw/dataset.parquet --target target

# Use configuration file
energizados eda --config config/eda.yaml

# Analyze output of an ETL
energizados eda --config config/eda.yaml --etl sample

# Enable geospatial analysis
energizados eda --config config/eda.yaml --lat-col LATITUDE --lon-col LONGITUDE

# Skip specific sections
energizados eda --config config/eda.yaml --skip-sections "geo,join"

# Dry run to see configuration
energizados eda --config config/eda.yaml --dry-run
```

---

## `energizados doctor [options]`

Checks system information and validates the environment.

### Options

- `--verbose, -v`: Show detailed system information
- `--optional, -o`: Include optional visualization packages (matplotlib, seaborn)

### Examples

```bash
# Basic system check
energizados doctor

# Detailed system information
energizados doctor --verbose

# Include optional packages
energizados doctor --optional
```

---

## Global Options

These options can be used with any command:

- `--verbose, -v`: Increase verbosity
  - `-v`: INFO level logging
  - `-vv` or `-vvv`: DEBUG level logging

### Examples

```bash
# Run with INFO level logging
energizados run --config config/training.yaml -v

# Run with DEBUG level logging
energizados run --config config/training.yaml -vv
```

---

## Pipeline Steps

The `--step` option in `energizados run` accepts the following values:

| Step | Description |
|------|-------------|
| `etl` | Run ETL processes defined in `etls.yaml` |
| `split` | Split data into train/val/test sets |
| `training` | Train models (includes feature engineering) |
| `evaluation` | Evaluate trained models |
| `inference` | Run inference on new data |

---

## Common Workflows

### Full Training Pipeline

```bash
# 1. Run ETLs
energizados run --config config/etls.yaml

# 2. Train models
energizados run --config config/training.yaml

# 3. Evaluate results (if not included in training)
energizados run --config config/training.yaml --step evaluation
```

### Development Workflow

```bash
# 1. Validate configuration
energizados validate --config config/etls.yaml --config config/training.yaml

# 2. Dry run to check execution plan
energizados run --config config/etls.yaml --dry-run

# 3. Run with verbose output for debugging
energizados run --config config/training.yaml -vv
```

### EDA Workflow

```bash
# 1. Run EDA on raw data
energizados eda --input data/raw/dataset.parquet --target target --output output/eda

# 2. Run EDA on processed data
energizados eda --config config/eda.yaml --etl sample
```

---

← [Project Structure](project-structure.md) | [Configuration: ETLs](configuration/etls.md) →
