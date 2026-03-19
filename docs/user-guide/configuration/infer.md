# Inference Configuration

Complete reference for `infer.yaml` configuration.

## Overview

Inference configuration defines how to apply a trained model to new data. It specifies the input data, model paths, output location, and prediction threshold.

## Configuration Structure

```yaml
inference:
  enabled: true
  input_path: "path/to/new_data.parquet"
  output_path: "path/to/predictions.csv"
  model_path: "path/to/model.pkl"
  feature_engineering_path: "path/to/feature_engineering.pkl"
  threshold: 0.5
```

## Required Fields

| Parameter | Type | Description |
|-----------|------|-------------|
| `enabled` | boolean | Whether to execute inference |
| `input_path` | string | Path to input data (parquet or CSV) |
| `output_path` | string | Path where predictions will be saved |
| `model_path` | string | Path to trained model file |
| `feature_engineering_path` | string | Path to feature engineering pipeline |

## Optional Fields

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | float | `0.5` | Decision threshold (0.0 to 1.0) |

---

## How Inference Works

The inference process follows these steps:

1. **Load Input Data**: Reads the input dataset from `input_path`
2. **Apply Feature Engineering**: Loads the saved feature engineering pipeline and transforms the data
3. **Load Model**: Loads the trained model from `model_path`
4. **Generate Predictions**: Applies the model to the transformed data
5. **Apply Threshold**: Converts probability scores to binary predictions (fraud/non-fraud)
6. **Save Results**: Writes predictions to `output_path`

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
inference:
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
inference:
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

---

## Running Inference

### Using the CLI

```bash
energizados run inference
```

### Using the Python Script

```bash
python src/run/04_inference.py
```

---

## Configuration Examples

### Basic Inference

```yaml
inference:
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
inference:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.7  # Higher threshold = fewer false positives
```

Use a lower threshold to reduce false negatives (catch more fraud):

```yaml
inference:
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
inference:
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
inference:
  enabled: true
  input_path: "data/batch/january_2024.parquet"
  output_path: "predictions/january_2024.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
```

Then run for each month, updating paths accordingly.

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
inference:
  enabled: true
  input_path: "data/new_data.parquet"
  output_path: "predictions.csv"
  model_path: "output/train-20260317_1430/models/model.pkl"
  feature_engineering_path: "output/train-20260317_1430/models/feature_engineering.pkl"
  threshold: 0.5
  custom_class: "src.inference.custom_inference.CustomInference"
```

---

## Best Practices

### 1. Model Versioning

Keep track of which model was used for inference:

```yaml
inference:
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
energizados run inference_batch1

# Run inference on second batch
energizados run inference_batch2
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
