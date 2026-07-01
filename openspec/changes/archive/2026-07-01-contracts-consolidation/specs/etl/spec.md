# ETL Contract Specification

> Capability: `etl` — modified (CleanFilesETL contract compliance via noop_load hook).  
> `contracts-consolidation` proposal, Finding 2, approach 2A (2-PR split).

## Purpose

`CleanFilesETL` respects the `BaseETL` contract without `NotImplementedError` violations, via a `noop_load` hook on the base class.

## Requirements

### Requirement: noop_load Hook on BaseETL

`BaseETL` MUST provide an optional `noop_load()` hook for non-dataset-producing ETLs.

#### Scenario: BaseETL defines noop_load hook

- GIVEN `BaseETL` from `energizados.contracts`
- WHEN inspected
- THEN it defines `def noop_load(self) -> pd.DataFrame` that returns an empty DataFrame (default implementation)

#### Scenario: BaseETL.run respects noop_load when set

- GIVEN a `BaseETL` subclass that overrides `noop_load()` to return `pd.DataFrame()`
- AND the subclass sets a flag or attribute (e.g., `_is_noop = True`)
- WHEN `BaseETL.run(output_path)` is called
- THEN the method calls `noop_load()` instead of `extract() → transform() → load()` and returns the empty DataFrame

#### Scenario: normal ETLs unaffected by noop_load presence

- GIVEN a normal `BaseETL` subclass like `SourceETL` that does NOT override `noop_load()`
- WHEN `run(output_path)` is called
- THEN the normal ETL flow executes (`extract() → transform() → load()`)

### Requirement: CleanFilesETL Uses noop_load Hook

`CleanFilesETL` MUST override `noop_load()` and set the noop flag.

#### Scenario: CleanFilesETL overrides noop_load

- GIVEN `CleanFilesETL` from `energizados.etl.pipeline`
- WHEN inspected
- THEN it overrides `noop_load()` to return `pd.DataFrame()` and sets `_is_noop = True` (or equivalent flag)

#### Scenario: CleanFilesETL.run calls base implementation

- GIVEN a `CleanFilesETL` instance configured with file paths
- WHEN `run(output_path)` is called
- THEN files are deleted and an empty DataFrame is returned (uses base `BaseETL.run()` logic)

#### Scenario: CleanFilesETL no longer has NotImplementedError stubs

- GIVEN `CleanFilesETL` after this change
- WHEN the methods `extract()`, `transform()`, `load()` are inspected
- THEN they do NOT raise `NotImplementedError` (either removed entirely or inherited from base without override)

### Requirement: Backward Compatibility

Existing `CleanFilesETL` usage MUST remain unchanged.

#### Scenario: CleanFilesETL YAML configs work

- GIVEN a YAML config with a `CleanFilesETL` block
- WHEN the ETL is executed via `ETLOrchestrator`
- THEN files are deleted and the orchestrator tracks completion normally

#### Scenario: CleanFilesETL still returns empty DataFrame

- GIVEN `CleanFilesETL` executed via orchestrator
- WHEN the result is captured
- THEN an empty `pd.DataFrame()` is returned (orchestrator compatibility)

### Requirement: Other ETLs Unaffected

Normal ETLs MUST NOT be impacted by the `noop_load` addition.

#### Scenario: SourceETL behavior unchanged

- GIVEN `SourceETL` from `energizados.etl.pipeline`
- WHEN `run(output_path)` is called
- THEN the ETL reads input files, transforms data, saves to output, and returns the DataFrame (normal flow)

#### Scenario: ClipOutliersETL behavior unchanged

- GIVEN `ClipOutliersETL` from `energizados.etl.pipeline`
- WHEN `run(output_path)` is called
- THEN the ETL clips outliers and returns the processed DataFrame (normal flow)

#### Scenario: GeoFeaturesETL behavior unchanged

- GIVEN `GeoFeaturesETL` from `energizados.etl.pipeline`
- WHEN `run(output_path)` is called
- THEN the ETL adds geographic features and returns the enriched DataFrame (normal flow)

### Requirement: Public Import Path Stability

Public import paths MUST resolve via shims.

#### Scenario: old import path works

- GIVEN `from energizados.etl.base import BaseETL`
- WHEN the import is executed
- THEN it succeeds and returns the class from `energizados.contracts` (shim re-export)

#### Scenario: isinstance checks from old path work

- GIVEN an object imported from `energizados.etl.base.BaseETL`
- WHEN `isinstance(obj, energizados.etl.base.BaseETL)` is checked
- THEN the result is `True`

#### Scenario: concrete ETL imports work

- GIVEN imports `from energizados.etl.pipeline import SourceETL, ClipOutliersETL, GeoFeaturesETL, CleanFilesETL`
- WHEN the imports are executed
- THEN all classes are available and unchanged (concrete classes don't move)
