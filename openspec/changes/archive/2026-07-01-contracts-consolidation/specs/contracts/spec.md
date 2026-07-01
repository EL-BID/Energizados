# Contracts Consolidation Specification

> Capability: `contracts` — greenfield (consolidated base classes from 5 modules).  
> Modified capabilities: `inference`, `feature-selection`, `etl`, `serialization`.  
> `contracts-consolidation` proposal, Finding 2, approach 2A (2-PR split).

## Purpose

A single source of truth for all framework base classes plus the missing `BasePipeline` and `BaseEvaluator`, with proper abstract methods, fixed contract violations, and normalized save/load API — while maintaining 100% backward compatibility via shim re-exports and preserving pickle safety.

## Requirements

### Requirement: Single Contracts Home

All 8 base classes MUST live in one module: `src/energizados/contracts.py`. The classes are:
- `BaseModel`, `BaseInference`, `BasePipeline`, `BaseEvaluator`
- `BaseETL`, `BaseFeatureEngineering`, `BaseFeatureSelector`, `BaseExplorer`

#### Scenario: contracts module exports all 8 bases

- GIVEN the framework is installed
- WHEN `import energizados.contracts` succeeds
- THEN the module defines `BaseModel`, `BaseInference`, `BasePipeline`, `BaseEvaluator`, `BaseETL`, `BaseFeatureEngineering`, `BaseFeatureSelector`, `BaseExplorer`

#### Scenario: old base modules are shims

- GIVEN imports from old paths: `energizados.core.base.BaseModel`, `energizados.etl.base.BaseETL`, `energizados.feature_engineering.base.BaseFeatureEngineering`, `energizados.feature_selection.base.BaseFeatureSelector`, `energizados.eda.base.BaseExplorer`, `energizados.inference.base.BaseInference`
- WHEN each module is imported
- THEN it re-exports the class from `energizados.contracts` (same object, not a copy)

### Requirement: Missing Bases Added

`BasePipeline` and `BaseEvaluator` MUST exist with proper abstract methods.

#### Scenario: BasePipeline is an ABC with run(context)

- GIVEN `BasePipeline` from `energizados.contracts`
- WHEN inspected
- THEN it is an ABC with `@abstractmethod def run(context: Dict) -> Dict` and optional `validate(context) -> bool` / `get_required_keys() -> list` methods

#### Scenario: BaseEvaluator is an ABC with evaluate(...)

- GIVEN `BaseEvaluator` from `energizados.contracts`
- WHEN inspected
- THEN it is an ABC with `@abstractmethod def evaluate(X, y, model, **kwargs) -> Dict[str, float]` returning metrics (e.g., `{'auc': 0.85, 'f1': 0.82}`) and optional `generate_reports(metrics, output_dir) -> None`

#### Scenario: DefaultEvaluator inherits BaseEvaluator

- GIVEN `DefaultEvaluator` from `energizados.evaluation.evaluator`
- WHEN inspected
- THEN `issubclass(DefaultEvaluator, BaseEvaluator)` is `True` and `issubclass(DefaultEvaluator, PipelineStep)` is `False`

### Requirement: BaseInference Abstract Methods Complete

`BaseInference.load_model` and `save_predictions` MUST be proper `@abstractmethod` (not stubs).

#### Scenario: load_model is abstract

- GIVEN `BaseInference` from `energizados.contracts`
- WHEN a concrete subclass omits `load_model`
- THEN `TypeError` is raised at class definition time (cannot instantiate without implementation)

#### Scenario: save_predictions is abstract

- GIVEN `BaseInference` from `energizados.contracts`
- WHEN a concrete subclass omits `save_predictions`
- THEN `TypeError` is raised at class definition time (cannot instantiate without implementation)

### Requirement: FeatureSelectionPipeline Inheritance Fixed

`FeatureSelectionPipeline` MUST inherit `BaseFeatureSelector`.

#### Scenario: FeatureSelectionPipeline is a BaseFeatureSelector

- GIVEN `FeatureSelectionPipeline` from `energizados.feature_selection.pipeline`
- WHEN inspected
- THEN `issubclass(FeatureSelectionPipeline, BaseFeatureSelector)` is `True`

#### Scenario: FeatureSelectionPipeline implements required methods

- GIVEN a `FeatureSelectionPipeline` instance
- WHEN `fit(X, y)` and `transform(X)` are called
- THEN methods execute without `NotImplementedError`

### Requirement: CleanFilesETL Contract Compliance

`CleanFilesETL` MUST respect `BaseETL` contract without `NotImplementedError` violations.

#### Scenario: noop_load hook allows BaseETL compliance

- GIVEN `BaseETL` defines `noop_load()` as an optional override hook
- WHEN a subclass like `CleanFilesETL` overrides `noop_load()` to return `pd.DataFrame()`
- THEN calling `extract()` / `transform()` / `load()` via `BaseETL.run()` does NOT raise `NotImplementedError`

#### Scenario: CleanFilesETL still works via run()

- GIVEN a `CleanFilesETL` instance configured with file paths
- WHEN `run(output_path)` is called
- THEN files are deleted and an empty DataFrame is returned

### Requirement: HierarchicalInference.load_model Return Type

`BaseInference.load_model` return type MUST accommodate both single models and `HierarchicalModelContainer`.

