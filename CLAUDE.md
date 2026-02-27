# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Energizados is a machine learning framework for detecting electricity theft (non-technical losses in energy distribution). The project implements both simple rule-based models and complex supervised models (LightGBM, CatBoost, Neural Networks, LSTM).

The framework also includes an **ETL system** with support for multiple ETLs with dependencies using YAML configuration.

## Development Commands

### Environment Setup
```bash
pip install -r requirements.txt
jupyter lab
```

### Running the Project
The project is primarily run through Jupyter notebooks:
- `notebooks/ejecucion_paso_paso.ipynb` - Local execution
- `notebooks/colab_ejecucion_paso_paso.ipynb` - Google Colab execution

### Framework CLI
```bash
# Initialize a new project
energizados init mi_proyecto

# Run pipeline (specify multiple config files)
energizados run --config config/etls.yaml --config config/feature_pipeline.yaml --config config/training.yaml

# Validate configuration
energizados validate --config config/etls.yaml --config config/feature_pipeline.yaml

# Run specific step
energizados run --config config/feature_pipeline.yaml --step feature_pipeline

# Run specific ETL
energizados run --config config/etls.yaml --etl sample
```

## Code Architecture

### Directory Structure
```
src/
├── preprocessing/      # Data cleaning and feature engineering transformers
├── modeling/           # Model implementations (supervised and simple models)
├── feature_pipeline/   # Combined preprocessing + feature selection
│   ├── base.py        # BaseFeaturePipeline abstract class
│   └── default.py     # DefaultFeaturePipeline implementation
├── feature_selection/  # Feature selection methods
│   ├── base.py        # BaseFeatureSelector abstract class
│   └── methods.py     # BorutaSelector, CorrelationSelector, ConstantSelector
├── core/              # Core framework components
│   ├── base.py        # Base classes for pipeline, models, inference
│   └── pipeline.py    # Pipeline orchestrator
├── cli/               # Command-line interface
│   ├── main.py        # CLI commands
│   ├── init.py        # Project initialization
│   ├── run.py         # Pipeline execution
│   └── validate.py    # Configuration validation
└── etl/               # ETL framework components
    ├── base.py        # BaseETL abstract class
    ├── pipeline.py    # SourceETL, MultiSourceETL, MergeETL implementations
    └── orchestrator.py # ETLOrchestrator for dependency management
data/
├── raw/               # Original input data
└── processed/         # ETL outputs and feature pipeline results
models/
└── trained/           # Trained models
config/                # Configuration files (4 separate YAMLs)
├── etls.yaml
├── feature_pipeline.yaml
├── training.yaml
└── inference.yaml
```

### ETL Framework

The ETL system uses a **multiple ETLs with dependencies** approach. Configuration is done via YAML in `config/etls.yaml`.

New projects created with `energizados init` include a **sample ETL** that processes the included example dataset:

```yaml
# config/etls.yaml
etls:
  sample:
    enabled: true
    description: "Procesa dataset de ejemplo (elimina filas con NULL)"
    input: "data/raw/sample_dataset.parquet"
    output: "data/processed/sample_dataset.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"  # 'concat' (default) or 'merge'
    depends_on: []
```

**SourceETL Modes:**

`SourceETL` supports two processing modes via the `mode` parameter:

1. **`concat`** (default): Concatenates multiple input files vertically
   ```yaml
   concatenar:
     enabled: true
     input:
       - "data/2023.csv"
       - "data/2024.csv"
     output: "data/completo.parquet"
     custom_class: "energizados.etl.pipeline.SourceETL"
     params:
       mode: "concat"
   ```

2. **`merge`**: Merges multiple input files horizontally using `merge_config`
   ```yaml
   merge_dataset:
     enabled: true
     input:
       - "data/consumos.parquet"
       - "data/clientes.parquet"
     output: "data/merged.parquet"
     custom_class: "energizados.etl.pipeline.SourceETL"
     params:
       mode: "merge"
       merge_config:
         how: "left"       # 'left', 'right', 'inner', 'outer'
         on: "id_cliente"  # Column to merge on
   ```

