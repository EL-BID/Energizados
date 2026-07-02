# Tasks: unified-registry

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | PR1: ~200-300 lines; PR2: ~150-200 lines; Total: ~350-500 lines |
| 400-line budget risk | Medium (aggregate within budget; each PR independently reviewable) |
| Chained PRs recommended | Yes (Approach 4B — locked scope) |
| Suggested split | PR1 → PR2 (exactly 2 chained PRs, no PR3) |
| Delivery strategy | auto-chain (locked to Approach 4B) |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Behavior-preservation RED tests for all 7 adapters | PR1 | Base: release/0.2.x; tests/docs included |
| 2 | Add `from_config` to all adapters | PR1 | Depends on Unit 1 (TDD) |
| 3 | Replace `_prepare_model_params` with `from_config` | PR1 | Depends on Unit 2 |
| 4 | Delete `_prepare_model_params` ladder | PR1 | Depends on Unit 3; guarded by equivalence tests |
| 5 | Fix `_build_meta_learner` via `_SklearnCalibWrapper` | PR1 | Independent of Units 1-4; same PR |
| 6 | Create `Registry` class and per-domain instances | PR2 | Base: release/0.2.x; independent of PR1 |
| 7 | Migrate `ModelRegistry` to silent alias | PR2 | Depends on Unit 6 |

## PR1: Kill Ladder + Fix Meta-Learner Bug

### Phase 1: Behavior-Preservation RED Tests (Strict TDD)

- [x] 1.1 Write RED test `test_from_config_lgbm_equivalence` asserting `LGBMModelAdapter.from_config(cfg, X_train) == old_ladder(cfg, X_train)` for representative lightgbm config
- [x] 1.2 Write RED test `test_from_config_cat_equivalence` asserting `CATModelAdapter.from_config(cfg, X_train) == old_ladder(cfg, X_train)` for catboost config with sampling+hyperparam_search
- [x] 1.3 Write RED test `test_from_config_xgb_equivalence` asserting `XGBModelAdapter.from_config(cfg, X_train) == old_ladder(cfg, X_train)` for xgboost config
- [x] 1.4 Write RED test `test_from_config_nn_equivalence` asserting `NNModelAdapter.from_config(cfg, X_train) == old_ladder(cfg, X_train)` verifying features_names/spents_name derivation from `_anterior` cols
- [x] 1.5 Write RED test `test_from_config_lstm_equivalence` asserting `LSTMNNModelAdapter.from_config(cfg, X_train) == old_ladder(cfg, X_train)` for LSTM config
- [x] 1.6 Write RED test `test_from_config_simple_trend_equivalence` asserting `SimpleTrendAdapter.from_config(cfg, X_train) == old_ladder(cfg, X_train)` verifying invalid key removal (sampling, class_weight, hyperparams)
- [x] 1.7 Write RED test `test_from_config_simple_constant_equivalence` asserting `SimpleConstantAdapter.from_config(cfg, X_train) == old_ladder(cfg, X_train)` for simple constant config

### Phase 2: Add from_config Classmethods

- [x] 2.1 Implement `LGBMModelAdapter.from_config(cls, config, X_train)` extracting cols_for_model, sampling flattening, hyperparam_search flattening (lines 802-830 of training.py ladder)
- [x] 2.2 Implement `CATModelAdapter.from_config(cls, config, X_train)` extracting cols_for_model, sampling flattening, hyperparam_search flattening (lines 831-858)
- [x] 2.3 Implement `XGBModelAdapter.from_config(cls, config, X_train)` extracting cols_for_model, sampling flattening, hyperparam_search flattening (lines 859-886)
- [x] 2.4 Implement `NNModelAdapter.from_config(cls, config, X_train)` deriving features_names (non-`_anterior`), spents_names (`_anterior` cols), sampling extraction (lines 887-913)
- [x] 2.5 Implement `LSTMNNModelAdapter.from_config(cls, config, X_train)` deriving features_names/spents_names, sampling extraction (lines 914-940)
- [x] 2.6 Implement `SimpleTrendAdapter.from_config(cls, config, X_train)` extracting last_base_value, last_eval_value, threshold; popping invalid keys (lines 941-957)
- [x] 2.7 Implement `SimpleConstantAdapter.from_config(cls, config, X_train)` extracting min_count_constante; popping invalid keys (lines 958-969)

### Phase 3: Replace Ladder in TrainingStep

