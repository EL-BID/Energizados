# Quick Experiment Template (3 Phases, ~6-8 experiments)

> Best for: rapid prototyping, proof of concept, initial assessment.
> Skips: Sampling, Encoding optimization, Feature Selection, Calibration, Ensemble.

## Phase Breakdown

### FASE 1 — Baselines (2-3 experiments, parallel)

> **Objective**: Quick check — can we detect fraud at all?
> **Config**: `class_weight: balanced`, ordinal encoding, no FE.

| Exp  | Name              | What varies             |
|------|-------------------|-------------------------|
| exp1 | lgbm-vanilla      | LightGBM default        |
| exp2 | catboost-vanilla  | CatBoost default        |

**Optional**: Add `exp3: xgboost-vanilla` if XGBoost is installed.

**Protocolo de decision**:
1. Correr todos en paralelo.
2. Comparar cada uno vs. AUC del mejor modelo de version anterior (o 0.5 si es la primera).
3. Ganador = mayor AUC test. Si AUC < 0.60 → revisar dataset/ETL antes de continuar.
4. Empate (<0.001): preferir LightGBM (mas inspeccionable que CatBoost para iteraciones rapidas).

### FASE 2 — Feature Engineering (2 experiments, sequential)

> **Objective**: Does feature engineering help?
> **Base**: F1 winner model + `class_weight: balanced`.

| Exp  | Name          | Global transformers                           | Hypothesis                     |
|------|---------------|-----------------------------------------------|--------------------------------|
| exp1 | extra-vars    | `extra_vars(3,6,12)`                          | Basic stats add signal         |
| exp2 | full-fe       | `extra_vars(3,6,12)` + `tsfel_vars(12)`       | Full FE is significantly better|

**Protocolo de decision**:
1. Correr exp1 primero. Si no mejora vs F1-winner → no correr exp2 (FE no ayuda en este dataset).
2. Si exp1 mejora → correr exp2 y comparar ambos vs el **ganador de F1**.
3. Ganador = mayor AUC test. Si ninguno supera F1-winner → llevar F1-winner a F3.
4. Umbral minimo practico: ganancia < 0.01 AUC no justifica la complejidad adicional.

### FASE 3 — Model Tuning (2-3 experiments, parallel)

> **Objective**: Quick tuning of the best candidates.
> **Base**: F2 winner FE + `class_weight: balanced`.

| Exp  | Name           | Model     | hyperparam_search    |
|------|----------------|-----------|----------------------|
| exp1 | lgbm-tuned     | LightGBM  | 50 iter, 3-fold TSS  |
| exp2 | catboost-tuned | CatBoost  | 50 iter, 3-fold TSS  |

**Optional**: Add `exp3: xgboost-tuned` if installed.

**Protocolo de decision**:
1. Correr todos en paralelo.
2. Comparar cada uno vs. el **ganador de F2** en AUC test. Tuning SOLO se adopta si AUC > F2-winner.
3. Ganador = mayor AUC test. Si ninguno supera F2-winner → entregar F2-winner como modelo final.
4. Empate (<0.001): preferir el modelo mas simple (menos iter / menos fold).

**IMPORTANTE**: Search reducido (50 iter vs 100) para velocidad — prioridad es iterar rapido.

## Total Experiments: 6-8

| Phase | Count | Can Parallelize | Est. Time |
|-------|-------|-----------------|-----------|
| 1     | 2-3   | Yes             | ~5 min    |
| 2     | 2     | No (sequential) | ~15 min   |
| 3     | 2-3   | Yes             | ~30 min   |

**Total estimated time**: ~1 hour (depends on dataset size).

## When to Upgrade to Standard/Full

After running quick experiments, upgrade if:
- AUC > 0.70 → worth investing in Standard template
- AUC > 0.80 → worth investing in Full template
- AUC < 0.60 → revisit ETL/data quality first
