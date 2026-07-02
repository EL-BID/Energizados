# Core Layering Specification

> Capability: `core-layering` — modified (core becomes true foundation with zero module-level edges to concrete packages).  
> Modified capabilities: `core` (behavior unchanged, import paths repointed).  
> `core-layering` proposal, Finding 1, scope (a') kill-cycle only.

## Purpose

The `energizados.core` package becomes a true architectural foundation with zero module-level import edges into concrete implementation packages (`etl`, `evaluation`, `inference`). This eliminates circular dependencies while maintaining 100% backward compatibility and zero behavior change via import repointing and lazy imports.

## Requirements

### Requirement: Edge 1 — BaseETL Import Repoint

`core/__init__.py:20` MUST import `BaseETL` from `energizados.contracts` (not `etl.base`).

#### Scenario: core imports BaseETL from contracts

- GIVEN the `energizados.core` package
- WHEN `core/__init__.py:20` is inspected
- THEN it contains `from energizados.contracts import BaseETL` (not `from energizados.etl.base import BaseETL`)

#### Scenario: BaseETL public import path works

- GIVEN `from energizados.core import BaseETL`
- WHEN the import is executed
- THEN it succeeds and returns the `BaseETL` class from `energizados.contracts` (re-exported via core)

#### Scenario: BaseETL sourced from contracts

- GIVEN `from energizados.core import BaseETL`
- WHEN the class's `__module__` attribute is inspected
- THEN it is `"energizados.contracts"` (not `"energizados.etl.base"`)

#### Scenario: BaseETL isinstance checks work

- GIVEN a `SourceETL` instance from `energizados.etl.pipeline`
- WHEN `isinstance(etl, energizados.core.BaseETL)` is checked
- THEN the result is `True` (SourceETL inherits from BaseETL via contracts)

### Requirement: Edge 2 — ETLOrchestrator Lazy Import

`etl_builder.py` MUST NOT import `ETLOrchestrator` at module level; import inside `build()` method.

#### Scenario: etl_builder has no module-level ETLOrchestrator import

- GIVEN `src/energizados/core/builders/etl_builder.py`
- WHEN the file is scanned for module-top imports
- THEN it does NOT contain `from energizados.etl.orchestrator import ETLOrchestrator` at module level

#### Scenario: ETLOrchestrator imported inside build()

- GIVEN the `ETLBuilder.build()` method
- WHEN the method source is inspected
- THEN it contains `from energizados.etl.orchestrator import ETLOrchestrator` inside the method body (line ~35)

#### Scenario: ETLOrchestrator type hint uses string annotation

- GIVEN the `ETLStep.__init__()` signature inside `build()`
- WHEN the type hint for `orchestrator` parameter is inspected
- THEN it uses string annotation `"ETLOrchestrator"` (not the class object directly)

#### Scenario: ETLBuilder behavior unchanged

- GIVEN an `ETLBuilder` instance configured with ETL definitions
- WHEN `build()` is called
- THEN it returns an `ETLStep` that orchestrates ETLs via `ETLOrchestrator` (same behavior as before)

### Requirement: Edge 3 — DefaultEvaluator Lazy Import

`evaluation_builder.py` MUST NOT import `DefaultEvaluator` at module level; import inside `build()` method.

#### Scenario: evaluation_builder has no module-level DefaultEvaluator import

- GIVEN `src/energizados/core/builders/evaluation_builder.py`
- WHEN the file is scanned for module-top imports
- THEN it does NOT contain `from energizados.evaluation import DefaultEvaluator` at module level

#### Scenario: DefaultEvaluator imported inside build()

- GIVEN the `EvaluationBuilder.build()` method
- WHEN the method source is inspected
- THEN it contains `from energizados.evaluation import DefaultEvaluator` inside the method body (line ~66)

#### Scenario: EvaluationBuilder behavior unchanged

- GIVEN an `EvaluationBuilder` instance configured with evaluation settings
- WHEN `build()` is called
- THEN it returns a `PipelineStep` that evaluates using `DefaultEvaluator` (same behavior as before)

### Requirement: Edge 4 — DefaultInference Lazy Import

`inference_builder.py` MUST NOT import `DefaultInference` at module level; import inside `build()` method.

#### Scenario: inference_builder has no module-level DefaultInference import

- GIVEN `src/energizados/core/builders/inference_builder.py`
- WHEN the file is scanned for module-top imports
- THEN it does NOT contain `from energizados.inference.default import DefaultInference` at module level

#### Scenario: DefaultInference imported inside build()

- GIVEN the `InferenceBuilder.build()` method
- WHEN the method source is inspected around line 51
- THEN it contains `from energizados.inference.default import DefaultInference` inside the method body (conditional branch)

#### Scenario: InferenceBuilder behavior unchanged

- GIVEN an `InferenceBuilder` instance configured with inference settings
- WHEN `build()` is called
- THEN it returns a `PipelineStep` that performs inference using `DefaultInference` (same behavior as before)

### Requirement: Core Has Zero Module-Level Edges to Concrete Packages

The `core` package MUST have zero module-level imports to `etl`, `evaluation`, `inference`, `modeling`, `feature_engineering`, or `eda`.

#### Scenario: core module load does not trigger concrete package imports

- GIVEN a fresh Python interpreter
- WHEN `import energizados.core` is executed
- THEN `sys.modules` does NOT contain `energizados.etl`, `energizados.evaluation`, `energizados.inference`, `energizados.modeling`, `energizados.feature_engineering`, or `energizados.eda`

#### Scenario: core builders import does not trigger concrete package imports

- GIVEN a fresh Python interpreter
- WHEN `import energizados.core.builders` is executed
- THEN `sys.modules` does NOT contain `energizados.etl`, `energizados.evaluation`, `energizados.inference` (builders are safe to import)

#### Scenario: AST verification confirms zero concrete imports

- GIVEN all `*.py` files under `src/energizados/core/`
- WHEN parsed with AST and scanned for `from energizados.etl|evaluation|inference|modeling|feature_engineering|eda` imports
- THEN zero module-level imports are found (lazy imports inside methods are allowed)

#### Scenario: grep verification confirms zero concrete imports

- GIVEN the `src/energizados/core/` directory
- WHEN scanned with `grep -r "^from energizados.etl\|^from energizados.evaluation\|^from energizados.inference\|^from energizados.modeling\|^from energizados.feature_engineering\|^from energizados.eda"`
- THEN no matches are returned (exit code non-zero)

### Requirement: No Behavior Change

All builders MUST produce identical runtime behavior with lazy imports.

#### Scenario: ETLStep produces same orchestrator instance

- GIVEN `ETLBuilder.build()` before and after the change
- WHEN the returned `ETLStep.orchestrator` is inspected
- THEN both are `ETLOrchestrator` instances with identical configuration

#### Scenario: EvaluationStep produces same evaluator instance

- GIVEN `EvaluationBuilder.build()` before and after the change
- WHEN the returned step's evaluator is inspected
- THEN both are `DefaultEvaluator` instances with identical configuration

#### Scenario: InferenceStep produces same inference instance

- GIVEN `InferenceBuilder.build()` before and after the change
- WHEN the returned step's inference engine is inspected
- THEN both are `DefaultInference` instances with identical configuration

### Requirement: Pickle Safety

Concrete classes MUST keep their original `__module__` attributes.

#### Scenario: SourceETL __module__ unchanged

- GIVEN `SourceETL` from `energizados.etl.pipeline`
- WHEN `SourceETL.__module__` is inspected
- THEN it is `"energizados.etl.pipeline"` (unchanged)

#### Scenario: ETLOrchestrator __module__ unchanged

- GIVEN `ETLOrchestrator` from `energizados.etl.orchestrator`
- WHEN `ETLOrchestrator.__module__` is inspected
- THEN it is `"energizados.etl.orchestrator"` (unchanged)

#### Scenario: DefaultEvaluator __module__ unchanged

- GIVEN `DefaultEvaluator` from `energizados.evaluation`
- WHEN `DefaultEvaluator.__module__` is inspected
- THEN it is `"energizados.evaluation.evaluator"` (unchanged)

#### Scenario: DefaultInference __module__ unchanged

- GIVEN `DefaultInference` from `energizados.inference.default`
- WHEN `DefaultInference.__module__` is inspected
- THEN it is `"energizados.inference.default"` (unchanged)

#### Scenario: legacy model.pkl loads

- GIVEN a `model.pkl` file created before this change
- WHEN `secure_load(model.pkl)` is called after the change
- THEN the model loads without error

#### Scenario: legacy feature_engineering.pkl loads

- GIVEN a `feature_engineering.pkl` file created before this change
- WHEN `secure_load(feature_engineering.pkl)` is called after the change
- THEN the pipeline loads without error

### Requirement: Backward Compatibility

All public import paths MUST continue working.

#### Scenario: from energizados.core import BaseETL works

- GIVEN `from energizados.core import BaseETL`
- WHEN the import is executed
- THEN it succeeds and returns the base class (now sourced from contracts)

#### Scenario: from energizados.etl.base import BaseETL works

- GIVEN `from energizados.etl.base import BaseETL`
- WHEN the import is executed
- THEN it succeeds and returns the class from `energizados.contracts` (shim re-export)

#### Scenario: existing templates work

- GIVEN user code or templates using `from energizados.core import BaseETL`
- WHEN the code is executed after this change
- THEN imports resolve and behavior is unchanged

### Requirement: Strict TDD Compliance

Every requirement MUST map to a `pytest` test scenario.

#### Scenario: test_core_layering_cycle_detection exists

- GIVEN `tests/test_core_layering.py` (or equivalent)
- WHEN `pytest tests/test_core_layering.py` is run
- THEN it contains `test_core_has_no_module_level_imports_to_concrete_packages` that uses AST or grep to verify zero imports

#### Scenario: test_core_import_paths_exist

- GIVEN `tests/test_core_layering.py`
- WHEN `pytest tests/test_core_layering.py::test_core_import_paths` is run
- THEN it verifies `from energizados.core import BaseETL` works and `BaseETL.__module__` is `"energizados.contracts"`

#### Scenario: test_lazy_imports_behavior_preserved

- GIVEN `tests/test_core_layering.py`
- WHEN `pytest tests/test_core_layering.py::test_lazy_imports_behavior_preserved` is run
- THEN it verifies each builder's `build()` method returns the same concrete instance type as before

#### Scenario: all_existing_tests_pass

- GIVEN the full test suite
- WHEN `pytest tests/` is run
- THEN all existing tests pass (no regressions)

### Requirement: Non-goals

This change MUST NOT:
- Move concrete classes to different modules (only import repoints)
- Add DI seams/factory parameters for fake injection (deferred to follow-up)
- Modify Edge 5 (`core → eda`) — NOT a cycle, leave as-is
- Modify `training.py` edges — NOT cycles, leave as-is
- Change any behavior besides import timing

#### Scenario: Edge 5 untouched

- GIVEN `src/energizados/core/builders/eda_builder.py:11`
- WHEN inspected
- THEN it still contains `from energizados.eda.dataset_explorer import DatasetExplorer` (no change)

#### Scenario: training.py edges untouched

- GIVEN `src/energizados/core/steps/training.py:17,18`
- WHEN inspected
- THEN imports to `feature_engineering` and `modeling.registry` remain (no change)

#### Scenario: no factory parameters added

- GIVEN the builder classes (`ETLBuilder`, `EvaluationBuilder`, `InferenceBuilder`)
- WHEN their `__init__` signatures are inspected
- THEN they do NOT have factory parameters for concrete injection (DI seams deferred)

## Acceptance Criteria

### Code Changes
- `core/__init__.py:20` imports `BaseETL` from `energizados.contracts`
- `etl_builder.py` has no module-top `ETLOrchestrator` import (imported inside `build()`)
- `evaluation_builder.py` has no module-top `DefaultEvaluator` import (imported inside `build()`)
- `inference_builder.py` has no module-top `DefaultInference` import (imported inside `build()`)
- Type hints use string annotations OR `from __future__ import annotations`

### Tests
- `pytest tests/` green (all existing tests pass)
- New `test_core_has_no_module_level_imports_to_concrete_packages` passes (AST or grep-based)
- Public-path test: `from energizados.core import BaseETL` resolves
- Behavior preservation tests for each builder

### Cycle Verification
- After `import energizados.core`, concrete packages NOT in `sys.modules`
- AST/grep check confirms zero module-level imports from `core` to concrete packages

### Budget
- Diff ≤ ~100 lines (well under 400-line budget)
