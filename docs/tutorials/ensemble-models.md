# Ensemble Models

Ensemble models combine multiple base models to produce more accurate and robust predictions. In fraud detection, ensembles typically improve AUC by 2-5 percentage points compared to single models.

## Why Use Ensembles?

### The Principle

Ensembles work on the principle that **multiple weak learners can be combined to form a strong learner**. Each base model makes different errors, and by combining them, we reduce the overall error rate.

### Benefits in Fraud Detection

1. **Reduced Variance**: Combining models smooths out individual model fluctuations
2. **Reduced Overfitting**: Less likely to overfit to training data
3. **Improved Accuracy**: Typically +0.02 to +0.05 AUC improvement
4. **Robustness**: Less sensitive to noisy data or outliers
5. **Diverse Perspectives**: Different model types capture different patterns

!!! example
    If LightGBM catches fraudsters based on consumption patterns, and CatBoost catches fraudsters based on categorical features (tariff type, activity), the ensemble can catch fraudsters identified by either model.

## Ensemble Methods

### Soft Voting

**How it works**: Weighted average of base model probabilities.

**Configuration**:
```yaml
models:
  - name: "lgbm"
    type: "lightgbm"
    # ... configuration
  - name: "cat"
    type: "catboost"
    # ... configuration

ensemble:
  method: "soft_voting"
  # No meta_learner needed for soft voting
```

**When to use**:
- Base models have similar performance (AUC within ±0.02 of each other)
- You want a simple, fast ensemble
- You want to assign different weights to models

**Pros**:
- Simple to implement and understand
- Fast (no additional training for meta-learner)
- Can weight models differently (e.g., give more weight to better model)

**Cons**:
- Limited improvement compared to stacking
- No learning—just averages existing predictions

**Example with weights**:
```yaml
ensemble:
  method: "soft_voting"
  weights: [0.6, 0.4]  # LightGBM has 60% weight, CatBoost 40%
```

### Stacking

**How it works**: Train a meta-learner on base model predictions. The meta-learner learns which base model to trust for each prediction.

**Configuration**:
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

ensemble:
  method: "stacking"
  meta_learner:
    type: "logistic_regression"
    params:
      C: 1.0
      max_iter: 1000
  use_val_as_oof: true
  cv: 5
```

**When to use**:
- Base models have diverse strengths (different feature focus)
- You want maximum performance
- You have enough data for meta-learner training

**Pros**:
- Typically outperforms soft voting (+0.01 to +0.03 AUC)
- Learns optimal combination of base models
- Can capture complex interactions between models

**Cons**:
- More complex to implement
- Requires training meta-learner (additional time)
- Risk of overfitting if not careful

**Meta-learner options**:
- `logistic_regression`: Simple, interpretable, good baseline (default)
- `lightgbm`: Can capture non-linear patterns
- `catboost`: Robust to overfitting
- Custom models: Implement in `src/models/`

## Blending vs. Proper OOF

The `use_val_as_oof` parameter controls how the meta-learner is trained:

### Blending (`use_val_as_oof: true`)

**How it works**: Use validation set predictions as training data for the meta-learner.

**Pros**:
- **Fast**: Only one training pass for base models
- **Simple**: No cross-validation needed

**Cons**:
- **Slight data leakage**: Validation set is used for both early stopping AND meta-learner training
- **Less data for meta-learner**: Only validation set (typically 10-20% of data)

!!! warning
    Blending introduces minor data leakage because the validation set is used for both early stopping during base model training AND meta-learner training. However, this is often acceptable for production use.

### Proper OOF (`use_val_as_oof: false`)

**How it works**: Generate out-of-fold predictions using K-fold cross-validation. Each fold's model predicts on the out-of-fold samples.

**Pros**:
- **No data leakage**: Each prediction is from a model that didn't see that sample during training
- **More data for meta-learner**: Full training set available

**Cons**:
- **Slow**: Requires K training passes for each base model (default: 5)
- **More complex**: Need to handle K-fold splits and model re-creation

!!! tip
    Use **blending (`use_val_as_oof: true`)** for fast iteration and production use. Use **proper OOF** for final model validation or when publishing results.

## Complete Ensemble Example

### Configuration

Here's a complete `train.yaml` with LightGBM + CatBoost ensemble:

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

  # Two base models
  models:
    - name: "lgbm"
      type: "lightgbm"
      sampling:
        method: "undersample"
        threshold: 0.5
      hyperparams:
        num_leaves: 31
        learning_rate: 0.05
        n_estimators: 500
        min_child_samples: 20
      hyperparam_search:
        enabled: false

    - name: "cat"
      type: "catboost"
      sampling:
        method: "undersample"
        threshold: 0.5
      hyperparams:
        iterations: 300
        depth: 6
        learning_rate: 0.1
      hyperparam_search:
        enabled: false

  # Ensemble configuration
  ensemble:
    method: "stacking"
    meta_learner:
      type: "logistic_regression"
      params:
        C: 1.0
        max_iter: 1000
        class_weight: "balanced"
    use_val_as_oof: true  # Use blending (fast)
    cv: 5  # Only used if use_val_as_oof: false

  evaluation:
    enabled: true
    threshold: 0.5
    metrics: [auc, precision, recall, f1, confusion_matrix, cumulative_gains]
    generate_plots: true
    generate_html_report: true
```

