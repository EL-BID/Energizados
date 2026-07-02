# Model-Registry Capability Specification

## Purpose

Centralized model registry with `from_config` classmethod pattern for adapter instantiation, unified `Registry` abstraction, and backward-compatible `ModelRegistry` alias. Eliminates dual-edit requirement when adding model types and fixes meta-learner bug in ensemble stacking.

## Requirements

### Requirement: from_config Classmethod Pattern

Each model adapter MUST provide a `from_config` classmethod that converts YAML configuration into constructor parameters.

The system SHALL provide `from_config(cls, config: Dict, X_train: pd.DataFrame) -> Dict` on all model adapters:
- LGBMModelAdapter
- CATModelAdapter  
- XGBModelAdapter
- NNModelAdapter
- LSTMNNModelAdapter
- SimpleTrendAdapter
- SimpleConstantAdapter

The method MUST accept the model configuration dict and training DataFrame and return a dict of constructor kwargs.

#### Scenario: Adapter converts config for tree-based models

- GIVEN a model config for "lightgbm" with sampling, hyperparams, and hyperparam_search
- WHEN LGBMModelAdapter.from_config is called with the config and X_train
- THEN the returned dict MUST include cols_for_model (from X_train.columns), sampling_method, sampling_th, hyperparams, search_hip, n_iter, cv, n_splits, class_weight, and config keys
- AND the sampling dict MUST be flattened into individual keys
- AND the hyperparam_search dict MUST be flattened into search_hip/n_iter/cv/n_splits keys
- AND the "type" key MUST be removed (not a constructor arg)

#### Scenario: Adapter converts config for neural models

- GIVEN a model config for "neural_network" with sampling and features_names
- WHEN NNModelAdapter.from_config is called with the config and X_train  
- THEN the returned dict MUST include features_names (non-consumption cols), spents_names (consumption cols with "_anterior"), sampling_method, sampling_th, class_weight, search_hip, and config keys
- AND features_names/spents_names MUST be derived from X_train.columns

#### Scenario: Adapter converts config for simple models

- GIVEN a model config for "simple_trend" with last_base_value, last_eval_value, threshold
- WHEN SimpleTrendAdapter.from_config is called with the config and X_train
- THEN the returned dict MUST include last_base_value, last_eval_value, threshold, and config keys
- AND sampling, class_weight, hyperparams, hyperparam_search keys MUST be removed

### Requirement: Ladder Replacement via from_config

The `TrainingStep._train_single_model` method MUST use `from_config` instead of `_prepare_model_params` ladder.

The system SHALL replace the `_prepare_model_params` method with registry-based calls.

#### Scenario: Training step instantiates model via from_config

- GIVEN a model config dict with type "lightgbm" and standard keys
- WHEN TrainingStep._train_single_model processes the config
- THEN the system MUST call ModelRegistry.get("lightgbm") to obtain the adapter class
- AND call adapter_class.from_config(cfg, X_train) to get constructor params
- AND instantiate the model with those params

#### Scenario: Behavior preservation for existing configs

- GIVEN an existing YAML config for "catboost" with sampling and hyperparam_search
- WHEN the new from_config path processes that config
- THEN the resulting constructor kwargs MUST be identical to the old _prepare_model_params output
- AND all existing tests MUST pass without behavior change

#### Scenario: Ladder method remains deprecated for one release

- GIVEN the _prepare_model_params method still exists (deprecated, not deleted)
- WHEN existing code calls it directly
- THEN the method MUST work identically to previous releases
- AND a deprecation warning SHOULD be logged

### Requirement: Meta-Learner Fix for Stacking Ensemble

The ensemble stacking meta-learner MUST accept ANY registered model type, not just sklearn's LogisticRegression.

The system SHALL wrap base model adapters with `_SklearnCalibWrapper` to provide 2D `predict_proba` output.

#### Scenario: Meta-learner accepts sklearn models

- GIVEN an ensemble config with method="stacking" and meta_learner.type="logistic_regression"
- WHEN EnsembleModel._build_meta_learner is called
- THEN a sklearn LogisticRegression instance MUST be returned

#### Scenario: Meta-learner accepts Energizados adapters

