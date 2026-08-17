# AGENTS.md / CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Name**: Energizados

Energizados is a machine learning framework for detecting electricity theft (non-technical losses in energy distribution). The project implements both simple rule-based models and complex supervised models (LightGBM, CatBoost, XGBoost, Neural Networks, LSTM), plus anomaly detection features via the `if_score` global transformer (Isolation Forest score).

The framework also includes an **ETL system** with support for multiple ETLs with dependencies using YAML configuration.

## Development Commands

### Environment Setup

```bash
# Poetry (recommended — installs the pinned poetry.lock)
poetry install --extras dev

# Or uv (fast; resolves from pyproject.toml, no lock file — avoid `uv sync`, it creates uv.lock)
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"

# Or plain pip
pip install -e ".[dev]"

jupyter lab
```

### Testing & Quality

```bash
pytest tests/                    # Run all tests (slow tests deselected by default)
pytest tests/ -m slow            # Run ONLY slow tests
pytest tests/ -m "not slow"      # Explicitly omit slow tests (same as default)
pytest tests/ -x                 # Stop on first failure
pytest tests/ -k "test_etl"      # Run specific tests
pre-commit run --all-files       # Run all linters (isort, black, bandit, flake8)
```

**Slow tests convention:** Tests that take a long time (end-to-end pipeline runs, full model training, boruta with many estimators) must be marked `@pytest.mark.slow`. A plain `pytest` omits them by default (configured via `addopts` in `pyproject.toml`); run them explicitly with `pytest -m slow`. The `slow`, `integration`, and `unit` markers are registered under `[tool.pytest.ini_options]` with `--strict-markers`, so unregistered markers fail loudly.

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
energizados run train --step train

# Run specific ETL
energizados run etl --etl sample

# Run EDA
energizados run eda

# Dry run (see plan without executing)
energizados run etl --dry-run

# Run with custom name (replaces if exists)
energizados run train -n mi-experimento
```

### Memory Profiling (`-vv`)

Run any pipeline with `-vv` to sample process RSS around every ETL and step and surface a live per-step memory readout plus a final profiling table:

```bash
energizados run etl,train -vv          # shows Δ + peak per step, then a Memory profile table
```

- **Metric**: process RSS via `psutil` — the correct choice for pandas/numpy DataFrames, which live in C-level memory that `tracemalloc` cannot see.
- **Overhead**: zero without `-vv`; the sampler daemon thread only starts under `verbose >= 2`.
- **Output**: each completed step shows `Δ<retained> peak <max>` in the progress bar (a `⚠` appears when a step retains more than 1 GB), followed by a `Memory profile` table sorted by peak.
- **Programmatic**: `ETLOrchestrator(..., profile_memory=True)` and `Pipeline(..., profile_memory=True)` enable sampling; metrics land in `on_etl_complete(name, rows, metrics=...)` / `on_step_complete(name, i, total, metrics=...)` and in `.memory_metrics`. The reusable primitive is `energizados.core.utils.memory_sampler.MemorySampler` (context manager) plus `format_bytes`.

### Web Console (async job runner)

```bash
# Install web dependencies
pip install -e ".[web]"

# Start BOTH server + worker with one command (recommended)
energizados-web --host 127.0.0.1 --port 8000 --db-path data/web/jobs.db --log-level INFO

# Or run them separately:
uvicorn energizados.web.app:app --reload          # Web server (FastAPI + HTMX UI)
energizados-web-worker --db-path data/web/jobs.db --log-level INFO  # Worker (job execution engine)
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

**Domain language**: `CONTEXT.md` is the single source of truth for ubiquitous-language terms (Pipeline, Step, Context, Model, Ensemble, Registry, Run, Job, Project…). Use the canonical terms and respect each `_Avoid_` list when naming code or writing docs. Key disambiguations: framework `Pipeline` ≠ user `Custom Pipeline` (`BasePipeline`); core `Run` (training output) is generalized by the web console; `Model` = `BaseModel` unit (single Adapter or Ensemble), not the raw estimator.

### Directory Structure

**Framework source (`src/energizados/`):**

