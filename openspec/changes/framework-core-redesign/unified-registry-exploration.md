# Exploration: unified-registry (re-scoped against current code)

> Change #4 of the `framework-core-redesign` program. Finding 4.
> **Re-investigation** — the program-level `exploration.md` (Finding 4 + Approach 4A) is STALE: it predates changes #2 (contracts-consolidation) and #3 (core-layering), which reorganized the codebase. Every claim below is verified against the source on `release/0.2.x` (post changes #2 and #3).

## What changes #2 and #3 already did for Finding 4

- **Change #2** moved the 8 base classes into `energizados.contracts` and turned old base modules into shim re-exports. This did NOT touch any of the 4 parallel extension mechanisms.
- **Change #3** eliminated the `core↔concrete` import cycles via lazy imports. This shifted `_prepare_model_params` from lines 812-855 to 802-869 but did NOT change its structure or the underlying problem.

## Current State (verified against current code)

### 1. Model Registry (STILL MODELS ONLY)

**File:** `src/energizados/modeling/registry.py`

`ModelRegistry` remains a simple classmethod dict mapping names to adapter classes:

```python
class ModelRegistry:
    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, model_class: type) -> None:
        cls._registry[name.lower()] = model_class

    @classmethod
    def get(cls, name: str) -> type:
        return cls._registry[name.lower()]
```

**Built-in models are registered at import time** (lines 91-136):
- Supervised: `lightgbm/lgbm`, `catboost/cat`, `xgboost/xgb`, `neural_network/nn`, `lstm`
- Simple baselines: `simple_trend`, `simple_constant`
- **`EnsembleModel` is intentionally NOT registered** (line 123 comment)

**Limitation:** Models only. No parallel mechanism for transformers or selectors.

---

### 2. The _prepare_model_params Ladder (STILL EXISTS, BYPASSES REGISTRY)

**File:** `src/energizados/core/steps/training.py`

