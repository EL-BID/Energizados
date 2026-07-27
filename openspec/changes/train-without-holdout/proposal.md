# Proposal: Train Without Holdout

**Change:** `train-without-holdout`
**Date:** 2026-07-24
**Status:** Proposal
**Depends on:** `openspec/changes/train-without-holdout/exploration.md`

---

## Problem Statement

The Energizados ML framework currently **requires** a validation split for every training run. `TrainingStep.execute()` raises `ValueError("train_path and val_path are required")` (training.py:244-245) when `val_path` is missing. This blocks a legitimate production workflow: once a data scientist has decided hyperparameters, feature engineering, and model architecture through a separate evaluation experiment, they want to retrain the **same configuration on all available data** — sacrificing honest validation metrics for a final, deployment-ready model that has seen every labeled row. The framework has no way to express this intent today.

---

## Goals

1. **Support no-holdout training end-to-end.** A user can configure the pipeline to train on 100% of available data, produce a valid model artifact, and run inference — with no val or test set reserved.
2. **Reuse the model layer's existing internal split for early stopping.** All three model classes (`LGBMModel`, `CATModel`, `XGBModel`) already do `train_test_split(test_size=0.1, random_state=42)` inside `.train()` when `df_val is None`. This change only propagates `None` to that code path — zero model-layer changes.
3. **Be honest about metrics.** No-holdout runs must NOT report `val_auc` / `val_f1`. The internal 10% split is for early stopping only and is not an independent generalization estimate.
4. **Maintain full backward compatibility.** Existing pipelines with a validation split continue to work byte-for-byte unchanged.

---

## Non-Goals

- **NOT changing the model layer** (adapters, supervised models). The internal-split behavior is already correct and stays untouched.
- **NOT adding cross-validation-based honest metrics** in this change. CV-based honest evaluation for no-holdout runs is a future enhancement.
- **NOT adding an internal-split fallback for ensemble blending.** The model's internal split is inaccessible as a separate DataFrame and would be misleading for blending. Future work.
- **NOT changing inference.** A model trained without a holdout is a valid model; inference already works out-of-the-box. This proposal confirms that as a non-goal to change.

---

## User Stories

### US-1: Production retraining on all data

> **As a** data scientist,
> **I want to** configure a training pipeline with `split.method: "none"` so that the model trains on every labeled row,
> **so that** I can deploy a final production model that has seen all available data, using the hyperparameters and feature engineering I already validated in a separate experiment.

### US-2: No misleading metrics

> **As a** data scientist,
> **I want** the pipeline to set `val_auc` and `val_f1` to `None` and log a clear message when I train without a holdout,
> **so that** I am never tricked into thinking an in-sample early-stopping split represents honest generalization.

### US-3: Graceful evaluation skip

> **As a** data scientist,
> **I want** the pipeline to skip evaluation automatically (with a warning) when there is no test set,
> **so that** I don't have to remember to disable evaluation and don't get a runtime crash.

### US-4: Ensemble compatibility

> **As a** data scientist,
> **I want to** use soft-voting ensembles and K-fold-OOF stacking ensembles in no-holdout training,
> **so that** I can deploy production ensembles without reserving a holdout.

---

## Proposed Solution

### 1. Config surface: `method: "none"` on SplitStep

Add `"none"` as a sixth value to the existing `method` enum in `SPLIT_SCHEMA`. When `method == "none"`:

- `SplitStep.execute()` assigns the **entire dataset** to `train_df`.
- `val_df` and `test_df` are empty DataFrames.
- `SplitStep` writes **only `train.parquet`** — `val.parquet` and `test.parquet` are NOT written (writing empty parquets creates downstream `pd.read_parquet` edge cases).
- Context receives `train_path` (full dataset), `val_path=None`, `test_path=None`.

```yaml
train:
  split:
    method: none
    input_path: data/processed/dataset.parquet
    target_column: target
  models:
    - type: lightgbm
  evaluation:
    enabled: false   # or true — director auto-skips with a warning
```

