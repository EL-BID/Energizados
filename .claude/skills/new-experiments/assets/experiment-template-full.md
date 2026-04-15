# Full Experiment Template (8 Phases, ~30-35 experiments)

> Best for: production projects requiring systematic optimization.

## Phase Breakdown

### FASE 1 — Baselines (5 experiments, parallel)

> **Objective**: Establish performance floor. Run all in parallel.
> **Config**: No sampling, no feature engineering, default hyperparams.

| Exp  | Name                     | What varies                                    |
|------|--------------------------|------------------------------------------------|
| exp1 | lgbm-vanilla             | LightGBM + ordinal encoding all                |
| exp2 | catboost-vanilla         | CatBoost + ordinal encoding all                |
| exp3 | simple-trend             | Rule-based: consumption drop threshold         |
| exp4 | simple-constant          | Rule-based: constant consumption pattern       |
| exp5 | lgbm-encoding            | LightGBM + TE high-card + ordinal low-card     |

**Decision criterion**: Highest AUC test. If LightGBM > CatBoost, use LightGBM for F2.
**Recommended carry-forward**: exp5 (best encoding + best model type).

### FASE 2 — Sampling (4 experiments, parallel)

> **Objective**: Handle class imbalance.
> **Base**: F1 winner model + encoding.
> **Config**: Only sampling changes.

| Exp  | Name            | What varies                                   |
|------|-----------------|-----------------------------------------------|
| exp1 | undersample     | `sampling.method: undersample, threshold: 0.5`|
| exp2 | oversample      | `sampling.method: oversample, threshold: 0.5` |
| exp3 | smotetomek      | `sampling.method: smotetomek, threshold: 0.5` |
| exp4 | class-weight    | `sampling.method: none` + `class_weight: balanced` |

**Decision criterion**: Highest AUC test.
**Common outcome**: `class_weight: balanced` often wins (no data loss).

### FASE 3 — Feature Engineering Incremental (7 experiments, partial sequential)

> **Objective**: Add feature groups incrementally and measure each group's contribution.
> **Base**: F1 winner + F2 winner sampling.
> **Execution order**: exp1 → (exp2, exp3 parallel) → exp4 → (exp5, exp6 parallel) → exp7.

| Exp  | Name                 | Global transformers                                     | Hypothesis                               |
|------|----------------------|---------------------------------------------------------|------------------------------------------|
| exp1 | clip-outliers        | `clip_outliers(threshold)`                              | Extreme outliers degrade the model       |
| exp2 | extra-vars           | `extra_vars(3,6,12)`                                    | Statistical features are predictive      |
| exp3 | consumption-patterns | `consumption_patterns(12)`                              | Domain features capture distinct signal  |
| exp4 | extra-plus-patterns  | `extra_vars(3,6,12)` + `consumption_patterns(12)`       | Stats + domain are complementary         |
| exp5 | tsfel                | `extra_vars(3,6,12)` + `tsfel_vars(12)`                 | TSFEL adds sophisticated temporal feats  |
| exp6 | extra-patterns-tsfel | `extra_vars(3,6,12)` + `consumption_patterns` + `tsfel` | All 3 transformers complement each other |
| exp7 | kitchen-sink         | All available transformers                               | Maximum feature extraction               |

**Decision criterion**: Compare AUC incrementally. If exp6 > max(exp4, exp5), all 3 are needed.
**Optional**: exp_geo (geo_features) if lat/lon available and GeoFeaturesETL ran.

### FASE 4 — Encoding Optimization (3 experiments, parallel)

> **Objective**: Refine categorical encoding.
> **Base**: F3 winner FE + F2 winner sampling + F1 winner model.

| Exp  | Name                    | What varies                                  |
|------|-------------------------|----------------------------------------------|
| exp1 | all-target-enc          | ALL columns use target_encoding              |
| exp2 | dummy-plus-te           | to_dummy low-card + TE high-card             |
| exp3 | cardinality-thresholds  | More aggressive cardinality_reducer thresholds|

**Decision criterion**: Highest AUC test. Often the F1 encoding is already optimal.

### FASE 5 — Feature Selection (4 experiments, sequential)

> **Objective**: Remove redundant features.
> **Base**: Full pipeline from F4 winner.
> **Execution order**: exp1 → exp2 → exp3 → exp4.

| Exp  | Name                 | What varies                                         |
|------|----------------------|-----------------------------------------------------|
| exp1 | drop-constant        | `constant(threshold=0.99)`                          |
| exp2 | drop-constant-corr   | `constant(0.99)` → `correlation(0.90)`              |
| exp3 | boruta               | `boruta(n_estimators=100, max_iter=100)`            |
| exp4 | selection-pipeline   | `constant` → `correlation` → `boruta` → union      |

**Decision criterion**: If AUC drops, DON'T use feature selection.
**Common outcome**: Feature selection often doesn't help with tree-based models.

### FASE 6 — Model Tuning (6 experiments, two groups parallel)

> **Objective**: Compare models and find best hyperparams.
> **Base**: Full pipeline from F5 winner (or F4 if F5 was skipped).
> **Group 1** (fast, no search): exp1-3 parallel.
> **Group 2** (slow, with search): exp4-6 parallel.

| Exp  | Name              | Model     | hyperparam_search    |
|------|-------------------|-----------|----------------------|
| exp1 | lgbm-no-tuned     | LightGBM  | disabled             |
| exp2 | catboost-no-tuned | CatBoost  | disabled             |
| exp3 | xgboost-no-tuned  | XGBoost   | disabled             |
| exp4 | lgbm-tuned        | LightGBM  | 100 iter, 5-fold TSS |
| exp5 | catboost-tuned    | CatBoost  | 100 iter, 5-fold TSS |
| exp6 | xgboost-tuned     | XGBoost   | 100 iter, 5-fold TSS |

**IMPORTANT**: exp4-6 MUST use the SAME pipeline for direct comparability.
**TSS** = TimeSeriesSplit, respects temporal order (avoids leakage).

### FASE 7 — Calibration (2 experiments, sequential)

> **Objective**: Optimize decision threshold and probability calibration.
> **Base**: TOP 1 model from F6.

| Exp  | Name                  | What varies                                    |
|------|-----------------------|------------------------------------------------|
| exp1 | threshold-calibration | `evaluation.calibration: cost_benefit(fp=1, fn=10)` |
| exp2 | prob-calibration      | `model.calibration: sigmoid(cv=3)` + cost_benefit |

**Decision criterion**: Best F1 or business metric (depends on cost ratio).

### FASE 8 — Ensemble (1+ experiments)

> **Objective**: Combine best models to maximize AUC.

| Exp  | Name                | What varies                                    |
|------|---------------------|------------------------------------------------|
| exp1 | stacking-ensemble   | TOP2 models + stacking + logistic meta-learner |

**Optional follow-ups**: soft_voting ensemble, 3-model stacking.

## Total Experiments: ~32

| Phase | Count | Can Parallelize |
|-------|-------|-----------------|
| 1     | 5     | Yes (all)       |
| 2     | 4     | Yes (all)       |
| 3     | 7     | Partial         |
| 4     | 3     | Yes (all)       |
| 5     | 4     | No (sequential) |
| 6     | 6     | Partial         |
| 7     | 2     | No (sequential) |
| 8     | 1     | —               |
