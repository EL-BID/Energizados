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

## `energizados run <configs> [options]`

Executes a pipeline from YAML configuration files.

### Required Arguments

- `configs`: Comma-separated config names (e.g., `etl,train`)

### Optional Options

- `--config-path, -p`: Override config directory (default: `config/`)
- `--step, -s`: Execute only a specific pipeline step (`etl`, `split`, `train`, `evaluation`, `infer`)
- `--etl, -e`: Execute a specific ETL (and its dependencies). Valid only with multiple ETLs.
- `--dry-run, -d`: Show execution plan without executing anything
- `--verbose, -v`: Increase verbosity (-v: INFO, -vv/-vvv: DEBUG)
- `--name, -n`: Custom run directory name. Without this, auto-generated timestamp is used (e.g., `train-20260318_2209`). Only alphanumeric, dashes, and underscores allowed.
- `--overwrite, -o`: Overwrite existing output directory if it exists
- `--log-file, -l`: Save logs to a file (e.g., `output/run.log`)

### Config Name Resolution

Before executing, the CLI checks the `schema_version` inside each config section (etl, train, eda, infer) to verify compatibility with the installed framework. If a config section uses a newer schema than the framework supports, an error is raised with upgrade instructions.

Config names are resolved to files in `config/` directory:
- `etl` → `config/etl.yaml`
- `train` → `config/train.yaml`
- `infer` → `config/infer.yaml`
- `eda` → `config/eda.yaml`
- `etl,train` → `config/etl.yaml` + `config/train.yaml`
- Subdirectory paths: `v0/etl` → `config/v0/etl.yaml`
- Wildcards: `v0/train*` → all matching files in `config/v0/`
- Absolute paths are passed through unchanged
- Use `--config-path` to override the default directory

### Examples

```bash
# Run full pipeline with multiple configs
energizados run etl,train

# Run only one step
energizados run train --step split
energizados run train --step train

# Run a specific ETL
energizados run etl --etl sample

# Dry run (see plan without executing)
energizados run etl --dry-run

# Use custom config directory
energizados run --config-path /custom/path etl,train

# Run with verbose output
energizados run etl -v
energizados run train -vv

# Run with custom run directory name
energizados run train -n mi-experimento-v1    # Custom run directory name
energizados run train -n experimento-v2       # Replaces if already exists

# Run with wildcard config names
energizados run train_01* -v                  # All configs matching pattern

# Overwrite existing output directory
energizados run train -o                       # Overwrite if exists

# Save logs to file
energizados run train -l output/run.log        # Save logs to file
energizados run train -o -l output/run.log      # Combine options

# Run EDA
energizados run eda
energizados run eda -v
```

---

## `energizados validate <configs> [options]`

Validates YAML configuration files.

### Required Arguments

- `configs`: Comma-separated config names (e.g., `etl,train`)

### Optional Options

- `--config-path, -p`: Override config directory (default: `config/`)
- `--verbose, -v`: Increase verbosity (-v: INFO, -vv/-vvv: DEBUG)

### Config Name Resolution

Same resolution rules as `energizados run` command (see above).

### Examples

```bash
# Validate single config
energizados validate etl

# Validate multiple configs
energizados validate etl,train

# Validate with verbose output
energizados validate etl -v
energizados validate etl,train -vv
```

---

## `energizados doctor [options]`

Checks system information and validates the environment.

### Options

- `--verbose, -v`: Increase verbosity (-v: INFO, -vv/-vvv: DEBUG)
- `--optional, -o`: Include optional visualization packages (matplotlib, seaborn)

### Examples

```bash
# Basic system check
energizados doctor

# Verbose system information
energizados doctor -v
energizados doctor -vv

# Include optional packages
energizados doctor --optional
```

---

## Pipeline Steps

The `--step` option in `energizados run` accepts the following values:

| Step | Description |
|------|-------------|
| `etl` | Run ETL processes defined in `etl.yaml` |
| `split` | Split data into train/val/test sets |
| `train` | Train models (includes feature engineering) |
| `evaluation` | Evaluate trained models |
| `infer` | Run inference on new data |

> **Note:** `energizados run eda` uses the same `run` command with `eda` as the config name. It is not a separate CLI command — it simply resolves to `config/eda.yaml`.

---

## Common Workflows

### Full Training Pipeline

```bash
# 1. Run ETLs
energizados run etl

# 2. Train models
energizados run train

# 3. Evaluate results (if not included in training)
energizados run train --step evaluation
```

### Development Workflow

```bash
# 1. Validate configuration
energizados validate etl,train

# 2. Dry run to check execution plan
energizados run etl --dry-run

# 3. Run with verbose output for debugging
energizados run train -vv
```

### EDA Workflow

```bash
# Run EDA using config
energizados run eda

# Run EDA with verbose output
energizados run eda -v
```

---

← [Project Structure](project-structure.md) | [Configuration: ETL](configuration/etl.md) →
