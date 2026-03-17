# Architecture

This document describes the architecture of the Energizados framework, including package structure, module responsibilities, data flow, and key design decisions.

## Overview

Energizados is a machine learning framework for detecting electricity theft (non-technical losses in energy distribution). The project implements both simple rule-based models and complex supervised models (LightGBM, CatBoost, Neural Networks, LSTM).

The framework provides:
- **ETL system** with support for multiple ETLs with dependencies
- **Feature engineering pipeline** with preprocessing and feature selection
- **Model training** with ensemble support
- **Model evaluation** with metrics and reports
- **Inference** for production predictions
- **EDA module** for exploratory data analysis

## Package Structure

### Framework Source (`src/energizados/`)

```
src/energizados/
├── preprocessing/              # Data cleaning and feature engineering transformers
│   ├── preprocessing.py      # Core transformers (ToDummy, TeEncoder, etc.)
│   └── base.py             # BaseTransformer abstract class
│
├── modeling/                   # Model implementations
│   ├── supervised_models.py  # LGBMModel, CATModel, NNModel, LSTMNNModel
│   ├── adapters.py          # LGBMModelAdapter, CATModelAdapter, NNModelAdapter, LSTMNNModelAdapter
│   ├── ensemble.py          # EnsembleModel (soft voting and stacking)
│   └── simple_models.py     # Rule-based baseline models
│
├── feature_engineering/       # Combined preprocessing + feature selection
│   ├── base.py             # BaseFeatureEngineering abstract class
│   └── default.py          # DefaultFeatureEngineering implementation
│
├── feature_selection/         # Feature selection methods
│   ├── base.py             # BaseFeatureSelector abstract class
│   └── methods.py          # BorutaSelector, CorrelationSelector, ConstantSelector
│
├── evaluation/               # Model evaluation and reporting
│   ├── evaluator.py        # DefaultEvaluator: runs full evaluation
│   ├── metrics.py          # Metrics calculation (AUC, F1, etc.)
│   ├── plots.py            # PlotGenerator: ROC, precision-recall, etc.
│   ├── report.py           # ReportGenerator: HTML + JSON
│   └── index.py            # index.html: summary table of all runs
│
├── inference/                # Inference implementations
│   ├── base.py             # BaseInference abstract class
│   └── default.py          # DefaultInference implementation
│
├── core/                     # Core framework components
│   ├── base.py             # Base classes: Pipeline, Model, Inference
│   ├── pipeline.py         # Pipeline orchestrator (ConfigPipelineBuilder)
│   ├── steps/              # Pipeline step implementations
│   │   ├── split.py        # SplitStep: train/val/test splits
│   │   └── training.py     # TrainingStep: model training
│   ├── plots/              # Shared plot utilities
│   │   └── utils.py
│   └── utils/              # Internal utilities
│       ├── import_utils.py   # Dynamic import with allowlist
│       └── secure_pickle.py  # SHA-256 verified pickle save/load
│
├── cli/                      # Command-line interface
│   ├── main.py             # CLI commands
│   ├── init.py             # Project initialization
│   ├── run.py              # Pipeline execution
│   └── validate.py         # Configuration validation
│
├── eda/                      # Exploratory Data Analysis module
│   ├── base.py                  # BaseExplorer abstract class
│   ├── dataset_explorer.py      # Main orchestrator (DatasetExplorer)
│   ├── column_explorer.py       # Phase 2: Per-column analysis
│   ├── target_explorer.py       # Phase 3: Target variable analysis
│   ├── geo_analyzer.py         # Phase 4: Geospatial analysis (optional)
│   ├── feature_importance.py    # Phase 5: IV/KS/Cramér's V ranking
│   ├── segmentation_analyzer.py # Phase 6: Segment drift analysis
│   ├── related_columns_analyzer.py # Phase 7: Hierarchical column relationships
│   ├── plots.py                 # Static Matplotlib/Plotly charts
│   ├── plots_interactive.py     # Interactive Plotly charts (HTML strings)
│   ├── report.py                # HTML report generator
│   └── utils.py                 # IV, WoE, KS, Cramér's V utilities
│
└── etl/                       # ETL framework components
    ├── base.py             # BaseETL abstract class
    ├── pipeline.py         # SourceETL implementation
    └── orchestrator.py     # ETLOrchestrator for dependency management
```

### Generated Project Structure

Projects created with `energizados init` have the following structure:

```
mi_proyecto/
├── config/                       # Configuration files (3 YAMLs)
│   ├── etls.yaml
│   ├── training.yaml             # Includes split, feature_engineering, model, evaluation
│   └── inference.yaml
│
├── data/
│   ├── raw/                     # Input data (includes sample_dataset.parquet)
│   ├── processed/               # ETL outputs and feature engineering results
│   └── splits/                  # Train/val/test splits
│
├── docs/
│   └── project_docs.md
│
├── output/                        # Training run outputs (auto-created per run)
│   ├── index.html                 # Summary table of all training runs with metrics
│   └── train-YYYYMMDD_HHMM/      # One directory per training execution
│       ├── models/                # Feature engineering + model(s)
│       │   ├── feature_engineering.pkl
│       │   ├── model.pkl          # Single model (if len(models)==1)
│       │   ├── lgbm/             # Base model sub-dirs (if ensemble)
│       │   │   └── model.pkl
│       │   ├── cat/
│       │   │   └── model.pkl
│       │   └── ensemble.pkl      # Ensemble model (if len(models)>1)
│       ├── reports/
│       │   └── evaluation/        # HTML report, JSON report, plots
│       └── config/               # Copy of YAML config files used for this run
│
├── notebooks/
│   └── example_notebook.ipynb
│
├── src/
│   ├── data/                     # Custom ETL (custom_etl.py)
│   ├── features/                  # Custom feature selector (custom_selector.py)
│   ├── models/                    # Custom model (custom_model.py)
│   ├── inference/                 # Custom inference (custom_inference.py)
│   ├── utils/                     # Shared utilities (helpers.py)
│   └── run/                       # Execution scripts
│       ├── 01_etl.py
│       ├── 02_training.py
│       ├── 03_evaluation.py
│       └── 04_inference.py
│
└── tests/
```

## Module Responsibilities

### Core Components

| Module | Responsibility |
|---------|---------------|
| `core/pipeline.py` | Orchestrates the entire ML pipeline (ETL → Split → Training → Evaluation) |
| `core/base.py` | Provides base classes for Pipeline, Model, and Inference |
| `core/steps/` | Implements pipeline steps (splitting, training) |
| `core/utils/import_utils.py` | Dynamic class loading with security allowlist |
| `core/utils/secure_pickle.py` | Pickle serialization with SHA-256 verification |

### ETL Framework

| Module | Responsibility |
|---------|---------------|
| `etl/base.py` | `BaseETL` abstract class for custom ETL implementations |
| `etl/pipeline.py` | `SourceETL` - supports concat (vertical) and merge (horizontal) modes |
| `etl/orchestrator.py` | `ETLOrchestrator` - manages ETL execution order based on dependencies |

### Feature Engineering

| Module | Responsibility |
|---------|---------------|
| `feature_engineering/base.py` | `BaseFeatureEngineering` abstract class for custom pipelines |
| `feature_engineering/default.py` | Default implementation combining preprocessing + feature selection |
| `feature_selection/base.py` | `BaseFeatureSelector` abstract class for custom selectors |
| `feature_selection/methods.py` | Built-in selectors: Boruta, Correlation, Constant |
| `preprocessing/preprocessing.py` | Core transformers: ToDummy, TeEncoder, CardinalityReducer, etc. |

### Modeling

| Module | Responsibility |
|---------|---------------|
| `modeling/supervised_models.py` | LGBMModel, CATModel, NNModel, LSTMNNModel implementations |
| `modeling/adapters.py` | Model adapters for framework integration |
| `modeling/ensemble.py` | EnsembleModel: soft voting or stacking with meta-learner |
| `modeling/simple_models.py` | Rule-based baseline models |

### Evaluation

| Module | Responsibility |
|---------|---------------|
| `evaluation/evaluator.py` | `DefaultEvaluator` - runs full evaluation suite |
| `evaluation/metrics.py` | Metrics calculation: AUC, Precision, Recall, F1, etc. |
| `evaluation/plots.py` | `PlotGenerator` - ROC, precision-recall, cumulative gains |
| `evaluation/report.py` | `ReportGenerator` - HTML + JSON reports |
| `evaluation/index.py` | Generates index.html summary of all training runs |

### Inference

| Module | Responsibility |
|---------|---------------|
| `inference/base.py` | `BaseInference` abstract class for custom inference |
| `inference/default.py` | `DefaultInference` - standard inference implementation |

### EDA Module

