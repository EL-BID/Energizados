# Training Configuration

Complete reference for `train.yaml` configuration.

## Overview

The training configuration file controls the entire training pipeline with five main sections:

- **`split`**: Data splitting into train/val/test sets
- **`feature_engineering`**: Preprocessing and feature selection
- **`models`**: Model configuration (single or multiple)
- **`ensemble`**: Ensemble configuration (optional, required when multiple models)
- **`evaluation`**: Metrics, reports, and threshold settings

## File Structure

```yaml
training:
  enabled: true                     # Whether to execute training
  input_path: "path/to/data.parquet"  # Input dataset
  target_column: "target"           # Target variable name
  periods_suffix: "_anterior"        # Suffix for time series columns

  split:
    # Split configuration

  feature_engineering:
    # Feature engineering configuration

  models:
    # Model configuration (list)

  ensemble:
    # Ensemble configuration (optional)

  evaluation:
    # Evaluation configuration
```

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Whether to execute training |
| `input_path` | string | Path to input dataset |
| `target_column` | string | Name of target column |
| `split` | dict | Data split configuration |
| `feature_engineering` | dict | Feature engineering configuration |
| `models` | list | Model configuration (at least one) |
| `evaluation` | dict | Evaluation configuration |

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `periods_suffix` | string | `"_anterior"` | Suffix for time series columns |
| `output_base_dir` | string | `"output"` | Base directory for outputs |

---

## Split Configuration

### Split Methods

#### Stratified Split

Maintains class distribution in each split.

```yaml
split:
  method: "stratified"
  test_size: 0.2
  val_size: 0.1
  random_state: 42
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | string | `"stratified"` | Must be `"stratified"` |
| `test_size` | float | `0.2` | Proportion of data for test set |
| `val_size` | float | `0.1` | Proportion of data for validation set |
| `random_state` | int | `42` | Random seed for reproducibility |

#### Random Split

Simple random split without stratification.

```yaml
split:
  method: "random"
  test_size: 0.2
  val_size: 0.1
  random_state: 42
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | string | `"random"` | Must be `"random"` |
| `test_size` | float | `0.2` | Proportion of data for test set |
| `val_size` | float | `0.1` | Proportion of data for validation set |
| `random_state` | int | `42` | Random seed for reproducibility |

#### Time Series Split

Split data by date ranges.

```yaml
split:
  method: "time_series"
  date_column: "fecha_inspeccion"
  train_period: ["2010-01-01", "2017-08-01"]
  val_period: ["2017-09-01", "2017-12-31"]
  test_period: ["2018-01-01"]
  save_splits: true
  splits_dir: "data/splits/"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | string | `"time_series"` | Must be `"time_series"` |
| `date_column` | string | - | Name of date column (required) |
| `train_period` | list | - | Start and end dates for training `[start, end]` |
| `val_period` | list | - | Start and end dates for validation `[start, end]` |
| `test_period` | list | - | Start date for test set (or `[start, end]`) |
| `save_splits` | boolean | `false` | Whether to save split indices to disk |
| `splits_dir` | string | `"data/splits/"` | Directory to save split files |

#### Group-based Split

Splits data ensuring that all rows sharing the same group value (e.g., all readings for a given customer) land in exactly one split. Prevents data leakage when multiple rows per entity exist in the dataset.

```yaml
split:
  method: "group_based"
  group_column: "customer_id"
  test_size: 0.2
  val_size: 0.1
  random_state: 42
  save_splits: true
  splits_dir: "data/splits/"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | string | - | Must be `"group_based"` |
| `group_column` | string | - | Column to group by (required for this method) |
| `test_size` | float | `0.2` | Approximate proportion of **groups** for test set |
| `val_size` | float | `0.1` | Approximate proportion of **groups** for validation set |
| `random_state` | int | `42` | Random seed for reproducibility |
| `save_splits` | boolean | `true` | Whether to save split parquet files to disk |
| `splits_dir` | string | `"data/splits/"` | Directory to save split files |

**Important:** Proportions apply at the **group level**, not the row level. Because groups may differ in size, row-level proportions may deviate from the requested `test_size`/`val_size`. This is inherent to group-aware splitting.

**Metadata:** When `method: "group_based"`, `split_metadata.json` includes additional keys: `group_column`, `n_groups_total`, `n_groups_train`, `n_groups_val`, `n_groups_test`.

**Class imbalance warning:** A `WARNING` is logged if any split's positive-class rate falls below 10% or exceeds 90%, since group-based splits cannot guarantee stratification.