### 2. TrainingStep: optional validation

Make `val_path` optional throughout `TrainingStep.execute()`. Every block that touches val data (`X_val`, `y_val`) gets a guard. When `val_path` is `None`:

- Model training receives `X_val=None, y_val=None` → the adapter's `.fit()` passes `None` to `.train()`, which triggers the internal 10% split for early stopping.
- Calibration is **skipped** (needs held-out data; internal split is in-sample).
- `val_auc`, `val_f1`, `val_predictions_path` are all set to `None`.
- Context receives `holdout_mode: "none"`.
- Log: `"Training in no-holdout mode. No honest validation metrics available. Internal 10% split used for early stopping only."`

### 3. Director: auto-skip evaluation

When `split.method == "none"` and `evaluation.enabled: true`, the director logs a `WARNING` and **skips** the evaluation step (sets it to `None`). This matches the mental model: no test set = nothing to evaluate. Better UX than a hard failure.

### 4. Evaluator: defensive guard

Add a top-of-`execute()` guard in `DefaultEvaluator`: if no `test_path` is available, log a warning and return early with `metrics: {}` and a `skipped: True` flag. The director auto-skip means this is mainly for standalone usage.

---

## Decisions

### D1: Early stopping uses an INTERNAL 10% split (PRE-RESOLVED)

**Decision:** When no external val is provided, models use their existing internal `train_test_split(test_size=0.1)` for early stopping.

**Rationale:** All three model classes already implement this. The model layer stays untouched — this change only propagates `None` to the existing code path. No new logic, no risk to the model layer.

### D2: Config surface is `method: "none"` on SplitStep (PRE-RESOLVED)

**Decision:** Add `"none"` as a sixth `method` value on `SplitStep`, not a separate flag or optional-periods alternative.

**Rationale:** `SplitStep` already dispatches on `method` via `if/elif`. Adding one branch is the deepest possible module: one config value, one branch, all downstream behavior cascades from `val_path=None`. A `train_on_all: bool` flag would create a second config surface for the same concept, with ambiguous precedence when both are set. Making `val_period`/`test_period` optional only works for `time_series` and leaks train-on-all semantics into period config. See the explore's comparison table for the full rationale.

### D3: Evaluation auto-skip with WARNING, not hard failure (PRE-RESOLVED)

**Decision:** When `method == "none"` + `evaluation.enabled: true`, the director logs a `WARNING` and skips evaluation. Does NOT raise.

**Rationale:** Matches the mental model (no test = nothing to evaluate). Better UX than crashing. The user can still explicitly set `evaluation.enabled: false` to silence the warning.

### D4: `holdout_mode` is a STRING (`"none"` / `"standard"`), not a boolean (PRE-RESOLVED)

**Decision:** Context key `holdout_mode` is a string with values `"none"` and `"standard"`, extensible to future modes like `"cv"`.

**Rationale:** A boolean (`has_honest_val`) encodes only two states and would need breaking changes when a third mode arrives. A string is forward-compatible and self-documenting. Downstream consumers (run_manager, web console Compare) can switch on the value.

### D5: Ensemble blending (`stacking` + `use_val_as_oof=True`) is DISALLOWED in no-holdout mode (RESOLVED)

**Decision:** Do **NOT** disallow all ensembles. Only the `stacking` + `use_val_as_oof=True` (blending) mode raises a clear `ConfigurationError` when `X_val is None`. Soft-voting and K-fold-OOF stacking remain fully supported.

**Rationale (from reading `ensemble.py`):**

| Ensemble mode | `X_val=None` behavior | Verdict |
|---|---|---|
| `soft_voting` | Base models each call `.fit(X, y, X_val=None)` → internal 10% split. Works. | **Supported** |
| `stacking` + `use_val_as_oof=False` | `_generate_oof()` does K-fold CV on `X, y`. No val needed. Works. | **Supported** |
| `stacking` + `use_val_as_oof=True` | `_fit_meta_learner` raises `ValueError("use_val_as_oof=True requires X_val and y_val.")` | **ConfigurationError** |

