# Serialization Contract Specification

> Capability: `serialization` — modified (normalized save/load on BaseModel and BaseFeatureSelector).  
> `contracts-consolidation` proposal, Finding 2, approach 2A (2-PR split).

## Purpose

`BaseModel` and `BaseFeatureSelector` gain `save()`/`load()` methods using `secure_pickle`, matching the existing `BaseFeatureEngineering` API.

## Requirements

### Requirement: BaseModel Save/Load API

`BaseModel` MUST have `save()`/`load()` methods.

#### Scenario: BaseModel has save method

- GIVEN `BaseModel` from `energizados.contracts`
- WHEN inspected
- THEN it defines `save(self, path: str) -> None` that:
  - Checks `self.is_fitted_` and raises `ModelNotFittedError` if False
  - Uses `energizados.core.utils.secure_pickle.secure_dump` to persist the model
  - Creates parent directories if needed
  - Logs save completion

#### Scenario: BaseModel has load classmethod

- GIVEN `BaseModel` from `energizados.contracts`
- WHEN inspected
- THEN it defines `@classmethod def load(cls, path: str) -> "BaseModel"` that:
  - Uses `energizados.core.utils.secure_pickle.secure_load` to read the model
  - Logs load completion
  - Returns the loaded model instance

#### Scenario: concrete model save works

- GIVEN a fitted `LGBMModelAdapter` instance
- WHEN `save(path)` is called
- THEN the model is saved with SHA-256 signature sidecar created

#### Scenario: concrete model load works

- GIVEN a saved `model.pkl` file (created before or after this change)
- WHEN `LGBMModelAdapter.load(model.pkl)` is called
- THEN the model is loaded, signature is verified, and the instance is ready for `predict()`

### Requirement: BaseFeatureSelector Save/Load API

`BaseFeatureSelector` MUST have `save()`/`load()` methods.

#### Scenario: BaseFeatureSelector has save method

- GIVEN `BaseFeatureSelector` from `energizados.contracts`
- WHEN inspected
- THEN it defines `save(self, path: str) -> None` that:
  - Checks `self.selected_features_` and raises `ModelNotFittedError` if None
  - Uses `energizados.core.utils.secure_pickle.secure_dump` to persist the selector
  - Creates parent directories if needed
  - Logs save completion

#### Scenario: BaseFeatureSelector has load classmethod

- GIVEN `BaseFeatureSelector` from `energizados.contracts`
- WHEN inspected
- THEN it defines `@classmethod def load(cls, path: str) -> "BaseFeatureSelector"` that:
  - Uses `energizados.core.utils.secure_pickle.secure_load` to read the selector
  - Logs load completion
  - Returns the loaded selector instance

#### Scenario: concrete selector save works

- GIVEN a fitted `BorutaSelector` instance
- WHEN `save(path)` is called
- THEN the selector is saved with SHA-256 signature sidecar created

#### Scenario: concrete selector load works

- GIVEN a saved `selector.pkl` file
- WHEN `BorutaSelector.load(selector.pkl)` is called
- THEN the selector is loaded, signature is verified, and `selected_features_` is populated

### Requirement: API Consistency Across Bases

All three bases with save/load MUST use the same pattern.

#### Scenario: all three bases use secure_pickle

- GIVEN `BaseModel`, `BaseFeatureSelector`, and `BaseFeatureEngineering`
- WHEN their `save()` and `load()` methods are inspected
- THEN all use `energizados.core.utils.secure_pickle.secure_dump` / `secure_load`

#### Scenario: all three bases check fitted state before save

- GIVEN instances of each base class
- WHEN `save()` is called before `fit()`
- THEN all raise `ModelNotFittedError` with consistent behavior

#### Scenario: all three bases are classmethods for load

- GIVEN the `load()` method on each base class
- WHEN inspected
- THEN all are decorated with `@classmethod`

### Requirement: Pickle Format Unchanged

Adding save/load MUST NOT break existing pickle files.

#### Scenario: legacy model.pkl loads

- GIVEN a `model.pkl` file from a previous framework version (before this change)
- WHEN `BaseModel.load(model.pkl)` is called
- THEN the model loads without error (pickle format unchanged)

#### Scenario: legacy feature_engineering.pkl loads

- GIVEN a `feature_engineering.pkl` file from a previous framework version
- WHEN `BaseFeatureEngineering.load(feature_engineering.pkl)` is called
- THEN the pipeline loads without error (API unchanged)

### Requirement: Backward Compatibility

Existing code MUST continue to work.

#### Scenario: existing model save code works

- GIVEN code that uses framework's existing save mechanisms (e.g., via `DefaultEvaluator` or manual pickling)
- WHEN the code is run after this change
- THEN the behavior is unchanged (new methods are additive)

#### Scenario: existing selector usage works

- GIVEN code that uses `BorutaSelector` or other selectors without calling `save()/load()`
- WHEN the code is run after this change
- THEN the behavior is unchanged (new methods are optional)

### Requirement: Error Handling

Save/load methods MUST handle errors appropriately.

#### Scenario: save raises ModelNotFittedError when not fitted

- GIVEN a `BaseModel` subclass with `is_fitted_ = False`
- WHEN `save(path)` is called
- THEN `ModelNotFittedError` is raised with class name in message

#### Scenario: save raises ModelNotFittedError for selector with no features

- GIVEN a `BaseFeatureSelector` subclass with `selected_features_ = None`
- WHEN `save(path)` is called
- THEN `ModelNotFittedError` is raised

#### Scenario: load raises secure_pickle errors

- GIVEN a corrupted pickle file (missing signature or invalid data)
- WHEN `load(path)` is called
- THEN the appropriate `secure_pickle` exception is raised (e.g., for signature mismatch)

### Requirement: Logging

Save/load operations MUST be logged.

#### Scenario: save logs completion

- GIVEN a model or selector instance
- WHEN `save(path)` is called successfully
- THEN an INFO log message is emitted indicating the save path

#### Scenario: load logs completion

- GIVEN a saved model or selector file
- WHEN `load(path)` is called successfully
- THEN an INFO log message is emitted indicating the load path
