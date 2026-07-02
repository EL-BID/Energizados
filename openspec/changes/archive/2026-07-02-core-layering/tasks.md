# Tasks: Core Layering

> Change: `core-layering` (change #3 of 4 in `framework-core-redesign` program).  
> Implements the 6-edge kill-cycle scope from the design (supersedes the 4-edge count in the proposal/spec).  
> Strict TDD is ON (`pytest tests/`). Every implementation task is paired with its failing test (RED → GREEN).  
> Single PR (well under 400-line budget — estimated ~60-80 lines).

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~60-80 lines (6 edges × ~10-15 lines each) |
| 400-line budget risk | Low |
| Chained PRs recommended | No (single PR) |
| Delivery strategy | N/A (single PR, no splitting needed) |
| Chain strategy | N/A |
| Decision needed before apply | No |

> No chained PRs needed. This is a small, focused change with ~60-80 lines total (well under 400-line budget). All edges can be implemented in one PR with clear RED→GREEN test flow.

## Task Structure

All tasks are grouped into a single PR with strict RED→GREEN TDD order:

**Phase 1: Cycle Detection Test (RED)**
- Task 1: Add RED test that FAILS before any changes (verifies cycles exist)

**Phase 2: Edge Cutting (GREEN)**
- Tasks 2-7: One task per edge (6 edges total), each fixes a specific import

**Phase 3: Verification (GREEN)**
- Task 8: Full test suite verification + public-path checks

## Phase 1: Cycle Detection Test (RED)

### Task 1.1: RED — Core cycle detection test

**Objective:** Add a test that FAILS now (detecting the 6 cycle-forming edges) and will PASS after all edges are cut. This test must use AST to scan ALL `src/energizados/core/**/*.py` files and assert ZERO module-level imports to concrete packages.

**Implementation:**
- Create `tests/test_core_layering.py` with `test_core_has_no_module_level_imports_to_concrete_packages()`
- Use AST to scan all `*.py` files under `src/energizados/core/` (including subdirectories)
- Assert NO module-level imports to these forbidden prefixes:
  - `energizados.etl`
  - `energizados.evaluation`
  - `energizados.inference`
  - `energizados.modeling`
  - `energizados.feature_engineering`
- Allow (do NOT flag) these imports:
  - `energizados.eda` (not a cycle — eda does NOT import core)
  - `energizados.contracts` (leaf package, safe)
- Implementation MUST exclude in-method lazy imports (scan module-level only)

**Test behavior:**
- **BEFORE change:** FAILS with 6 violations (edges 1-6)
- **AFTER change:** PASSES with 0 violations (all 6 edges are lazy or repointed)
- **eda_builder.py:11:** MUST still import `DatasetExplorer` (not flagged, explicitly allowed)

**Files:** `tests/test_core_layering.py`

**Scenarios:** core-layering-spec/REQ "Core Has Zero Module-Level Edges to Concrete Packages" (AST verification scenario)

**Acceptance:** Test runs and FAILS with 6 violations before any code changes. Test lists the 6 violating file:line pairs clearly.

**Estimated lines:** ~50 lines

**Example violations (expected before change):**
```
Found 6 module-level imports to concrete packages:
- (src/energizados/core/__init__.py, 'energizados.etl.base', 20)
- (src/energizados/core/builders/etl_builder.py, 'energizados.etl.orchestrator', 11)
- (src/energizados/core/builders/evaluation_builder.py, 'energizados.evaluation', 12)
- (src/energizados/core/builders/inference_builder.py, 'energizados.inference.default', 19)
- (src/energizados/core/steps/training.py, 'energizados.feature_engineering', 17)
- (src/energizados/core/steps/training.py, 'energizados.modeling.registry', 18)
```

### Task 1.2: RED — EDA import preservation test

**Objective:** Add a test that verifies `eda_builder.py:11` remains UNCHANGED (not a cycle, should stay as-is). This test PASSES now and must continue PASSING after all changes.

**Implementation:**
- Add `test_eda_import_remains_unchanged()` to `tests/test_core_layering.py`
- Assert `src/energizados/core/builders/eda_builder.py` contains `from energizados.eda.dataset_explorer import DatasetExplorer`
- This is a POSITIVE test — it checks that a safe edge is NOT removed

**Test behavior:**
- **BEFORE change:** PASSES (eda import exists)
- **AFTER change:** PASSES (eda import still exists, untouched)

**Files:** `tests/test_core_layering.py`

**Scenarios:** core-layering-spec/REQ "Non-goals" (Edge 5 untouched scenario)

**Acceptance:** Test passes before and after the change

**Estimated lines:** ~8 lines

## Phase 2: Edge Cutting (GREEN)

### Task 2.1: GREEN — Edge 1: Repoint BaseETL import in core/__init__.py:20

**Objective:** Cut Edge 1 by repointing `core/__init__.py:20` from `energizados.etl.base` to `energizados.contracts`. The re-export in `core/__init__.py` keeps `from energizados.core import BaseETL` working.

**Before:**
```python
# src/energizados/core/__init__.py:20
from energizados.etl.base import BaseETL
```

**After:**
```python
from energizados.contracts import BaseETL
```

**Verification:**
- `from energizados.core import BaseETL` returns the same class (now sourced from `contracts`)
- `BaseETL.__module__` is now `"energizados.contracts"` (was `"energizados.etl.base"`)
- `energizados.etl.base` is a shim that also re-exports from `contracts` (from change #2), so existing code still works

**Files:** `src/energizados/core/__init__.py`

**Scenarios:** core-layering-spec/REQ "Edge 1 — BaseETL Import Repoint" (all scenarios)

**Acceptance:** Task 1.1 test now reports 5 violations (Edge 1 fixed). Public-path test: `from energizados.core import BaseETL` resolves and `BaseETL.__module__ == "energizados.contracts"`.

**Estimated lines:** ~1 line (repoint 1 import)

### Task 2.2: GREEN — Edge 2: Lazy import ETLOrchestrator in etl_builder.py:11

**Objective:** Cut Edge 2 by moving the `ETLOrchestrator` import from module-top into the `build()` method where it's used (line 35). Convert type hint at line 45 to string annotation.

**Before:**
```python
# src/energizados/core/builders/etl_builder.py:11
from energizados.etl.orchestrator import ETLOrchestrator

def build(self) -> Optional[PipelineStep]:
    # ...
    orchestrator = ETLOrchestrator(etl_configs)  # line 35
    # ...
    class ETLStep(PipelineStep):
        def __init__(self, orchestrator: ETLOrchestrator, etl_names: List[str]):  # line 45
```

**After:**
```python
# Remove module-top import (line 11)

def build(self) -> Optional[PipelineStep]:
    # Lazy import at line 35
    from energizados.etl.orchestrator import ETLOrchestrator

    orchestrator = ETLOrchestrator(etl_configs)
    # ...
    class ETLStep(PipelineStep):
        def __init__(self, orchestrator: "ETLOrchestrator", etl_names: List[str]):  # string annotation
```

**Verification:**
- `ETLOrchestrator` is instantiated only at line 35 (now inside `build()`)
- Type hint uses string annotation `"ETLOrchestrator"` (no module-level import needed)
- Behavior unchanged: `ETLBuilder.build()` returns same `ETLStep` with same `ETLOrchestrator` instance

**Files:** `src/energizados/core/builders/etl_builder.py`

**Scenarios:** core-layering-spec/REQ "Edge 2 — ETLOrchestrator Lazy Import" (all scenarios)

**Acceptance:** Task 1.1 test now reports 4 violations (Edge 2 fixed). `ETLBuilder` behavior unchanged (same class instantiated).

**Estimated lines:** ~2 lines (remove 1 import, add 1 inside method, change type hint)

### Task 2.3: GREEN — Edge 3: Lazy import DefaultEvaluator in evaluation_builder.py:12

**Objective:** Cut Edge 3 by moving the `DefaultEvaluator` import from module-top into the `build()` method where it's used (line 66).

**Before:**
```python
# src/energizados/core/builders/evaluation_builder.py:12
from energizados.evaluation import DefaultEvaluator

def build(self) -> Optional[PipelineStep]:
    # ...
    return DefaultEvaluator(  # line 66
        input_path=eval_config.get("input_path"),
        # ...
    )
```

**After:**
```python
# Remove module-top import (line 12)

def build(self) -> Optional[PipelineStep]:
    # ... (config parsing lines 48-65)

    # Lazy import at line 66
    from energizados.evaluation import DefaultEvaluator

    return DefaultEvaluator(
        input_path=eval_config.get("input_path"),
        # ...
    )
```

**Verification:**
- `DefaultEvaluator` is instantiated only at line 66 (now inside `build()`)
- No type hint uses this class
- Behavior unchanged: `EvaluationBuilder.build()` returns same `DefaultEvaluator` instance

**Files:** `src/energizados/core/builders/evaluation_builder.py`

**Scenarios:** core-layering-spec/REQ "Edge 3 — DefaultEvaluator Lazy Import" (all scenarios)

**Acceptance:** Task 1.1 test now reports 3 violations (Edge 3 fixed). `EvaluationBuilder` behavior unchanged.

**Estimated lines:** ~2 lines (remove 1 import, add 1 inside method)

### Task 2.4: GREEN — Edge 4: Lazy import DefaultInference in inference_builder.py:19

**Objective:** Cut Edge 4 by moving the `DefaultInference` import from module-top into the `build()` method where it's used (line 51).

**Before:**
```python
# src/energizados/core/builders/inference_builder.py:19
from energizados.inference.default import DefaultInference

def build(self) -> Optional[PipelineStep]:
    # ...
    if custom_class:
        InferenceClass = import_class(custom_class)
    else:
        InferenceClass = DefaultInference  # line 51
```

**After:**
```python
# Remove module-top import (line 19)

def build(self) -> Optional[PipelineStep]:
    # ... (config parsing lines 39-48)

    if custom_class:
        InferenceClass = import_class(custom_class)
    else:
        # Lazy import at line 51
        from energizados.inference.default import DefaultInference
        InferenceClass = DefaultInference
```

**Verification:**
- `DefaultInference` is only assigned at line 51 (now inside `build()`)
- No type hint uses this class
- Behavior unchanged: `InferenceBuilder.build()` returns same `DefaultInference` instance

**Files:** `src/energizados/core/builders/inference_builder.py`

**Scenarios:** core-layering-spec/REQ "Edge 4 — DefaultInference Lazy Import" (all scenarios)

**Acceptance:** Task 1.1 test now reports 2 violations (Edge 4 fixed). `InferenceBuilder` behavior unchanged.

**Estimated lines:** ~2 lines (remove 1 import, add 1 inside method)

### Task 2.5: GREEN — Edge 5: Lazy import DefaultFeatureEngineering in training.py:17

**Objective:** Cut Edge 5 by moving the `DefaultFeatureEngineering` import from module-top into the `execute()` method where it's used (line 306).

**Before:**
```python
# src/energizados/core/steps/training.py:17
from energizados.feature_engineering import DefaultFeatureEngineering

def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
    # ... (lines 189-305: data loading, filtering, datetime handling) ...

    feature_engineering = DefaultFeatureEngineering(  # line 306
        preprocessing_config=fe_config,
        feature_selection_config=fs_config,
    )
```

**After:**
```python
# Remove module-top import (line 17)

def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
    # ... (lines 189-305: data loading, filtering, datetime handling) ...

    # Lazy import at line 306 (inside execute)
    from energizados.feature_engineering import DefaultFeatureEngineering

    feature_engineering = DefaultFeatureEngineering(
        preprocessing_config=fe_config,
        feature_selection_config=fs_config,
    )
```

**Verification:**
- `DefaultFeatureEngineering` is instantiated only at line 306 (now inside `execute()`)
- No type hint uses this class
- `execute()` is called at runtime by `Pipeline.run()`, not at module load
- Behavior unchanged: `TrainingStep.execute()` returns same `DefaultFeatureEngineering` instance

**Files:** `src/energizados/core/steps/training.py`

**Scenarios:** core-layering-spec/REQ "Edge 5 — DefaultFeatureEngineering Lazy Import" (all scenarios)

**Acceptance:** Task 1.1 test now reports 1 violation (Edge 5 fixed). `TrainingStep` behavior unchanged.

**Estimated lines:** ~2 lines (remove 1 import, add 1 inside method)

### Task 2.6: GREEN — Edge 6: Lazy import ModelRegistry in training.py:18

**Objective:** Cut Edge 6 by moving the `ModelRegistry` import from module-top into the `_train_single_model()` method where it's used (line 592).

**Before:**
```python
# src/energizados/core/steps/training.py:18
from energizados.modeling.registry import ModelRegistry

def _train_single_model(self, ...):
    # ... (lines 572-591: prep work) ...

    model_class = ModelRegistry.get(model_type)  # line 592
```

**After:**
```python
# Remove module-top import (line 18)

def _train_single_model(self, ...):
    # ... (lines 572-591: prep work) ...

    # Lazy import at line 592 (inside _train_single_model)
    from energizados.modeling.registry import ModelRegistry

    model_class = ModelRegistry.get(model_type)
```

**Verification:**
- `ModelRegistry` is used only at line 592 (`ModelRegistry.get(model_type)`)
- No type hint uses this class
- `_train_single_model()` is called from `execute()` at runtime, not at module load
- Behavior unchanged: `_train_single_model()` returns same `ModelRegistry.get()` result

**Files:** `src/energizados/core/steps/training.py`

**Scenarios:** core-layering-spec/REQ "Edge 6 — ModelRegistry Lazy Import" (all scenarios)

**Acceptance:** Task 1.1 test now reports 0 violations (Edge 6 fixed, ALL CYCLES ELIMINATED). `TrainingStep._train_single_model()` behavior unchanged.

**Estimated lines:** ~2 lines (remove 1 import, add 1 inside method)

## Phase 3: Verification (GREEN)

### Task 3.1: GREEN — Public import path tests

**Objective:** Add tests to verify all public import paths still work after the changes.

**Implementation:**
- Add `test_core_import_paths()` to `tests/test_core_layering.py`
- Verify `from energizados.core import BaseETL` works and returns class from `contracts`
- Verify `BaseETL.__module__` is `"energizados.contracts"`
- Verify `from energizados.etl.base import BaseETL` still works (shim re-export)
- Verify `issubclass(SourceETL, BaseETL)` passes (SourceETL inherits from BaseETL via contracts)

**Files:** `tests/test_core_layering.py`

**Scenarios:** core-layering-spec/REQ "Backward Compatibility" (all import path scenarios)

**Acceptance:** All public import paths resolve correctly. BaseETL now sourced from contracts, but old paths still work.

**Estimated lines:** ~15 lines

### Task 3.2: GREEN — Behavior preservation tests

**Objective:** Add tests to verify each builder's behavior is unchanged after lazy imports.

**Implementation:**
- Add `test_lazy_imports_behavior_preserved()` to `tests/test_core_layering.py`
- Verify `ETLBuilder.build()` returns `ETLStep` with correct `ETLOrchestrator` instance
- Verify `EvaluationBuilder.build()` returns step with correct `DefaultEvaluator` instance
- Verify `InferenceBuilder.build()` returns step with correct `DefaultInference` instance
- Verify `TrainingStep.execute()` instantiates correct `DefaultFeatureEngineering` and `ModelRegistry`

**Files:** `tests/test_core_layering.py`

**Scenarios:** core-layering-spec/REQ "No Behavior Change" (all scenarios)

**Acceptance:** Each builder produces identical runtime behavior with lazy imports (same class instantiated, same configuration).

**Estimated lines:** ~20 lines

### Task 3.3: GREEN — Full test suite verification

**Objective:** Run the full test suite to ensure no regressions. This is the authoritative verification — run from a CLEAN tree to avoid stale-state artifacts.

**Implementation:**
- Run `pytest tests/` from a clean working tree
- Clean tree means: no `output/` artifacts, no `data/temp/splits/` files
- E2e/integration tests write to these directories, so a dirty tree can hide failures
- This test validates that lazy imports don't break anything in the framework

**Files:** All test files (existing suite)

**Scenarios:** core-layering-spec/REQ "all_existing_tests_pass"

**Acceptance:** `pytest tests/` exits with code 0 (all tests pass). No new failures introduced.

**Estimated lines:** 0 lines (verification only)

### Task 3.4: GREEN — Module load verification (sys.modules check)

**Objective:** Verify that `import energizados.core` does NOT trigger concrete package imports.

**Implementation:**
- Add `test_core_module_load_does_not_trigger_concrete_imports()` to `tests/test_core_layering.py`
- In a fresh subprocess, import `energizados.core` and check `sys.modules`
- Assert `energizados.etl`, `energizados.evaluation`, `energizados.inference`, `energizados.modeling`, `energizados.feature_engineering` are NOT in `sys.modules`
- Allow `energizados.eda` (safe edge) and `energizados.contracts` (leaf)

**Files:** `tests/test_core_layering.py`

**Scenarios:** core-layering-spec/REQ "Core Has Zero Module-Level Edges to Concrete Packages" (sys.modules verification scenario)

**Acceptance:** After `import energizados.core`, concrete packages are NOT in `sys.modules` (unless explicitly imported elsewhere).

**Estimated lines:** ~12 lines

## Implementation Order

**Strict RED→GREEN sequence (no parallelization):**

1. **Phase 1 (RED):** Task 1.1 → Task 1.2 (cycle detection tests)
2. **Phase 2 (GREEN):** Task 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 (edges 1-6 in order)
3. **Phase 3 (GREEN):** Task 3.1 → 3.2 → 3.3 → 3.4 (verification)

**Dependencies:**
- Task 1.1 MUST complete first (establishes RED baseline)
- Tasks 2.1-2.6 MUST execute sequentially (each edge is independent, but sequential order ensures clean progress)
- Tasks 3.1-3.4 can run in parallel after Phase 2 completes (all are independent verification checks)

**Work-Unit Commit Suggestions (single PR, 8 commits):**

1. `test(core): add cycle detection test (RED)` — Task 1.1 + 1.2
2. `fix(core): repoint BaseETL import to contracts` — Task 2.1 (Edge 1)
3. `refactor(builders): lazy import ETLOrchestrator` — Task 2.2 (Edge 2)
4. `refactor(builders): lazy import DefaultEvaluator` — Task 2.3 (Edge 3)
5. `refactor(builders): lazy import DefaultInference` — Task 2.4 (Edge 4)
6. `refactor(steps): lazy import DefaultFeatureEngineering` — Task 2.5 (Edge 5)
7. `refactor(steps): lazy import ModelRegistry` — Task 2.6 (Edge 6)
8. `test(core): add verification tests (GREEN)` — Tasks 3.1 + 3.2 + 3.3 + 3.4

## Key Invariants to Preserve

1. **Pickle safety:** No class moves. Concretes keep their `__module__`. Only BaseETL repoints to contracts (which is where `etl.base` already re-exported from).
2. **Public paths:** `from energizados.core import BaseETL` works (re-exported from contracts). `from energizados.etl.base import BaseETL` works (shim re-export).
3. **Behavior preservation:** Lazy imports execute at same time as before (during `build()` or `execute()`), just relocated from module-top.
4. **EDA edge untouched:** `eda_builder.py:11` imports `DatasetExplorer` (not a cycle, must remain).
5. **Type hints:** String annotations (`"ETLOrchestrator"`) avoid module-level imports.
6. **No DI seams:** This change does NOT add factory parameters for fake injection (deferred to follow-up).

## Test Coverage Summary

| Category | Tests | Purpose |
|----------|-------|---------|
| Cycle detection | 2 | AST test verifies zero module-level edges; EDA test verifies safe edge untouched |
| Public paths | 4 | Verify `from energizados.core import BaseETL` works and sources from contracts |
| Behavior preservation | 6 | Verify each builder produces same concrete instance after lazy import |
| Full suite | 1 | Run `pytest tests/` to catch any regressions |
| Module load | 1 | Verify `import energizados.core` doesn't trigger concrete imports |

**Total:** ~14 test assertions across 8 tasks.

## Success Criteria

### Code Changes
- [ ] `core/__init__.py:20` imports `BaseETL` from `energizados.contracts`
- [ ] `etl_builder.py` has no module-top import of `ETLOrchestrator` (import inside `build()`)
- [ ] `evaluation_builder.py` has no module-top import of `DefaultEvaluator` (import inside `build()`)
- [ ] `inference_builder.py` has no module-top import of `DefaultInference` (import inside `build()`)
- [ ] `training.py` has no module-top imports of `DefaultFeatureEngineering` or `ModelRegistry` (import inside `execute()` and `_train_single_model()`)
- [ ] Type hints use string annotations (no runtime import)

### Tests
- [ ] `pytest tests/test_core_layering.py::test_core_has_no_module_level_imports_to_concrete_packages` passes (AST verification)
- [ ] `pytest tests/test_core_layering.py::test_eda_import_remains_unchanged` passes (EDA edge untouched)
- [ ] `pytest tests/test_core_layering.py::test_core_import_paths` passes (public paths work)
- [ ] `pytest tests/test_core_layering.py::test_lazy_imports_behavior_preserved` passes (behavior unchanged)
- [ ] `pytest tests/test_core_layering.py::test_core_module_load_does_not_trigger_concrete_imports` passes (sys.modules check)
- [ ] `pytest tests/` green (all existing tests pass, no regressions)

### Cycle Verification
- [ ] After `import energizados.core`, concrete packages NOT in `sys.modules`
- [ ] AST/grep check confirms zero module-level imports from `core` to concrete packages
- [ ] `eda_builder.py:11` still imports `DatasetExplorer` (safe edge untouched)

### Budget
- [ ] Diff ≤ ~80 lines (well under 400-line budget)

## Edges Covered (6)

| # | File:line | Mechanism | Instantiation Line | Task |
|---|-----------|-----------|-------------------|------|
| 1 | `core/__init__.py:20` | Repoint to `contracts` | N/A (re-export) | 2.1 |
| 2 | `core/builders/etl_builder.py:11` | Lazy import in `build()` | Line 35: `ETLOrchestrator(etl_configs)` | 2.2 |
| 3 | `core/builders/evaluation_builder.py:12` | Lazy import in `build()` | Line 66: `DefaultEvaluator(...)` | 2.3 |
| 4 | `core/builders/inference_builder.py:19` | Lazy import in `build()` | Line 51: `InferenceClass = DefaultInference` | 2.4 |
| 5 | `core/steps/training.py:17` | Lazy import in `execute()` | Line 306: `DefaultFeatureEngineering(...)` | 2.5 |
| 6 | `core/steps/training.py:18` | Lazy import in `_train_single_model()` | Line 592: `ModelRegistry.get(model_type)` | 2.6 |

## Open Questions

None. The 6-edge scope is verified and well-defined. All tasks are concrete and testable.

## Dependencies

- **Soft-depends on change #2 (`contracts-consolidation`)**: Edge 1 repoints to `energizados.contracts`, which was created in change #2. Assumption: change #2 has landed and `contracts.py` exists.
- **No other dependencies**: Independent of Findings 3 and 4.

## Risk Summary

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **Lazy import timing edge case** | Low | Lazy imports execute in `build()` or `execute()`, which are called at runtime by `ConfigPipelineBuilder` from YAML. No module-level singleton or class-attribute references. Verified per edge. |
| **Type hint consumers break** | Low | String annotations (`"ETLOrchestrator"`) are sufficient. No runtime annotation resolution consumers in the codebase. |
| **Pickle break from BaseETL repoint** | None | No class move. `BaseETL` now lives in `contracts`, but that's where `etl.base` already re-exported from. Pickled `SourceETL` still references `etl.pipeline` (unchanged). |
| **EDA edge mistakenly removed** | Low | Task 1.2 explicitly tests that EDA import remains. Design clearly marks it as out-of-scope. |
| **DI seams expected but missing** | Medium | This change does NOT add fake-injection capability. Documented as out-of-scope. DI-seams work deferred to follow-up. |

## Next Recommended

`apply` — All tasks are concrete and ordered. Ready for implementation with strict RED→GREEN TDD flow.