The ensemble code already raises for the blending case (ensemble.py:103-105). The proposal improves this into an actionable `ConfigurationError` at the TrainingStep level, directing the user to: (a) provide a val split, (b) switch to `use_val_as_oof=False` (K-fold OOF — the principled alternative), or (c) use `soft_voting`.

An internal-split fallback for blending is **rejected** because:

1. The model's internal 10% split is not surfaced as a separate DataFrame — it lives inside `.train()` and only affects early-stopping callbacks.
2. Even if accessible, it would be **misleading for blending**: the model has seen the 10% for early stopping, so predictions on it are not truly out-of-fold.

Disallowing **all** ensembles (the orchestrator's initial recommendation) was considered but rejected as overly restrictive — it would block soft voting and K-fold OOF, both of which work correctly without a holdout.

### D6: Calibration is SKIPPED when `X_val is None`

**Decision:** `_apply_calibration` is skipped (with a warning log) when validation data is absent.

**Rationale:** `CalibratedClassifierCV` needs held-out data. The internal 10% split is in-sample for the final model — calibrating on it would produce a misleadingly optimistic calibration. No-holdout models ship uncalibrated. Users who need calibration must provide a val split.

---

## Alternatives Considered

### Config surface (from explore §2)

| Alternative | Verdict | Why |
|---|---|---|
| `method: "none"` | **ADOPTED** | Deepest module. One config value, one branch. Orthogonal to all existing methods. |
| `train_on_all: bool` flag | Rejected | Second config surface for the same concept. Ambiguous precedence with `method`. Violates one-concept-one-config. |
| Optional `val_period`/`test_period` on `time_series` | Rejected | Only works for one method. Leaks train-on-all semantics into period config. Shallow. |

### Evaluation handling (from explore §3.6)

| Alternative | Verdict | Why |
|---|---|---|
| Director auto-skip with WARNING | **ADOPTED** | Matches mental model. Prevents runtime crash. User-friendly. |
| Hard-fail (raise) | Rejected | Punishes the user for forgetting to disable evaluation. No recovery without config change. |
| Evaluator handles `test_path=None` gracefully | **Partially adopted** (defensive guard added) | Separation-of-concerns improvement for standalone usage, but the director auto-skip is the primary gate. |

### Ensemble handling (this proposal)

| Alternative | Verdict | Why |
|---|---|---|
| Disallow blending only, keep soft-voting + K-fold-OOF | **ADOPTED** | Precisely targets the one broken mode. Maximally permissive. |
| Disallow all ensembles | Rejected | Overly conservative. Blocks two modes that work correctly. |
| Internal-split fallback for blending | Rejected | Internal split is inaccessible and misleading for blending. |

---

## Open Risks / Future Work

| Item | Status |
|---|---|
| **Honest metrics via CV for no-holdout runs** | Out of scope. A future change could add `holdout_mode: "cv"` with K-fold cross-validation metrics. The string-typed `holdout_mode` flag is designed for this. |
| **Internal-split fallback for ensemble blending** | Out of scope. Would require surfacing the model's internal split as a separate DataFrame — invasive model-layer change. |
| **Web console Compare with `null` val_auc** | Low risk. `RunMetadata` already accepts `val_auc=None, val_f1=None`. The web console should handle null metrics gracefully, but this proposal does not change web console code. Verify during spec phase. |
| **Comparison mode in TrainingStep** | The comparison-mode code path also computes val metrics per model. The same guards (`if X_val is not None`) apply. Low risk but needs explicit test coverage. |

---

## Affected Areas

| File | Change Type | Summary |
|---|---|---|
| `src/energizados/core/steps/split.py` | Additive | Add `"none"` method branch; conditional path output (write train only) |
| `src/energizados/core/steps/training.py` | Additive guards | Make `val_path` optional; guard all val access; skip metrics/calibration; add `holdout_mode` to context |
| `src/energizados/core/schemas/schemas.py` | Additive | Add `"none"` to method enum |
| `src/energizados/core/builders/director.py` | Additive | Auto-skip evaluation when `method == "none"` |
| `src/energizados/evaluation/evaluator.py` | Additive | Defensive guard for missing `test_path` |
| `src/energizados/modeling/ensemble.py` | Additive | Improve blending `ValueError` into actionable `ConfigurationError` |

**Files NOT changed:** adapters.py, supervised_models.py, training_builder.py, split_builder.py, run_manager.py, config_validator.py. All changes are additive — no existing code path is removed.

---

## Rollback Strategy

All changes are additive and feature-gated by `method == "none"`. Rolling back means:

1. Revert the `"none"` enum value (schema rejects the config again).
2. Revert the split branch (no `"none"` dispatch).
3. The training/director/evaluator guards are no-ops when `val_path` is not `None` — they can remain or be reverted with zero behavioral impact on existing pipelines.

No data migration, no breaking config changes. Existing pipelines are unaffected.

---

## Success Criteria

1. A pipeline with `split.method: "none"` trains a model on 100% of data and produces a valid, loadable `model.pkl`.
2. No-holdout runs set `val_auc=None`, `val_f1=None`, `val_predictions_path=None`, `holdout_mode="none"` in context.
3. No-holdout runs with `evaluation.enabled: true` skip evaluation with a WARNING — no crash.
4. Soft-voting ensembles and K-fold-OOF stacking ensembles work in no-holdout mode.
5. Stacking with `use_val_as_oof=True` in no-holdout mode raises a clear `ConfigurationError` with actionable guidance.
6. **All existing tests pass unchanged** — zero backward-compatibility regressions.
7. Inference on a no-holdout-trained model works out-of-the-box.

---

## Glossary

| Term | Definition |
|---|---|
| **No-holdout training** | A training mode where the model trains on 100% of available labeled data, reserving no validation or test set. Early stopping uses an internal 10% split. No honest generalization metrics are reported. Activated via `split.method: "none"`. |
| **`holdout_mode`** | A Context key (string) indicating how the run handled held-out data. Values: `"none"` (no holdout reserved), `"standard"` (val split reserved, honest metrics reported). Extensible to future modes like `"cv"`. |
| **Internal split** | The `train_test_split(test_size=0.1, random_state=42)` that each model class performs inside `.train()` when `df_val is None`. Used for early-stopping callbacks only. NOT an independent generalization estimate. |
| **Blending** | A stacking strategy (`use_val_as_oof=True`) that uses a held-out val set's predictions as meta-learner training data. Incompatible with no-holdout training. |

**Note:** These terms should be added to `CONTEXT.md` during the spec phase, under a new "Training Modes" subsection in the Modeling section.

---

## Proposal Question Round

The following product questions are offered for user review before finalizing. Most decisions are pre-resolved; these address remaining product unknowns.

1. **Primary use case confirmation:** Is the primary motivation monthly/batch production deployment where hyperparameters are already decided from a prior eval experiment? Or is there another driving scenario (e.g., cold-start with limited data)?
2. **Web console Compare impact:** Should Compare runs with `null` val_auc against runs with real metrics, or should it filter them out? (This proposal doesn't change web console code, but the product behavior matters.)
3. **Audit trail expectation:** For a no-holdout production model, is it sufficient to record `holdout_mode: "none"` in `run_metadata.json`, or does the user need a more prominent artifact (e.g., a warning in the Run summary UI)?
4. **Calibration fallback:** Is shipping an uncalibrated model acceptable for production, or should the pipeline block no-holdout training when calibration is enabled in config? (Current decision: skip calibration with a warning.)
