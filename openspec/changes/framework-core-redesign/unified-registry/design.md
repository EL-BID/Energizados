# Design: unified-registry (Approach 4B)

## Technical Approach

**Two-PR refactor** that kills the `_prepare_model_params` ladder and fixes the `_build_meta_learner` bug, then extracts a unified `Registry` abstraction. PR1 moves config-mapping logic into per-adapter `from_config` classmethods; PR2 generalizes `ModelRegistry` into a reusable `Registry` class with per-domain instances. Transformer/selector migration deferred.

## Architecture Decisions

### Decision 1: `from_config` Location — Per-Adapter Classmethod

**Choice**: Add `@classmethod def from_config(cls, config: Dict, X_train: pd.DataFrame) -> Dict` to each adapter class. Param-mapping logic from the ladder moves into the adapter that uses it.

**Alternatives considered**:
- **Mixin/base class**: Would require a new `ConfigurableAdapter` base with type-specific hooks.
- **Free-standing function**: Would break encapsulation — adapters own their constructor logic.

**Rationale**:
- Adapter already owns its `__init__` signature — `from_config` is the natural factory
- No class moves — pickle-safe (adapters stay in `modeling/adapters.py`)
- Each adapter is independently testable
- Hexagonal: domain logic (how YAML maps to constructor) lives inside the domain entity

**Contract**: Each `from_config` must return `Dict` such that `cls(**from_config(cfg, X_train))` produces identical instance to old ladder + `cls(**params)`.

---

### Decision 2: `X_train.columns` Plumbing

**Choice**: Pass `X_train` (the post-feature-engineering DataFrame) as argument to `from_config`.

**Rationale**:
- Ladder already uses `X_train.columns.tolist()` for gradient boosters and column filtering for NN/LSTM (`_anterior` detection)
- `from_config` needs access to derive `cols_for_model`, `features_names`, `spents_names`
- No abstraction leak — columns are a fact of the model-construction domain

---

### Decision 3: `_build_meta_learner` Fix — Reuse `_SklearnCalibWrapper`

**Choice**: Keep direct `LogisticRegression` path untouched. For registry-sourced adapters, wrap with `_SklearnCalibWrapper` to provide 2D `predict_proba`.

**Alternatives considered**:
- **Modify adapter `predict_proba` to return 2D**: Breaking change to `BaseModel` contract (frozen).
- **New adapter subclass for meta-learners**: Unnecessary indirection.

**Rationale**:
- `_SklearnCalibWrapper` already bridges 1D→2D for calibration — same problem
- Direct `LogisticRegression` path remains zero-cost (no wrapper overhead)
- Wrapper only applies when user explicitly chooses non-sklearn meta-learner

**Implementation**:
```python
def _build_meta_learner(self):
    meta_type = self.meta_learner_config.get("type", "logistic_regression")
    params = self.meta_learner_config.get("params", {})

    if meta_type == "logistic_regression":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(**params)

    cls = model_registry.get(meta_type)
    meta = cls(**params)
    return _SklearnCalibWrapper(meta)  # 1D → 2D bridge
```

---

### Decision 4: `Registry` Class Design

**Choice**: Extract to `src/energizados/core/registry.py` as standalone class with instance methods (not classmethods). Name-casing: `name.lower()` for storage, case-insensitive lookup. KeyError with available-list on missing.

**Alternatives considered**:
- **Add to `contracts.py`**: Contracts are frozen — this is implementation detail, not public API.
- **Keep classmethods**: Instance methods allow multiple registries without `__init__` hacks.

**API**:
```python
class Registry:
    def __init__(self, name: str): ...
    def register(self, name: str, factory: type) -> None: ...
    def get(self, name: str) -> type: ...  # raises KeyError with available names
    def is_registered(self, name: str) -> bool: ...
    def list_registered(self) -> List[str]: ...
```

**Per-domain instances** (exposed at module level):
```python
# core/registry.py
model_registry = Registry("models")
transformer_registry = Registry("transformers")
selector_registry = Registry("selectors")
```

---

### Decision 5: `ModelRegistry` Alias — Silent (No Deprecation Warning)