| Module | Responsibility |
|---------|---------------|
| `eda/base.py` | `BaseExplorer` abstract class for EDA phases |
| `eda/dataset_explorer.py` | Main orchestrator running all EDA phases |
| `eda/column_explorer.py` | Phase 2: Per-column analysis |
| `eda/target_explorer.py` | Phase 3: Target variable analysis |
| `eda/geo_analyzer.py` | Phase 4: Geospatial analysis (optional) |
| `eda/feature_importance.py` | Phase 5: IV, KS, Cramér's V ranking |
| `eda/segmentation_analyzer.py` | Phase 6: Segment drift analysis |
| `eda/related_columns_analyzer.py` | Phase 7: Hierarchical column relationships |
| `eda/plots.py` | Static Matplotlib/Plotly charts |
| `eda/plots_interactive.py` | Interactive Plotly charts (HTML strings) |
| `eda/report.py` | HTML report generator |

### CLI

| Module | Responsibility |
|---------|---------------|
| `cli/main.py` | Main CLI entry point with subcommands |
| `cli/init.py` | `energizados init` - project initialization |
| `cli/run.py` | `energizados run` - pipeline execution |
| `cli/validate.py` | `energizados validate` - configuration validation |

## Data Flow

### Training Pipeline

```
Raw Data
    ↓
ETL (config/etls.yaml)
    ↓
Processed Data (data/processed/)
    ↓
Split (config/training.yaml → split section)
    ↓
Train/Val/Test Splits (data/splits/)
    ↓
Feature Engineering (config/training.yaml → feature_engineering)
    ├── Preprocessing (column-level transformers)
    ├── Global Transformers
    └── Feature Selection
    ↓
Feature Engineering Pipeline (saved as .pkl)
    ↓
Model Training (config/training.yaml → models)
    ├── Sampling (undersample/oversample/none)
    ├── Hyperparameter Search (optional)
    └── Model Fitting
    ↓
Trained Model (output/train-XXX/models/model.pkl)
    ↓
Evaluation (config/training.yaml → evaluation)
    ├── Metrics Calculation
    ├── Plot Generation
    └── Report Generation
    ↓
Evaluation Results (output/train-XXX/reports/evaluation/)
```

### Inference Pipeline

```
New Data
    ↓
Load Feature Engineering Pipeline
    ↓
Transform New Data
    ↓
Load Trained Model
    ↓
Make Predictions
    ↓
Apply Custom Inference (optional)
    ├── Thresholding
    └── Business Rules
    ↓
Save Predictions
```

### ETL Pipeline with Dependencies

```
ETL A (no dependencies)
    ↓
ETL B (depends_on: [A])
    ↓
ETL C (depends_on: [A, B])
    ↓
ETL D (depends_on: [C])
```

## Key Design Decisions

### 1. YAML-Based Configuration

All pipeline configuration is done through YAML files:
- `config/etls.yaml` - ETL definitions with dependencies
- `config/training.yaml` - Split, feature engineering, models, ensemble, evaluation
- `config/inference.yaml` - Inference configuration

**Rationale:** YAML is human-readable, easy to version control, and allows for complex nested structures without code changes.

### 2. Plugin System with `custom_class`

The framework uses a dynamic import system that loads custom classes referenced in YAML configuration. Classes must be in the security allowlist.

**Rationale:** Allows users to extend the framework without modifying core code, while maintaining security through the allowlist.

### 3. Separate ETL, Training, and Inference

ETL, training, and inference are separate steps that can be run independently.

**Rationale:** Allows for modular development, testing of individual components, and reuse of artifacts (feature engineering pipelines, trained models).

### 4. Feature Engineering Pipeline Saved as Artifact

The complete feature engineering pipeline (preprocessing + feature selection) is saved as a `.pkl` file after training.

**Rationale:** Ensures reproducibility and allows the exact same transformations to be applied during inference.

### 5. Ensemble Support

The framework supports ensembling multiple models via soft voting or stacking.

**Rationale:** Ensembles often outperform single models. Stacking allows a meta-learner to learn optimal combinations of base model predictions.

### 6. Security Allowlist for Dynamic Imports

Dynamic class imports are restricted to trusted module prefixes (`energizados.`, `src.`, etc.).

**Rationale:** Prevents arbitrary code execution from untrusted YAML configuration files.

### 7. SHA-256 Verified Pickle

Pickle files include a SHA-256 hash to verify integrity when loading.

**Rationale:** Prevents loading of corrupted or tampered model/pipeline files.

### 8. Time Series Split Support

The framework supports time-series aware splitting for chronological data.