### Training the Ensemble

Run the ensemble training:

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
Feature engineering completed in 2.3 seconds

Training base model: lgbm (lightgbm)
Training completed in 35.2 seconds
Validation AUC: 0.821

Training base model: cat (catboost)
Training completed in 42.7 seconds
Validation AUC: 0.819

Training ensemble (stacking) with 2 base models...
Stacking: using val set as blending data for meta-learner.
Meta-learner type: logistic_regression
Meta-learner fitted.

Evaluation:
AUC: 0.834
Precision: 0.29
Recall: 0.77
F1 Score: 0.42

Ensemble description: Ensemble (lightgbm, catboost)
```

Notice how the ensemble AUC (0.834) is higher than either base model individually (0.821, 0.819).

## Output Structure

### Single Model

When you train a single model, the output is:
```
output/train-20240315_1430/
└── models/
    ├── feature_engineering.pkl
    └── model.pkl  # Single model file
```

### Ensemble

When you train an ensemble, the output is:
```
output/train-20240315_1430/
└── models/
    ├── feature_engineering.pkl
    ├── lgbm/           # Base model 1 subdirectory
    │   └── model.pkl
    ├── cat/            # Base model 2 subdirectory
    │   └── model.pkl
    └── ensemble.pkl    # Ensemble model file
```

Each base model is saved in its own subdirectory (named by the `name` field in `models` list). The ensemble.pkl contains the combination logic and meta-learner.

## Inference with Ensemble

Inference automatically uses the ensemble if `ensemble.pkl` exists. The inference configuration doesn't need to change:

```yaml
# config/infer.yaml
infer:
  enabled: true
  input_path: "data/new_customers.parquet"
  model_path: "output/train-20240315_1430/models/ensemble.pkl"  # Points to ensemble
  feature_engineering_path: "output/train-20240315_1430/models/feature_engineering.pkl"
  threshold: 0.5
  output_path: "output/inference_predictions.parquet"
```

Run inference:
```bash
energizados run inference
```

The inference automatically:
1. Loads the ensemble.pkl
2. Loads each base model from their subdirectories
3. Loads the meta-learner (for stacking)
4. Runs predictions through the ensemble

## Ensemble Strategies

### Strategy 1: LightGBM + CatBoost (Recommended)

**When to use**: Your primary baseline models are LightGBM and CatBoost

**Why**: Both are gradient boosting models but have different implementations and strengths. Combining them often yields the best AUC.

**Configuration**:
```yaml
models:
  - name: "lgbm"
    type: "lightgbm"
    # ... LightGBM config
  - name: "cat"
    type: "catboost"
    # ... CatBoost config
```

### Strategy 2: LightGBM + Neural Network

**When to use**: You have a large dataset and want to combine tree-based and neural approaches

**Why**: Tree models excel at structured features, neural networks can learn complex non-linear patterns.

**Configuration**:
```yaml
models:
  - name: "lgbm"
    type: "lightgbm"
    # ... LightGBM config
  - name: "nn"
    type: "neural_network"
    # ... Neural network config
```

### Strategy 3: Three-Model Ensemble

**When to use**: You want maximum performance and have computational resources

**Why**: More diverse models can capture more patterns, but returns diminish after 3-4 models.

**Configuration**:
```yaml
models:
  - name: "lgbm"
    type: "lightgbm"
    # ... config
  - name: "cat"
    type: "catboost"
    # ... config
  - name: "nn"
    type: "neural_network"
    # ... config
