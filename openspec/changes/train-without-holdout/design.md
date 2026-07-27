# Design: Train Without Holdout

**Change:** `train-without-holdout`
**Status:** Design
**Depends on:** `proposal.md`, `specs/no-holdout-training/spec.md`, `exploration.md`

---

## 1. Architecture Overview

### 1.1 Standard Pipeline (val present) — unchanged

```
Config (method=stratified)
  │
  ▼
SplitStep ──── writes train.parquet, val.parquet, test.parquet
  │            returns train_path, val_path, test_path
  ▼
TrainingStep ─ loads train + val → feature engineering fit/transform
  │             → model.fit(X_train, y_train, X_val, y_val)
  │             → calibration on val
  │             → val_auc, val_f1 computed → val_predictions.parquet
  │             → context: holdout_mode="standard", val_auc=0.xx, val_f1=0.xx
  ▼
Evaluator ──── reads test_path → metrics, plots, reports
  │
  ▼
RunManager ─── reads val_auc, val_f1 from context → run_metadata.json
```

### 1.2 No-Holdout Pipeline (val absent) — new path

```
Config (method="none")
  │
  ▼
SplitStep ──── writes ONLY train.parquet (entire dataset)
  │            returns train_path, val_path=None, test_path=None
  ▼
TrainingStep ─ loads train only → feature engineering fit/transform
  │             → model.fit(X_train, y_train, X_val=None, y_val=None)
  │                                  └── adapter triggers internal 10% split
  │             → calibration SKIPPED (no held-out data)
  │             → val_auc=None, val_f1=None, val_predictions_path=None
  │             → context: holdout_mode="none"
  │             → fail-fast ConfigurationError if blending requested
  ▼
Director ───── split.method=="none" → SKIP evaluation step (WARNING)
  │            (Evaluator never built — no Step added to pipeline)
  ▼
RunManager ─── reads val_auc=None, val_f1=None → run_metadata.json
```

The key architectural property: **the no-holdout path is the standard path with `None` propagated through it**. Every component reacts to `None` data rather than following a separate branch. The only top-level branching decision is the director's evaluation skip (a construction-time concern) and the blending ConfigurationError (a fail-fast guard).

---

## 2. Resolved Design Questions

### 2.1 DQ-1: Where is the blending ConfigurationError detected?

**Decision: Both — fail-fast in TrainingStep.execute() AND defense-in-depth in EnsembleModel._fit_meta_learner.**

**Rationale:**

| Seam | What it catches | Cost avoided | Scope |
|---|---|---|---|
| **TrainingStep.execute()** (primary) | Config-level: `ensemble_config.use_val_as_oof=True` + `X_val=None` | Avoids training all base models before discovering the conflict | Pipeline usage |
| **EnsembleModel._fit_meta_learner** (defense-in-depth) | Runtime-level: `X_val is None` when blending requested | Protects standalone EnsembleModel API usage | Direct API |

The fail-fast in TrainingStep is possible because it has access to `self.ensemble_config` (which contains `use_val_as_oof`) and can check it *before* calling `_train_ensemble()`, which trains all base models first. By the time `_fit_meta_learner` raises, all base models are already fitted — wasted computation.

The defense-in-depth upgrade in EnsembleModel catches the case where someone constructs an `EnsembleModel` directly (not via TrainingStep) and calls `.fit()` with `X_val=None`. The current code raises a bare `ValueError("use_val_as_oof=True requires X_val and y_val.")` at line ~128. This is upgraded to `ConfigurationError` with the actionable message.

**Placement of the TrainingStep fail-fast:** After feature engineering transform (so `X_val_transformed` is known to be `None`) and before the model training dispatch section (lines ~436). This is line ~434 in the current code, right after `names = self._resolve_model_names(self.models_configs)`.

```python
# Fail-fast: blending requires validation data
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

**The EnsembleModel defense-in-depth** upgrades the existing `ValueError` at `_fit_meta_learner` line ~128:

```python
# Before:
raise ValueError("use_val_as_oof=True requires X_val and y_val.")

