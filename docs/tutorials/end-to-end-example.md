# End-to-End Example

This tutorial walks you through building a complete fraud detection pipeline using Energizados. We'll use the sample dataset included with new projects created via `energizados init`.

!!! tip
    This tutorial assumes you have already installed Energizados. If not, see [Getting Started](../getting-started/installation.md).

## Step 1: Initialize Project

Create a new project with the sample dataset:

```bash
energizados init fraud_detection
cd fraud_detection
```

This creates a project structure with:

```
fraud_detection/
├── config/
│   ├── etl.yaml            # ETL configuration
│   ├── train.yaml          # Training configuration
│   ├── infer.yaml          # Inference configuration
│   └── eda.yaml            # EDA configuration
├── data/
│   ├── raw/
│   │   └── sample_dataset.parquet    # Sample data (42,500 rows)
│   ├── processed/                      # ETL outputs
│   └── temp/
│       └── splits/                     # Train/val/test splits
├── output/                  # Training run outputs
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   ├── inference/
│   └── run/               # Execution scripts
└── notebooks/
    └── example_notebook.ipynb
```

## Step 2: Explore Sample Data

Let's briefly examine the sample dataset:

```bash
# Load Python and inspect the data
python << 'EOF'
import pandas as pd

df = pd.read_parquet("data/raw/sample_dataset.parquet")

print(f"Dataset shape: {df.shape}")
print(f"\nColumns: {list(df.columns)}")
print(f"\nTarget distribution:")
print(df['target'].value_counts(normalize=True))
print(f"\nTarget count:")
print(df['target'].value_counts())
EOF
```

**Expected output**:
```
Dataset shape: (42500, 20)

Columns: ['index', '12_anterior', '11_anterior', '10_anterior', '9_anterior',
          '8_anterior', '7_anterior', '6_anterior', '5_anterior', '4_anterior',
          '3_anterior', '2_anterior', '1_anterior', 'zona', 'actividad',
          'tipo_tarifa', 'nivel_tension', 'material_instalacion',
          'fecha_inspeccion', 'target']

Target distribution:
0    0.942118
1    0.057882
Name: target, dtype: float64

Target count:
0    40010
1     2490
Name: target, dtype: int64
```

**Dataset characteristics**:

- **42,500 customers** with 20 columns (one is `index`, a parquet export artifact that is not a model feature — 19 are meaningful variables)
- **5.8% fraud rate** (2,490 fraudsters, 40,010 legitimate customers)
- **12 monthly consumption columns** (`12_anterior` through `1_anterior`)
- **5 categorical features**: `actividad`, `tipo_tarifa`, `nivel_tension`, `material_instalacion`, `zona`
- **Target**: `target` (1 = fraudulent, 0 = legitimate)
- **Date column**: `fecha_inspeccion` (inspection date)

## Step 3: Run Sample ETL

The sample ETL simply removes rows with null values:

```bash
energizados run etl
```

**Expected output**:
```
Running ETL: sample
Loading data from data/raw/sample_dataset.parquet
Removing rows with NULL values
Original rows: 42500
After removing NULLs: 42497
Saving to data/processed/sample_dataset.parquet

ETL pipeline completed successfully in 0.5 seconds
```

The processed data is now available at `data/processed/sample_dataset.parquet`.

!!! info
    The sample ETL is intentionally simple. In practice, you'd configure more complex ETLs with data merging, filtering, transformations, and dependencies.

## Step 4: Run EDA (Optional but Recommended)

Before training, it's good practice to explore the data:

```bash
energizados run eda
```

This generates an interactive HTML report at `output/eda/eda_report.html`. Open it in your browser to see:

- Data quality metrics (missing values, duplicates, constants)
- Column distributions (histograms, boxplots, value counts)
- Target analysis (class balance, temporal rate)
- Feature importance rankings (IV, KS, Cramér's V)

!!! tip
    The EDA report helps you identify data quality issues and understand which features are most predictive before training.

## Step 5: Configure and Run Training

The default `train.yaml` is already configured for LightGBM training. Let's review the key sections:

```yaml
# config/train.yaml
train:
  enabled: true
  input_path: "data/processed/sample_dataset.parquet"
  target_column: "target"

  split:
    method: "time_series"
    date_column: "fecha_inspeccion"
    train_period: ["2010-01-01", "2017-08-01"]
    val_period: ["2017-09-01", "2017-12-31"]
    test_period: ["2018-01-01"]

  feature_engineering:
    enabled: true
    preprocessing:
      enabled: true
      columns:
        actividad:
          - cardinality_reducer: { threshold: 0.001 }
          - to_dummy: {}
        tipo_tarifa:
          - cardinality_reducer: { threshold: 0.001 }
          - target_encoding: { w: 20 }
        zona:
          - ordinal_encoding: {}
        nivel_tension:
          - ordinal_encoding: {}
        material_instalacion:
          - target_encoding: { w: 10 }
      global_transformers:
        - extra_vars: { num_periodos: 12 }

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
```

**Key points**:
- **Time series split**: Train on 2010-2017 data, validate on 2017 Q4, test on 2018+
- **Feature engineering**: One-hot encoding for high-cardinality features, target encoding for medium-cardinality, ordinal encoding for low-cardinality
- **Global transformer**: Statistical features from 12-month consumption window
- **LightGBM with undersampling**: Balances the 94% vs 6% class imbalance
- **Hyperparameter search**: 60 iterations of random search with 3-fold CV

Now run the training:

```bash
energizados run train
```

**Expected output** (abbreviated):
```
Loading data from data/processed/sample_dataset.parquet
Splitting data using time_series method
Train period: 2010-01-01 to 2017-08-01 (39231 rows)
Val period: 2017-09-01 to 2017-12-31 (2266 rows)
Test period: 2018-01-01 onwards (1000 rows)

Running feature engineering...
Preprocessing categorical columns...
Generating global transformers...
Feature engineering completed in 2.3 seconds

Training model: lightgbm
Performing hyperparameter search (60 iterations)...
Best hyperparameters found:
  num_leaves: 47
  learning_rate: 0.038
  n_estimators: 847
  min_child_samples: 15

Training final model with best hyperparameters...
Training completed in 45.2 seconds

Generating evaluation report...
AUC: 0.823
Precision: 0.28
Recall: 0.76
F1 Score: 0.41

Report saved to output/train-20240315_1430/reports/evaluation/evaluation_report.html
```

## Step 6: Interpret Results

### View the Run Index

Open `output/index.html` in your browser to see all runs. For a single run, you'll see:

| Run ID | Model | AUC | Precision | Recall | F1 | Threshold |
|--------|-------|-----|-----------|--------|-----|-----------|
| 20240315_1430 | lightgbm | 0.823 | 0.28 | 0.76 | 0.41 | 0.5 |

### View Detailed Report

Open `output/train-20240315_1430/reports/evaluation/evaluation_report.html` to see:

- **ROC Curve**: Shows the tradeoff between TPR and FPR at different thresholds
- **Precision-Recall Curve**: Use this to choose an optimal threshold
- **Confusion Matrix**: Shows TP, FP, FN, TN counts
- **Cumulative Gains Chart**: Shows how many fraudsters you catch by inspecting top X% of customers
- **Feature Importance**: SHAP values or model-specific importance
- **Interactive threshold slider**: Adjust threshold and see metrics update in real-time

### Understanding Our Results

For this sample dataset:

- **AUC = 0.823**: Good discrimination—model can distinguish fraudsters from legitimate customers 82% of the time
- **Precision = 0.28**: Only 28% of flagged customers are actual fraudsters—72% of inspections are wasted
- **Recall = 0.76**: We catch 76% of fraudsters—24% escape detection
- **F1 = 0.41**: Balanced score reflecting the precision-recall tradeoff

!!! example "Business interpretation"
    If you have 1,000 inspections per month and flag 1,000 customers with this model:
    - **280 are actual fraudsters** (caught)
    - **720 are legitimate** (wasted inspections)
    - **940 fraudsters remain undetected** (assuming 2,490 total fraudsters in the dataset)

    To improve precision (reduce waste), increase the threshold. To improve recall (catch more fraudsters), decrease the threshold.

### Calibrate Threshold

Use the interactive threshold slider in the evaluation report to find the optimal threshold for your business needs:

- **Need higher precision?** Increase threshold (e.g., to 0.65) → fewer, higher-confidence predictions
- **Need higher recall?** Decrease threshold (e.g., to 0.35) → catch more fraudsters, accept more waste

## Step 7: Run Inference on New Data

Now that you have a trained model, use it to predict on new data:

### Prepare New Data

Create a new CSV or parquet file with the same columns as the training data (except `target`). For example:

```bash
# Create a sample inference file
python << 'EOF'
import pandas as pd
import numpy as np

# Load the training data to get column structure
train_df = pd.read_parquet("data/processed/sample_dataset.parquet")

# Create 10 mock customers
new_data = train_df.drop(columns=['target']).sample(n=10, random_state=42)
new_data['fecha_inspeccion'] = '2024-01-15'

# Save for inference
new_data.to_parquet("data/new_customers.parquet", index=False)
print(f"Created {len(new_data)} mock customers for inference")
print(f"\nColumns: {list(new_data.columns)}")
EOF
```

### Configure Inference

The default `infer.yaml` is already configured:

```yaml
# config/infer.yaml
infer:
  enabled: true
  input_path: "data/new_customers.parquet"
  model_path: "output/train-20240315_1430/models/model.pkl"
  feature_engineering_path: "output/train-20240315_1430/models/feature_engineering.pkl"
  threshold: 0.5
  output_predictions_path: "output/inference_predictions.parquet"
```

!!! note
    You may need to update `model_path` and `feature_engineering_path` to match your actual run ID (e.g., `train-20240315_1430`).

### Run Inference

```bash
energizados run infer
```

**Expected output**:
```
Loading feature engineering pipeline from output/train-20240315_1430/models/feature_engineering.pkl
Loading model from output/train-20240315_1430/models/model.pkl
Running inference on 10 samples
Inference completed in 0.3 seconds
Predictions saved to output/inference_predictions.parquet
```

### View Predictions

```bash
python << 'EOF'
import pandas as pd

preds = pd.read_parquet("output/inference_predictions.parquet")
print(preds[['probability', 'prediction']].sort_values('probability', ascending=False))
EOF
```

**Expected output**:
```
      probability  prediction
7               0.7842                 1
2               0.6521                 1
5               0.4123                 0
9               0.3456                 0
1               0.2891                 0
0               0.2134                 0
3               0.1567                 0
4               0.0892                 0
6               0.0456                 0
8               0.0234                 0
```

The predictions include:
- **probability**: Model's confidence score (0-1)
- **prediction**: Binary prediction (1 = fraud, 0 = legitimate) based on threshold

## Step 8: What to Do Next

Now that you've completed your first end-to-end run, here are ways to improve your fraud detection system:

### Improve Model Performance

1. **Feature Engineering**:
   - Add domain-specific features (e.g., consumption volatility, sudden drops, constant consumption)
   - Use time-based features (day of week, month of year, seasonal patterns)
   - Add geographic features (distance to known fraud hotspots, cluster membership)

2. **Try Different Models**:
   - [CatBoost](../tutorials/model-selection-guide.md): Better with categorical features
   - [Neural Networks](../tutorials/model-selection-guide.md): Capture complex non-linear patterns
   - [LSTM](../tutorials/model-selection-guide.md): Model sequential patterns in consumption history
   - [Ensemble Models](../tutorials/ensemble-models.md): Combine multiple models for better performance

3. **Hyperparameter Tuning**:
   - Increase `n_iter` in `hyperparam_search` (e.g., to 200)
   - Use Bayesian optimization instead of random search
   - Tune preprocessing parameters (e.g., `threshold` in `cardinality_reducer`)

4. **Feature Selection**:
   - Enable `feature_selection` to remove weak features
   - Try different methods (Boruta, correlation, constant)

### Optimize for Business Goals

1. **Threshold Calibration**:
   - Use the interactive threshold slider in the evaluation report
   - Choose threshold that maximizes business value (considering inspection cost and fraud recovery value)

2. **Custom Metrics**:
   - Define business-specific metrics (e.g., expected profit per inspection)
   - See [Advanced Metrics](../advanced/contributing.md) for implementation

3. **Segmentation**:
   - Build separate models for different customer segments (e.g., residential vs commercial)
   - Use [EDA segmentation](../user-guide/eda.md#phase-6-segmentation-analysis-optional) to identify meaningful segments

### Productionize

1. **Automated Pipeline**:
   - Use the generated scripts in `src/run/` for scheduled execution
   - Integrate with your CI/CD pipeline

2. **Model Monitoring**:
   - Track performance metrics over time
   - Detect data drift and model degradation
   - Set up alerts for performance drops

3. **Scalability**:
   - Use distributed computing for large datasets
   - Optimize inference for real-time predictions

## Summary

In this tutorial, you:

1. ✅ Initialized a new project with sample data
2. ✅ Ran the sample ETL to process the data
3. ✅ (Optional) Ran EDA to understand the data
4. ✅ Trained a LightGBM model with undersampling and hyperparameter search
5. ✅ Interpreted the results (AUC, precision, recall, confusion matrix)
6. ✅ Ran inference on new customers
7. ✅ Identified next steps for improvement

## Next Tutorials

- [Model Selection Guide](model-selection-guide.md) - Choose the right model for your use case
- [Ensemble Models](ensemble-models.md) - Combine multiple models for better performance
- [Advanced Configuration](../user-guide/configuration/etl.md) - Deep dive into configuration options
- [Understanding Results](../user-guide/understanding-results.md) - Master result interpretation
