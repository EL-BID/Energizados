# Evaluation Configuration

Complete reference for evaluation configuration in `train.yaml`.

## Overview

The evaluation section in `train.yaml` controls how models are evaluated, which metrics are computed, what visualizations are generated, and how reports are produced.

## Configuration Structure

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
    method: "cost_benefit"
    params:
      # Calibration method parameters

  # SHAP explainability (optional)
  shap:
    enabled: false
    max_samples: 500
    top_n_features: 20
    plot_types: [summary, bar]
```

## Parameters

### Required Fields

| Parameter | Type | Description |
|-----------|------|-------------|
| `enabled` | boolean | Whether to perform evaluation |
| `threshold` | float | Decision threshold for binary classification (0.0 to 1.0) |

> ⚠️ **IMPORTANT:** The `threshold` parameter is ignored if `calibration.enabled: true`. The calibrated threshold is used instead.

### Optional Fields

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metrics` | list | `[auc, precision, recall, f1, confusion_matrix, cumulative_gains]` | List of metrics to compute |
| `generate_plots` | boolean | `true` | Whether to generate visualization plots |
| `generate_html_report` | boolean | `true` | Whether to generate HTML report |
| `generate_json_report` | boolean | `true` | Whether to generate JSON report |
| `calibration` | dict | - | Threshold calibration configuration |
| `shap` | dict | - | SHAP explainability configuration |
| `segment_columns` | list[string] | `[]` | Column names to compute per-segment metrics |

---

## Per-Segment Evaluation

Evaluate model performance broken down by configurable grouping columns (e.g., zone, tariff type, customer category).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `segment_columns` | list[string] | `[]` | Column names to compute per-segment metrics |

Example:

```yaml
evaluation:
  segment_columns:
    - "zona"
    - "tipo_tarifa"
```

This generates a segment comparison table and interactive chart in the HTML report showing AUC, Precision, Recall, and F1 for each segment value. Segments are color-coded: green (≥0.7), yellow (≥0.4), red (<0.4).

---

## Available Metrics

| Metric | Description | Computed On |
|--------|-------------|-------------|
| `auc` | Area Under ROC Curve | Probability scores |
| `precision` | Precision score | Binary predictions |
| `recall` | Recall score | Binary predictions |
| `f1` | F1 score (harmonic mean of precision and recall) | Binary predictions |
| `confusion_matrix` | Confusion matrix with counts | Binary predictions |
| `cumulative_gains` | Cumulative gains chart | Probability scores (sorted) |

### Example: Specifying Metrics

```yaml
evaluation:
  enabled: true
  threshold: 0.5
  metrics: [auc, precision, recall, f1, confusion_matrix, cumulative_gains]
```

Or select a subset:

```yaml
evaluation:
  enabled: true
  threshold: 0.5
  metrics: [auc, precision, recall, f1]
```

---

## Output Files

When evaluation is enabled, the following files are generated in `output/train-YYYYMMDD_HHMM/reports/evaluation/`:

### HTML Report

**File:** `report.html`

A comprehensive, interactive HTML report containing:

- **Executive Summary**: Key metrics at a glance
- **Performance Metrics**: Detailed metric values and interpretations
- **Confusion Matrix**: Visual representation with counts
- **ROC Curve**: True positive rate vs false positive rate
- **Precision-Recall Curve**: Precision vs recall at various thresholds
- **Cumulative Gains Chart**: Lift analysis for business decision making
- **Feature Importance**: Top contributing features (for supported models)
- **Threshold Analysis**: Impact of different threshold values

The HTML report is self-contained and can be opened directly in any web browser.

### JSON Report

**File:** `report.json`

A machine-readable JSON file containing all metrics and metadata:

```json
{
  "metrics": {
    "auc": 0.95,
    "precision": 0.82,
    "recall": 0.78,
    "f1": 0.80
  },
  "confusion_matrix": {
    "tn": 8000,
    "fp": 200,
    "fn": 500,
    "tp": 200
  },
  "threshold": 0.5,
  "model_type": "lightgbm"
}
```