# After:
raise ConfigurationError(
    "Ensemble blending (use_val_as_oof=True) requires a validation split, "
    "but X_val is None. Options: (a) provide X_val and y_val, "
    "(b) switch to use_val_as_oof=False (K-fold OOF stacking), or "
    "(c) use method='soft_voting'."
)
```

This requires importing `ConfigurationError` in `ensemble.py` (currently not imported).

**Why `ConfigurationError` and not a new exception:** `ConfigurationError` is part of the public exception hierarchy (`ConfigurationError(EnergizadosError)` — `src/energizados/core/exceptions.py:88`). Blending-without-val is a configuration mistake, not a runtime failure. Users who catch `EnergizadosError` at the pipeline level will catch it.

### 2.2 DQ-2: Guard pattern in TrainingStep.execute()

**Decision: Inline `None` guards at each point — no helper, no separate branch.**

**Rationale (deep-module lens):**

- **Inline guards are the deepest interface.** The guard `if X_val is not None:` is self-documenting at the exact point where val is consumed. No new abstraction, no indirection.
- **A helper would be shallow.** A hypothetical `_process_val_data(val_df, fe, ...)` would just move `if val is not None` into a function — same interface surface, more indirection, no leverage (callers still need to handle the None return).
- **A separate "no-holdout branch" would double the logic.** Two code paths for the same pipeline step risks drift. The val-present path must be byte-identical; a branch makes this an invariant to maintain rather than a property of construction.
- **Backward compat is automatic.** When `val_path` is provided, `X_val` is not `None`, every guard evaluates to `True`, and the existing code runs unchanged. Zero behavioral diff.

**Guard inventory (13 points in `execute()` + 1 in `_train_single_model`):**

| # | Location (approx. line) | Current code | Guard |
|---|---|---|---|
| G1 | 244 | `if not self.train_path or not self.val_path:` | Change to `if not self.train_path:` |
| G2 | 255 | `val_df = pd.read_parquet(self.val_path)` | `val_df = pd.read_parquet(self.val_path) if self.val_path else None` |
| G3 | 263-264 | `X_val = val_df.drop(...)`, `y_val = val_df[...]` | Add `if val_df is not None else None` to each |
| G4 | 296-300 | columns_filter on `X_val, y_val` | Wrap with `if X_val is not None:` |
| G5 | 306-307 | datetime drop on `X_val` | Guard inside `if cols_to_drop:` with `if X_val is not None:` |
| G6 | 367 | `X_val_transformed = fe.transform(X_val)` | Add `if X_val is not None else None` |
| G7 | 378-380 | residual datetime drop on `X_val_transformed` | Guard with `if X_val_transformed is not None:` |
| G8 | 385-386 | `val_nan = X_val_transformed.isnull().sum().sum()` | `val_nan = ... if X_val_transformed is not None else 0` |
| G9 | ~434 | (new code) | Fail-fast ConfigurationError for blending (see DQ-1) |
| G10 | 465-510 | Phase D: val metrics block | Split into `if X_val_transformed is not None:` / `else:` |
| G11 | 492-500 | val_proba stats logging | Guard with `if val_proba is not None:` |
| G12 | 496-501 | val_predictions.parquet save | Guard with `if X_val is not None and val_proba is not None:` |
| G13 | 503-530 | context return | Add `holdout_mode` key; variables already None |
| G14 | 655 (in `_train_single_model`) | calibration | Add `and X_val is not None` condition + warning log |

**Phase D restructure (G10) — the most significant change:**

```python
# Phase D: Quick val metrics
from sklearn.metrics import f1_score, roc_auc_score

if X_val_transformed is not None:
    # ---- EXISTING CODE UNCHANGED (comparison mode or single model) ----
    # ... lines 467-510 run exactly as today ...
    # Computes val_proba, val_auc, val_f1, val_metrics as before.
else:
    # ---- No-holdout mode: no honest val metrics ----
    logger.info(
        "Training in no-holdout mode. No honest validation metrics available. "
        "Internal 10%% split used for early stopping only."
    )
    val_proba = None
    val_auc = None
    val_f1 = None
    if len(self.models_configs) > 1 and not self.ensemble_config:
        val_metrics = {name: {"auc": None, "f1": None} for name in names}
    else:
        val_metrics = None
```

The existing Phase D code (comparison mode loop + single model branch) becomes the `if X_val_transformed is not None:` branch — byte-identical. The `else:` branch is pure additive.

### 2.3 DQ-3: Director auto-skip mechanism

**Decision: Insert a `split.method == "none"` check in `build()` right before the evaluation step construction (Step 4, lines ~215-230), using the already-resolved `split_config` variable.**

**Rationale:**

The director already resolves `split_config` at Step 2 (line ~191):

```python
split_config = self.config.get("train", {}).get("split", {})
if not split_config:
    split_config = self.config.get("split", {})
