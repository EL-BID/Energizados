# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **GeoFeaturesETL: `include_cluster` parameter** — new `include_cluster: false` option to skip KMeans geographic clustering (`geo_cluster` column) while still generating IBGE hierarchy and distance features; useful when `stratified_time` split is not needed
- **Split: Unlabeled negatives injection** (`split.unlabeled_negatives`) — load external unlabeled contracts as `target=0` samples into train split; supports `time_series` date filtering, ID dedup against val/test, `max_per_cutoff` sampling, and NaN fill for missing columns
- **Split: Geo-stratified sampling** (`split.geo_stratify`) — balance geographic representation in train set with three strategies: `proportional` (cap to median), `equal` (reduce to min), `capped` (cap at `max_per_stratum`); logs WARNING if >50% data loss; metadata persisted in `split_metadata.json`
- **Evaluation: Segment thresholds export** — export per-segment optimal thresholds as `segment_thresholds_{column}.json` during evaluation (for each column in `segmented_evaluation.by`); JSON includes `threshold_mode`, `default_threshold`, and per-segment `threshold`/`auc`/`n_samples`
- **Inference: Per-segment thresholds** (`inference.segment_thresholds`) — load `segment_thresholds.json` and apply per-row thresholds based on segment column; `fallback_threshold` for unknown segments; `ValueError` raised if segment column missing from inference data
- **Evaluation: `threshold_mode="segment"` alias** — friendly alias for `"youden"` in segmented metrics; resolved before the loop to avoid parameter mutation
- **Skill: `version-deliverable`** — generate per-version deliverable documents with experiment summary and model comparison

### Fixed

- **Evaluation: `segment` alias mutation bug** — `threshold_mode="segment"` no longer mutates the parameter inside the loop, preventing incorrect "Unknown threshold_mode" warnings and wrong export values
- **Preprocessing: `GroupRelativeConsumption` dtype** — explicit `.astype(float)` before `.fillna(0.0)` prevents TypeError on mixed-type group columns
- **ETL: Upstream output validation** — orchestrator no longer raises "input file does not exist" for paths that are the declared output of an upstream ETL in the DAG

### Refactoring

- Remove release automation components (commitlint, husky, git-cliff scripts, GitHub Actions workflow)

## [0.2.6] - 2026-04-25

### CI/CD

- Opt into Node.js 24 for GitHub Actions (#10)
- **workflows:** Upgrade actions/checkout and actions/setup-python to v6 (#11)

## [0.2.2] - 2026-04-15

### Fixed
- `doctor` command now uses `importlib.metadata` for reliable package version detection instead of unreliable module-level attributes
- Added `jsonschema` dependency for config validation

## [0.2.1] - 2026-04-15

### Changed
- Updated license to new IDB template with AI_BID disclaimer

## [0.2.0] - 2026-04-15

### Core
- Full redesign: Builder pattern, Pydantic validation, modular pipeline steps
- CLI: `init`, `run`, `validate`, `eda` commands with wildcard support and custom run naming (`-n`)
- Config files: `etl.yaml`, `train.yaml`, `infer.yaml`, `eda.yaml` — three separate files, each evolving independently
- Schema versioning: each config section carries `schema_version`; the CLI blocks execution if the project schema is newer than the installed framework
- Run scripts in `src/run/` for direct execution without CLI (`ConfigPipelineBuilder` API)

### ETL
- Multi-ETL orchestration with DAG dependency resolution (topological sort)

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
- 
### Inference
- Configurable pipeline with auto-loading of feature engineering + model artifacts
- `columns_filter` with comparison operators for record-level filtering
- Enriched output with original columns alongside predictions

### Quality
- Comprehensive test suite: `test_source_etl.py`, `test_etl_orchestrator.py`, `test_cli_init.py`, `test_default_inference.py`
- Pre-commit hooks (black, flake8, mypy, bandit)
- Secure pickle: SHA-256 verified load/save for model artifacts


## [0.1.0] - 2024-01-01

Initial notebook-based research framework published by the IDB ([EL-BID/Energizados](https://github.com/EL-BID/Energizados)).

### Added
- Jupyter notebooks for local and Google Colab execution
- Rule-based models: consumption drop detection (`ChangeTrend`), constant consumption detection (`ConstantConsumption`)
- Supervised models: LightGBM, feedforward Neural Network, LSTM+Dense hybrid
- Preprocessing: TSFEL time-series feature extraction, statistical vars, categorical encoding (dummy, cardinality reducer, target encoding), row-wise MinMax scaling
- Feature selection: constant removal, correlation-based, Boruta
- Imbalanced-class handling: random oversampling and undersampling
- Hyperparameter optimization via Random Search
- Evaluation: AUC-ROC metric
- Anonymized sample dataset (42,500 records, 19 columns, 5.8 % fraud rate)