**Lines:** 802-869 (shifted from 812-855 in the program exploration due to lazy imports in change #3)

**Problem:** An if/elif ladder that maps `model_type` strings → constructor kwargs. This is SEPARATE from the registry — adding a model means editing BOTH places.

**Current structure (lines 816-860):**

```python
def _prepare_model_params(self, model_config: Dict, X_train: pd.DataFrame) -> Dict:
    params = model_config.copy()
    model_type = params.get("type", "lightgbm")

    if model_type in ["lightgbm", "lgbm", "catboost", "cat", "xgboost", "xgb"]:
        params["cols_for_model"] = X_train.columns.tolist()
        sampling_config = params.pop("sampling", {})
        params["sampling_method"] = sampling_config.get("method", "undersample")
        params["sampling_th"] = sampling_config.get("threshold", 0.5)
        # ... more param mapping

    elif model_type in ["neural_network", "nn", "lstm"]:
        consumption_cols = [c for c in X_train.columns if "_anterior" in c]
        feature_cols = [c for c in X_train.columns if c not in consumption_cols]
        params["features_names"] = feature_cols
        params["spents_names"] = consumption_cols
        # ... more param mapping

    elif model_type in ["simple_trend", "simple_constant"]:
        # Simple model params
        if model_type == "simple_trend":
            params["last_base_value"] = params.get("last_base_value", 6)
            params["last_eval_value"] = params.get("last_eval_value", 3)
            params["threshold"] = params.get("threshold", 50)
        elif model_type == "simple_constant":
            params["min_count_constante"] = params.get("min_count_constante", 3)
        # Remove invalid keys
        params.pop("sampling", None)
        params.pop("class_weight", None)
        # ...

    return params
```

**Impact:** When adding a new model type, you must:
1. Add it to `ModelRegistry._register_default_models()` in `modeling/registry.py`
2. Add a new branch to this if/elif ladder in `training.py`

This dual-edit requirement is error-prone and violates DRY.

---

### 3. The _build_meta_learner Bug (STILL BROKEN FOR NON-SKLEARN META-LEARNERS)

**File:** `src/energizados/modeling/ensemble.py`

**Lines:** 199-213 (method), 232 (bug site)

**Problem:** `_build_meta_learner` calls `ModelRegistry.get(meta_type)` which returns an adapter whose `predict_proba` returns **1D**, but line 232 indexes `[:, 1]` expecting **2D**:

```python
def _build_meta_learner(self):
    """Instantiate the meta-learner from config."""
    meta_type = self.meta_learner_config.get("type", "logistic_regression")
    params = self.meta_learner_config.get("params", {})

    if meta_type == "logistic_regression":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(**params)

    # Delegate to ModelRegistry for other types
    from energizados.modeling.registry import ModelRegistry

    cls = ModelRegistry.get(meta_type)  # Returns adapter with 1D predict_proba
    return cls(**params)

def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
    # ...
    if self.method == "stacking":
        return self._meta_learner.predict_proba(base_preds)[:, 1]  # BUG: expects 2D
```

**Current workaround:** Only `logistic_regression` (built directly, not via registry) works. Any model-type meta-learner is broken.

**Fix already exists:** The `_SklearnCalibWrapper` class (lines 21-41 in `training.py`) bridges 1D→2D for calibration. The same wrapper can be reused here.

---

### 4. transformer_map (STILL HARDCODED, NOT A CLASS)

**File:** `src/energizados/feature_engineering/default.py`

**Lines:** 62-133

**Problem:** A module-local dict mapping names → `(class, default_params)`. Not extensible from outside without editing this file.

```python
def _build_transformer_from_config(...):
    transformer_map = {
        "cardinality_reducer": (CardinalityReducer, {"threshold": 0.001}),
        "to_dummy": (ToDummy, {}),
        "target_encoding": (TeEncoder, {"w": 20}),
        # ... 10 more entries
    }

    if transform_name not in transformer_map:
        raise ValueError(f"Unknown transformer: {transform_name}")

    cls, default_params = transformer_map[transform_name]
    params = {**default_params, **(params or {})}
    return cls(**params)
```

**Limitation:** Adding a custom transformer requires either:
- Using `custom_class` escape hatch (generic fallback)
- Editing this module-local dict (not a true registry)

---

### 5. _get_default_method_map (STILL ANOTHER HARDCODED DICT)

**File:** `src/energizados/feature_selection/pipeline.py`

**Lines:** 24-42

**Problem:** Another module-local dict for selector methods. Parallel to `transformer_map`.

```python
_DEFAULT_METHOD_MAP: Optional[Dict[str, type]] = None

def _get_default_method_map() -> Dict[str, type]:
    global _DEFAULT_METHOD_MAP
    if _DEFAULT_METHOD_MAP is None:
        from energizados.feature_selection.methods import (
            BorutaSelector,
            CategoricalSelector,
            ConstantSelector,
            CorrelationSelector,
            MutualInformationSelector,
        )

        _DEFAULT_METHOD_MAP = {
            "boruta": BorutaSelector,
            "categorical": CategoricalSelector,
            "correlation": CorrelationSelector,
            "constant": ConstantSelector,
            "mutual_info": MutualInformationSelector,
        }
    return _DEFAULT_METHOD_MAP
```

**Limitation:** Same as `transformer_map` — not extensible without edits.

---

### 6. custom_class Escape Hatch (STILL THE GENERIC FALLBACK)

**File:** `src/energizados/core/utils/import_utils.py`

**Lines:** 32-90 (`import_class` function)

**Mechanism:** A security-controlled import function that allows local projects to reference custom classes via YAML config (`custom_class: "preprocessing.MyCustomTransformer"`). Uses an allowlist to prevent arbitrary code execution.

**Role:** Generic fallback for all extension types (ETLs, transformers, evaluators, inference, feature engineering). This is the 4th parallel mechanism.

**Interaction with registries:** When a unified registry is implemented, imported classes should also register themselves so the framework sees them through a single interface.

---

## Approaches

### 4A. Single Registry Abstraction + Per-Adapter from_config (RECOMMENDED)

**Design:**
1. **Generalize `ModelRegistry` into a reusable `Registry` class** in `src/energizados/core/registry.py` (or `contracts.py`):
   ```python
   class Registry:
       def __init__(self, name: str):
           self._name = name
           self._registry: Dict[str, type] = {}

       def register(self, name: str, factory: Union[type, Callable]) -> None:
           self._registry[name.lower()] = factory

       def get(self, name: str) -> Union[type, Callable]:
           return self._registry[name.lower()]
   ```

2. **Create per-domain instances**:
   ```python
   model_registry = Registry("models")
   transformer_registry = Registry("transformers")
   selector_registry = Registry("selectors")
   ```

3. **Add `from_config` classmethod to each adapter** (kills the `_prepare_model_params` ladder):
   ```python
   class LGBMModelAdapter(BaseModel):
       @classmethod
       def from_config(cls, config: Dict, X_train: pd.DataFrame) -> Dict:
           cols = X_train.columns.tolist()
           sampling = config.get("sampling", {})
           return {
               "cols_for_model": cols,
               "sampling_method": sampling.get("method", "undersample"),
               "sampling_th": sampling.get("threshold", 0.5),
               "hyperparams": config.get("hyperparams", {}),
               # ... all other param mapping logic from the ladder
           }
   ```

4. **Update `TrainingStep._train_single_model`** to use `from_config`:
   ```python
   model_class = model_registry.get(model_type)
   params = model_class.from_config(cfg, X_train)  # Replaces the ladder
   model = model_class(**params)
   ```

5. **Fix `_build_meta_learner`** via `_SklearnCalibWrapper`:
   ```python
   if meta_type == "logistic_regression":
       return LogisticRegression(**params)

   cls = model_registry.get(meta_type)
   meta = cls(**params)

   # Wrap adapters to provide 2D predict_proba
   wrapped = _SklearnCalibWrapper(meta)
   return wrapped
   ```

6. **Migrate `transformer_map` and `_get_default_method_map`** into their registries:
   - Built-ins self-register via decorators or explicit calls
   - `custom_class` imports also register dynamically

**Pros:**
- Kills the `_prepare_model_params` ladder (single point of model config logic)
- Fixes the `_build_meta_learner` bug (adapters get 2D via wrapper)
- Unifies all 4 mechanisms under one abstraction
- Extensible without core edits (just register + implement `from_config`)
- Clear extension point for users: `from_config` classmethod

**Cons:**
- Largest blast radius (touches ~12-15 files)
- Must preserve YAML semantics exactly (behavior preservation)
- Higher review surface
- Requires adding `from_config` to every adapter

**Effort:** **High** (~450-650 lines) — needs **2-3 chained PRs**

---

### 4B. Kill the Ladder Only (MINIMAL SCOPE)

**Design:** Move `_prepare_model_params` logic into per-adapter `from_config` methods, but leave `transformer_map` and selector map as-is. Fix `_build_meta_learner` via `_SklearnCalibWrapper`.

**Pros:**
- Smaller scope (~250-350 lines)
- Fixes the most-irksome dual-edit problem
- Fixes the meta-learner bug
- Leaves transformers/selectors untouched (lower risk)

**Cons:**
- Still 3 parallel mechanisms (doesn't fully unify)
- Doesn't improve transformer/selector extensibility

**Effort:** **Medium** (~250-350 lines) — **1-2 PRs**

---

### 4C. Full Unification Including Transformers/Selectors (MAXIMUM SCOPE)

**Design:** Same as 4A but also migrates `transformer_map` and `_get_default_method_map` into the unified registry system immediately.

**Pros:**
- One story for the whole framework
- Cleanest architecture

**Cons:**
- Largest blast radius (~500-700 lines)
- Highest review surface
- Transformers/selectors have different default-param semantics (more complex migration)

**Effort:** **High** (~500-700 lines) — **2-3 PRs**

---

## Recommendation

**Approach 4A**, split into **3 chained PRs**:

### PR1: Kill Ladder + Fix Meta-Learner (highest value, lowest risk)
- Add `from_config` to each adapter (LGBM, CAT, XGB, NN, LSTM, SimpleTrend, SimpleConstant)
- Update `TrainingStep._train_single_model` to call `from_config` instead of `_prepare_model_params`
- Delete `_prepare_model_params` method
- Fix `_build_meta_learner` via `_SklearnCalibWrapper`
- **Outcome:** Dual-edit requirement gone, meta-learner bug fixed
- **Lines:** ~200-300

### PR2: Implement Unified Registry
- Extract `Registry` class to `core/registry.py` (or `contracts.py`)
- Create `model_registry`, `transformer_registry`, `selector_registry` instances
- Migrate `ModelRegistry` registration calls to use `model_registry`
- Update all `ModelRegistry.get` calls to use `model_registry.get`
- Keep `ModelRegistry` as a backward-compatible alias (deprecation warning)
- **Outcome:** Single abstraction, foundation for unification
- **Lines:** ~150-200

### PR3: Migrate Transformers and Selectors (optional, can defer)
- Migrate `transformer_map` into `transformer_registry` with self-registration
- Migrate `_get_default_method_map` into `selector_registry` with self-registration
- Update `_build_transformer_from_config` and selector logic to use registries
- Ensure `custom_class` imports also register dynamically
- **Outcome:** Full unification, all 4 mechanisms consolidated
- **Lines:** ~100-150

**Why this split:**
- PR1 delivers immediate value (kills ladder + fixes bug) with low risk
- PR2 builds the foundation without touching transformers/selectors
- PR3 is optional polish — can be deferred if budget/time constrained
- Each PR stays under the 400-line review budget

**Alternative:** If PR3 is deemed too large, stop at PR2 (Approach 4B). Ladder is dead, bug is fixed, registry abstraction exists. Transformer/selector migration can be a separate follow-up change.

---

## Risks

### Pickle / Model Compatibility (LOW RISK)
- No class moves in PR1 or PR2 (only adds `from_config` methods and `Registry` class)
- Existing `model.pkl` and `feature_engineering.pkl` load unchanged (concrete classes keep `__module__`)
- PR3 doesn't move transformer/selector classes, only changes how they're registered
- **Risk level:** LOW

### Public Extension-Point Compatibility (LOW RISK)
- `ModelRegistry` becomes an alias in PR2 (backward-compatible)
- `custom_class` escape hatch continues to work
- All existing import paths (`energizados.modeling.registry.ModelRegistry`, etc.) keep resolving
- New `from_config` classmethod is additive, not breaking
- **Risk level:** LOW

### Behavior Preservation (MEDIUM RISK)
- PR1 must preserve exact YAML semantics (sampling config, hyperparams, etc.)
- Need tests that verify `from_config` produces identical kwargs to the old ladder
- Risk is in the migration details, not the design
- **Mitigation:** Add behavior-preservation tests before deleting the ladder
- **Risk level:** MEDIUM (mitigated by tests)

### Test Surface (MEDIUM RISK)
- 34 test files. PR1 touches model construction paths.
- PR2 touches registry calls throughout the codebase.
- **Mitigation:** Run `pytest tests/` after each PR. Add tests for `from_config` methods.
- **Risk level:** MEDIUM

### 400-Line Review Budget (MANAGED)
- PR1: ~200-300 lines (under budget)
- PR2: ~150-200 lines (under budget)
- PR3: ~100-150 lines (under budget)
- Total: ~450-650 lines across 3 PRs, each independently reviewable
- **Risk level:** LOW (chained approach manages budget)

---

## What's STALE vs Program Exploration

**Line number shifts:**
- `_prepare_model_params`: Was 812-855, now 802-869 (shifted due to lazy imports in change #3)
- Everything else: Unchanged

**Structural claims:** 100% accurate. All 4 mechanisms still exist with identical problems.

**Approach 4A:** Still the recommended approach. Design remains valid.

**Dependencies:**
- Change #2 (contracts-consolidation) is DONE — provides clean foundation
- Change #3 (core-layering) is DONE — eliminates cycles, but didn't touch these mechanisms
- This change can proceed independently now

---

## Ready for Proposal

**Yes.** The recommended approach (4A, split into 3 chained PRs) is:
- **Architecturally sound:** Single registry abstraction + per-adapter `from_config`
- **Low risk:** No class moves, backward-compatible aliases, behavior preservation via tests
- **High value:** Kills the dual-edit ladder, fixes meta-learner bug, unifies all 4 mechanisms
- **Reviewable:** Each PR stays under 400-line budget
- **Builds on completed changes:** #2 and #3 are done, providing clean foundation

**Next step:** Create proposal for change #4 (`unified-registry`).
