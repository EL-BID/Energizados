# Exploration: Train Without Holdout

**Change:** `train-without-holdout`
**Date:** 2026-07-24
**Status:** Exploration complete

---

## 1. Problem Framing

The Energizados ML framework currently **REQUIRES** a validation split. `TrainingStep.execute()` raises `ValueError("train_path and val_path are required")` at line 244-245 of `training.py` when `val_path` is missing.

**Goal:** Support training a production model WITHOUT any holdout (no val/test reserved), so a user can train on ALL available data and get a usable model artifact for inference.

**Design decision (PRE-RESOLVED):** Early stopping uses an INTERNAL 10% split. All three model classes (`LGBMModel`, `CATModel`, `XGBModel`) already do `train_test_split(test_size=0.1, random_state=42)` inside `.train()` when `df_val is None`. This is the chosen approach; the exploration focuses on HOW to propagate it through the pipeline.

---

## 2. Recommended Config Surface

### Recommendation: `method: "none"` on SplitStep

Add a sixth split method value `"none"` to the existing `method` enum.

**Rationale (vs alternatives):**

| Alternative | Verdict | Why |
|---|---|---|
| `method: "none"` | **RECOMMENDED** | Deepest module. One config value, `SplitStep` already branches on `method`. Context gets `val_path=None, test_path=None`. All downstream steps adapt to `None`. Orthogonal to all other methods. |
| Make `val_period`/`test_period` optional in `time_series` | Rejected | Only works for `time_series` method. Leaks "train-on-all" semantics into period config. Shallow — just removes a guard, doesn't centralize. |
| `train_on_all: bool` flag | Rejected | Second config surface for the same concept. Conflicts with `method`. When `train_on_all=True` and `method=stratified`, which wins? Ambiguous. Violates one-concept-one-config. |

**Config example:**

```yaml
train:
  split:
    method: none          # ALL data → train; no val, no test
    input_path: data/processed/dataset.parquet
    target_column: target
  models:
    - type: lightgbm
  evaluation:
    enabled: false        # no test set to evaluate
```

### What `method: "none"` produces

- `SplitStep.execute()` puts the entire dataset into `train.parquet`.
- `val.parquet` and `test.parquet` are NOT written (or written as empty / sentinel — see risks below).
- Context keys `val_path` and `test_path` are set to `None`.
- Context key `train_path` points to the full-dataset parquet.

---

## 3. Blast Radius (File-by-File with Line Refs)

### 3.1 `src/energizados/core/steps/split.py` — SplitStep

**Current state:** 5 methods dispatched by `if/elif` on `self.method` inside `execute()` (lines 130-230). Each branch sets `train_df`, `val_df`, `test_df`. Lines 378-387 unconditionally write 3 parquet files. Lines 485-487 unconditionally return 3 path keys.

**Changes needed:**

1. Add `elif self.method == "none":` branch (before the final `else`):
   - `train_df = df.copy()`
   - `val_df = pd.DataFrame()`
   - `test_df = pd.DataFrame()`
   - No split logic needed.

2. **Path output (lines 378-387):** When `method == "none"`:
   - Write `train.parquet` as usual.
   - Set `val_path = None`, `test_path = None` (do NOT write empty parquets — writing empty files creates downstream `pd.read_parquet` edge cases).
   - `save_splits` still writes `train.parquet`; metadata records `n_val: 0, n_test: 0`.

3. **Context return (lines 485-487):** Return `val_path=None, test_path=None`.

4. **Logging (lines ~430-460):** Guard against empty-DataFrame `.value_counts()` on `val_df`/`test_df` (would produce empty dicts — safe, but log "No val/test (train-on-all mode)").

5. **`_inject_unlabeled_negatives`** (line ~395): Currently receives `val_df, test_df`. With empty DataFrames, `id_column` dedup set is empty — no rows excluded. Safe, no change needed.

6. **`get_output_keys`** (line 534): Currently returns `["train_path", "val_path", "test_path", "splits_dir"]`. No change — keys still exist, just `None`.

**No existing method branch changes.** Backward compatible by construction.

### 3.2 `src/energizados/core/steps/training.py` — TrainingStep.execute()

**Current state:**

