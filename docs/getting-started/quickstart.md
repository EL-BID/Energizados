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

> 💡 **Tip:** Choose a name that reflects the purpose (e.g., `energizados_projects`, `ml_projects`, `energy_theft`). Inside this folder, each `energizados init <name>` will create its own subdirectory with its own data, configs, and output results.

## 1. Create a New Project

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

## 2. Navigate to the Project

```bash
cd my_project
```

## 3. Edit the Configuration Files

The main configuration files are in the `config/` directory:

- **`etls.yaml`**: Defines ETL processes (extract, transform, load) to prepare your data. The generated project includes a sample ETL that processes the included example dataset.

- **`training.yaml`**: Configures the entire training pipeline:
  - Data splitting (stratified, random, or time-based)
  - Feature engineering (preprocessing + feature selection)
  - Model configuration (single model or ensemble)
  - Evaluation settings (metrics, reports, threshold)

- **`inference.yaml`**: Defines how to apply the trained model to new data.

- **`eda.yaml`**: Optional configuration for exploratory data analysis (EDA).

## 4. Run the Pipeline Step by Step

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

## 5. View Results

Training results are saved in the `output/` directory:

- **`output/index.html`**: Summary table showing all training runs and their metrics.
- **`output/train-YYYYMMDD_HHMM/`**: Specific directory for each run containing:
  - Trained models
  - Evaluation reports (HTML and JSON)
  - Plots and visualizations
  - Copies of the configuration files used

Open the HTML file in your browser to view detailed results.

---

← [Installation](installation.md) | [First Project](first-project.md) →
