# Understanding Results

After running a training pipeline, Energizados generates comprehensive evaluation reports in the `output/` directory. This guide explains how to interpret these results and use them to improve your fraud detection model.

## Where to Find Results

Each training run creates a timestamped directory under `output/`:

```
output/
├── index.html                           # Run comparison dashboard
└── train-20240315_1430/                 # Individual run directory
    ├── models/
    │   ├── feature_engineering.pkl     # Trained feature pipeline
    │   ├── model.pkl                   # Trained model (or ensemble.pkl)
    │   ├── lgbm/                       # Base model subdirectories (ensemble)
    │   │   └── model.pkl
    │   └── cat/
    │       └── model.pkl
    ├── reports/
    │   └── evaluation/
    │       ├── evaluation_report.html  # Interactive evaluation report
    │       ├── evaluation_report.json  # Machine-readable metrics
    │       ├── confusion_matrix.png
    │       ├── roc_curve.png
    │       └── cumulative_gains.png
    └── config/
        └── train.yaml                 # Configuration used for this run
```

## The Run Index (`output/index.html`)

The run index provides a summary table of all training runs with key metrics:

- **Run ID**: Timestamp identifier (e.g., `20240315_1430`)
- **Model Type**: LightGBM, CatBoost, Neural Network, LSTM, or Ensemble
- **AUC**: Area Under the ROC Curve
- **Precision**: Positive Predictive Value
- **Recall**: True Positive Rate
- **F1 Score**: Harmonic mean of precision and recall
- **Threshold**: Decision threshold used for classification

!!! tip
    Use the run index to compare different hyperparameter settings, sampling strategies, or model types. Click any row to view the detailed report for that run.

## Evaluation Metrics Explained

### AUC-ROC (Area Under ROC Curve)

**What it measures**: How well the model distinguishes between fraudulent and non-fraudulent customers.

**Interpretation**:
- **0.5**: Random guessing (no discrimination)
- **0.6-0.7**: Poor discrimination
- **0.7-0.8**: Acceptable discrimination
- **0.8-0.9**: Excellent discrimination
- **0.9-1.0**: Outstanding discrimination (suspicious—possible overfitting or data leakage)

For fraud detection, an AUC of **0.75-0.85** is typically considered good.

!!! example
    An AUC of 0.82 means that if you randomly pick one fraudulent customer and one non-fraudulent customer, the model will assign a higher fraud probability to the fraudulent customer 82% of the time.

### Precision vs Recall Tradeoff

In fraud detection, these metrics have a crucial business interpretation:

**Precision** (Positive Predictive Value):
- **Question**: "Of all customers flagged as fraudulent, how many are actually fraudulent?"
- **Formula**: TP / (TP + FP)
- **High precision** means fewer false alarms (inspectors' time is wasted less often)

**Recall** (True Positive Rate):
- **Question**: "Of all actual fraudsters, how many did we catch?"
- **Formula**: TP / (TP + FN)
- **High recall** means fewer fraudsters escape detection (less revenue loss)

!!! example
    If precision is 0.30 and recall is 0.75:
    - **30%** of flagged customers are actually fraudsters (7 out of 10 inspections are wasted)
    - **75%** of actual fraudsters are caught (1 in 4 fraudsters escapes)

This is a classic tradeoff: **optimizing for precision reduces waste, optimizing for recall reduces revenue loss**. The right balance depends on your business priorities.

### F1 Score

**What it measures**: Harmonic mean of precision and recall—a single metric that balances both.

**When to use it**: When you need a balanced view or when precision and recall are equally important. However, in fraud detection, you typically want to **optimize specifically for your business constraint** (inspection capacity vs revenue loss), not just maximize F1.

### Confusion Matrix

The confusion matrix breaks down predictions into four quadrants:

|                     | Predicted Non-Fraud | Predicted Fraud |
|---------------------|---------------------|-----------------|
| **Actual Non-Fraud**| True Negative (TN)  | False Positive (FP) |
| **Actual Fraud**    | False Negative (FN) | True Positive (TP) |

**In fraud detection context**:

- **True Negative (TN)**: Correctly identified legitimate customer
- **False Positive (FP)**: Wasted inspection (false alarm)
- **False Negative (FN)**: Missed fraudster (revenue loss)
- **True Positive (TP)**: Caught fraudster (successful inspection)

!!! tip
    The confusion matrix is most useful when combined with business costs. If an inspection costs $50 and catching fraud saves $500, you can calculate the expected profit of any threshold.

### Cumulative Gains Chart

**What it shows**: How many fraudsters you catch by inspecting the top X% of customers (ordered by fraud probability).

**How to read it**:
- **X-axis**: Percentage of customers inspected (ordered by risk score)
- **Y-axis**: Percentage of fraudsters caught
- **Diagonal line**: Random selection baseline

!!! example
    If the curve shows that by inspecting the top 20% of customers, you catch 60% of all fraudsters, this means you achieve 3x the random baseline (random would catch only 20%).

**Practical use**: Use this chart to determine your inspection capacity. If you have capacity for 1,000 inspections and have 10,000 customers, the gains chart tells you what percentage of fraudsters you'll catch by inspecting the top 10%.

## Threshold Calibration

The default threshold is 0.5, but **this is rarely optimal for fraud detection** due to class imbalance (typically 5-10% fraudsters).

### Why Threshold Matters

- **Lower threshold** (e.g., 0.3): Flag more customers as fraudulent → higher recall, lower precision → more inspections, catch more fraudsters
- **Higher threshold** (e.g., 0.7): Flag fewer customers as fraudulent → lower recall, higher precision → fewer inspections, catch fewer fraudsters

### How to Choose the Right Threshold

1. **Determine your constraint**: What limits you?
   - **Inspection capacity**: Max number of inspections per month
   - **Precision requirement**: Minimum acceptable precision (e.g., avoid wasting more than 50% of inspections)

2. **Use the precision-recall curve** (in the evaluation report):
   - Find the threshold that meets your constraint
   - Example: If you need ≥30% precision, find where precision crosses 0.30 and use that threshold

3. **Validate with business metrics**:
   - Calculate expected value: `(TP × savings_per_fraudster) - (FP × cost_per_inspection)`
   - Choose threshold that maximizes expected profit

!!! tip
    The evaluation report includes interactive threshold sliders that update all metrics in real-time. Use this to find the optimal threshold for your business context.

## Feature Importance

Energizados provides feature importance plots:

### Feature Importance Plots

**What they show**: Ranked list of features by importance (varies by model type):
- **LightGBM/CatBoost**: Gain or split-based importance

!!! warning
    Correlated features can inflate importance scores. If two features are highly correlated (e.g., `mean_consumption_6m` and `mean_consumption_12m`), their individual importance scores may be unreliable.

## Comparing Runs

### Using the Run Index

1. Open `output/index.html`
2. Sort by the metric that matters most to your business (e.g., precision, recall, AUC)
3. Click the best-performing row to view its detailed report

### Key Comparison Points

- **Model type**: Did LightGBM outperform CatBoost? Did ensemble improve over single models?
- **Sampling**: Did undersampling vs oversampling affect results?
- **Hyperparameters**: Which hyperparameter settings produced the best results?
- **Threshold**: How did threshold calibration affect the tradeoff?

!!! example
    You might find that:
- LightGBM with undersampling gives AUC 0.82, precision 0.25, recall 0.80
- CatBoost with no sampling gives AUC 0.80, precision 0.30, recall 0.70
- Ensemble of both gives AUC 0.83, precision 0.28, recall 0.78

If inspection capacity is limited (need high precision), choose CatBoost. If catching more fraudsters is the priority (need high recall), choose LightGBM or the ensemble.

## Common Issues and Solutions

### Low Precision (< 20%)

**Problem**: Most flagged customers are not actually fraudulent—too many wasted inspections.

**Possible causes**:
- Threshold too low
- Model not well-calibrated
- Poor features (weak predictive signal)

**Solutions**:
- Increase threshold to improve precision
- Add stronger predictive features (e.g., inspection history, geographic hotspots)
- Use ensemble methods to combine multiple models

### Low Recall (< 50%)

**Problem**: Most fraudsters escape detection—significant revenue loss.

**Possible causes**:
- Threshold too high
- Model overfitting to training data
- Missing key fraud signals in features

**Solutions**:
- Decrease threshold to catch more fraudsters
- Add regularization to prevent overfitting
- Engineer domain-specific features (e.g., sudden consumption drops, constant consumption)

### Overfitting (Train AUC >> Test AUC)

**Problem**: Model performs much better on training data than test data.

**Possible causes**:
- Too many features relative to sample size
- Complex model with insufficient regularization
- Data leakage (features that directly encode target)

**Solutions**:
- Use feature selection (Boruta, correlation-based)
- Increase regularization (e.g., `max_depth`, `min_child_samples` in LightGBM)
- Investigate and remove potentially leaking features

### Data Leakage (AUC > 0.95 or sudden spikes in importance)

**Problem**: Features contain information about the target that wouldn't be available in production.

**Warning signs**:
- AUC > 0.95 (unrealistically high for fraud detection)
- Single feature with 50%+ of total importance
- Features named "inspected_fraud", "fraud_detected", etc.

**Solution**:
- Remove leaking features
- Review feature importance for suspicious patterns
- Re-train with only features available at prediction time

## Next Steps

- [EDA Module](eda.md) - Understanding your data before training
- [Model Selection Guide](../tutorials/model-selection-guide.md) - Choosing the right model type
- [Advanced Evaluation](../advanced/contributing.md) - Defining custom evaluation metrics
