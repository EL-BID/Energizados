# Tasks: Train Without Holdout

**Change:** `train-without-holdout`
**Status:** Tasks
**Depends on:** `proposal.md`, `specs/no-holdout-training/spec.md`, `design.md`

---

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~450–550 (code ~130–180, tests ~350–400) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | single PR (feature is coherent; partial states are non-functional) |
| Delivery strategy | ask-on-risk |
| Chain strategy | size-exception |

```text
Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium
```

**Rationale:** All six source files form one indivisible feature — no-holdout training end-to-end. Shipping schema + split without the training guards produces a pipeline that crashes on `val_path=None`; shipping training guards without split/director/evaluator is incomplete. The changes are additive (zero deletions of existing code paths; Phase D indent is the largest diff contributor). A single PR with a size exception is the right call; chained PRs would ship non-functional partial states.

---

## Strict TDD Mode

**Active.** Test runner: `pytest tests/`. Markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow` (`--strict-markers`).

Every batch follows: **RED** (write failing test) → **GREEN** (minimal code to pass) → commit. Tests and their implementation go in the **same commit** (never test-only then code-only). Refactoring is deferred to the review stage.

Test names and file mapping come directly from design §6.1 — do not rename.

---

## Batch Dependency Graph

```
A (schema)           — no deps; unlocks config validation
  └─ B (split)        — needs schema to accept "none"
       └─ C1 (train input)  — needs split to produce val_path=None
            ├─ C2 (train metrics/context)  — needs C1 guards
            └─ C3 (train calibration)      — needs C1 guards

D (ensemble)   — depends on C1 (fail-fast location in training.py after G1–G8)
E (director)   — depends on A (reads split.method from config)
F (evaluator)  — independent (standalone guard)
```

E and F can be done in any order after A. D must come after C1.

---

## Batch A — Schema: Accept split method "none"

**FR:** FR1 (schema scenarios)
**Files:** `src/energizados/core/schemas/schemas.py`, `tests/test_config_schemas.py`

### RED — Write failing tests

| Test name | File | Marker | Asserts |
|---|---|---|---|
| `test_split_method_none_valid` | `tests/test_config_schemas.py` | `@pytest.mark.unit` | Config with `train.split.method: "none"` validates without error |
| `test_split_method_none_no_extra_fields` | `tests/test_config_schemas.py` | `@pytest.mark.unit` | Config with `method: "none"` passes WITHOUT `group_column` or `date_column` |

Run: `pytest tests/test_config_schemas.py::test_split_method_none_valid tests/test_config_schemas.py::test_split_method_none_no_extra_fields` → **must FAIL** (schema rejects unknown enum value).

### GREEN — Minimal implementation

Edit `src/energizados/core/schemas/schemas.py` (~line 44):

Add `"none"` to `SPLIT_SCHEMA["properties"]["method"]["enum"]`:

```python
"enum": ["stratified", "random", "time_series", "group_based", "stratified_time", "none"],
```

No new `if/then` conditional — `"none"` requires no extra fields.

Run: same pytest command → **must PASS**.

### Commit

```
feat(schema): accept split method none
```

---

## Batch B — SplitStep: No-holdout branch

**FR:** FR1 (split scenarios)
**Files:** `src/energizados/core/steps/split.py`, `tests/test_split.py`
**Depends on:** Batch A

### RED — Write failing tests

| Test name | File | Marker | Asserts |
|---|---|---|---|
| `test_split_method_none_all_data_in_train` | `tests/test_split.py` | `@pytest.mark.unit` | `train_path` parquet contains all N input rows; `val_path` is `None`; `test_path` is `None` |
| `test_split_none_writes_train_parquet_only` | `tests/test_split.py` | `@pytest.mark.unit` | `train.parquet` exists; `val.parquet` does NOT exist; `test.parquet` does NOT exist |
| `test_split_none_metadata_zero_val_test` | `tests/test_split.py` | `@pytest.mark.unit` | Split metadata records `n_val: 0` and `n_test: 0` |

Run: `pytest tests/test_split.py::test_split_method_none_all_data_in_train tests/test_split.py::test_split_none_writes_train_parquet_only tests/test_split.py::test_split_none_metadata_zero_val_test` → **must FAIL**.

### GREEN — Minimal implementation

**1. New `"none"` branch** (insert before the final `else:` at ~line 315):

```python
elif self.method == "none":
    logger.info("Split method 'none': assigning all data to train (no holdout).")
    train_df = df.copy()
    val_df = pd.DataFrame()
    test_df = pd.DataFrame()
