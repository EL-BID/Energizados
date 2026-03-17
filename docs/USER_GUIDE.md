# Energizados User Guide

Energizados is a machine learning framework for detecting electricity theft (non-technical losses in energy distribution). The framework implements both simple rule-based models and complex supervised models (LightGBM, CatBoost, Neural Networks, LSTM) to help energy distribution companies identify fraudulent consumption patterns and reduce revenue losses.

The framework provides a complete pipeline for electricity theft detection, from data preparation through ETL processes to model training, evaluation, and inference. It supports multiple preprocessing transformations, feature selection methods, and ensemble techniques. The ETL system allows you to define multiple ETLs with dependencies, creating a Directed Acyclic Graph (DAG) that executes in the correct order automatically. This makes it easy to build complex data pipelines while maintaining flexibility and reproducibility.

Energizados is designed for data scientists who need a production-ready ML framework without the complexity of building everything from scratch. You can get started quickly with the CLI, explore your data with automated EDA reports, and deploy models through a simple inference API. The framework handles the engineering details so you can focus on the modeling.

## 1. Overview

Energizados is a machine learning framework specifically designed for detecting electricity theft (non-technical losses) in energy distribution systems. Electricity theft is a major problem for utilities worldwide, resulting in significant revenue losses. The framework addresses this by providing a complete end-to-end pipeline from data ingestion to model deployment.

The framework solves several key problems: managing complex ETL workflows with dependencies, handling imbalanced classification data (fraud is rare), supporting multiple model types with ensemble capabilities, and providing automated evaluation and reporting. Energizados includes pre-built transformers for consumption time series data, categorical features, and supports both classical ML models and deep learning approaches.

Key capabilities include: multi-ETL orchestration with dependency management (serial, parallel, and diamond patterns), feature engineering with column-specific and global transformers (including TSFEL for time series), multiple split strategies (stratified, random, time-based), ensemble models (stacking and soft voting), automated evaluation with customizable metrics, and comprehensive HTML reports with visualizations. The framework is production-ready with model serialization and a simple inference API.

## 2. Prerequisites

> ⚠️ **IMPORTANT:** Always use a virtual environment for Python projects. Never install packages in your global Python installation. Virtual environments isolate dependencies, prevent version conflicts, and make it easy to clean up.

### Python >= 3.10

Energizados requires Python 3.10 or higher. Verify your current version:

```bash
python --version
```

**If you need to install or update Python:**

**macOS:**

- With Homebrew:
  ```bash
  brew install python@3.11
  ```

- With pyenv:
  ```bash
  pyenv install 3.11.0
  pyenv global 3.11.0
  ```

**Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv
```

**Windows:**

- Download from [python.org](https://www.python.org/downloads/)
- Or from Microsoft Store: Search for "Python 3.11" or higher

### pip updated

Ensure you have the latest pip:

```bash
python -m pip install --upgrade pip
```

## 3. Installation

> ⚠️ **IMPORTANT: Always use a virtual environment.** Never install packages in your global Python installation. Virtual environments isolate dependencies, prevent version conflicts, and make it easy to clean up. This guide assumes you're using a virtual environment.

### Step 1: Create a Virtual Environment

Choose one of the following methods:

#### Option A: venv (built-in, recommended)

The simplest option — no additional tools required.

**macOS / Linux:**

```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows:**

```cmd
python -m venv .venv
.venv\Scripts\activate
```

#### Option B: pyenv + pyenv-virtualenv

Good for managing multiple Python versions.

**macOS:**

```bash
brew install pyenv pyenv-virtualenv

# Add to ~/.zshrc or ~/.bashrc:
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv-virtualenv-init -)"

# Create and activate
pyenv virtualenv 3.11 energizados
pyenv activate energizados
```

**Linux:**

```bash
curl https://pyenv.run | bash

# Add to ~/.bashrc:
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv-virtualenv-init -)"

# Create and activate
pyenv virtualenv 3.11 energizados
pyenv activate energizados
```