#### Scenario: BaseInference.load_model return type is ModelContainer Protocol

- GIVEN `BaseInference.load_model` signature
- WHEN type-checked
- THEN the return type is a Protocol `ModelContainer` (duck-typed: has `predict` and `predict_proba` methods) not a concrete class

#### Scenario: HierarchicalInference.load_model satisfies Protocol

- GIVEN `HierarchicalInference.load_model` returns `HierarchicalModelContainer`
- WHEN the return value is checked against `ModelContainer` Protocol
- THEN it passes (has `predict_proba` method)

### Requirement: Normalized Save/Load API

`BaseModel` and `BaseFeatureSelector` MUST have `save()` / `load()` methods.

#### Scenario: BaseModel has save and load

- GIVEN `BaseModel` from `energizados.contracts`
- WHEN inspected
- THEN it defines `save(self, path: str) -> None` and `@classmethod def load(cls, path: str) -> "BaseModel"`

#### Scenario: BaseFeatureSelector has save and load

- GIVEN `BaseFeatureSelector` from `energizados.contracts`
- WHEN inspected
- THEN it defines `save(self, path: str) -> None` and `@classmethod def load(cls, path: str) -> "BaseFeatureSelector"`

#### Scenario: save methods use secure_pickle

- GIVEN a concrete `BaseModel` subclass instance
- WHEN `save(path)` is called
- THEN `energizados.core.utils.secure_pickle.secure_dump` is used (SHA-256 signature sidecar created)

#### Scenario: load methods use secure_pickle

- GIVEN a saved model file
- WHEN `BaseModel.load(path)` or `BaseFeatureSelector.load(path)` is called
- THEN `energizados.core.utils.secure_pickle.secure_load` is used (signature verified)

### Requirement: Pickle Safety (Hard Constraint)

Concrete classes MUST NOT change `__module__` — only base classes move.

#### Scenario: legacy pickle loads after base move

- GIVEN a `model.pkl` file created before this change (contains `LGBMModelAdapter` instance)
- WHEN the change is applied and `secure_load(model.pkl)` is called
- THEN the model loads without error and `model.__module__` is unchanged (still `energizados.modeling.adapters`)

#### Scenario: legacy feature_engineering.pkl loads

- GIVEN a `feature_engineering.pkl` file created before this change (contains `DefaultFeatureEngineering` instance)
- WHEN the change is applied and `secure_load(feature_engineering.pkl)` is called
- THEN the pipeline loads without error and `fe.__module__` is unchanged

### Requirement: Backward Compatibility via Shims (Hard Constraint)

All public import paths MUST resolve via shims.

#### Scenario: isinstance from old path works

- GIVEN an object imported from `energizados.etl.base.BaseETL` (the shim)
- WHEN `isinstance(obj, energizados.etl.base.BaseETL)` is checked
- THEN the check returns `True`

#### Scenario: templates still generate working code

- GIVEN a template that references `energizados.etl.pipeline.SourceETL`, `energizados.feature_selection.base.BaseFeatureSelector`, `energizados.inference.base.BaseInference`
- WHEN code is generated from templates
- WHEN the generated code is executed
- THEN imports resolve and classes are usable

#### Scenario: user configs with custom_class work

- GIVEN a YAML config with `custom_class: "energizados.etl.pipeline.SourceETL"` or `custom_class: "energizados.inference.base.BaseInference"`
- WHEN the config is processed and classes are instantiated
- THEN imports resolve and objects are created

### Requirement: Abstract Method Enforcement Tests

Per-base abstract method enforcement tests MUST exist.

#### Scenario: test_contracts enforces abstract methods

- GIVEN `tests/test_contracts.py`
- WHEN `pytest tests/test_contracts.py` is run
- THEN each base class has tests verifying that:
  - Abstract methods cannot be called without implementation
  - Concrete subclasses that omit abstract methods fail at instantiation
  - `issubclass` relationships are preserved

### Requirement: Public API Documentation

The contracts home MUST be documented in `AGENTS.md`.

#### Scenario: AGENTS.md documents contracts module

- GIVEN `AGENTS.md`
- WHEN a reader consults the Base Classes section
- THEN it lists `energizados.contracts` as the single home for all 8 base classes, with backward-compatible import paths documented

### Requirement: Non-goals

This change MUST NOT:
- Move concrete classes (`*Adapter`, `Default*`, `SourceETL`, `ClipOutliersETL`, `GeoFeaturesETL`, `CleanFilesETL`)
- Break existing `model.pkl` / `feature_engineering.pkl` files
- Break public import paths used in templates or user configs
- Fix Finding 1 (core layering / circular dependency)
- Fix Finding 4 (unified registry)

#### Scenario: concrete class modules unchanged

- GIVEN concrete classes in their original modules (`modeling/adapters.py`, `feature_engineering/default.py`, `etl/pipeline.py`)
- WHEN this change is applied
- THEN those classes remain in place with unchanged `__module__` attributes

#### Scenario: other findings untouched

- GIVEN the framework after this change
- WHEN `core/__init__.py` imports from `etl.base`
- THEN the circular dependency (Finding 1) still exists
- WHEN registries are inspected
- THEN parallel registries (Finding 4) still exist
