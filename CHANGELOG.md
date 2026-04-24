# Changelog

## [Unreleased]

## [0.2.3] - 2026-04-23

### Added
- `GeoFeaturesETL`: `include_hierarchy` now accepts a list of level names (`"estado"`, `"municipio"`, `"regiao"`)
- `TemporalFeatures`: new transformer for calendar features from a date column — flat (`month=7`) and/or cyclic (`month_sin/cos`) encoding
- `ExtraVars`: `count_nulls` param (default `False`) — adds `cant_null_N` column with count of NaN values per row across the `N` consumption periods
- `ConsumptionPatterns`: `enable_last_period_zscore` param (default `False`) — adds `zscore_last_vs_history_N`: z-score of the last month vs the client's own history mean/std; 0.0 when std==0
- `ConsumptionPatterns`: `enable_autocorr_lag1` param (default `False`) — adds `autocorr_lag1_N`: lag-1 autocorrelation; low values signal irregular/manipulated consumption; 0.0 for constant series
- `ConsumptionPatterns`: `enable_seasonal_ratio` + `date_column` params (both default off/`None`) — adds `seasonal_ratio_N`: mean summer consumption / mean winter consumption (southern hemisphere — summer Dec–Feb, winter Jun–Aug); silently skipped if `date_column` is absent or not in the dataset
- `CATModel`: `class_weight="balanced"` now resolved at fit time from label distribution (previously it was passed raw to CatBoost, which does not accept the string shorthand)

### Fixed
- EDA: `string` and `CategoricalDtype` columns now correctly classified as categorical
- EDA report: numeric stats render with 4 decimal places; `None`/`NaN` shown as `—`
- `ConsumptionPatterns.seasonal_ratio`: safe division when winter mean is zero or a season has no mapped months
- `CorrelationSelector`: algorithm rewritten — now sorts features by target correlation (descending) and greedily keeps non-redundant ones; previously could drop the feature with higher target correlation instead of the weaker one
- `ConstantSelector`: crash on all-NaN columns (`value_counts()` empty → `IndexError`); now treated as 100 % constant and dropped
- `IsolationForestScore`: all-NaN training columns produced `NaN` medians; now logs a warning and fills with `0.0`; `transform()` also has a final `fillna(0.0)` guard for unseen all-NaN columns
- `MinMaxScalerRow`: constant rows (min == max) produced `NaN` output due to 0/0 division; now fills with the midpoint of `feature_range`
- `ConsumptionPatterns`: `fit()` now stores global z-score statistics from training data (`_zscore_mean_global`, `_zscore_std_global`); `transform()` uses them to prevent data leakage on val/test sets; falls back to current-batch stats with a warning if `fit()` was skipped

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