- Lines 244-245: `if not self.train_path or not self.val_path: raise ValueError("train_path and val_path are required")`
- Line 255: `val_df = pd.read_parquet(self.val_path)` — unconditional val load.
- Lines 258-268: `X_val = val_df.drop(...)`, `y_val = val_df[...]` — unconditional val feature extraction.
- Lines 291-310: `columns_filter` applied to `X_val, y_val` unconditionally.
- Lines 312-325: datetime column drop applied to `X_val` unconditionally.
- Lines 355-365: `feature_engineering.transform(X_val)` — unconditional.
- Lines 390-420: Model training receives `X_val, y_val` — the model's internal 10% split only triggers if X_val is None, so currently it NEVER triggers (val is always provided).
- Lines 430-480: Val metrics (AUC, F1, proba stats, predictions parquet) — unconditional.
- Lines 550-580: Context return with `val_auc`, `val_f1`, `val_predictions_path`.

**Changes needed (additive, no removal of existing paths):**

1. **Guard (line 244):** Change condition to only require `train_path`:

   ```python
   if not self.train_path:
       raise ValueError("train_path is required")
   ```

   `val_path` becomes optional.

2. **Val load (line 255):** Make conditional:

   ```python
   val_df = pd.read_parquet(self.val_path) if self.val_path else None
   ```

   (test_df already handles `None` at line 256.)

3. **Val feature extraction (lines 258-268):** Guard:

   ```python
   X_val = val_df.drop(...) if val_df is not None else None
   y_val = val_df[...] if val_df is not None else None
   ```

4. **columns_filter (lines 291-310):** Guard `X_val`/`y_val` blocks with `if X_val is not None:`.

5. **Datetime drop (lines 312-325):** Guard `X_val` drop with `if X_val is not None:`.

6. **Feature engineering transform (line 355):** Guard: `X_val_transformed = fe.transform(X_val) if X_val is not None else None`.

7. **NaN diagnostics (lines 374-380):** Guard `val_nan` with `if X_val_transformed is not None:`.

8. **Model training (lines 390-420):** Pass `X_val=X_val_transformed, y_val=y_val` — when these are `None`, the model adapter's `.fit()` already handles it (passes `None` to `.train()`, which triggers the internal 10% split).

9. **Calibration (line 425-430):** `_apply_calibration` uses `X_val, y_val` for CalibratedClassifierCV. When val is None, **skip calibration** (log warning). Calibration needs held-out data; the internal split's data is in-sample for the final model.

10. **Val metrics (lines 430-480):** This is the CRITICAL honesty concern. When `val_df is None`:
    - The internal 10% split metrics are **in-sample for early stopping, NOT honest generalization**.
    - **Recommendation:** Set `val_auc = None`, `val_f1 = None`, skip `val_predictions.parquet`.
    - Set `val_predictions_path = None`.
    - Add a context flag: `"holdout_mode": "none"` (or `"has_honest_val": False`) so downstream (evaluator, run_manager) knows.
    - Log: `"Training in no-holdout mode. No honest validation metrics available. Internal 10% split used for early stopping only."`

11. **Comparison mode (lines 430-470):** Same guard — when val is None, set `val_metrics = None` per model.

12. **Context return (lines 550-580):** Return `val_auc=None, val_f1=None, val_predictions_path=None, holdout_mode="none"`.

13. **`validate_input` (lines 836-841):** Only require `train_path` to exist.

14. **`get_required_keys` (lines 844-846):** Return `["train_path"]` only (drop `val_path` requirement). **BUT** — to preserve backward compat, only do this when the step is explicitly in no-holdout mode. Simpler: always return `["train_path"]` since val is now optional.

### 3.3 `src/energizados/core/schemas/schemas.py` — SPLIT_SCHEMA

**Current state:** `SPLIT_SCHEMA["properties"]["method"]` enum is `["stratified", "random", "time_series", "group_based", "stratified_time"]` (lines ~37-39).

**Changes needed:**

1. Add `"none"` to the method enum.
2. The `if/then` conditional for `group_based` (lines ~78-80) stays as-is. No new conditional needed for `none` — it requires no extra fields.

### 3.4 `src/energizados/core/builders/training_builder.py` — TrainingBuilder

**Current state:** `build()` constructs `TrainingStep(...)` without passing `train_path`, `val_path`, or `test_path` (lines 50-60). These come from context via `SplitStep`.

**Changes needed:** None. The builder doesn't pass paths — they flow from context. When SplitStep sets `val_path=None` in context, TrainingStep picks it up via `context.get("val_path")` → `None`.

### 3.5 `src/energizados/core/builders/evaluation_builder.py` — EvaluationBuilder

