# Project Structure

Understanding the project structure created by `energizados init`.

## Overview

When you run `energizados init <project_name>`, a complete project structure is generated with all necessary directories, configuration files, and example code.

## Directory Structure

```
my_project/
├── config/                 # YAML configuration files
│   ├── etl.yaml           # ETL configuration
│   ├── train.yaml         # Training pipeline configuration
│   ├── infer.yaml         # Inference configuration
│   └── eda.yaml           # Exploratory data analysis configuration
├── data/
│   ├── raw/               # Input data (includes sample_dataset.parquet)
│   ├── processed/         # ETL outputs and feature engineering results
│   └── temp/
│       └── splits/        # Train/val/test splits
├── output/                # Training run outputs (auto-created per run)
│   ├── index.html         # Summary table of all training runs
│   └── train-YYYYMMDD_HHMM/  # One directory per training execution
├── notebooks/
│   └── example_notebook.ipynb
├── src/
│   ├── data/              # Custom ETL (custom_etl.py)
│   ├── features/          # Custom feature selector (custom_selector.py)
│   ├── models/            # Custom model (custom_model.py)
│   ├── inference/         # Custom inference (custom_inference.py)
│   ├── utils/             # Shared utilities (helpers.py)
│   └── run/               # Execution scripts
│       ├── 00_etl.py
│       ├── 01_eda.py
│       ├── 02_training.py
│       └── 03_inference.py
├── docs/
│   └── project_docs.md
└── tests/
```

## Detailed Explanation

### `config/`

All pipeline configuration files in YAML format.

- **`etl.yaml`**: Defines ETL (Extract, Transform, Load) processes. Each ETL specifies input sources, transformations, and output locations. Supports dependencies between ETLs using `depends_on`.

- **`train.yaml`**: Configures the complete training pipeline:
  - **Split**: Data splitting strategy (stratified, random, time-series)
  - **Feature Engineering**: Preprocessing transformers and feature selection
  - **Models**: Model configuration (single or ensemble)
  - **Evaluation**: Metrics, reports, threshold settings

- **`infer.yaml`**: Defines inference parameters including input data path, model path, and output location.

- **`eda.yaml`**: Configuration for automated exploratory data analysis reports.

### `data/`

All data-related directories.

- **`raw/`**: Contains your raw input data. The template includes `sample_dataset.parquet` with 42,500 records demonstrating the expected data format.

- **`processed/`**: Where ETL outputs and feature engineering results are saved. Intermediate datasets are stored here.

- **`temp/splits/`**: Contains train/validation/test split files. Used when `split.save_splits: true` in training configuration.

### `output/`

Auto-generated directory containing all training outputs.

- **`index.html`**: Summary table showing all training runs and their metrics. Useful for comparing different experiments.

- **`train-YYYYMMDD_HHMM/`**: A timestamped directory for each training execution containing:
  - **`models/`**: Trained models and feature engineering pipeline
  - **`reports/evaluation/`**: HTML report, JSON report, and plots
  - **`config/`**: Copies of YAML config files used for this run

### `notebooks/`

Jupyter notebooks for interactive analysis and experimentation.

- **`example_notebook.ipynb`**: Demonstrates how to use the framework API in notebooks, including data loading, ETL configuration, training, and visualization.

### `src/`

Source code for custom components and execution scripts.

- **`data/`**:
  - **`custom_etl.py`**: Template for custom ETL implementations. Extend `BaseETL` to create your own data transformations.

- **`features/`**:
  - **`custom_selector.py`**: Template for custom feature selectors. Extend `BaseFeatureSelector` to implement custom feature selection logic.

- **`models/`**:
  - **`custom_model.py`**: Template for custom model implementations. Extend the base model classes to implement your own algorithms.

- **`inference/`**:
  - **`custom_inference.py`**: Template for custom inference logic. Extend `BaseInference` to implement custom prediction pipelines.

- **`utils/`**:
  - **`helpers.py`**: Shared utility functions that can be used across custom components.

- **`run/`**: Python scripts for direct execution without CLI:
  - **`00_etl.py`**: Executes ETLs from `etl.yaml`
  - **`01_eda.py`**: Runs exploratory data analysis from `eda.yaml`
  - **`02_training.py`**: Runs the training pipeline from `train.yaml`
  - **`03_inference.py`**: Runs inference on new data

### `docs/`

Project-specific documentation.

- **`project_docs.md`**: Placeholder for your project's documentation. Use this to document project-specific decisions, data sources, and modeling choices.

### `tests/`

Directory for unit and integration tests.

The directory is created but empty by default. Add your test files here to ensure your custom components work correctly.

## File Naming Conventions

- YAML files: lowercase with underscores (e.g., `etl.yaml`)
- Python files: lowercase with underscores (e.g., `custom_etl.py`)
- Data files: descriptive names with extensions (e.g., `sample_dataset.parquet`)
- Output directories: timestamped format `train-YYYYMMDD_HHMM`

## Sample Dataset

The template includes `data/raw/sample_dataset.parquet` with:

- **42,500 records** of electricity consumption data
- **12 monthly consumption columns**: `12_anterior` through `1_anterior`
- **Categorical features**:
  - `actividad`: Economic activity (~284 categories)
  - `tipo_tarifa`: Tariff type (~47 categories)
  - `zona`: Geographic zone (~38 categories)
  - `nivel_tension`: Voltage level (~18 categories)
  - `material_instalacion`: Meter material (~39 categories)
- **Binary target**: `target` column indicating fraud (1) vs non-fraud (0)

Use this dataset to experiment with the framework before using your own data.

---

← [First Project](../getting-started/first-project.md) | [CLI Reference](cli-reference.md) →
