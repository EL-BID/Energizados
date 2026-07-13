# Framework Core

The framework core is the bounded context for the ML framework itself: it
defines the pipeline that turns raw data + configuration into trained models,
predictions, reports, and analyses. It is consumed by the CLI, the web console,
and user projects through the `energizados.api` service layer. Its eight base
classes are frozen public API.

## Language

### Orchestration

**Pipeline**:
The orchestrator that executes Steps in sequence over a shared Context, turning
a configuration into trained models and outputs. Built from config by the
`ConfigPipelineBuilder` (the builder) and internally delegated by a
`PipelineDirector`. The framework's `Pipeline` does **not** inherit `BasePipeline`.
_Avoid_: workflow, DAG, job

**Custom Pipeline**:
A user-defined pipeline that extends the framework through the `BasePipeline`
contract (`run` / `validate` / `get_required_keys`). A *different concept* from
the framework Pipeline, despite the shared code name. The code name `BasePipeline`
is kept for back-compat (frozen API).
_Avoid_: pipeline (unqualified — see Pipeline)

**Step**:
A phase of a Pipeline — a `PipelineStep` that executes over the shared Context,
validates its inputs, and declares the context keys it requires and produces.
The framework ships `SplitStep` and `TrainingStep`. The configuration sections
`feature_engineering`, `models`, `ensemble`, and `evaluation` are **sub-phases
nested inside `TrainingStep`**, not Steps. Progress, retry, and the CLI `--step`
flag operate at the Step level.
_Avoid_: phase, stage, task

**Context**:
The shared mutable state — a plain `dict` — that flows between Steps as the
Pipeline executes. Each Step reads the keys it needs and writes the keys it
produces (`train_path`, `model_path`, `val_predictions_path`…), and the keys
accumulate over the run. There is no schema: the contract between Steps is
implicit, declared by each Step's `get_required_keys` / `get_output_keys`.
Distinct from the web console's **Run summary** (typed, per-Run metadata).
_Avoid_: state, payload, blackboard, RunContext (appears in docs, not a class)

### Data

**ETL**:
A data phase that extracts, transforms, and loads data — turning raw inputs
(`data/raw/`) into a processed dataset for training or analysis. Defined by the
frozen `BaseETL` contract (`extract` / `transform` / `load`); the framework
ships `SourceETL` (concat / merge / incremental modes) and the
`ETLOrchestrator` runs multiple ETLs in dependency order. Driven by the `etl`
config section.
_Avoid_: pipeline (it is one phase), ingestion, stage

**EDA**:
The exploratory-data-analysis phase — profiles a raw dataset (nulls,
distributions, target balance, geospatial, feature importance) and emits a
self-contained HTML report, with no ML. Defined by the frozen `BaseExplorer`
contract (`explore`); orchestrated by `DatasetExplorer`. Driven by the `eda`
config section.
_Avoid_: profiling, analysis (too generic), report (the output, not the phase)

### Modeling

**Model**:
The unit that learns from data and predicts — what the framework trains,
evaluates, persists (`model.pkl`), and loads for inference. Defined by the
frozen `BaseModel` contract (`fit` / `predict` / `predict_proba` /
`get_raw_model`). A Model is either a single unit, provided by an **Adapter**
(`LGBMModelAdapter`, `CATModelAdapter`…) that fulfills `BaseModel` by wrapping
a legacy estimator class, or an **Ensemble** of several. The legacy class and
the raw estimator underneath are an implementation detail (exposed via
`get_raw_model`), not ubiquitous-language terms.
_Avoid_: estimator, algorithm, classifier, learner

**Ensemble**:
A Model that combines N base Models into one predictive unit — via soft voting
(weighted average) or stacking (meta-learner over base predictions). Persisted
as `ensemble.pkl` alongside its base Models under `models/{name}/`.
_Avoid_: blend, composite

**Registry**:
The unified name→class catalog for framework components — Models, Transformers,
and FeatureSelectors — held in per-domain instances (`model_registry`,
`transformer_registry`, `selector_registry`). Case-insensitive lookup; the
framework resolves a config name (e.g. `"lightgbm"`, `"if_score"`, `"boruta"`)
to its class through it.
_Avoid_: directory, index, lookup table

### Feature Engineering

