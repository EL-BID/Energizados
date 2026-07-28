# Inference Configuration

Complete reference for `infer.yaml` configuration.

## Overview

Inference configuration defines how to apply a trained model to new data. It specifies the input data, model paths, output location, and prediction threshold.

## Configuration Structure

```yaml
infer:
  enabled: false          # Set to true to run inference
  input_path: "data/processed/sample_dataset.parquet"
  output_path: "output/predictions.csv"
  # Uncomment and set to point to a specific training run:
  # model_path: "output/train-YYYYMMDD_HHMM/models/model.pkl"
  # feature_engineering_path: "output/train-YYYYMMDD_HHMM/models/feature_engineering.pkl"
  threshold: 0.5
  type: "default"         # Use "default" or set custom_class
```

> **Note:** The template ships with `enabled: false`. You must set `enabled: true` and configure `model_path` and `feature_engineering_path` before running inference.

## Required Fields

| Parameter | Type | Description |
|-----------|------|-------------|
| `enabled` | boolean | Whether to execute inference |
| `input_path` | string | Path to input data (parquet or CSV) |
| `output_path` | string | Path where predictions will be saved |

## Optional Fields

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | float | `0.5` | Decision threshold (0.0 to 1.0) |
| `model_path` | string | auto-detected | Path to trained model file. If omitted, auto-detects from latest training run. |
| `feature_engineering_path` | string | auto-detected | Path to feature engineering pipeline. If omitted, auto-detects from same run as model. |
| `output_base_dir` | string | `"output"` | Base directory to search for latest training run |
| `output_include_input` | bool | `false` | **DEPRECATED.** Prepend ALL original input columns. Kept for backward compatibility — emits a `DeprecationWarning`; prefer `output_columns`. Ignored (with a warning) when `output_columns` is set. |
| `output_format` | string | `"csv"` | Output format: `"csv"` or `"parquet"` |
| `columns_filter` | dict | `null` | Filter rows by column values BEFORE FE. Supports equality, operators (>, <, >=, <=, !=, like), and pandas `_expr` |
| `output_columns` | list | `null` | **Self-sufficient** final column selection over `[input + prediction + probability + rule_*]`. Input columns named here are included automatically (no `output_include_input` needed); unlisted columns are dropped (omit `prediction` to exclude it). If absent, defaults to `[prediction, probability]` (+ `rule_*`). |

---

## How Inference Works

The inference process follows these steps:

1. **Load Input Data**: Reads the input dataset from `input_path`
2. **Apply Feature Engineering**: Loads the saved feature engineering pipeline and transforms the data
3. **Load Model**: Loads the trained model from `model_path`
4. **Generate Predictions**: Applies the model to the transformed data
5. **Apply Per-Row Thresholds**: (Optional) Applies per-segment thresholds if `segment_thresholds` is enabled
6. **Apply Business Rules**: (Optional) Evaluates rule-based overlays against raw pre-FE data if `business_rules` is enabled
7. **Finalize Predictions**: Converts probability scores to binary predictions (fraud/non-fraud)
8. **Save Results**: Writes predictions and probabilities to `output_path`

> **Note:** The template ships with `enabled: false`. You must set `enabled: true` to run inference. Model paths are auto-detected from the latest training run if not specified.

### Auto-Detect Model

If you omit `model_path` and `feature_engineering_path`, the system will automatically detect the latest training run:

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  # model_path and feature_engineering_path are auto-detected
  # from output/train-YYYYMMDD_HHMM/
  threshold: 0.5
```

### Single Model Inference

For a single model, the directory structure is:

```
output/train-20260317_1430/
├── models/
│   ├── feature_engineering.pkl
│   └── model.pkl
```

Configuration:

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
```

### Ensemble Model Inference

For an ensemble model, the directory structure is:

```
output/train-20260317_1430/
├── models/
│   ├── feature_engineering.pkl
│   ├── lgbm/
│   │   └── model.pkl
│   ├── cat/
│   │   └── model.pkl
│   └── ensemble.pkl
```

