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

### Config Name Resolution

Config names are resolved to files in `config/` directory:
- `etls` → `config/etls.yaml`
- `training` → `config/training.yaml`
- `etls,training` → `config/etls.yaml` + `config/training.yaml`
- Absolute paths are passed through unchanged
- Use `--config-path` to override the default directory

### Examples

```bash
# Run full pipeline with multiple configs
energizados run etls,training

# Run only one step
energizados run training --step split
energizados run training --step training

# Run a specific ETL
energizados run etls --etl sample

# Dry run (see plan without executing)
energizados run etls --dry-run

# Use custom config directory
energizados run --config-path /custom/path etls,training
```

---

## `energizados validate <configs> [options]`

Validates YAML configuration files.

### Required Arguments

- `configs`: Comma-separated config names (e.g., `etls,training`)

### Optional Options

- `--config-path, -p`: Override config directory (default: `config/`)
- `--verbose, -v`: Show detailed validation information

### Config Name Resolution

Same resolution rules as `energizados run` command (see above).

### Examples

```bash
# Validate single config
energizados validate etls

# Validate multiple configs with detailed output
energizados validate etls,training --verbose
```

---

## `energizados run eda [options]`

Runs exploratory data analysis (EDA) on a dataset using `config/eda.yaml`.

**Note**: The `eda` subcommand has been removed. Use `energizados run eda` instead.

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
energizados run training -v

# Run with DEBUG level logging
energizados run training -vv
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
energizados run etls

# 2. Train models
energizados run training

# 3. Evaluate results (if not included in training)
energizados run training --step evaluation
```

### Development Workflow

```bash
# 1. Validate configuration
energizados validate etls,training

# 2. Dry run to check execution plan
energizados run etls --dry-run

# 3. Run with verbose output for debugging
energizados run training -vv
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
