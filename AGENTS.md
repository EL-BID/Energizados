# AGENTS.md / CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent Rules (Always Apply)

- Never load in context the following directories and their files:
  - `node_modules/`
  - `htmlcov/`
  - `.proyects/`
  - `.plans/`
  - `notebooks/`
- Update CLAUDE.md and all documentation if necessary.
- Check and fix tests.
- Check pre-commit rules and ensure controls pass.
- Do NOT use `print` for logging. Use the Python `logging` module instead.
- **Code search rules — `Grep` tool vs `colgrep`:**
  - Use the **`Grep` tool** (ripgrep) when you know **exactly** what to look for:
    - Exact function/class/variable name: `Grep pattern="class EnsembleModel"`
    - Exact string or import: `Grep pattern="from energizados.modeling"`
    - Regex over a known pattern: `Grep pattern="def fit\(self"`
    - Counting occurrences or listing files: use `output_mode="count"` or `"files_with_matches"`
    - Searching within 2–3 specific files you already have open
  - Use **`colgrep`** (semantic grep) when you know **what the code does** but not its exact name:
    - Concept-based search: `colgrep "error handling logic"` or `colgrep "resampling for class imbalance"`
    - Discovering where a behavior lives without knowing the symbol name
    - Hybrid mode when you have both a concept and a known token: `colgrep "feature importance ranking" -e "def "`
    - Exploring unfamiliar areas of the codebase before diving in
  - **Decision rule**: If you can write the exact text you expect to find → `Grep`. If you need to describe the intent in plain English → `colgrep`.
  - **Never** call `grep`, `rg`, or `find` as Bash commands — use the `Grep` tool or `colgrep` instead.

- **ALWAYS search Engram memory FIRST before starting work:**
  - At the start of each session or when the user mentions a feature, bug, or past work:
    1. Call `mem_context` to check recent session history
    2. If not found, call `mem_search` with relevant keywords
    3. If you find a match, use `mem_get_observation` for full content
  - **Why**: Avoid repeating work, discover past decisions/bugs, understand context
  - **When to search**: 
    - User's FIRST message references the project or a feature
    - Starting work on something that might have been done before
    - User asks to "remember", "recall", "recordar", "acordate"
    - Any mention of "qué hicimos" or "what did we do"
  - **Project name**: Use "Energizados" (with capital E) for `project` parameter in mem searches

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

# Run pipeline (specify multiple config names)
energizados run etl,train

# Validate configuration
energizados validate etl,train

# Run specific step
energizados run etl --step etl
energizados run train --step split
energizados run train --step training

# Run specific ETL
energizados run etl --etl sample

# Run EDA
energizados run eda

# Dry run (see plan without executing)
energizados run etl --dry-run

