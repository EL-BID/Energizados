# Changelog

## [Unreleased]

### Added
- Population segmentation analysis in EDA module: Detects multiple distinct populations in numeric distributions
- `PopulationAnalyzer` class in `energizados.eda._population_segmenter`
- Population analysis HTML report section with table showing: Range, Percentile, Row count, Interpretation
- Detected jumps table showing significant distribution breaks (percentile range, value change, ratio)
- Configurable population analysis in `config/eda.yaml`: percentile_step, jump_ratio_threshold, max_populations, min_population_pct
- 28 unit tests for PopulationAnalyzer covering: initialization, detection logic, edge cases, interpretation
- Enhanced outlier analysis in EDA module with multi-method detection (IQR, Z-score, Modified Z-score)
- `OutlierDetector` class in `energizados.eda._outlier_detector`
- New outlier visualization plots: boxplots, heatmaps, consumption anomaly scatter
- Consumption outlier patterns: zero variance, range outliers, mean Z-score
- Configurable outlier thresholds in `config/eda.yaml`
- Notebook template: `notebooks/template_outlier_analysis.ipynb`

### Breaking Changes

#### Config File Renaming
- **BREAKING**: Renamed configuration files from plural to singular:
  - `etls.yaml` → `etl.yaml`
  - `training.yaml` → `train.yaml`
  - `inference.yaml` → `infer.yaml`
- **BREAKING**: Updated CLI config name resolution to match new file names:
  - `etls` → `etl`
  - `training` → `train`
  - `inference` → `infer`
- **Migration guide for existing projects**: Rename files in `config/` directory:
  ```bash
  mv config/etls.yaml config/etl.yaml
  mv config/training.yaml config/train.yaml
  mv config/inference.yaml config/infer.yaml
  ```
- Documentation and examples updated throughout

#### CLI Redesign
- **BREAKING**: Removed `--config` option from `run` and `validate` commands. Use positional config names instead.
  - Old: `energizados run --config config/etls.yaml --config config/training.yaml`
  - New: `energizados run etls,training`
- **BREAKING**: Removed `eda` subcommand. EDA now runs via `energizados run eda`
- Added `--config-path/-p` option to specify custom config directory
- Added support for comma-separated config names: `etl,train,infer`

### Feature/Refactor - Complete Framework Redesign

#### Architecture & Core
- **BREAKING**: Extracted Builder pattern from monolithic pipeline implementation
- **BREAKING**: Config schemas now use Pydantic for validation (`core/schemas/`)
- **BREAKING**: New `ConfigPipelineBuilder` orchestrates all pipeline steps
- **BREAKING**: Modularized pipeline steps into `core/steps/` (split, training)

#### CLI Improvements
- **NEW**: `energizados init` command for project creation with complete templates
- **NEW**: `energizados doctor` command for environment validation with UI module
- **NEW**: `--name` / `-n` option for custom run directory names in `energizados run` (replaces if exists)
- Enhanced CLI messages with Rich formatting and actionable tips
- Fixed `validate.py` bug and improved error messages
- Support for comma-separated config names in `run` command

#### Modeling
- **NEW**: Multi-model ensemble support (stacking and soft voting)
- **NEW**: Model adapters for LightGBM, CatBoost, Neural Networks, and LSTM
- **NEW**: Integrated simple models (ChangeTrend, ConstantConsumption) into pipeline
- **NEW**: Model registry for dynamic model registration
- **NEW**: Multi-model comparison mode for single execution
- Fixed LSTM, neural networks integration into training pipeline

#### ETL Framework
- **NEW**: Multiple ETLs with dependencies support via ETLOrchestrator
- **NEW**: SourceETL supports both concatenation (vertical) and merge (horizontal) modes
- **NEW**: `@etl_name` references for ETL dependencies in config
- **NEW**: Custom class support per ETL
- **BREAKING**: Removed DefaultETL class - each ETL must specify `custom_class`

#### Feature Engineering
- **BREAKING**: Feature engineering now unified under `training.yaml` (no more `feature_pipeline.yaml`)
- **NEW**: Global transformers: `tsfel_vars`, `extra_vars` for time series features
- **NEW**: BaseFeatureEngineering abstract class for custom implementations
- **NEW**: Feature selection pipeline with multiple methods (Boruta, Correlation, Constant, MutualInformation)
- **NEW**: Column resolver for automatic column resolution with configuration
- Column-based preprocessing with transformers: cardinality_reducer, to_dummy, target_encoding, ordinal_encoding, minmax_scaler_row, cast_dtype

#### Split Strategies
- **NEW**: Time series split with date_column and train/val/test periods
- **NEW**: Stratified split for balanced classification
- **NEW**: Random split with seed
- **NEW**: Group-based split (FR-SPLIT-005)

#### EDA Module (Complete Rewrite)
- **NEW**: 7-phase analysis: Loading, Global, Column, Target, Geospatial, Feature Importance, Segmentation
- **NEW**: Interactive Plotly charts as HTML strings
- **NEW**: Self-contained HTML report generation
- **NEW**: RelatedColumnsAnalyzer for hierarchical column relationships (crosstabs, heatmaps, sunburst/sankey)
- **NEW**: Per-column detail charts (histograms, boxplots, treemaps, target rate)
- **BREAKING**: All user-visible strings translated from Spanish to English (i18n)