- GIVEN an ensemble config with method="stacking" and meta_learner.type="lightgbm"
- WHEN EnsembleModel._build_meta_learner is called via ModelRegistry
- THEN the system MUST wrap the LGBMModelAdapter instance with _SklearnCalibWrapper
- AND the wrapper MUST expose classes_=[0,1] and _estimator_type="classifier"
- AND wrapper.predict_proba MUST return 2D array (n_samples, 2) with [negative_prob, positive_prob]

#### Scenario: Stacking prediction works with non-sklearn meta-learner

- GIVEN a fitted stacking ensemble with lightgbm meta-learner
- WHEN ensemble.predict_proba(X) is called
- THEN the system MUST call _meta_learner.predict_proba(base_predictions)[:, 1] without error
- AND the returned array MUST be 1D with shape (n_samples,)

### Requirement: Unified Registry Abstraction

A reusable `Registry` class MUST provide centralized registration and lookup for models, transformers, and selectors.

The system SHALL extract `Registry(name)` class with `register` and `get` methods to `core/registry.py`.

#### Scenario: Registry instance creation

- GIVEN the Registry class is defined in core/registry.py
- WHEN called as Registry("models")
- THEN the instance MUST maintain a private _registry dict
- AND provide register(name, item) and get(name) classmethods

#### Scenario: Multiple independent registry instances

- GIVEN model_registry, transformer_registry, selector_registry are created
- WHEN "lightgbm" is registered to model_registry
- AND "boruta" is registered to selector_registry  
- THEN model_registry.get("lightgbm") MUST return the adapter class
- AND selector_registry.get("boruta") MUST return the selector class
- AND model_registry.get("boruta") MUST raise KeyError

### Requirement: Backward-Compatible ModelRegistry Alias

The `ModelRegistry` class MUST remain importable and fully functional as a backward-compatible alias.

The system SHALL provide `ModelRegistry` as an alias to `model_registry` instance.

#### Scenario: Existing import paths continue to work

- GIVEN code imports `from energizados.modeling.registry import ModelRegistry`
- WHEN ModelRegistry.register("custom_model", CustomClass) is called
- THEN the model MUST be registered in the underlying model_registry instance
- AND ModelRegistry.get("custom_model") MUST return CustomClass
- AND ModelRegistry.list_models() MUST include "custom_model"

#### Scenario: ModelRegistry.create still works

- GIVEN ModelRegistry is an alias to model_registry
- WHEN ModelRegistry.create("lightgbm", cols_for_model=[...], hyperparams={...})
- THEN the system MUST instantiate LGBMModelAdapter with the provided kwargs

### Requirement: Pickle Safety and Extension Points

No concrete class moves MUST occur. Existing `.pkl` files MUST load unchanged. Public extension points MUST keep resolving.

The system SHALL preserve backward compatibility for all persisted models and custom extension points.

#### Scenario: Existing pickled models load unchanged

- GIVEN a `.pkl` file containing a trained LGBMModelAdapter from v0.2.x
- WHEN the file is loaded via secure_pickle.load
- THEN the model MUST deserialize without error
- AND all model attributes (is_fitted_, config, cols_for_model, threshold) MUST be preserved

#### Scenario: Custom model registration still works

- GIVEN a custom model class CustomAdapter(BaseModel) is defined
- WHEN ModelRegistry.register("custom", CustomAdapter) is called in project code
- AND a YAML config specifies type: "custom"
- THEN the training pipeline MUST instantiate CustomAdapter via ModelRegistry.get("custom")
- AND the custom model MUST train and predict like built-in models

#### Scenario: custom_class escape hatch still works

- GIVEN a YAML config specifies model.custom_class: "myproject.models.MyCustomModel"
- WHEN the training step processes this config
- THEN the system MUST dynamically import MyCustomModel via import_utils
- AND instantiate it with the config params
- AND the custom model MUST integrate without changes to framework code

## REMOVED Requirements

### Requirement: _prepare_model_params Ladder

(Reason: Replaced by adapter-specific `from_config` classmethods — eliminates dual-edit requirement and DRY violation)
(Migration: Behavior-preservation tests verify `from_config` produces identical output before ladder deletion. Ladder remains deprecated for one release.)

The `TrainingStep._prepare_model_params` method with model-type-specific if/elif/else branches is REMOVED.

## RENAMED Requirements

None.