```

**2. Conditional parquet write** (~lines 378–383):

```python
if self.save_splits:
    train_df.to_parquet(train_path, index=False)
    if self.method != "none":
        val_df.to_parquet(val_path, index=False)
        test_df.to_parquet(test_path, index=False)
```

**3. Conditional return** (~lines 485–492):

```python
return {
    **context,
    "train_path": str(train_path),
    "val_path": str(val_path) if self.method != "none" else None,
    "test_path": str(test_path) if self.method != "none" else None,
    "splits_dir": str(self.splits_dir),
}
```

**4. Metadata** — no change needed. Empty DataFrames produce `n_val: 0`, `n_test: 0`, empty `target_distribution` dicts. All safe.

Run: same pytest command → **must PASS**.

### Commit

```
feat(split): add no-holdout method
```

---

## Batch C1 — TrainingStep: Optional val_path input guards

**FR:** FR2
**Files:** `src/energizados/core/steps/training.py`, `tests/test_training_step.py`
**Depends on:** Batch B

This batch makes `val_path` optional and guards all val-data access so `X_val` and `y_val` are `None` when `val_path` is not provided. It covers design guards G1–G8 and the `validate_input` / `get_required_keys` changes.

### RED — Write failing tests

| Test name | File | Marker | Asserts |
|---|---|---|---|
| `test_training_no_holdout_succeeds` | `tests/test_training_step.py` | `@pytest.mark.unit` | `execute()` with `val_path=None` completes without error; `model_path` points to a loadable `model.pkl` |
| `test_training_no_holdout_model_receives_none_val` | `tests/test_training_step.py` | `@pytest.mark.unit` | Model `.fit()` receives `X_val=None`, `y_val=None`; internal 10% split is triggered |

Use a synthetic dataset fixture (~200 rows, 5 features, binary target). The split `method="none"` fixture from Batch B tests can be reused or shared via `conftest.py`.

Run: `pytest tests/test_training_step.py::test_training_no_holdout_succeeds tests/test_training_step.py::test_training_no_holdout_model_receives_none_val` → **must FAIL**.

### GREEN — Minimal implementation

**Import** (top of file, ~line 12):

```python
from energizados.core.exceptions import ConfigurationError
```

**G1 — Input guard** (~line 244):

```python
if not self.train_path:
    raise ValueError("train_path is required")