---

## Feature Engineering Configuration

```yaml
feature_engineering:
  enabled: true
  output_pkl: "data/processed/feature_engineering.pkl"

  preprocessing:
    enabled: true
    drop_columns: ["index", "fecha_inspeccion"]
    # output_parquet: "data/processed/preprocessing.parquet"  # optional

    columns:
      # Column-specific preprocessing

    global_transformers:
      # Global transformers

  feature_selection:
    enabled: false
    # output_parquet: "data/processed/feature_selection.parquet"  # optional
    steps:
      # Feature selection steps
```

### Preprocessing Transformations

Available per-column transformations:

| Transformation | Description | Parameters |
|----------------|-------------|------------|
| `cardinality_reducer` | Groups infrequent categories into "otros" | `threshold` (float, class default=0.1; YAML template default=0.001) |
| `to_dummy` | One-hot encoding | None |
| `target_encoding` | Replaces category with target probability | `w` (int, default=20) |
| `ordinal_encoding` | Ordinal encoding (0, 1, 2, ...) | sklearn OrdinalEncoder params |
| `minmax_scaler_row` | Row-wise MinMax scaling | `feature_range` (tuple, default=[0,1]) |
| `cast_dtype` | Converts column to a pandas dtype | `dtype` (str, default=`"float32"`) |

### Global Transformers

Global transformers act on the entire dataset and generate new features. They are executed AFTER column-based preprocessing.

#### tsfel_vars

Time series feature extraction using the tsfel library.

```yaml
- tsfel_vars:
    num_periodos: 12
    features_names_path: null  # or path to JSON with custom config
    periods_suffix: "_anterior"
    n_jobs: -1        # -1 = all cores, 1 = sequential
    chunk_size: 500   # rows per chunk per worker
    cache_dir: null   # e.g.: ".cache/tsfel" to cache on disk
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_periodos` | int | `12` | Number of time series columns |
| `features_names_path` | string | `null` | Path to JSON with custom feature configuration |
| `periods_suffix` | string | `"_anterior"` | Suffix of time series columns |
| `n_jobs` | int | `1` | Number of parallel jobs (1 = sequential) |
| `chunk_size` | int | `500` | Rows per chunk per worker |
| `cache_dir` | string | `null` | Directory to cache tsfel results |

#### extra_vars

Statistical features for different time windows.

```yaml
- extra_vars:
    num_periodos: 3
    periods_suffix: "_anterior"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_periodos` | int | `3` | Number of time series columns |
| `periods_suffix` | string | `"_anterior"` | Suffix of time series columns |

#### Custom Global Transformer

```yaml
- custom_class: "preprocessing.CustomGlobalTransformer"
  params:
    custom_param: value
```

### Complete Preprocessing Example

```yaml
feature_engineering:
  enabled: true
  output_pkl: "data/processed/feature_engineering.pkl"

  preprocessing:
    enabled: true
    drop_columns: ["index", "fecha_inspeccion"]

    columns:
      # Multiple transformers on the same column
      actividad:
        - cardinality_reducer:
            threshold: 0.001
        - to_dummy: {}

      # Target encoding with smoothing
      tipo_tarifa:
        - target_encoding:
            w: 20

      # Ordinal encoding
      zona:
        - ordinal_encoding: {}

      nivel_tension:
        - ordinal_encoding: {}

      # Cast to specific dtype
      consumo_total:
        - cast_dtype:
            dtype: "float32"

    # Global transformers execute AFTER column-based preprocessing
    global_transformers:
      # Time series feature extraction with tsfel
      - tsfel_vars:
          num_periodos: 12
          features_names_path: null
          periods_suffix: "_anterior"
          n_jobs: -1
          chunk_size: 500
          cache_dir: null

      # Statistical features for different time windows
      - extra_vars:
          num_periodos: 3
          periods_suffix: "_anterior"
      - extra_vars:
          num_periodos: 6
          periods_suffix: "_anterior"
      - extra_vars:
          num_periodos: 12
          periods_suffix: "_anterior"
```

### Feature Selection

