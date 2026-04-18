# Changelog

## [Unreleased]

## [0.2.3] - 2026-04-18

### Added
- `GeoFeaturesETL`: `regions_file` param — assign `geo_regiao` from a `REGION;CITY` CSV/Parquet (accent/case-insensitive matching, logs matched/unmatched municipalities)
- `GeoFeaturesETL`: `region_cities` param — assign `geo_regiao` as nearest city from a `REFERENCE_CITIES` subset
- `GeoFeaturesETL`: `include_hierarchy` now accepts a list of level names (`"estado"`, `"municipio"`, `"regiao"`)
- 9 new Santa Catarina reference cities

### Fixed
- EDA: `string` and `CategoricalDtype` columns now correctly classified as categorical
- EDA report: numeric stats render with 4 decimal places; `None`/`NaN` shown as `—`

## [0.2.2] - 2026-04-15

### Fixed
- `doctor` command now uses `importlib.metadata` for reliable package version detection instead of unreliable module-level attributes
- Added `jsonschema` dependency for config validation

## [0.2.1] - 2026-04-15

### Changed
- Updated license to new IDB template with AI_BID disclaimer

## [0.2.0] - 2026-04-15

Full framework redesign.

- **CLI**: `init`, `run`, `validate`, `eda` — wildcard support, custom run names (`-n`)
- **Config**: three independent YAML files (`etl.yaml`, `train.yaml`, `infer.yaml`) with per-section `schema_version`
- **ETL**: multi-ETL DAG with dependency resolution; `SourceETL` (concat/merge/incremental), `GeoFeaturesETL`, `ClipOutliersETL`, `CleanFilesETL`
- **Feature engineering**: column + global transformers (`tsfel_vars`, `extra_vars`, `consumption_patterns`, `clip_outliers`); Boruta/Correlation/Constant selection — all inside `train.yaml`
- **Models**: LightGBM, CatBoost, XGBoost, Neural Network, LSTM; ensemble (stacking/soft voting); rule-based baselines
- **Splits**: `time_series`, `stratified`, `random`, `group_based`, `stratified_time`
- **EDA**: 7-phase interactive HTML report with IV/KS/Cramér's V, segmentation, and hierarchical column analysis
- **Evaluation**: AUC, Precision, Recall, F1, confusion matrix, cumulative gains; HTML + JSON reports; per-run index
- **Inference**: auto-loads feature engineering + model artifacts; `columns_filter` support
- **Quality**: pre-commit hooks, SHA-256 verified pickle, comprehensive test suite


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
