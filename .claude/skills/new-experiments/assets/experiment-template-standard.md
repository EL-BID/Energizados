# Standard Experiment Template (4-5 Phases, ~12-15 experiments)

> Best for: quick iterations when some decisions are already known.
> Skips: Sampling (assumes class_weight or known strategy), Encoding (assumes known), Feature Selection.

## Phase Breakdown

### FASE 1 — Baselines (3 experiments, parallel)

> **Objective**: Quick performance floor with the top model candidates.
> **Config**: `class_weight: balanced` (skip sampling phase), default FE, default hyperparams.

| Exp  | Name                | What varies                          |
|------|---------------------|--------------------------------------|
| exp1 | lgbm-vanilla        | LightGBM + encoding                  |
| exp2 | catboost-vanilla    | CatBoost + encoding                  |
| exp3 | xgboost-vanilla     | XGBoost + encoding                   |

**Decision criterion**: Highest AUC test.

### FASE 2 — Feature Engineering (4 experiments, partial sequential)

> **Objective**: Find the best feature combination.
> **Base**: F1 winner model + `class_weight: balanced`.

| Exp  | Name                | Global transformers                    | Hypothesis                        |
|------|---------------------|----------------------------------------|-----------------------------------|
| exp1 | extra-vars          | `extra_vars(3,6,12)`                   | Statistical features are key      |
| exp2 | patterns-tsfel      | `consumption_patterns` + `tsfel_vars`  | Domain + temporal features        |
| exp3 | full-fe             | `extra_vars` + `patterns` + `tsfel`    | All FE combined is best           |
| exp4 | kitchen-sink        | All + `clip_outliers` + `if_score`     | Maximum feature extraction        |

**Decision criterion**: Highest AUC test.
**Common outcome**: exp3 (full FE without outliers) often wins.

### FASE 3 — Model Tuning (3 experiments, parallel)

> **Objective**: Tune the best model types with hyperparameter search.
> **Base**: F2 winner FE + `class_weight: balanced`.
> **All use hyperparam_search** for direct comparability.

| Exp  | Name           | Model     | hyperparam_search    |
|------|----------------|-----------|----------------------|
| exp1 | lgbm-tuned     | LightGBM  | 80 iter, 5-fold TSS  |
| exp2 | catboost-tuned | CatBoost  | 80 iter, 5-fold TSS  |
| exp3 | xgboost-tuned  | XGBoost   | 80 iter, 5-fold TSS  |

**IMPORTANT**: Same pipeline, same encoding, same FE. Only model type + search varies.

### FASE 4 — Calibration (1 experiment)

> **Objective**: Optimize threshold.
> **Base**: TOP 1 model from F3.

| Exp  | Name                  | What varies                              |
|------|-----------------------|------------------------------------------|
| exp1 | threshold-calibration | `evaluation.calibration: cost_benefit`   |

### FASE 5 — Ensemble (1 experiment, optional)

> **Objective**: Combine top 2 models.

| Exp  | Name              | What varies                                   |
|------|-------------------|-----------------------------------------------|
| exp1 | stacking-ensemble | TOP2 models + stacking + logistic meta-learner |

## Optional: Add Sampling Phase

If imbalance is severe (>95/5) and `class_weight` isn't enough, insert between F1 and F2:

| Exp  | Name           | What varies               |
|------|----------------|---------------------------|
| exp1 | undersample    | `sampling: undersample`   |
| exp2 | class-weight   | `class_weight: balanced`  |

## Total Experiments: 12-15

| Phase   | Count | Can Parallelize |
|---------|-------|-----------------|
| 1       | 3     | Yes             |
| 2       | 4     | Partial         |
| 3       | 3     | Yes             |
| 4       | 1     | —               |
| 5 (opt) | 1     | —               |