**Current state:** `build()` constructs `DefaultEvaluator(...)` with `input_path=eval_config.get("input_path")` (line 56). When running in-pipeline, `input_path` is None and the evaluator reads `test_path` from context.

**Changes needed:** None directly. The gating happens at the **director** level (see 3.6).

### 3.6 `src/energizados/core/builders/director.py` — PipelineDirector.build()

**Current state (lines 215-230):** Evaluation is gated by `eval_config.get("enabled", False)`. If evaluation is enabled but there's no test_path, the evaluator will fail at runtime (`ValueError("No input_path provided and 'test_path' not found in context.")` — evaluator.py line ~84).

**Changes needed:**

1. When `method == "none"`, evaluation should be **auto-skipped** even if `enabled: true` — log a warning. OR: require the user to explicitly set `evaluation.enabled: false`.
2. **Recommendation:** Make it a **soft guard** in the director: if `split.method == "none"` and evaluation is enabled, log WARNING and skip the evaluation step (set it to None). This prevents runtime failures and matches the mental model (no test = nothing to evaluate).
3. Alternative: let the evaluator handle `test_path=None` gracefully (return early with a message). This is cleaner from a separation-of-concerns view but more invasive.

### 3.7 `src/energizados/evaluation/evaluator.py` — DefaultEvaluator

**Current state:** Line ~84: `if not input_path: raise ValueError(...)`. Line ~87: `if not Path(input_path).exists(): raise FileNotFoundError(...)`.

**Changes needed (defensive):** If we auto-skip in the director (3.6), the evaluator is never reached. But for standalone usage, add a guard at the top of `execute()`:

```python
if not input_path:
    logger.warning("No test_path available — skipping evaluation.")
    return {**ctx, "metrics": {}, "skipped": True, ...}
```

This makes the evaluator resilient rather than throwing.

### 3.8 `src/energizados/core/builders/run_manager.py` — RunMetadata

**Current state:** `_write_run_metadata` reads `context.get("val_auc")` and `context.get("val_f1")` (lines ~218-219). These are already `Optional[float]` with default `None`. The `RunMetadata` dataclass already supports `val_auc=None, val_f1=None`.

**Changes needed:** None. The metadata will simply record `val_auc: null, val_f1: null` for no-holdout runs. This is semantically correct.

### 3.9 `src/energizados/modeling/adapters.py` — Model Adapters

**Current state:** All adapter `.fit()` methods already accept `X_val=None, y_val=None` and pass through to `.train()`. The model `.train()` methods already do the internal 10% split when `df_val is None`.

**Changes needed:** None. This is the layer that's already ready.

### 3.10 `src/energizados/core/builders/split_builder.py` — SplitBuilder

**Current state:** `build()` constructs `SplitStep(method=split_config.get("method", "stratified"), ...)`.

**Changes needed:** None. `"none"` passes through as-is.

---

## 4. Honesty of Metrics — Critical Design Concern

**The internal 10% split is for EARLY STOPPING ONLY.** When `val=None`, the model reserves 10% of train for early-stopping callbacks, but:

- The 90% used for fitting is in-sample for the final model.
- The 10% used for early stopping is NOT independent — the model has effectively seen it.
- Reporting AUC/F1 from this split as "validation metrics" would be **misleading**.

**Recommendation:** `TrainingStep` must NOT report val_auc/val_f1 when in no-holdout mode. Set them to `None`. Add `holdout_mode` to context so consumers can distinguish.

The model's internal split metrics are **not surfaced** to the pipeline context — they only affect the `early_stopping` callback and `best_iteration_`. No code change needed at the model layer to suppress them.

---

## 5. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Empty parquet files cause downstream `pd.read_parquet` to fail | Medium | Don't write val/test parquets; set paths to `None` in context |
| CalibratedClassifierCV called with None val data | Medium | Guard `_apply_calibration` — skip when `X_val is None` |
| Evaluator crashes on `test_path=None` | Medium | Director auto-skips evaluation when `method=="none"`; add defensive guard in evaluator |
| Users misinterpret absent val_auc as model failure | Low | Add `holdout_mode` flag to context; log clear message |
| `columns_filter` applied to None val | Low | Guard with `if X_val is not None` |
| Ensemble fit receives None val | Medium | Check `EnsembleModel.fit` — uses `X_val` for OOF predictions when `use_val_as_oof=True`. Guard or disable `use_val_as_oof` when val is None. |
| `validate_input` / `get_required_keys` break pipeline dependency resolution | Medium | Relax `TrainingStep.get_required_keys` to `["train_path"]` only |

