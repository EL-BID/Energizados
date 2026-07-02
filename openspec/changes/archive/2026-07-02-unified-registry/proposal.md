# Proposal: unified-registry

## Intent

Fix the dual-edit requirement when adding model types and the broken meta-learner bug in ensemble stacking. The `_prepare_model_params` ladder in `training.py` duplicates `ModelRegistry` logic — adding a model requires editing both places. Additionally, `_build_meta_learner` incorrectly indexes `[:,1]` on adapter `predict_proba` (1D output), breaking any non-sklearn meta-learner.

## Scope

### In Scope
- **PR1** (~200-300 lines): Add `from_config` classmethod to each model adapter; replace `_prepare_model_params` with registry-based calls; fix `_build_meta_learner` via `_SklearnCalibWrapper`
- **PR2** (~150-200 lines): Extract reusable `Registry` class to `core/registry.py`; create per-domain instances (`model_registry`, `transformer_registry`, `selector_registry`); migrate `ModelRegistry` to backward-compatible alias

### Out of Scope
- **Deferred to follow-up**: Migrating `transformer_map` and `_get_default_method_map` into unified registries (PR3 from exploration 4A)
- **Out of program scope**: The `_anterior` / 12-month domain leak is a separate future concern

## Capabilities

### Modified Capabilities
- `model-registry`: Extend with `from_config` classmethod pattern; replace with unified `Registry` abstraction; backward-compatible alias maintained

### New Capabilities
- None at spec level (architectural refactor only)

## Approach

**4B (recommended)**: Stop at PR2. PR1 kills the ladder + fixes meta-learner bug (highest value, lowest risk). PR2 builds the unified registry foundation. Transformer/selector migration deferred.

1. Add `from_config(cls, config: Dict, X_train: pd.DataFrame) -> Dict` to each adapter (LGBM, CAT, XGB, NN, LSTM, SimpleTrend, SimpleConstant)
2. Update `TrainingStep._train_single_model`: `params = model_class.from_config(cfg, X_train)` (replaces ladder)
3. Fix `_build_meta_learner`: wrap adapters with `_SklearnCalibWrapper` for 2D `predict_proba`
4. Extract `Registry(name)` class with `register`/`get` methods
5. Create `model_registry`, `transformer_registry`, `selector_registry` instances
6. Keep `ModelRegistry` as alias to `model_registry` (deprecation warning)

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/modeling/registry.py` | Modified | Add `from_config` to each adapter; migrate to `Registry` |
| `src/energizados/core/steps/training.py` | Modified | Replace `_prepare_model_params` with `from_config`; fix `_build_meta_learner` |
| `src/energizados/core/registry.py` | New | Extract unified `Registry` class |
| `src/energizados/modeling/ensemble.py` | Modified | Fix `_build_meta_learner` bug via wrapper |
| `src/energizados/modeling/adapters.py` | Modified | Add `from_config` classmethods |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Behavior change in YAML config parsing | Med | RED→GREEN behavior-preservation tests before deleting ladder |
| Pickle incompatibility from class moves | Low | No class moves; only adding methods (pickle-safe) |
| Breaking public extension points | Low | `ModelRegistry` becomes backward-compatible alias; `custom_class` unchanged |

## Rollback Plan

- PR1: Keep `_prepare_model_params` deprecated (not deleted) for one release; revert `from_config` calls if issues found
- PR2: `ModelRegistry` alias allows revert to old pattern; delete `core/registry.py` if needed
- Existing `.pkl` files load unchanged (no class `__module__` changes)

## Dependencies

- Change #2 (contracts-consolidation): DONE — provides clean foundation
- Change #3 (core-layering): DONE — eliminates cycles, shifted ladder line numbers but structure unchanged

## Success Criteria

- [ ] Adding a model type requires ONE edit (register + `from_config`), not two
- [ ] Meta-learner works with any registered model type (not just `logistic_regression`)
- [ ] All existing tests pass (`pytest tests/`)
- [ ] Behavior-preservation tests verify `from_config` produces identical kwargs to old ladder
- [ ] `ModelRegistry` public alias resolves without deprecation warning in current release