```yaml
feature_selection:
  enabled: false
  # output_parquet: "data/processed/feature_selection.parquet"  # optional
  steps:
    - name: selector
      method: "boruta"  # boruta, correlation, constant
      params:
        n_estimators: 100
        max_iter: 100
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | `false` | Whether to perform feature selection |
| `steps` | list | `[]` | List of feature selection steps |

**Feature Selection Methods:**

| Method | Description | Parameters |
|--------|-------------|------------|
| `boruta` | Boruta algorithm for feature selection | `n_estimators`, `max_iter` |
| `correlation` | Removes highly correlated features | `threshold` |
| `constant` | Removes low-variance features | `threshold` |

---

## Model Configuration

### Available Model Types

Energizados supports six model types:

| Type | Aliases | Description | Requires Preprocessing |
|------|---------|-------------|----------------------|
| `lightgbm` | `lgbm` | Gradient Boosting with LightGBM | Yes |
| `catboost` | `cat` | CatBoost classifier | Yes |
| `neural_network` | `nn` | Feedforward Neural Network (Dense) | Yes |
| `lstm` | - | LSTM for sequential consumption data | Yes |
| `simple_trend` | - | Rule-based trend detector | No (uses raw data) |
| `simple_constant` | - | Rule-based constant consumption detector | No (uses raw data) |

### Model Categories

#### Machine Learning Models (Require Preprocessing)

These models require feature engineering preprocessing to work correctly:

- **lightgbm**: Fast gradient boosting, good for tabular data
- **catboost**: Handles categorical features natively
- **neural_network**: Feedforward Dense network with scaled features
- **lstm**: Long Short-Term Memory network for sequential consumption patterns

#### Rule-Based Models (Use Raw Data)

These models work directly on raw consumption columns without preprocessing:

- **simple_trend**: Detects fraud based on consumption trend drops
- **simple_constant**: Detects fraud based on suspiciously constant consumption

### Single Model Configuration

```yaml
models:
  - type: "lightgbm"  # lightgbm, catboost, neural_network, lstm
    sampling:
      method: "undersample"  # over, undersample, smotetomek, none
      threshold: 0.5
    hyperparams:
      num_leaves: 31
      learning_rate: 0.05
      n_estimators: 1000
    hyperparam_search:
      enabled: true
      n_iter: 60
      cv: 3
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | - | Model type: `lightgbm`, `catboost`, `neural_network`, `lstm`, `simple_trend`, `simple_constant` |
| `sampling` | dict | - | Sampling configuration (ML models only) |
| `sampling.method` | string | `"none"` | `over`, `undersample`, `smotetomek`, `none` |
| `sampling.threshold` | float | `0.5` | Threshold for undersampling |
| `hyperparams` | dict | - | Model hyperparameters (ML models only) |
| `hyperparam_search` | dict | - | Hyperparameter search configuration (ML models only) |
| `hyperparam_search.enabled` | boolean | `false` | Whether to perform hyperparameter search |
| `hyperparam_search.n_iter` | int | `60` | Number of iterations for RandomizedSearchCV |
| `hyperparam_search.cv` | int | `3` | Number of cross-validation folds |

### Model-Specific Configuration

#### LightGBM Configuration

```yaml
models:
  - type: "lightgbm"
    sampling:
      method: "undersample"  # over, undersample, smotetomek, none
      threshold: 0.5
    hyperparams:
      num_leaves: 31
      max_depth: -1
      learning_rate: 0.05
      n_estimators: 1000
    hyperparam_search:
      enabled: true
      n_iter: 60
      cv: 3
```

**LightGBM Hyperparameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_leaves` | int | `31` | Maximum number of leaves in one tree |
| `max_depth` | int | `-1` | Maximum tree depth (-1 = unlimited) |
| `learning_rate` | float | `0.05` | Boosting learning rate |
| `n_estimators` | int | `1000` | Number of boosting iterations |
| `min_child_samples` | int | `20` | Minimum samples in leaf |
| `subsample` | float | `1.0` | Subsample ratio of training data |

#### CatBoost Configuration

```yaml
models:
  - type: "catboost"
    sampling:
      method: "undersample"
      threshold: 0.5
    hyperparams:
      iterations: 500
      learning_rate: 0.05
      depth: 6
```

**CatBoost Hyperparameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `iterations` | int | `500` | Number of iterations |
| `learning_rate` | float | `0.05` | Learning rate |
| `depth` | int | `6` | Tree depth |
| `l2_leaf_reg` | float | `3.0` | L2 regularization |

#### Neural Network (Feedforward) Configuration

```yaml
models:
  - type: "neural_network"
    sampling:
      method: "undersample"
      threshold: 0.5