Configuration:

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/ensemble.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
```

> ⚠️ **IMPORTANT:** For ensembles, specify the path to `ensemble.pkl`, not individual model files.

---

## Output Format

The inference output is saved as a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| `prediction` | Binary prediction (0 or 1) based on threshold |
| `probability` | Probability score (0.0 to 1.0) |

### Example Output

```csv
prediction,probability
0,0.12
0,0.08
1,0.87
0,0.23
1,0.91
```

If your input data has an index column, the output will preserve that index. Otherwise, row numbers are used.

> 💡 **Customize the output columns** with `output_columns` — it is self-sufficient (input columns named in it are included automatically, no `output_include_input` needed) and lets you drop `prediction` by simply omitting it. See [Inference with Custom Output Columns](#inference-with-custom-output-columns) below.

---

## Running Inference

### Using the CLI

```bash
energizados run infer
```

### Using the Python Script

```bash
python src/run/03_inference.py --run-dir output/train-YYYYMMDD_HHMM
```

---

## Configuration Examples

### Basic Inference

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
```

### Inference with Custom Threshold

Use a higher threshold to reduce false positives (fewer unnecessary inspections):

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.7  # Higher threshold = fewer false positives
```

Use a lower threshold to reduce false negatives (catch more fraud):

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.3  # Lower threshold = catch more fraud
```

### Inference with Calibrated Threshold

If you used threshold calibration during training, use the calibrated threshold:

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.42  # Calibrated threshold from evaluation report
```

Check the evaluation report (`output/train-YYYYMMDD_HHMM/reports/evaluation/report.json`) to find the calibrated threshold.

### Batch Inference

Process multiple files by updating the configuration:

```yaml
infer:
  enabled: true
  input_path: "data/batch/january_2024.parquet"
  output_path: "predictions/january_2024.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
```

Then run for each month, updating paths accordingly.

### Inference with Filters (Optimization)

Filter records BEFORE feature engineering to avoid expensive operations like tsfel on records you don't need:

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
  
  # Filter BEFORE feature engineering (optimization)
  columns_filter:
    zona: ["FLORIANOPOLIS", "PALHOCA"]
```

### Filtering with Operators

Filter by comparison operators (`>`, `<`, `>=`, `<=`, `!=`, `like`):

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
  
  columns_filter:
    # Simple equality (list of values)
    zona: ["FLORIANOPOLIS", "PALHOCA"]
    nivel_tension: ["BT"]
    
    # Comparison operators
    consumo_1_anterior:
      ">": 0                    # consumption > 0
      "<=": 10000               # and consumption <= 10000
    
    fecha_inspeccion:
      ">=": "2026-01-01"        # date >= 2026-01-01
      "!=": null                # not null
    
    # Pattern matching ( LIKE %pattern% )
    actividad:
      like: "INDUSTRI"
```

### Filtering with Pandas Expression

Use pandas query syntax for complex filters:

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  threshold: 0.5
  
  columns_filter:
    _expr: "(zona == 'FLORIANOPOLIS') & (consumo_1_anterior > 500)"
```

### Inference with Custom Output Columns

Select specific columns for the output CSV. `output_columns` is **self-sufficient** — input columns named in it are included automatically (no `output_include_input` needed), and omitting `prediction` drops it:

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5

  # output_columns selects the FINAL output columns, in order. Input columns
  # (cliente, actividad, zona) are included automatically; 'prediction' is
  # omitted → not generated.
  output_columns:
    - cliente
    - actividad
    - zona
    - probability