```
src/energizados/
├── contracts.py      # **SINGLE HOME** for all 8 framework base classes (see Base Classes section)
├── preprocessing/      # Data cleaning and feature engineering transformers
│   ├── isolation_forest_score.py  # IsolationForestScore — sklearn transformer for IF anomaly scoring
├── modeling/           # Model implementations (supervised and unsupervised)
│   ├── adapters.py    # LGBMModelAdapter, CATModelAdapter, XGBModelAdapter, NNModelAdapter, LSTMNNModelAdapter
│   ├── registry.py    # ModelRegistry with all registered model names
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
│   ├── default.py     # DefaultInference implementation
│   └── hierarchical.py # HierarchicalInference — routes rows to per-route models
├── core/              # Core framework components
│   ├── base.py        # BaseModel, BaseInference, PipelineStep (shim re-exports from energizados.contracts)
│   ├── pipeline.py    # Pipeline orchestrator (ConfigPipelineBuilder)
│   ├── builders/      # Step-specific builder implementations
│   │   ├── base.py          # StepBuilder: abstract base class
│   │   ├── director.py      # PipelineDirector: orchestrates pipeline construction
│   │   ├── run_manager.py   # RunManager: run dirs + index.html
│   │   ├── etl_builder.py
│   │   ├── split_builder.py
│   │   ├── training_builder.py
│   │   ├── evaluation_builder.py
│   │   ├── inference_builder.py
│   │   └── eda_builder.py
│   ├── schemas/       # Pydantic config schemas & validator
│   │   ├── schemas.py
│   │   └── config_validator.py
│   ├── steps/         # Pipeline step implementations
│   │   ├── split.py   # SplitStep
│   │   └── training.py # TrainingStep
│   ├── plots/         # Shared plot utilities
│   │   └── utils.py
│   └── utils/         # Internal utilities
│       ├── import_utils.py   # Dynamic class import with allowlist
│       └── integrity_pickle.py  # SHA-256 verified pickle save/load
├── explainability/    # SHAP-based model explainability
│   └── shap_explainer.py
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
├── etl/               # ETL framework components
│   ├── base.py        # BaseETL abstract class
│   ├── pipeline.py    # SourceETL implementation
│   └── orchestrator.py # ETLOrchestrator for dependency management
└── web/               # Web console and async job runner (multi-project workspace)
    ├── app.py         # FastAPI web application with HTMX support
    ├── launcher.py    # energizados-web — cross-platform launcher (spawns server + worker)
    ├── projects.py    # Multi-project workspace management
    ├── store.py       # JobStore with SQLite persistence
    ├── runner.py      # JobRunner worker execution engine
    ├── worker.py      # Worker CLI entrypoint
    ├── models.py      # JobStatus enum and JobRow dataclass
    ├── docs/          # Web console documentation
    ├── templates/     # Jinja2 templates (jobs, runs, dashboard, projects, compare_runs…)
    └── static/        # Static assets (CSS, JS, etc.)
```

### Base Classes (Public API)

The **single home** for all framework base classes is `energizados.contracts` (added in v0.2.7). All 8 base classes are defined there:

- **`BaseModel`** — Abstract base for custom ML models. Requires `fit()`, `predict()`, `predict_proba()`, `get_raw_model()`.
- **`BaseInference`** — Abstract base for inference engines. Requires `predict()`, `predict_proba()`, `load_model()`, `save_predictions()`.
- **`BasePipeline`** — Abstract base for user-defined pipelines. Requires `run(context)`.
- **`BaseEvaluator`** — Abstract base for model evaluation. Requires `evaluate(X, y, model, threshold=0.5)`.
- **`BaseETL`** — Abstract base for ETL processes. Requires `extract()`, `transform()`, `load()`.
- **`BaseFeatureEngineering`** — Abstract base for feature engineering pipelines. Requires `fit()`, `transform()`. Includes `save()`/`load()` via `integrity_pickle`.
- **`BaseFeatureSelector`** — Abstract base for feature selection methods. Requires `fit()`, `transform()`.
- **`BaseExplorer`** — Abstract base for exploratory data analysis. Requires `explore()`.

**Backward-compatible import paths** (shim re-exports from `energizados.contracts`):

- `energizados.core.base.BaseModel`
- `energizados.core.base.BaseInference`
- `energizados.etl.base.BaseETL`
- `energizados.feature_engineering.base.BaseFeatureEngineering`
- `energizados.feature_selection.base.BaseFeatureSelector`
- `energizados.eda.base.BaseExplorer`
- `energizados.inference.base.BaseInference`

**Stability commitment**: 5 of the 8 base classes are **frozen public API** — they have multiple adapters or subclasses in the framework, which validates their interface shape. The other 3 are **extension points for users**: still supported, but not stability-frozen, because a single adapter (or none) does not yet validate the interface shape against real-world usage. They will be promoted to frozen API when a second adapter appears in the wild.

