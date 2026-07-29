# Training Configuration

Complete reference for `train.yaml` configuration.

## Overview

The training configuration file controls the entire training pipeline with five main sections:

- **`split`**: Data splitting into train/val/test sets
- **`feature_engineering`**: Preprocessing and feature selection
- **`models`**: Model configuration (single or multiple)
- **`ensemble`**: Ensemble configuration (optional, required when multiple models)
- **`evaluation`**: Metrics, reports, and threshold settings

**In this page:**

| Section | Covers |
|---------|--------|
| [Split Configuration](#split-configuration) | train/val/test splits, `none` no-holdout, time-series, group-based, geo-stratify |
| [Feature Engineering](#feature-engineering-configuration) | preprocessing, global transformers, feature selection |
| [Model Configuration](#model-configuration) | single model, sampling, hyperparams, hyperparam search |
| [Ensemble Configuration](#ensemble-configuration) | soft voting, stacking, blending vs OOF |
| [Evaluation Configuration](#evaluation-configuration) | metrics, threshold calibration, segmented evaluation |
| [Complete Example](#complete-example) | full annotated `train.yaml` |

## File Structure

```yaml
train:
  enabled: true                     # Whether to execute training
  description: "Experiment description"  # Optional: shown in evaluation report
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
| `description` | string | `""` | Experiment description shown in the evaluation HTML report header |
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
  splits_dir: "data/temp/splits/"
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
| `splits_dir` | string | `"data/temp/splits/"` | Directory to save split files |

**group_based split**

Split by groups to prevent data leakage. All rows with the same group value
(e.g., `customer_id`) are kept in the same split.

```yaml
split:
  method: "group_based"
  group_column: "customer_id"
  test_size: 0.2
  val_size: 0.1
  random_state: 42
  save_splits: true
  splits_dir: "data/temp/splits/"
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
| `splits_dir` | string | `"data/temp/splits/"` | Directory to save split files |

**Important:** Proportions apply at the **group level**, not the row level. Because groups may differ in size, row-level proportions may deviate from the requested `test_size`/`val_size`. This is inherent to group-aware splitting.

**Metadata:** When `method: "group_based"`, `split_metadata.json` includes additional keys: `group_column`, `n_groups_total`, `n_groups_train`, `n_groups_val`, `n_groups_test`.

**Class imbalance warning:** A `WARNING` is logged if any split's positive-class rate falls below 10% or exceeds 90%, since group-based splits cannot guarantee stratification.

#### Stratified Time Split

Temporal split within each geographic cluster. Requires the `geo_cluster` column produced by `GeoFeaturesETL`. Performs a time-based split separately for each cluster, maintaining geographic representation across train/val/test sets.

```yaml
split:
  method: "stratified_time"
  date_column: "fecha_inspeccion"
  cluster_column: "geo_cluster"   # requires GeoFeaturesETL run beforehand
  test_size: 0.15
  val_size: 0.15
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | string | - | Must be `"stratified_time"` |
| `date_column` | string | - | Date column for temporal ordering (required) |
| `cluster_column` | string | - | Column containing cluster IDs (e.g., `geo_cluster` from GeoFeaturesETL) (required) |
| `test_size` | float | `0.15` | Proportion of data for test set |
| `val_size` | float | `0.15` | Proportion of data for validation set |

**Important:** Requires `GeoFeaturesETL` to be executed before training to generate the `cluster_column` (e.g., `geo_cluster`). Each cluster is split independently using time-based logic, then the splits are combined.

#### No-Holdout Training (`none`)

Trains on the **full dataset** without reserving a validation or test split. Use this for production model training once offline evaluation is complete and you want to maximize the signal from all available data.

```yaml
split:
  method: "none"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | string | - | Must be `"none"` |

**What changes under the hood:**

- `SplitStep` writes only `train.parquet`; `val_path` and `test_path` remain `None`.
- `TrainingStep` accepts `val_path=None` and internally reserves 10% of the data for early stopping only.
- Metrics that require holdout data (`val_auc`, `val_f1`) return `None` honestly instead of fabricated numbers.
- A new `holdout_mode` field is exposed in the run context: `"none"` or `"standard"`.
- The evaluation step is auto-skipped by the director with a `WARNING`; `DefaultEvaluator` returns `skipped=True` defensively.

**Interactions to be aware of:**

- **Probability calibration** is skipped with a `WARNING` (it needs validation data).
- **Ensemble blending** (`use_val_as_oof: true`) raises a `ConfigurationError`. Three alternatives: (1) provide a `split.method` with a holdout, (2) switch to `use_val_as_oof: false` (K-fold OOF stacking), or (3) use `method: "soft_voting"`.
- **Soft-voting ensembles** and **K-fold OOF stacking** work without validation data.

> **Available since v0.3.3.** Every other `split.method` (`stratified`, `random`, `time_series`, `group_based`, `stratified_time`) remains byte-identical.

#### Unlabeled Negatives (Optional)

Injects unlabeled contracts as `target=0` samples into the train split to reduce selection bias. Useful when the labeled dataset is biased toward inspected contracts (e.g., only high-risk or region-specific inspections).

```yaml
split:
  method: "time_series"
  date_column: "fecha_inspeccion"
  train_period: ["2010-01-01", "2017-08-01"]
  val_period: ["2017-09-01", "2017-12-31"]
  test_period: ["2018-01-01"]

  # Optional: inject unlabeled negatives as target=0 (reduces selection bias)
  unlabeled_negatives:
    enabled: true
    source_path: "data/external/unlabeled.parquet"
    max_per_cutoff: 1500
    random_state: 42
    date_column: "fecha_inspeccion"
    id_column: "contract_id"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | `false` | Whether to inject unlabeled negatives |
| `source_path` | string | - | Path to external parquet file with unlabeled contracts (required when enabled) |
| `max_per_cutoff` | int | `1500` | Maximum number of unlabeled negatives to sample per cutoff period |
| `random_state` | int | `42` | Random seed for reproducibility |
| `date_column` | string | - | Date column for time-based filtering and deduplication |
| `id_column` | string | - | Contract ID column for deduplication (excludes contracts already in val/test) |

**Important:** Unlabeled negatives are added to the **train split only**. Contracts present in val/test sets are excluded via deduplication on `id_column`.

#### Geo-Stratify (Optional)

Balances geographic representation in the train set by limiting samples per stratum. Useful when some regions are overrepresented and you want a more balanced training distribution.

```yaml
split:
  method: "stratified"
  test_size: 0.2
  val_size: 0.1
  random_state: 42

  # Optional: balance geographic representation in train set
  geo_stratify:
    enabled: true
    column: "geo_region"
    strategy: "proportional"  # proportional | equal | capped
    max_per_stratum: null     # required when strategy: capped
    random_state: 42
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | `false` | Whether to apply geo-stratification |
| `column` | string | - | Column defining geographic strata (required when enabled) |
| `strategy` | string | - | Strategy: `proportional` (cap to median), `equal` (reduce to min), or `capped` (cap at max_per_stratum) |
| `max_per_stratum` | int | - | Maximum samples per stratum (required when `strategy="capped"`) |
| `random_state` | int | `42` | Random seed for reproducibility |

**Strategies:**

- `proportional`: Caps each stratum to the median count (reduces overrepresented regions proportionally)
- `equal`: Reduces all strata to the minimum count (aggressive balancing)
- `capped`: Caps each stratum to `max_per_stratum` (manual control)

**Warning:** A `WARNING` is logged if geo-stratification would remove more than 50% of training data. This is a guardrail against aggressive downsampling.

---

## Feature Engineering Configuration

```yaml
feature_engineering:
  enabled: true
  output_pkl: "data/processed/feature_engineering.pkl"

  preprocessing:
    enabled: true
    drop_columns: ["index", "fecha_inspeccion"]
    # columns_filter: Optional row-level filter applied to train/val/test BEFORE
    #   feature engineering. See "Row-level filtering (columns_filter)" below.
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

### Row-level filtering (`columns_filter`)

`columns_filter` removes rows from the dataset **before** feature engineering. It applies independently to each split (train, val, test), keeping `X` and `y` aligned by index. Useful when you want to train a region-specific model without splitting the ETL into separate outputs.

> **Tip:** For a single-region training run, `columns_filter` is simpler than adding a custom ETL. For multi-region experiments, consider running separate training configs (one per region) so each run has its own model and metadata.

```yaml
preprocessing:
  columns_filter:
    # Simple equality (single value or list)
    geo_region: "FLORIANOPOLIS"
    zona: ["NORTE", "SUL"]

    # Comparison operators (column: {">": 250, "<=": 500})
    consumo: {">": 100, "<=": 50000}

    # Pandas query expression (applied first, before per-column filters)
    _expr: "(zona != 'A') & (consumo > 200)"
```

**Supported operators:** `>`, `<`, `>=`, `<=`, `!=`, `==`, `like` (case-insensitive substring via `str.contains`).

**Important behavior:**

- The filter is applied to **all splits** (train, val, test) so that evaluation stays consistent. If your goal is to only filter the training set, keep the unfiltered val/test in your splits and rely on the model's generalization.
- Filtering happens before `drop_columns` and before any column encoding — the filter columns don't need to be in the `columns:` config.
- The number of rows removed from each split is logged at INFO level.
- If a referenced column is missing from the data, a WARNING is logged and the filter is skipped for that column.

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

**Global transformers:**

All transformers are listed under `global_transformers`. The framework automatically determines their execution stage:

- **Pre-encoding** (`pipeline_stage = "pre"`): run before column-level encoding, so they see the original categorical columns. Use when the transformer needs to `groupby` on a column that would otherwise be target-encoded.
- **Post-encoding** (default): run after column-level encoding, on the fully transformed feature set.

| Transformation | Stage | Description | Parameters |
|----------------|-------|-------------|------------|
| `clip_outliers` | post | Clips extreme values in consumption columns | `threshold` (float, default=100000), `columns` (list, default=null), `periods_suffix` (str, default="_anterior") |
| `tsfel_vars` | post | Time series feature extraction using tsfel | `num_periodos` (int, default=12), `features` (dict, default=null), `periods_suffix` (str, default="_anterior"), `n_jobs` (int, default=1), `chunk_size` (int, default=500), `cache_dir` (str, default=null) |
| `extra_vars` | post | Statistical features for different time windows | `num_periodos` (int, default=3), `periods_suffix` (str, default="_anterior"), `count_nulls` (bool, default=false) |
| `consumption_patterns` | post | Domain-specific fraud detection features | `num_periodos` (int, default=12), `periods_suffix` (str, default="_anterior"), plus enable flags |
| `group_relative_consumption` | **pre** | Consumption relative to group statistics (e.g. actividad, tarifa, zona). Generates `prop_cons_{window}_{metric}_{group_column}` | `group_column` (str, default="actividad"), `windows` (list[int], default=[3,6,12]), `metrics` (list[str], default=["mean","max"]), `periods_suffix` (str, default="_anterior") |
| `seasonal_anomaly` | **pre** | Seasonal z-score for each month vs group mean/std for that calendar month. Generates `seasonal_anomaly_{i}_anterior` | `group_column` (str, default="actividad"), `date_column` (str, required), `periods_suffix` (str, default="_anterior") |
| `if_score` | post | Isolation Forest anomaly score | `columns` (list, default=null), `n_estimators` (int, default=100), `contamination` (float/str, default="auto"), `output_column` (str, default="if_score"), `periods_suffix` (str, default="_anterior") |

### Global Transformers

Global transformers act on the entire dataset and generate new features. They are all listed under the single `global_transformers` key — no manual ordering between stages is needed.

The framework splits them into two internal stages based on each transformer's `pipeline_stage` class attribute:

1. **Pre-encoding** (`pipeline_stage = "pre"`): runs *before* `column_transformer`. These transformers need the original categorical columns (e.g., to `groupby("actividad")` before it becomes `actividad_prob` after target encoding). `SeasonalAnomaly` and `GroupRelativeConsumption` use this stage.
2. **Post-encoding** (default): runs *after* `column_transformer`, on the fully encoded feature set. All other built-in transformers use this stage.

The assembled pipeline is always: **[pre-encoding?] → column_transformer → [post-encoding?]**

#### clip_outliers

Clips extreme values in consumption columns to a configurable threshold. Use this to remove data reading errors (e.g., values of 10^16 kWh) before any feature extraction. Should be the **first** global transformer in the list.

```yaml
- clip_outliers:
    threshold: 100000
    periods_suffix: "_anterior"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | float | `100000` | Maximum allowed value — values above this are replaced with the threshold |
| `columns` | list | `null` | Explicit list of columns to clip. If null, auto-detects columns ending with `periods_suffix` |
| `periods_suffix` | string | `"_anterior"` | Suffix for auto-detection of consumption columns |

#### tsfel_vars

Time series feature extraction using the tsfel library.

Use `features` to select specific features inline in YAML (recommended). If omitted, all domains are extracted and the full feature list is logged at INFO level so you can copy-paste it into future configs.

```yaml
# Recommended: inline feature selection
- tsfel_vars:
    num_periodos: 12
    features:
      statistical:
        - Mean
        - Standard deviation
        - Max
        - Min
        - Median
        - Skewness
        - Kurtosis
        - Mean absolute deviation
      temporal:
        - Autocorrelation
        - Mean absolute diff
        - Median absolute diff
        - Slope
        - Zero crossing rate
    periods_suffix: "_anterior"
    n_jobs: -1        # -1 = all cores, 1 = sequential
    chunk_size: 500   # rows per chunk per worker
    cache_dir: ".cache/tsfel"  # recommended for iterative runs

# Alternative: all features (logs the list for copy-paste)
- tsfel_vars:
    num_periodos: 12
    periods_suffix: "_anterior"
    n_jobs: -1
    cache_dir: ".cache/tsfel"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_periodos` | int | `12` | Number of time series columns |
| `features` | dict | `null` | Inline feature selection: `{domain: [name, ...]}`. If null, all domains are used and the list is logged at INFO. |
| `periods_suffix` | string | `"_anterior"` | Suffix of time series columns |
| `n_jobs` | int | `1` | Number of parallel jobs (1 = sequential) |
| `chunk_size` | int | `500` | Rows per chunk per worker |
| `cache_dir` | string | `null` | Directory to cache tsfel results (recommended) |

Available domains: `statistical`, `temporal`, `spectral`. Feature names within each domain must match the tsfel 0.1.9+ API (e.g. `Standard deviation`, not `Std`). Run without `features` once to get the full logged list.

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

#### consumption_patterns

Domain-specific fraud detection features derived from the consumption time series.

```yaml
- consumption_patterns:
    num_periodos: 12
    periods_suffix: "_anterior"
    enable_diff_ratios: true
    enable_minmax_ratio: true
    enable_zscore: true
    enable_zero_ratio: true
    enable_slope: true
    enable_consistency: true
    enable_drastic_changes: true
    drastic_threshold: 0.5
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_periodos` | int | `12` | Number of time series columns |
| `periods_suffix` | string | `"_anterior"` | Suffix of time series columns |
| `enable_diff_ratios` | bool | `true` | Enable diff ratio features between consecutive periods |
| `enable_minmax_ratio` | bool | `true` | Enable min/max ratio feature |
| `enable_zscore` | bool | `true` | Enable z-score feature |
| `enable_zero_ratio` | bool | `true` | Enable zero ratio feature |
| `enable_slope` | bool | `true` | Enable slope and normalized slope features |
| `enable_consistency` | bool | `true` | Enable consistency score feature |
| `enable_drastic_changes` | bool | `true` | Enable drastic changes count feature |
| `drastic_threshold` | float | `0.5` | Threshold for drastic changes (0.5 = 50%) |
| `enable_last_period_zscore` | bool | `false` | Enable z-score of last period vs client's own mean/std (adds `zscore_last_vs_history_N`) |
| `enable_autocorr_lag1` | bool | `false` | Enable lag-1 autocorrelation (adds `autocorr_lag1_N`) — low values signal manipulation |
| `enable_seasonal_ratio` | bool | `false` | Enable summer/winter seasonal ratio (adds `seasonal_ratio_N`) — southern hemisphere context |
| `date_column` | str | `null` | Inspection date column (required when `enable_seasonal_ratio=true`) |

**Generated features (when enabled):**

- `diff_X_Y`: Ratio of change between consecutive periods
- `min_max_ratio_X`: Ratio of min/max consumption
- `zscore_mean_X`: Z-score of mean consumption
- `zero_ratio_X`: Proportion of months with zero consumption
- `slope_normalized_X`: Slope normalized by mean
- `consistency_score_X`: Consistency score (low variability = suspicious)
- `drastic_changes_count_X`: Count of changes exceeding threshold
- `zscore_last_vs_history_N`: Z-score of last period vs client's own mean/std (when `enable_last_period_zscore=true`)
- `autocorr_lag1_N`: Lag-1 autocorrelation (when `enable_autocorr_lag1=true`)
- `seasonal_ratio_N`: Summer/winter mean ratio (when `enable_seasonal_ratio=true`, southern hemisphere)

#### group_relative_consumption

Computes the ratio between each client's own consumption aggregate (mean or max over a window) and the corresponding aggregate for the peer group defined by `group_column` (e.g., `actividad`, `tipo_tarifa`, `zona`).

This is a strong fraud signal: a residential customer consuming like an industrial one is a red flag.

> **Stage:** `pre` — runs before column encoding. `group_column` must be a column present in the raw dataset (before target encoding renames it).

```yaml
- group_relative_consumption:
    group_column: "actividad"
    windows: [3, 6, 12]
    metrics: ["mean", "max"]
    periods_suffix: "_anterior"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `group_column` | string | `"actividad"` | Column defining the peer group (must be categorical, pre-encoding) |
| `windows` | list[int] | `[3, 6, 12]` | Window sizes (number of recent periods) |
| `metrics` | list[str] | `["mean", "max"]` | Group statistics to compare against. Supported: `"mean"`, `"max"` |
| `periods_suffix` | string | `"_anterior"` | Suffix of time series columns |

**Generated features:** `prop_cons_{window}_{metric}_{group_column}`

> **Anti-leakage note:** Group statistics are learned from the data passed to `fit()` (typically the training set). To use population-level statistics, ensure the training data includes the full population.

#### seasonal_anomaly

For each consumption month, computes a z-score relative to the group's historical mean and standard deviation for that calendar month. Tells the model *"this client consumes 30% less than expected for its type in this month"*.

> **Stage:** `pre` — runs before column encoding. `group_column` must be a column present in the raw dataset (before target encoding renames it).

```yaml
- seasonal_anomaly:
    group_column: "actividad"
    date_column: "fecha_inspeccion"
    periods_suffix: "_anterior"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `group_column` | string | `"actividad"` | Column defining the peer group (must be categorical, pre-encoding) |
| `date_column` | string | *(required)* | Inspection/cutoff date column (maps each period to a calendar month) |
| `periods_suffix` | string | `"_anterior"` | Suffix of time series columns |

**Generated features:** `seasonal_anomaly_{i}_anterior` (one per consumption period)

> **Anti-leakage note:** Group monthly statistics are learned from the training data passed to `fit()`. Ensure temporal ordering is respected.

#### geo_features

Geographic features — clustering (`geo_cluster`), IBGE hierarchy, and distances — are owned by the `GeoFeatures` transformer (`preprocessing/geo_features.py`). The convenient path is `GeoFeaturesETL` in `etl.yaml` (a thin wrapper that handles file I/O and the train/infer model hand-off via `geo_model_path`). See [ETL configuration → GeoFeaturesETL](etl.md#geofeaturesetl).

You can also use `GeoFeatures` directly via `custom_class` in `global_transformers`: it supports `include_cluster: true` (clustering), hierarchy, distances, and — for target encoding of geographic columns (e.g. `geo_estado_prob`) — `include_target_encoding: true`.

#### if_score

Isolation Forest anomaly score — generates an `if_score` column where **higher values indicate more anomalous observations**. This is an unsupervised feature that complements supervised models by encoding how "unusual" each observation is across its consumption patterns.

```yaml
- if_score:
    columns: null                  # auto-detect columns ending with periods_suffix
    n_estimators: 100
    contamination: "auto"          # "auto", or a float between 0 and 0.5
    contamination_from_target: true  # uses y.mean() as contamination (recommended)
    output_column: "if_score"
    periods_suffix: "_anterior"
```

**Key parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `columns` | list | `null` | Explicit list of columns. If null, auto-detects numeric columns ending with `periods_suffix` |
| `n_estimators` | int | `100` | Number of trees in the Isolation Forest |
| `max_samples` | int/str | `"auto"` | Number of samples to draw for training each tree |
| `max_features` | float | `1.0` | Fraction of features to consider for each split |
| `contamination` | float/str | `"auto"` | Expected proportion of anomalies. Use `"auto"` or a float between 0 and 0.5 |
| `random_state` | int | `null` | Random seed for reproducibility |
| `contamination_from_target` | bool | `false` | When `true`, uses `y.mean()` as contamination (derived from fraud rate) |
| `output_column` | str | `"if_score"` | Name of the generated score column |
| `periods_suffix` | str | `"_anterior"` | Suffix for auto-detecting consumption columns |

**Tips:**

- Set `contamination_from_target: true` to automatically use the fraud rate as the expected anomaly proportion
- Run `clip_outliers` **before** `if_score` to avoid extreme values distorting anomaly detection
- The score is inverted from sklearn's `score_samples()` so that higher = more anomalous (more intuitive for fraud detection)

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
          features:
            statistical:
              - Mean
              - Standard deviation
              - Max
              - Min
              - Median
              - Skewness
              - Kurtosis
              - Mean absolute deviation
            temporal:
              - Autocorrelation
              - Mean absolute diff
              - Median absolute diff
              - Slope
              - Zero crossing rate
          periods_suffix: "_anterior"
          n_jobs: -1
          chunk_size: 500
          cache_dir: ".cache/tsfel"

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
| `boruta` | Boruta algorithm — runs 10 times, selects features in ≥5 runs | `n_estimators` (100), `max_depth` (8), `max_iter` (100) |
| `correlation` | Removes one of each highly correlated pair | `method` ("pearson"), `threshold` (0.9) |
| `constant` | Removes columns where one value covers >threshold of rows | `threshold` (0.99) |
| `categorical` | Keeps only object/category dtype columns | `include_category` (true), `include_object` (true) |
| `mutual_information` | Keeps top-k features by mutual information | `k` (10), `random_state` (42) |

---

## Model Configuration

### Available Model Types

Energizados supports seven model types:

| Type | Aliases | Description | Requires Preprocessing |
|------|---------|-------------|----------------------|
| `lightgbm` | `lgbm` | Gradient Boosting with LightGBM | Yes |
| `catboost` | `cat` | CatBoost classifier | Yes |
| `xgboost` | `xgb` | XGBoost classifier | Yes |
| `neural_network` | `nn` | Feedforward Neural Network (Dense) | Yes |
| `lstm` | - | LSTM for sequential consumption data | Yes |
| `simple_trend` | - | Rule-based trend detector | No (uses raw data) |
| `simple_constant` | - | Rule-based constant consumption detector | No (uses raw data) |

### Model Categories

#### Machine Learning Models (Require Preprocessing)

These models require feature engineering preprocessing to work correctly:

- **lightgbm**: Fast gradient boosting, good for tabular data
- **catboost**: Handles categorical features natively
- **xgboost**: XGBoost gradient boosting (optional: `pip install energizados[xgboost]`)
- **neural_network**: Feedforward Dense network with scaled features
- **lstm**: Long Short-Term Memory network for sequential consumption patterns

#### Anomaly Detection (Feature Engineering)

Isolation Forest anomaly scoring is available as a **global_transformer** (`if_score`) in preprocessing, not as a model type. See the [Global Transformers](#global-transformers) section for configuration.

#### Rule-Based Models (Use Raw Data)

These models work directly on raw consumption columns without preprocessing:

- **simple_trend**: Detects fraud based on consumption trend drops
- **simple_constant**: Detects fraud based on suspiciously constant consumption

### Single Model Configuration

```yaml
models:
  - type: "lightgbm"  # lightgbm, catboost, neural_network, lstm
    sampling:
      method: "undersample"  # oversample, undersample, smotetomek, none
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
| `type` | string | - | Model type: `lightgbm`, `catboost`, `xgboost`, `neural_network`, `lstm`, `simple_trend`, `simple_constant` |
| `sampling` | dict | - | Sampling configuration (ML models only) |
| `sampling.method` | string | `"none"` | `oversample`, `undersample`, `smotetomek`, `none` |
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
      method: "undersample"  # oversample, undersample, smotetomek, none
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
| `class_weight` | string/dict | `null` | e.g. `"balanced"` — when set, **sampling is bypassed entirely** and class imbalance is handled via LightGBM weights instead |

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
| `skip_base_fit` | boolean | - | Internal to EnsembleModel API; not a user-facing YAML config. The built-in training flow always pre-fits base models and sets this internally when training the ensemble. |

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
    strategy: "cost_benefit"   # Options: cost_benefit | operational | precision_recall
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

**Segmented Evaluation:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `evaluation.segment_columns` | list[string] | `[]` | Column names to compute per-segment metrics (legacy) |
| `evaluation.segmented_evaluation.by` | list[string] | `[]` | Columns or combos (e.g. `"zona+region"`) for segmented evaluation |
| `evaluation.segmented_evaluation.min_samples` | int | `30` | Minimum samples per segment |
| `evaluation.segmented_evaluation.threshold_mode` | string | `"global"` | Threshold mode: `global`, `youden`, `f1_optimal`, `recall_target` |
| `evaluation.segmented_evaluation.recall_target` | float | `0.80` | Target recall (only when threshold_mode=`recall_target`) |

Example:

```yaml
evaluation:
  segment_columns:
    - "zona"
    - "tipo_tarifa"

  segmented_evaluation:
    enabled: true
    by: ["zona", "region", "zona+region"]
    min_samples: 30
    threshold_mode: "global"  # or "youden", "f1_optimal", "recall_target"
    recall_target: 0.80
```

**Threshold modes:**

- `global`: uses the global threshold for all segments
- `youden`: finds optimal threshold per segment using Youden's J statistic (maximizes sensitivity + specificity - 1)
- `f1_optimal`: maximizes F1 score per segment
- `recall_target`: finds threshold that achieves target recall per segment

---

## Complete Example

### Single Model Example

```yaml
train:
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
train:
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