```

> ⚠️ `output_include_input` is **deprecated**. If set together with `output_columns`, `output_columns` wins and `output_include_input` is ignored (with a `DeprecationWarning`). Use it only for the legacy “include ALL input columns” behavior (`output_include_input: true` without `output_columns`).

---

## Hierarchical / Route-Based Inference

Route rows to different models based on column-value conditions. This enables per-region, per-tariff, or per-cluster models with a fallback default model. Routing is **first-match-wins** — the first route condition that matches a row determines which model is used.

### Configuration Keys

| Parameter | Type | Description |
|-----------|------|-------------|
| `routes` | list | List of route definitions (see structure below) |
| `default_model_path` | string | Path to fallback model for rows matching no route |
| `feature_engineering_paths` | dict (optional) | Mapping of route name → FE `.pkl` path. If omitted, routes share the top-level FE. Use the reserved key `"__default__"` to provide the FE `.pkl` for the default model's rows (rows matching no route). |

> **Note:** `routes`, `default_model_path`, and `feature_engineering_paths` are builder-level keys and not validated by the config schema; typos won't be caught by `energizados validate`.

### Route Structure

Each entry in `routes` is a dict with:

- `name` (str): descriptive route name
- `condition` (dict): `{column: value_or_list}` matching logic. Conditions are combined with AND. Use a list for OR semantics (e.g., `geo_region: ["FLORIANOPOLIS", "SAO_PAULO"]`).
- `model_path` (str): path to the model `.pkl` file for this route

### Important Note

When `routes` are configured, `HierarchicalInference` loads its own route models internally. The top-level `model_path` is **not required** at the config level. This is native builder integration — no custom code needed.

### Example: Per-Region Models

```yaml
infer:
  enabled: true
  input_path: "data/processed/new_data.parquet"
  output_path: "output/predictions.csv"
  threshold: 0.5

  # No top-level model_path needed when routes are configured
  routes:
    - name: "florianopolis"
      condition:
        geo_region: "FLORIANOPOLIS"
      model_path: "models/regional/flor_model.pkl"

    - name: "south_regions"
      condition:
        geo_region: ["SAO_PAULO", "RIO", "BELO_HORIZONTE"]
      model_path: "models/regional/south_model.pkl"

    - name: "alta_tension"
      condition:
        nivel_tension: "ALTA"
      model_path: "models/alta_tension/model.pkl"

  default_model_path: "models/global/model.pkl"

  # Optional: route-specific feature engineering
  feature_engineering_paths:
    florianopolis: "models/regional/flor_fe.pkl"
    south_regions: "models/regional/south_fe.pkl"
    # alta_tension shares the top-level FE if omitted.
    # "__default__" provides the FE for the default model's rows (unrouted rows):
    __default__: "models/global/global_fe.pkl"
```

### Routing Behavior

- Rows are evaluated against routes in order
- First matching route determines the model used
- Rows matching no route use the `default_model_path`
- If no default is configured and a row is unrouted, it receives probability `0.0` (prediction `0`) with a warning

---

## Segment Thresholds

Apply per-segment optimal thresholds instead of a single global threshold. This is useful when different regions, zones, or customer segments require different operating points to optimize business metrics (e.g., fraud catch rate vs inspection cost).

### Configuration Keys

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `segment_thresholds.enabled` | boolean | `false` | Enable per-segment thresholds |
| `segment_thresholds.path` | string | `null` | Path to the JSON file exported by evaluation (e.g., `segment_thresholds_geo_region.json`) |
| `segment_thresholds.fallback_threshold` | float | `null` | Threshold for rows with unknown/missing segment values. If `null`, uses the global `threshold` |

### Exporting Segment Thresholds

Segment thresholds are exported by the evaluation step when `evaluation.segment_columns` is configured in `train.yaml`. The JSON file maps each unique segment value to its optimal threshold.

> **Default location change:** as of v0.4.0 the JSON is exported to the
> trained model's directory (`output/train-YYYYMMDD_HHMM/models/`) by
> default, because it is a deployment artifact consumed at predict time,
> not a report. Update existing `infer.yaml` `segment_thresholds.path`
> entries from `.../reports/evaluation/...` to `.../models/...`, or set
> `segmented_evaluation.thresholds_output_dir` in `train.yaml` to
> preserve the old location. See [Configuration: Evaluation](evaluation.md)
> for the override syntax.

### Example Configuration

```yaml
infer:
  enabled: true
  input_path: "data/processed/new_data.parquet"
  output_path: "output/predictions.csv"
  threshold: 0.5  # Global fallback (used for unknown segments)

  segment_thresholds:
    enabled: true
    path: "output/train-20260317_1430/models/segment_thresholds_geo_region.json"
    fallback_threshold: 0.5  # Optional: overrides global threshold for unknown segments
