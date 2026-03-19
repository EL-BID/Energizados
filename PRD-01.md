# PRD-01: Energizados Framework

## Product Requirements Document

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| **Title**   | Energizados -- ML Framework for Non-Technical Loss Detection |
| **Version** | 1.4 (Draft)                                                                                           |
| **Date**    | 2026-03-16                                                                                            |
| **Status**  | Draft v1.5 -- Added CLI error messages with tips, fixed validate.py bug, JSON Schema integration       |
| **Authors** | BID (Inter-American Development Bank) Engineering            |
| **License** | MIT                                                          |
| **Python**  | >= 3.10                                                      |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision & Goals](#2-product-vision--goals)
3. [Target Users & Personas](#3-target-users--personas)
4. [Problem Statement](#4-problem-statement)
5. [Product Overview](#5-product-overview)
6. [Functional Requirements](#6-functional-requirements)
    - [FR-CLI: CLI & Project Scaffolding](#fr-cli-cli--project-scaffolding)
    - [FR-ETL: ETL Pipeline & DAG Orchestration](#fr-etl-etl-pipeline--dag-orchestration)
    - [FR-SPLIT: Data Splitting Strategies](#fr-split-data-splitting-strategies)
    - [FR-PREPROCESS: Transformers & Preprocessing](#fr-preprocess-transformers--preprocessing)
    - [FR-FEATSEL: Feature Selection](#fr-featsel-feature-selection)
    - [FR-TRAINING: Model Training](#fr-training-model-training)
    - [FR-ENSEMBLE: Ensemble Methods](#fr-ensemble-ensemble-methods)
    - [FR-EVAL: Evaluation & Reporting](#fr-eval-evaluation--reporting)
    - [FR-INFERENCE: Prediction Pipeline](#fr-inference-prediction-pipeline)
    - [FR-EDA: Exploratory Data Analysis](#fr-eda-exploratory-data-analysis)
    - [FR-CONFIG: YAML Configuration System](#fr-config-yaml-configuration-system)
    - [FR-OUTPUT: Output Structure & Run Management](#fr-output-output-structure--run-management)
    - [FR-SECURITY: Security](#fr-security-security)
    - [FR-FIELDVAL: Field Validation & Pilot-Control](#fr-fieldval-field-validation--pilot-control)
7. [User Stories — Functional Requirements (Detailed)](#7-user-stories--functional-requirements-detailed)
    - [US-CLI: CLI & Project Scaffolding](#us-cli-cli--project-scaffolding)
    - [US-ETL: ETL Pipeline & DAG Orchestration](#us-etl-etl-pipeline--dag-orchestration)
    - [US-SPLIT: Data Splitting Strategies](#us-split-data-splitting-strategies)
    - [US-PREPROCESS: Transformers & Preprocessing](#us-preprocess-transformers--preprocessing)
    - [US-FEATSEL: Feature Selection](#us-featsel-feature-selection)
    - [US-TRAINING: Model Training](#us-training-model-training)
    - [US-ENSEMBLE: Ensemble Methods](#us-ensemble-ensemble-methods)
    - [US-EVAL: Evaluation & Reporting](#us-eval-evaluation--reporting)
    - [US-INFERENCE: Prediction Pipeline](#us-inference-prediction-pipeline)
    - [US-EDA: Exploratory Data Analysis](#us-eda-exploratory-data-analysis)
    - [US-CONFIG: YAML Configuration System](#us-config-yaml-configuration-system)
    - [US-OUTPUT: Output Structure & Run Management](#us-output-output-structure--run-management)
    - [US-SECURITY: Security](#us-security-security)
    - [US-FIELDVAL: Field Validation & Pilot-Control](#us-fieldval-field-validation--pilot-control)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Data Requirements](#9-data-requirements)
10. [Technical Architecture](#10-technical-architecture)
11. [Configuration Reference](#11-configuration-reference)
12. [Supported Models](#12-supported-models)
13. [Current Limitations & Known Issues](#13-current-limitations--known-issues)
14. [Future Roadmap](#14-future-roadmap)
15. [Dependencies](#15-dependencies)
16. [Testing Strategy](#16-testing-strategy)
17. [Glossary](#17-glossary)

---

## 1. Executive Summary

**Energizados** is an open-source machine learning framework developed under the Inter-American Development Bank (BID)
initiative, purpose-built for detecting **non-technical losses (NTL)** -- commonly electricity theft -- in energy
distribution systems.

The framework provides a complete, opinionated ML pipeline from raw data ingestion through model training, evaluation,
and inference. It abstracts the complexity of building fraud detection models behind a YAML-driven configuration system
and a CLI interface, enabling data science teams at energy utilities to produce reproducible, auditable detection models
without writing boilerplate pipeline code.

**Current version:** 0.1.2.dev0 (Alpha)

**Key differentiators:**

- Domain-specific transformers for energy consumption data (time-series features, row-wise normalization)
- DAG-based ETL orchestration for complex multi-source data integration
- Built-in threshold calibration with cost-benefit analysis tuned for field inspection economics
- Reproducible runs with timestamped output directories and global run comparison
- Zero-code pipeline execution via YAML configuration files

---

## 2. Product Vision & Goals

### Vision

Become the standard open-source toolkit for non-technical loss detection across Latin American and Caribbean energy
utilities, reducing commercial losses that cost the region an estimated USD 10+ billion annually.

### Key Objectives

| ID    | Objective                                                  | Horizon     |
|-------|------------------------------------------------------------|-------------|
| OBJ-1 | Provide a production-ready ML pipeline for NTL detection   | Short-term  |
| OBJ-2 | Enable non-ML-expert analysts to train and deploy models   | Short-term  |
| OBJ-3 | Support reproducibility and auditability of model results  | Short-term  |
| OBJ-4 | Reduce time-to-model from weeks to hours for new utilities | Medium-term |
| OBJ-5 | Integrate explainability (SHAP) for regulatory compliance  | Medium-term |
| OBJ-6 | Support experiment tracking and model versioning           | Medium-term |
| OBJ-7 | Enable data drift detection for production monitoring      | Long-term   |

---

## 3. Target Users & Personas

### Persona 1: Utility Data Scientist

- **Role:** Data scientist at an energy distribution company
- **Goals:** Build, evaluate, and iterate on NTL detection models
- **Pain points:** Repetitive pipeline code, inconsistent evaluation, no standard tooling
- **Usage:** Full pipeline -- ETL through evaluation. Writes custom transformers, tunes models
- **Technical level:** High (Python, ML, pandas)

### Persona 2: Utility Data Analyst

- **Role:** Analyst in the commercial losses department
- **Goals:** Run pre-configured models, interpret results, generate reports for field teams
- **Pain points:** Needs results without deep ML knowledge, must justify inspection targets
- **Usage:** CLI commands with pre-built configs. Consumes reports and EDA outputs
- **Technical level:** Medium (basic Python, comfortable with YAML)

### Persona 3: BID Technical Advisor

- **Role:** Consultant deploying the framework across multiple utilities
- **Goals:** Standardize NTL detection methodology, compare results across deployments
- **Pain points:** Each utility has different data formats, needs reproducible benchmarks
- **Usage:** Configures ETL for new data sources, runs comparative evaluations
- **Technical level:** High

### Persona 4: ML Engineer / DevOps

- **Role:** Responsible for productionizing models
- **Goals:** Deploy trained models, automate retraining, monitor performance
- **Pain points:** Pickle security, no MLflow integration, no drift detection
- **Usage:** Inference pipeline, model export, integration with production systems
- **Technical level:** High

---

## 4. Problem Statement

### The Non-Technical Losses Problem

Non-technical losses (NTL) in electricity distribution -- primarily theft, meter fraud, and billing irregularities --
represent a significant economic drain on utilities, particularly in Latin America and the Caribbean. These losses:

- Account for **15-40%** of total electricity distributed in some regions
- Cost utilities billions in unrealized revenue annually
- Disproportionately affect developing economies
- Are difficult to detect through manual inspection alone (millions of customers, limited field crews)

### Current Detection Challenges

1. **Data complexity:** Consumption data is time-series, multi-source, and noisy
2. **Class imbalance:** Fraud cases are rare (typically 1-10% of customers)
3. **Feature engineering:** Domain-specific features (consumption patterns, geographic clustering) require specialized
   knowledge
4. **Operational constraints:** Field inspection capacity is limited; false positives waste scarce resources
5. **Reproducibility:** Ad-hoc scripts produce inconsistent, non-auditable results
6. **Tooling gap:** No standard framework exists for this specific domain

### How Energizados Addresses This

Energizados provides an end-to-end, domain-aware ML pipeline that encapsulates best practices for NTL detection, from
data ingestion through operationally-calibrated predictions, reducing the barrier to entry and ensuring reproducibility.

---

## 5. Product Overview

### High-Level Architecture

```
                         +------------------+
                          |   YAML Configs   |
                          | etl / train      |
                          | infer / eda      |
                         +--------+---------+
                                  |
                         +--------v---------+
                         |    CLI Layer     |
                         | init|run|validate|
                         | eda | doctor     |
                         +--------+---------+
                                  |
              +-------------------+-------------------+
              |                                       |
     +--------v---------+                    +--------v---------+
     |   EDA Pipeline   |                    | Training Pipeline|
     | (standalone)     |                    |                  |
     +------------------+                    +--------+---------+
                                                      |
         +----------+---------+-----------+-----------+----------+
         |          |         |           |           |          |
    +----v---+ +----v---+ +--v-----+ +---v----+ +---v----+ +---v------+
    |  ETL   | | Split  | |Feature | |Feature | | Model  | |Evaluation|
    |  DAG   | |Strategy| |Engineer| |Select  | |Training| |& Reports |
    +--------+ +--------+ +--------+ +--------+ +--------+ +----------+
         |                                            |
         |                                   +--------v---------+
         |                                   |    Inference     |
         |                                   | (secure pickle)  |
         +-----------------------------------+------------------+
                                                      |
                                             +--------v---------+
                                             |     Output       |
                                             | Timestamped runs |
                                             | HTML / JSON / CSV|
                                             +------------------+
```

### Key Capabilities

| Capability            | Description                                                    |
|-----------------------|----------------------------------------------------------------|
| DAG-based ETL         | Multi-source data ingestion with dependency resolution         |
| Domain transformers   | Energy-specific feature engineering (time-series, row scaling) |
| Multi-model support   | LightGBM, CatBoost, Neural Nets, LSTM, rule-based baselines    |
| Ensemble methods      | Soft voting and stacking with meta-learner                     |
| Threshold calibration | Cost-benefit, operational, and precision-recall strategies     |
| Automated EDA         | 8-phase analysis with alert system and HTML reports            |
| Reproducible runs     | Timestamped output, config snapshots, global run index         |
| CLI-first             | Zero-code execution via YAML configuration                     |
| Extensible            | ABC-based design for custom models, transformers, selectors    |

---

## 6. Functional Requirements

### FR-CLI: CLI & Project Scaffolding

| ID         | Requirement                                                                | Status        |
|------------|----------------------------------------------------------------------------|---------------|
| FR-CLI-001 | `energizados init` creates a new project with standard directory structure | [IMPLEMENTED] |
| FR-CLI-002 | `energizados run` executes a training or inference pipeline from config    | [IMPLEMENTED] |
| FR-CLI-003 | `energizados validate` checks YAML config files for correctness            | [IMPLEMENTED] |
| FR-CLI-004 | `energizados run eda` runs exploratory data analysis on a dataset          | [IMPLEMENTED] |
| FR-CLI-005 | `energizados doctor` checks environment (dependencies, versions, GPU)      | [IMPLEMENTED] |
| FR-CLI-006 | CLI uses Click framework with Rich console output for formatting           | [IMPLEMENTED] |
| FR-CLI-007 | CLI provides meaningful error messages with suggested fixes                | [IMPLEMENTED] |
| FR-CLI-008 | CLI supports `--verbose` / `--debug` flags for log level control           | [IMPLEMENTED] |

### FR-ETL: ETL Pipeline & DAG Orchestration

| ID         | Requirement                                                                                 | Status        |
|------------|---------------------------------------------------------------------------------------------|---------------|
| FR-ETL-001 | Support multiple data sources per pipeline (CSV, Parquet via pandas/pyarrow)                | [IMPLEMENTED] |
| FR-ETL-002 | ETLOrchestrator resolves dependencies between ETL steps via topological sort (DAG)          | [IMPLEMENTED] |
| FR-ETL-003 | SourceETL supports `concat` operation (vertical stacking of datasets)                       | [IMPLEMENTED] |
| FR-ETL-004 | SourceETL supports `merge` operation (horizontal join with configurable join type and keys) | [IMPLEMENTED] |
| FR-ETL-005 | BaseETL abstract class defines extract/transform/load/run interface                         | [IMPLEMENTED] |
| FR-ETL-006 | ETL steps declare their dependencies for DAG resolution                                     | [IMPLEMENTED] |
| FR-ETL-007 | ETL supports column selection, renaming, and type casting at load time                      | [IMPLEMENTED] |
| FR-ETL-008 | ETL validates that all declared dependencies exist before execution                         | [IMPLEMENTED] |
| FR-ETL-009 | ETL supports custom transform functions per step                                            | [IMPLEMENTED] |
| FR-ETL-010 | ETL supports incremental / delta loading                                                    | [PLANNED]     |

### FR-SPLIT: Data Splitting Strategies

| ID           | Requirement                                                              | Status        |
|--------------|--------------------------------------------------------------------------|---------------|
| FR-SPLIT-001 | Support stratified train/test split preserving target class distribution | [IMPLEMENTED] |
| FR-SPLIT-002 | Support configurable test size ratio                                     | [IMPLEMENTED] |
| FR-SPLIT-003 | Support random seed for reproducibility                                  | [IMPLEMENTED] |
| FR-SPLIT-004 | Support temporal split (time-based train/test boundary)                  | [IMPLEMENTED]  |
| FR-SPLIT-005 | Support group-based split (e.g., by customer ID to prevent leakage)      | [IMPLEMENTED] |
| FR-SPLIT-006 | Split step passes train/test DataFrames through pipeline context         | [IMPLEMENTED] |

### FR-PREPROCESS: Transformers & Preprocessing

| ID                | Requirement                                                                                    | Status        |
|-------------------|------------------------------------------------------------------------------------------------|---------------|
| FR-PREPROCESS-001 | **ToDummy**: One-hot encode categorical columns                                                | [IMPLEMENTED] |
| FR-PREPROCESS-002 | **TeEncoder**: Target encoding with smoothing (configurable weight, default w=20)              | [IMPLEMENTED] |
| FR-PREPROCESS-003 | **CardinalityReducer**: Collapse low-frequency categories into "other" (threshold=0.1)         | [IMPLEMENTED] |
| FR-PREPROCESS-004 | **CastDtype**: Cast columns to specified dtype (default float32 for memory optimization)       | [IMPLEMENTED] |
| FR-PREPROCESS-005 | **MinMaxScalerRow**: Row-wise min-max normalization (domain-specific for consumption profiles) | [IMPLEMENTED] |
| FR-PREPROCESS-006 | **TsfelVars**: Time-series feature extraction via tsfel library                                | [IMPLEMENTED] |
| FR-PREPROCESS-007 | **ExtraVars**: Statistical feature generation (mean, std, min, max, etc.)                      | [IMPLEMENTED] |
| FR-PREPROCESS-008 | All transformers follow sklearn-compatible fit/transform interface                             | [IMPLEMENTED] |
| FR-PREPROCESS-009 | Transformers are composable in ColumnTransformer pipelines                                     | [IMPLEMENTED] |
| FR-PREPROCESS-010 | Support custom transformer registration                                                        | [IMPLEMENTED]  |
| FR-PREPROCESS-011 | Transformer parameters configurable via YAML                                                   | [IMPLEMENTED] |
| FR-PREPROCESS-012 | **GroupStatComparison**: Compare individual values against group-level statistics (mean, median) with configurable grouping columns and outlier removal via IQR | [PLANNED] |
| FR-PREPROCESS-013 | **TsfelVars** supports configurable feature domains: statistical, temporal, and spectral (FFT, MFCC, wavelets) | [PLANNED] |

### FR-FEATSEL: Feature Selection

| ID             | Requirement                                                                                             | Status        |
|----------------|---------------------------------------------------------------------------------------------------------|---------------|
| FR-FEATSEL-001 | **BorutaSelector**: Boruta all-relevant feature selection (10 runs, majority vote)                      | [IMPLEMENTED] |
| FR-FEATSEL-002 | **CorrelationSelector**: Remove highly correlated features (Pearson, threshold=0.9)                     | [IMPLEMENTED] |
| FR-FEATSEL-003 | **ConstantSelector**: Remove near-constant features (threshold=0.99 single-value dominance)             | [IMPLEMENTED] |
| FR-FEATSEL-004 | **ColumnResolver**: Flexible column specification with glob, regex, @reference, and !exclusion patterns | [IMPLEMENTED] |
| FR-FEATSEL-005 | Multi-step selection pipeline (chain multiple selectors)                                                | [IMPLEMENTED] |
| FR-FEATSEL-006 | BaseFeatureSelector ABC with fit/transform/fit_transform/get_selected_features                          | [IMPLEMENTED] |
| FR-FEATSEL-007 | Feature selection results logged and persisted for auditability                                         | [IMPLEMENTED] |
| FR-FEATSEL-008 | Support mutual information-based selection                                                              | [IMPLEMENTED]  |
| FR-FEATSEL-009 | **KFoldBorutaSelector**: Cross-validated Boruta that runs selection per fold and keeps features appearing in a configurable majority of folds | [PLANNED] |

### FR-TRAINING: Model Training

| ID              | Requirement                                                  | Status        |
|-----------------|--------------------------------------------------------------|---------------|
| FR-TRAINING-001 | Support LightGBM gradient boosting classifier                | [IMPLEMENTED] |
| FR-TRAINING-002 | Support CatBoost gradient boosting classifier                | [IMPLEMENTED] |
| FR-TRAINING-003 | Support Neural Network classifier (Keras/TensorFlow backend) | [IMPLEMENTED] |
| FR-TRAINING-004 | Support LSTM recurrent network for sequence data             | [IMPLEMENTED] |
| FR-TRAINING-005 | Support SimpleTrend rule-based baseline model                | [IMPLEMENTED] |
| FR-TRAINING-006 | Support SimpleConstant rule-based baseline model             | [IMPLEMENTED] |
| FR-TRAINING-007 | ModelRegistry for adapter discovery and instantiation        | [IMPLEMENTED] |
| FR-TRAINING-008 | BaseModel ABC with fit/predict/predict_proba interface       | [IMPLEMENTED] |
| FR-TRAINING-009 | Model hyperparameters configurable via YAML                  | [IMPLEMENTED] |
| FR-TRAINING-010 | Models serialized via pickle to output directory             | [IMPLEMENTED] |
| FR-TRAINING-011 | Support class weight balancing for imbalanced datasets       | [IMPLEMENTED] |
| FR-TRAINING-012 | Support cross-validation during training                     | [PLANNED]     |
| FR-TRAINING-013 | Support hyperparameter optimization (grid/random/Bayesian)   | [IMPLEMENTED]  |
| FR-TRAINING-014 | All model adapters conform to BaseModel ABC                  | [IMPLEMENTED]  |

### FR-ENSEMBLE: Ensemble Methods

| ID              | Requirement                                                                 | Status        |
|-----------------|-----------------------------------------------------------------------------|---------------|
| FR-ENSEMBLE-001 | **Soft voting**: Average predicted probabilities across models              | [IMPLEMENTED] |
| FR-ENSEMBLE-002 | **Stacking**: Meta-learner (LogisticRegression) over base model predictions | [IMPLEMENTED] |
| FR-ENSEMBLE-003 | EnsembleModel composes multiple trained BaseModel instances                 | [IMPLEMENTED] |
| FR-ENSEMBLE-004 | Configurable model weights for soft voting                                  | [IMPLEMENTED]  |
| FR-ENSEMBLE-005 | Support custom meta-learner selection for stacking                          | [IMPLEMENTED]  |

### FR-EVAL: Evaluation & Reporting

| ID          | Requirement                                                                    | Status        |
|-------------|--------------------------------------------------------------------------------|---------------|
| FR-EVAL-001 | Compute AUC-ROC metric                                                         | [IMPLEMENTED] |
| FR-EVAL-002 | Compute precision, recall, F1-score                                            | [IMPLEMENTED] |
| FR-EVAL-003 | Compute accuracy                                                               | [IMPLEMENTED] |
| FR-EVAL-004 | Generate confusion matrix                                                      | [IMPLEMENTED] |
| FR-EVAL-005 | Compute cumulative gains curve                                                 | [IMPLEMENTED] |
| FR-EVAL-006 | **ThresholdCalibrator** with cost_benefit strategy (optimize inspection ROI)   | [IMPLEMENTED] |
| FR-EVAL-007 | **ThresholdCalibrator** with operational strategy (fixed capacity constraints) | [IMPLEMENTED] |
| FR-EVAL-008 | **ThresholdCalibrator** with precision_recall strategy                         | [IMPLEMENTED] |
| FR-EVAL-009 | Generate static plots via matplotlib/seaborn (ROC, gains, distributions)       | [IMPLEMENTED] |
| FR-EVAL-010 | Generate interactive plots via Plotly                                          | [IMPLEMENTED] |
| FR-EVAL-011 | Generate HTML evaluation report                                                | [IMPLEMENTED] |
| FR-EVAL-012 | Generate JSON metrics report                                                   | [IMPLEMENTED] |
| FR-EVAL-013 | **RunIndexGenerator**: Global index.html comparing all training runs           | [IMPLEMENTED] |
| FR-EVAL-014 | Support SHAP-based feature importance in reports                               | [PLANNED]     |
| FR-EVAL-015 | Support custom metric registration                                             | [PLANNED]     |
| FR-EVAL-016 | **Probability calibration**: adjust raw model scores to reflect true frequencies via isotonic regression or Platt scaling (`CalibratedClassifierCV`), distinct from threshold calibration | [IMPLEMENTED] |
| FR-EVAL-017 | Per-segment evaluation: compute metrics broken down by a configurable grouping column | [PLANNED]     |

### FR-INFERENCE: Prediction Pipeline

| ID               | Requirement                                                              | Status        |
|------------------|--------------------------------------------------------------------------|---------------|
| FR-INFERENCE-001 | Load trained model from pickle file                                      | [IMPLEMENTED] |
| FR-INFERENCE-002 | Apply same feature engineering pipeline as training                      | [IMPLEMENTED] |
| FR-INFERENCE-003 | Generate probability scores for all input records                        | [IMPLEMENTED] |
| FR-INFERENCE-004 | Save predictions to CSV                                                  | [IMPLEMENTED] |
| FR-INFERENCE-005 | BaseInference ABC with predict/predict_proba/load_model/save_predictions | [IMPLEMENTED] |
| FR-INFERENCE-006 | Secure pickle loading with allowlisted classes                           | [IMPLEMENTED] |
| FR-INFERENCE-007 | Support batch inference optimization                                     | [PLANNED]     |
| FR-INFERENCE-008 | Support real-time / single-record inference API                          | [PLANNED]     |

### FR-EDA: Exploratory Data Analysis

| ID         | Requirement                                                                                    | Status        |
|------------|------------------------------------------------------------------------------------------------|---------------|
| FR-EDA-001 | **Phase 0 -- Loading Validation**: Data integrity checks, schema validation                    | [IMPLEMENTED] |
| FR-EDA-002 | **Phase 1 -- Global Stats**: Dataset shape, memory, dtypes, missing values summary             | [IMPLEMENTED] |
| FR-EDA-003 | **Phase 2 -- Column Analysis**: Per-column distributions, outliers, unique values              | [IMPLEMENTED] |
| FR-EDA-004 | **Phase 3 -- Target Analysis**: Target variable distribution, class balance assessment         | [IMPLEMENTED] |
| FR-EDA-005 | **Phase 4 -- Geospatial**: Geographic distribution of records and target                       | [IMPLEMENTED] |
| FR-EDA-006 | **Phase 5 -- Feature Importance**: Information Value (IV), Kolmogorov-Smirnov (KS), Cramer's V | [IMPLEMENTED] |
| FR-EDA-007 | **Phase 6 -- Segmentation**: Cluster-based or rule-based segmentation analysis                 | [IMPLEMENTED] |
| FR-EDA-008 | **Phase 7 -- Related Columns**: Correlation heatmaps, multicollinearity detection              | [IMPLEMENTED] |
| FR-EDA-009 | **Alert system**: Automatic alerts with severity levels (info, warning, critical)              | [IMPLEMENTED] |
| FR-EDA-010 | Generate interactive HTML EDA report                                                           | [IMPLEMENTED] |
| FR-EDA-011 | Generate static plot versions for PDF/print                                                    | [IMPLEMENTED] |
| FR-EDA-012 | BaseExplorer ABC with analyze/get_alerts interface                                             | [IMPLEMENTED] |
| FR-EDA-013 | Configurable phase selection (run subset of phases)                                            | [IMPLEMENTED] |

### FR-CONFIG: YAML Configuration System

| ID            | Requirement                                                    | Status        |
|---------------|----------------------------------------------------------------|---------------|
| FR-CONFIG-001 | Support `etl.yaml` for ETL pipeline definition                  | [IMPLEMENTED] |
| FR-CONFIG-002 | Support `train.yaml` for training pipeline configuration      | [IMPLEMENTED] |
| FR-CONFIG-003 | Support `infer.yaml` for inference pipeline configuration    | [IMPLEMENTED] |
| FR-CONFIG-004 | Support `eda.yaml` for EDA configuration                       | [IMPLEMENTED] |
| FR-CONFIG-005 | `energizados validate` checks config syntax and structure      | [IMPLEMENTED] |
| FR-CONFIG-006 | JSON Schema validation for all YAML config files               | [IMPLEMENTED] |
| FR-CONFIG-007 | Config supports variable interpolation / templating            | [PLANNED]     |
| FR-CONFIG-008 | Config snapshots saved to output directory for reproducibility | [IMPLEMENTED] |

### FR-OUTPUT: Output Structure & Run Management

| ID            | Requirement                                                 | Status        |
|---------------|-------------------------------------------------------------|---------------|
| FR-OUTPUT-001 | Timestamped run directories: `output/train-YYYYMMDD_HHMM/`  | [IMPLEMENTED] |
| FR-OUTPUT-002 | `models/` subdirectory for serialized model artifacts       | [IMPLEMENTED] |
| FR-OUTPUT-003 | `reports/evaluation/` subdirectory for metrics and plots    | [IMPLEMENTED] |
| FR-OUTPUT-004 | `config/` subdirectory with config snapshot                 | [IMPLEMENTED] |
| FR-OUTPUT-005 | Global `index.html` for cross-run comparison                | [IMPLEMENTED] |
| FR-OUTPUT-006 | Run metadata (duration, dataset size, parameters) persisted | [IMPLEMENTED]  |
| FR-OUTPUT-007 | Support custom output directory via config                  | [IMPLEMENTED]  |

### FR-SECURITY: Security

| ID              | Requirement                                                       | Status        |
|-----------------|-------------------------------------------------------------------|---------------|
| FR-SECURITY-001 | Secure pickle loading with allowlisted module/class restrictions  | [IMPLEMENTED] |
| FR-SECURITY-002 | Path validation to prevent directory traversal in file operations | [IMPLEMENTED] |
| FR-SECURITY-003 | Allowlisted imports for deserialization safety                    | [IMPLEMENTED] |
| FR-SECURITY-004 | No secrets or credentials in configuration files                  | [IMPLEMENTED] |
| FR-SECURITY-005 | Bandit static security analysis in pre-commit hooks               | [IMPLEMENTED] |
| FR-SECURITY-006 | Support for signed model artifacts                                | [PLANNED]     |

### FR-FIELDVAL: Field Validation & Pilot-Control

| ID              | Requirement                                                                                                           | Status    |
|-----------------|-----------------------------------------------------------------------------------------------------------------------|-----------|
| FR-FIELDVAL-001 | Pilot-control split: divide scored population into balanced pilot/control groups using iterative randomized matching   | [PLANNED] |
| FR-FIELDVAL-002 | Configurable control variables (categorical and numeric) for pilot-control balance validation                          | [PLANNED] |
| FR-FIELDVAL-003 | Balance metrics: symmetric percentage difference for numeric, PSI-like divergence for categorical variables            | [PLANNED] |
| FR-FIELDVAL-004 | Top-N selection from pilot group based on model score for field inspection targeting                                    | [PLANNED] |
| FR-FIELDVAL-005 | Post-inspection result comparison between pilot and control groups to measure model ROI                                | [PLANNED] |

---

## 7. User Stories — Functional Requirements (Detailed)

### US-CLI: CLI & Project Scaffolding

**US-CLI-001: Initialize new project**

- **As** Framework user
- **I want** to execute `energizados init` to create the standard directory structure
- **So that** I have a project ready to configure and execute pipelines
- **Acceptance criteria**:
    - [x] Creates directories: `data/`, `configs/`, `output/`, `models/`
    - [x] Generates example configuration files
    - [x] Shows success message with next steps
- **Status**: [IMPLEMENTED]

**US-CLI-002: Execute pipeline from configuration**

- **As** Framework user
- **I want** to execute `energizados run --config train.yaml` to run the complete pipeline
- **So that** I can train or execute inference without writing code
- **Acceptance criteria**:
    - [x] Loads YAML configuration
    - [x] Executes pipeline: ETL → Split → Preprocess → Feature Selection → Training → Evaluation
    - [x] Shows progress in console
    - [x] Saves results in timestamped directory
- **Status**: [IMPLEMENTED]

**US-CLI-003: Validate configuration files**

- **As** Framework user
- **I want** to execute `energizados validate` to verify YAML syntax
- **So that** I can detect configuration errors before executing the pipeline
- **Acceptance criteria**:
    - [x] Validates YAML syntax
    - [x] Verifies structure against expected schema
    - [x] Shows specific errors with line and fix suggestion
- **Status**: [IMPLEMENTED]

**US-CLI-004: Execute exploratory analysis**

- **As** Framework user
- **I want** to execute `energizados run eda` to analyze a dataset
- **So that** I can understand data distribution before training models
- **Acceptance criteria**:
    - [x] Executes the 8 configured EDA phases
    - [x] Generates interactive HTML report
    - [x] Shows automatic alerts for data problems
- **Status**: [IMPLEMENTED]

**US-CLI-005: Verify environment**

- **As** Framework user
- **I want** to execute `energizados doctor` to verify dependencies
- **So that** I can diagnose environment issues before executing pipelines
- **Acceptance criteria**:
    - [x] Verifies Python version (>= 3.10)
    - [x] Lists installed dependencies and their versions
    - [x] Detects available GPU
    - [x] Shows warnings for outdated versions
- **Status**: [IMPLEMENTED]

**US-CLI-006: Logging control**

- **As** Framework user
- **I want** to use `--verbose` or `--debug` flags to control log level
- **So that** I can see detailed information during development or debugging
- **Acceptance criteria**:
    - [x] `--verbose` shows INFO and above
    - [x] `--debug` shows DEBUG and above
    - [x] Persists level in pipeline context
- **Status**: [IMPLEMENTED]

---

### US-ETL: ETL Pipeline & DAG Orchestration

**US-ETL-001: Load data from multiple sources**

- **As** Data Scientist
- **I want** to define multiple data sources (CSV, Parquet) in the configuration
- **So that** I can integrate data from different systems into a single dataset
- **Acceptance criteria**:
    - [x] Supports CSV and Parquet via pandas/pyarrow
    - [x] Allows selecting specific columns
    - [x] Supports renaming columns
    - [x] Supports forcing data types
- **Status**: [IMPLEMENTED]

**US-ETL-002: Execute merge and concat operations**

- **As** Data Scientist
- **I want** to perform `concat` (vertical stacking) and `merge` (horizontal join) operations
- **So that** I can combine multiple data sources according to business logic
- **Acceptance criteria**:
    - [x] `concat`: stacks datasets with same columns
    - [x] `merge`: joins by keys with configurable join type (left/right/inner/outer)
    - [x] Validates that join keys exist
- **Status**: [IMPLEMENTED]

**US-ETL-003: Resolve dependencies between ETL steps**

- **As** Data Scientist
- **I want** the system to automatically resolve execution order using DAG
- **So that** I don't need to specify manual order and avoid circular dependency errors
- **Acceptance criteria**:
    - [x] Topological sort to resolve dependencies
    - [x] Detects cycles and reports error
    - [x] Validates that all dependencies exist before executing
- **Status**: [IMPLEMENTED]

**US-ETL-004: Custom transformations**

- **As** Data Scientist
- **I want** to define custom transformation functions per ETL step
- **So that** I can apply specific business logic not covered by standard transformations
- **Acceptance criteria**:
    - [x] Allows defining Python function per step
    - [x] Receives DataFrame and returns DataFrame
    - [x] Integrates into DAG flow
- **Status**: [IMPLEMENTED]

**US-ETL-005: Incremental / delta loading**

- **As** Data Scientist
- **I want** to load only new or updated records since the last ETL run
- **So that** I can reduce processing time and resource usage in production environments
- **Acceptance criteria**:
    - [ ] Supports configurable delta key (e.g., timestamp or ID column)
    - [ ] Detects new records since last run
    - [ ] Appends or merges delta into existing processed dataset
- **Status**: [PLANNED]

---

### US-SPLIT: Data Splitting Strategies

**US-SPLIT-001: Stratified split**

- **As** Data Scientist
- **I want** to split data into train/test maintaining class distribution
- **So that** I can avoid skew in training data especially with imbalanced classes
- **Acceptance criteria**:
    - [x] Maintains target proportion in both splits
    - [x] Configurable test_size (default 0.2)
    - [x] Random seed for reproducibility
- **Status**: [IMPLEMENTED]

**US-SPLIT-002: Temporal split**

- **As** Data Scientist
- **I want** to split data by time (train earlier, test later)
- **So that** I can simulate real prediction scenario where we only train with past data
- **Acceptance criteria**:
    - [x] Defines cutoff date (via train_period, val_period, test_period)
    - [x] Train: data before cutoff
    - [x] Test: data after cutoff
- **Status**: [IMPLEMENTED]

**US-SPLIT-003: Group-based split**

- **As** Data Scientist
- **I want** to split by group (e.g., customer_id) to prevent data leakage
- **So that** I can ensure the model doesn't learn patterns from specific customers that appear in both sets
- **Acceptance criteria**:
    - [ ] Specifies group column
    - [ ] Ensures entire group is in train or test, not both
- **Status**: [PLANNED]

---

### US-PREPROCESS: Transformers & Preprocessing

**US-PREPROCESS-001: One-hot encoding**

- **As** Data Scientist
- **I want** to transform categorical columns to dummy variables
- **So that** I can use categorical variables in models that require numeric input
- **Acceptance criteria**:
    - [x] Implements ToDummy transformer
    - [x] sklearn-compatible fit/transform
    - [x] Handles missing values
- **Status**: [IMPLEMENTED]

**US-PREPROCESS-002: Target encoding**

- **As** Data Scientist
- **I want** to perform target encoding with smoothing for categorical columns
- **So that** I can reduce cardinality while maintaining predictive information
- **Acceptance criteria**:
    - [x] Implements TeEncoder
    - [x] Configurable smoothing weight (default w=20)
    - [x] Prevents data leakage with train stats only
- **Status**: [IMPLEMENTED]

**US-PREPROCESS-003: Cardinality reduction**

- **As** Data Scientist
- **I want** to collapse infrequent categories into "other"
- **So that** I can reduce dimensionality and noise in high-cardinality variables
- **Acceptance criteria**:
    - [x] Implements CardinalityReducer
    - [x] Configurable threshold (default 0.1 = 10%)
    - [x] sklearn-compatible
- **Status**: [IMPLEMENTED]

**US-PREPROCESS-004: Row-wise normalization**

- **As** Data Scientist
- **I want** to normalize by row (not by column) for consumption profiles
- **So that** I can capture relative consumption patterns per customer
- **Acceptance criteria**:
    - [x] Implements MinMaxScalerRow
    - [x] Normalizes each row independently
    - [x] Useful for consumption time series
- **Status**: [IMPLEMENTED]

**US-PREPROCESS-005: Time-series feature extraction**

- **As** Data Scientist
- **I want** to extract statistical features from consumption time series
- **So that** I can generate predictive features automatically
- **Acceptance criteria**:
    - [x] Integration with tsfel library
    - [x] Generates: mean, std, min, max, slope, etc.
    - [x] sklearn-compatible
- **Status**: [IMPLEMENTED]

**US-PREPROCESS-006: Custom transformer registration**

- **As** Developer
- **I want** to register custom transformers in the pipeline
- **So that** I can extend functionality without modifying core
- **Acceptance criteria**:
    - [x] ABC BaseFeatureEngineering
    - [x] Dynamic registration via configuration
    - [x] Supports sklearn-compatible custom transformers
- **Status**: [PARTIAL]

**US-PREPROCESS-007: Group-level consumption comparison**

- **As** Data Scientist
- **I want** to compare each record's values against group-level statistics (mean, median) using configurable grouping columns
- **So that** I can detect anomalies relative to peers (e.g., a customer consuming significantly less than others in the same tariff/zone)
- **Acceptance criteria**:
    - [ ] Configurable grouping columns and comparison columns
    - [ ] Group statistics computed with IQR-based outlier removal
    - [ ] Generates ratio and binary flag features (e.g., `below_group_mean`)
    - [ ] sklearn-compatible fit/transform interface
- **Status**: [PLANNED]

**US-PREPROCESS-008: Configurable TSFEL feature domains**

- **As** Data Scientist
- **I want** to configure which tsfel feature domains to extract (statistical, temporal, spectral)
- **So that** I can include spectral features (FFT, MFCC, wavelets) that may improve model performance, or exclude them to reduce dimensionality
- **Acceptance criteria**:
    - [ ] Configurable `domains` parameter: list of `["statistical", "temporal", "spectral"]`
    - [ ] Default: `["statistical", "temporal"]` (current behavior)
    - [ ] Spectral features include FFT coefficients, MFCC, and wavelet features
- **Status**: [PLANNED]

---

### US-FEATSEL: Feature Selection

**US-FEATSEL-001: Boruta feature selection**

- **As** Data Scientist
- **I want** to execute Boruta for relevant feature selection
- **So that** I can identify all features that contribute to predictions
- **Acceptance criteria**:
    - [x] Implements BorutaSelector
    - [x] Configurable n_runs (default 10)
    - [x] Majority vote for final selection
- **Status**: [IMPLEMENTED]

**US-FEATSEL-002: Remove correlated features**

- **As** Data Scientist
- **I want** to remove features with high correlation among themselves
- **So that** I can reduce multicollinearity and improve interpretation
- **Acceptance criteria**:
    - [x] Implements CorrelationSelector
    - [x] Configurable method (pearson) and threshold (0.9)
    - [x] Keeps one of each correlated pair
- **Status**: [IMPLEMENTED]

**US-FEATSEL-003: Remove constant features**

- **As** Data Scientist
- **I want** to remove features with constant or near-constant values
- **So that** I can reduce dimensionality without losing information
- **Acceptance criteria**:
    - [x] Implements ConstantSelector
    - [x] Configurable threshold (default 0.99)
    - [x] Detects single-value dominance
- **Status**: [IMPLEMENTED]

**US-FEATSEL-004: Flexible ColumnResolver**

- **As** Data Scientist
- **I want** to specify columns using patterns (glob, regex, @reference, !exclusion)
- **So that** I can dynamically select column groups
- **Acceptance criteria**:
    - [x] Supports `month_*` (glob)
    - [x] Supports regex patterns
    - [x] Supports @reference and !exclusion
- **Status**: [IMPLEMENTED]

**US-FEATSEL-005: Multi-step selection pipeline**

- **As** Data Scientist
- **I want** to chain multiple feature selectors
- **So that** I can apply selection strategy in multiple stages
- **Acceptance criteria**:
    - [x] Chain of selectors
    - [x] Output of one is input to next
    - [x] Logging of each stage
- **Status**: [IMPLEMENTED]

**US-FEATSEL-006: Feature selection audit log**

- **As** Data Scientist
- **I want** to see which features were selected and which were removed at each selection step
- **So that** I can audit the feature selection process and justify model inputs
- **Acceptance criteria**:
    - [x] Logs selected and rejected features per selector
    - [x] Persists selection results to output directory
    - [x] Includes feature counts before and after each step
- **Status**: [IMPLEMENTED]

**US-FEATSEL-007: Mutual information-based selection**

- **As** Data Scientist
- **I want** to select features based on mutual information with the target variable
- **So that** I have an additional filter complementary to Boruta and correlation methods
- **Acceptance criteria**:
    - [x] Implements MutualInformationSelector
    - [x] Configurable number of top features to keep (k)
    - [x] sklearn-compatible fit/transform interface
    - [x] Supports classification and regression targets
    - [x] Handles non-numeric columns by filtering them out
- **Status**: [IMPLEMENTED]

**US-FEATSEL-008: K-Fold cross-validated Boruta**

- **As** Data Scientist
- **I want** to run Boruta feature selection with k-fold cross-validation
- **So that** feature selection is more robust and less prone to overfitting on a single train split
- **Acceptance criteria**:
    - [ ] Runs Boruta independently on each fold
    - [ ] Selects features appearing in a configurable majority of folds (default ≥ 50%)
    - [ ] Configurable number of folds (default 5)
    - [ ] sklearn-compatible fit/transform interface
- **Status**: [PLANNED]

---

### US-TRAINING: Model Training

**US-TRAINING-001: Train LightGBM**

- **As** Data Scientist
- **I want** to train a LightGBM model configured via YAML
- **So that** I can use high-performance gradient boosting
- **Acceptance criteria**:
    - [x] Implements LGBMAdapter
    - [x] Inherits from BaseModel ABC
    - [x] Serializes to pickle
- **Status**: [IMPLEMENTED]

**US-TRAINING-002: Train CatBoost**

- **As** Data Scientist
- **I want** to train a CatBoost model configured via YAML
- **So that** I can use gradient boosting with native categorical handling
- **Acceptance criteria**:
    - [x] Implements CatBoostAdapter
    - [x] Inherits from BaseModel ABC
    - [x] Serializes to pickle
- **Status**: [IMPLEMENTED]

**US-TRAINING-003: Train Neural Network**

- **As** Data Scientist
- **I want** to train a neural network (MLP) with Keras/TensorFlow
- **So that** I can use deep learning for complex patterns
- **Acceptance criteria**:
    - [x] Implements NNAdapter
    - [x] Backend Keras/TensorFlow
    - [x] GPU support
- **Status**: [IMPLEMENTED]

**US-TRAINING-004: Train LSTM**

- **As** Data Scientist
- **I want** to train an LSTM network for sequential data
- **So that** I can capture temporal patterns in consumption series
- **Acceptance criteria**:
    - [x] Implements LSTMAdapter
    - [x] Input: consumption sequences
    - [x] GPU support
- **Status**: [IMPLEMENTED]

**US-TRAINING-005: Rule-based baseline models**

- **As** Data Scientist
- **I want** to use baseline models (SimpleTrend, SimpleConstant) as reference
- **So that** I can compare against more complex models
- **Acceptance criteria**:
    - [x] SimpleTrend: predicts based on trend
    - [x] SimpleConstant: predicts majority class
    - [x] Useful for benchmark
- **Status**: [IMPLEMENTED]

**US-TRAINING-006: Dynamic model registration**

- **As** Developer
- **I want** to register and discover models dynamically via ModelRegistry
- **So that** I can allow extension without modifying core code
- **Acceptance criteria**:
    - [x] ModelRegistry with lookup by name
    - [x] Supports registration of third-party adapters
    - [x] Instantiation from configuration
- **Status**: [IMPLEMENTED]

**US-TRAINING-007: Class weight balancing**

- **As** Data Scientist
- **I want** to configure class_weight to handle class imbalance
- **So that** I can improve recall for fraud detection (minority class)
- **Acceptance criteria**:
    - [x] Supports `balanced` auto-balance
    - [x] Configurable manual weights
    - [x] Applies in training
- **Status**: [IMPLEMENTED]

**US-TRAINING-008: Cross-validation**

- **As** Data Scientist
- **I want** to execute cross-validation during training
- **So that** I can obtain robust performance estimation
- **Acceptance criteria**:
    - [x] k-fold CV configurable
    - [x] Reports metrics per fold
    - [x] Averages final metrics
- **Status**: [PLANNED]

**US-TRAINING-009: Hyperparameter optimization**

- **As** Data Scientist
- **I want** to run automated hyperparameter search (grid, random, or Bayesian)
- **So that** I can find optimal model parameters without manual tuning
- **Acceptance criteria**:
    - [x] Supports grid search and random search strategies (via hyperparam_search.enabled + method)
    - [x] Supports Bayesian optimization strategy (via method: "bayesian" in schema)
    - [x] Configurable number of iterations and CV folds
    - [x] Best parameters logged and saved with run artifacts
- **Status**: [IMPLEMENTED]

---

### US-ENSEMBLE: Ensemble Methods

**US-ENSEMBLE-001: Soft voting**

- **As** Data Scientist
- **I want** to average probabilities from multiple models
- **So that** I can combine strengths of different algorithms
- **Acceptance criteria**:
    - [x] Average of predict_proba
    - [x] Supports 2+ base models
    - [x] Configurable weights
- **Status**: [IMPLEMENTED]

**US-ENSEMBLE-002: Stacking with meta-learner**

- **As** Data Scientist
- **I want** to train a meta-learner on predictions of base models
- **So that** I can learn optimal combination automatically
- **Acceptance criteria**:
    - [x] Meta-learner LogisticRegression by default
    - [x] Uses predictions as features
    - [x] Two-stage training: base → meta
- **Status**: [IMPLEMENTED]

**US-ENSEMBLE-003: Configurable weights for voting**

- **As** Data Scientist
- **I want** to specify weights for each model in soft voting
- **So that** I can give more importance to better models
- **Acceptance criteria**:
    - [x] List of weights in configuration
    - [x] Normalizes automatically
    - [x] Default: equal weights
- **Status**: [IMPLEMENTED]

**US-ENSEMBLE-004: Custom meta-learner for stacking**

- **As** Data Scientist
- **I want** to specify the meta-learner algorithm used in stacking ensembles
- **So that** I can use classifiers better suited to my data beyond the default LogisticRegression
- **Acceptance criteria**:
    - [x] Supports configurable meta-learner type via YAML (meta_learner.type)
    - [x] Supports at minimum: LogisticRegression, LightGBM, CatBoost (via ModelRegistry)
    - [x] Meta-learner hyperparameters configurable (meta_learner.params)
- **Status**: [IMPLEMENTED]

---

### US-EVAL: Evaluation & Reporting

**US-EVAL-001: Classification metrics**

- **As** Data Scientist
- **I want** to obtain standard metrics: AUC-ROC, Precision, Recall, F1, Accuracy
- **So that** I can evaluate model performance
- **Acceptance criteria**:
    - [x] AUC-ROC
    - [x] Precision, Recall, F1
    - [x] Accuracy
    - [x] Confusion Matrix
- **Status**: [IMPLEMENTED]

**US-EVAL-002: Cumulative gains curve**

- **As** Data Scientist
- **I want** to generate cumulative gains curve
- **So that** I can understand model lift vs random
- **Acceptance criteria**:
    - [x] Calculates gains by percentile
    - [x] Plots gains vs % population
    - [x] Compares with random baseline
- **Status**: [IMPLEMENTED]

**US-EVAL-003: Threshold calibration**

- **As** Utility Analyst
- **I want** to calibrate threshold to optimize field inspection ROI
- **So that** I can maximize fraud detection with limited budget
- **Acceptance criteria**:
    - [x] strategy `cost_benefit`: optimizes inspection_cost vs recovery_value
    - [x] strategy `operational`: fixes inspection capacity
    - [x] strategy `precision_recall`: optimizes F1 or specifies precision/recall
- **Status**: [IMPLEMENTED]

**US-EVAL-004: Visualizations**

- **As** Data Scientist
- **I want** to generate static (matplotlib) and interactive (Plotly) plots
- **So that** I can analyze and present results
- **Acceptance criteria**:
    - [x] ROC curve
    - [x] Precision-Recall curve
    - [x] Confusion matrix heatmap
    - [x] Feature importance
    - [x] Static (PNG) + Interactive (HTML)
- **Status**: [IMPLEMENTED]

**US-EVAL-005: Reports**

- **As** Utility Analyst
- **I want** to generate HTML and JSON evaluation reports
- **So that** I can share results with stakeholders
- **Acceptance criteria**:
    - [x] HTML report with embedded plots
    - [x] JSON with all metrics
    - [x] Metrics per threshold
- **Status**: [IMPLEMENTED]

**US-EVAL-006: Global run index**

- **As** BID Technical Advisor
- **I want** to compare all training runs in index.html
- **So that** I can benchmark between different configurations
- **Acceptance criteria**:
    - [x] Lists all runs in output/
    - [x] Shows key metrics per run
    - [x] Links to detailed reports
- **Status**: [IMPLEMENTED]

**US-EVAL-007: SHAP feature importance**

- **As** Data Scientist
- **I want** to generate SHAP explanations of predictions
- **So that** I can meet regulatory explainability requirements
- **Acceptance criteria**:
    - [x] Calculates SHAP values
    - [x] Summary plot
    - [x] Dependence plots
- **Status**: [PLANNED]

**US-EVAL-008: Custom metric registration**

- **As** Data Scientist
- **I want** to register and use custom evaluation metrics in the pipeline
- **So that** I can evaluate models against domain-specific criteria beyond standard ML metrics
- **Acceptance criteria**:
    - [ ] Supports custom metric function registration
    - [ ] Custom metrics appear in JSON and HTML reports
    - [ ] Metrics conform to a standard interface (y_true, y_pred/y_proba)
- **Status**: [PLANNED]

**US-EVAL-009: Model probability calibration**

- **As** Data Scientist
- **I want** to calibrate model predicted probabilities using isotonic regression or Platt scaling
- **So that** predicted scores reflect actual fraud rates, improving threshold-based operational decisions
- **Acceptance criteria**:
    - [x] Supports isotonic regression and Platt (sigmoid) scaling via `CalibratedClassifierCV`
    - [x] Configurable number of CV folds for calibration (default 5)
    - [x] Calibrated model saved alongside uncalibrated model
    - [ ] Calibration curve (reliability diagram) included in evaluation report
- **Status**: [IMPLEMENTED]

**US-EVAL-010: Per-segment evaluation**

- **As** Data Scientist
- **I want** to compute evaluation metrics broken down by a configurable grouping column (e.g., customer category, zone, tariff type)
- **So that** I can identify segments where the model performs well or poorly and adjust strategies accordingly
- **Acceptance criteria**:
    - [ ] Configurable `segment_column` in evaluation config
    - [ ] Computes AUC, precision, recall, F1 per segment
    - [ ] Segment breakdown included in HTML and JSON reports
    - [ ] Warns when a segment has too few samples for reliable metrics
- **Status**: [PLANNED]

---

### US-INFERENCE: Prediction Pipeline

**US-INFERENCE-001: Load trained model**

- **As** ML Engineer
- **I want** to load a serialized model from pickle
- **So that** I can execute predictions in production
- **Acceptance criteria**:
    - [x] Loads from configured path
    - [x] Applies training feature engineering
    - [x] Supports batch and single record
- **Status**: [IMPLEMENTED]

**US-INFERENCE-002: Generate predictions**

- **As** ML Engineer
- **I want** to obtain probability scores for all input records
- **So that** I can rank customers by fraud likelihood
- **Acceptance criteria**:
    - [x] predict() → predicted class
    - [x] predict_proba() → probabilities
    - [x] CSV output with probabilities
- **Status**: [IMPLEMENTED]

**US-INFERENCE-003: Secure pickle loading**

- **As** ML Engineer
- **I want** to load models with security restrictions
- **So that** I can prevent malicious code execution in untrusted models
- **Acceptance criteria**:
    - [x] Allowlist of allowed classes
    - [x] Blocks malicious __reduce__
    - [x] Logging of warnings
- **Status**: [IMPLEMENTED]

**US-INFERENCE-004: Batch inference optimization**

- **As** ML Engineer
- **I want** to optimize inference for large volumes
- **So that** I can reduce processing time
- **Acceptance criteria**:
    - [x] Chunked processing
    - [x] Parallelization
    - [x] Memory-efficient
- **Status**: [PLANNED]

**US-INFERENCE-005: Real-time inference API**

- **As** ML Engineer
- **I want** to serve predictions via HTTP endpoint
- **So that** I can integrate with operational systems
- **Acceptance criteria**:
    - [x] POST /predict endpoint
    - [x] Single record input
    - [x] Response with probability
- **Status**: [PLANNED]

---

### US-EDA: Exploratory Data Analysis

**US-EDA-001: Data loading validation**

- **As** Data Scientist
- **I want** to execute automatic validation when loading dataset
- **So that** I can detect format problems before analysis
- **Acceptance criteria**:
    - [x] Verifies file integrity
    - [x] Validates expected schema
    - [x] Reports clear errors
- **Status**: [IMPLEMENTED]

**US-EDA-002: Global stats**

- **As** Data Scientist
- **I want** to see global dataset statistics
- **So that** I can understand size, memory, types, missing values
- **Acceptance criteria**:
    - [x] Shape, memory usage
    - [x] Data types distribution
    - [x] Missing values summary
- **Status**: [IMPLEMENTED]

**US-EDA-003: Per-column analysis**

- **As** Data Scientist
- **I want** to analyze distribution of each column
- **So that** I can identify outliers, cardinality, patterns
- **Acceptance criteria**:
    - [x] Histograms for numeric
    - [x] Bar charts for categorical
    - [x] Outlier detection (IQR)
    - [x] Unique values count
- **Status**: [IMPLEMENTED]

**US-EDA-004: Target analysis**

- **As** Data Scientist
- **I want** to analyze target distribution
- **So that** I can evaluate class imbalance
- **Acceptance criteria**:
    - [x] Class distribution
    - [x] Imbalance ratio
    - [x] Handling recommendations
- **Status**: [IMPLEMENTED]

**US-EDA-005: Geospatial analysis**

- **As** Data Scientist
- **I want** to visualize geographic distribution
- **So that** I can identify spatial fraud patterns
- **Acceptance criteria**:
    - [x] Density maps
    - [x] Color by target
    - [x] Optional if lat/lon available
- **Status**: [IMPLEMENTED]

**US-EDA-006: Feature importance (EDA)**

- **As** Data Scientist
- **I want** to calculate IV, KS, Cramer's V
- **So that** I can identify most discriminative features
- **Acceptance criteria**:
    - [x] Information Value for numeric
    - [x] Kolmogorov-Smirnov test
    - [x] Cramer's V for categorical
- **Status**: [IMPLEMENTED]

**US-EDA-007: Correlation analysis**

- **As** Data Scientist
- **I want** to see correlation heatmaps
- **So that** I can detect multicollinearity
- **Acceptance criteria**:
    - [x] Correlation matrix
    - [x] Heatmap visualization
    - [x] Highlights high correlations
- **Estado**: [IMPLEMENTED]

**US-EDA-008: Alert system**

- **As** Data Scientist
- **I want** to receive automatic alerts for data problems
- **So that** I don't miss critical issues during EDA
- **Acceptance criteria**:
    - [x] Alerts: info, warning, critical
    - [x] Detects: missing >50%, extreme imbalance, constants
    - [x] Includes in report
- **Status**: [IMPLEMENTED]

**US-EDA-009: Interactive HTML report**

- **As** Utility Analyst
- **I want** to generate navigable HTML report
- **So that** I can share analysis without needing Python
- **Acceptance criteria**:
    - [x] HTML with interactive Plotly
    - [x] Navigation between phases
    - [x] Exportable
- **Status**: [IMPLEMENTED]

**US-EDA-010: Segmentation analysis**

- **As** Data Scientist
- **I want** to execute cluster-based or rule-based segmentation analysis on the dataset
- **So that** I can identify behavioral segments with different fraud risk profiles
- **Acceptance criteria**:
    - [x] Segments dataset by relevant groupings
    - [x] Computes fraud rate per segment
    - [x] Visualizes segment distributions and target rate differences
- **Status**: [IMPLEMENTED]

**US-EDA-011: Configurable phase selection**

- **As** Data Scientist
- **I want** to specify which EDA phases to run via configuration
- **So that** I can run only the relevant analysis phases and reduce processing time
- **Acceptance criteria**:
    - [x] `phases` list in `eda.yaml` controls which phases execute
    - [x] Skipped phases are logged but not executed
    - [x] Default: all phases run when not specified
- **Status**: [IMPLEMENTED]

---

### US-CONFIG: YAML Configuration System

**US-CONFIG-001: ETL configuration**

- **As** Data Scientist
- **I want** to define ETL pipeline in `etl.yaml`
- **So that** I can specify sources, operations, and dependencies
- **Acceptance criteria**:
    - [x] Declarative syntax
    - [x] Supports concat and merge
    - [x] Dependencies between steps
- **Status**: [IMPLEMENTED]

**US-CONFIG-002: Training configuration**

- **As** Data Scientist
- **I want** to define complete pipeline in `train.yaml`
- **So that** I can configure: split, preprocess, feature selection, model, evaluation
- **Acceptance criteria**:
    - [x] All pipeline sections
    - [x] Parameters per component
    - [x] Reference to ETL output
- **Status**: [IMPLEMENTED]

**US-CONFIG-003: Inference configuration**

- **As** ML Engineer
- **I want** to define inference pipeline in `infer.yaml`
- **So that** I can specify model and features to use
- **Acceptance criteria**:
    - [x] Path to serialized model
    - [x] Path to feature pipeline
    - [x] Output configuration
- **Status**: [IMPLEMENTED]

**US-CONFIG-004: Configuration validation**

- **As** User
- **I want** `energizados validate` to verify my configuration files
- **So that** I can detect errors before executing
- **Acceptance criteria**:
    - [x] Validates YAML syntax
    - [x] Verifies structure
    - [x] Useful error messages
- **Status**: [IMPLEMENTED]

**US-CONFIG-005: JSON Schema validation**

- **As** Developer
- **I want** configs to be validated against JSON Schema
- **So that** I can ensure clear contracts and early errors
- **Acceptance criteria**:
    - [x] Schema for each config type
    - [x] Automatic validation on load
    - [x] Errors with path and expected type
- **Status**: [IMPLEMENTED]

**US-CONFIG-006: Templates/variables in config**

- **As** User
- **I want** to use variables or templates in configs
- **So that** I can avoid repetition and facilitate maintenance
- **Acceptance criteria**:
    - [x] Variable interpolation `${var}`
    - [x] Section reuse
    - [x] Sensible defaults
- **Status**: [PLANNED]

**US-CONFIG-007: EDA configuration**

- **As** Data Scientist
- **I want** to define EDA pipeline parameters in `eda.yaml`
- **So that** I can configure dataset path, target column, phases, and output options declaratively
- **Acceptance criteria**:
    - [x] Supports dataset path and target column
    - [x] Supports phase selection list
    - [x] Supports geospatial column mapping
    - [x] Supports output directory and format options
- **Status**: [IMPLEMENTED]

---

### US-OUTPUT: Output Structure & Run Management

**US-OUTPUT-001: Timestamped directories**

- **As** User
- **I want** each execution to generate a directory with timestamp
- **So that** I can maintain reproducible experiment history
- **Acceptance criteria**:
    - [x] Format: `output/train-YYYYMMDD_HHMMSS/`
    - [x] Unique per execution
    - [x] Clear identification
- **Status**: [IMPLEMENTED]

**US-OUTPUT-002: Directory structure**

- **As** User
- **I want** predictable structure: models/, reports/, config/
- **So that** I know where to find each artifact
- **Acceptance criteria**:
    - [x] `models/` → .pkl
    - [x] `reports/evaluation/` → metrics, plots
    - [x] `config/` → YAML snapshot
- **Status**: [IMPLEMENTED]

**US-OUTPUT-003: Global run index**

- **As** BID Technical Advisor
- **I want** an index.html that lists all runs
- **So that** I can compare experiments easily
- **Acceptance criteria**:
    - [x] Lists all runs
    - [x] Table with key metrics
    - [x] Links to individual reports
- **Status**: [IMPLEMENTED]

**US-OUTPUT-004: Run metadata**

- **As** User
- **I want** run metadata to be persisted
- **So that** I have record of: duration, dataset size, parameters
- **Acceptance criteria**:
    - [x] JSON with metadata
    - [x] Total duration
    - [x] Dataset rows
    - [x] Hyperparameters
- **Status**: [PARTIAL]

**US-OUTPUT-005: Custom output directory**

- **As** User
- **I want** to specify different output directory via config
- **So that** I can organize experiments according to needs
- **Acceptance criteria**:
    - [x] `output.directory` field in config
    - [x] Overrides default
    - [x] Validates that path exists or creates it
- **Status**: [PARTIAL]

---

### US-SECURITY: Security

**US-SECURITY-001: Secure pickle loading**

- **As** ML Engineer
- **I want** to load models only with allowlisted classes
- **So that** I can prevent arbitrary code execution
- **Acceptance criteria**:
    - [x] Allowlist of modules/classes
    - [x] Blocks insecure deserialization
    - [x] Logging of rejected loads
- **Status**: [IMPLEMENTED]

**US-SECURITY-002: Path traversal prevention**

- **As** Developer
- **I want** to validate paths to prevent directory traversal
- **So that** I can avoid unauthorized file access
- **Acceptance criteria**:
    - [x] Validates that paths are within workspace
    - [x] Blocks malicious `../`
    - [x] Sanitizes user inputs
- **Status**: [IMPLEMENTED]

**US-SECURITY-003: No secrets in configs**

- **As** User
- **I want** the system to warn if there are secrets in configs
- **So that** I can avoid accidental credential commits
- **Acceptance criteria**:
    - [x] Detects API keys, passwords patterns
    - [x] Warning on validate
    - [x] Suggests environment variables usage
- **Status**: [IMPLEMENTED]

**US-SECURITY-004: Pre-commit security checks**

- **As** Developer
- **I want** pre-commit to run Bandit
- **So that** I can detect security vulnerabilities
- **Acceptance criteria**:
    - [x] Bandit in pre-commit hook
    - [x] Blocks commit if high issues
    - [x] Findings report
- **Status**: [IMPLEMENTED]

**US-SECURITY-005: Signed model artifacts**

- **As** ML Engineer
- **I want** to sign models with cryptographic signature
- **So that** I can guarantee model integrity in production
- **Acceptance criteria**:
    - [x] Generate signature on save
    - [x] Verify signature on load
    - [x] Reject tampered models
- **Status**: [PLANNED]

---

### US-FIELDVAL: Field Validation & Pilot-Control

**US-FIELDVAL-001: Pilot-control split for field validation**

- **As** BID Technical Advisor
- **I want** to split the scored population into balanced pilot and control groups
- **So that** I can design a randomized controlled trial to prove model ROI against random inspection
- **Acceptance criteria**:
    - [ ] Iterative random splitting (configurable max iterations, default 10,000)
    - [ ] Configurable control variables (categorical and numeric)
    - [ ] Balance validation: symmetric percentage difference for numeric, PSI-like divergence for categorical
    - [ ] Configurable maximum allowed error threshold (default 0.01)
    - [ ] Output: each record tagged as "pilot" or "control"
- **Status**: [PLANNED]

**US-FIELDVAL-002: Top-N inspection targeting**

- **As** Utility Analyst
- **I want** to select the top-N highest-scoring records from the pilot group for field inspection
- **So that** I can prioritize inspections by fraud likelihood within my operational capacity
- **Acceptance criteria**:
    - [ ] Configurable N (number of inspections) or top percentage
    - [ ] Exports inspection list with scores, key features, and consumption history
    - [ ] Supports filtering by geographic zone or segment before selection
- **Status**: [PLANNED]

**US-FIELDVAL-003: Post-inspection ROI evaluation**

- **As** BID Technical Advisor
- **I want** to compare fraud detection rates between pilot (model-driven) and control (random) groups after field inspections
- **So that** I can quantify the model's added value and justify continued investment
- **Acceptance criteria**:
    - [ ] Ingests inspection results (fraud found / not found per record)
    - [ ] Computes detection rate, precision, and lift for pilot vs control
    - [ ] Generates comparison report with statistical significance test
    - [ ] Produces visualizations (bar charts, lift curves) for stakeholder presentations
- **Status**: [PLANNED]

---

## 8. Non-Functional Requirements

| ID      | Category        | Requirement                                                                                     | Status        |
|---------|-----------------|-------------------------------------------------------------------------------------------------|---------------|
| NFR-001 | Performance     | Training pipeline processes datasets up to 1M rows within reasonable time on commodity hardware | [PARTIAL]     |
| NFR-002 | Performance     | EDA report generation completes within 5 minutes for datasets up to 500K rows                   | [IMPLEMENTED] |
| NFR-003 | Performance     | Memory-optimized dtype casting (float32) reduces DataFrame memory footprint                     | [IMPLEMENTED] |
| NFR-004 | Scalability     | Pipeline architecture supports pluggable model adapters without core changes                    | [IMPLEMENTED] |
| NFR-005 | Scalability     | ETL DAG supports arbitrary numbers of data sources and transformations                          | [IMPLEMENTED] |
| NFR-006 | Compatibility   | Python >= 3.10 required                                                                         | [IMPLEMENTED] |
| NFR-007 | Compatibility   | Cross-platform: Linux, macOS, Windows                                                           | [PARTIAL]     |
| NFR-008 | Extensibility   | All core components backed by ABCs for custom implementations                                   | [IMPLEMENTED] |
| NFR-009 | Extensibility   | ModelRegistry allows third-party model adapter registration                                     | [IMPLEMENTED] |
| NFR-010 | Extensibility   | Transformer pipeline supports custom sklearn-compatible transformers                            | [IMPLEMENTED] |
| NFR-011 | Maintainability | Pre-commit hooks enforce code style (isort, black, flake8, bandit, prettier)                    | [IMPLEMENTED] |
| NFR-012 | Maintainability | Strict marker policy for pytest (no unmarked tests)                                             | [IMPLEMENTED] |
| NFR-013 | Reproducibility | All runs produce deterministic results given same seed and data                                 | [IMPLEMENTED] |
| NFR-014 | Reproducibility | Config snapshots and output structure enable full run recreation                                | [IMPLEMENTED] |
| NFR-015 | Observability   | Logging via Python logging module (no print statements)                                         | [IMPLEMENTED] |
| NFR-016 | Observability   | Rich console output for CLI progress and status                                                 | [IMPLEMENTED] |
| NFR-017 | Testing         | Minimum 80% code coverage target                                                                | [PLANNED]     |
| NFR-018 | Testing         | All tests pass in CI before merge                                                               | [PLANNED]     |
| NFR-019 | Documentation   | All public ABCs and core classes have docstrings                                                | [PARTIAL]     |
| NFR-020 | Documentation   | YAML config files are self-documenting with comments                                            | [PARTIAL]     |

---

## 9. Data Requirements

### Input Data

| Aspect          | Specification                                                              |
|-----------------|----------------------------------------------------------------------------|
| **Formats**     | CSV, Parquet (via pandas / pyarrow)                                        |
| **Structure**   | Tabular. Rows = customers or customer-period. Columns = features           |
| **Target**      | Binary classification label (0 = normal, 1 = fraud/NTL)                    |
| **Time series** | Consumption columns representing temporal periods (e.g., monthly readings) |
| **Identifiers** | Customer ID column for deduplication and group-aware operations            |
| **Geographic**  | Optional latitude/longitude or zone identifiers for geospatial EDA         |
| **Encoding**    | UTF-8. Column names cleaned via unidecode                                  |
| **Size**        | Designed for datasets from 10K to 1M+ rows                                 |

### Output Data

| Output             | Format        | Location                             |
|--------------------|---------------|--------------------------------------|
| Trained models     | Pickle (.pkl) | `output/train-*/models/`             |
| Evaluation metrics | JSON          | `output/train-*/reports/evaluation/` |
| Evaluation report  | HTML          | `output/train-*/reports/evaluation/` |
| Evaluation plots   | PNG / HTML    | `output/train-*/reports/evaluation/` |
| Predictions        | CSV           | `output/inference-*/`                |
| EDA report         | HTML          | `output/eda-*/`                      |
| Run index          | HTML          | `output/index.html`                  |
| Config snapshot    | YAML          | `output/train-*/config/`             |

---

## 10. Technical Architecture

### Module Dependency Diagram

```
                            +-------------+
                            |     cli     |
                            +------+------+
                                   |
                    +--------------+--------------+
                    |              |              |
               +----v----+   +----v----+   +----v----+
               |  core   |   |   eda   |   |  etl    |
               +-+--+--+-+   +---------+   +----+----+
                 |  |  |                         |
        +--------+  |  +--------+                |
        |           |           |                |
   +----v------+ +--v-------+ +v-----------+ +--v-----------+
   |  feature  | | feature  | | modeling   | |preprocessing |
   |engineering| | selection| |            | |              |
   +-----------+ +----------+ +-----+------+ +--------------+
                                    |
                              +-----v------+
                              | evaluation |
                              +-----+------+
                                    |
                              +-----v------+
                              | inference  |
                              +------------+
```

### Core Abstractions

| ABC                      | Module                | Methods                                                                     | Purpose                    |
|--------------------------|-----------------------|-----------------------------------------------------------------------------|----------------------------|
| `PipelineStep`           | `core`                | `execute()`, `validate_input()`, `get_required_keys()`, `get_output_keys()` | Pipeline stage contract    |
| `StepBuilder`            | `core/builders`       | `build()`, `is_enabled()`                                                   | Step construction contract |
| `BaseETL`                | `etl`                 | `extract()`, `transform()`, `load()`, `run()`                               | Data ingestion contract    |
| `BaseModel`              | `modeling`            | `fit()`, `predict()`, `predict_proba()`                                     | Model adapter contract     |
| `BaseFeatureEngineering` | `feature_engineering` | `fit()`, `transform()`, `fit_transform()`, `save()`, `load()`               | Feature pipeline contract  |
| `BaseFeatureSelector`    | `feature_selection`   | `fit()`, `transform()`, `fit_transform()`, `get_selected_features()`        | Selection contract         |
| `BaseInference`          | `inference`           | `predict()`, `predict_proba()`, `load_model()`, `save_predictions()`        | Inference contract         |
| `BaseExplorer`           | `eda`                 | `analyze()`, `get_alerts()`                                                 | EDA phase contract         |

### Design Patterns

| Pattern                     | Where Used                                              | Purpose                                      |
|-----------------------------|---------------------------------------------------------|----------------------------------------------|
| **Strategy**                | Model adapters, split strategies, threshold calibrators | Interchangeable algorithms via config        |
| **Adapter**                 | LGBMAdapter, CatBoostAdapter, NNAdapter, LSTMAdapter    | Uniform interface over heterogeneous ML libs |
| **Registry**                | ModelRegistry                                           | Dynamic adapter discovery and instantiation  |
| **Builder**                 | PipelineDirector + StepBuilder (modular)                | Construct pipelines from YAML config         |
| **StepBuilder**             | ETLBuilder, SplitBuilder, TrainingBuilder, etc.         | Modular step construction from config        |
| **Template Method**         | BaseETL, BaseExplorer                                   | Fixed algorithm skeleton, variable steps     |
| **Chain of Responsibility** | Feature selection pipeline                              | Sequential processing with optional steps    |
| **Factory Method**          | Model/transformer creation from config                  | Decouple creation from usage                 |
| **DAG / Topological Sort**  | ETLOrchestrator                                         | Dependency-ordered execution of ETL steps    |
| **Composite**               | EnsembleModel                                           | Treat model collections as single model      |
| **Context-Passing**         | Pipeline execution                                      | Dict-based state propagation between steps   |

### Pipeline Context-Passing Pattern

The pipeline uses a dictionary-based context object passed between steps:

```python
context = {}

# Each PipelineStep:
#   1. Reads required keys from context (declared via get_required_keys())
#   2. Performs computation
#   3. Writes output keys to context (declared via get_output_keys())
#   4. Returns modified context

context = etl_step.execute(context)  # adds 'dataframe'
context = split_step.execute(context)  # adds 'X_train', 'X_test', 'y_train', 'y_test'
context = fe_step.execute(context)  # transforms X_train, X_test
context = training_step.execute(context)  # adds 'model'
context = eval_step.execute(context)  # adds 'metrics', 'reports'
```

---

## 11. Configuration Reference

### etl.yaml

```yaml
etls:
  - name: "main_data"                # Unique ETL step identifier
    type: "source"                   # ETL type
    sources: # One or more data sources
      - path: "data/consumption.csv" # File path (CSV or Parquet)
        format: "csv"                # File format
        columns: # Optional: select specific columns
          - "customer_id"
          - "month_*"
        rename: # Optional: rename columns
          old_name: "new_name"
        dtypes: # Optional: force column types
          customer_id: "str"
    operation: "concat"              # concat | merge
    merge_on: [ "customer_id" ]        # Required for merge
    merge_how: "left"                # left | right | inner | outer
    depends_on: [ ]                   # DAG dependencies (other ETL names)

  - name: "labels"
    type: "source"
    sources:
      - path: "data/labels.parquet"
        format: "parquet"
    depends_on: [ ]

  - name: "combined"
    type: "source"
    operation: "merge"
    merge_on: [ "customer_id" ]
    merge_how: "inner"
    depends_on: [ "main_data", "labels" ]
```

### train.yaml

```yaml
pipeline:
  etl: "combined"                     # Reference to ETL output
  target: "fraud_label"              # Target column name

  split:
    test_size: 0.2                   # Test set proportion
    random_state: 42                 # Reproducibility seed
    stratify: true                   # Stratified split

  preprocessing:
    steps:
      - type: "cardinality_reducer"
        columns: [ "zone", "tariff" ]
        threshold: 0.1
      - type: "te_encoder"
        columns: [ "zone" ]
        smoothing: 20
      - type: "to_dummy"
        columns: [ "tariff_type" ]
      - type: "cast_dtype"
        dtype: "float32"
      - type: "minmax_scaler_row"
        columns: [ "month_*" ]
      - type: "tsfel_vars"
        columns: [ "month_*" ]
      - type: "extra_vars"
        columns: [ "month_*" ]

  feature_selection:
    steps:
      - type: "constant"
        threshold: 0.99
      - type: "correlation"
        method: "pearson"
        threshold: 0.9
      - type: "boruta"
        n_runs: 10
        columns: "month_*"          # ColumnResolver patterns

  model:
    type: "lightgbm"                 # Model adapter name
    params: # Model-specific hyperparameters
      n_estimators: 500
      learning_rate: 0.05
      max_depth: 7
      num_leaves: 31
      class_weight: "balanced"

  evaluation:
    metrics:
      - "auc"
      - "precision"
      - "recall"
      - "f1"
      - "accuracy"
      - "confusion_matrix"
      - "cumulative_gains"
    threshold_calibration:
      strategy: "cost_benefit"       # cost_benefit | operational | precision_recall
      params:
        inspection_cost: 100
        recovery_value: 500
    plots:
      static: true                   # matplotlib/seaborn
      interactive: true              # plotly
    report:
      format: [ "html", "json" ]

output:
  directory: "output"
```

### infer.yaml

```yaml
pipeline:
  model_path: "output/train-20260315_1400/models/model.pkl"
  feature_engineering_path: "output/train-20260315_1400/models/fe_pipeline.pkl"
  etl: "combined"

  output:
    predictions_file: "predictions.csv"
    include_probabilities: true
```

### eda.yaml

```yaml
eda:
  dataset: "data/consumption.csv"     # Path to dataset
  target: "fraud_label"              # Target column
  id_column: "customer_id"          # Identifier column

  phases: # Phases to run (all by default)
    - 0  # Loading Validation
    - 1  # Global Stats
    - 2  # Column Analysis
    - 3  # Target Analysis
    - 4  # Geospatial
    - 5  # Feature Importance
    - 6  # Segmentation
    - 7  # Related Columns

  geospatial:
    lat_column: "latitude"
    lon_column: "longitude"

  output:
    directory: "output/eda"
    interactive: true
    static: true
```

---

## 12. Supported Models

| Model             | Adapter Class     | Type                | Library      | GPU Support | Status        |
|-------------------|-------------------|---------------------|--------------|-------------|---------------|
| LightGBM          | `LGBMAdapter`     | Gradient Boosting   | lightgbm     | Yes         | [IMPLEMENTED] |
| CatBoost          | `CatBoostAdapter` | Gradient Boosting   | catboost     | Yes         | [IMPLEMENTED] |
| Neural Network    | `NNAdapter`       | Deep Learning (MLP) | keras/tf     | Yes         | [IMPLEMENTED] |
| LSTM              | `LSTMAdapter`     | Recurrent NN        | keras/tf     | Yes         | [IMPLEMENTED] |
| Simple Trend      | `SimpleTrend`     | Rule-based          | (built-in)   | N/A         | [IMPLEMENTED] |
| Simple Constant   | `SimpleConstant`  | Rule-based          | (built-in)   | N/A         | [IMPLEMENTED] |
| Ensemble (Voting) | `EnsembleModel`   | Soft Voting         | scikit-learn | Depends     | [IMPLEMENTED] |
| Ensemble (Stack)  | `EnsembleModel`   | Stacking (LR meta)  | scikit-learn | Depends     | [IMPLEMENTED] |
| XGBoost           | --                | Gradient Boosting   | xgboost      | Yes         | [PLANNED]     |
| Random Forest     | --                | Bagging             | scikit-learn | No          | [PLANNED]     |

---

## 13. Current Limitations & Known Issues

### Architecture Issues

| ID     | Severity | Issue                                                                                                   | Status       |
|--------|----------|---------------------------------------------------------------------------------------------------------|--------------|
| KI-001 | High     | **God Class**: `ConfigPipelineBuilder` is 806 lines. Needs decomposition into smaller, focused builders | [RESOLVED]   |
| KI-002 | Medium   | **Legacy modeling**: Some model code does not conform to `BaseModel` ABC                                | [DOCUMENTED] |
| KI-003 | Low      | **Dead registries**: Unused registry entries exist in the codebase                                      | [RESOLVED]   |

### Configuration & Validation

| ID     | Severity | Issue                                                                                                                            | Status     |
|--------|----------|----------------------------------------------------------------------------------------------------------------------------------|------------|
| KI-004 | High     | **No JSON Schema validation**: YAML configs are not validated against a schema; malformed configs produce cryptic runtime errors | [RESOLVED] |
| KI-005 | Medium   | **Line length conflict**: isort/black configured for 140 chars, flake8 for 100 chars                                             | [RESOLVED] |

### Code Quality

| ID     | Severity | Issue                                                                                        | Status     |
|--------|----------|----------------------------------------------------------------------------------------------|------------|
| KI-006 | Medium   | **Missing exception chains**: `raise X` instead of `raise X from e` loses traceback context  | [RESOLVED] |
| KI-007 | Medium   | **Broken root logger**: Preprocessing module configures root logger instead of module logger | [RESOLVED] |
| KI-008 | Low      | **35% test coverage**: Significant gaps in unit and integration test coverage                | Open       |

### Security

| ID     | Severity | Issue                                                                                                                                                      |
|--------|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| KI-009 | Medium   | **Pickle limitations**: Despite allowlisting, pickle deserialization carries inherent security risks. Consider ONNX or safetensors for model serialization |

### Operations

| ID     | Severity | Issue                                                                            |
|--------|----------|----------------------------------------------------------------------------------|
| KI-010 | High     | **No CI/CD pipeline**: No automated testing, linting, or deployment pipeline     |
| KI-011 | Medium   | **No experiment tracking**: No MLflow or equivalent integration                  |
| KI-012 | Medium   | **No drift detection**: No mechanism to detect data or model drift in production |

---

## 14. Future Roadmap

### Phase 1: Stability & Quality (Short-term)

| Feature                         | Priority | Related Issues        |
|---------------------------------|----------|-----------------------|
| Increase test coverage to 80%+  | High     | KI-008                |
| CI/CD pipeline (GitHub Actions) | High     | KI-010                |
| SHAP integration                | High     | OBJ-5, FR-EVAL-014    |

> **Note**: KI-001, KI-003, KI-004, KI-005, KI-006, KI-007 have been resolved as of March 2026. KI-002 is documented as
> intentional design (legacy models wrapped by BaseModel-compliant adapters).
> SHAP moved from Phase 2 to Phase 1 (v1.2): GAP-ANALYSIS-01 classifies it as P1 with Low effort and it is a
> prerequisite for the REST API `/explain` endpoint planned in Phase 2.

### Phase 2: Tracking & Deployment (Medium-term)

| Feature                      | Priority | Description                                                                                    |
|------------------------------|----------|------------------------------------------------------------------------------------------------|
| Experiment tracking (MLflow) | High     | Track parameters, metrics, and artifacts across runs                                           |
| REST API for inference       | High     | Real-time predictions via HTTP endpoint for operational system integration (billing, CRM, etc.)|
| Model registry & versioning  | Medium   | Formal model lifecycle management                                                              |
| Cross-validation support     | Medium   | k-fold CV during training for more robust evaluation                                           |
| Hyperparameter optimization  | Medium   | Grid, random, and Bayesian search                                                              |
| Model probability calibration    | High     | Isotonic/Platt scaling for reliable predicted probabilities                                        |
| Per-segment evaluation           | Medium   | Metrics broken down by configurable grouping column (category, zone, tariff)                       |

### Phase 3: Production Readiness (Long-term)

| Feature                      | Priority | Description                                              |
|------------------------------|----------|----------------------------------------------------------|
| Data drift detection         | High     | Monitor input distribution changes over time             |
| Model drift detection        | High     | Monitor prediction quality degradation                   |
| Online learning support      | Medium   | Incremental model updates without full retraining        |
| Batch inference optimization | Medium   | Parallel/chunked processing for large-scale inference    |
| ONNX model export            | Low      | Framework-agnostic model serialization                   |
| Temporal split strategies    | Medium   | Time-based train/test splits to prevent temporal leakage |
| Group-aware splits           | Medium   | Customer-level splits to prevent data leakage            |
| Pilot-control field validation   | High     | RCT design for proving model ROI against random inspection                                         |

---

## 15. Dependencies

### Core Dependencies (Required)

| Package            | Purpose                                    |
|--------------------|--------------------------------------------|
| `boruta`           | All-relevant feature selection (Boruta)    |
| `catboost`         | CatBoost gradient boosting                 |
| `click`            | CLI framework                              |
| `imbalanced-learn` | Handling class imbalance (SMOTE, etc.)     |
| `lightgbm`         | LightGBM gradient boosting                 |
| `numpy`            | Numerical computing                        |
| `pandas`           | Data manipulation and analysis             |
| `pyarrow`          | Parquet file support                       |
| `pyyaml`           | YAML configuration parsing                 |
| `rich`             | Terminal formatting and progress bars      |
| `scikit-learn`     | ML utilities, preprocessing, meta-learners |
| `scipy`            | Statistical functions                      |
| `tsfel`            | Time-series feature extraction             |
| `tqdm`             | Progress bars                              |
| `unidecode`        | Unicode column name normalization          |

### Optional Dependencies

| Package      | Purpose                     | Required For         |
|--------------|-----------------------------|----------------------|
| `matplotlib` | Static plot generation      | Evaluation/EDA plots |
| `seaborn`    | Statistical visualizations  | Evaluation/EDA plots |
| `plotly`     | Interactive plot generation | Interactive reports  |
| `tensorflow` | Neural network backend      | NN and LSTM models   |
| `keras`      | Neural network API          | NN and LSTM models   |
| `GPUtil`     | GPU monitoring              | `doctor` command     |
| `psutil`     | System resource monitoring  | `doctor` command     |

### Development Dependencies

| Package      | Purpose             |
|--------------|---------------------|
| `pytest`     | Test framework      |
| `isort`      | Import sorting      |
| `black`      | Code formatting     |
| `flake8`     | Linting             |
| `bandit`     | Security analysis   |
| `prettier`   | YAML/MD formatting  |
| `pre-commit` | Git hook management |

---

## 16. Testing Strategy

### Current State

| Metric           | Value                                  |
|------------------|----------------------------------------|
| Test files       | 15                                     |
| Total tests      | 280                                    |
| Pass rate        | 100%                                   |
| Code coverage    | 35%                                    |
| Framework        | pytest                                 |
| Marker policy    | Strict (no unmarked tests)             |
| Pre-commit hooks | isort, black, bandit, flake8, prettier |

### Coverage Targets

| Category          | Current | Target | Priority |
|-------------------|---------|--------|----------|
| Core pipeline     | ~40%    | 90%    | High     |
| ETL               | ~30%    | 85%    | High     |
| Preprocessing     | ~35%    | 85%    | Medium   |
| Feature selection | ~40%    | 80%    | Medium   |
| Modeling          | ~30%    | 80%    | High     |
| Evaluation        | ~35%    | 85%    | Medium   |
| Inference         | ~25%    | 80%    | High     |
| EDA               | ~20%    | 70%    | Low      |
| CLI               | ~30%    | 75%    | Medium   |

### Testing Strategy (Planned)

1. **Unit tests:** All ABCs, transformers, selectors, model adapters tested in isolation
2. **Integration tests:** End-to-end pipeline execution with synthetic data
3. **Configuration tests:** All YAML config permutations validated
4. **Security tests:** Pickle loading, path traversal, allowlist enforcement
5. **Regression tests:** Known-good outputs preserved and validated against
6. **Performance tests:** Benchmark training/inference time on standard datasets

---

## 17. Glossary

| Term                         | Definition                                                                                                                                                                |
|------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **NTL**                      | Non-Technical Losses. Electricity losses due to theft, fraud, meter tampering, or billing errors -- as opposed to technical losses from transmission/distribution physics |
| **BID / IDB**                | Banco Interamericano de Desarrollo / Inter-American Development Bank                                                                                                      |
| **Feature Engineering**      | The process of creating new features from raw data to improve model performance                                                                                           |
| **Feature Selection**        | The process of selecting the most relevant features and removing redundant or irrelevant ones                                                                             |
| **Boruta**                   | An all-relevant feature selection algorithm that uses shadow features and statistical tests to identify features significantly more important than random noise           |
| **Target Encoding**          | Replacing a categorical value with the mean of the target variable for that category, with smoothing to prevent overfitting                                               |
| **Cardinality Reduction**    | Collapsing rare categories (below a frequency threshold) into a single "other" category                                                                                   |
| **Information Value (IV)**   | A measure of the predictive power of a feature, commonly used in credit scoring and fraud detection                                                                       |
| **Kolmogorov-Smirnov (KS)**  | A statistical test measuring the maximum distance between two cumulative distribution functions; used to assess feature discriminative power                              |
| **Cramer's V**               | A measure of association between two categorical variables, based on chi-squared statistics                                                                               |
| **Cumulative Gains**         | A chart showing the percentage of positive cases captured as a function of the percentage of the population targeted, measuring model lift                                |
| **Threshold Calibration**    | Adjusting the classification threshold (default 0.5) to optimize for operational objectives (e.g., inspection ROI, precision targets)                                     |
| **Cost-Benefit Calibration** | Setting the threshold by comparing the cost of a false positive (wasted inspection) against the benefit of a true positive (recovered revenue)                            |
| **Soft Voting**              | Ensemble method that averages predicted probabilities from multiple models                                                                                                |
| **Stacking**                 | Ensemble method that trains a meta-learner on the predictions of base models                                                                                              |
| **DAG**                      | Directed Acyclic Graph. Used for dependency resolution in ETL orchestration                                                                                               |
| **Context-Passing**          | Pipeline pattern where a mutable dictionary is passed between steps, accumulating state                                                                                   |
| **tsfel**                    | Time Series Feature Extraction Library. Extracts statistical and temporal features from time series data                                                                  |
| **Pickle**                   | Python's native object serialization format. Used for model persistence. Carries security risks with untrusted data                                                       |
| **SHAP**                     | SHapley Additive exPlanations. A game-theoretic approach to explain individual model predictions                                                                          |
| **MLflow**                   | Open-source platform for ML lifecycle management (experiment tracking, model registry, deployment)                                                                        |
| **Data Drift**               | Changes in the statistical distribution of input data over time, which may degrade model performance                                                                      |

---

*End of Document -- PRD-01 v1.0*
