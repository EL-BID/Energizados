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

- `configs`: Comma-separated config names (e.g., `etls,training`)

### Optional Options

- `--config-path, -p`: Override config directory (default: `config/`)
- `--step, -s`: Execute only a specific pipeline step (`etl`, `split`, `training`, `evaluation`, `inference`)
- `--etl, -e`: Execute a specific ETL (and its dependencies). Valid only with multiple ETLs.
- `--dry-run, -d`: Show execution plan without executing anything
- `--verbose, -v`: Increase verbosity (-v: INFO, -vv/-vvv: DEBUG)

### Config Name Resolution

Config names are resolved to files in `config/` directory:
- `etl` → `config/etl.yaml`
- `train` → `config/train.yaml`
- `infer` → `config/infer.yaml`
- `etl,train` → `config/etl.yaml` + `config/train.yaml`
- Absolute paths are passed through unchanged
- Use `--config-path` to override the default directory

### Examples

```bash
# Run full pipeline with multiple configs
energizados run etl,train

# Run only one step
energizados run train --step split
energizados run train --step training

# Run a specific ETL
energizados run etl --etl sample

# Dry run (see plan without executing)
energizados run etl --dry-run

# Use custom config directory
energizados run --config-path /custom/path etl,train

# Run with verbose output
energizados run etl -v
energizados run train -vv
```

---

## `energizados validate <configs> [options]`

Validates YAML configuration files.

### Required Arguments

- `configs`: Comma-separated config names (e.g., `etls,training`)

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

## `energizados run eda [options]`

Runs exploratory data analysis (EDA) on a dataset using `config/eda.yaml`.

### Options

All options from `energizados run` are available when using `eda` config:
- `--config-path, -p`: Override config directory (default: `config/`)
- `--step, -s`: Execute only a specific pipeline step
- `--dry-run, -d`: Show execution plan without executing

### Config Name Resolution

Same resolution rules as `energizados run` command.

### Examples

```bash
# Run EDA with default config
energizados run eda

# Run EDA with custom config directory
energizados run --config-path /custom/path eda

# Dry run to see execution plan
energizados run eda --dry-run
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
| `training` | Train models (includes feature engineering) |
| `evaluation` | Evaluate trained models |
| `inference` | Run inference on new data |

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

← [Project Structure](project-structure.md) | [Configuration: ETLs](configuration/etls.md) →