**Windows:** Use [pyenv-win](https://github.com/pyenv-win/pyenv-win):

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"
&"./install-pyenv-win.ps1"

pyenv install 3.11.9
pyenv virtualenv 3.11.9 energizados
pyenv activate energizados
```

#### Option C: Conda

If you already use Anaconda or Miniconda.

**macOS / Linux:**

```bash
conda create -n energizados python=3.11
conda activate energizados
```

**Windows:**

```cmd
conda create -n energizados python=3.11
conda activate energizados
```

> 💡 **Tip:** Whichever method you choose, make sure to add the environment folder (`.venv`, `envs/energizados`, etc.) to your `.gitignore` if it's inside your project folder.

### Step 2: Install Energizados

**Basic Installation** (includes LightGBM):

```bash
pip install energizados
```

**With Extras:**

- **CatBoost** (for CatBoost models):
  ```bash
  pip install energizados[catboost]
  ```

- **TensorFlow** (for neural networks and LSTM):
  ```bash
  pip install energizados[tensorflow]
  ```

- **All extras** (CatBoost + TensorFlow):
  ```bash
  pip install energizados[all]
  ```

### Step 3: Verify Installation

Once installed, verify the CLI is available:

```bash
energizados --version
energizados --help
```

If you see the help message, installation was successful.

## 4. Quick Start

### 0. Create a Working Folder

Create a dedicated folder that will contain **all your Energizados projects**. This keeps your work organized and separate from other projects:

**macOS / Linux:**

```bash
mkdir energizados_projects
cd energizados_projects
```

**Windows:**

```cmd
mkdir energizados_projects
cd energizados_projects
```

> 💡 **Tip:** Choose a name that reflects the purpose (e.g., `energizados_projects`, `ml_projects`, `energy_theft`). Inside this folder, each `energizados init <name>` will create its own subdirectory with its own data, configs, and output results.

### 1. Create a New Project

The `energizados init` command creates a complete project structure with configuration files, execution scripts, and a sample dataset with 42,500 records:

```bash
energizados init my_project
```

This generates the following structure:

```
my_project/
├── config/                 # YAML configuration files
│   ├── etls.yaml          # ETL configuration
│   ├── training.yaml      # Training pipeline configuration
│   ├── inference.yaml     # Inference configuration
│   └── eda.yaml           # Exploratory data analysis configuration
├── data/
│   ├── raw/               # Input data (includes sample_dataset.parquet)
│   ├── processed/         # ETL outputs and feature engineering results
│   └── splits/            # Train/val/test splits
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
│       ├── 01_etl.py
│       ├── 02_training.py
│       ├── 03_evaluation.py
│       └── 04_inference.py
├── docs/
│   └── project_docs.md
└── tests/
```

**Directory explanations:**

- `config/`: All pipeline configuration in YAML files
- `data/raw/`: Place your raw input data here (sample dataset included)
- `data/processed/`: ETL outputs and processed data
- `data/splits/`: Train/validation/test split files
- `output/`: Training results, models, and reports (auto-generated)
- `notebooks/`: Jupyter notebooks for interactive exploration
- `src/`: Custom components (ETLs, models, features, inference)
- `src/run/`: Python scripts for direct execution (alternative to CLI)

### 2. Navigate to the Project

```bash
cd my_project
```

### 3. Edit the Configuration Files

The main configuration files are in the `config/` directory:

- **`etls.yaml`**: Defines ETL processes (extract, transform, load) to prepare your data. The generated project includes a sample ETL that processes the included example dataset.

- **`training.yaml`**: Configures the entire training pipeline:
  - Data splitting (stratified, random, or time-based)
  - Feature engineering (preprocessing + feature selection)
  - Model configuration (single model or ensemble)
  - Evaluation settings (metrics, reports, threshold)

- **`inference.yaml`**: Defines how to apply the trained model to new data.

- **`eda.yaml`**: Optional configuration for exploratory data analysis (EDA).

### 4. Run the Pipeline Step by Step

**Run ETLs** (processes raw data):

```bash
energizados run --config config/etls.yaml
```

**Run training** (includes split, feature engineering, and model training):

```bash
energizados run --config config/training.yaml
```

**Run inference** (applies the trained model to new data):

```bash
energizados run --config config/inference.yaml
```

### 5. View Results

Training results are saved in the `output/` directory:

- **`output/index.html`**: Summary table showing all training runs and their metrics.
- **`output/train-YYYYMMDD_HHMM/`**: Specific directory for each run containing:
  - Trained models
  - Evaluation reports (HTML and JSON)
  - Plots and visualizations
  - Copies of the configuration files used

Open the HTML file in your browser to view detailed results.

## 5. CLI Reference

### `energizados init <name>`

Creates a new project from a template or copies an existing one.

**Options:**

- `--template, -t`: Template to use (default: `default`)
- `--path, -p`: Directory where to create the project (default: `.`)
- `--copy, -c`: Copy from an existing project (takes precedence over `--template`)
- `--force, -f`: Force creation, removing existing directory if necessary

**Examples:**

```bash
energizados init my_project                    # Create from template
energizados init new --copy existing           # Copy from existing project
energizados init my_project --force            # Replace if exists
```

### `energizados run --config <file> [options]`

Executes a pipeline from a YAML configuration file.

**Required options:**

- `--config, -c`: Path to YAML file (can be specified multiple times)

**Optional options:**

- `--step, -s`: Execute only a specific pipeline step (`etl`, `split`, `training`, `evaluation`, `inference`)
- `--etl, -e`: Execute a specific ETL (and its dependencies). Valid only with multiple ETLs.
- `--dry-run, -d`: Show execution plan without executing anything

**Examples:**

```bash
# Run full pipeline
energizados run --config config/etls.yaml --config config/training.yaml

# Run only one step
energizados run --config config/training.yaml --step split
energizados run --config config/training.yaml --step training

# Run a specific ETL
energizados run --config config/etls.yaml --etl sample

# Dry run (see plan without executing)
energizados run --config config/etls.yaml --dry-run
```

### `energizados validate --config <file>`

Validates YAML configuration files.

**Options:**

- `--config, -c`: Path to YAML file (can be specified multiple times)
- `--verbose, -v`: Show detailed validation information

**Example:**

```bash
energizados validate --config config/etls.yaml --config config/training.yaml --verbose
```

### `energizados eda [options]`

Runs exploratory data analysis (EDA) on a dataset.

**Options:**

- `--input, -i`: Path to input dataset (parquet or CSV). Overrides the config file.
- `--target, -t`: Name of binary target column.
- `--config, -c`: Path to `eda.yaml` configuration file.
- `--output, -o`: Output directory for report and plots.
- `--lat-col`: Latitude column name (enables geospatial analysis).
- `--lon-col`: Longitude column name (enables geospatial analysis).
- `--etl, -e`: Name of an ETL defined in `etls.yaml` whose output to analyze.
- `--skip-sections`: Comma-separated list of sections to skip (e.g., `geo,join,segmentation`).
- `--dry-run, -d`: Show configuration that would be used without executing analysis.

**Examples:**

```bash
# Basic analysis
energizados eda --input data/raw/dataset.parquet --target target

# Use configuration file
energizados eda --config config/eda.yaml

# Analyze output of an ETL
energizados eda --config config/eda.yaml --etl sample

# Enable geospatial analysis
energizados eda --config config/eda.yaml --lat-col LATITUDE --lon-col LONGITUDE

# Skip specific sections
energizados eda --config config/eda.yaml --skip-sections "geo,join"
```

### `energizados doctor [options]`

Checks system information and validates the environment.

**Options:**

- `--verbose, -v`: Show detailed system information
- `--optional, -o`: Include optional visualization packages (matplotlib, seaborn)

**Examples:**

```bash
energizados doctor
energizados doctor --verbose
energizados doctor --optional
```

### Global Options

- `--verbose, -v`: Increase verbosity (`-v` for INFO, `-vv` or `-vvv` for DEBUG)

## 6. Configuration Reference

### 6.1 etls.yaml

The ETL configuration file defines data extraction, transformation, and loading processes. Each ETL can depend on other ETLs, creating a DAG that executes in topological order.

#### SourceETL with `mode: concat`

Concatenates multiple input files vertically:

```yaml
etls:
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

#### SourceETL with `mode: merge`

Merges multiple input files horizontally using `merge_config`:

```yaml
etls:
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

The `merge_config` accepts any parameter from `pandas.merge()`: `how`, `on`, `left_on`, `right_on`, `left_index`, `right_index`.

#### ETL Dependencies with `@etl_name` References

Use the `@` prefix to reference another ETL's output:

```yaml
etls:
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

#### Dependency Patterns

**Serial Pattern:**

```yaml
etls:
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

**Parallel Pattern:**

```yaml
etls:
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

**Diamond Pattern (Convergence):**

```yaml
etls:
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

### 6.2 training.yaml

The training configuration has five main sections: `split`, `feature_engineering`, `models`, `ensemble` (optional), and `evaluation`.

#### Split Methods

**Stratified Split** (maintains class distribution):

```yaml
split:
  method: "stratified"
  test_size: 0.2
  val_size: 0.1
  random_state: 42
```

**Random Split** (simple random split):

```yaml
split:
  method: "random"
  test_size: 0.2
  val_size: 0.1
  random_state: 42
```

**Time Series Split** (split by date):

```yaml
split:
  method: "time_series"
  date_column: "fecha_inspeccion"
  train_period: ["2010-01-01", "2017-08-01"]
  val_period: ["2017-09-01", "2017-12-31"]
  test_period: ["2018-01-01"]
  save_splits: true
  splits_dir: "data/splits/"
```

#### Preprocessing Transformations

| Transformation        | Description                                     | Parameters                                                                               |
|-----------------------|-------------------------------------------------|------------------------------------------------------------------------------------------|
| `cardinality_reducer` | Groups infrequent categories into "otros"       | `threshold` (float, class default=0.1; YAML template default=0.001)                       |
| `to_dummy`            | One-hot encoding                                | None                                                                                     |
| `target_encoding`     | Replaces category with target probability       | `w` (int, default=20)                                                                   |
| `ordinal_encoding`    | Ordinal encoding (0, 1, 2, ...)                 | sklearn OrdinalEncoder params                                                             |
| `minmax_scaler_row`   | Row-wise MinMax scaling                         | `feature_range` (tuple, default=[0,1])                                                    |
| `cast_dtype`          | Converts column to a pandas dtype               | `dtype` (str, default=`"float32"`)                                                       |
| `tsfel_vars`          | Time series feature extraction using tsfel      | `num_periodos`, `features_names_path`, `periods_suffix`, `n_jobs`, `chunk_size`, `cache_dir` |
| `extra_vars`          | Statistical features for different time windows | `num_periodos` (int, default=3), `periods_suffix` (str, default="_anterior")             |

**Example preprocessing configuration:**

```yaml
feature_engineering:
  enabled: true
  output_pkl: "data/processed/feature_engineering.pkl"

  preprocessing:
    enabled: true
    drop_columns: ["index", "fecha_inspeccion"]
    # output_parquet: "data/processed/preprocessing.parquet"  # optional

    columns:
      # Multiple transformers on the same column
      actividad:
        - cardinality_reducer:
            threshold: 0.001
        - to_dummy: {}

      # Target encoding with smoothing
      tipo_tarifa:
        - target_encoding:
            w: 20

      # Ordinal encoding
      zona:
        - ordinal_encoding: {}

      nivel_tension:
        - ordinal_encoding: {}

      # Cast to specific dtype
      consumo_total:
        - cast_dtype:
            dtype: "float32"

    # Global transformers execute AFTER column-based preprocessing
    global_transformers:
      # Time series feature extraction with tsfel
      - tsfel_vars:
          num_periodos: 12
          features_names_path: null  # or path to JSON with custom config
          periods_suffix: "_anterior"
          n_jobs: -1        # -1 = all cores, 1 = sequential
          chunk_size: 500   # rows per chunk per worker
          cache_dir: null   # e.g.: ".cache/tsfel" to cache on disk

      # Statistical features for different time windows
      - extra_vars:
          num_periodos: 3
          periods_suffix: "_anterior"
      - extra_vars:
          num_periodos: 6
          periods_suffix: "_anterior"
      - extra_vars:
          num_periodos: 12
          periods_suffix: "_anterior"

      # Custom global transformer class
      - custom_class: "preprocessing.CustomGlobalTransformer"
        params:
          custom_param: value
```

#### Feature Selection

```yaml
feature_engineering:
  feature_selection:
    enabled: false
    # output_parquet: "data/processed/feature_selection.parquet"  # optional
    steps:
      - name: selector
        method: "boruta"  # boruta, correlation, constant
        params:
          n_estimators: 100
          max_iter: 100
```

#### Single Model Example

```yaml
training:
  enabled: true
  input_path: "data/processed/sample_dataset.parquet"
  target_column: "target"
  periods_suffix: &_anterior "_anterior"

  split:
    method: "stratified"
    test_size: 0.2
    val_size: 0.1
    random_state: 42

  feature_engineering:
    enabled: true

    preprocessing:
      enabled: true
      columns:
        actividad:
          - cardinality_reducer:
              threshold: 0.001
          - to_dummy: {}
        tipo_tarifa:
          - target_encoding:
              w: 20
        zona:
          - ordinal_encoding: {}

    feature_selection:
      enabled: false

  # Single model (list with one item)
  models:
    - type: "lightgbm"  # lightgbm, catboost, neural_network, lstm
      sampling:
        method: "undersample"  # oversample, undersample, none
        threshold: 0.5
      hyperparams:
        num_leaves: 31
        learning_rate: 0.05
        n_estimators: 1000
      hyperparam_search:
        enabled: true
        n_iter: 60
        cv: 3

  evaluation:
    enabled: true
    threshold: 0.5
    metrics: [auc, precision, recall, f1, confusion_matrix, cumulative_gains]
    generate_plots: true
    generate_html_report: true
    generate_json_report: true
```

#### Ensemble Example (Stacking + Soft Voting)

```yaml
training:
  enabled: true
  input_path: "data/processed/sample_dataset.parquet"
  target_column: "target"

  split:
    method: "stratified"
    test_size: 0.2
    val_size: 0.1
    random_state: 42

  feature_engineering:
    enabled: true
    preprocessing:
      enabled: true
      columns:
        actividad:
          - cardinality_reducer:
              threshold: 0.001
          - to_dummy: {}

    feature_selection:
      enabled: false

  # Multiple base models enable ensemble
  models:
    - name: "lgbm"
      type: "lightgbm"
      sampling: { method: "undersample", threshold: 0.5 }
      hyperparams: { num_leaves: 31, learning_rate: 0.05, n_estimators: 500 }
      hyperparam_search: { enabled: false }

    - name: "cat"
      type: "catboost"
      sampling: { method: "undersample", threshold: 0.5 }
      hyperparams: { iterations: 300 }
      hyperparam_search: { enabled: false }

  # Ensemble configuration (required when len(models) > 1)
  ensemble:
    method: "stacking"          # "stacking" | "soft_voting"
    meta_learner:
      type: "logistic_regression"
      params: { C: 1.0, max_iter: 1000 }
    use_val_as_oof: true        # true=blending (fast); false=proper CV OOF
    cv: 5                        # K-folds for OOF (only when use_val_as_oof=false)

  evaluation:
    enabled: true
    threshold: 0.5
    metrics: [auc, precision, recall, f1]
    generate_plots: true
    generate_html_report: true
```

**Ensemble methods:**

- **`stacking`**: Trains a meta-learner on base model predictions. More powerful but slower.
- **`soft_voting`**: Averages base model predictions. Simpler and faster.

#### Evaluation Configuration

```yaml
evaluation:
  enabled: true
  # threshold is ignored if calibration.enabled=true
  threshold: 0.5
  metrics: [auc, precision, recall, f1, confusion_matrix, cumulative_gains]
  generate_plots: true
  generate_html_report: true
  generate_json_report: true

  # Automatic threshold calibration (optional)
  calibration:
    enabled: false
    method: "cost_benefit"   # Options: cost_benefit | operational | precision_recall
    params:
      # For cost_benefit (minimizes total FP/FN cost):
      cost_fp: 1    # cost of inspecting a legitimate user
      cost_fn: 10   # cost of missing a fraud
      # For operational (fixes number of alerts):
      # capacity: 200   # maximum alerts per period
      # For precision_recall (guaranteed minimum recall):
      # min_recall: 0.80
```

### 6.3 inference.yaml

Basic inference configuration:

```yaml
inference:
  enabled: true
  input_path: "data/processed/new_data.parquet"
  output_path: "output/predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
```

## 7. Available Models

| Model           | Extra Required | Description                                    |
|-----------------|----------------|------------------------------------------------|
| `lightgbm`      | None (default) | LightGBM with imbalanced-learn sampling       |
| `catboost`      | `[catboost]`   | CatBoost with native categorical handling     |
| `neural_network`| `[tensorflow]` | Feedforward neural network (TensorFlow/Keras) |
| `lstm`          | `[tensorflow]` | LSTM + Dense for sequential consumption data  |
| `ensemble`      | Depends on base models | Stacking or soft voting ensemble of multiple models |

**Installation for extras:**

```bash
pip install energizados[catboost]      # For CatBoost
pip install energizados[tensorflow]    # For neural_network and lstm
pip install energizados[all]           # For all extras
```

## 8. Run Scripts (Alternative to CLI)

Projects generated with `energizados init` include Python scripts in `src/run/` for direct execution without using the CLI:

```bash
python src/run/01_etl.py          # ETLs
python src/run/02_training.py     # Training (includes feature engineering)
python src/run/03_evaluation.py   # Evaluation
python src/run/04_inference.py    # Inference
```

### When to Use Scripts vs CLI

**Use the CLI when:**

- You prefer simple commands from the terminal
- You want to execute specific steps or perform dry-runs
- You need quick configuration validation

**Use scripts when:**

- You want to integrate execution into custom workflows
- You need more control over the execution flow
- You prefer programmatic execution from Python

The scripts use the `ConfigPipelineBuilder` API directly and offer the same control as the CLI, but with the flexibility of Python code.

## 9. Using Jupyter Notebooks

Energizados integrates seamlessly with Jupyter Notebook for interactive analysis and experimentation.

### Install JupyterLab

```bash
pip install jupyterlab
```

### Launch JupyterLab

```bash
jupyter lab
```

This opens JupyterLab in your browser.

### Example Notebook

The `energizados init` command generates an example notebook at `notebooks/example_notebook.ipynb`. This notebook demonstrates:

- How to load and explore data
- Examples of ETL configuration
- How to run training step by step
- Visualization of results

### Notebook Execution

You can open and run the example notebook directly in JupyterLab, or create new notebooks for your analysis. The framework APIs are accessible from notebooks, allowing you to experiment with different configurations interactively.

## 10. Output Structure

Each training run creates a timestamped directory with the following structure:

```
output/
├── index.html                                    # Summary table of all runs with metrics
└── train-20260317_1430/                         # One directory per run (YYYYMMDD_HHMM)
    ├── models/                                 # Trained models and feature engineering
    │   ├── feature_engineering.pkl             # Feature engineering pipeline
    │   ├── model.pkl                           # Single model (if len(models)==1)
    │   ├── lgbm/                               # Base model sub-directories (if ensemble)
    │   │   └── model.pkl
    │   ├── cat/
    │   │   └── model.pkl
    │   └── ensemble.pkl                        # Ensemble model (if len(models)>1)
    ├── reports/                                # Evaluation reports and plots
    │   └── evaluation/
    │       ├── report.html                     # Comprehensive HTML evaluation report
    │       ├── report.json                     # Machine-readable JSON metrics
    │       └── plots/                          # Generated plots
    │           ├── confusion_matrix.png
    │           ├── roc_curve.png
    │           ├── precision_recall_curve.png
    │           ├── cumulative_gains.png
    │           └── feature_importance.png
    └── config/                                 # Copy of YAML configs used for this run
        ├── etls.yaml
        ├── training.yaml
        └── inference.yaml
```

### Output Differences: Single Model vs Ensemble

**Single Model (len(models) == 1):**

```
models/
├── feature_engineering.pkl
└── model.pkl
```

**Ensemble (len(models) > 1):**

```
models/
├── feature_engineering.pkl
├── lgbm/
│   └── model.pkl
├── cat/
│   └── model.pkl
└── ensemble.pkl
```

Each base model is saved in its own subdirectory named after the model, and the ensemble model is saved at the root level.

## 11. Threshold Calibration

### What It Is

Threshold calibration is the process of selecting the optimal decision threshold for converting model probabilities into binary predictions (fraud vs non-fraud). The default threshold is 0.5, but this is rarely optimal for imbalanced problems like electricity theft detection.

### Why It Matters

Choosing the right threshold balances two types of errors:

- **False Positives (FP)**: Incorrectly flagging a legitimate user as fraudulent (costs inspection resources)
- **False Negatives (FN)**: Missing a fraudulent user (costs revenue from theft)

The optimal threshold depends on your business constraints, costs, and operational capacity.

### How to Configure in training.yaml

Enable automatic threshold calibration:

```yaml
evaluation:
  enabled: true
  # threshold is ignored if calibration.enabled=true
  threshold: 0.5
  metrics: [auc, precision, recall, f1]

  calibration:
    enabled: true
    method: "cost_benefit"   # Options: cost_benefit | operational | precision_recall
    params:
      # For cost_benefit (minimizes total cost):
      cost_fp: 1     # Cost of inspecting a legitimate user (relative units)
      cost_fn: 10    # Cost of missing a fraud (relative units)
```

**Calibration methods:**

1. **`cost_benefit`**: Minimizes total cost = (FP × cost_fp) + (FN × cost_fn). Provide `cost_fp` and `cost_fn` parameters.

2. **`operational`**: Ensures the number of alerts matches inspection capacity. Provide `capacity` parameter:
   ```yaml
   calibration:
     enabled: true
     method: "operational"
     params:
       capacity: 200   # Maximum alerts per period (e.g., per month)
   ```

3. **`precision_recall`**: Guarantees a minimum recall rate. Provide `min_recall` parameter:
   ```yaml
   calibration:
     enabled: true
     method: "precision_recall"
     params:
       min_recall: 0.80   # Ensure at least 80% of fraud is caught
   ```

When `calibration.enabled: true`, the framework automatically finds the optimal threshold using the validation set and reports it in the evaluation results.

## 12. Troubleshooting

### `energizados` not found in PATH

**Symptom:**
```
bash: energizados: command not found
```

**Solutions by operating system:**

**macOS / Linux:**

1. Verify the virtual environment is activated:
   ```bash
   which energizados  # Should show path inside venv
   ```

2. If not in PATH, verify installation:
   ```bash
   pip show energizados  # Should show package location
   ```

3. Reinstall if necessary:
   ```bash
   pip uninstall energizados
   pip install energizados
   ```

**Windows:**

1. Verify the virtual environment is activated:
   ```cmd
   where energizados  # Should show path inside venv
   ```

2. If not in PATH, verify installation:
   ```cmd
   pip show energizados
   ```

3. Reinstall if necessary:
   ```cmd
   pip uninstall energizados
   pip install energizados
   ```

4. If persistent, ensure the `Scripts` folder of your venv is in the Windows PATH.

### Python Version Conflicts

**Symptom:** Installation error indicating package requires Python >= 3.10

**Solutions:**

1. Check your Python version:
   ```bash
   python --version
   ```

2. If you have multiple Python versions, use the correct one explicitly:
   - **macOS / Linux**: `python3.11 --version`, `python3.11 -m pip install energizados`
   - **Windows**: `py -3.11 --version`, `py -3.11 -m pip install energizados`

3. Consider using a Python version manager:
   - **pyenv** (macOS/Linux): `pyenv install 3.11.0 && pyenv global 3.11.0`
   - **pyenv-win** (Windows): Install from [pyenv-win](https://github.com/pyenv-win/pyenv-win)

### CatBoost Installation Errors

**Symptom:** Error installing `energizados[catboost]`

**Solutions by operating system:**

**macOS:**

- CatBoost may require compilation. Ensure you have development tools:
  ```bash
  xcode-select --install
  ```

**Linux:**

- Install compilation dependencies if needed:
  ```bash
  # Ubuntu/Debian
  sudo apt install build-essential

  # Fedora
  sudo dnf install gcc-c++ make
  ```

**Windows:**

- CatBoost has precompiled binaries for Windows. If errors occur:
  - Ensure Visual C++ Redistributable is installed
  - Try installing catboost directly:
    ```cmd
    pip install catboost==1.2.8
    ```

### TensorFlow Installation Errors

**Symptom:** Error installing `energizados[tensorflow]`

**Solutions by operating system:**

**macOS (M1/M2/M3 Apple Silicon):**

- TensorFlow for macOS ARM requires a specific version:
  ```bash
  pip install tensorflow-macos
  ```

**Linux:**

- TensorFlow requires CUDA for GPU support. For CPU only:
  ```bash
  pip install tensorflow-cpu>=2.10.0
  ```

**Windows:**

- TensorFlow has limited Windows support. Use CPU version:
  ```cmd
  pip install tensorflow-cpu>=2.10.0
  ```

### General Troubleshooting Tips

1. **Check the environment:**
   ```bash
   energizados doctor
   ```

2. **Validate configuration:**
   ```bash
   energizados validate --config config/etls.yaml --config config/training.yaml --verbose
   ```

3. **Increase verbosity:**
   Add `-v`, `-vv`, or `-vvv` to commands to see more debug information:
   ```bash
   energizados run --config config/training.yaml -vv
   ```

4. **Dry run:** Check the execution plan without running:
   ```bash
   energizados run --config config/etls.yaml --dry-run
   ```

5. **Common issues to check:**
   - Virtual environment is activated
   - Configuration files are in correct paths
   - Input data files exist and are readable
   - Python version meets requirements (>= 3.10)
   - Sufficient disk space for outputs
   - Required optional packages are installed for the models you're using

---

**Need more help?**

- Check the documentation: https://energizados.readthedocs.io
- Report issues: https://github.com/energizados/energizados/issues