# Run with custom name (replaces if exists)
energizados run train -n mi-experimento
```

### Run Scripts (generated projects)
New projects include Python scripts in `src/run/` for direct execution without CLI:
```bash
python src/run/00_etl.py          # ETLs
python src/run/01_eda.py           # EDA (Exploratory Data Analysis)
python src/run/02_training.py      # Entrenamiento (incluye feature engineering y evaluación)
python src/run/03_inference.py     # Inferencia
```
These scripts use `ConfigPipelineBuilder` API directly.

## Code Architecture

### Directory Structure

**Framework source (`src/energizados/`):**
```
src/energizados/
├── preprocessing/      # Data cleaning and feature engineering transformers
├── modeling/           # Model implementations (supervised and simple models)
│   ├── adapters.py    # LGBMModelAdapter, CATModelAdapter, NNModelAdapter, LSTMNNModelAdapter
│   └── ensemble.py    # EnsembleModel (soft voting and stacking)
├── feature_engineering/  # Combined preprocessing + feature selection
│   ├── base.py        # BaseFeatureEngineering abstract class
│   └── default.py     # DefaultFeatureEngineering implementation
├── feature_selection/  # Feature selection methods
│   ├── base.py        # BaseFeatureSelector abstract class
│   └── methods.py     # BorutaSelector, CorrelationSelector, ConstantSelector
├── evaluation/        # Model evaluation and reporting
│   ├── evaluator.py   # DefaultEvaluator
│   ├── metrics.py     # Metrics calculation
│   ├── plots.py       # PlotGenerator
│   ├── report.py      # ReportGenerator
│   └── index.py       # Run index (output/index.html)
├── inference/         # Inference implementations
│   ├── base.py        # BaseInference abstract class
│   └── default.py     # DefaultInference implementation
├── core/              # Core framework components
│   ├── base.py        # Base classes for pipeline, models, inference
│   ├── pipeline.py    # Pipeline orchestrator (ConfigPipelineBuilder)
│   ├── steps/         # Pipeline step implementations
│   │   ├── split.py   # SplitStep
│   │   └── training.py # TrainingStep
│   ├── plots/         # Shared plot utilities
│   │   └── utils.py
│   └── utils/         # Internal utilities
│       ├── import_utils.py   # Dynamic class import with allowlist
│       └── secure_pickle.py  # SHA-256 verified pickle save/load
├── cli/               # Command-line interface
│   ├── main.py        # CLI commands
│   ├── init.py        # Project initialization
│   ├── run.py         # Pipeline execution
│   └── validate.py    # Configuration validation
├── eda/               # Exploratory Data Analysis module
│   ├── base.py        # BaseExplorer abstract class
│   ├── dataset_explorer.py   # Main orchestrator (DatasetExplorer)
│   ├── column_explorer.py    # Phase 2: Per-column analysis
│   ├── target_explorer.py    # Phase 3: Target variable analysis
│   ├── geo_analyzer.py       # Phase 4: Geospatial analysis (optional)
│   ├── feature_importance.py # Phase 5: IV/KS/Cramér's V ranking
│   ├── segmentation_analyzer.py # Phase 6: Segment drift analysis
│   ├── related_columns_analyzer.py # Phase 7: Hierarchical column relationships
│   ├── plots.py              # Static Matplotlib/Plotly charts
│   ├── plots_interactive.py  # Interactive Plotly charts (HTML strings)
│   ├── report.py             # HTML report generator
│   └── utils.py              # Column classification, IV/WoE, KS, Cramér's V
└── etl/               # ETL framework components
    ├── base.py        # BaseETL abstract class
    ├── pipeline.py    # SourceETL implementation
    └── orchestrator.py # ETLOrchestrator for dependency management
```

**Generated project structure (`energizados init`):**
```
mi_proyecto/
├── config/                 # Configuration files (3 YAMLs)
│   ├── etl.yaml
│   ├── train.yaml         # Includes split, feature_engineering, model, evaluation
│   └── infer.yaml
├── data/
│   ├── raw/               # Input data (includes sample_dataset.parquet)
│   ├── processed/         # ETL outputs and feature engineering results
│   └── splits/            # Train/val/test splits
├── docs/
│   └── project_docs.md
├── output/                # Training run outputs (auto-created per run)
│   ├── index.html         # Summary table of all training runs with metrics
│   └── train-YYYYMMDD_HHMM/  # One directory per training execution
│       ├── models/        # Feature engineering + model(s)
│       │   ├── feature_engineering.pkl
│       │   ├── model.pkl  # Single model (if len(models)==1)
│       │   ├── lgbm/      # Base model sub-dirs (if ensemble)
│       │   │   └── model.pkl
│       │   ├── cat/
│       │   │   └── model.pkl
│       │   └── ensemble.pkl # Ensemble model (if len(models)>1)
│       ├── reports/
│       │   └── evaluation/  # HTML report, JSON report, plots
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
│       ├── 00_etl.py          # ETLs
│       ├── 01_eda.py           # EDA (Exploratory Data Analysis)
│       ├── 02_training.py      # Entrenamiento (incluye feature engineering y evaluación)
│       └── 03_inference.py     # Inferencia
└── tests/
```

### ETL Framework

The ETL system uses a **multiple ETLs with dependencies** approach. Configuration is done via YAML in `config/etl.yaml`.

New projects created with `energizados init` include a **sample ETL** that processes the included example dataset:

```yaml
# config/etl.yaml
etl:
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

