# Model Selection Guide

Choosing the right model is critical for building an effective fraud detection system. This guide helps you understand the tradeoffs between different model types and select the best one for your use case.

## Model Comparison

| Model | When to Use | Pros | Cons |
|-------|-------------|------|------|
| **LightGBM** | First choice for tabular data, large datasets, balanced performance | • Fast training (gradient boosting)<br>• Handles imbalanced data well with built-in support<br>• Memory efficient<br>• Good accuracy<br>• Less sensitive to hyperparameter tuning | • Less interpretable than linear models<br>• Requires categorical encoding (though it handles them well)<br>• May overfit on very small datasets |
| **CatBoost** | Many categorical features, need native categorical handling | • **Native categorical support** (no preprocessing needed)<br>• Robust to overfitting<br>• Good out-of-the-box performance<br>• Handles missing values automatically | • Slower training than LightGBM<br>• Larger memory footprint<br>• More parameters to tune |
| **XGBoost** | Sklearn-compatible ecosystems, existing XGBoost pipelines | • Sklearn API compatibility<br>• Large ecosystem and community<br>• Well-understood hyperparameters<br>• Good performance on tabular data | • Optional dependency (`pip install energizados[xgboost]`)<br>• Typically slower than LightGBM for same accuracy<br>• Higher memory usage |
| **Neural Network (NNModel)** | Large datasets, complex non-linear patterns | • Flexible architecture<br>• Can learn complex feature interactions<br>• Works well with high-dimensional data | • Requires more data to perform well<br>• Longer training time<br>• Harder to interpret<br>• More hyperparameters to tune |
| **LSTM** | When consumption sequence order matters, temporal patterns are critical | • Captures temporal dependencies in consumption history<br>• Learns patterns across time steps<br>• Good for sequential anomaly detection | • Most complex model<br>• Longest training time<br>• Requires sequential data preprocessing<br>• Needs more data<br>• Hardest to tune |

## Choosing Your First Model

### Start with LightGBM

**Why LightGBM is the default choice:**

1. **Fast iteration**: Train and evaluate models quickly to establish a baseline
2. **Handles imbalance well**: Built-in support for class weights and sampling
3. **Memory efficient**: Works well with large datasets (100k+ rows)
4. **Robust**: Less sensitive to hyperparameter choices than neural networks
5. **Good accuracy**: Typically achieves 0.75-0.85 AUC on fraud detection tasks

!!! tip
    For 90% of fraud detection use cases, LightGBM with proper feature engineering is sufficient. Don't overcomplicate things by jumping straight to neural networks or LSTMs.

### When to Try CatBoost

Consider CatBoost when:

- **You have many categorical features** (10+ categorical columns)
- **Categorical features have high cardinality** (100+ unique values)
- **You want minimal preprocessing** (no one-hot encoding needed)
- **You want robust performance without extensive tuning**

!!! example
    If your dataset has 15+ categorical features like `actividad`, `tipo_tarifa`, `zona`, `nivel_tension`, `material_instalacion`, etc., CatBoost's native categorical handling can save significant preprocessing time and often outperforms LightGBM.

### When to Try XGBoost

Consider XGBoost when:

- **You already have XGBoost pipelines** you want to plug in to the framework
- **You need sklearn API compatibility** for downstream tooling (GridSearch, SHAP, etc.)
- **You want a second boosting benchmark** alongside LightGBM

!!! note
    XGBoost requires an optional dependency: `pip install energizados[xgboost]`. In terms of raw accuracy on fraud detection, LightGBM and CatBoost typically match or beat XGBoost with faster training. Prefer XGBoost when ecosystem compatibility outweighs raw performance.

### Using Isolation Forest as a Feature (`if_score`)

Isolation Forest is available as a **global_transformer** (not a model type). Use `if_score` in `feature_engineering.preprocessing.global_transformers` to generate an anomaly score column that supervised models can use as input:

```yaml
global_transformers:
  - if_score:
      contamination_from_target: true  # uses y.mean() as contamination
```

**Benefits**:
- Produces a continuous anomaly score (higher = more anomalous)
- Complements supervised models with unsupervised signal
- Configurable `contamination_from_target` to leverage target labels

!!! warning
     The `isolation_forest` model type has been removed. Isolation Forest is now exclusively a feature engineering transformer (`if_score`), not a standalone model. It cannot be used in the `models:` section of `train.yaml`.

### When to Try Neural Networks

Consider Neural Networks when:

- **You have a large dataset** (100k+ samples, 50+ features)
- **You need to capture complex non-linear interactions**
- **Gradient boosting has plateaued** (AUC stuck at ~0.80-0.82)
- **You have deep learning expertise** to tune architecture

!!! warning
    Neural networks require significantly more data and tuning to outperform well-tuned LightGBM. Only use them if you have deep learning experience and have exhausted simpler options.

### When to Try LSTM

Consider LSTM when:

- **Consumption sequence order is critical** (temporal patterns matter)
- **You have long consumption histories** (12+ months, preferably 24+)
- **Sudden changes in consumption are fraud signals**
- **You want to model sequential dependencies**

!!! tip
    LSTM is most effective when the fraud signal is in the **sequence itself**, not just in aggregated statistics. If mean/std/sum of consumption captures most of the signal, LSTM may not provide significant improvement over LightGBM.

## Model Selection Workflow

### Step 1: Establish a Baseline

1. **Start with LightGBM** using the default configuration from `energizados init`
2. **Run with undersampling** to handle class imbalance
3. **Record baseline metrics**: AUC, precision, recall, F1
4. **Review feature importance**: Identify top predictive features