**FeatureEngineering**:
A sub-phase of `TrainingStep` that turns raw columns into model-ready features
and decides which to keep. Bundles two sub-phases — **Preprocessing** (encode,
scale, derive) and **FeatureSelection** (drop redundant / uninformative
columns) — into one fit/transform artifact persisted as
`feature_engineering.pkl`. Implemented by `DefaultFeatureEngineering`
(`BaseFeatureEngineering`). Despite the colloquial sense (transform only),
here it explicitly includes selection.
_Avoid_: preprocessing (as a synonym — it is a sub-phase), feature extraction

**Preprocessing**:
The transform sub-phase of FeatureEngineering — encodes categoricals, scales,
and derives new columns via per-column transformers plus `global_transformers`
(`if_score`, `tsfel_vars`, `consumption_patterns`…). Produces the
`preprocessor` held inside the feature-engineering artifact. Its transformers
split into a pre-stage (before column encoding) and a post-stage (after).
_Avoid_: feature engineering (as a synonym — it is the bundle)

**FeatureSelection**:
The reduce sub-phase of FeatureEngineering — keeps the informative columns and
drops the rest (boruta, correlation, constant). Optional; when disabled, every
preprocessed column reaches the Model.
_Avoid_: feature engineering, dimensionality reduction

**Transformer**:
A `fit`/`transform` unit that modifies columns during Preprocessing, following
the scikit-learn convention (`BaseEstimator` / `TransformerMixin`). Has two
scopes: a **column transformer** runs per-column (under `preprocessing.columns`,
e.g. `to_dummy`, `target_encoding`) and a **global transformer** runs
cross-column (under `global_transformers`, e.g. `if_score`, `tsfel_vars`,
`clip_outliers`). A global transformer declares a `pipeline_stage` — `pre`
(runs before column encoding, sees raw categoricals) or `post` (default,
after).
_Avoid_: estimator, processor, mapper

**TransformerError**:
The framework exception raised when a Transformer's transform fails during
FeatureEngineering. Frozen public-API type (`EnergizadosError`, `ValueError`).
_Avoid_: transform failure (generic)

### Configuration

**Configuration**:
The merged dict — loaded from YAML (one or more files, last-wins) — that drives
a Pipeline. Held as `Pipeline.config` and consumed by `ConfigPipelineBuilder`.
Answers *"what should this run do?"* before any Step runs.
_Avoid_: settings, options, yaml (the format, not the object)

**Config section**:
A named top-level block of a Configuration, typed as `etl` / `train` / `eda` /
`infer`. Each section carries its own `schema_version` and evolves
independently (`CURRENT_SCHEMA_VERSIONS`). The section's type is the web
console's **Config type** (shared vocabulary — see the Web Console context).
_Avoid_: file (a section may span files), block

**Schema**:
The JSON-Schema validation contract for a Config section (`ETL_SCHEMA`,
`TRAIN_SCHEMA`…), enforced by `ConfigValidator` before a Pipeline runs.
Independent per section type.
_Avoid_: model, definition

**params**:
The keyword arguments handed to a class — a Transformer, Model, ETL, or
feature selector — as configured under its `params` key. Distinct from a
Configuration (the whole) and a section (a block).
_Avoid_: args, hyperparams (a Model's params), configuration

**Allowlist registration**:
The import-safety mechanism (`register_allowed_prefix`) that admits a module
prefix (beyond the defaults `energizados.` and `src.`) for dynamic class
loading from Configuration. Distinct from the Registry — it gates *which
modules may be imported*, not which names map to which classes.
_Avoid_: registry (different concept), whitelist

### Evaluation

**Evaluator**:
The sub-phase of `TrainingStep` that measures a trained Model against held-out
data — computes metrics (AUC, F1, precision, recall…), plots, and HTML/JSON
reports. Defined by the frozen `BaseEvaluator` contract (`evaluate`). Driven by
the `evaluation` config section.
_Avoid_: metrics (the output), scoring, assessment

### Inference

**Inference**:
The phase that scores new (unlabeled) data with a trained Model to produce
predictions — distinct from training. Driven by the `infer` config section.
_Avoid_: prediction (the output, not the phase), scoring (the mechanism)

**Inference engine**:
The unit that performs Inference, fulfilling the frozen `BaseInference`
contract (`predict` / `predict_proba` / `load_model` / `save_predictions`).
The framework ships `DefaultInference` (single Model) and
`HierarchicalInference` (routes rows to per-route Models by condition).
_Avoid_: predictor, scorer
