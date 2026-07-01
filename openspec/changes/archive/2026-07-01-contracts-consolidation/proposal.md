# Proposal: Contracts Consolidation

## Intent

The framework's contract layer (abstract base classes) is **fragmented across 5 packages** and has **documented but missing bases** (`BasePipeline`, `BaseEvaluator`). Base classes live in `core/base.py` (partial), `etl/base.py`, `feature_engineering/base.py`, `feature_selection/base.py`, and `eda/base.py` — with no single source of truth. Several **contract violations** exist: `FeatureSelectionPipeline` does not inherit `BaseFeatureSelector`; `CleanFilesETL` raises `NotImplementedError` for all abstract methods; `HierarchicalInference.load_model` returns `HierarchicalModelContainer` (a dict wrapper), not `BaseModel`. The save/load API is asymmetric: `BaseFeatureEngineering` has `save()/load()`, but `BaseModel` and `BaseFeatureSelector` have none. `BaseInference.load_model`/`save_predictions` are stubs, not abstract methods.

This change consolidates all base classes into a single home (`energizados.contracts` or `core/contracts.py`), adds the missing bases, fixes all violations, and normalizes the save/load API — while maintaining **100% backward compatibility** via shim re-exports and preserving pickle safety for concrete classes.

## Scope

### In Scope

