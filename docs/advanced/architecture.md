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
│   ├── pipeline.py         # Pipeline orchestrator (ConfigPipelineBuilder - DEPRECATED)
│   ├── builders/           # Pipeline step builders (current architecture)
│   │   ├── base.py         # StepBuilder: abstract base class for builders
│   │   ├── director.py     # PipelineDirector: orchestrates pipeline construction
│   │   ├── run_manager.py  # RunManager: manages run directories and post-run tasks
│   │   ├── etl_builder.py  # ETLBuilder: constructs ETL steps
│   │   ├── split_builder.py # SplitBuilder: constructs split steps
│   │   ├── training_builder.py # TrainingBuilder: constructs training steps
│   │   ├── evaluation_builder.py # EvaluationBuilder: constructs evaluation steps
│   │   ├── inference_builder.py # InferenceBuilder: constructs inference steps
│   │   └── eda_builder.py   # EDABuilder: constructs EDA steps
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
├── explainability/             # Model interpretability (SHAP)
│   ├── __init__.py
│   └── shap_explainer.py      # ShapExplainer (TreeExplainer + KernelExplainer)
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
├── config/                       # Configuration files (4 YAMLs)
│   ├── etl.yaml
│   ├── train.yaml                # Includes split, feature_engineering, model, evaluation
│   ├── infer.yaml
│   └── eda.yaml
```

## Module Responsibilities

### Core Components

| Module | Responsibility |
|---------|---------------|
| `core/pipeline.py` | **DEPRECATED**: `ConfigPipelineBuilder` is a backwards compatibility wrapper. New code should use `PipelineDirector` from `core/builders/`. |
| `core/builders/director.py` | `PipelineDirector`: Orchestrates the entire ML pipeline (ETL → Split → Training → Evaluation) using specialized builders |
| `core/builders/base.py` | `StepBuilder`: Abstract base class for all pipeline step builders |
| `core/builders/run_manager.py` | `RunManager`: Manages run directory creation, config copying, and index.html generation |
| `core/builders/etl_builder.py` | `ETLBuilder`: Constructs ETL pipeline steps from configuration |
| `core/builders/split_builder.py` | `SplitBuilder`: Constructs data splitting pipeline steps |
| `core/builders/training_builder.py` | `TrainingBuilder`: Constructs training pipeline steps (feature engineering + model training) |
| `core/builders/evaluation_builder.py` | `EvaluationBuilder`: Constructs evaluation pipeline steps |
| `core/builders/inference_builder.py` | `InferenceBuilder`: Constructs inference pipeline steps |
| `core/builders/eda_builder.py` | `EDABuilder`: Constructs EDA (Exploratory Data Analysis) pipeline steps |
| `core/base.py` | Provides base classes for Pipeline, Model, and Inference |
| `core/steps/` | Implements pipeline steps (splitting, training) |
| `core/utils/import_utils.py` | Dynamic class loading with security allowlist |
| `core/utils/secure_pickle.py` | Pickle serialization with SHA-256 verification |

### Configuration Schema Module

| Module | Responsibility |
|---------|---------------|
| `core/schemas/schemas.py` | JSON Schema definitions for ETL, training, evaluation, and inference configurations |
| `core/schemas/config_validator.py` | `ConfigValidator` class for validating YAML configs against JSON schemas |

**Key Schemas:**

| Schema | Description |
|--------|-------------|
| `ETL_SCHEMA` | Validates ETL configuration (input/output, custom_class, dependencies) |
| `SPLIT_SCHEMA` | Validates data split configuration (method, train/val/test periods, groups) |
| `FEATURE_ENGINEERING_SCHEMA` | Validates preprocessing and feature selection steps |
| `MODEL_CONFIG_SCHEMA` | Validates model configuration (type, sampling, hyperparams, hyperparam_search) |
| `ENSEMBLE_SCHEMA` | Validates ensemble configuration (method, meta_learner, weights) |
| `EVALUATION_SCHEMA` | Validates evaluation configuration (metrics, calibration, shap, segment_columns) |
| `INFERENCE_SCHEMA` | Validates inference configuration (input/output, threshold) |

**Sampling Methods Validated:**
- `over` — increases minority class samples (RandomOverSampler)
- `undersample` — reduces majority class samples (RandomUnderSampler)
- `smotetomek` — combines SMOTE oversampling with Tomek links cleaning (SMOTETomek)
- `none` — disable class balancing

**SHAP Configuration Validated:**
- `enabled` — enable/disable SHAP value computation
- `max_samples` — maximum samples for SHAP computation (default: 500)
- `top_n_features` — number of top features to display (default: 20)
- `plot_types` — which plots to generate: `["summary", "bar"]`

### Pipeline Builders Module

The `core/builders/` module implements the **Builder pattern** for constructing pipeline steps from YAML configuration.

**Key Classes:**

| Class | Location | Purpose |
|-------|----------|---------|
| `PipelineDirector` | `director.py` | Orchestrates the construction of the complete pipeline from configuration, using specialized builders for each step type. Also manages configuration validation and run directory creation. |
| `StepBuilder` | `base.py` | Abstract base class that defines the interface for all pipeline step builders. Subclasses implement `build()` to construct specific pipeline steps. |
| `RunManager` | `run_manager.py` | Handles run directory management: creates timestamped run directories, copies config files to the run directory, and regenerates the global `index.html` summary. |
| `ETLBuilder` | `etl_builder.py` | Constructs ETL pipeline steps using `ETLOrchestrator` to execute ETLs with dependencies. |
| `SplitBuilder` | `split_builder.py` | Constructs data splitting steps (stratified, random, or time-series split) from configuration. |
| `TrainingBuilder` | `training_builder.py` | Constructs training steps that perform feature engineering and model training. Supports single models or ensembles. |
| `EvaluationBuilder` | `evaluation_builder.py` | Constructs evaluation steps using `DefaultEvaluator` to generate metrics, plots, and reports. |
| `InferenceBuilder` | `inference_builder.py` | Constructs inference steps for making predictions with trained models. |
| `EDABuilder` | `eda_builder.py` | Constructs EDA (Exploratory Data Analysis) steps using `DatasetExplorer`. |

**How It Works:**

1. `PipelineDirector` reads YAML configuration and validates it against JSON schemas
2. For each step type (ETL, Split, Training, Evaluation, Inference, EDA), the director delegates to a specialized builder
3. Each builder constructs a `PipelineStep` instance from the configuration
4. The director adds all steps to a `Pipeline` instance
5. When `director.run()` is called, the pipeline executes all steps in order

**Benefits:**

- **Separation of Concerns**: Each builder is responsible for one type of step
- **Extensibility**: Adding new step types requires only a new builder class
- **Testability**: Builders can be unit tested independently
- **Configuration Validation**: Schema validation happens before pipeline execution

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

### Explainability

| Module | Responsibility |
|---------|---------------|
| `explainability/shap_explainer.py` | `ShapExplainer`: SHAP-based model explainability with TreeExplainer and KernelExplainer support |

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
ETL (config/etl.yaml)
    ↓
Processed Data (data/processed/)
    ↓
Split (config/train.yaml → split section)
    ↓
Train/Val/Test Splits (data/splits/)
    ↓
Feature Engineering (config/train.yaml → feature_engineering)
    ├── Preprocessing (column-level transformers)
    ├── Global Transformers
    └── Feature Selection
    ↓
Feature Engineering Pipeline (saved as .pkl)
    ↓
Model Training (config/train.yaml → models)
    ├── Sampling (over/undersample/smotetomek/none)
    ├── Hyperparameter Search (optional)
    └── Model Fitting
    ↓
Trained Model (output/train-XXX/models/model.pkl)
    ↓
Evaluation (config/train.yaml → evaluation)
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
- `config/etl.yaml` - ETL definitions with dependencies
- `config/train.yaml` - Split, feature engineering, models, ensemble, evaluation
- `config/infer.yaml` - Inference configuration

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

### ETL Configuration (`etl.yaml`)

```yaml
etl:
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

### Training Configuration (`train.yaml`)

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
        method: "undersample"  # or "oversample", "smotetomek", "none"
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

### Inference Configuration (`infer.yaml`)

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