#### Evaluation
- **NEW**: Comprehensive metrics suite: AUC, precision, recall, F1, confusion matrix, cumulative gains
- **NEW**: Threshold calibration with optimization
- **NEW**: Multi-model comparison in single execution
- **NEW**: HTML and JSON report generation
- **NEW**: Run index at `output/index.html` with table of all training runs
- **NEW**: Comparative evaluation support

#### Inference
- **NEW**: BaseInference and DefaultInference classes
- **NEW**: Automatic loading of feature engineering + model(s)
- **NEW**: Configurable inference pipeline

#### Testing
- **NEW**: Comprehensive test suite (~7,000 lines)
- **NEW**: Unit tests for preprocessing, modeling adapters, inference, evaluation
- **NEW**: Integration tests for end-to-end pipeline
- **NEW**: ETL tests (SourceETL, ETLOrchestrator)
- **NEW**: CLI tests including `test_cli_init.py` (446 lines)
- **NEW**: Model adapter tests (LGBM, CatBoost, LSTM, NN)
- **NEW**: Feature selection pipeline tests
- **NEW**: Comparative evaluator tests

#### Quality & Tooling
- **BREAKING**: Migrated to Poetry for dependency management (pyproject.toml, poetry.lock)
- **NEW**: Pre-commit hooks configured
- **NEW**: Code quality tools: Flake8 (150 char limit), MyPy, Bandit, Black
- **NEW**: MkDocs documentation with complete structure (advanced, user-guide, tutorials)
- **NEW**: Template system for `energizados init` command
- **NEW**: Secure pickle with SHA-256 verification

#### Configuration
- **BREAKING**: 3 YAML files instead of 4: `etls.yaml`, `training.yaml`, `inference.yaml` (removed `feature_pipeline.yaml`)
- **NEW**: Pydantic schemas for config validation
- **NEW**: Sample dataset included in project templates
- **NEW**: Global transformers config section in `training.yaml`

#### Documentation
- **NEW**: Complete MkDocs site with guides, tutorials, and API docs
- **NEW**: Getting started guide (installation, quickstart, first project)
- **NEW**: Advanced guides (architecture, contributing, development setup, extending)
- **NEW**: User guides (CLI reference, configuration, EDA, troubleshooting)
- **NEW**: Tutorials (end-to-end, ensemble models, model selection)
- **NEW**: PRD-01.md (Product Requirements Document)

#### Misc
- **BREAKING**: Renamed `datos/` to `data/` directory
- **NEW**: Logging module instead of print statements
- **NEW**: Secure pickle with SHA-256 verification
- **NEW**: colgrep for code searches
- **NEW**: AGENTS.md file with agent coordination rules
- **NEW**: Skill registry for AI agents (.atl/skill-registry.md)
- Removed compiled files and added pre-commit hooks

### Added
- **SHAP Integration** (FR-EVAL-014): Model explainability via SHAP values
  - `ShapExplainer` class with TreeExplainer (LGBM/CatBoost) and KernelExplainer fallback
  - Summary (beeswarm) and bar (importance) plots in evaluation HTML report
  - Configurable via `evaluation.shap` in train.yaml (enabled, max_samples, top_n_features, plot_types)
  - Dedicated "SHAP Explainability" section in HTML report with top features
  - `get_raw_model()` method on BaseModel ABC for extracting fitted models from adapters
  - New module: `energizados.explainability` with `ShapExplainer`
  - Added `shap>=0.42.0` dependency
- **Per-Segment Evaluation** (FR-EVAL-017): Compute metrics broken down by configurable grouping columns (e.g., zona, tipo_tarifa)
  - AUC, Precision, Recall, F1 per segment value
  - Interactive Plotly chart + heatmap-colored HTML table
  - Configured via `evaluation.segment_columns` in train.yaml
- **SMOTETomek Sampling**: New sampling method combining SMOTE (oversampling) with Tomek links cleaning
  - Added `smotetomek` to `sampling.method` enum in configuration schema
  - Supports threshold parameter for class imbalance handling
  - Available for all ML models: LightGBM, CatBoost, Neural Networks, LSTM

### Fixed
- **Schema Validation Completeness**:
  - Fixed `MODEL_CONFIG_SCHEMA.sampling.method` enum to match actual implementation
  - Corrected method names: `"oversample"` (not `"over"`), removed non-existent `"smote"`
  - Validated sampling methods: `["oversample", "undersample", "smotetomek", "none"]`
  - Added `threshold` property to sampling schema
  - Added `shap` configuration to `TRAINING_SCHEMA.evaluation` section
  - Added comprehensive test suite in `tests/test_config_schemas.py` (7 tests)
  - Updated `train.yaml.tpl` template with SHAP configuration example
  - Updated documentation (architecture.md, train.md, model-selection-guide.md) with correct method names

---

### Stats (feature/refactor → master)
- 116 commits
- +56,087 / -7,722 lines
- 220 files modified
- ~7,000 lines of new tests