**Important:** When `mode="merge"`, `merge_config` is required. The `merge_config` accepts any parameter from `pd.merge()`: `how`, `on`, `left_on`, `right_on`, `left_index`, `right_index`.

### Feature Pipeline

The **Feature Pipeline** unifies preprocessing and feature selection in a single step. Configuration is in `config/feature_pipeline.yaml`:

```yaml
# config/feature_pipeline.yaml
feature_pipeline:
  enabled: true
  input_path: "data/processed/sample_dataset.parquet"
  output_pkl: "data/processed/feature_pipeline.pkl"
  output_parquet: "data/processed/feature_pipeline.parquet"  # Optional

  preprocessing:
    # NUEVO: Configuración por columna
    columns:
      actividad:
        - cardinality_reducer:
            threshold: 0.001
        - to_dummy: {}

      tipo_tarifa:
        - cardinality_reducer:
            threshold: 0.001
        - target_encoding:
            w: 20

      zona:
        - ordinal_encoding: {}

      nivel_tension:
        - ordinal_encoding: {}

      material_instalacion:
        - target_encoding:
            w: 10

  feature_selection:
    enabled: true
    method: "boruta"  # boruta, correlation, constant
    params:
      n_estimators: 100
      max_iter: 100
```

**Available Preprocessing Transformations:**

| Transformation | Description | Parameters |
|----------------|-------------|------------|
| `cardinality_reducer` | Groups infrequent categories into "otros" | `threshold` (float, default=0.001) |
| `to_dummy` | One-hot encoding | None |
| `target_encoding` | Replaces category with target probability (requires y) | `w` (int, default=20) |
| `ordinal_encoding` | Ordinal encoding (0, 1, 2, ...) | sklearn OrdinalEncoder params |
| `minmax_scaler_row` | Row-wise MinMax scaling | `feature_range` (tuple, default=[0,1]) |
| `tsfel_vars` | Time series feature extraction using tsfel | `num_periodos` (int, default=12), `features_names_path` (str, default=None), `periods_suffix` (str, default="_anterior") |
| `extra_vars` | Statistical features for different time windows | `num_periodos` (int, default=3), `periods_suffix` (str, default="_anterior") |

**Global Transformers:**

Global transformers act on the entire dataset and generate new features. They are executed AFTER column-based preprocessing.

```yaml
preprocessing:
  columns:
    # ... column-based preprocessing

  global_transformers:
    # Extracción de features de series temporales con tsfel
    - tsfel_vars:
        num_periodos: 12
        features_names_path: null  # o path a JSON con configuración custom
        periods_suffix: "_anterior"

    # Variables estadísticas para diferentes ventanas de tiempo
    - extra_vars:
        num_periodos: 3
    - extra_vars:
        num_periodos: 6
    - extra_vars:
        num_periodos: 12

    # Custom class para transformers globales
    - custom_class: "preprocessing.CustomGlobalTransformer"
      params:
        custom_param: value
```

**Key Feature Pipeline Classes:**
- `BaseFeaturePipeline`: Abstract base class for custom implementations
- `DefaultFeaturePipeline`: Default implementation combining preprocessing + feature selection
- Methods: `fit(X, y)`, `transform(X)`, `fit_transform(X, y)`, `save(path)`, `load(path)`

Additional ETL examples are provided (commented out) in the template:
- `consumos`: Single source ETL for consumption data (mode='concat')
- `clientes`: Single source ETL for customer data (mode='concat')
- `concatenar_archivos`: Concatenates multiple CSV files (mode='concat')
- `merge_dataset`: Merges consumos and clientes by id_cliente (mode='merge')

**Reference Syntax**: Use `@etl_name` to reference another ETL's output:
```yaml
  merge_dataset:
    input:
      - "@consumos"  # References consumos ETL output
      - "data/raw/clientes.csv"
```