**Choice**: `ModelRegistry` becomes a silent alias to `model_registry.get` methods. No deprecation warning in this release.

**Rationale for resolving proposal inconsistency**:
- Proposal line 34 mentions warning, line 71 says "resolves without" — conflicting guidance.
- **Recommendation**: Silent alias this release. Reason:
  1. Public extension point — users import `from energizados.modeling.registry import ModelRegistry`
  2. Deprecation warning in library code triggers CI failures in downstream repos
  3. Alias is permanent (not transitional) — users can continue importing old path
  4. Future release can add warning if we decide to deprecate

**Implementation** (`modeling/registry.py` becomes thin shim):
```python
from energizados.core.registry import model_registry

# Backward-compatible alias (silent)
class ModelRegistry:
    @classmethod
    def register(cls, name: str, model_class: type) -> None:
        model_registry.register(name, model_class)

    @classmethod
    def get(cls, name: str) -> type:
        return model_registry.get(name)

    # ... other methods delegate similarly
```

---

### Decision 6: Pickle Safety — No Moves

**Choice**: NO concrete class `__module__` changes. Adapters remain in `modeling/adapters.py`. `_prepare_model_params` is deleted (no pickle impact). `Registry` is new.

**Concrete classes untouched**:
- `LGBMModelAdapter`, `CATModelAdapter`, `XGBModelAdapter`
- `NNModelAdapter`, `LSTMNNModelAdapter`
- `SimpleTrendAdapter`, `SimpleConstantAdapter`
- `EnsembleModel`

**Result**: Existing `.pkl` files load unchanged. `ModelRegistry` alias preserves import paths.

---

## Data Flow

### Before (Current Ladder)

```
TrainingStep._train_single_model:
  └─> _prepare_model_params(model_config, X_train)
        └─> if/elif ladder by model_type
              └─> returns Dict of constructor kwargs
  └─> model_class = ModelRegistry.get(model_type)
  └─> model = model_class(**params)
```

### After (from_config)

```
TrainingStep._train_single_model:
  └─> model_class = model_registry.get(model_type)
  └─> params = model_class.from_config(model_config, X_train)  # replaces ladder
  └─> model = model_class(**params)
```

### Meta-Learner Fix

```
_build_meta_learner:
  ├─> meta_type == "logistic_regression" → LogisticRegression(**params)  # unchanged
  └─> else:
        ├─> cls = model_registry.get(meta_type)
        ├─> meta = cls(**params)
        └─> return _SklearnCalibWrapper(meta)  # 1D → 2D bridge
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/energizados/core/steps/training.py` | Modify | Replace `_prepare_model_params` call with `model_class.from_config(cfg, X_train)`; delete `_prepare_model_params` method (lines 802-869); keep `_SklearnCalibWrapper` (lines 21-41) unchanged |
| `src/energizados/modeling/adapters.py` | Modify | Add `from_config(cls, config, X_train) -> Dict` to LGBM, CAT, XGB, NN, LSTM, SimpleTrend, SimpleConstant |
| `src/energizados/modeling/ensemble.py` | Modify | `_build_meta_learner`: wrap registry-sourced adapters with `_SklearnCalibWrapper` |
| `src/energizados/core/registry.py` | Create | New `Registry` class with `register`/`get`/`is_registered`/`list_registered`; module-level `model_registry`, `transformer_registry`, `selector_registry` instances |
| `src/energizados/modeling/registry.py` | Modify | `_register_default_models()` calls `model_registry.register()`; convert `ModelRegistry` to silent alias delegating to `model_registry` |

## Interfaces / Contracts

### `from_config` Contract (Per Adapter)

```python
@classmethod
def from_config(cls, config: Dict, X_train: pd.DataFrame) -> Dict:
    """
    Derive constructor kwargs from YAML config.

    Args:
        config: Model config dict (with "type", "hyperparams", "sampling", etc.)
        X_train: Post-feature-engineering DataFrame (used to derive column lists)

    Returns:
        Dict: Constructor kwargs for cls.__init__

    Contract:
        cls(**from_config(cfg, X_train)) must produce identical instance
        to the old _prepare_model_params(cls, cfg, X_train) + cls(**params).
    """
```

