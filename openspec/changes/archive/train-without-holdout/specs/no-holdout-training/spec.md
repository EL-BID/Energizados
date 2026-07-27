# No-Holdout Training Specification

**Change:** `train-without-holdout`
**Domain:** `no-holdout-training` (Framework Core bounded context)
**Status:** Spec
**Depends on:** `openspec/changes/train-without-holdout/proposal.md`

---

## Purpose

Specify the behavior of the Energizados ML framework when a user configures training on 100% of available labeled data without reserving a validation or test holdout. This mode — **no-holdout training** — lets a data scientist deploy a production Model that has seen every labeled row after hyperparameters, feature engineering, and model architecture have already been validated in a separate experiment. Early stopping uses an **internal split** inside each Model class; no honest generalization metrics are reported.

---

## Requirements

### Requirement: FR1 — Split with method "none" assigns all data to train

The `SPLIT_SCHEMA` method enum MUST accept `"none"` as a sixth value. When `SplitStep` executes with `method == "none"`, it MUST assign 100% of the input dataset to `train_df`, set `val_df` and `test_df` to empty DataFrames, write only `train.parquet`, and set `val_path=None` and `test_path=None` in Context. `val.parquet` and `test.parquet` MUST NOT be written — writing empty parquet files creates downstream `pd.read_parquet` edge cases.

*(Implements D2: config surface is `method: "none"` on SplitStep.)*

#### Scenario: method "none" puts all rows in train

- GIVEN a `SplitStep` configured with `method: "none"` and an input dataset of N rows
- WHEN `execute()` runs
- THEN `train_path` points to a parquet containing all N rows
- AND `val_path` is `None` in Context
- AND `test_path` is `None` in Context

#### Scenario: only train.parquet is written

- GIVEN a `SplitStep` configured with `method: "none"`
- WHEN `execute()` runs
- THEN `train.parquet` exists in the output directory
- AND `val.parquet` does NOT exist
- AND `test.parquet` does NOT exist

#### Scenario: split metadata records zero val and test

- GIVEN a `SplitStep` configured with `method: "none"`
- WHEN `execute()` runs and writes split metadata
- THEN the metadata records `n_val: 0` and `n_test: 0`

#### Scenario: schema accepts method none

- GIVEN a Configuration with `train.split.method: "none"`
- WHEN `ConfigValidator` validates the train section
- THEN validation passes with no error
- AND no additional fields (`group_column`, `date_column`) are required for the `"none"` method

---

### Requirement: FR2 — TrainingStep accepts optional val_path

`TrainingStep.execute()` MUST accept `val_path=None` without raising. The guard at the top of `execute()` MUST require only `train_path`. When `val_path` is `None`, every block that touches validation data — load, feature extraction, `columns_filter`, datetime-column drop, FeatureEngineering transform, and NaN diagnostics — MUST be guarded so that `X_val` and `y_val` are `None`. `TrainingStep` MUST pass `X_val=None, y_val=None` to the Model's `.fit()`, which triggers the Model's existing internal split for early stopping. The Model layer (adapters, supervised models) MUST NOT be modified.

*(Implements D1: early stopping uses internal 10% split, model layer untouched.)*

#### Scenario: training succeeds without val_path

- GIVEN a `TrainingStep` with `train_path` set and `val_path=None`
- WHEN `execute()` runs
- THEN execution completes without error
- AND `model_path` in Context points to a loadable `model.pkl`

#### Scenario: model layer receives X_val=None

- GIVEN a `TrainingStep` with `val_path=None`
- WHEN `execute()` calls `model.fit(X, y, X_val, y_val)`
- THEN `X_val` passed to `.fit()` is `None`
- AND `y_val` passed to `.fit()` is `None`
- AND the Model's internal `train_test_split(test_size=0.1)` for early stopping is triggered

---

### Requirement: FR3 — No-holdout runs report no honest metrics and set holdout_mode

When `val_path` is `None`, `TrainingStep` MUST set `val_auc=None`, `val_f1=None`, `val_predictions_path=None`, and `holdout_mode="none"` in Context. It MUST NOT write a `val_predictions.parquet`. It MUST log a message stating that no honest validation metrics are available and that the internal split is for early stopping only — the internal 10% split is in-sample for the final Model and is NOT an independent generalization estimate. When a validation split IS provided, `TrainingStep` MUST set `holdout_mode="standard"` in Context. Comparison mode MUST apply the same guards: per-Model val metrics are `None` when `X_val` is `None`.

