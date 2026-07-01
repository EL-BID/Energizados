# Contracts Specification

> Capability: `contracts` — single source of truth for all framework base classes.
> Stable public API. Future changes require deprecation paths for backward compatibility.

## Purpose

A single home for all framework base classes with proper abstract methods, normalized save/load API, and 100% backward compatibility via shim re-exports. All 8 base classes live in `src/energizados/contracts.py` while legacy import paths remain supported.

## Requirements

### Requirement: Single Contracts Home

All 8 base classes MUST live in one module: `src/energizados/contracts.py`. The classes are:
- `BaseModel`, `BaseInference`, `BasePipeline`, `BaseEvaluator`
- `BaseETL`, `BaseFeatureEngineering`, `BaseFeatureSelector`, `BaseExplorer`

#### Scenario: contracts module exports all 8 bases

- GIVEN the framework is installed
- WHEN `import energizados.contracts` succeeds
- THEN the module defines `BaseModel`, `BaseInference`, `BasePipeline`, `BaseEvaluator`, `BaseETL`, `BaseFeatureEngineering`, `BaseFeatureSelector`, `BaseExplorer`

#### Scenario: legacy base modules are shims

- GIVEN imports from legacy paths: `energizados.core.base.BaseModel`, `energizados.etl.base.BaseETL`, `energizados.feature_engineering.base.BaseFeatureEngineering`, `energizados.feature_selection.base.BaseFeatureSelector`, `energizados.eda.base.BaseExplorer`, `energizados.inference.base.BaseInference`
- WHEN each module is imported
- THEN it re-exports the class from `energizados.contracts` (same object, not a copy)

### Requirement: Complete Base Class Coverage

`BasePipeline` and `BaseEvaluator` MUST exist alongside the 6 legacy bases.

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

### Requirement: Abstract Method Completeness

All base classes MUST have complete abstract methods — no stubs.

#### Scenario: BaseInference has proper abstract methods

- GIVEN `BaseInference` from `energizados.contracts`
- WHEN a concrete subclass omits `load_model` or `save_predictions`
- THEN `TypeError` is raised at class definition time (cannot instantiate without implementation)

#### Scenario: BaseModel requires fit and predict

- GIVEN `BaseModel` from `energizados.contracts`
- WHEN a concrete subclass omits `fit` or `predict_proba`
- THEN `TypeError` is raised at class definition time

#### Scenario: BaseETL requires extract/transform/load

- GIVEN `BaseETL` from `energizados.contracts`
- WHEN a concrete subclass omits `extract`, `transform`, or `load`
- THEN `TypeError` is raised at class definition time

### Requirement: Save/Load API Normalization

`BaseModel` and `BaseFeatureSelector` MUST have `save()` / `load()` methods using secure pickle.

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

Concrete classes MUST NOT change `__module__` — only base classes may move.

#### Scenario: legacy pickle loads after base move

- GIVEN a `model.pkl` file created before base class consolidation (contains `LGBMModelAdapter` instance)
- WHEN `secure_load(model.pkl)` is called
- THEN the model loads without error and `model.__module__` is unchanged (still `energizados.modeling.adapters`)

#### Scenario: legacy feature_engineering.pkl loads

- GIVEN a `feature_engineering.pkl` file created before consolidation (contains `DefaultFeatureEngineering` instance)
- WHEN `secure_load(feature_engineering.pkl)` is called
- THEN the pipeline loads without error and `fe.__module__` is unchanged

### Requirement: Backward Compatibility via Shims (Hard Constraint)

All public import paths MUST resolve via shims.

#### Scenario: isinstance from legacy path works

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

### Requirement: Contract Violation Prevention

Implementations MUST respect base class contracts.

#### Scenario: noop_load hook allows BaseETL compliance

- GIVEN `BaseETL` defines `noop_load()` as an optional override hook
- WHEN a subclass like `CleanFilesETL` overrides `noop_load()` to return `pd.DataFrame()`
- THEN calling `extract()` / `transform()` / `load()` via `BaseETL.run()` does NOT raise `NotImplementedError`

#### Scenario: FeatureSelectionPipeline is a BaseFeatureSelector

- GIVEN `FeatureSelectionPipeline` from `energizados.feature_selection.pipeline`
- WHEN inspected
- THEN `issubclass(FeatureSelectionPipeline, BaseFeatureSelector)` is `True`

### Requirement: Public API Documentation

The contracts home MUST be documented in `AGENTS.md`.

#### Scenario: AGENTS.md documents contracts module

- GIVEN `AGENTS.md`
- WHEN a reader consults the Base Classes section
- THEN it lists `energizados.contracts` as the single home for all 8 base classes, with backward-compatible import paths documented