```

(Drop the `or not self.val_path` clause and its mention from the message.)

**G2 — Val load** (~line 255):

```python
val_df = pd.read_parquet(self.val_path) if self.val_path else None
```

**G3 — Val feature extraction** (~lines 263–264):

```python
X_val = val_df.drop(columns=[self.target_column]) if val_df is not None else None
y_val = val_df[self.target_column] if val_df is not None else None
```

**G4 — columns_filter val block** (~lines 296–300): Wrap existing val lines inside `if X_val is not None:`.

**G5 — datetime drop val block** (~lines 306–307): Guard with `if X_val is not None:` inside the existing `if cols_to_drop:` block.

**G6 — FE transform val** (~line 367):

```python
X_val_transformed = feature_engineering.transform(X_val) if X_val is not None else None
```

**G7 — Residual datetime drop** (~lines 378–380): Guard with `if X_val_transformed is not None:`.

**G8 — NaN diagnostics** (~lines 385–386):

```python
val_nan = X_val_transformed.isnull().sum().sum() if X_val_transformed is not None else 0
```

**validate_input** (~line 836): Make `val_path` optional — when present, file must exist; when absent, return `True`.

**get_required_keys** (~line 844): Return `["train_path"]` only when `train_path` is missing (drop `val_path` from required list).

**Transformed shape logging** (~lines 382–384): Guard `X_val_transformed` and `X_test_transformed` logging with `is not None` checks.

Run: same pytest command → **must PASS**.

### Commit

```
feat(training): make val_path optional in input guards
```

---

## Batch C2 — TrainingStep: No-holdout metrics and holdout_mode

**FR:** FR3
**Files:** `src/energizados/core/steps/training.py`, `tests/test_training_step.py`
**Depends on:** Batch C1

This batch restructures Phase D (val metrics computation) into a conditional branch and adds `holdout_mode` to the context. It covers design guards G10–G13.

### RED — Write failing tests

| Test name | File | Marker | Asserts |
|---|---|---|---|
| `test_training_no_holdout_metrics_none` | `tests/test_training_step.py` | `@pytest.mark.unit` | `val_auc=None`, `val_f1=None`, `val_predictions_path=None`, `holdout_mode="none"` |
| `test_training_no_holdout_logs_honesty_message` | `tests/test_training_step.py` | `@pytest.mark.unit` | Log contains message stating no honest validation metrics available and internal split is for early stopping only |
| `test_training_with_val_sets_holdout_mode_standard` | `tests/test_training_step.py` | `@pytest.mark.unit` | Standard run (val_path provided) sets `holdout_mode="standard"`; `val_auc`/`val_f1` are floats |
| `test_training_comparison_mode_no_holdout_metrics_none` | `tests/test_training_step.py` | `@pytest.mark.unit` | Comparison mode with `val_path=None`: per-model val metrics are `None` |

Run: `pytest tests/test_training_step.py::test_training_no_holdout_metrics_none tests/test_training_step.py::test_training_no_holdout_logs_honesty_message tests/test_training_step.py::test_training_with_val_sets_holdout_mode_standard tests/test_training_step.py::test_training_comparison_mode_no_holdout_metrics_none` → **must FAIL**.

### GREEN — Minimal implementation

**G10 — Phase D restructure** (~lines 465–510):

Wrap the existing val-metrics block inside `if X_val_transformed is not None:`. Add `else:` branch:

```python
else:
    logger.info(
        "Training in no-holdout mode. No honest validation metrics available. "
        "Internal 10% split used for early stopping only."
    )
    val_proba = None
    val_auc = None
    val_f1 = None
    if len(self.models_configs) > 1 and not self.ensemble_config:
        val_metrics = {name: {"auc": None, "f1": None} for name in names}
    else:
        val_metrics = None
```

> **Note on `%` formatting:** The design uses `%%` in log strings. In Python logging, `%%` only produces `%` when %-style formatting with args is used. This call has no args (plain string), so `%%` would appear literally. Use single `%` in the message.

**G11 — val_proba stats logging** (~lines 492–500): Guard with `if val_proba is not None:`.

**G12 — Val predictions save** (~lines 496–501): Guard with `if X_val is not None and val_proba is not None:`; set `val_predictions_path = None` in the else.

**G13 — Context return** (~lines 503–530): Add `"holdout_mode": "none" if X_val_transformed is None else "standard"` to the `result` dict construction (before the comparison/single-model branch).

Run: same pytest command → **must PASS**.

### Commit

```
feat(training): report None metrics and holdout_mode in no-holdout
```

---

## Batch C3 — TrainingStep: Skip calibration without val

**FR:** FR7
**Files:** `src/energizados/core/steps/training.py`, `tests/test_training_step.py`
**Depends on:** Batch C1

Covers design guard G14 — the calibration skip in `_train_single_model`.

### RED — Write failing test

| Test name | File | Marker | Asserts |
|---|---|---|---|
| `test_training_no_holdout_calibration_skipped` | `tests/test_training_step.py` | `@pytest.mark.unit` | With `val_path=None` and calibration enabled: calibration is skipped; warning is logged; model ships uncalibrated |

Run: `pytest tests/test_training_step.py::test_training_no_holdout_calibration_skipped` → **must FAIL**.

### GREEN — Minimal implementation

**G14 — Calibration skip** in `_train_single_model` (~line 655):

```python
if calibration_config.get("enabled", False):
    if X_val is not None:
        model = self._apply_calibration(model, model_type, X_val, y_val, calibration_config)
        logger.info(f"Applied probability calibration to model '{name}'")
    else:
        logger.warning(
            f"Calibration enabled for model '{name}' but no validation data available "
            "(holdout_mode='none'). Skipping calibration. Model will ship uncalibrated."
        )