`holdout_mode` is a string-typed Context key (`"none"` / `"standard"`), extensible to future modes such as `"cv"`.

*(Implements D4: holdout_mode is a string, extensible.)*

#### Scenario: no-holdout metrics are None

- GIVEN a `TrainingStep` with `val_path=None`
- WHEN `execute()` completes
- THEN `val_auc` in Context is `None`
- AND `val_f1` in Context is `None`
- AND `val_predictions_path` in Context is `None`
- AND `holdout_mode` in Context is `"none"`

#### Scenario: no-holdout logs honesty message

- GIVEN a `TrainingStep` with `val_path=None`
- WHEN `execute()` runs
- THEN the log contains a message stating that no honest validation metrics are available and the internal split is used for early stopping only

#### Scenario: standard run sets holdout_mode standard

- GIVEN a `TrainingStep` with `val_path` set to a valid parquet
- WHEN `execute()` completes
- THEN `holdout_mode` in Context is `"standard"`
- AND `val_auc` and `val_f1` are computed (floats, not None)

#### Scenario: comparison mode guards val metrics

- GIVEN a `TrainingStep` in comparison mode with `val_path=None`
- WHEN `execute()` runs
- THEN per-Model val metrics are `None`

---

### Requirement: FR4 — Director auto-skips evaluation in no-holdout mode

When `split.method == "none"` and `evaluation.enabled == true`, the `PipelineDirector` MUST log a WARNING and skip the Evaluator Step (set it to `None`). It MUST NOT raise an exception. This matches the mental model: no test set means nothing to evaluate. The user MAY explicitly set `evaluation.enabled: false` to silence the warning.

*(Implements D3: evaluation auto-skip with WARNING, not hard failure.)*

#### Scenario: evaluation auto-skipped with warning

- GIVEN a pipeline Configuration with `split.method: "none"` and `evaluation.enabled: true`
- WHEN the `PipelineDirector` builds the pipeline
- THEN the Evaluator Step is not included in the pipeline (set to `None`)
- AND a WARNING is logged
- AND no exception is raised

---

### Requirement: FR5 — Evaluator defensive guard for missing test_path

`DefaultEvaluator.execute()` MUST return early with `skipped=True` and `metrics={}` when no `test_path` is available in Context, logging a warning. This guard provides standalone-usage safety; the director auto-skip (FR4) is the primary gate.

*(Implements D3, defensive layer for standalone evaluator usage.)*

#### Scenario: evaluator skips gracefully without test_path

- GIVEN a `DefaultEvaluator` invoked with no `test_path` in Context
- WHEN `execute()` runs
- THEN the result contains `skipped=True` and `metrics={}`
- AND a warning is logged
- AND no exception is raised

---

### Requirement: FR6 — Ensemble blending raises ConfigurationError in no-holdout mode

When `X_val is None`, an Ensemble configured with `method: "stacking"` and `use_val_as_oof: true` (**blending**) MUST raise a `ConfigurationError` with actionable guidance directing the user to at least one of: (a) provide a validation split, (b) switch to `use_val_as_oof: false` (K-fold OOF stacking — the principled alternative), or (c) use `soft_voting`. Soft-voting ensembles and K-fold-OOF stacking (`use_val_as_oof: false`) MUST work without a holdout. An internal-split fallback for blending is explicitly NOT supported.

*(Implements D5: blending disallowed, soft-voting and K-fold-OOF stacking allowed.)*

#### Scenario: blending raises ConfigurationError

- GIVEN an Ensemble configured with `method: "stacking"` and `use_val_as_oof: true`
- WHEN `.fit()` is called with `X_val=None`
- THEN a `ConfigurationError` is raised
- AND the error message mentions at least one actionable alternative (provide a val split, use K-fold OOF, or use soft voting)

#### Scenario: soft voting works without holdout

- GIVEN an Ensemble configured with `method: "soft_voting"`
- WHEN `.fit()` is called with `X_val=None`
- THEN the Ensemble fits successfully without error

