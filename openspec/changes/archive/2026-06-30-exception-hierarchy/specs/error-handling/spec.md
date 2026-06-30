# Error Handling Specification

> Capability: `error-handling` — greenfield (no prior spec).
> `exception-hierarchy` proposal, Finding 3, approach 3A.

## Purpose

A coherent, public, backward-compatible exception hierarchy plus a boundary
error-preservation contract in `Pipeline.run`: callers catch framework
exceptions by concrete type, not an erased `PipelineError`.

## Requirements

### Requirement: Exception Hierarchy Completeness

One public base `EnergizadosError(Exception)` plus a complete per-layer type
set. Existing types keep a single `EnergizadosError` base (unchanged). Each
new/converted type additionally inherits the stdlib type it replaces.

| Type | Bases | Status |
|------|-------|--------|
| `ModelNotFittedError` | `(EnergizadosError, ValueError)` | MUTATED (Q1) |
| `TransformerError` | `(EnergizadosError, ValueError)` | NEW |
| `FeatureSelectionError` | `(EnergizadosError, ValueError)` | NEW |
| `InferenceError` | `(EnergizadosError, RuntimeError)` | NEW |
| `EvaluatorError` | `(EnergizadosError,)` | NEW (no site) |

#### Scenario: catch each new type as a framework error

- GIVEN `TransformerError`, `FeatureSelectionError`, `InferenceError`, `EvaluatorError`, or `ModelNotFittedError`
- WHEN raised and caught with `except EnergizadosError`
- THEN the handler runs

#### Scenario: backward-compatible stdlib catch

- GIVEN raised `TransformerError`/`FeatureSelectionError`/`ModelNotFittedError`, or `InferenceError`
- WHEN caught with `except ValueError` (resp. `except RuntimeError`)
- THEN the handler runs

#### Scenario: MRO computable for the mutated type

- WHEN `core/exceptions.py` is imported
- THEN no `TypeError` and `ModelNotFittedError.__mro__` contains `EnergizadosError` and `ValueError`

#### Scenario: existing types unchanged

- GIVEN `PipelineError`, `ConfigurationError`, `ETLDependencyError`
- WHEN inspected
- THEN each subclasses `EnergizadosError` and NOT `ValueError`/`RuntimeError`

### Requirement: Pipeline.run Preserves Framework Exceptions

`Pipeline.run` MUST re-raise any `EnergizadosError` subclass from a step
unchanged (no re-wrap; type/attributes preserved). Non-`EnergizadosError`
exceptions MUST be wrapped into `PipelineError` via `from e`. `on_step_error`
MUST still fire in both cases.

#### Scenario: framework exception reaches caller unchanged

- GIVEN a `Pipeline` whose step raises `ETLDependencyError`
- WHEN `pipeline.run()` propagates the error
- THEN the caller receives an `ETLDependencyError`; `isinstance(err, PipelineError)` is False

#### Scenario: unexpected exception wrapped and chained

- GIVEN a `Pipeline` whose step raises `KeyError`
- WHEN `pipeline.run()` is called
- THEN a `PipelineError` is raised and its `__cause__` is the original `KeyError`

#### Scenario: step-error callback fires for both paths

- GIVEN a `Pipeline` with an `on_step_error` callback
- WHEN a step raises an `EnergizadosError` or unexpected `Exception`
- THEN the callback fires once with the step name and original exception

### Requirement: Fitted-state Guard Consistency

Fitted-state guards MUST raise a single type `ModelNotFittedError`, matching
`BaseModel.check_fitted` (unchanged). Sites: `BaseFeatureEngineering.{check_fitted,
save, get_feature_names_out}` and `BaseFeatureSelector.{get_selected_features,
get_audit_stats}`.

#### Scenario: unfitted feature engineering raises ModelNotFittedError

- GIVEN a `BaseFeatureEngineering` subclass not yet fitted
- WHEN `transform`, `get_feature_names_out`, or `save` is called
- THEN `ModelNotFittedError` is raised

#### Scenario: unfitted feature selector raises ModelNotFittedError

- GIVEN a `BaseFeatureSelector` subclass with `selected_features_` unset
- WHEN `get_selected_features` or `get_audit_stats` is called
- THEN `ModelNotFittedError` is raised

#### Scenario: converted guard stays ValueError-compatible

- GIVEN the `ModelNotFittedError` raised by a fitted guard
- WHEN caught with `except ValueError`
- THEN the handler runs

### Requirement: Inference Contract Error Conversion

The `RuntimeError` at `inference/hierarchical.py:164` MUST convert to `InferenceError`.

#### Scenario: hierarchical inference raises InferenceError

- GIVEN `HierarchicalInference` in the "models not loaded" condition
- WHEN that code path executes
- THEN `InferenceError` is raised and is catchable by `except RuntimeError`

### Requirement: Public API and Documentation

The hierarchy MUST be documented as stable public API in a dedicated `AGENTS.md`
section: every public exception + its bases, with a stability commitment (future
changes require deprecation paths).

#### Scenario: docs enumerate the hierarchy

- GIVEN `AGENTS.md`
- WHEN a reader consults the exception-hierarchy section
- THEN every public exception (`EnergizadosError` + all table subclasses) is listed with its bases

### Requirement: Non-goals

This change MUST NOT convert the ~94 remaining bare
`ValueError`/`RuntimeError`/`TypeError` sites outside the specified guards.
Findings 1, 2, 4 and the `_anterior` leak are OUT OF SCOPE.

#### Scenario: unrelated bare raises are untouched

- GIVEN bare `raise ValueError(...)` outside the fitted-guard sites
- WHEN this change is applied
- THEN those raise sites are unchanged