```

Run: same pytest command → **must PASS**.

### Commit

```
feat(training): skip calibration in no-holdout mode
```

---

## Batch D — Ensemble: ConfigurationError for blending without val

**FR:** FR6
**Files:** `src/energizados/modeling/ensemble.py`, `src/energizados/core/steps/training.py`, `tests/test_ensemble.py`
**Depends on:** Batch C1 (fail-fast location needs `X_val_transformed is None` from C1 guards)

Two changes: (1) upgrade the standalone `EnsembleModel` blending error, (2) add fail-fast in `TrainingStep.execute()` before base model training.

### RED — Write failing tests

| Test name | File | Marker | Asserts |
|---|---|---|---|
| `test_ensemble_blending_no_val_raises_config_error` | `tests/test_ensemble.py` | `@pytest.mark.unit` | Ensemble with `method="stacking"`, `use_val_as_oof=True`, `.fit()` with `X_val=None` raises `ConfigurationError`; message mentions at least one actionable alternative |
| `test_ensemble_soft_voting_no_holdout_succeeds` | `tests/test_ensemble.py` | `@pytest.mark.unit` | Ensemble with `method="soft_voting"`, `.fit()` with `X_val=None` fits without error |
| `test_ensemble_kfold_oof_no_holdout_succeeds` | `tests/test_ensemble.py` | `@pytest.mark.unit` | Ensemble with `method="stacking"`, `use_val_as_oof=False`, `.fit()` with `X_val=None` fits using K-fold CV |

Run: `pytest tests/test_ensemble.py::test_ensemble_blending_no_val_raises_config_error tests/test_ensemble.py::test_ensemble_soft_voting_no_holdout_succeeds tests/test_ensemble.py::test_ensemble_kfold_oof_no_holdout_succeeds` → **must FAIL** (first test expects `ConfigurationError`, currently raises `ValueError`; second/third may pass or fail depending on existing code).

### GREEN — Minimal implementation

**1. ensemble.py import** (top of file):

```python
from energizados.core.exceptions import ConfigurationError
```

**2. ensemble.py `_fit_meta_learner`** (~line 128): Upgrade `ValueError` to `ConfigurationError` with actionable message:

```python
raise ConfigurationError(
    "Ensemble blending (use_val_as_oof=True) requires a validation split, "
    "but X_val is None. Options: (a) provide X_val and y_val, "
    "(b) switch to use_val_as_oof=False (K-fold OOF stacking), or "
    "(c) use method='soft_voting'."
)
```

**3. training.py fail-fast** (G9, insert before model dispatch at ~line 434, after `names = self._resolve_model_names(...)`):

```python
if (
    self.ensemble_config
    and self.ensemble_config.get("use_val_as_oof", True)
    and X_val_transformed is None
):
    raise ConfigurationError(
        "Ensemble blending (use_val_as_oof=True) requires a validation split, "
        "but no validation data is available (split.method='none'). "
        "Options: (a) provide a validation split (split.method != 'none'), "
        "(b) switch to K-fold OOF stacking (use_val_as_oof: false), or "
        "(c) use soft_voting ensemble method."
    )
```

Run: same pytest command → **must PASS**.

### Commit

```
feat(ensemble): raise ConfigurationError for blending without val
```

---

## Batch E — Director: Auto-skip evaluation in no-holdout mode

**FR:** FR4
**Files:** `src/energizados/core/builders/director.py`, `tests/test_pipeline.py`
**Depends on:** Batch A (reads `split.method` from config)

### RED — Write failing test

| Test name | File | Marker | Asserts |
|---|---|---|---|
| `test_pipeline_no_holdout_eval_skipped` | `tests/test_pipeline.py` | `@pytest.mark.integration` | Pipeline with `split.method="none"` and `evaluation.enabled=true`: no evaluator Step in pipeline; WARNING logged; no exception raised |

Run: `pytest tests/test_pipeline.py::test_pipeline_no_holdout_eval_skipped` → **must FAIL**.

### GREEN — Minimal implementation

Edit `src/energizados/core/builders/director.py`, Step 4 (evaluation section, ~lines 215–230):

After `if eval_config.get("enabled", False):`, add the method check before constructing the evaluator:

```python
split_method = split_config.get("method", "stratified")
if split_method == "none":
    logger.warning(
        "Evaluation is enabled but split.method is 'none' — "
        "no test set available. Skipping evaluation step automatically."
    )
