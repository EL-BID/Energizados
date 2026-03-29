# Changelog

## [Unreleased] - 1.0.0

### Core
- Full redesign: Builder pattern, Pydantic validation, modular pipeline steps
- CLI: `init`, `run`, `validate`, `doctor` with wildcard support and custom run naming
- Config files: `etl.yaml`, `train.yaml`, `infer.yaml` and `eda.yaml` 

### ETL
- Multi-ETL orchestration

### Feature Engineering
- Column transformers: cardinality reducer, dummies, target/ordinal encoding, scaler, cast
- Global transformers: tsfel, extra_vars, consumption_patterns, clip_outliers, geo_features
- Feature selection: Boruta, Correlation, Constant, Mutual Information

### Modeling
- Models: LightGBM, CatBoost, Neural Networks, LSTM
- Ensemble: stacking and soft voting
- Rule-based baselines: ChangeTrend, ConstantConsumption
- SMOTETomek sampling, hyperparam search

### Splits
- time_series, stratified, random, group_based, stratified_time

### EDA
- 7-phase interactive HTML report with Plotly
- Population segmentation, outlier detection, related columns analysis

### Evaluation
- AUC, Precision, Recall, F1, SHAP, per-segment metrics, threshold calibration
- HTML/JSON reports, run index, multi-model comparison

### Inference
- Configurable pipeline with auto-loading of feature engineering + models

### Quality
- Improved test coverage
- Pre-commit check rules on commmit