Use this for:
- Programmatic access to metrics
- Integration with CI/CD pipelines
- Custom dashboard visualizations
- Automated reporting systems

### Plots

**Directory:** `plots/`

Individual PNG files for each visualization:

- `confusion_matrix.png`: Confusion matrix visualization
- `roc_curve.png`: ROC curve plot
- `precision_recall_curve.png`: Precision-recall curve
- `cumulative_gains.png`: Cumulative gains chart
- `feature_importance.png`: Feature importance bar chart (if applicable)
- `shap_summary.png`: SHAP beeswarm plot (if SHAP enabled)
- `shap_bar.png`: Mean |SHAP| per feature (if SHAP enabled)

---

## Threshold Calibration

Threshold calibration automatically finds the optimal decision threshold based on your business constraints.

### Why Calibrate?

The default threshold of 0.5 is rarely optimal for imbalanced problems like electricity theft detection. Calibration allows you to:

- Minimize business costs
- Match operational capacity constraints
- Guarantee minimum fraud detection rates

### Configuration

```yaml
evaluation:
  enabled: true
  # threshold is ignored if calibration.enabled=true
  threshold: 0.5
  metrics: [auc, precision, recall, f1]

  calibration:
    enabled: true
    method: "cost_benefit"   # Options: cost_benefit | operational | precision_recall
    params:
      # Method-specific parameters
```

### Calibration Methods

#### 1. Cost Benefit Method

Minimizes total cost = (FP × cost_fp) + (FN × cost_fn).

**Use case:** You know the relative costs of false positives vs false negatives.

```yaml
calibration:
  enabled: true
  method: "cost_benefit"
  params:
    cost_fp: 1     # Cost of inspecting a legitimate user (relative units)
    cost_fn: 10    # Cost of missing a fraud (relative units)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `cost_fp` | float | Cost of false positive (inspecting a legitimate user) |
| cost_fn | float | Cost of false negative (missing a fraud) |

**Example:** If missing a fraud costs 10x more than inspecting a legitimate user, use `cost_fp: 1, cost_fn: 10`.

#### 2. Operational Method

Ensures the number of alerts matches your inspection capacity.

**Use case:** You have a fixed budget for inspections per period.

```yaml
calibration:
  enabled: true
  method: "operational"
  params:
    capacity: 200   # Maximum alerts per period
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `capacity` | int | Maximum number of alerts to generate per period |

**Example:** If you can inspect 200 customers per month, set `capacity: 200`.

#### 3. Precision Recall Method

Guarantees a minimum recall rate (fraud detection rate).

**Use case:** You need to catch at least X% of all fraud cases.

```yaml
calibration:
  enabled: true
  method: "precision_recall"
  params:
    min_recall: 0.80   # Ensure at least 80% of fraud is caught
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `min_recall` | float | Minimum recall rate (0.0 to 1.0) |

**Example:** To catch at least 80% of all fraud, set `min_recall: 0.80`.

### Calibration Output

When calibration is enabled:

1. The framework searches for the optimal threshold on the validation set
2. The calibrated threshold is reported in the evaluation results
3. All metrics (precision, recall, confusion matrix) are computed using the calibrated threshold
4. The HTML report shows both the calibrated threshold and its impact on metrics

### Example: Full Evaluation with Calibration

```yaml
evaluation:
  enabled: true
  # threshold is ignored since calibration.enabled=true
  threshold: 0.5
  metrics: [auc, precision, recall, f1, confusion_matrix, cumulative_gains]
  generate_plots: true
  generate_html_report: true
  generate_json_report: true

  calibration:
    enabled: true
    method: "cost_benefit"
    params:
      cost_fp: 1
      cost_fn: 10