---

## 6. Dependencies

- No new Python packages needed.
- The internal `train_test_split(test_size=0.1)` in model classes is already present — no change to model layer.
- `jsonschema` validation: adding `"none"` to the enum is the only schema change.

---

## 7. Affected Files Summary

| File | Change Type | Lines Affected |
|---|---|---|
| `src/energizados/core/steps/split.py` | Add `none` method branch, conditional path output | ~378-390, ~485-487, new branch ~130 |
| `src/energizados/core/steps/training.py` | Make val optional throughout; guard all val access; skip metrics | ~244-245, ~255, ~258-268, ~291-310, ~312-325, ~355, ~374-380, ~390-480, ~550-580, ~836-846 |
| `src/energizados/core/schemas/schemas.py` | Add `"none"` to method enum | ~37-39 |
| `src/energizados/core/builders/director.py` | Auto-skip evaluation when `method=="none"` | ~215-230 |
| `src/energizados/evaluation/evaluator.py` | Defensive guard for missing test_path | ~84-87 |
| `src/energizados/modeling/ensemble.py` | Guard `X_val=None` in fit (if `use_val_as_oof`) | TBD — needs check |

**Files NOT changed:** adapters.py, supervised_models.py, training_builder.py, split_builder.py, run_manager.py, config_validator.py.

---

## 8. Test Strategy

### 8.1 New Tests (TDD — write FIRST)

**`tests/test_split.py` (or `test_split_none.py`):**

1. `test_split_method_none_all_data_in_train` — `SplitStep(method="none")` produces `train_path` with ALL rows, `val_path=None`, `test_path=None`.
2. `test_split_none_writes_train_parquet_only` — Only `train.parquet` is written; `val.parquet`/`test.parquet` not created.
3. `test_split_none_metadata` — `split_metadata.json` records `n_val: 0, n_test: 0`.
4. `test_split_none_backward_compat` — Existing methods still produce 3 parquets and 3 paths.

**`tests/test_training_step.py`:**
5. `test_training_no_holdout_succeeds` — `TrainingStep(train_path=..., val_path=None, ...)` completes without error.
6. `test_training_no_holdout_model_saved` — `model_path` exists and is loadable.
7. `test_training_no_holdout_val_metrics_none` — `result["val_auc"] is None`, `result["val_f1"] is None`.
8. `test_training_no_holdout_holdout_mode_flag` — `result["holdout_mode"] == "none"`.
9. `test_training_no_holdout_no_val_predictions` — `result["val_predictions_path"] is None`.
10. `test_training_with_val_still_works` — Existing path: val provided → val_auc/val_f1 are floats (regression guard).

**`tests/test_config_schemas.py`:**
11. `test_split_method_none_valid` — Config with `method: none` passes schema validation.
12. `test_split_method_none_no_extra_fields_required` — No group_column/date_column needed.

**`tests/test_pipeline*.py` (integration):**
13. `test_pipeline_no_holdout_eval_skipped` — Full pipeline with `method: none` and `evaluation.enabled: true` skips evaluation gracefully.

### 8.2 Existing Tests that Guard Backward Compat (MUST NOT BREAK)

- `test_training_step.py::TestTrainingStepSingleModel::*` — All single-model tests provide val_path and expect val_auc/val_f1.
- `test_training_step.py::TestTrainingStepEnsemble::*` — Ensemble tests with val.
- `test_training_step.py::TestTrainingStepComparisonMode::*` — Comparison mode with val_metrics.
- `test_e2e_pipeline.py::*` — End-to-end pipeline with stratified split.
- `test_config_schemas.py::test_split_*` — All existing split validation tests.
- `test_integration.py::*` — Pipeline build tests.

### 8.3 Test Markers

All new tests: `@pytest.mark.unit` (split, schema, training step unit tests) or `@pytest.mark.integration` (pipeline-level). Run with `pytest tests/ --strict-markers`.

---

## 9. Open Questions for Proposal Phase

1. Should `holdout_mode` be a string (`"none"`, `"standard"`) or a boolean (`has_honest_val`)?
2. When `method="none"` and evaluation is enabled, should we hard-skip (log warning) or hard-fail (raise error)?
3. Should `EnsembleModel.fit` handle `X_val=None` by falling back to internal split, or should ensembles be disallowed in no-holdout mode?
4. Should inference work out-of-the-box with a no-holdout model? (It should — model is a model regardless of how it was trained.)
