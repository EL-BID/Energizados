# Changelog

## [Unreleased]

### Breaking Changes

#### CLI Redesign
- **BREAKING**: Removed `--config` option from `run` and `validate` commands. Use positional config names instead.
  - Old: `energizados run --config config/etls.yaml --config config/training.yaml`
  - New: `energizados run etls,training`
- **BREAKING**: Removed `eda` subcommand. EDA now runs via `energizados run eda`
- Added `--config-path/-p` option to specify custom config directory
- Added support for comma-separated config names: `etls,training,inference`

### Feature/Refactor - Complete Framework Redesign

#### Architecture & Core
- **BREAKING**: Extracted Builder pattern from monolithic pipeline implementation
- **BREAKING**: Config schemas now use Pydantic for validation (`core/schemas/`)
- **BREAKING**: New `ConfigPipelineBuilder` orchestrates all pipeline steps
- **BREAKING**: Modularized pipeline steps into `core/steps/` (split, training)

#### CLI Improvements
- **NEW**: `energizados init` command for project creation with complete templates
- **NEW**: `energizados doctor` command for environment validation with UI module
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

---

### Stats (feature/refactor → master)
- 116 commits
- +56,087 / -7,722 lines
- 220 files modified
- ~7,000 lines of new tests