```

!!! warning
    Adding more than 3-4 base models typically yields diminishing returns and increases training time significantly. Stick to 2-3 well-tuned models.

### Strategy 4: Soft Voting with Weights

**When to use**: One model consistently outperforms others

**Why**: Weight the better model more heavily to prioritize its predictions.

**Configuration**:
```yaml
ensemble:
  method: "soft_voting"
  weights: [0.7, 0.3]  # LightGBM 70%, CatBoost 30%
```

## Performance Expectations

### Typical Gains

Based on fraud detection benchmarks:

| Setup | Typical AUC Improvement |
|-------|------------------------|
| LightGBM alone | 0.78 - 0.85 |
| CatBoost alone | 0.77 - 0.84 |
| LightGBM + CatBoost (soft voting) | +0.01 to +0.03 vs best single |
| LightGBM + CatBoost (stacking) | +0.02 to +0.05 vs best single |
| LightGBM + CatBoost + NN (stacking) | +0.03 to +0.06 vs best single |

!!! tip
    Don't expect magic. Ensembles typically provide 2-5% absolute AUC improvement. If base models are weak (AUC < 0.70), ensembles won't fix the problem—focus on feature engineering instead.

## Common Issues and Solutions

### Ensemble Underperforms Best Single Model

**Problem**: Ensemble AUC is lower than the best base model's AUC.

**Possible causes**:
- Base models are too similar (low diversity)
- Meta-learner is overfitting
- `use_val_as_oof: true` causing data leakage issues

**Solutions**:
1. **Increase model diversity**: Try LightGBM + CatBoost + Neural Network
2. **Change meta-learner**: Try `lightgbm` or `catboost` instead of `logistic_regression`
3. **Use proper OOF**: Set `use_val_as_oof: false` to avoid blending issues
4. **Check base model performance**: Ensure each base model has AUC > 0.75

### Overfitting to Validation Set (Blending)

**Problem**: Ensemble performs well on validation set but poorly on test set.

**Cause**: `use_val_as_oof: true` uses validation set for both early stopping AND meta-learner training.

**Solution**: Use proper OOF (`use_val_as_oof: false`) for final model validation:

```yaml
ensemble:
  method: "stacking"
  use_val_as_oof: false  # Proper OOF
  cv: 5
```

### Slow Training (Proper OOF)

**Problem**: Ensemble training with `use_val_as_oof: false` takes too long.

**Cause**: K-fold CV requires K training passes per base model (e.g., 5 folds × 3 models = 15 training passes).

**Solutions**:
1. **Use blending for iteration**: Set `use_val_as_oof: true` during development
2. **Reduce CV folds**: Set `cv: 3` instead of default `cv: 5`
3. **Reduce base models**: Stick to 2 models instead of 3-4
4. **Use proper OOF only for final validation**: Switch back to blending for production

### Meta-learner Fails to Converge

**Problem**: Logistic regression meta-learner fails or produces warnings.

**Cause**: Meta-learner sees perfectly correlated or constant features (base model predictions are too similar).

**Solutions**:
1. **Increase regularization**: Set `C: 0.1` or `C: 0.01` in meta_learner params
2. **Add different models**: Ensure base models are diverse
3. **Change meta-learner type**: Use `lightgbm` or `catboost` instead of `logistic_regression`

```yaml
ensemble:
  method: "stacking"
  meta_learner:
    type: "logistic_regression"
    params:
      C: 0.1  # Strong regularization
      max_iter: 2000
```

## Advanced Ensemble Techniques

### Cross-Validation Ensemble

Train multiple ensembles on different CV folds and average predictions:

```python
# Custom implementation in src/models/custom_ensemble.py
# (Requires custom model implementation)
```

### Stacking with Feature Engineering

Include engineered features along with base model predictions in meta-learner:

```yaml
# Requires custom meta-learner implementation
ensemble:
  method: "stacking"
  meta_learner:
    type: "lightgbm"  # Can handle features + predictions
```

### Dynamic Ensembling

Use different models for different customer segments (e.g., residential vs commercial):

```python
# Custom implementation in src/inference/custom_inference.py
# Route to different models based on customer segment
```

## Next Steps

- [Model Selection Guide](model-selection-guide.md) - Choosing the right base models
- [End-to-End Example](end-to-end-example.md) - Hands-on tutorial
- [Configuration Guide](../configuration/) - Detailed ensemble configuration options
- [Understanding Results](../user-guide/understanding-results.md) - Interpreting ensemble performance