- [x] 3.1 Update `TrainingStep._train_single_model` (`core/steps/training.py`) to call `params = model_class.from_config(cfg, X_train)` instead of `_prepare_model_params(cfg, X_train, model_class)`
- [x] 3.2 Verify all Phase 1 RED tests now GREEN (equivalence proven)
- [x] 3.3 Delete `_prepare_model_params` method from `core/steps/training.py` (lines 802-869)

### Phase 4: Fix Meta-Learner Bug

- [x] 4.1 Write test `test_meta_l Adapter_wrapper_predict_proba_2d` asserting `_SklearnCalibWrapper(LGBMModelAdapter()).predict_proba(X).shape == (n, 2)` and `[:,1]` equals adapter's 1D output
- [x] 4.2 Update `EnsembleModel._build_meta_learner` (`modeling/ensemble.py:199-213,232`) to wrap registry-sourced adapters with `_SklearnCalibWrapper` while keeping direct `LogisticRegression` path untouched
- [x] 4.3 Write integration test `test_stacking_with_lightgbm_meta_learner` verifying stacking ensemble with lightgbm meta-learner trains and predicts without `[:,1]` indexing error

### Phase 5: PR1 Verification

- [x] 5.1 Run `pytest tests/` — all existing tests pass
- [x] 5.2 Run behavior-preservation tests — all GREEN
- [x] 5.3 Run meta-learner wrapper test — GREEN
- [x] 5.4 Manual verification: train single model with each adapter type using CLI, confirm metrics match baseline

## PR2: Unified Registry Abstraction

### Phase 1: Registry Class Implementation

- [ ] 1.1 Create `src/energizados/core/registry.py` with `Registry(name)` class (instance methods: `register`, `get`, `is_registered`, `list_registered`)
- [ ] 1.2 Implement case-insensitive storage via `name.lower()` with KeyError containing available names on missing `get`
- [ ] 1.3 Add module-level instances: `model_registry = Registry("models")`, `transformer_registry = Registry("transformers")`, `selector_registry = Registry("selectors")`
- [ ] 1.4 Write unit test `test_registry_case_insensitive_lookup` verifying "CatBoost" and "catboost" resolve same factory
- [ ] 1.5 Write unit test `test_registry_independent_instances` verifying model_registry and selector_registry are isolated

### Phase 2: Migrate ModelRegistry

- [ ] 2.1 Update `modeling/registry._register_default_models()` to call `model_registry.register(name, cls)` instead of `self._registry[name] = cls`
- [ ] 2.2 Convert `ModelRegistry` class to silent alias delegating to `model_registry` (no deprecation warning)
- [ ] 2.3 Write test `test_model_registry_alias_compatibility` verifying `ModelRegistry.register/get/list_models` still work via old import path
- [ ] 2.4 Update `ensemble.py` `_build_meta_learner` to use `model_registry.get` (completing PR1→PR2 swap)

### Phase 3: PR2 Verification

- [ ] 3.1 Run `pytest tests/` — all tests pass
- [ ] 3.2 Verify import `from energizados.modeling.registry import ModelRegistry` resolves without error
- [ ] 3.3 Verify custom model registration via `ModelRegistry.register("custom", CustomModel)` still works
- [ ] 3.4 Manual verification: load existing `.pkl` file, confirm model deserializes without pickle error

## Rollback Boundaries

- **PR1 rollback**: Revert `from_config` calls, restore `_prepare_model_params` ladder, revert `_build_meta_learner` wrapper
- **PR2 rollback**: Delete `core/registry.py`, revert `ModelRegistry` to original class implementation
- **Pickle safety**: Both PRs preserve existing `.pkl` compatibility (no `__module__` changes to concrete adapter classes)

## Dependencies

- **Spec requirement mapping**: Task 1.1-1.7 satisfy "from_config Classmethod Pattern" requirement; Task 3.1-3.3 satisfy "Ladder Replacement via from_config"; Task 4.1-4.3 satisfy "Meta-Learner Fix"; Task 1.1-1.3 satisfy "Unified Registry Abstraction"; Task 2.1-2.4 satisfy "Backward-Compatible ModelRegistry Alias"
- **Design decision mapping**: Task 2.1-2.7 implement Decision 1 (per-adapter `from_config`); Task 4.1-4.3 implement Decision 3 (wrapper fix); Task 1.1-1.3 implement Decision 4 (Registry class); Task 2.1-2.4 implement Decision 5 (silent alias)
- **Sequential vs parallel**: Phase 1 (RED tests) → Phase 2 (from_config) → Phase 3 (ladder replacement) MUST be sequential. Phase 4 (meta-learner fix) can run in parallel with Phase 2-3 but is grouped in PR1 for coherence. PR2 is fully independent of PR1.
