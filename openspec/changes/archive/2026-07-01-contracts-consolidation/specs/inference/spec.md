# Inference Contract Specification

> Capability: `inference` — modified (proper abstract methods + ModelContainer Protocol).  
> `contracts-consolidation` proposal, Finding 2, approach 2A (2-PR split).

## Purpose

`BaseInference.load_model` and `save_predictions` become true abstract methods (cannot be left unimplemented), and `load_model` return type accommodates both single models and `HierarchicalModelContainer` via a Protocol.

## Requirements

### Requirement: BaseInference.load_model is Abstract

`BaseInference.load_model` MUST be a `@abstractmethod`, not a stub.

#### Scenario: subclass must implement load_model

- GIVEN a new concrete subclass of `BaseInference`
- WHEN the subclass omits `load_model` implementation
- THEN `TypeError` is raised at class definition time with message about missing abstract method

#### Scenario: existing inference templates work

- GIVEN `templates/src/inference/custom_inference.py.tpl`
- WHEN the template is read
- THEN it implements `load_model(self, model_path: str) -> BaseModel` (template already correct)

### Requirement: BaseInference.save_predictions is Abstract

`BaseInference.save_predictions` MUST be a `@abstractmethod`, not a stub.

#### Scenario: subclass must implement save_predictions

- GIVEN a new concrete subclass of `BaseInference`
- WHEN the subclass omits `save_predictions` implementation
- THEN `TypeError` is raised at class definition time

### Requirement: ModelContainer Protocol for load_model Return Type

`BaseInference.load_model` return type MUST be a Protocol that accepts both single models and `HierarchicalModelContainer`.

#### Scenario: ModelContainer Protocol defined

- GIVEN `energizados.contracts` module
- WHEN inspected
- THEN it defines `ModelContainer` Protocol with methods:
  - `predict_proba(X: pd.DataFrame) -> np.ndarray`
  - `predict(X: pd.DataFrame) -> np.ndarray`

#### Scenario: BaseModel satisfies ModelContainer

- GIVEN a concrete `BaseModel` subclass (e.g., `LGBMModelAdapter`)
- WHEN checked against `ModelContainer` Protocol
- THEN it satisfies the Protocol (has `predict_proba` and `predict` methods)

#### Scenario: HierarchicalModelContainer satisfies ModelContainer

- GIVEN `HierarchicalModelContainer` from `energizados.inference.hierarchical`
- WHEN checked against `ModelContainer` Protocol
- THEN it satisfies the Protocol

#### Scenario: HierarchicalInference.load_model type-compatible

- GIVEN `HierarchicalInference.load_model` signature
- WHEN type-checked
- THEN the declared return type is compatible with `ModelContainer` Protocol (e.g., `-> ModelContainer` or `-> Any` with runtime Protocol check)

#### Scenario: single-model inference still works

- GIVEN `DefaultInference` from `energizados.inference.default`
- WHEN `load_model(model_path)` is called
- THEN it returns a `BaseModel` instance which satisfies `ModelContainer`

### Requirement: Custom Inference Templates Remain Valid

Existing custom inference templates MUST continue to work.

#### Scenario: template implements all abstract methods

- GIVEN `templates/src/inference/custom_inference.py.tpl`
- WHEN the template code is instantiated
- THEN no `TypeError` about missing abstract methods (template already implements `load_model` and `save_predictions`)

### Requirement: Backward Compatibility

Existing user code using `BaseInference` MUST continue to work.

#### Scenario: existing custom inference classes work

- GIVEN a user-defined `BaseInference` subclass that already implements `load_model` and `save_predictions`
- WHEN the code is run after this change
- THEN the class works without modification (already had the methods)

#### Scenario: incomplete custom classes fail clearly

- GIVEN a user-defined `BaseInference` subclass that does NOT implement `load_model` or `save_predictions`
- WHEN the code is run after this change
- THEN `TypeError` is raised at class definition time (clearer than runtime `NotImplementedError`)