#### Scenario: K-fold OOF stacking works without holdout

- GIVEN an Ensemble configured with `method: "stacking"` and `use_val_as_oof: false`
- WHEN `.fit()` is called with `X_val=None`
- THEN the Ensemble fits successfully using K-fold cross-validation for OOF predictions

---

### Requirement: FR7 — Calibration skipped when validation data is absent

When `X_val is None`, `TrainingStep` MUST skip calibration (the `_apply_calibration` call) and log a warning. No-holdout Models MUST ship uncalibrated. Users who require calibration MUST provide a validation split. Calibrating on the internal split would be misleadingly optimistic because the Model has seen that data for early stopping.

*(Implements D6: calibration skipped with warning when X_val is None.)*

#### Scenario: calibration skipped without val

- GIVEN a `TrainingStep` with `val_path=None` and calibration enabled in Configuration
- WHEN `execute()` runs
- THEN calibration is skipped
- AND a warning is logged
- AND the Model ships uncalibrated

---

## Constraints

### Backward Compatibility

The existing pipeline path (validation split required) MUST continue to work byte-for-byte unchanged. All changes MUST be additive — no existing code path is removed. The training/director/evaluator guards MUST be no-ops when `val_path` is not `None`. Rolling back the `"none"` enum value MUST cause the Schema to reject the Configuration again, with no data migration and no breaking config changes.

#### Scenario: existing val-required path unchanged

- GIVEN a pipeline Configuration with `split.method: "stratified"` (or any pre-existing method)
- WHEN the pipeline runs
- THEN behavior is identical to before this change
- AND `val_auc`, `val_f1`, `val_predictions_path` are computed as before
- AND `holdout_mode` is `"standard"`

### Logging Discipline

All output MUST use the `logging` module. No `print` statements.

### Strict TDD

All requirements MUST be test-driven. Tests are written first and run with `pytest tests/`.

---

## Non-Functional Requirements

### Additive-only Changes

No new Python dependencies. All changes are additive — new branches, new guards, new Context keys. No existing method signature is changed in a breaking way.

#### Scenario: no new dependencies

- GIVEN the project after this change
- WHEN `pip install -e .` runs
- THEN no new packages beyond the existing dependency set are required

### No Performance Regression

Existing pipelines (with a validation split) MUST NOT incur measurable performance regression. The added guards are constant-time `None` checks.

---

## Out of Scope

- **Cross-validation-based honest metrics** for no-holdout runs. A future change may add `holdout_mode: "cv"` with K-fold CV metrics. The string-typed `holdout_mode` is designed for this extensibility.
- **Internal-split fallback for ensemble blending.** The Model's internal split is not surfaced as a separate DataFrame and would be misleading for blending.
- **Web console changes.** The web console's Compare feature should handle `null` val metrics gracefully, but no web console code is changed in this change.
- **CONTEXT.md updates.** The glossary terms (no-holdout training, `holdout_mode`, internal split, blending) should be added to CONTEXT.md under a new "Training Modes" subsection, but this is tracked as a task, not part of the spec.
- **Inference changes.** A Model trained without a holdout is a valid Model; inference already works out-of-the-box. Confirmed as a non-goal.

---

## Decision Traceability

| Requirement | Decision | Summary |
|---|---|---|
| FR1 | D2 | `method: "none"` is the config surface; 100% → train; `val_path=None, test_path=None`; train.parquet only |
| FR2 | D1, D2 | TrainingStep accepts `val_path=None`; passes `X_val=None` to model; internal 10% split for early stopping; model layer untouched |
| FR3 | D4 | `val_auc/val_f1/val_predictions_path=None`; `holdout_mode` string (`"none"` / `"standard"`); honesty log message |
| FR4 | D3 | Director auto-skips evaluation with WARNING when `method=="none"`, even if `enabled=true` |
| FR5 | D3 | Evaluator defensive guard: `skipped=True, metrics={}` when no `test_path` |
| FR6 | D5 | Blending (`stacking` + `use_val_as_oof=true`) → `ConfigurationError`; soft-voting and K-fold-OOF stacking allowed |
| FR7 | D6 | Calibration skipped with warning when `X_val=None` |
