# Quick Start

Get up and running with Energizados in 5 minutes.

## 0. Create a Working Folder

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

> 💡 **Tip:** Choose a name that reflects purpose (e.g., `energizados_projects`, `ml_projects`, `energy_theft`). Inside this folder, each `energizados init <name>` will create its own subdirectory with its own data, configs, and output results.

## 1. Create a New Project

The `energizados init` command creates a complete project structure with configuration files, execution scripts, and a sample dataset with 42,500 records:

```bash
energizados init fraud_detection
```

This generates following structure:

```
fraud_detection/
├── config/                 # YAML configuration files
│   ├── etl.yaml           # ETL configuration
│   ├── train.yaml         # Training pipeline configuration
│   ├── infer.yaml         # Inference configuration
│   └── eda.yaml           # Exploratory data analysis configuration
├── data/
│   ├── raw/               # Input data (includes sample_dataset.parquet)
│   ├── processed/         # ETL outputs and feature engineering results
│   └── splits/            # Train/val/test splits
├── output/                # Training run outputs (auto-created per run)
│   ├── index.html         # Summary table of all training runs
│   └── train-YYYYMMDD_HHMM/  # One directory per training execution
│       ├── models/        # Feature engineering + model(s)
│       ├── reports/evaluation/  # HTML report, JSON report, plots
│       └── config/        # Copy of YAML config files used for this run
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

## 2. Navigate to Project

```bash
cd fraud_detection
```

## 3. Edit Configuration Files

The main configuration files are in the `config/` directory:

- **`etl.yaml`**: Defines ETL processes (extract, transform, load) to prepare your data. The generated project includes a sample ETL that processes the included example dataset.

- **`train.yaml`**: Configures the entire training pipeline:
  - Data splitting (stratified, random, or time-based)
  - Feature engineering (preprocessing + feature selection)
  - Model configuration (single model or ensemble)
  - Evaluation settings (metrics, reports, threshold)

- **`infer.yaml`**: Defines how to apply trained model to new data.

- **`eda.yaml`**: Optional configuration for exploratory data analysis (EDA).

## 4. Run Pipeline Step by Step

**Run ETLs** (processes raw data):

```bash
energizados run etls
```

**Run training** (includes split, feature engineering, and model training):

```bash
energizados run training
```

**Run inference** (applies trained model to new data):

```bash
energizados run inference
```

**Run multiple configs at once**:

```bash
energizados run etls,training
```

## 5. View Results

Training results are saved in the `output/` directory:

- **`output/index.html`**: Summary table showing all training runs and their metrics.
- **`output/train-YYYYMMDD_HHMM/`**: Specific directory for each run containing:
  - Trained models
  - Evaluation reports (HTML and JSON)
  - Plots and visualizations
  - Copies of configuration files used

Open the HTML file in your browser to view detailed results.

---

← [Installation](installation.md) | [First Project](first-project.md) →
