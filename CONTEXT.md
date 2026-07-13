# Context

This is the domain model for the Energizados repo. It has two bounded contexts —
Framework Core and Web Console — and this file is the single source of truth for
the ubiquitous language.

## Context Map

This repo has two bounded contexts.

### Contexts

- [Framework Core](#framework-core) — the ML framework itself: turns raw data + config into trained models, predictions, reports, and analyses. Owns all ML logic.
- [Web Console](#web-console) — manages ML experiments: registers projects, queues async pipeline executions, and browses what they produced.

### Relationships

- **Web Console → Framework Core**: the web console is a thin observer/controller over the core. It triggers runs through the core's `ConfigPipelineBuilder` (via the `energizados.api` service layer), streams progress events, and reads core-produced artifacts (Runs, metrics, models, reports). The core has no dependency on the web console.
- **Shared vocabulary**: both contexts use *Run* (the core produces one per successful training execution; the web console generalizes it — see each context's section below). *Pipeline*, *Step*, *Model* are core concepts the web console references but does not own.

## Framework Core

The framework core is the bounded context for the ML framework itself: it
defines the pipeline that turns raw data + configuration into trained models,
predictions, reports, and analyses. It is consumed by the CLI, the web console,
and user projects through the `energizados.api` service layer. Its eight base
classes are frozen public API.

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

**FeatureSelector**:
A `fit`/`transform` unit that drops columns during FeatureSelection, following
the scikit-learn convention (`BaseEstimator` / `TransformerMixin`). Defined by
the frozen `BaseFeatureSelector` contract and resolved by config name
(`"boruta"`, `"correlation"`, `"constant"`) through `selector_registry` — the
same Registry that catalogs Models and Transformers. The *reduce* counterpart
to a Transformer: a Transformer modifies columns during Preprocessing; a
FeatureSelector drops them during FeatureSelection.
_Avoid_: filter, reducer, column selector

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

## Output

**Run**:
The persisted output bundle of a successful training execution — everything
the Pipeline left behind under `output/train-YYYYMMDD_HHMM/` (trained Models,
reports, plots, config snapshot, `run.log`), described by `RunMetadata`
(persisted as `run_metadata.json`) and queryable through `RunManager`. The
core sense is a **training run** — the only kind the core produces; the web
console generalizes Run to etl / eda / inference / training types (see the
Web Console context). Distinct from the in-memory **Context** (the live dict
flowing between Steps) and from a **Job** (the web console's attempt to
execute).
_Avoid_: output, result, run-dir, experiment

## Web Console

The web console is a bounded context for managing ML experiments: it registers
projects, queues asynchronous pipeline executions, and lets users browse what
those executions produced. It is a thin layer over the framework core
(`energizados.api`) — it owns execution orchestration and the experiment
vocabulary, not the ML itself.

### Workspace

**Project**:
A workspace directory generated by `energizados init` — bundles a configuration
(`config/`), a codebase (`src/`), data, and Runs (`output/`). Exists on disk
independently of any console. Registering a Project into a console assigns the
`project_id` that console uses to refer to it. The registry is the source of
truth for *which Projects a console knows*; the directory is the source of truth
for *the Project's content*.
_Avoid_: codebase, directory, repo, workspace

**Codebase**:
The extensible source code of a Project — the entire `src/` tree (custom ETLs,
models, feature selectors, inference engines, utilities, run scripts). Loaded by
the framework via the `src.` import prefix. One of the two things `energizados
init` generates alongside the configuration.
_Avoid_: project, source, code, extensions

**Global** *(deprecated)*:
The pre-multi-project scope where a Job/Run has no owning Project
(`project_path` is null). Legacy. The canonical model is **Project-scoped**:
every Job and Run belongs to exactly one Project. Do not create new Global
executions; existing ones surface read-only.
_Avoid_: unscoped, sandbox

### Execution

**Job**:
An attempt to execute a pipeline asynchronously. It has a lifecycle
(queued → running → success / failed / aborted) and carries the configuration
that was submitted. It answers *"did it run, when, and how did it end?"* Belongs
to exactly one Project.
_Avoid_: task, process, execution, run (as a synonym — see Run)

**Config type**:
Which configuration schema (`etl` / `train` / `eda` / `infer`) a submitted config
is validated against. A **validation label only** — it does not determine what
the Job executes. A Job executes a **Pipeline** (a core-framework concept): the
worker builds it from every enabled section of the merged config, so a `train`
Job may also run ETL when that section is enabled.
_Avoid_: execution scope, step, phase

**Run**:
The persisted output bundle produced by a successful Job — everything that
execution left behind (metrics, models, artifacts, reports, predictions). It
answers *"what did this execution produce?"* A Job produces at most one Run.
A Run is **type-specific** (etl / eda / inference / training); only same-type
Runs are meaningfully comparable.
_Avoid_: output, result, run-dir, experiment

**Run type**:
Which kind of pipeline produced a Run. Determines what the Run contains, the
shape of its summary, and which other Runs it can be compared against. Derived
from the producing Job.

**Run summary**:
The typed, structured summary every Run carries — the facts that identify and
characterize it. A **shared base** (run identity, type, timestamps, duration,
status, framework / python / git versions, config reference) extended by
**type-specific** fields. Drives what the UI shows per type and what Compare can
align on.
_Avoid_: metrics (too narrow), metadata

**TrainingRun**:
A Run produced by a training Job. Carries the trained model(s), reports, plots,
and the config snapshot. Its summary adds AUC, F1, precision, recall, and model
type(s).

**ETLRun**:
A Run produced by an ETL Job. Carries the processed dataset(s) and the ETL
execution plan. Its summary adds rows_in, rows_out, and files written.

**EDARun**:
A Run produced by an EDA Job. Carries the exploratory-data-analysis report. Its
summary adds the report path and dataset statistics (no ML metrics).

**InferenceRun**:
A Run produced by an inference Job. Carries the scored predictions and the model
that produced them. Its summary adds prediction count, score distribution, and
model used.
_Avoid_: experiment (reserved for a future training-experiment concept)

**Compare**:
Side-by-side viewing of same-type Runs aligned on their shared summary fields.
**Type-scoped**: only Runs of the same Run type can be compared; defaults to
TrainingRun, where metric comparison is meaningful. Cross-type comparison is not
supported.
_Avoid_: diff, benchmark

### Lineage

**Retry**:
A new Job that re-executes a prior Job (typically because it failed or was
aborted) with the same configuration. An execution-level relationship between
Jobs (linked via `retried_from`). Not a Run concept.
_Avoid_: re-run, re-execute, retrain

**Retrain**:
Producing a new Run by re-executing from a prior Run's saved configuration. An
experiment-level relationship between Runs. Distinct from Retry.
_Avoid_: re-run, retry, fork

**derived_from**:
The Run → Run relationship stating that one Run was produced by retraining from
another. Roots the experiment-lineage tree (Run A → Run B → Run C).
_Avoid_: parent, source, origin