**Key ETL Classes:**
- `BaseETL`: Abstract base class for all ETL implementations
- `SourceETL`: Reads from one or multiple source files with `mode` parameter (`concat` or `merge`)
- `ETLOrchestrator`: Manages execution order based on dependencies
- `SchemaValidator`: Validates DataFrame schemas (required columns, categorical/numeric types)

**IMPORTANT:** Each ETL must specify `custom_class`. The `DefaultETL` class has been removed.

### Key Modules

**`src/preprocessing/preprocessing.py`** - Core preprocessing transformers:
- `ToDummy`: Converts categorical variables to dummy variables
- `TeEncoder`: Target encoding for categorical variables
- `CardinalityReducer`: Reduces cardinality of categorical features
- `TsfelVars`: Time series feature extraction using tsfel library
- `ExtraVars`: Creates statistical features from consumption time series (mean, slope, std, zeros count, etc.)

**`src/modeling/supervised_models.py`** - Supervised model classes:
- `LGBMModel`: LightGBM with imbalanced-learn sampling (under/over)
- `CATModel`: CatBoost with native categorical handling
- `NNModel`: Feedforward neural network (TensorFlow/Keras)
- `LSTMNNModel`: LSTM + Dense neural network for sequential consumption data

**`src/modeling/simple_models.py`** - Rule-based baseline models:
- `ChangeTrendPercentajeIdentifierWide`: Detects dramatic consumption drops
- `ConstantConsumptionClassifierWide`: Identifies constant consumption patterns

**`src/modeling/feature_selection.py`** - Feature selection methods:
- `feature_selection_by_correlation()`: Removes highly correlated features
- `feature_selection_by_constant()`: Removes low-variance features
- `feature_selection_by_boruta()`: Boruta algorithm for feature selection

### Data Format

The project uses wide-format data with 12 monthly consumption columns (`12_anterior` through `1_anterior`) plus categorical user features:

**Categorical features:**
- `actividad`: Economic activity (high cardinality, ~284)
- `tipo_tarifa`: Tariff type (~47)
- `nivel_tension`: Voltage level (~18)
- `material_instalacion`: Meter material (~39)
- `zona`: Geographic zone (~38)

**Target:**
- Binary classification (fraudulent vs non-fraudulent users)

### Model Training Pipeline

1. **Preprocessing** (`get_preprocesor()`): Custom pipelines for each categorical variable with different encoding strategies
2. **Sampling**: RandomUnderSampler or RandomOverSampler for imbalanced classes
3. **Model Training**: Early stopping with validation set (30 rounds, AUC metric)
4. **Hyperparameter Search**: RandomizedSearchCV with 60 iterations

### Important Implementation Notes

- Configuration is now split into 4 separate YAML files: `etls.yaml`, `feature_pipeline.yaml`, `training.yaml`, `inference.yaml`
- The CLI accepts multiple `--config` parameters which are merged ("last wins" for duplicates)
- `preprocessing` and `feature_selection` sections have been unified into `feature_pipeline`
- All categorical preprocessing is defined in `get_preprocesor(preprocesor_num)` in `supervised_models.py`
- Time series consumption data uses row-wise MinMax scaling (`MinMaxScalerRow`)
- Neural models concatenate processed features with scaled consumption series
- LSTM models reshape consumption data to (samples, 12, 1) for sequential processing
- Preprocessed datasets are saved in `data/processed/` as parquet files
- Feature pipelines are saved as `.pkl` files for reuse in training and inference
- **ETL configuration requires `custom_class` for each ETL** - use `SourceETL`, `MultiSourceETL`, `MergeETL`, or custom classes
- **New projects include `data/raw/sample_dataset.parquet`** for immediate testing
- The framework uses Python's `logging` module for all internal logging (configurable via logging handlers)
- CLI output uses `click.echo` for user-facing messages

### Language Context

The project documentation and comments are in Spanish. The codebase uses Spanish variable names for features (e.g., `actividad`, `tipo_tarifa`, `zona`) but English for class/method names.

### AGENTS.md compatibility

- Always use AGENTS.md for additional instructions before make changes. Use too when planning.