!!! example
    Baseline results might look like:
    - AUC: 0.78
    - Precision: 0.22
    - Recall: 0.70
    - F1: 0.34

### Step 2: Iterate on Single Models

2.1 **Improve LightGBM**:
   - Tune hyperparameters (`num_leaves`, `learning_rate`, `min_child_samples`)
   - Add more features (consumption volatility, sudden drops, geographic features)
    - Try different sampling strategies (over vs undersample vs smotetomek)

2.2 **Try CatBoost**:
   - Keep the same features and sampling strategy
   - Compare AUC and training time
   - If CatBoost outperforms LightGBM by >0.02 AUC, consider switching

2.3 **Compare results**:
   - Use the run index (`output/index.html`) to compare runs
   - Focus on AUC and the metric that matters most to your business

!!! tip
    If both LightGBM and CatBoost achieve similar AUC (±0.01), choose the faster one (usually LightGBM) for production.

### Step 3: Consider Ensembles

If **both LightGBM and CatBoost achieve AUC > 0.80**, consider an ensemble:

- **Stacking**: Often improves AUC by 0.02-0.05
- **Soft voting**: Simpler, but typically smaller gains (0.01-0.03)

See [Ensemble Models](ensemble-models.md) for details.

### Step 4: Advanced Models (Optional)

If you've exhausted ensemble options and still need better performance:

1. **Neural Network**: If you have 100k+ samples and complex feature interactions
2. **LSTM**: If temporal patterns in consumption history are critical
3. **Custom models**: Implement domain-specific models in `src/models/`

!!! warning
    Neural networks and LSTMs require significant expertise to tune properly. Only proceed if you have deep learning experience or have plateaued at ~0.82-0.85 AUC with ensembles.

## Business-Driven Model Selection

The "best" model depends on your business constraints:

### High-Precision Use Case

**Scenario**: Limited inspection capacity, high cost per inspection

**Goal**: Minimize false positives (wasted inspections)

**Choose**: Model with higher precision, even if recall is lower

**Approach**:
1. Train LightGBM and CatBoost
2. Increase decision threshold (e.g., 0.6-0.7) to improve precision
3. Compare which model maintains better recall at high precision
4. Use precision-recall curve in evaluation report to choose optimal threshold

!!! example
    If you can only afford 500 inspections per month:
    - LightGBM at threshold 0.65: precision 0.35, recall 0.55
    - CatBoost at threshold 0.65: precision 0.38, recall 0.52

    Choose CatBoost (higher precision = fewer wasted inspections).

### High-Recall Use Case

**Scenario**: High revenue loss from undetected fraud, many inspectors available

**Goal**: Catch as many fraudsters as possible (minimize false negatives)

**Choose**: Model with higher recall, even if precision is lower

**Approach**:
1. Train LightGBM and CatBoost
2. Decrease decision threshold (e.g., 0.3-0.4) to improve recall
3. Compare which model maintains better precision at high recall
4. Use cumulative gains chart to estimate fraudsters caught at top X%

!!! example
    If catching fraudsters is the priority:
    - LightGBM at threshold 0.35: precision 0.18, recall 0.85
    - CatBoost at threshold 0.35: precision 0.20, recall 0.80

    Choose LightGBM (higher recall = fewer fraudsters escape).

### Balanced Use Case

**Scenario**: Moderate inspection capacity, moderate revenue loss

**Goal**: Balance precision and recall (maximize F1 or expected profit)

**Choose**: Model with highest F1 or business-calibrated expected value

**Approach**:
1. Train LightGBM, CatBoost, and optionally ensemble
2. Use interactive threshold slider to find optimal balance
3. Calculate expected profit: `(TP × savings_per_fraudster) - (FP × cost_per_inspection)`
4. Choose model/threshold that maximizes expected profit

## Practical Recommendations

### For Small Teams / Quick Wins

1. **Start with LightGBM** (default in `energizados init`)
2. **Focus on feature engineering** (biggest performance lever)
3. **Tune hyperparameters** using randomized search (built-in)
4. **Skip ensemble and neural networks** unless you hit a plateau

### For Large Teams / Production Systems

1. **Train LightGBM and CatBoost in parallel**
2. **Compare AUC and business metrics**
3. **Build ensemble if both achieve AUC > 0.80**
4. **Consider LSTM if temporal patterns are strong**
5. **Deploy A/B tests to measure real-world impact**

### For Research / Benchmarking

1. **Try all model types** (LightGBM, CatBoost, NN, LSTM)
2. **Use feature selection to reduce overfitting**
3. **Compare with simple baselines** (constant consumption, trend detection)
4. **Document which features are most important per model**

## Common Pitfalls

### Over-Engineering

**Problem**: Jumping straight to neural networks without a proper baseline.

**Solution**: Always start with LightGBM. Only move to complex models after establishing a solid baseline.

### Ignoring Business Constraints

**Problem**: Optimizing for AUC alone without considering precision/recall tradeoffs.

**Solution**: Identify your business constraint (inspection capacity, revenue loss) and choose metrics accordingly.

### Neglecting Feature Engineering

**Problem**: Expecting complex models to fix poor features.

**Solution**: 80% of performance comes from features. Focus on feature engineering before model selection.

### Not Comparing Properly

**Problem**: Comparing models on different datasets, splits, or thresholds.

**Solution**: Always compare models on the same test split and threshold, or use the run index to ensure fair comparison.

## Next Steps

- [Ensemble Models](ensemble-models.md) - Combine multiple models for better performance
- [End-to-End Example](end-to-end-example.md) - Hands-on tutorial
- [Understanding Results](../user-guide/understanding-results.md) - Interpreting evaluation metrics
- [Configuration Guide](../user-guide/configuration/) - Detailed configuration options
