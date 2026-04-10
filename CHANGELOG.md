# Changelog

## [Unreleased] - 1.0.0

### Core
- Full redesign: Builder pattern, Pydantic validation, modular pipeline steps
- CLI: `init`, `run`, `validate`, `eda` commands with wildcard support and custom run naming (`-n`)
- Config files: `etl.yaml`, `train.yaml`, `infer.yaml`, `eda.yaml` — three separate files, each evolving independently
- Schema versioning: each config section carries `schema_version`; the CLI blocks execution if the project schema is newer than the installed framework
- Run scripts in `src/run/` for direct execution without CLI (`ConfigPipelineBuilder` API)

### ETL
- Multi-ETL orchestration with DAG dependency resolution (topological sort)
- `@etl_name` reference syntax to wire ETL outputs as inputs
- **`SourceETL`** with three processing modes:
  - `concat` — vertical concatenation of multiple files
  - `merge` — horizontal join via `merge_config` (any `pd.merge()` parameter)
  - `incremental` — record-level filtering by datetime/numeric key with high-water mark persistence
- **Incremental mode** (introduced in this branch):
  - `incremental_key` — column used to detect new records
  - `incremental_partition` — strftime format for output partition directories (default `"%Y-%m"` → `partition=2024-01/`)
  - `incremental_format` — optional explicit strftime for parsing ambiguous date formats (e.g. `"%d/%m/%Y"`)
  - `reprocess` — re-read all files ignoring the processed-file list
  - `write_mode` — `"append"` (default) or `"replace"` for existing partitions
  - `state_file` — JSON file persisting high-water mark and processed-file list across runs
  - File-by-file processing for constant memory usage
  - `partition_by` deprecated in incremental mode — emits warning if used; use `incremental_partition` instead
- `input_params` / `output_params` — extra kwargs passed to `pd.read_*` / `df.to_*`
- `transform_fn` — custom transform applied post-read (dotted path or callable)
- `sample` — random N-row subsample for fast iteration
- **`GeoFeaturesETL`** — KMeans clusters + IBGE administrative hierarchy + haversine distances from lat/lon
- **`ClipOutliersETL`** — clips extreme numeric values (data reading errors) before feature engineering
- **`CleanFilesETL`** — removes intermediate outputs after pipeline completes; supports `@etl_name` refs and globs

### Feature Engineering
- Column transformers: cardinality reducer, dummies, target/ordinal encoding, MinMax scaler, cast dtype
- Global transformers: `tsfel_vars`, `extra_vars`, `consumption_patterns`, `clip_outliers`, `geo_features`
- Feature selection: Boruta, Correlation, Constant
- `feature_engineering` moved inside `train.yaml` (no separate `feature_pipeline.yaml`)

### Modeling
- Models: LightGBM, CatBoost, **XGBoost** (optional dep: `pip install energizados[xgboost]`), Neural Networks, LSTM
- Unsupervised: **IsolationForest** (trains without labels; uses `contamination` param)
- Rule-based baselines: `simple_trend` (ChangeTrend), `simple_constant` (ConstantConsumption)
- Ensemble: stacking (OOF or blending) and soft voting via `EnsembleModel`
- Sampling: `undersample`, `oversample`, `none` per-model
- Hyperparameter search: `RandomizedSearchCV` with configurable `n_iter` and `cv`

### Splits
- `time_series`, `stratified`, `random`, `group_based`, `stratified_time` (requires `geo_cluster` from GeoFeaturesETL)

### EDA
- 7-phase interactive HTML report (Plotly + Matplotlib)
- Phase 5: IV, KS, Cramér's V feature importance ranking
- Phase 6: population segmentation and drift analysis
- Phase 7: configurable hierarchical column relationships (`RelatedColumnsAnalyzer`)

### Evaluation
- Metrics: AUC, Precision, Recall, F1, confusion matrix, cumulative gains
- HTML + JSON reports per training run
- Per-run index (`output/index.html`) for multi-experiment comparison
- Threshold calibration

### Inference
- Configurable pipeline with auto-loading of feature engineering + model artifacts
- `columns_filter` with comparison operators for record-level filtering
- Enriched output with original columns alongside predictions

### Quality
- Comprehensive test suite: `test_source_etl.py`, `test_etl_orchestrator.py`, `test_cli_init.py`, `test_default_inference.py`
- Pre-commit hooks (black, flake8, mypy, bandit)
- Secure pickle: SHA-256 verified load/save for model artifacts