```

**Neural Network Notes:**
- Architecture: Dense(512) → Dense(64) → Dense(32) → Dense(16) → Dense(1, sigmoid)
- Uses early stopping with patience=50 on validation PR-AUC
- Automatically scales features using MinMaxScaler

#### LSTM Configuration

```yaml
models:
  - type: "lstm"
    sampling:
      method: "undersample"
      threshold: 0.5
```

**LSTM Notes:**
- Architecture: LSTM(128) → Concatenate with features → Dense(64) → Dense(32) → Dense(16) → Dense(1, sigmoid)
- Uses early stopping with patience=50 on validation PR-AUC
- Requires consumption columns in format: `12_anterior`, `11_anterior`, ..., `1_anterior`

#### Simple Trend Configuration (Rule-Based)

```yaml
models:
  - type: "simple_trend"
    threshold: 50              # Percentage drop to flag as fraud
    last_base_value: 6         # Number of periods for baseline (default: 6)
    last_eval_value: 3         # Number of periods for evaluation (default: 3)
```

**Simple Trend Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | float | `50` | Percentage drop above which user is flagged as fraud |
| `last_base_value` | int | `6` | Number of historical periods for baseline |
| `last_eval_value` | int | `3` | Number of recent periods for evaluation |

**How it works:**
- Computes: `trend_perc = 100 * mean(recent_periods) / mean(base_periods)`
- Flags as fraud if: `100 - trend_perc > threshold`
- Does NOT require preprocessing — uses raw consumption columns

#### Simple Constant Configuration (Rule-Based)

```yaml
models:
  - type: "simple_constant"
    min_count_constante: 3     # Consecutive equal values to flag (default: 3)
```

**Simple Constant Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_count_constante` | int | `3` | Minimum consecutive identical values to flag as fraud |

**How it works:**
- Detects runs of consecutive identical consumption values
- Flags as fraud if any run length >= min_count_constante
- Does NOT require preprocessing — uses raw consumption columns

### Multiple Models (Ensemble)

When you specify multiple models, ensemble configuration becomes required.

```yaml
models:
  - name: "lgbm"
    type: "lightgbm"
    sampling: { method: "undersample", threshold: 0.5 }
    hyperparams: { num_leaves: 31, learning_rate: 0.05, n_estimators: 500 }
    hyperparam_search: { enabled: false }

  - name: "cat"
    type: "catboost"
    sampling: { method: "undersample", threshold: 0.5 }
    hyperparams: { iterations: 300 }
    hyperparam_search: { enabled: false }
```

---

## Ensemble Configuration

Required when `len(models) > 1`.

```yaml
ensemble:
  method: "stacking"          # "stacking" | "soft_voting"
  meta_learner:
    type: "logistic_regression"
    params: { C: 1.0, max_iter: 1000 }
  use_val_as_oof: true        # true=blending (fast); false=proper CV OOF
  cv: 5                        # K-folds for OOF (only when use_val_as_oof=false)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | string | - | Ensemble method: `stacking` or `soft_voting` |
| `meta_learner` | dict | - | Meta-learner configuration (for stacking) |
| `meta_learner.type` | string | - | Meta-learner type |
| `meta_learner.params` | dict | - | Meta-learner hyperparameters |
| `use_val_as_oof` | boolean | `true` | Use validation set for OOF (blending) |
| `cv` | int | `5` | Number of CV folds (only when `use_val_as_oof=false`) |

**Ensemble Methods:**

- **`stacking`**: Trains a meta-learner on base model predictions. More powerful but slower.
- **`soft_voting`**: Averages base model predictions. Simpler and faster.

---

## Evaluation Configuration

```yaml
evaluation:
  enabled: true
  # threshold is ignored if calibration.enabled=true
  threshold: 0.5
  metrics: [auc, precision, recall, f1, confusion_matrix, cumulative_gains]
  generate_plots: true
  generate_html_report: true
  generate_json_report: true

  # Automatic threshold calibration (optional)
  calibration:
    enabled: false
    method: "cost_benefit"   # Options: cost_benefit | operational | precision_recall
    params:
      # For cost_benefit (minimizes total FP/FN cost):
      cost_fp: 1    # cost of inspecting a legitimate user
      cost_fn: 10   # cost of missing a fraud
      # For operational (fixes number of alerts):
      # capacity: 200   # maximum alerts per period
      # For precision_recall (guaranteed minimum recall):
      # min_recall: 0.80
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | `true` | Whether to perform evaluation |
| `threshold` | float | `0.5` | Decision threshold (ignored if `calibration.enabled=true`) |
| `metrics` | list | - | List of metrics to compute |
| `generate_plots` | boolean | `true` | Whether to generate plots |
| `generate_html_report` | boolean | `true` | Whether to generate HTML report |
| `generate_json_report` | boolean | `true` | Whether to generate JSON report |
| `calibration` | dict | - | Threshold calibration configuration |
| `calibration.enabled` | boolean | `false` | Whether to perform threshold calibration |
| `calibration.method` | string | - | Calibration method |
| `calibration.params` | dict | - | Calibration method parameters |