### Feature Engineering and Model Training

Feature engineering (preprocessing + feature selection) is now configured inside `config/train.yaml` under the `feature_engineering` key. There is no longer a separate `feature_pipeline.yaml`.

The full `train.yaml` has five sections: `split`, `feature_engineering`, `models` (list), `ensemble` (optional), and `evaluation`.

```yaml
# config/train.yaml
training:
  enabled: true
  input_path: "data/processed/sample_dataset.parquet"
  target_column: "target"
  periods_suffix: &period_suffix "_anterior"
  # output_base_dir: "output"  # override opcional; cada run genera output/train-YYYYMMDD_HHMM/

  split:
    method: "time_series"  # Opciones: stratified, random, time_series
    # Para time_series:
    date_column: "fecha_inspeccion"
    train_period: ["2010-01-01", "2017-08-01"]
    val_period: ["2017-09-01", "2017-12-31"]
    test_period: ["2018-01-01"]
    save_splits: true
    splits_dir: "data/splits/"
    # Para stratified/random:
    # test_size: 0.2
    # val_size: 0.1
    # random_state: 42

  feature_engineering:
    enabled: true
    output_pkl: "data/processed/feature_engineering.pkl"

    preprocessing:
      enabled: true
      # output_parquet: "data/processed/preprocessing.parquet"  # opcional (incluye target para inspección)
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
      enabled: false
      # output_parquet: "data/processed/feature_selection.parquet"  # opcional (incluye target para inspección)
      steps:
        - name: selector
          method: "boruta"  # boruta, correlation, constant
          params:
            n_estimators: 100
            max_iter: 100

  # Single model example
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

  # For stacking ensemble (uncomment to use multiple base models)
  # models:
  #   - name: "lgbm"
  #     type: "lightgbm"
  #     sampling: { method: "undersample", threshold: 0.5 }
  #     hyperparams: { num_leaves: 31, learning_rate: 0.05, n_estimators: 500 }
  #     hyperparam_search: { enabled: false }
  #   - name: "cat"
  #     type: "catboost"
  #     sampling: { method: "undersample", threshold: 0.5 }
  #     hyperparams: { iterations: 300 }
  #     hyperparam_search: { enabled: false }
  #
  # ensemble:
  #   method: "stacking"          # "stacking" | "soft_voting"
  #   meta_learner:
  #     type: "logistic_regression"
  #     params: { C: 1.0, max_iter: 1000 }
  #   use_val_as_oof: true        # true=blending (fast); false=proper CV OOF
  #   cv: 5

  evaluation:
    enabled: true
    # output_dir se gestiona automáticamente dentro del run directory
    threshold: 0.5
    metrics: [auc, precision, recall, f1, confusion_matrix, cumulative_gains]
    generate_plots: true
    generate_html_report: true
    generate_json_report: true
```

**Available Preprocessing Transformations:**