| Base class | Framework adapters | Status |
|---|---|---|
| `BaseModel` | 7 adapters (`LGBMModelAdapter`, `CATModelAdapter`, `XGBModelAdapter`, `NNModelAdapter`, `LSTMNNModelAdapter`, `SimpleTrendAdapter`, `SimpleConstantAdapter`) | **frozen** |
| `BaseETL` | 4+ subclasses (`SourceETL`, `CleanFilesETL`, `ClipOutliersETL`, `GeoFeaturesETL`) | **frozen** |
| `BaseFeatureSelector` | 6 subclasses (`BorutaSelector`, `CorrelationSelector`, `ConstantSelector`, plus their variants) | **frozen** |
| `BaseExplorer` | 7+ subclasses under `energizados.eda.*` | **frozen** |
| `BaseInference` | 2 adapters (`DefaultInference`, `HierarchicalInference`) | **frozen** |
| `BasePipeline` | 0 framework consumers (the framework's own `Pipeline` does not inherit it — see class docstring) | **extension point** |
| `BaseEvaluator` | 1 adapter (`DefaultEvaluator`) | **extension point** |
| `BaseFeatureEngineering` | 1 adapter (`DefaultFeatureEngineering`) | **extension point** |

Shims guarantee old import paths continue to work for all 8.

### Service Layer API (energizados.api)

The **service layer API** (`energizados.api`) provides programmatic framework usage with structured return values and no stdout coupling. All CLI commands delegate to this API layer.

**Core API Functions:**

- **`validate_dict(config, config_type)`** — Configuration validation without file I/O
  - Returns `ValidationResult` with `is_valid`, `errors`, `warnings`, `info`
  - Use `result.to_dict()` for JSON serialization
  - Replaces CLI `validate` command for programmatic access

- **`Pipeline.from_dict(config)`** — Create pipeline from dict
  - Alternative to YAML-based pipeline creation
  - Returns configured `Pipeline` instance

- **`Pipeline.plan()`** — Get execution plan without running
  - Returns DAG of steps and dependencies
  - Useful for debugging and validation

- **`RunManager`** — Query interface for run metadata
  - `RunManager.list_runs()` — Get all run directories
  - `RunManager.get_run(run_id)` — Get specific run metadata
  - `RunManager.get_latest_run()` — Get most recent run

- **`RunResult.from_context(context)`** — Structured access to pipeline results
  - Converts pipeline context to structured result
  - Use for JSON output in web applications

- **`ProgressEvent`** — Progress streaming for observability
  - `console_progress()` — CLI progress bar helper
  - Event-based progress for long-running operations

- **`merge_configs(configs)`** — Configuration merging utility
  - Deep merge for multiple config dicts
  - Last-write-wins for scalar values

- **`doctor(include_optional=False)`** — System health checks
  - Returns `DoctorReport` with `system_info` and `checks`
  - Use `report.to_dict()` for JSON serialization

- **`format_error(exception)`** — Exception formatting helper
  - Standardized error messages with error codes

- **`register_allowed_prefix(prefix)`** — Import safety extension
  - Register custom module prefixes for dynamic imports
  - Use for project-specific class prefixes beyond `energizados.` and `src.`
  - Example: `register_allowed_prefix("ml_models")`

**Migration Notes:**

- **`result["model_metrics"]` deprecated**: Pipeline run results now use `result["metrics"]` as the canonical key for both single-model and ensemble runs. The legacy `result["model_metrics"]` key is still supported — it maps to `metrics` — but emits a `DeprecationWarning`. Removal is deferred; as of v0.3.1 the alias has not been removed yet. This deprecates the result-dict key, not a module.
- **`ALLOWED_PREFIXES` narrowed**: The default allowlist now contains only `{"energizados.", "src."}` for security. Projects using custom prefixes (e.g., `data.`, `features.`) must call `register_allowed_prefix()` before framework usage.

**Generated project structure (`energizados init`):**

```
mi_proyecto/
├── config/                 # Configuration files
│   ├── etl.yaml
│   ├── train.yaml         # Includes split, feature_engineering, model, evaluation
│   └── infer.yaml
├── data/
│   ├── raw/               # Input data (includes sample_dataset.parquet)
│   ├── processed/         # ETL outputs and feature engineering results
│   └── temp/              # Temporary files
│       └── splits/        # Train/val/test splits
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
  schema_version: 1
  sample:
    enabled: true
    description: "Processes example dataset (removes rows with NULL)"
    input: "data/raw/sample_dataset.parquet"
    output: "data/processed/sample_dataset.parquet"
    custom_class: "src.data.custom_etl.CustomETL"
    params:
      mode: "concat"  # 'concat' (default) or 'merge'
    depends_on: []
```

The sample ETL uses the project's own `CustomETL` class (generated in `src/data/custom_etl.py`, extends `BaseETL`). Use `energizados.etl.pipeline.SourceETL` when you want the built-in implementation directly.

**SourceETL Modes:**

`SourceETL` supports three processing modes via the `mode` parameter:

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

3. **`incremental`**: Filters records by a key column — only rows newer than the last processed value are kept. Stores the high-water mark in a state file so each run continues from where the previous one left off. Processes files one-by-one for constant memory usage.

   ```yaml
   consumos_incremental:
     enabled: true
     input: "data/raw/consumos_*.csv"   # glob — all matching files are read
     output: "data/processed/consumos/" # directory; partitions written inside
     custom_class: "energizados.etl.pipeline.SourceETL"
     params:
       mode: "incremental"
       incremental_key: "fecha_actualizacion"  # datetime column to filter new records
       incremental_format: null                # optional: explicit strftime for date parsing (e.g. "%d/%m/%Y")
       incremental_partition: "%Y-%m"          # strftime for partition values (default: monthly)
       reprocess: false                        # true = re-read all files; false = only pending
       write_mode: "append"                    # "append" = concat to existing; "replace" = overwrite
       state_file: ".cache/etl_states/consumos.json"
       # last_processed: "2024-01-01"  # optional: initial cutoff on first run
   ```

**Important:**

- When `mode="merge"`, `merge_config` is required. Accepts any `pd.merge()` parameter: `how`, `on`, `left_on`, `right_on`, `left_index`, `right_index`.
- When `mode="incremental"`, `incremental_key` is required. The column is parsed as datetime automatically if needed. On first run all records are processed (unless `last_processed` is set). After each run `max(incremental_key)` is persisted in `state_file`.
- `incremental_format`: Optional strftime string for explicit date parsing. When set, `pd.to_datetime(col, format=incremental_format)` is used instead of auto-parsing. Useful for ambiguous date formats like `"15/01/2024"` (DD/MM/YYYY).
- `incremental_partition`: strftime format string (default `"%Y-%m"`). Controls output partition directory names. Output structure: `output_dir/partition=<value>/data.parquet`. Common values: `"%Y-%m"` → `partition=2024-01/`, `"%Y"` → `partition=2024/`.
- `partition_by` is **deprecated** in incremental mode. If passed, a deprecation warning is logged and the parameter is ignored. Use `incremental_partition` instead. For concat/merge modes, `partition_by` still works with Hive-style partitioning.

### Project Versioning

Each config file includes a `schema_version` inside its root section, allowing independent evolution:

```yaml
# etl.yaml
etl:
  schema_version: 1
  sample:
    enabled: true
    ...

# train.yaml
train:
  schema_version: 2
  enabled: true
  ...
```

- **Per-section schema**: Each config type (etl, train, eda, infer) has its own schema version that evolves independently. Defined in `CURRENT_SCHEMA_VERSIONS` dict in `src/energizados/_version.py`.
- **Schema validation**: The CLI checks each section's `schema_version` before `run` and `validate`. If a section's schema is newer than the framework supports, execution is blocked with an upgrade message.
- **ETL filtering**: The `schema_version` key is filtered out by `ETLOrchestrator` and validators so it's not treated as an ETL name.
- **Version pinning**: Generated `requirements.txt` uses `energizados~=X.Y.Z` (compatible release) to allow patches but block breaking changes.

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
  # output_name: "mi-experimento"  # override opcional del NOMBRE del run-dir (igual que CLI -n); default: train-<timestamp>

  split:
    method: "time_series"  # Opciones: stratified, random, time_series, group_based, stratified_time
    # Para time_series:
    date_column: "fecha_inspeccion"
    train_period: ["2010-01-01", "2017-08-01"]
    val_period: ["2017-09-01", "2017-12-31"]
    test_period: ["2018-01-01"]
    save_splits: true
    splits_dir: "data/temp/splits/"
    # Para stratified/random:
    # test_size: 0.2
    # val_size: 0.1
    # random_state: 42
    # Para stratified_time (split temporal dentro de cada cluster geográfico):
    # method: "stratified_time"
    # date_column: "fecha_inspeccion"
    # cluster_column: "geo_cluster"   # requiere GeoFeaturesETL ejecutado previamente
    # test_size: 0.15
    # val_size: 0.15
    #
    # Optional: inject unlabeled negatives as target=0 (reduces selection bias)
    # unlabeled_negatives:
    #   enabled: true
    #   source_path: "data/external/unlabeled.parquet"
    #   max_per_cutoff: 1500
    #   random_state: 42
    #   date_column: "fecha_inspeccion"
    #   id_column: "contract_id"
    #
    # Optional: balance geographic representation in train set
    # geo_stratify:
    #   enabled: true
    #   column: "geo_region"
    #   strategy: "proportional"  # proportional | equal | capped
    #   max_per_stratum: null     # required when strategy: capped
    #   random_state: 42

  feature_engineering:
    enabled: true
    output_pkl: "data/processed/feature_engineering.pkl"

    preprocessing:
      enabled: true
      # output_parquet: "data/processed/preprocessing.parquet"  # opcional (incluye target para inspección)
      # columns_filter: Row-level filtering applied before feature engineering.
      #   Supports equality, comparison operators, and pandas query expressions.
      #   Examples:
      #     columns_filter:
      #       geo_region: "FLORIANOPOLIS"              # simple equality
      #       zona: ["NORTE", "SUL"]                   # multiple values
      #       consumo: {">": 100, "<=": 50000}         # comparison operators
      #       _expr: "(zona != 'A') & (consumo > 200)"  # pandas query expression
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
    - type: "lightgbm"  # lightgbm, catboost, xgboost, neural_network, lstm
      sampling:
        method: "undersample"  # oversample, undersample, smotetomek, none
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
| `tsfel_vars` | Time series feature extraction using tsfel | `num_periodos` (int, default=12), `features` (dict, default=None — inline `{domain: [names]}` selection; if null uses all domains and logs the list at INFO), `periods_suffix` (str, default="_anterior"), `n_jobs` (int, default=1), `chunk_size` (int, default=500), `cache_dir` (str, default=None) |
| `extra_vars` | Statistical features for different time windows | `num_periodos` (int, default=3), `periods_suffix` (str, default="_anterior"), `count_nulls` (bool, default=False — adds `cant_null_N`: count of NaN values per row) |
| `consumption_patterns` | Domain-specific fraud detection features (abrupt drops, zero ratio, drastic changes, consistency, z-score vs history, autocorrelation, seasonal ratio) | `num_periodos` (int, default=12), `periods_suffix` (str, default="_anterior"), `enable_diff_ratios` (bool, default=True), `enable_minmax_ratio` (bool, default=True), `enable_zscore` (bool, default=True), `enable_zero_ratio` (bool, default=True), `enable_slope` (bool, default=True), `enable_consistency` (bool, default=True), `enable_drastic_changes` (bool, default=True), `drastic_threshold` (float, default=0.5), `enable_last_period_zscore` (bool, default=False — `zscore_last_vs_history_N`: z-score of last month vs client's own mean/std), `enable_autocorr_lag1` (bool, default=False — `autocorr_lag1_N`: lag-1 autocorrelation; low = manipulation signal), `enable_seasonal_ratio` (bool, default=False — `seasonal_ratio_N`: summer/winter mean ratio for southern hemisphere; requires `date_column`), `date_column` (str, default=None — required when `enable_seasonal_ratio=True`) |
| `temporal_features` | Calendar features from a date column with flat (`month=7`) and/or cyclic (`month_sin/cos`) encoding. Cyclic encoding preserves calendar circularity (Dec & Jan are neighbors) | `date_column` (str, required), `features` (list, default=["month","quarter","week","dayofweek"] — also supports "day","year"), `encoding` (str, default="both" — "flat"/"cyclic"/"both"), `drop_date_column` (bool, default=False) |
| `geo_features` | `GeoFeatures` still lives in `preprocessing/geo_features.py`; `GeoFeaturesETL` wraps it for the ETL stage. Not a built-in `global_transformers` key — to use it inside feature engineering, reference it via `custom_class` (see example below). | `custom_class` path + `GeoFeatures` params |
| `group_relative_consumption` | **[pre-encoding]** Consumption relative to group statistics (e.g., actividad, tarifa, zona). Generates `prop_cons_{window}_{metric}_{group_column}` — strong fraud signal when a client deviates from its peer group. Group stats are learned from `fit()` data (use full population for anti-leakage). Runs before column encoding — `group_column` must be the original categorical column name. | `group_column` (str, default="actividad"), `windows` (list[int], default=[3, 6, 12]), `metrics` (list[str], default=["mean", "max"] — supported: "mean", "max"), `periods_suffix` (str, default="_anterior") |
| `seasonal_anomaly` | **[pre-encoding]** Seasonal z-score for each consumption month: `(consumo_mes - mean_grupo_mes) / std_grupo_mes` using `group_column × calendar_month` as group. Tells the model "this client consumes X% less than expected for its type in this month". Runs before column encoding — `group_column` must be the original categorical column name. | `group_column` (str, default="actividad"), `date_column` (str, required — inspection date to map periods to calendar months), `periods_suffix` (str, default="_anterior") |
| `clip_outliers` | Clips extreme values in consumption columns (data reading errors) — run FIRST among post-encoding global_transformers | `threshold` (float, default=100000), `columns` (list, default=None — auto-detects `*_anterior`), `periods_suffix` (str, default="_anterior") |
| `if_score` | Isolation Forest anomaly score (inverted, higher = more anomalous) — appends `if_score` column | `columns` (list, default=None — auto-detect by `periods_suffix`, fallback all numeric), `n_estimators` (int, default=100), `max_samples` (int/str, default="auto"), `max_features` (float, default=1.0), `contamination` (float/str, default="auto"), `random_state` (int, default=None), `contamination_from_target` (bool, default=False — uses `y.mean()`), `output_column` (str, default="if_score"), `periods_suffix` (str, default="_anterior") |

**Global Transformers:**

Global transformers are listed under a single `global_transformers` key. The framework automatically splits them into two stages based on each transformer's `pipeline_stage` class attribute:

- **pre** (`pipeline_stage = "pre"`): runs before column encoding — sees original categorical columns. Used by `group_relative_consumption` and `seasonal_anomaly`.
- **post** (default): runs after column encoding. Used by all other built-in transformers.

Pipeline order: **[pre?] → column_transformer → [post?]**

```yaml
preprocessing:
  columns:
    # ... column-based preprocessing

  global_transformers:
    # [pre-encoding] — runs BEFORE column_transformer, needs original categorical columns
    # group_column must be the raw column name (e.g. "actividad", not "actividad_prob")
    - group_relative_consumption:
        group_column: "actividad"
        windows: [3, 6, 12]
        metrics: ["mean", "max"]
        periods_suffix: "_anterior"

    # [pre-encoding] — runs BEFORE column_transformer
    - seasonal_anomaly:
        group_column: "actividad"
        date_column: "fecha_inspeccion"
        periods_suffix: "_anterior"

    # [post-encoding] — all transformers below run AFTER column_transformer

    # Clip extreme values FIRST among post-encoding transformers (removes data reading errors)
    - clip_outliers:
        threshold: 100000
        periods_suffix: "_anterior"

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
    # NOTE: `geo_features` is NOT a built-in global_transformers key. The
    # GeoFeatures class lives in energizados.preprocessing.geo_features; use it
    # via custom_class here, or prefer GeoFeaturesETL in etl.yaml for the ETL stage.
    - custom_class: "energizados.preprocessing.geo_features.GeoFeatures"
      params:
        lat_col: "latitud"
        lon_col: "longitud"
        include_hierarchy: true               # true = all; false = none; or list like ["estado", "municipio"]
        include_target_encoding: true
        te_w: 20
        include_distances: true
        distance_cities:
          - sao_paulo
          - rio_de_janeiro
          - brasilia
        include_coords: false
        cache_dir: ".cache/ibge"  # persist IBGE shapefiles to disk (avoids re-download)

    # Custom class para transformers globales
    - custom_class: "preprocessing.CustomGlobalTransformer"
      params:
        custom_param: value
```

**Custom class options in `feature_engineering`:**

- Per-column: `custom_class` inside a column's transformer list
- Full preprocessing replacement: `preprocessing.custom_class`
- Full feature engineering replacement: `feature_engineering.custom_class`
- Custom model: NOT supported via `custom_class` in `models:` — register the class in `ModelRegistry` (`ModelRegistry.register(name, cls)` with a `from_config(cls, config, X_train)` classmethod) and reference it via `type: "<registered-name>"`

**Key Feature Engineering Classes (internal framework):**

- `BaseFeatureEngineering`: Abstract base class for custom implementations (`feature_engineering/base.py`)
- `DefaultFeatureEngineering`: Default implementation combining preprocessing + feature selection (`feature_engineering/default.py`)
- Methods: `fit(X, y)`, `transform(X)`, `fit_transform(X, y)`, `save(path)`, `load(path)`

**Key Inference Classes (internal framework):**

- `BaseInference`: Abstract base class for inference (`inference/base.py`)
- `DefaultInference`: Default single-model inference (`inference/default.py`)
- `HierarchicalInference`: Routes rows to different models based on column-value conditions (`inference/hierarchical.py`). Configured in `infer.yaml` via `routes` (list of `{name, condition: {col: value | [values]}, model_path}`), `default_model_path`, and optional `feature_engineering_paths` (dict route name → FE `.pkl`). Use "**default**" as the key in `feature_engineering_paths` to provide FE for the default model's rows. It loads its own route models internally, so `model_path` is **not** required at the top level when routes are configured. Rows matching no route use the default model.

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
- `SourceETL`: Reads from one or multiple source files with `mode` parameter (`concat`, `merge`, or `incremental`). Key incremental params: `incremental_key` (column used to filter new records), `last_processed` (initial cutoff), `incremental_format` (optional strftime for date parsing), `incremental_partition` (strftime for partition values, default `"%Y-%m"` → `partition=YYYY-MM/`), `state_file` (persists high-water mark across runs). `partition_by` is deprecated in incremental mode — use `incremental_partition` instead.
- `ClipOutliersETL`: Clips extreme values in consumption columns (data reading errors). Use after the main dataset-building ETL, before training. `custom_class: "energizados.etl.pipeline.ClipOutliersETL"`.
- `GeoFeaturesETL`: Adds geographic features from lat/lon coordinates. Appends `geo_cluster` (int, KMeans), IBGE hierarchy (`geo_estado`, `geo_municipio`, `geo_regiao`), and haversine distance columns. Run after the main dataset ETL and before training. Required if using `stratified_time` split. Points with invalid/zero coords get `geo_cluster=-1` and `"sin_dato"` for hierarchy. `custom_class: "energizados.etl.pipeline.GeoFeaturesETL"`. Params: `n_clusters` (default: 10), `lat_col`, `lon_col`, `random_state`, `include_cluster` (bool, default: `True` — set to `False` to skip KMeans clustering and only keep hierarchy/distances features), `include_hierarchy` (bool or list of level names: `"estado"`, `"municipio"`, `"regiao"` — `true`=all, `false`=none, list=specific subset), `include_distances` (bool), `distance_cities` (list), `include_coords` (bool), `cache_dir` (str), `regions_file` (str, path to a `REGION;CITY` CSV — when set, `geo_regiao` is assigned by matching IBGE municipality names to `CITY`, accent- and case-insensitive; takes priority over `region_cities`; on `fit()` logs matched/unmatched municipalities and stores `unmatched_municipalities_` and `matched_municipalities_` attributes for diagnostics), `region_cities` (list of city keys from `REFERENCE_CITIES` — when set and `regions_file` is not provided, `geo_regiao` is the nearest city by haversine distance instead of the IBGE macro-region), `geo_model_path` (str, path to persist/load the KMeans+scaler model — train fits+saves, infer loads if present for consistent clusters; omit to fit fresh). ADR-0001: clustering is owned by the `GeoFeatures` transformer; `GeoFeaturesETL` is a thin wrapper that delegates to it while preserving this param surface.
- `CleanFilesETL`: Deletes files listed in the `input` field. Useful for removing intermediate outputs after the pipeline completes. Supports `@etl_name` references, glob patterns, and direct paths in `input`. Does not produce a dataset — returns an empty DataFrame so the orchestrator tracks it normally in the DAG. `custom_class: "energizados.etl.pipeline.CleanFilesETL"`. Params: `missing_ok` (bool, default: `True` — silently skips missing files). The `output` field is optional (no file is written).
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

**`src/energizados/preprocessing/preprocessing.py`** - Core preprocessing transformers:

- `ToDummy`: Converts categorical variables to dummy variables
- `TeEncoder`: Target encoding for categorical variables
- `CardinalityReducer`: Reduces cardinality of categorical features
- `CastDtype`: Converts columns to a specific pandas dtype
- `TsfelVars`: Time series feature extraction using tsfel library
- `ExtraVars`: Creates statistical features from consumption time series (mean, slope, std, zeros count, etc.)
- `MinMaxScalerRow`: Row-wise MinMax scaling transformer

**`src/energizados/modeling/supervised_models.py`** - Supervised model classes:

- `LGBMModel`: LightGBM with imbalanced-learn sampling (undersample/over)
- `CATModel`: CatBoost with native categorical handling
- `XGBModel`: XGBoost with imbalanced-learn sampling (optional dependency: `pip install energizados[xgboost]`)
- `NNModel`: Feedforward neural network (TensorFlow/Keras)
- `LSTMNNModel`: LSTM + Dense neural network for sequential consumption data

**`src/energizados/modeling/adapters.py`** - Model adapters implementing BaseModel interface:

- `LGBMModelAdapter`, `CATModelAdapter`, `XGBModelAdapter`: Wrap supervised models
- `NNModelAdapter`, `LSTMNNModelAdapter`: Wrap neural network models
- `SimpleTrendAdapter`, `SimpleConstantAdapter`: Rule-based baseline models

**`src/energizados/modeling/ensemble.py`** - Ensemble model combining multiple base models:

- `EnsembleModel`: Combines N base models via soft voting or stacking with meta-learner
  - `method`: `"soft_voting"` (weighted average) or `"stacking"` (meta-learner trained on base predictions)
  - `use_val_as_oof`: True=blending (fast, uses val set); False=proper K-fold OOF (slower, no leakage)
  - `skip_base_fit`: When True, assumes base models are pre-fitted; only trains meta-learner
  - `ensemble_description` property: Human-readable format like `"Ensemble (lightgbm, catboost)"`

**`src/energizados/modeling/simple_models.py`** - Rule-based baseline models:

- `ChangeTrendPercentajeIdentifierWide`: Detects dramatic consumption drops
- `ConstantConsumptionClassifierWide`: Identifies constant consumption patterns

**`src/energizados/feature_selection/methods.py`** - Feature selection methods:

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
- **ETL configuration requires `custom_class` for each ETL** - use `SourceETL` (supports `concat`, `merge`, and `incremental` modes) or a custom class
- **New projects include `data/raw/sample_dataset.parquet`** for immediate testing
- The framework uses Python's `logging` module for all internal logging (configurable via logging handlers)
- CLI output uses `click.echo` for user-facing messages

### Language Context

The project documentation and comments are in English. The codebase uses Spanish variable names for features (e.g., `actividad`, `tipo_tarifa`, `zona`) but English for class/method names.

### Exception Hierarchy (Public API)

The exception hierarchy in `src/energizados/core/exceptions.py` is a **stable public API**. Every framework exception subclasses `EnergizadosError`, so `except EnergizadosError` catches all framework errors. Types that replace a stdlib exception additionally inherit it, so existing `except ValueError` / `except RuntimeError` callers keep working.

| Type | Bases | Raised by |
|------|-------|-----------|
| `EnergizadosError` | `(Exception,)` | Public base — `except EnergizadosError` catches all framework errors |
| `PipelineError` | `(EnergizadosError,)` | `Pipeline.run` wrapping unexpected step errors (preserves cause on `__cause__`) |
| `StepValidationError` | `(EnergizadosError,)` | Step input/context validation failures |
| `ConfigurationError` | `(EnergizadosError,)` | YAML config format/value/missing-field errors |
| `ETLError` | `(EnergizadosError,)` | ETL extract/transform/load phase errors |
| `ETLDependencyError` | `(EnergizadosError,)` | ETL DAG dependency/cycle errors |
| `ModelNotFittedError` | `(EnergizadosError, ValueError)` | `predict`/`transform`/`save` on an unfitted model, feature-engineering, or selector |
| `TransformerError` | `(EnergizadosError, ValueError)` | Feature-engineering transform failures |
| `FeatureSelectionError` | `(EnergizadosError, ValueError)` | Feature-selection operation failures |
| `InferenceError` | `(EnergizadosError, RuntimeError)` | Inference engine failures (e.g. `predict_proba` before `load_model`) |
| `EvaluatorError` | `(EnergizadosError,)` | Evaluation/reporting failures (no raise site yet — reserved) |

**Boundary contract:** `Pipeline.run` re-raises any `EnergizadosError` subclass from a step unchanged (type/attributes/traceback preserved); only non-framework `Exception`s are wrapped as `PipelineError` via `from e`. Catch `except EnergizadosError` (not `except PipelineError`) to intercept inner framework errors.

**Stability commitment:** This hierarchy is frozen public API. Future changes (renames, base-class changes, removals) require a deprecation path — never a silent break. Adding new subclasses of `EnergizadosError` is allowed and non-breaking.

## Skills

| Skill | Description | Trigger |
|-------|-------------|---------|
| `experiment-results` | Generates a complete experiment results report with metrics, insights, next steps, and a business section with operational impact simulator. | When the user requests experiment results or to generate _results.md. [SKILL.md](.claude/skills/experiment-results/SKILL.md) |
| `new-experiments` | Design and generate a complete set of ML training experiments (roadmap + YAMLs) for an Energizados project. | When the user says "new experiments", "nuevos experimentos", "crear experimentos". [SKILL.md](.claude/skills/new-experiments/SKILL.md) |
| `run-experiment` | Run a full training experiment (validate → ETL → train) and surface key metrics from the JSON report. | When the user wants to kick off a pipeline run and see results. [SKILL.md](.claude/skills/run-experiment/SKILL.md) |
| `new-etl` | Scaffold a new ETL block for `config/etl.yaml` (name, mode, inputs, outputs, dependencies). | When the user says "new etl", "nuevo etl", "agregar etl". [SKILL.md](.claude/skills/new-etl/SKILL.md) |
| `marp-slides` | Convert a slide-delimited markdown file into a professional Marp presentation (PDF/PPTX/HTML) with the energizados theme and quality validation. | When the user wants to generate slides, presentation, deck from markdown. [SKILL.md](.claude/skills/marp-slides/SKILL.md) |
| `version-deliverable` | Generate a version deliverable document (Markdown) summarizing experiments, winning model, results, and comparison vs previous version. | When the user says "entregable de versión", "generar entregable", "version deliverable", "release notes versión". [SKILL.md](.claude/skills/version-deliverable/SKILL.md) |

## Agent Rules (Always Apply)

- Update CLAUDE.md and all documentation if necessary.
- Check and fix tests.
- Check pre-commit rules and ensure controls pass.
- Do NOT use `print` for logging. Use the Python `logging` module instead.

## Agent skills

### Issue tracker

Issues live as GitHub issues in `EL-BID/Energizados` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at the repo root + `docs/adr/` for ADRs. See `docs/agents/domain.md`.

## Release & Changelog Conventions

This project follows [Keep a Changelog](https://keepachangelog.com/) and
[Semantic Versioning](https://semver.org/). All commit messages must adhere to
the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Commit Message Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

| Type       | Description          | Changelog Section |
|------------|---------------------|--------------------|
| `feat`     | New feature         | **Features**       |
| `fix`      | Bug fix             | **Bug Fixes**      |
| `refactor` | Code restructure    | **Refactoring**    |
| `perf`     | Performance         | **Performance**    |
| `revert`   | Revert commit       | **Reverts**        |
| `docs`     | Documentation       | **Documentation**  |
| `test`     | Tests               | **Testing**        |
| `ci`       | CI changes          | **CI/CD**          |
| `chore`    | Maintenance         | (excluded from CHANGELOG) |
| `build`    | Build system        | (excluded)         |
| `style`    | Formatting          | (excluded)         |

**Examples:**

```bash
# Feature
feat(preprocessing): add enable_last_period_zscore to ConsumptionPatterns

# Bug fix with body
fix(correlation): always keep the feature with higher target correlation

When two features are highly correlated the greedy selector previously
could drop either one arbitrarily. The algorithm now sorts by target
correlation (descending) and greedily keeps non-redundant ones.

Closes #15

# Breaking change
feat(api)!: change model.predict return shape

BREAKING CHANGE: ... migration guide ...
```