**Available Metrics:**

- `auc`: Area Under ROC Curve
- `precision`: Precision score
- `recall`: Recall score
- `f1`: F1 score
- `confusion_matrix`: Confusion matrix
- `cumulative_gains`: Cumulative gains chart

**Calibration Methods:**

| Method | Description | Parameters |
|--------|-------------|------------|
| `cost_benefit` | Minimizes total cost = (FP × cost_fp) + (FN × cost_fn) | `cost_fp`, `cost_fn` |
| `operational` | Ensures number of alerts matches inspection capacity | `capacity` |
| `precision_recall` | Guarantees minimum recall rate | `min_recall` |

**SHAP Explainability:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `shap.enabled` | bool | `false` | Enable SHAP value computation |
| `shap.max_samples` | int | `500` | Max samples for SHAP (controls compute time) |
| `shap.top_n_features` | int | `20` | Number of top features in SHAP plots |
| `shap.plot_types` | list | `["summary", "bar"]` | Which plots to generate |

Example:

```yaml
evaluation:
  shap:
    enabled: true
    max_samples: 500
    top_n_features: 20
    plot_types: [summary, bar]
```

> SHAP uses TreeExplainer for LightGBM/CatBoost and KernelExplainer for other model types.

**Per-Segment Evaluation:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `evaluation.segment_columns` | list[string] | `[]` | Column names to compute per-segment metrics |

Example:

```yaml
evaluation:
  segment_columns:
    - "zona"
    - "tipo_tarifa"
```

---

## Complete Example

### Single Model Example

```yaml
training:
  enabled: true
  input_path: "data/processed/sample_dataset.parquet"
  target_column: "target"
  periods_suffix: "_anterior"

  split:
    method: "stratified"
    test_size: 0.2
    val_size: 0.1
    random_state: 42

  feature_engineering:
    enabled: true

    preprocessing:
      enabled: true
      columns:
        actividad:
          - cardinality_reducer:
              threshold: 0.001
          - to_dummy: {}
        tipo_tarifa:
          - target_encoding:
              w: 20
        zona:
          - ordinal_encoding: {}

    feature_selection:
      enabled: false

  models:
    - type: "lightgbm"
      sampling:
        method: "undersample"
        threshold: 0.5
      hyperparams:
        num_leaves: 31
        learning_rate: 0.05
        n_estimators: 1000
      hyperparam_search:
        enabled: true
        n_iter: 60
        cv: 3

  evaluation:
    enabled: true
    threshold: 0.5
    metrics: [auc, precision, recall, f1, confusion_matrix, cumulative_gains]
    generate_plots: true
    generate_html_report: true
    generate_json_report: true
```

### Ensemble Example

```yaml
training:
  enabled: true
  input_path: "data/processed/sample_dataset.parquet"
  target_column: "target"

  split:
    method: "stratified"
    test_size: 0.2
    val_size: 0.1
    random_state: 42

  feature_engineering:
    enabled: true
    preprocessing:
      enabled: true
      columns:
        actividad:
          - cardinality_reducer:
              threshold: 0.001
          - to_dummy: {}

    feature_selection:
      enabled: false

  models:
    - name: "lgbm"
      type: "lightgbm"
      sampling: { method: "undersample", threshold: 0.5 }
      hyperparams: { num_leaves: 31, learning_rate: 0.05, n_estimators: 500 }
      hyperparam_search: { enabled: false }

    - name: "cat"
      type: "catboost"
      sampling: { method: "undersample", threshold: 0.5 }
      hyperparams: { iterations: 300 }
      hyperparam_search: { enabled: false }

  ensemble:
    method: "stacking"
    meta_learner:
      type: "logistic_regression"
      params: { C: 1.0, max_iter: 1000 }
    use_val_as_oof: true
    cv: 5

  evaluation:
    enabled: true
    threshold: 0.5
    metrics: [auc, precision, recall, f1]
    generate_plots: true
    generate_html_report: true
```

---

← [Configuration: ETL](etl.md) | [Configuration: Evaluation](evaluation.md) →