else:
    # existing evaluation builder code — unchanged, nested in else
    eval_output_dir = (
        str(self._run_dir / "reports" / "evaluation") if self._run_dir else None
    )
    experiment_description = self.config.get("train", {}).get("description")
    eval_builder = EvaluationBuilder(
        eval_config, eval_output_dir, experiment_description=experiment_description
    )
    eval_step = eval_builder.build()
    if eval_step is not None:
        pipeline.add_step(eval_step)
```

The existing evaluation code moves inside `else:` — byte-identical for all methods except `"none"`.

Run: same pytest command → **must PASS**.

### Commit

```
feat(director): auto-skip evaluation in no-holdout mode
```

---

## Batch F — Evaluator: Defensive guard for missing test_path

**FR:** FR5
**Files:** `src/energizados/evaluation/evaluator.py`, `tests/test_evaluator.py`
**Depends on:** none (standalone guard)

### RED — Write failing test

| Test name | File | Marker | Asserts |
|---|---|---|---|
| `test_evaluator_no_test_path_skips_gracefully` | `tests/test_evaluator.py` | `@pytest.mark.unit` | `DefaultEvaluator` with no `test_path` in context: returns `skipped=True`, `metrics={}`; warning logged; no exception |

Run: `pytest tests/test_evaluator.py::test_evaluator_no_test_path_skips_gracefully` → **must FAIL** (currently raises `ValueError`).

### GREEN — Minimal implementation

Edit `src/energizados/evaluation/evaluator.py`, `execute()` (~lines 130–135):

Replace the `ValueError` with an early return:

```python
if not input_path:
    logger.warning(
        "No test_path available in context — skipping evaluation. "
        "(This is expected in no-holdout training mode.)"
    )
    return {
        **ctx,
        "metrics": {},
        "plots": {},
        "reports": {},
        "evaluation_dir": str(self.output_dir),
        "skipped": True,
    }
```

The `FileNotFoundError` check for a non-existent path (~line 134) stays unchanged.

Run: same pytest command → **must PASS**.

### Commit

```
feat(evaluator): defensive guard for missing test_path
```

---

## Post-Implementation: Full Regression Run

After all batches are committed:

```bash
pytest tests/ --strict-markers
```

**Must pass:** all 17 new tests + all existing tests (design §6.2 regression guards). Zero backward-compatibility failures.

Key regression targets:

- `tests/test_training_step.py::TestTrainingStepSingleModel::*` — single model with val → floats
- `tests/test_training_step.py::TestTrainingStepEnsemble::*` — ensemble with val → unchanged
- `tests/test_training_step.py::TestTrainingStepComparisonMode::*` — comparison with val_metrics
- `tests/test_split.py::test_split_*` (existing) — all existing split methods produce 3 parquets + 3 paths
- `tests/test_e2e_pipeline.py::*` — end-to-end pipeline with stratified split

---

## Conventional Commits Summary

| # | Commit message | Batch |
|---|---|---|
| 1 | `feat(schema): accept split method none` | A |
| 2 | `feat(split): add no-holdout method` | B |
| 3 | `feat(training): make val_path optional in input guards` | C1 |
| 4 | `feat(training): report None metrics and holdout_mode in no-holdout` | C2 |
| 5 | `feat(training): skip calibration in no-holdout mode` | C3 |
| 6 | `feat(ensemble): raise ConfigurationError for blending without val` | D |
| 7 | `feat(director): auto-skip evaluation in no-holdout mode` | E |
| 8 | `feat(evaluator): defensive guard for missing test_path` | F |

Each commit includes its tests (never test-only then code-only). No AI attribution. Scope follows `feat(<module>):` convention.

---

## Design Notes for Apply Phase

1. **`%` in log strings:** Use single `%` (not `%%`) in plain-string `logger.info(...)` calls without format args. See design §8.5.
2. **`holdout_mode` in `get_output_keys()`:** Add `"holdout_mode"` to the return list (design §7 risk 5).
3. **`val_metrics` shape in no-holdout comparison mode:** Design chooses `{name: {"auc": None, "f1": None}}`. If downstream proves indifferent, simplify to `{}`.
4. **CONTEXT.md:** Glossary update (no-holdout training, `holdout_mode`, internal split, blending) is tracked as a task per spec out-of-scope — not part of the code commits. Add as a docs commit after all code batches.
5. **`use_val_as_oof` default:** The fail-fast checks `self.ensemble_config.get("use_val_as_oof", True)` — default `True` means blending configs trigger the error by default. This is correct (fail-safe).