**2A-i: Add contracts home + shims (PR #1, additive/safe)**
- Create `src/energizados/contracts.py` (or `src/energizados/core/contracts.py`) as the single home for all base classes:
  - `BaseModel`, `BaseInference`, `BasePipeline`, `BaseEvaluator`
  - `BaseETL`, `BaseFeatureEngineering`, `BaseFeatureSelector`, `BaseExplorer`
  - Move existing implementations from `core/base.py`, `etl/base.py`, `feature_engineering/base.py`, `feature_selection/base.py`, `eda/base.py`
- Convert old modules to **shim re-exports** (`from energizados.contracts import BaseETL`) — public paths survive unchanged.
- Add the **missing bases**:
  - `BasePipeline(ABC)` with `@abstractmethod` `run()` and optional `validate()` / `get_required_keys()`
  - `BaseEvaluator(ABC)` with `@abstractmethod` `evaluate()` and optional `generate_reports()`
- Make `BaseInference.load_model` and `save_predictions` **proper `@abstractmethod`** (currently stubs that raise `NotImplementedError`).
- **Pickle safety (hard constraint)**: concrete classes (`*Adapter`, `Default*`, `SourceETL`, `ClipOutliersETL`, `GeoFeaturesETL`, `CleanFilesETL`) MUST NOT change `__module__` — only base classes move.
- **Public extension-point compat (hard constraint)**: generated templates and user configs reference `energizados.etl.base.BaseETL`, `energizados.feature_selection.base.BaseFeatureSelector`, `energizados.inference.base.BaseInference`, `energizados.etl.pipeline.SourceETL`, `energizados.etl.pipeline.ClipOutliersETL`, `energizados.etl.pipeline.GeoFeaturesETL`, `energizados.etl.pipeline.CleanFilesETL` — all paths MUST keep resolving via shims.
- Add `tests/test_contracts.py` for per-base abstract-method enforcement tests.
- Document the contracts home in `AGENTS.md`.

**2A-ii: Fix violations + normalize save/load (PR #2)**
- Fix `FeatureSelectionPipeline` inheritance: make it inherit `BaseFeatureSelector` (currently it does not).
- Fix `CleanFilesETL`: either add a `noop_load` hook to `BaseETL` (optional override for non-dataset-producing ETLs) OR create a separate `BaseFileETL` that sidesteps `extract/transform/load` abstract methods. Preferred: `noop_load` hook on `BaseETL` — smaller change.
- Fix `HierarchicalInference.load_model` return type: update `BaseInference.load_model` return type to a `ModelContainer` Protocol (duck-typed, not a concrete class), so both single models and `HierarchicalModelContainer` are valid.
- Normalize save/load: add `save()`/`load()` to `BaseModel` and `BaseFeatureSelector`. Two options:
  - **Option A (preferred)**: factor a `SerializableMixin` with `save()`/`load()` (using `secure_pickle`), mix into both bases.
  - **Option B**: add `save()`/`load()` directly to each base (more duplication).
  - `BaseFeatureEngineering.save()/load()` already exist — migrate them to use the same pattern (or the mixin).
- Update `DefaultEvaluator` to inherit `BaseEvaluator` (currently inherits `PipelineStep` directly).
- Update existing tests and add coverage for new abstract methods.

### Out of Scope

- Finding 1 (core layering / circular dependency) — deferred to change #3 (`core-layering`).
- Finding 3 (exception hierarchy) — already completed in change #1 (`exception-hierarchy`).
- Finding 4 (unified registry) — deferred to change #4 (`unified-registry`).
- The `_anterior` / 12-month domain leak — out-of-scope for the entire program.
- Moving concrete classes (`*Adapter`, `Default*`, `SourceETL`, etc.) — forbidden by pickle-safety constraint.
- Breaking changes to public import paths — shims must preserve all existing paths.

## Capabilities

### New Capabilities

- `contracts`: consolidated base classes + `BasePipeline`, `BaseEvaluator` with proper abstract methods.

### Modified Capabilities

- `inference`: `BaseInference.load_model`/`save_predictions` become true abstract methods (cannot be left unimplemented).
- `feature-selection`: `FeatureSelectionPipeline` now correctly inherits `BaseFeatureSelector`.
- `etl`: `CleanFilesETL` respects the `BaseETL` contract via `noop_load` hook (no more abstract-method violations).
- `serialization`: `BaseModel` and `BaseFeatureSelector` gain `save()`/`load()` (parfait with `BaseFeatureEngineering`).

## Approach

Exploration approach **2A — full consolidation** with a **2-PR split** to respect the 400-line review budget:

1. **PR #1 (2A-i)**: Add contracts module + shims (additive, safe). This PR touches ONLY the new `contracts.py` and the shim conversions of old base modules. No behavior changes, no violation fixes. Fully backward-compatible via re-exports. Zero pickle risk (concrete classes untouched).
2. **PR #2 (2A-ii)**: Fix violations + normalize save/load. This PR touches the violating implementations (`FeatureSelectionPipeline`, `CleanFilesETL`, `HierarchicalInference`) and adds `save()`/`load()` to bases. Depends on PR #1 landing (needs the consolidated contracts).

**Hard constraints enforced:**
- **Pickle safety**: only base classes move; concrete classes keep their `__module__`. Old `model.pkl`/`feature_engineering.pkl` files load unchanged.
- **Public extension-point compat**: all documented import paths (`energizados.etl.base.BaseETL`, etc.) resolve via shims. User code continues to work.
- **Backward compatibility**: new bases are additive; old imports keep working; no breaking API changes.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/contracts.py` | New | Single home for all base classes (BaseModel, BaseInference, BasePipeline, BaseEvaluator, BaseETL, BaseFeatureEngineering, BaseFeatureSelector, BaseExplorer) |
| `src/energizados/core/base.py` | Modified | Becomes a shim re-export from contracts (keeps BaseModel, BaseInference, PipelineStep for backward compat) |
| `src/energizados/etl/base.py` | Modified | Becomes a shim re-export from contracts (keeps BaseETL) |
| `src/energizados/feature_engineering/base.py` | Modified | Becomes a shim re-export from contracts (keeps BaseFeatureEngineering) |
| `src/energizados/feature_selection/base.py` | Modified | Becomes a shim re-export from contracts (keeps BaseFeatureSelector) |
| `src/energizados/eda/base.py` | Modified | Becomes a shim re-export from contracts (keeps BaseExplorer) |
| `src/energizados/inference/base.py` | Modified | Already a shim; update to re-export from contracts |
| `src/energizados/feature_selection/pipeline.py` | Modified | `FeatureSelectionPipeline` now inherits `BaseFeatureSelector` |
| `src/energizados/etl/pipeline.py` | Modified | `CleanFilesETL` gains `noop_load` hook override (or moves to `BaseFileETL`) |
| `src/energizados/inference/hierarchical.py` | Modified | `load_model` return type compatible with `ModelContainer` Protocol |
| `src/energizados/evaluation/evaluator.py` | Modified | `DefaultEvaluator` now inherits `BaseEvaluator` (not `PipelineStep`) |
| `tests/test_contracts.py` | New | Per-base abstract-method enforcement tests |
| `AGENTS.md` | Modified | Document contracts home + public API stability |
| `templates/**` | Unchanged | Public import paths preserved via shims |

**Impact on existing experiments/models**: none. Concrete classes untouched; pickle format unchanged. Old `model.pkl`/`feature_engineering.pkl` files load without migration.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Pickle format break (base class move) | Low | Pickle stores **concrete** class (`LGBMModelAdapter`, `DefaultFeatureEngineering`), not base. Base move is invisible to existing pickles. Test with legacy fixture. |
| Shim re-export breaks `isinstance` checks | Low | `isinstance(obj, BaseETL)` still works because `BaseETL` from old path is the same class (re-exported, not copied). Add test. |
| `FeatureSelectionPipeline` inheritance change breaks subclassing | Low | `FeatureSelectionPipeline` is internal; not documented for user extension. Add migration note in AGENTS.md if any external usage suspected. |
| `BaseInference.load_model` → `@abstractmethod` breaks custom inference | Low | Custom inference templates already implement this (see `templates/src/inference/custom_inference.py.tpl:37`). Only affects incomplete user subclasses — those would have failed at runtime anyway. |
| `noop_load` hook on `BaseETL` is misused | Low | Document clearly in docstring; add test that `BaseETL.run()` still works for normal ETLs. |
| `ModelContainer` Protocol is too permissive | Low | Protocol only validates shape (`hasattr predict`, etc.), not behavior. Same as current duck-typing. Add type tests. |
| 400-line budget exceeded (2A-ii is large) | Medium | 2-PR split keeps each under budget. PR #1 is additive/safe (~200-250 lines). PR #2 is the violation fixes (~150-250 lines). Total ~350-500 lines as estimated. |
| Chained PR delivery miscoordinated | Low | Document dependency explicitly; PR #2 cannot land until PR #1 is merged. Use `chained-pr` skill in apply. |

## Rollback Plan

**Per-PR rollback:**

- **PR #1 (contracts + shims)**: Pure revert. No persisted artifacts affected. Shims removed, bases deleted from contracts. Concrete classes untouched → pickle-safe.
- **PR #2 (violations + save/load)**: Pure revert. `FeatureSelectionPipeline` stops inheriting `BaseFeatureSelector`, `CleanFilesETL` loses `noop_load`, `HierarchicalInference.load_model` reverts to `HierarchicalModelContainer`, `BaseModel`/`BaseFeatureSelector` lose `save()`/`load()`. Existing user code continues to work (backward-compatible changes only).

**Program-level rollback**: Both PRs revert cleanly. No data migration needed. Existing experiments/models unaffected.

## Dependencies

- **Soft-depends on change #1 (`exception-hierarchy`)**: Not a hard dependency, but having `NotFittedError`, `TransformerError`, `FeatureSelectionError`, `InferenceError`, `EvaluatorError` available makes contract-violation fixes cleaner (fitted guards can use `ModelNotFittedError` instead of bare `ValueError`). If change #1 is not yet merged, use bare `ValueError`/`RuntimeError` in 2A-ii and update imports after change #1 lands.
- **No other dependencies**: Independent of Findings 1 and 4. Can run in parallel with change #3 (`core-layering`), though sequencing recommends 2 before 3 (builders can type-hint against consolidated bases).

## Success Criteria

**PR #1 (2A-i):**
- [ ] `contracts.py` exists with all 8 base classes (BaseModel, BaseInference, BasePipeline, BaseEvaluator, BaseETL, BaseFeatureEngineering, BaseFeatureSelector, BaseExplorer).
- [ ] Old base modules (`core/base.py`, `etl/base.py`, etc.) are shims that re-export from `contracts`.
- [ ] `pytest tests/` green; `isinstance(obj, BaseETL)` passes for objects imported from old path.
- [ ] `tests/test_contracts.py` enforces abstract methods on each base.
- [ ] Diff ≤ ~250 lines (under 400-line budget).

**PR #2 (2A-ii):**
- [ ] `FeatureSelectionPipeline` inherits `BaseFeatureSelector` (verified via `issubclass`).
- [ ] `CleanFilesETL` respects `BaseETL` contract (no `NotImplementedError` in abstract methods).
- [ ] `HierarchicalInference.load_model` return type satisfies `ModelContainer` Protocol.
- [ ] `BaseModel` and `BaseFeatureSelector` have `save()`/`load()` methods (or mixin).
- [ ] `BaseInference.load_model` and `save_predictions` are `@abstractmethod` (cannot instantiate without implementation).
- [ ] `DefaultEvaluator` inherits `BaseEvaluator`.
- [ ] `pytest tests/` green; `tests/test_contracts.py` covers new abstract methods.
- [ ] Diff ≤ ~250 lines (under 400-line budget).
- [ ] AGENTS.md updated with contracts home documentation.

**Cross-cutting:**
- [ ] Legacy pickle (`model.pkl`/`feature_engineering.pkl` from before PR #1) loads after both PRs land.
- [ ] All public import paths resolve (`energizados.etl.base.BaseETL`, etc.).
- [ ] Templates (`templates/**/*.tpl`) still generate working code.
- [ ] CHANGELOG entry notes backward compatibility + pickle safety.

## Open Questions

1. **Contracts module location**: `energizados.contracts` (top-level package) vs. `energizados.core.contracts` (inside core). The exploration suggests both. Top-level is cleaner (contracts are a peer to core, not inside it), but `core/contracts.py` keeps core as the architectural home. Default to `energizados.contracts` for layering clarity (finding 1C), but `core/contracts.py` is also acceptable. **Preferred: `energizados.contracts`**.
2. **`CleanFilesETL` fix strategy**: `noop_load` hook on `BaseETL` (smaller, single place) vs. separate `BaseFileETL` class (cleaner separation, but adds a base class). `noop_load` is simpler and keeps the hierarchy flat. **Preferred: `noop_load` hook**.
3. **`SerializableMixin` vs. direct save/load on each base**: Mixin reduces duplication but adds a class to the hierarchy. Direct methods are more explicit. Given the small number of bases (3: `BaseModel`, `BaseFeatureSelector`, and potentially `BaseETL`), **prefer direct methods** for clarity. Mixin only if duplication becomes burdensome.
4. **`BasePipeline.run()` signature**: Should it match `PipelineStep.execute(context)` (dict-based, stateful) or be a simpler `run(config)`? Given `PipelineStep` already exists and `ConfigPipelineBuilder` drives the framework, `BasePipeline` should likely align with the existing `PipelineStep` pattern. **Default: `run(context) -> Dict` matching `PipelineStep.execute`**, but this is open to refinement in spec.
5. **`BaseEvaluator.evaluate()` signature**: Should it return a `dict` (metrics) or an `EvaluationResult` dataclass? The current `DefaultEvaluator.run(context)` returns the context; metrics are computed internally and written to reports. For the base contract, **prefer `evaluate(X, y, model) -> Dict[str, float]`** (simple, testable). Report generation can be a separate optional method.