```

### JSON Format (from evaluation)

```json
{
  "segment_column": "geo_region",
  "threshold_mode": "youden",
  "default_threshold": 0.5,
  "segments": {
    "FLORIANOPOLIS": { "threshold": 0.42, "auc": 0.82, "n_samples": 150 },
    "SAO_PAULO": { "threshold": 0.55, "auc": 0.88, "n_samples": 320 },
    "RIO": { "threshold": 0.48, "auc": 0.79, "n_samples": 210 },
    "BELO_HORIZONTE": { "threshold": 0.51, "auc": 0.81, "n_samples": 180 }
  }
}
```

### Error Handling

- If the segment column is missing from the inference data, a `ValueError` is raised
- Unknown segment values use `fallback_threshold` (or the global `threshold` if not set)
- The JSON file is validated at load time

### Cross-Reference

See [Configuration: Evaluation](evaluation.md) for how to generate `segment_thresholds_*.json` files during training.

---

## Business Rules Overlay

Apply rule-based overlays to predictions AFTER segment thresholds. Rules evaluate pandas expressions against the **raw pre-feature-engineering data** and modify probabilities or add flag columns. This is useful for domain-specific logic where the model under-performs (e.g., regions with AUC < 0.5).

### Rule Actions

| Action | Description | Use Case |
|--------|-------------|----------|
| `flag` | Records that the rule triggered in `rule_<name>` (bool) and `rule_<name>_value` (float) columns, but does NOT modify probabilities. Use this for downstream analysis or manual review. | "Mark for investigation" flags that don't force a prediction |
| `override` | Sets `probability[triggered] = 1.0` (value is ignored). After this, the final prediction will be `1` since `1.0 >= threshold`. | "Force to fraud" for clear violations (e.g., zero consumption for 3 months) |
| `score_boost` | Adds `value` to `probability[triggered]` (clipped to [0, 1]). The boost respects segment thresholds if enabled. | "Increase suspicion score" for patterns the model should catch but doesn't |

### Configuration Keys

| Parameter | Type | Description |
|-----------|------|-------------|
| `business_rules.enabled` | boolean | Enable business rules evaluation |
| `business_rules.apply_to.column` | string | Column to filter rule eligibility (default: `"geo_region"`) |
| `business_rules.apply_to.regions` | list | Only rows with this column value in the list are eligible for rules. If omitted, rules apply to ALL rows. |
| `business_rules.rules` | list | List of rule definitions (see structure below) |
| `business_rules.output.add_rule_columns` | boolean | Whether to add `rule_<name>` (bool) and `rule_<name>_value` (float) columns to output (default: `true`) |

### Rule Structure

Each entry in `rules` is a dict with:

- `name` (str): descriptive rule name (used for output column names)
- `condition` (str): pandas `eval` expression. Must return a boolean Series. Use backticks for column names starting with digits (e.g., `` `3_anterior` ``). Use `"False"` for stub rules that never trigger.
- `action` (str): `"flag"`, `"override"`, or `"score_boost"`
- `value` (float): For `score_boost`, the amount to add (clipped to [0, 1]). For `override`, ignored (probability is set to 1.0). For `flag`, ignored.

### Pipeline Order

Business rules are evaluated **after** segment thresholds (or global threshold) in the inference pipeline. The model produces probabilities → segment thresholds may modify the binary decision → business rules may modify probabilities → final binary prediction is derived.

### Example Configuration

```yaml
infer:
  enabled: true
  input_path: "data/processed/new_data.parquet"
  output_path: "output/predictions.csv"
  threshold: 0.5

  segment_thresholds:
    enabled: true
    path: "output/train-20260317_1430/models/segment_thresholds_geo_region.json"
    fallback_threshold: 0.5

  business_rules:
    enabled: true

    # Only apply rules to specific regions (optional)
    apply_to:
      column: "geo_region"
      regions:
        - "FLORIANOPOLIS"
        - "SAO_PAULO"

    rules:
      - name: "consumo_cero_3m"
        condition: "(`3_anterior` == 0) & (`2_anterior` == 0) & (`1_anterior` == 0)"
        action: "override"
        value: 1.0  # Ignored for override

      - name: "caida_abrupta"
        condition: "(`1_anterior` * 11) < 0.4 * (`12_anterior` + `11_anterior` + `10_anterior` + `9_anterior` + `8_anterior` + `7_anterior` + `6_anterior` + `5_anterior` + `4_anterior` + `3_anterior` + `2_anterior`)"
        action: "score_boost"
        value: 0.3

      - name: "denuncia_sac"
        condition: "False"  # Stub rule — never triggers until data column exists
        action: "flag"
        value: 0.0

    output:
      add_rule_columns: true  # Adds rule_consumo_cero_3m, rule_consumo_cero_3m_value, etc.