```

---

## SHAP Explainability

### SHAP Configuration

SHAP (SHapley Additive exPlanations) provides model interpretability by computing feature attribution values.
It helps answer "which features drove this prediction?" — critical for regulatory compliance and model debugging.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `false` | Enable SHAP value computation and plot generation |
| `max_samples` | int | `500` | Maximum samples for SHAP computation (background + test). Higher = more accurate but slower |
| `top_n_features` | int | `20` | Number of top features to display in SHAP plots |
| `plot_types` | list | `["summary", "bar"]` | Plot types: `summary` (beeswarm) and/or `bar` (mean |SHAP|) |

### How it works

- **LightGBM / CatBoost**: Uses `shap.TreeExplainer` (fast, accurate)
- **Ensembles / NN / LSTM**: Uses `shap.KernelExplainer` (model-agnostic, slower)

> ⚠️ **Performance**: SHAP on large datasets can be slow. Use `max_samples` to limit computation.
> For 500K+ row test sets, SHAP automatically subsamples to `max_samples` rows.

### Output

SHAP generates two plots in the evaluation report:
- **Summary Plot (beeswarm)**: Shows feature impact on predictions, colored by feature value
- **Bar Plot**: Mean absolute SHAP value per feature (feature importance)

These appear in a dedicated "SHAP Explainability" section in the HTML report.

---

## Complete Examples

### Basic Evaluation

```yaml
evaluation:
  enabled: true
  threshold: 0.5
  metrics: [auc, precision, recall, f1]
  generate_plots: true
  generate_html_report: true
  generate_json_report: true
```

### Evaluation with Cost-Based Calibration

```yaml
evaluation:
  enabled: true
  metrics: [auc, precision, recall, f1, confusion_matrix]
  generate_plots: true
  generate_html_report: true
  generate_json_report: true

  calibration:
    enabled: true
    method: "cost_benefit"
    params:
      cost_fp: 1    # Inspecting a legitimate user costs $10
      cost_fn: 50   # Missing a fraud costs $500
```

### Evaluation with Operational Constraints

```yaml
evaluation:
  enabled: true
  metrics: [auc, precision, recall, f1, confusion_matrix]
  generate_plots: true
  generate_html_report: true
  generate_json_report: true

  calibration:
    enabled: true
    method: "operational"
    params:
      capacity: 200   # Can only inspect 200 customers per month
```

### Evaluation with Minimum Recall Guarantee

```yaml
evaluation:
  enabled: true
  metrics: [auc, precision, recall, f1, confusion_matrix]
  generate_plots: true
  generate_html_report: true
  generate_json_report: true

  calibration:
    enabled: true
    method: "precision_recall"
    params:
      min_recall: 0.80   # Must catch at least 80% of fraud
```

---

## Interpreting Results

### AUC (Area Under ROC Curve)

- **Range:** 0.0 to 1.0
- **Interpretation:**
  - 0.5: Random guessing
  - 0.7-0.8: Acceptable
  - 0.8-0.9: Excellent
  - 0.9-1.0: Outstanding

### Precision

- **Range:** 0.0 to 1.0
- **Interpretation:** Of all predicted fraud cases, how many are actually fraud?
  - Higher precision = fewer false positives (fewer unnecessary inspections)

### Recall

- **Range:** 0.0 to 1.0
- **Interpretation:** Of all actual fraud cases, how many did we catch?
  - Higher recall = fewer false negatives (less revenue lost to theft)

### F1 Score

- **Range:** 0.0 to 1.0
- **Interpretation:** Harmonic mean of precision and recall
  - Good balance metric when both precision and recall are important

### Confusion Matrix

```
                 Predicted
                Non-Fraud | Fraud
Actual Non-Fraud    TN     |  FP
Actual Fraud        FN     |  TP
```

- **TN (True Negative):** Correctly identified non-fraud
- **FP (False Positive):** Legitimate user incorrectly flagged as fraud
- **FN (False Negative):** Fraud missed
- **TP (True Positive):** Correctly identified fraud

### Cumulative Gains

- **Interpretation:** Shows the percentage of fraud captured when targeting the top X% of predictions
- **Use case:** Helps decide how many customers to inspect given limited resources

---

← [Configuration: Training](train.md) | [Configuration: Inference](infer.md) →
