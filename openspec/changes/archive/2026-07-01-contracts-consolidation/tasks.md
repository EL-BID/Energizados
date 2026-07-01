# Tasks: Contracts Consolidation

> Change: `contracts-consolidation` (change #2 of 4 in `framework-core-redesign` program).
> Implements all 5 delta specs: contracts, inference, feature-selection, etl, serialization.
> Approach 2A (full consolidation) with 2-PR split.
> Strict TDD is ON (`pytest tests/`). Every implementation task is paired with its failing test (RED → GREEN).

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~400-450 lines (PR#1: 200-250, PR#2: 200-250) |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes (2 PRs) |
| Suggested split | PR#1 (contracts+shims), PR#2 (violations+save/load) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes (2 PRs)
Chain strategy: stacked-to-main
400-line budget risk: Medium

> Review-budget decision: 2-PR split keeps each PR under 400 lines. `ask-on-risk` requires user confirmation for chained PRs. `stacked-to-main` strategy recommended for fast iteration.

## PR#1 (2A-i): Add contracts.py + shims + missing bases

**Goal:** Create the single contracts home, convert old modules to shims, add missing `BasePipeline` and `BaseEvaluator`, make `BaseInference.load_model`/`save_predictions` proper abstract methods. Purely additive, no behavior changes, no violation fixes.

### Phase 1: contracts.py foundation (WU1)

- [ ] 1.1 RED — Create `tests/test_contracts.py` with `TestContractsModule`, `TestAllBasesExist`, `TestAbstractMethodsEnforced`. Test that all 8 base classes exist in `energizados.contracts`, have required abstract methods, and cannot be instantiated without implementation. **Files:** `tests/test_contracts.py`. **Scenarios:** contracts-spec/REQ1 (contracts module exports all 8 bases), REQ2 (Missing Bases Added). **Acceptance:** tests fail — `contracts.py` doesn't exist, bases not defined. ~60 lines.

- [ ] 1.2 GREEN — Create `src/energizados/contracts.py` with all 8 base classes:
  - `BaseModel` (existing abstract methods: `fit`, `predict`, `predict_proba`, `get_raw_model`)
  - `BaseInference` (existing abstract methods: `predict`, `predict_proba`, plus make `load_model` and `save_predictions` `@abstractmethod`)
  - `BasePipeline` (NEW: `@abstractmethod run(context) -> Dict`, optional `validate()`, `get_required_keys()`)
  - `BaseEvaluator` (NEW: `@abstractmethod evaluate(X, y, model, threshold=0.5, **kwargs) -> Dict[str, float]`, optional `generate_reports()`)
  - `BaseETL` (existing: `extract`, `transform`, `load`, plus `run()` method, `_is_noop_load` flag, `noop_load()` hook)
  - `BaseFeatureEngineering` (existing: `fit`, `transform`, `save()`, `load()`, `get_feature_names_out()`, `check_fitted()`)
  - `BaseFeatureSelector` (existing: `fit`, `transform`, `get_selected_features()`, `get_audit_stats()`)
  - `BaseExplorer` (existing: `explore()`)
  
  Also add `ModelContainer` Protocol (duck-typed: `predict_proba(X)`, `predict(X)`). **Files:** `src/energizados/contracts.py`. **Scenarios:** contracts-spec/REQ1, REQ2 (BasePipeline, BaseEvaluator). **Acceptance:** 1.1 passes; all bases defined with correct abstract methods; module imports successfully. ~200 lines.

- [ ] 1.3 — Add docstrings and type hints to all base classes in `contracts.py`. Ensure consistency with existing patterns. **Files:** `src/energizados/contracts.py`. **Scenarios:** contracts-spec/REQ1. **Acceptance:** all classes have comprehensive docstrings with Args/Returns/Raises. ~40 lines.

### Phase 2: Shim re-exports (WU2)

- [ ] 2.1 RED — Extend `tests/test_contracts.py` with `TestShimReexports`, `TestIsinstanceFromShim`. Test that old modules re-export the same class object (not copies), and `isinstance` checks from old paths pass. **Files:** `tests/test_contracts.py`. **Scenarios:** contracts-spec/REQ1 (old base modules are shims), REQ7 (isinstance from old path works). **Acceptance:** tests fail — shims don't exist yet. ~30 lines.

- [ ] 2.2 GREEN — Convert old base modules to shim re-exports:
  - `src/energizados/core/base.py` → re-export `BaseModel`, `BaseInference` from contracts (keep `PipelineStep` — it's not in contracts)
  - `src/energizados/etl/base.py` → re-export `BaseETL` from contracts
  - `src/energizados/feature_engineering/base.py` → re-export `BaseFeatureEngineering` from contracts
  - `src/energizados/feature_selection/base.py` → re-export `BaseFeatureSelector` from contracts
  - `src/energizados/eda/base.py` → re-export `BaseExplorer` from contracts
  - `src/energizados/inference/base.py` → already a shim; update to re-export from contracts
  
  Each shim module should only contain: `from energizados.contracts import <ClassName>` and `__all__ = ["<ClassName>"]`. **Files:** `core/base.py`, `etl/base.py`, `feature_engineering/base.py`, `feature_selection/base.py`, `eda/base.py`, `inference/base.py`. **Scenarios:** contracts-spec/REQ1 (shims), REQ7 (backward compatibility). **Acceptance:** 2.1 passes; old import paths resolve; `isinstance` checks pass; shims re-export same object (identity check passes). ~25 lines.

### Phase 3: Abstract method enforcement tests (WU3)

- [ ] 3.1 GREEN — Extend `tests/test_contracts.py` with per-base abstract method tests:
  - `TestBaseModelAbstract` — cannot instantiate without implementing `fit`, `predict`, `predict_proba`, `get_raw_model`
  - `TestBaseInferenceAbstract` — cannot instantiate without implementing `load_model` and `save_predictions` (NEW requirement)
  - `TestBasePipelineAbstract` — cannot instantiate without implementing `run(context)`
  - `TestBaseEvaluatorAbstract` — cannot instantiate without implementing `evaluate(X, y, model)`
  - `TestBaseETLAbstract` — cannot instantiate without implementing `extract`, `transform`, `load`
  - `TestBaseFeatureEngineeringAbstract` — cannot instantiate without implementing `fit`, `transform`
  - `TestBaseFeatureSelectorAbstract` — cannot instantiate without implementing `fit`, `transform`
  - `TestBaseExplorerAbstract` — cannot instantiate without implementing `explore()`
  
  **Files:** `tests/test_contracts.py`. **Scenarios:** contracts-spec/REQ6 (abstract method enforcement), inference-spec/REQ1 (load_model is abstract), REQ2 (save_predictions is abstract). **Acceptance:** all tests pass; concrete subclasses that omit abstract methods fail at instantiation time with clear `TypeError`. ~80 lines.

### Phase 4: Public import path verification (WU4)

- [ ] 4.1 GREEN — Add `TestPublicImportPaths` to `tests/test_contracts.py`. Verify all documented public import paths resolve:
  - `energizados.core.base.BaseModel`
  - `energizados.core.base.BaseInference`
  - `energizados.etl.base.BaseETL`
  - `energizados.feature_engineering.base.BaseFeatureEngineering`
  - `energizados.feature_selection.base.BaseFeatureSelector`
  - `energizados.eda.base.BaseExplorer`
  - `energizados.inference.base.BaseInference`
  
  Also verify concrete class imports work: `energizados.etl.pipeline.SourceETL`, `energizados.etl.pipeline.ClipOutliersETL`, `energizados.etl.pipeline.GeoFeaturesETL`, `energizados.etl.pipeline.CleanFilesETL`. **Files:** `tests/test_contracts.py`. **Scenarios:** contracts-spec/REQ7 (public import paths), inference-spec/REQ6, feature-selection-spec/REQ6, etl-spec/REQ6. **Acceptance:** all imports succeed; no `ImportError` or `AttributeError`. ~25 lines.

### Phase 5: AGENTS.md documentation (WU5)

- [ ] 5.1 — Add "Base Classes (Public API)" section to `AGENTS.md`. Document:
  - `energizados.contracts` as the single home for all 8 base classes
  - Backward-compatible import paths via shims
  - List all base classes with their purpose
  - Stability commitment (frozen public API)
  
  **Files:** `AGENTS.md`. **Scenarios:** contracts-spec/REQ8 (public API documentation). **Acceptance:** section is clear and complete; lists all 8 bases; mentions shim re-exports. ~35 lines.

## PR#2 (2A-ii): Fix violations + normalize save/load

**Goal:** Fix all documented contract violations, normalize save/load API on `BaseModel` and `BaseFeatureSelector`, ensure pickle safety via legacy fixture test. Depends on PR#1 landing.

### Phase 6: save/load on BaseModel and BaseFeatureSelector (WU6)

- [ ] 6.1 RED — Extend `tests/test_contracts.py` with `TestBaseModelSaveLoad`, `TestBaseFeatureSelectorSaveLoad`, `TestSecurePickleIntegration`. Test:
  - `save()` raises `ModelNotFittedError` when not fitted (both bases)
  - `save()` uses `secure_pickle.secure_dump` (both bases)
  - `load()` uses `secure_pickle.secure_load` (both bases)
  - Fitted state is preserved after round-trip
  - Parent directories are created if needed
  
  **Files:** `tests/test_contracts.py`. **Scenarios:** serialization-spec/REQ1 (BaseModel save/load), REQ2 (BaseFeatureSelector save/load), REQ3 (API consistency), REQ6 (error handling), REQ7 (logging). **Acceptance:** tests fail — `save()`/`load()` methods don't exist yet. ~50 lines.

- [ ] 6.2 GREEN — Add `save()` and `load()` methods to `BaseModel` in `contracts.py`:
  - `save(self, path: str) -> None`: check `is_fitted_`, raise `ModelNotFittedError` if False, create parent dirs, call `secure_dump(self, path)`, log completion
  - `@classmethod load(cls, path: str) -> "BaseModel"`: call `secure_load(path)`, log completion, return loaded model
  
  **Files:** `src/energizados/contracts.py`. **Scenarios:** serialization-spec/REQ1. **Acceptance:** 6.1 tests pass for `BaseModel`. ~25 lines.

- [ ] 6.3 GREEN — Add `save()` and `load()` methods to `BaseFeatureSelector` in `contracts.py`:
  - `save(self, path: str) -> None`: check `selected_features_` is not None, raise `ModelNotFittedError` if None, create parent dirs, call `secure_dump(self, path)`, log completion
  - `@classmethod load(cls, path: str) -> "BaseFeatureSelector"`: call `secure_load(path)`, log completion, return loaded selector
  
  **Files:** `src/energizados/contracts.py`. **Scenarios:** serialization-spec/REQ2. **Acceptance:** 6.1 tests pass for `BaseFeatureSelector`. ~25 lines.

- [ ] 6.4 — Verify `BaseFeatureEngineering.save/load` already use `secure_pickle` (no change needed). Add test asserting the pattern matches the new methods. **Files:** `tests/test_contracts.py`. **Scenarios:** serialization-spec/REQ3 (API consistency). **Acceptance:** test confirms all three bases use the same `secure_pickle` pattern. ~10 lines.

### Phase 7: noop_load hook on BaseETL (WU7)

- [ ] 7.1 RED — Extend `tests/test_contracts.py` with `TestNoopLoadHook`, `TestCleanFilesETLCompliance`. Test:
  - `BaseETL` defines `noop_load()` method that returns empty DataFrame
  - `BaseETL.run()` checks `_is_noop_load` flag before running normal flow
  - Normal ETLs (`SourceETL`) ignore the hook and run extract/transform/load
  - `CleanFilesETL` respects the contract via noop_load hook
  
  **Files:** `tests/test_contracts.py`. **Scenarios:** etl-spec/REQ1 (noop_load hook), REQ2 (CleanFilesETL uses noop_load), REQ3 (backward compatibility), REQ4 (other ETLs unaffected). **Acceptance:** tests fail — hook doesn't exist, `CleanFilesETL` still has `NotImplementedError` stubs. ~40 lines.

- [ ] 7.2 GREEN — Add `_is_noop_load: bool = False` flag and `noop_load()` hook to `BaseETL` in `contracts.py`. Update `BaseETL.run()` to check the flag:
  ```python
  def run(self, output_path: str) -> pd.DataFrame:
      if self._is_noop_load:
          return self.noop_load()
      # Normal flow: extract -> transform -> load
      df = self.extract()
      if len(df) == 0:
          return df
      df = self.transform(df)
      self.load(df, output_path)
      self._on_load_success()
      return df
  ```
  
  **Files:** `src/energizados/contracts.py`. **Scenarios:** etl-spec/REQ1. **Acceptance:** 7.1 tests pass for base ETL behavior. ~10 lines.

- [ ] 7.3 GREEN — Update `CleanFilesETL` in `src/energizados/etl/pipeline.py`:
  - Add `self._is_noop_load = True` in `__init__`
  - Override `noop_load(self) -> pd.DataFrame` with deletion logic (move existing `run()` implementation here)
  - Remove `NotImplementedError` stubs from `extract()`, `transform()`, `load()` (they're never called now)
  
  **Files:** `src/energizados/etl/pipeline.py`. **Scenarios:** etl-spec/REQ2. **Acceptance:** 7.1 tests pass for `CleanFilesETL`; files are deleted; empty DataFrame returned; no `NotImplementedError`. ~15 lines.

### Phase 8: FeatureSelectionPipeline inheritance fix (WU8)

- [ ] 8.1 RED — Extend `tests/test_contracts.py` with `TestFeatureSelectionPipelineInheritance`. Test:
  - `issubclass(FeatureSelectionPipeline, BaseFeatureSelector)` is `True`
  - `FeatureSelectionPipeline` implements `fit()`, `transform()`, `get_selected_features()`, `get_audit_stats()`
  - Fitted `FeatureSelectionPipeline` can `transform()` data
  
  **Files:** `tests/test_contracts.py`. **Scenarios:** feature-selection-spec/REQ1 (inheritance fix), REQ2-5 (required methods work). **Acceptance:** tests fail — `FeatureSelectionPipeline` doesn't inherit `BaseFeatureSelector` yet. ~25 lines.

- [ ] 8.2 GREEN — Update `FeatureSelectionPipeline` in `src/energizados/feature_selection/pipeline.py`:
  - Change inheritance from `PipelineStep` to `BaseFeatureSelector`
  - Ensure `fit(X, y)` calls parent and populates `selected_features_`
  - Ensure `transform(X)` uses selected features
  - Keep existing `get_selected_features()` and `get_audit_stats()` overrides
  
  **Files:** `src/energizados/feature_selection/pipeline.py`. **Scenarios:** feature-selection-spec/REQ1. **Acceptance:** 8.1 tests pass; `issubclass` check passes; pipeline works end-to-end. ~10 lines.

### Phase 9: DefaultEvaluator inheritance fix (WU9)

- [ ] 9.1 RED — Extend `tests/test_contracts.py` with `TestDefaultEvaluatorInheritance`. Test:
  - `issubclass(DefaultEvaluator, BaseEvaluator)` is `True`
  - `issubclass(DefaultEvaluator, PipelineStep)` is `False` (migration, not dual inheritance)
  - `DefaultEvaluator.evaluate()` returns metrics dict
  
  **Files:** `tests/test_contracts.py`. **Scenarios:** contracts-spec/REQ3 (DefaultEvaluator inherits BaseEvaluator). **Acceptance:** test fails — still inherits `PipelineStep`. ~15 lines.

- [ ] 9.2 GREEN — Update `DefaultEvaluator` in `src/energizados/evaluation/evaluator.py`:
  - Change inheritance from `PipelineStep` to `BaseEvaluator`
  - Implement `evaluate(X, y, model, threshold=0.5, **kwargs) -> Dict[str, float]` (extract metrics computation from `execute()`)
  - Keep `execute(context)` for pipeline compatibility (orchestrator uses this)
  - Move report generation to optional `generate_reports(metrics, output_dir)` override
  
  **Files:** `src/energizados/evaluation/evaluator.py`. **Scenarios:** contracts-spec/REQ3. **Acceptance:** 9.1 tests pass; `evaluate()` returns metrics; `execute()` still works for pipeline. ~20 lines.

### Phase 10: HierarchicalInference ModelContainer Protocol (WU10)

- [ ] 10.1 RED — Extend `tests/test_contracts.py` with `TestModelContainerProtocol`, `TestHierarchicalModelContainerSatisfiesProtocol`. Test:
  - `ModelContainer` Protocol checks for `predict_proba(X)` and `predict(X)` methods
  - `BaseModel` subclasses satisfy the Protocol at runtime
  - `HierarchicalModelContainer` satisfies the Protocol at runtime
  - `HierarchicalInference.load_model()` returns Protocol-satisfying object
  
  **Files:** `tests/test_contracts.py`. **Scenarios:** inference-spec/REQ3 (ModelContainer Protocol), REQ4-6 (Protocol satisfaction). **Acceptance:** tests fail — Protocol defined but return type not yet annotated; `HierarchicalModelContainer` not explicitly checked. ~25 lines.

- [ ] 10.2 GREEN — Update `BaseInference.load_model` signature in `contracts.py`:
  - Change return type from `-> BaseModel` to `-> ModelContainer`
  - `ModelContainer` Protocol is already defined in Phase 1 (check that it's `@runtime_checkable`)
  
  **Files:** `src/energizados/contracts.py`. **Scenarios:** inference-spec/REQ3. **Acceptance:** 10.1 tests pass for Protocol definition and type annotation. ~3 lines.

- [ ] 10.3 — Verify `HierarchicalInference.load_model` in `src/energizados/inference/hierarchical.py` returns `HierarchicalModelContainer` which already satisfies `ModelContainer` Protocol (no code change needed). Add comment confirming Protocol satisfaction. **Files:** `src/energizados/inference/hierarchical.py`. **Scenarios:** inference-spec/REQ6 (HierarchicalInference type-compatible). **Acceptance:** code inspection confirms `HierarchicalModelContainer` has `predict_proba()` and `predict()` methods. ~2 lines.

### Phase 11: Legacy pickle round-trip test (WU11)

- [ ] 11.1 — Generate legacy pickle fixtures BEFORE running any PR#2 code changes:
  ```bash
  # In a fresh virtual env with current framework (before PR#1)
  python - << 'EOF'
  import pickle
  from pathlib import Path
  from energizados.modeling.adapters import LGBMModelAdapter
  from energizados.feature_engineering.default import DefaultFeatureEngineering
  import numpy as np
  import pandas as pd
  
  # Create a simple model adapter
  model = LGBMModelAdapter(config={"type": "lightgbm"})
  model.is_fitted_ = True
  model.model_ = None  # Dummy fitted state
  
  # Create a simple feature engineering
  fe = DefaultFeatureEngineering(config={})
  fe.is_fitted_ = True
  
  # Save with regular pickle (not secure_dump, for legacy fixture)
  fixture_dir = Path("tests/fixtures/pickles")
  fixture_dir.mkdir(parents=True, exist_ok=True)
  
  with open(fixture_dir / "legacy_adapter.pkl", "wb") as f:
      pickle.dump(model, f)
  
  with open(fixture_dir / "legacy_feature_eng.pkl", "wb") as f:
      pickle.dump(fe, f)
  
  print("Fixtures generated")
  EOF
  ```
  
  **Files:** `tests/fixtures/pickles/legacy_adapter.pkl`, `tests/fixtures/pickles/legacy_feature_eng.pkl`. **Scenarios:** contracts-spec/REQ5 (pickle safety), serialization-spec/REQ4 (legacy pickle loads). **Acceptance:** fixture files exist; contain dummy fitted instances. 0 lines (fixture generation).

- [ ] 11.2 GREEN — Add `test_legacy_pickle_roundtrip` to `tests/test_contracts.py`. Load both legacy pickles using regular `pickle.load()` (not `secure_load`, since these are legacy fixtures without signatures) and assert:
  - Model loads successfully
  - `model.__module__` is unchanged (`"energizados.modeling.adapters"`)
  - `model.is_fitted_` is `True`
  - Feature engineering loads successfully
  - `fe.__module__` is unchanged (`"energizados.feature_engineering.default"`)
  - `fe.is_fitted_` is `True`
  
  **Files:** `tests/test_contracts.py`. **Scenarios:** contracts-spec/REQ5 (pickle safety), serialization-spec/REQ4. **Acceptance:** test passes; confirms concrete classes keep `__module__` after base move. ~15 lines.

### Phase 12: Template and config compatibility verification (WU12)

- [ ] 12.1 GREEN — Add `TestTemplateCompatibility` to `tests/test_contracts.py`. Verify:
  - `templates/src/inference/custom_inference.py.tpl` implements all abstract methods (`load_model`, `save_predictions`)
  - `templates/*/custom_*.tpl` imports resolve (e.g., `energizados.etl.base.BaseETL`, `energizados.feature_selection.base.BaseFeatureSelector`, `energizados.inference.base.BaseInference`)
  
  **Files:** `tests/test_contracts.py`. **Scenarios:** inference-spec/REQ5 (custom inference templates valid), contracts-spec/REQ7 (templates still generate working code), REQ6 (user configs with custom_class work). **Acceptance:** template inspection confirms all abstract methods implemented; imports resolve. ~20 lines.

### Phase 13: CHANGELOG entry (WU13)

- [ ] 13.1 — Add CHANGELOG entry following the design's template:
  ```markdown
  ### Added
  - `energizados.contracts` — single home for all 8 framework base classes.
  - `BasePipeline` — new base class for user-defined pipelines with `run(context)` contract.
  - `BaseEvaluator` — new base class for model evaluation with `evaluate(X, y, model)` contract.
  - `BaseModel.save()`/`load()` — save/load fitted models via `secure_pickle`.
  - `BaseFeatureSelector.save()`/`load()` — save/load fitted selectors via `secure_pickle`.
  - `ModelContainer` Protocol — duck-typed contract for objects with `predict`/`predict_proba`.
  - `BaseETL.noop_load()` hook — optional override for non-dataset-producing ETLs (e.g., `CleanFilesETL`).

  ### Changed
  - Old base modules (`core/base.py`, `etl/base.py`, etc.) are now shim re-exports from `energizados.contracts`. All public import paths remain unchanged.
  - `BaseInference.load_model` and `save_predictions` are now `@abstractmethod` (cannot be left unimplemented).
  - `BaseInference.load_model` return type is now `ModelContainer` Protocol (accepts single models and `HierarchicalModelContainer`).
  - `DefaultEvaluator` now inherits `BaseEvaluator` (instead of `PipelineStep` directly).
  - `FeatureSelectionPipeline` now inherits `BaseFeatureSelector` (previously inherited `PipelineStep`).
  - `CleanFilesETL` now uses the `noop_load` hook on `BaseETL` (no longer raises `NotImplementedError` in abstract methods).

  ### Fixed
  - Contract violations: `FeatureSelectionPipeline` now correctly inherits `BaseFeatureSelector`.
  - Contract violations: `CleanFilesETL` now respects the `BaseETL` contract via `noop_load` hook.
  - Contract violations: `HierarchicalInference.load_model` return type now accommodates both single models and `HierarchicalModelContainer` via `ModelContainer` Protocol.

  ### Migration Notes
  - **Pickle safety:** Existing `model.pkl` and `feature_engineering.pkl` files load unchanged. Concrete classes keep their `__module__`.
  - **Public import paths:** All documented paths (`energizados.etl.base.BaseETL`, etc.) continue to work via shims.
  - **User code:** No breaking changes. All modifications are additive (new methods, new bases) or fix violations (inheritance corrections).
  ```
  
  **Files:** `CHANGELOG.md`. **Scenarios:** all scenarios (backward compatibility documentation). **Acceptance:** CHANGELOG entry is complete and accurate. ~40 lines.

## Implementation Order

**PR#1 (can merge independently):**
WU1 → WU2 → WU3 → WU4 → WU5

**PR#2 (depends on PR#1):**
WU6 → WU7 → WU8 → WU9 → WU10 → WU11 → WU12 → WU13

**Dependencies:**
- WU1 must complete first (defines `contracts.py` and all bases)
- WU2 depends on WU1 (converts old modules to shims)
- WU6-13 all depend on PR#1 landing (require `contracts.py` to exist)

**Parallel opportunities:**
- Within PR#1: WU3, WU4, WU5 can run in parallel (all are tests/docs that depend on WU1+WU2)
- Within PR#2: WU8, WU9, WU10 can run in parallel (all are independent violation fixes)

## Work-Unit Commit Suggestions

**PR#1 (5 commits):**
1. `feat(contracts): add contracts.py with all 8 base classes` (WU1)
2. `refactor(base): convert old base modules to shim re-exports` (WU2)
3. `test(contracts): add abstract method enforcement tests` (WU3)
4. `test(contracts): verify public import paths and isinstance compatibility` (WU4)
5. `docs(agents): document contracts home as single source of truth` (WU5)

**PR#2 (8 commits):**
1. `feat(contracts): add save/load to BaseModel and BaseFeatureSelector` (WU6)
2. `feat(etl): add noop_load hook to BaseETL` (WU7)
3. `fix(feature-selection): FeatureSelectionPipeline now inherits BaseFeatureSelector` (WU8)
4. `refactor(evaluation): DefaultEvaluator inherits BaseEvaluator` (WU9)
5. `feat(inference): ModelContainer Protocol for load_model return type` (WU10)
6. `test(contracts): add legacy pickle round-trip test` (WU11)
7. `test(contracts): verify template and config compatibility` (WU12)
8. `chore(changelog): document contracts consolidation changes` (WU13)

## Key Invariants to Preserve

1. **Pickle safety:** Concrete classes never move. `LGBMModelAdapter.__module__` stays `"energizados.modeling.adapters"`. Only base classes move to `contracts.py`.
2. **Shim identity:** `energizados.etl.base.BaseETL is energizados.contracts.BaseETL` (same object, not copy).
3. **Backward compatibility:** All public import paths resolve via shims. User code and templates work unchanged.
4. **Abstract enforcement:** `@abstractmethod` means cannot instantiate without implementation. Tests verify this.
5. **Secure pickle:** All `save()`/`load()` methods use `secure_dump`/`secure_load` (SHA-256 signatures).
6. **Noop ETL pattern:** `BaseETL._is_noop_load` flag + `noop_load()` hook is the only exception to extract/transform/load flow.

## Cross-PR Dependencies

- **PR#2 depends on PR#1:** Cannot fix violations or add save/load until `contracts.py` exists and shims are in place.
- **No merge conflicts:** PR#2 only touches `contracts.py` (additive methods) and concrete implementations. PR#1 touched old base modules (shims) and created `contracts.py`. Changes are orthogonal.
- **Chain strategy:** `stacked-to-main` recommended. PR#1 merges to main first. PR#2 targets main (or PR#1 branch if main hasn't advanced). Fast iteration, fix on the go.

## Test Coverage Summary

| Category | Tests | Purpose |
|----------|-------|---------|
| Module existence | 8 | Verify all 8 bases exist in `contracts.py` |
| Abstract enforcement | 16 | Verify abstract methods cannot be bypassed |
| Shim compatibility | 12 | Verify old paths resolve and `isinstance` passes |
| save/load | 24 | Verify `BaseModel` and `BaseFeatureSelector` serialization |
| noop_load | 8 | Verify `BaseETL` hook and `CleanFilesETL` compliance |
| Inheritance fixes | 10 | Verify `FeatureSelectionPipeline` and `DefaultEvaluator` |
| ModelContainer | 6 | Verify Protocol shape and satisfaction |
| Pickle safety | 2 | Verify legacy fixtures load |
| Template compat | 4 | Verify templates and configs work |

**Total:** ~90 test assertions across 13 phases.

## Success Criteria (Cross-PR)

### PR#1 Success
- [x] `contracts.py` exists with all 8 base classes
- [x] Old base modules are shims that re-export from `contracts`
- [x] `pytest tests/test_contracts.py` is green
- [x] `isinstance(obj, BaseETL)` passes for objects imported from old path
- [x] Diff ≤ ~250 lines

### PR#2 Success
- [x] `FeatureSelectionPipeline` inherits `BaseFeatureSelector`
- [x] `CleanFilesETL` respects `BaseETL` contract via `noop_load`
- [x] `HierarchicalInference.load_model` satisfies `ModelContainer` Protocol
- [x] `BaseModel` and `BaseFeatureSelector` have `save()`/`load()`
- [x] `DefaultEvaluator` inherits `BaseEvaluator`
- [x] `pytest tests/test_contracts.py` is green (all phases)
- [x] Legacy pickle round-trip test passes
- [x] Diff ≤ ~250 lines

### Cross-Cutting Success
- [x] All public import paths resolve (`energizados.etl.base.BaseETL`, etc.)
- [x] Templates (`templates/**/*.tpl`) still generate working code
- [x] CHANGELOG entry notes backward compatibility + pickle safety
- [x] AGENTS.md documents contracts home