```

### Output Columns

When `add_rule_columns: true`, the output CSV includes:

- `rule_<name>` (bool): `true` if the rule triggered
- `rule_<name>_value` (float): the `value` parameter from the rule (for audit/analysis)

These columns are in addition to the standard `prediction` and `probability` columns.

### Error Handling

- If a rule's `condition` references a non-existent column or fails to parse, the rule is skipped (error logged) and its trigger columns are all `False`. Other rules continue.
- Multi-line YAML conditions (using `>-`) are normalized to single spaces before evaluation, making them work with the pandas `eval` engine.
- `value` is automatically clipped to [0, 1].

---

## Custom Inference

To implement custom inference logic, edit `src/inference/custom_inference.py`:

```python
from energizados.inference.base import BaseInference
import pandas as pd

class CustomInference(BaseInference):
    def predict(self, data: pd.DataFrame) -> pd.DataFrame:
        # Apply feature engineering
        transformed = self.feature_engineering.transform(data)

        # Get probability scores
        probabilities = self.model.predict_proba(transformed)[:, 1]

        # Apply threshold
        predictions = (probabilities >= self.threshold).astype(int)

        # Create output DataFrame
        result = pd.DataFrame({
            'prediction': predictions,
            'probability': probabilities
        })

        # Add custom logic here
        # For example: filter out low-risk customers
        high_risk = result[result['probability'] >= 0.8]

        return high_risk
```

Update `infer.yaml` to use your custom class:

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
  custom_class: "inference.custom_inference.CustomInference"
```

---

## Best Practices

### 1. Model Versioning

Keep track of which model was used for infer:

```yaml
infer:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions_model_v1.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
```

### 2. Data Quality Checks

Ensure input data matches training data schema:

- Same columns
- Same data types
- Similar value ranges
- No new categories in categorical columns

### 3. Threshold Tuning

Adjust threshold based on business needs:

- **High precision** (fewer false positives): Use threshold 0.7-0.9
- **High recall** (catch more fraud): Use threshold 0.2-0.4
- **Balanced**: Use threshold 0.5 or calibrated threshold

### 4. Batch Processing

For large datasets, consider splitting into batches:

```bash
# Run inference on first batch
energizados run infer_batch1

# Run inference on second batch
energizados run infer_batch2
```

### 5. Monitoring

Track inference results over time to detect model drift:

- Monitor prediction distribution
- Track fraud rate in predictions
- Compare with historical performance

---

## Troubleshooting

### Common Issues

**Issue:** Feature engineering pipeline fails

**Solution:** Ensure input data has the same columns and types as training data.

**Issue:** Model loading fails

**Solution:** Verify the `model_path` points to the correct file:

- Single model: `models/model.pkl`
- Ensemble: `models/ensemble.pkl`

**Issue:** All predictions are the same

**Solution:** Check that:

- Input data is not empty
- Feature engineering is applying correctly
- Threshold is not set to 0.0 or 1.0

**Issue:** Out of memory error

**Solution:** Process data in smaller batches:

```python
# In custom_inference.py
for chunk in pd.read_csv(input_path, chunksize=10000):
    predictions = self.predict(chunk)
    predictions.to_csv(output_path, mode='a', header=not exists)
```

---

← [Configuration: Evaluation](evaluation.md) | [Troubleshooting](../troubleshooting.md) →