```

This same variable is in scope at Step 4. The check reads from config, not from runtime context — this is correct because the director builds the pipeline *before* any step executes. SplitStep hasn't run yet when the director decides whether to add the evaluator.

**Exact change (Step 4, lines ~215-230):**

```python
# Step 4: Evaluation
eval_config = self.config.get("train", {}).get("evaluation", {})
if not eval_config:
    eval_config = self.config.get("evaluation", {})
if eval_config.get("enabled", False):
    # Auto-skip evaluation when no test set is available (no-holdout mode)
    split_method = split_config.get("method", "stratified")
    if split_method == "none":
        logger.warning(
            "Evaluation is enabled but split.method is 'none' — "
            "no test set available. Skipping evaluation step automatically."
        )
    else:
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

The existing evaluation code is nested inside an `else:` block — byte-identical behavior for all methods except `"none"`. No step is added to the pipeline, so `pipeline.run()` never invokes the evaluator.

---

## 3. Component-by-Component Design

### 3.1 `src/energizados/core/schemas/schemas.py`

**Change type:** Additive (one enum value).

| Line | Change |
|---|---|
| ~44 | Add `"none"` to `SPLIT_SCHEMA["properties"]["method"]["enum"]` |

```python
# Before:
"enum": ["stratified", "random", "time_series", "group_based", "stratified_time"],

# After:
"enum": ["stratified", "random", "time_series", "group_based", "stratified_time", "none"],
```

No new `if/then` conditional needed — `"none"` requires no extra fields (unlike `group_based` which requires `group_column`). The existing `if/then` at line ~78 only triggers for `group_based`.

### 3.2 `src/energizados/core/steps/split.py`

**Change type:** Additive (one new branch + conditional output).

#### 3.2.1 New `"none"` branch (insert before `else:` at line 315)

```python
elif self.method == "none":
    logger.info("Split method 'none': assigning all data to train (no holdout).")
    train_df = df.copy()
    val_df = pd.DataFrame()
    test_df = pd.DataFrame()
```

No split logic needed. `val_df` and `test_df` are empty DataFrames (not `None`) so all downstream metadata/logging code works without additional guards — `.value_counts()` returns empty dicts, `len()` returns 0.

#### 3.2.2 Conditional parquet write (lines ~378-383)

```python
if self.save_splits:
    train_df.to_parquet(train_path, index=False)
    if self.method != "none":
        val_df.to_parquet(val_path, index=False)
        test_df.to_parquet(test_path, index=False)
```

When `method == "none"`, only `train.parquet` is written. `val.parquet` and `test.parquet` are NOT created.

#### 3.2.3 Conditional return (lines ~485-492)

```python
return {
    **context,
    "train_path": str(train_path),
    "val_path": str(val_path) if self.method != "none" else None,
    "test_path": str(test_path) if self.method != "none" else None,
    "splits_dir": str(self.splits_dir),
}
```

#### 3.2.4 Metadata (no change needed)