### Per-Adapter Implementation Mapping

| Adapter | Extracted from ladder | Returns |
|---------|----------------------|---------|
| LGBM/CAT/XGB | `cols_for_model = X_train.columns.tolist()`, sampling extraction, hyperparams flattening, hyperparam_search → `search_hip`, `n_iter`, `cv`, `n_splits`, `class_weight`, `config={"type": ...}` | `{"cols_for_model": list, "hyperparams": dict, "sampling_method": str, "sampling_th": float, ...}` |
| NN/LSTM | `consumption_cols = [c for c in X_train.columns if "_anterior" in c]`, `feature_cols = [c for c in X_train.columns if c not in consumption_cols]`, sampling extraction | `{"features_names": list, "spents_names": list, "sampling_method": str, ...}` |
| SimpleTrend | `last_base_value`, `last_eval_value`, `threshold` extraction; pop `sampling`, `class_weight`, `hyperparams`, `hyperparam_search` | `{"last_base_value": int, "last_eval_value": int, "threshold": float}` |
| SimpleConstant | `min_count_constante` extraction; pop invalid keys | `{"min_count_constante": int}` |

### `Registry` API

```python
class Registry:
    def __init__(self, name: str) -> None: ...

    def register(self, name: str, factory: type) -> None:
        """Store factory under name.lower(). Overwrites if exists."""

    def get(self, name: str) -> type:
        """Retrieve factory by case-insensitive name. Raises KeyError with available names."""

    def is_registered(self, name: str) -> bool: ...

    def list_registered(self) -> List[str]: ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (behavior preservation) | `from_config` produces identical kwargs to old ladder | RED test before deleting ladder: assert `from_config(cfg, X) == _prepare_model_params(cfg, X)` for each model type |
| Unit (meta-learner fix) | `_SklearnCalibWrapper` exposes 2D `predict_proba` | Test wrapper on adapter — verify `predict_proba(X).shape == (n, 2)` and `[:, 1]` equals adapter's 1D |
| Integration | TrainingStep._train_single_model uses `from_config` | Test full training run with each model type; compare metrics to baseline |
| Regression | Existing tests pass | `pytest tests/` after each PR |

### TDD Ordering (Strict TDD Mode)

1. **Before PR1 implementation**: Write RED tests asserting `from_config` equivalence
   - Test per adapter type with representative config
   - Fixture: `assert_params_equal(adapter.from_config(cfg, X_train), old_ladder(cfg, X_train))`
2. **Implement `from_config` methods**: Tests turn GREEN
3. **Delete ladder**: Tests still pass (prove equivalence)
4. **PR2**: Registry extraction tests (instance methods, per-domain isolation)
5. **Meta-learner fix**: Test stacking with non-sklearn meta-learner

## Migration / Rollout

### PR1 Execution Order
1. Add `from_config` to all adapters (RED tests exist)
2. Update `TrainingStep._train_single_model` to call `from_config`
3. Fix `_build_meta_learner` via `_SklearnCalibWrapper`
4. Delete `_prepare_model_params` method
5. Verify all tests pass

### PR2 Execution Order
1. Create `core/registry.py` with `Registry` class and 3 instances
2. Update `modeling/registry._register_default_models()` to use `model_registry.register()`
3. Convert `ModelRegistry` to silent alias
4. Verify all tests pass + import paths resolve

### Rollback Plan
- **PR1**: Revert `from_config` calls, restore `_prepare_model_params` ladder
- **PR2**: Delete `core/registry.py`, revert `ModelRegistry` to original class
- Both PRs: Existing `.pkl` files compatible (no class moves)

## Open Questions

None. All design decisions resolved.

## Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| Behavior preservation bug (from_config deviates from ladder) | Medium | RED→GREEN tests before deletion; exhaustive coverage of all model type branches |
| Meta-learner wrapper edge cases | Low | `_SklearnCalibWrapper` already battle-tested in calibration path |
| Registry name collision (case-insensitivity) | Low | Document lowercasing; tests verify "CatBoost" and "catboost" resolve same |
| Pickle incompatibility from `ModelRegistry` alias change | Low | Alias preserves import path; concrete adapter classes unmoved |