| Transformation | Description | Parameters |
|----------------|-------------|------------|
| `cardinality_reducer` | Groups infrequent categories into "otros" | `threshold` (float, class default=0.1; YAML template default=0.001) |
| `to_dummy` | One-hot encoding | None |
| `target_encoding` | Replaces category with target probability (requires y) | `w` (int, default=20) |
| `ordinal_encoding` | Ordinal encoding (0, 1, 2, ...) | sklearn OrdinalEncoder params |
| `minmax_scaler_row` | Row-wise MinMax scaling | `feature_range` (tuple, default=[0,1]) |
| `cast_dtype` | Converts column to a pandas dtype | `dtype` (str, default=`"float32"`) |
| `tsfel_vars` | Time series feature extraction using tsfel | `num_periodos` (int, default=12), `features_names_path` (str, default=None), `periods_suffix` (str, default="_anterior"), `n_jobs` (int, default=1), `chunk_size` (int, default=500), `cache_dir` (str, default=None) |
| `extra_vars` | Statistical features for different time windows | `num_periodos` (int, default=3), `periods_suffix` (str, default="_anterior") |
| `consumption_patterns` | Domain-specific fraud detection features (abrupt drops, zero ratio, drastic changes, consistency) | `num_periodos` (int, default=12), `periods_suffix` (str, default="_anterior") |
| `geo_features` | Geographic features from lat/lon: estado, município, região, distances to capitals/cities, target encoding | `lat_col` (str), `lon_col` (str), `include_hierarchy` (bool), `include_target_encoding` (bool), `te_w` (int), `include_distances` (bool), `distance_cities` (list), `include_coords` (bool) |

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

    # Patrones de consumo específicos para detección de fraude
    # Genera features como: diff ratios, min_max_ratio, zscore, zero_ratio,
    # slope_normalized, consistency_score, drastic_changes_count
    - consumption_patterns:
        num_periodos: 12
        periods_suffix: "_anterior"

    # Features geográficas a partir de lat/long (usa shapefiles IBGE)
    # Genera: geo_estado, geo_municipio, geo_regiao + target encoding + distancias
    - geo_features:
        lat_col: "latitud"
        lon_col: "longitud"
        include_hierarchy: true
        include_target_encoding: true
        te_w: 20
        include_distances: true
        distance_cities:
          - sao_paulo
          - rio_de_janeiro
          - brasilia
        include_coords: false

    # Custom class para transformers globales
    - custom_class: "preprocessing.CustomGlobalTransformer"
      params:
        custom_param: value
```

**Custom class options in `feature_engineering`:**
- Per-column: `custom_class` inside a column's transformer list
- Full preprocessing replacement: `preprocessing.custom_class`
- Full feature engineering replacement: `feature_engineering.custom_class`
- Custom model: `model.custom_class`

**Key Feature Engineering Classes (internal framework):**
- `BaseFeatureEngineering`: Abstract base class for custom implementations (`feature_engineering/base.py`)
- `DefaultFeatureEngineering`: Default implementation combining preprocessing + feature selection (`feature_engineering/default.py`)
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
- `SourceETL`: Reads from one or multiple source files with `mode` parameter (`concat` or `merge`). This single class handles both concatenation and merge; there are no separate `MultiSourceETL` or `MergeETL` classes.
- `ETLOrchestrator`: Manages execution order based on dependencies
- `SchemaValidator`: Defined in `etl/validators.py` but not integrated into the pipeline. Available for manual use in custom ETLs.

**IMPORTANT:** Each ETL must specify `custom_class`. The `DefaultETL` class has been removed.

### EDA Module

The EDA module generates an interactive HTML report from raw datasets. Configured via `config/eda.yaml`.

**Phases:**
- Phase 0: Loading validation (BOM, encoding, numeric-as-string)
- Phase 1: Global stats (nulls, duplicates, constants)
- Phase 2: Column analysis (numeric/categorical/temporal/consumption) with optional per-column detail charts
- Phase 3: Target variable (class balance, temporal rate)
- Phase 4: Geospatial (optional)
- Phase 5: Feature importance (IV, KS, Cramér's V)
- Phase 6: Segmentation (optional)
- Phase 7: Related columns (optional, configurable hierarchies)

**Per-column detail charts** (Phase 2): When `detailed_charts: true` is set undersample `sections.numeric` or `sections.categorical`, collapsible `<details>` blocks are generated per column with histograms, boxplots, treemaps, and target rate charts.

**Related columns** (Phase 7): Generic `RelatedColumnsAnalyzer` for configurable column hierarchies. Produces tree breakdowns, cross-tabulations, sunburst/sankey charts, and target rate heatmaps.

```yaml
# config/eda.yaml - related_columns section
sections:
  related_columns:
    enabled: true
    hierarchies:
      - name: "Proceso de inspección"
        columns: ["TIPO_SERVICO", "ACAO", "CATEGORIA_NOTA"]
      - name: "Ubicación × Tarifa"
        columns: ["ZONA", "TIPO_TARIFA"]