The metadata block at lines ~389-397 already records `n_val: len(val_df)` and `n_test: len(test_df)`. With empty DataFrames, these are `0` — exactly what the spec requires (scenario: "split metadata records zero val and test"). The `target_distribution` for val/test will be empty dicts. The `else:` metadata branch at line ~418 adds `test_size` and `val_size` — for `"none"` these are the config defaults (harmless; the split didn't use them).

#### 3.2.5 Logging (no change needed)

The summary logging at lines ~435-457 handles empty DataFrames safely: `len(val_df) / len(df) * 100` evaluates to `0.0`, and the per-label loop in target distribution iterates over empty `value_counts()` (no iterations).

#### 3.2.6 `_inject_unlabeled_negatives` and `geo_stratify` (no change needed)

Both operate on `train_df` only. `_inject_unlabeled_negatives` receives `val_df, test_df` for ID dedup — with empty DataFrames, the dedup set is empty, so no rows are excluded (all unlabeled negatives are accepted). This is correct: in no-holdout mode, there's no val/test to leak into.

### 3.3 `src/energizados/core/steps/training.py`

**Change type:** Additive guards throughout `execute()` + `_train_single_model`.

#### 3.3.1 Import (top of file, line ~12)

Add `ConfigurationError` import:

```python
from energizados.core.exceptions import ConfigurationError
```

#### 3.3.2 Input guard (line 244)

```python
# Before:
if not self.train_path or not self.val_path:
    raise ValueError("train_path and val_path are required")

# After:
if not self.train_path:
    raise ValueError("train_path is required")
```

`val_path` is now optional. When it's `None` (set by SplitStep in no-holdout mode), execution continues.

#### 3.3.3 Val load (line 255)

```python
val_df = pd.read_parquet(self.val_path) if self.val_path else None
```

#### 3.3.4 Val feature extraction (lines 263-264)

```python
X_val = val_df.drop(columns=[self.target_column]) if val_df is not None else None
y_val = val_df[self.target_column] if val_df is not None else None
```

#### 3.3.5 columns_filter val block (lines 296-300)

Wrap the existing val lines inside `if X_val is not None:`:

```python
if columns_filter:
    from energizados.core.utils.columns_filter import apply_columns_filter

    logger.info("Applying columns_filter to training data...")
    X_train, n_removed = apply_columns_filter(X_train, columns_filter)
    y_train = y_train.loc[X_train.index]
    if n_removed > 0:
        logger.info(f"  Train: removed {n_removed} rows")

    if X_val is not None:
        X_val, n_removed = apply_columns_filter(X_val, columns_filter)
        y_val = y_val.loc[X_val.index]
        if n_removed > 0:
            logger.info(f"  Val: removed {n_removed} rows")

    if X_test is not None:
        X_test, n_removed = apply_columns_filter(X_test, columns_filter)
        y_test = y_test.loc[X_test.index]
        if n_removed > 0:
            logger.info(f"  Test: removed {n_removed} rows")
```

#### 3.3.6 datetime drop val block (lines 306-307)

```python
if cols_to_drop:
    logger.info(f"Dropping datetime columns before feature engineering: {cols_to_drop}")
    X_train = X_train.drop(columns=cols_to_drop)
    if X_val is not None:
        X_val = X_val.drop(columns=cols_to_drop)
    if X_test is not None:
        X_test = X_test.drop(columns=cols_to_drop)
```

#### 3.3.7 FE transform val (line 367)

```python
X_val_transformed = feature_engineering.transform(X_val) if X_val is not None else None
```

#### 3.3.8 Residual datetime drop (lines 378-380)

```python
if residual_dt_cols:
    logger.info(...)
    X_train_transformed = X_train_transformed.drop(columns=residual_dt_cols)
    if X_val_transformed is not None:
        X_val_transformed = X_val_transformed.drop(columns=residual_dt_cols)
    if X_test_transformed is not None:
        X_test_transformed = X_test_transformed.drop(columns=residual_dt_cols)
```

#### 3.3.9 Transformed shape logging (lines 382-384)

```python
logger.info(f"Train transformed shape: {X_train_transformed.shape}")
if X_val_transformed is not None:
    logger.info(f"Val transformed shape: {X_val_transformed.shape}")
if X_test_transformed is not None:
    logger.info(f"Test transformed shape: {X_test_transformed.shape}")
```

#### 3.3.10 NaN diagnostics (lines 385-386)

```python
train_nan = X_train_transformed.isnull().sum().sum()
val_nan = X_val_transformed.isnull().sum().sum() if X_val_transformed is not None else 0
```

#### 3.3.11 Blending fail-fast (new, before model dispatch at ~line 434)

```python
# Fail-fast: blending requires validation data
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

#### 3.3.12 Phase D restructure (lines 465-510)

Replace the current Phase D block with:

```python
# Phase D: Quick val metrics
from sklearn.metrics import f1_score, roc_auc_score

if X_val_transformed is not None:
    # ---- EXISTING CODE: comparison mode + single model val metrics ----
    # (Lines 467-510 unchanged — moved inside the if-branch)
    ...
else:
    # ---- No-holdout mode: no honest val metrics ----
    logger.info(
        "Training in no-holdout mode. No honest validation metrics available. "
        "Internal 10%% split used for early stopping only."
    )
    val_proba = None
    val_auc = None
    val_f1 = None
    if len(self.models_configs) > 1 and not self.ensemble_config:
        val_metrics = {name: {"auc": None, "f1": None} for name in names}
    else:
        val_metrics = None
```

#### 3.3.13 val_proba stats logging (lines 492-500)

```python
if val_proba is not None:
    logger.info(
        f"Val proba stats (first model): min={val_proba.min():.4f}, ..."
    )
```

#### 3.3.14 Val predictions save (lines 496-501)

```python
if X_val is not None and val_proba is not None:
    val_pred_dir = Path(self.val_path).parent if self.val_path else Path("data/temp/splits")
    val_pred_path = val_pred_dir / "val_predictions.parquet"
    val_predictions = pd.DataFrame(
        {"y_true": y_val.values, "y_proba": val_proba},
        index=y_val.index,
    )
    val_predictions.to_parquet(val_pred_path)
    logger.info(f"Val predictions saved to: {val_pred_path}")
    val_predictions_path = str(val_pred_path)
else:
    val_predictions_path = None
```

#### 3.3.15 Context return (lines 503-530)

Add `holdout_mode` to both branches:

```python
result = {
    **context,
    "feature_engineering_path": str(fe_path),
    "val_predictions_path": val_predictions_path,
    "feature_engineering": feature_engineering,
    "holdout_mode": "none" if X_val_transformed is None else "standard",
}

# Comparison mode branch:
if len(self.models_configs) > 1 and not self.ensemble_config:
    result["model_paths"] = ...
    result["val_auc"] = None  # unchanged
    result["val_f1"] = None   # unchanged
    ...
else:
    result["val_auc"] = val_auc   # None in no-holdout, float in standard
    result["val_f1"] = val_f1     # None in no-holdout, float in standard
    ...
```

`holdout_mode` is set at the top of `result` dict construction and applies to both branches.

#### 3.3.16 `_train_single_model` calibration (line 655)

```python
calibration_config = cfg.get("calibration", {})
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

#### 3.3.17 `validate_input` (line 836)

```python
# Before:
def validate_input(self, context):
    train_path = self.train_path or context.get("train_path")
    val_path = self.val_path or context.get("val_path")
    if not train_path or not val_path:
        return False
    return Path(train_path).exists() and Path(val_path).exists()

# After:
def validate_input(self, context):
    train_path = self.train_path or context.get("train_path")
    if not train_path:
        return False
    if not Path(train_path).exists():
        return False
    val_path = self.val_path or context.get("val_path")
    if val_path and not Path(val_path).exists():
        return False
    return True
```

`val_path` is optional. When present, its file must still exist (backward compat). When absent, validation passes.

#### 3.3.18 `get_required_keys` (line 844)

```python
# Before:
def get_required_keys(self) -> list:
    if not self.train_path or not self.val_path:
        return ["train_path", "val_path"]
    return []

# After:
def get_required_keys(self) -> list:
    if not self.train_path:
        return ["train_path"]
    return []
```

`val_path` is no longer required for pipeline dependency resolution. When `train_path` is provided at construction, no context keys are required.

### 3.4 `src/energizados/core/builders/director.py`

**Change type:** Additive (conditional skip).

See DQ-3 above (Section 2.3) for the exact change. No import changes needed — `logger` is already available.

### 3.5 `src/energizados/evaluation/evaluator.py`

**Change type:** Additive (early-return guard).

Insert at the top of `execute()`, after path resolution (lines ~130-135), replacing the current `ValueError`:

```python
# Before:
if not input_path:
    raise ValueError("No input_path provided and 'test_path' not found in context.")

# After:
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

The `skipped: True` flag is a new context key that downstream consumers can check. The director auto-skip (FR4) means this guard is primarily for standalone evaluator usage. The `FileNotFoundError` check for a non-existent path (line ~134) stays unchanged — it only triggers when a path IS provided but doesn't exist.

**Backward compat:** When `test_path` is provided and exists, the guard is a no-op — execution continues to the existing code.

### 3.6 `src/energizados/modeling/ensemble.py`

**Change type:** Additive (exception upgrade + import).

#### 3.6.1 Import (top of file)

```python
from energizados.core.exceptions import ConfigurationError
```

#### 3.6.2 `_fit_meta_learner` blending error (line ~128)

```python
# Before:
if self.use_val_as_oof:
    if X_val is None or y_val is None:
        raise ValueError("use_val_as_oof=True requires X_val and y_val.")

# After:
if self.use_val_as_oof:
    if X_val is None or y_val is None:
        raise ConfigurationError(
            "Ensemble blending (use_val_as_oof=True) requires a validation split, "
            "but X_val is None. Options: (a) provide X_val and y_val, "
            "(b) switch to use_val_as_oof=False (K-fold OOF stacking), or "
            "(c) use method='soft_voting'."
        )
```

No other change to `EnsembleModel`. Soft-voting and K-fold-OOF stacking (`use_val_as_oof=False`) already work with `X_val=None`:

- Soft-voting: base models each receive `X_val=None` → internal 10% split. No stacking, no meta-learner.
- K-fold OOF: `_generate_oof()` uses `StratifiedKFold` on `X, y` only — never touches `X_val`.

---

## 4. Error Handling Strategy

### 4.1 Exception usage table

| Error | Exception type | Raised at | When |
|---|---|---|---|
| Blending without val (pipeline) | `ConfigurationError` | `TrainingStep.execute()` (fail-fast, ~line 434) | `ensemble_config.use_val_as_oof=True` + `X_val is None` |
| Blending without val (standalone) | `ConfigurationError` | `EnsembleModel._fit_meta_learner()` (defense-in-depth, ~line 128) | Direct API: `.fit(X, y, X_val=None)` with `use_val_as_oof=True` |
| Missing train_path | `ValueError` | `TrainingStep.execute()` (line 244, unchanged message) | `train_path` is None — same as today, just no longer requires val_path |
| No test_path (standalone evaluator) | Early return with `skipped=True` | `DefaultEvaluator.execute()` (~line 131) | `input_path` and `test_path` both absent |

### 4.2 Actionable blending message

The `ConfigurationError` message lists all three alternatives:

```
Ensemble blending (use_val_as_oof=True) requires a validation split,
but no validation data is available (split.method='none').
Options: (a) provide a validation split (split.method != 'none'),
(b) switch to K-fold OOF stacking (use_val_as_oof: false), or
(c) use soft_voting ensemble method.
```

This satisfies FR6 scenario "blending raises ConfigurationError" — the message mentions at least one actionable alternative (it mentions all three).

### 4.3 Warning messages (logging, not exceptions)

| Situation | Log level | Message summary |
|---|---|---|
| No-holdout mode entered | `INFO` | "Training in no-holdout mode. No honest validation metrics available. Internal 10% split used for early stopping only." |
| Calibration skipped | `WARNING` | "Calibration enabled for '{name}' but no validation data available. Skipping calibration. Model will ship uncalibrated." |
| Evaluation auto-skipped | `WARNING` | "Evaluation is enabled but split.method is 'none' — no test set available. Skipping evaluation step automatically." |
| Evaluator standalone skip | `WARNING` | "No test_path available in context — skipping evaluation." |
| Split mode 'none' | `INFO` | "Split method 'none': assigning all data to train (no holdout)." |

All messages use `logging` — no `print`.

---

## 5. Context Contract

### 5.1 New context keys

| Key | Type | Set by | Values |
|---|---|---|---|
| `holdout_mode` | `str` | `TrainingStep.execute()` | `"none"` (no val) / `"standard"` (val present) |

### 5.2 Modified context key semantics

| Key | Standard mode | No-holdout mode |
|---|---|---|
| `val_path` | `str` (path to val.parquet) | `None` |
| `test_path` | `str` (path to test.parquet) | `None` |
| `val_auc` | `float` | `None` |
| `val_f1` | `float` | `None` |
| `val_predictions_path` | `str` (path to parquet) | `None` |
| `metrics` (single model) | `{"auc": float, "f1": float}` | `{"auc": None, "f1": None}` |
| `val_metrics` (comparison) | `{name: {"auc": float, "f1": float}}` | `{name: {"auc": None, "f1": None}}` |

### 5.3 Downstream consumer behavior

**RunManager (`_write_run_metadata`, line ~457):** Reads `context.get("val_auc")` and `context.get("val_f1")`. Both are already `Optional[float] = None` in `RunMetadata`. When the context value is `None`, the metadata records `val_auc: null, val_f1: null` in `run_metadata.json`. **No code change needed.** The metadata correctly reflects "no honest metrics."

**Web Console (Compare):** Out of scope for this change. `RunMetadata.to_dict()` already serializes `None` as `null`. The web console should handle null metrics gracefully, but no web console code is changed.

**Evaluator:** When the director auto-skips evaluation (FR4), the evaluator is never invoked — no `metrics`, `plots`, or `reports` keys are added to context. When the evaluator is invoked standalone with no `test_path`, it returns early with `metrics={}, skipped=True`.

---

## 6. Test Architecture

### 6.1 Test-to-Requirement mapping

Strict TDD: tests are written FIRST, then implementation makes them pass.

| FR | Scenario | Test file | Test name | Marker |
|---|---|---|---|---|
| FR1 | method "none" puts all rows in train | `tests/test_split.py` | `test_split_method_none_all_data_in_train` | `@pytest.mark.unit` |
| FR1 | only train.parquet is written | `tests/test_split.py` | `test_split_none_writes_train_parquet_only` | `@pytest.mark.unit` |
| FR1 | split metadata records zero val/test | `tests/test_split.py` | `test_split_none_metadata_zero_val_test` | `@pytest.mark.unit` |
| FR1 | schema accepts method none | `tests/test_config_schemas.py` | `test_split_method_none_valid` | `@pytest.mark.unit` |
| FR1 | no extra fields required for none | `tests/test_config_schemas.py` | `test_split_method_none_no_extra_fields` | `@pytest.mark.unit` |
| FR2 | training succeeds without val_path | `tests/test_training_step.py` | `test_training_no_holdout_succeeds` | `@pytest.mark.unit` |
| FR2 | model layer receives X_val=None | `tests/test_training_step.py` | `test_training_no_holdout_model_receives_none_val` | `@pytest.mark.unit` |
| FR3 | no-holdout metrics are None | `tests/test_training_step.py` | `test_training_no_holdout_metrics_none` | `@pytest.mark.unit` |
| FR3 | no-holdout logs honesty message | `tests/test_training_step.py` | `test_training_no_holdout_logs_honesty_message` | `@pytest.mark.unit` |
| FR3 | standard run sets holdout_mode standard | `tests/test_training_step.py` | `test_training_with_val_sets_holdout_mode_standard` | `@pytest.mark.unit` |
| FR3 | comparison mode guards val metrics | `tests/test_training_step.py` | `test_training_comparison_mode_no_holdout_metrics_none` | `@pytest.mark.unit` |
| FR4 | evaluation auto-skipped with warning | `tests/test_pipeline.py` | `test_pipeline_no_holdout_eval_skipped` | `@pytest.mark.integration` |
| FR5 | evaluator skips gracefully without test_path | `tests/test_evaluator.py` | `test_evaluator_no_test_path_skips_gracefully` | `@pytest.mark.unit` |
| FR6 | blending raises ConfigurationError | `tests/test_ensemble.py` | `test_ensemble_blending_no_val_raises_config_error` | `@pytest.mark.unit` |
| FR6 | soft voting works without holdout | `tests/test_ensemble.py` | `test_ensemble_soft_voting_no_holdout_succeeds` | `@pytest.mark.unit` |
| FR6 | K-fold OOF stacking works without holdout | `tests/test_ensemble.py` | `test_ensemble_kfold_oof_no_holdout_succeeds` | `@pytest.mark.unit` |
| FR7 | calibration skipped without val | `tests/test_training_step.py` | `test_training_no_holdout_calibration_skipped` | `@pytest.mark.unit` |

### 6.2 Regression guards (existing tests that MUST pass unchanged)

These tests provide the backward-compatibility proof. They are NOT modified:

| File | Test class/pattern | What it guards |
|---|---|---|
| `tests/test_training_step.py` | `TestTrainingStepSingleModel::*` | Single model with val → val_auc/val_f1 are floats |
| `tests/test_training_step.py` | `TestTrainingStepEnsemble::*` | Ensemble with val → works as before |
| `tests/test_training_step.py` | `TestTrainingStepComparisonMode::*` | Comparison mode with val_metrics |
| `tests/test_split.py` | `test_split_*` (existing) | All existing split methods produce 3 parquets + 3 paths |
| `tests/test_config_schemas.py` | `test_split_*` (existing) | Existing method enum validation |
| `tests/test_e2e_pipeline.py` | `*` | End-to-end pipeline with stratified split |

### 6.3 Test fixtures

No-holdout tests need minimal fixtures — a small synthetic dataset (e.g., 200 rows, 5 features, binary target). The existing test fixtures in `tests/conftest.py` or `tests/fixtures/` should be reused. A `method="none"` split config fixture can be parameterized alongside existing method fixtures.

### 6.4 Test command

```bash
pytest tests/ --strict-markers
```

---

## 7. Risks & Mitigations (design-specific)

| Risk | Severity | Mitigation |
|---|---|---|
| **`use_val_as_oof` defaults to `True` in `_train_ensemble`** — users with multi-model + stacking config who switch to `method="none"` without changing ensemble config get a `ConfigurationError`. This is correct behavior but may surprise. | Medium | The error message lists all three alternatives explicitly. The fail-fast fires before any base model training (no wasted computation). |
| **Comparison mode `val_metrics` shape changes** — in no-holdout, entries are `{"auc": None, "f1": None}` instead of floats. Downstream code that does `metrics["auc"] + 1` would fail. | Low | `val_metrics` is consumed by the evaluator's comparison report, which is auto-skipped in no-holdout mode. No downstream consumer reads comparison `val_metrics` when evaluation is skipped. |
| **`val_predictions_path=None` breaks evaluator calibration** — `DefaultEvaluator` reads `ctx.get("val_predictions_path")` for threshold calibration (evaluator.py ~line 160). When None, it already logs a warning and uses the default threshold. | Low | The evaluator already handles `val_predictions_path=None` gracefully (line ~170: "Calibration enabled but val_predictions_path not found, using default threshold"). No change needed. |
| **Empty DataFrames in SplitStep metadata** — `value_counts().to_dict()` on empty DataFrames returns `{}`. If a consumer expects keys `0` and `1` in target_distribution, it may break. | Low | The metadata is informational JSON. No code path depends on target_distribution keys existing for empty splits. |
| **`holdout_mode` not in `get_output_keys`** — TrainingStep's `get_output_keys()` doesn't list `holdout_mode`. This may affect pipeline validation or introspection. | Low | Add `"holdout_mode"` to the `get_output_keys()` return list. See §3.3 — this is a minor addition. |

---

## 8. Explicit Non-Decisions

The following are deliberately left to the `sdd-apply` phase:

1. **Exact log message wording.** The design specifies the *information content* of each message. Final wording may be adjusted during implementation as long as the key facts are present (no honest metrics, internal split is for early stopping only, actionable alternatives).
2. **Test fixture data shapes.** The design specifies test names and what they assert. The exact synthetic dataset (row count, feature names) is decided during apply.
3. **Whether to add `holdout_mode` to `get_output_keys()`.** The design recommends it (§7 risk 5) but the exact list edit is mechanical.
4. **`CONTEXT.md` glossary updates.** Tracked as a task (per spec out-of-scope), not part of the implementation code.
5. **Exact `%%` vs `%` formatting in f-string log messages.** Python f-strings require `%%` to produce a literal `%` — the design uses `%%` in log strings but the apply phase should verify the actual output.
6. **Whether `val_metrics` in no-holdout comparison mode should be `{}` (empty dict) or `{name: {"auc": None, "f1": None}}`.** The design chooses the latter (explicit per-model None), but the apply phase may simplify to `{}` if downstream doesn't depend on the shape.

---

## 9. Decision Traceability

| Design question | Section | Resolution |
|---|---|---|
| DQ-1: Blending error detection point | §2.1 | Both: fail-fast in TrainingStep + defense-in-depth in EnsembleModel |
| DQ-2: Guard pattern in TrainingStep | §2.2 | Inline `None` guards — no helper, no branch |
| DQ-3: Director auto-skip mechanism | §2.3 | Config-level check in `build()`, skip evaluation step construction |

| FR | Design section(s) | Key file(s) |
|---|---|---|
| FR1 | §3.1, §3.2 | schemas.py, split.py |
| FR2 | §3.3 (G1-G9) | training.py |
| FR3 | §3.3 (G10-G14), §5 | training.py |
| FR4 | §2.3, §3.4 | director.py |
| FR5 | §3.5 | evaluator.py |
| FR6 | §2.1, §3.6 | training.py, ensemble.py |
| FR7 | §3.3.16 | training.py |