**Rationale:** Electricity consumption data is temporal. Time series split prevents data leakage and provides more realistic performance estimates.

### 9. Sampling for Imbalanced Classes

Built-in support for undersampling and oversampling to handle class imbalance.

**Rationale:** Fraud detection typically has highly imbalanced classes (few fraud cases, many legitimate cases).

### 10. EDA as Separate Module

EDA is a standalone module that can be run independently of training.

**Rationale:** EDA is often done once at the start of a project. Separating it from training allows for faster iteration during the exploratory phase.

## Extension Points

The framework provides several base classes for extending functionality:

| Base Class | Location | Purpose |
|------------|----------|---------|
| `BaseETL` | `src/energizados/etl/base.py` | Create custom ETLs |
| `BaseFeatureEngineering` | `src/energizados/feature_engineering/base.py` | Custom feature engineering pipelines |
| `BaseFeatureSelector` | `src/energizados/feature_selection/base.py` | Custom feature selection methods |
| `BaseInference` | `src/energizados/inference/base.py` | Custom inference logic |
| `BaseExplorer` | `src/energizados/eda/base.py` | Custom EDA phases |

For detailed guides on extending the framework, see [Extending Framework](extending/).

## Data Format

The framework uses wide-format data with 12 monthly consumption columns plus categorical user features:

**Consumption Columns:**
- `12_anterior`, `11_anterior`, ..., `1_anterior` (12 monthly consumption values)

**Categorical Features:**
- `actividad`: Economic activity (high cardinality, ~284)
- `tipo_tarifa`: Tariff type (~47)
- `nivel_tension`: Voltage level (~18)
- `material_instalacion`: Meter material (~39)
- `zona`: Geographic zone (~38)

**Target:**
- Binary classification (fraudulent vs non-fraudulent users)

## Configuration Structure

### ETL Configuration (`etls.yaml`)

```yaml
etls:
  etl_name:
    enabled: true
    description: "Description of the ETL"
    input: "data/raw/source.csv"  # or ["@etl1", "file2.csv"] for merge
    output: "data/processed/output.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"  # or custom class
    params:
      mode: "concat"  # or "merge" for SourceETL
      merge_config:  # required when mode="merge"
        how: "left"
        on: "id_column"
    depends_on: ["etl1", "etl2"]  # optional dependencies
```

### Training Configuration (`training.yaml`)

```yaml
training:
  enabled: true
  input_path: "data/processed/data.parquet"
  target_column: "target"

  split:
    method: "time_series"  # or "stratified", "random"
    date_column: "fecha"
    train_period: ["2020-01-01", "2022-12-31"]
    val_period: ["2023-01-01", "2023-06-30"]
    test_period: ["2023-07-01"]

  feature_engineering:
    enabled: true
    preprocessing:
      columns:
        column_name:
          - transformation_name:
              param: value
      global_transformers:
        - custom_class: "path.to.CustomTransformer"
    feature_selection:
      enabled: true
      steps:
        - name: selector_name
          method: "boruta"  # or "correlation", "constant"
          params: {}

  models:
    - type: "lightgbm"  # or "catboost", "neural_network", "lstm"
      sampling:
        method: "undersample"  # or "oversample", "none"
        threshold: 0.5
      hyperparams:
        n_estimators: 1000
      hyperparam_search:
        enabled: true
        n_iter: 60
        cv: 3

  ensemble:  # optional, required when len(models) > 1
    method: "stacking"  # or "soft_voting"
    meta_learner:
      type: "logistic_regression"
      params: {}
    use_val_as_oof: true  # or false for proper CV OOF
    cv: 5

  evaluation:
    enabled: true
    threshold: 0.5
    metrics: [auc, precision, recall, f1, confusion_matrix]
    generate_plots: true
    generate_html_report: true
    generate_json_report: true
```

### Inference Configuration (`inference.yaml`)

```yaml
inference:
  enabled: true
  input_path: "data/processed/new_data.parquet"
  output_path: "output/predictions.csv"
  model_path: "output/train-XXX/models/model.pkl"
  feature_engineering_path: "output/train-XXX/models/feature_engineering.pkl"
  custom_class: "energizados.inference.default.DefaultInference"  # or custom
  params: {}
```

## See Also

- [Extending Framework](extending/) - Customizing the framework
- [User Guide](../user-guide/) - End-user documentation
- [Contributing](contributing.md) - Development guidelines

---

← [Advanced Topics](../advanced/) | [Extending Framework](extending/) →