```

**Key EDA Classes:**
- `DatasetExplorer`: Main orchestrator that runs all phases and generates the HTML report
- `RelatedColumnsAnalyzer`: Generic analyzer for hierarchical column relationships (replaces the removed `InspectionAnalyzer`)
- `EDAInteractivePlots`: Generates interactive Plotly charts as HTML strings
- `EDAReportGenerator`: Produces the self-contained HTML report

### Key Modules

**`src/preprocessing/preprocessing.py`** - Core preprocessing transformers:
- `ToDummy`: Converts categorical variables to dummy variables
- `TeEncoder`: Target encoding for categorical variables
- `CardinalityReducer`: Reduces cardinality of categorical features
- `CastDtype`: Converts columns to a specific pandas dtype
- `TsfelVars`: Time series feature extraction using tsfel library
- `ExtraVars`: Creates statistical features from consumption time series (mean, slope, std, zeros count, etc.)
- `MinMaxScalerRow`: Row-wise MinMax scaling transformer

**`src/modeling/supervised_models.py`** - Supervised model classes:
- `LGBMModel`: LightGBM with imbalanced-learn sampling (undersample/over)
- `CATModel`: CatBoost with native categorical handling
- `NNModel`: Feedforward neural network (TensorFlow/Keras)
- `LSTMNNModel`: LSTM + Dense neural network for sequential consumption data

**`src/modeling/ensemble.py`** - Ensemble model combining multiple base models:
- `EnsembleModel`: Combines N base models via soft voting or stacking with meta-learner
  - `method`: `"soft_voting"` (weighted average) or `"stacking"` (meta-learner trained on base predictions)
  - `use_val_as_oof`: True=blending (fast, uses val set); False=proper K-fold OOF (slower, no leakage)
  - `skip_base_fit`: When True, assumes base models are pre-fitted; only trains meta-learner
  - `ensemble_description` property: Human-readable format like `"Ensemble (lightgbm, catboost)"`

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

- Configuration uses **3 separate YAML files**: `etl.yaml`, `train.yaml`, `infer.yaml` (no more `feature_pipeline.yaml`)
- `feature_engineering` is now a sub-section inside `train.yaml` (not a separate file or top-level section)
- The CLI accepts multiple `--config` parameters which are merged ("last wins" for duplicates)
- `preprocessing` and `feature_selection` are unified under `train.feature_engineering`
- **Model configuration uses `models:` list (not singular `model:`)**: single model as list with one item, multiple models enable ensemble
- **Ensemble configuration**: When `len(models) > 1`, `ensemble:` section is required; specifies `method` (`stacking` or `soft_voting`), `meta_learner` (for stacking), and `use_val_as_oof` (blending vs OOF)
- **Output directory structure**: Single model saves to `models/model.pkl`; ensemble saves each base model to `models/{name}/model.pkl` and the ensemble to `models/ensemble.pkl`
- All categorical preprocessing is defined in `get_preprocesor(preprocesor_num)` in `supervised_models.py`
- Time series consumption data uses row-wise MinMax scaling (`MinMaxScalerRow`)
- Neural models concatenate processed features with scaled consumption series
- LSTM models reshape consumption data to (samples, 12, 1) for sequential processing
- Preprocessed datasets are saved in `data/processed/` as parquet files (include target column for inspection)
- Feature pipelines are saved as `.pkl` files for reuse in training and inference
- **ETL configuration requires `custom_class` for each ETL** - use `SourceETL` (supports both `concat` and `merge` modes) or a custom class
- **New projects include `data/raw/sample_dataset.parquet`** for immediate testing
- The framework uses Python's `logging` module for all internal logging (configurable via logging handlers)
- CLI output uses `click.echo` for user-facing messages

### Language Context

The project documentation and comments are in English. The codebase uses Spanish variable names for features (e.g., `actividad`, `tipo_tarifa`, `zona`) but English for class/method names.
