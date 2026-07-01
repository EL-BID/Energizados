# Feature Selection Contract Specification

> Capability: `feature-selection` — modified (FeatureSelectionPipeline inheritance fixed + save/load API).  
> `contracts-consolidation` proposal, Finding 2, approach 2A (2-PR split).

## Purpose

`FeatureSelectionPipeline` correctly inherits `BaseFeatureSelector`, and `BaseFeatureSelector` gains normalized `save()`/`load()` methods.

## Requirements

### Requirement: FeatureSelectionPipeline Inheritance Fix

`FeatureSelectionPipeline` MUST inherit `BaseFeatureSelector`.

#### Scenario: FeatureSelectionPipeline is a BaseFeatureSelector

- GIVEN `FeatureSelectionPipeline` from `energizados.feature_selection.pipeline`
- WHEN `issubclass(FeatureSelectionPipeline, BaseFeatureSelector)` is checked
- THEN the result is `True`

#### Scenario: FeatureSelectionPipeline implements required abstract methods

- GIVEN a `FeatureSelectionPipeline` instance configured with steps
- WHEN `fit(X, y)` is called
- THEN the method executes without `NotImplementedError` and `selected_features_` is populated

#### Scenario: FeatureSelectionPipeline.transform works

- GIVEN a fitted `FeatureSelectionPipeline` instance
- WHEN `transform(X)` is called
- THEN a DataFrame with selected features is returned (no `NotImplementedError`)

#### Scenario: FeatureSelectionPipeline.get_selected_features works

- GIVEN a fitted `FeatureSelectionPipeline` instance
- WHEN `get_selected_features()` is called
- THEN the list of selected feature names is returned (inherited from `BaseFeatureSelector`)

#### Scenario: FeatureSelectionPipeline.get_audit_stats works

- GIVEN a fitted `FeatureSelectionPipeline` instance
- WHEN `get_audit_stats()` is called
- THEN a dictionary with step results is returned (override that extends base behavior)

### Requirement: BaseFeatureSelector Save/Load API

`BaseFeatureSelector` MUST have `save()`/`load()` methods.

#### Scenario: BaseFeatureSelector has save method

- GIVEN `BaseFeatureSelector` from `energizados.contracts`
- WHEN inspected
- THEN it defines `save(self, path: str) -> None` that uses `secure_pickle.secure_dump`

#### Scenario: BaseFeatureSelector has load classmethod

- GIVEN `BaseFeatureSelector` from `energizados.contracts`
- WHEN inspected
- THEN it defines `@classmethod def load(cls, path: str) -> "BaseFeatureSelector"` that uses `secure_pickle.secure_load`

#### Scenario: save raises ModelNotFittedError when not fitted

- GIVEN a `BaseFeatureSelector` subclass instance with `selected_features_ = None`
- WHEN `save(path)` is called
- THEN `ModelNotFittedError` is raised (consistent with `BaseFeatureEngineering.save`)

#### Scenario: load restores fitted state

- GIVEN a fitted `BorutaSelector` instance saved to `selector.pkl`
- WHEN `BorutaSelector.load(selector.pkl)` is called
- THEN the loaded instance has `selected_features_` populated and is ready for `transform()`

### Requirement: Backward Compatibility

Existing `BaseFeatureSelector` subclasses MUST continue to work.

#### Scenario: existing selector subclasses unaffected

- GIVEN existing selector classes (`BorutaSelector`, `CorrelationSelector`, `ConstantSelector`)
- WHEN the code is run after this change
- THEN the classes work without modification (no new abstract methods added)

#### Scenario: FeatureSelectionPipeline usage unchanged

- GIVEN code using `FeatureSelectionPipeline` before this change
- WHEN the code is run after this change
- THEN the behavior is identical (only the inheritance is fixed)

### Requirement: Public Import Path Stability

Public import paths MUST resolve via shims.

#### Scenario: old import path works

- GIVEN `from energizados.feature_selection.base import BaseFeatureSelector`
- WHEN the import is executed
- THEN it succeeds and returns the class from `energizados.contracts` (shim re-export)

#### Scenario: isinstance checks from old path work

- GIVEN an object imported from `energizados.feature_selection.base.BaseFeatureSelector`
- WHEN `isinstance(obj, energizados.feature_selection.base.BaseFeatureSelector)` is checked
- THEN the result is `True`
