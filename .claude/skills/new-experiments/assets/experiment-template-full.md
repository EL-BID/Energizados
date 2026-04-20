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

**Protocolo de decision**:
1. Correr todos en paralelo.
2. Comparar cada uno vs. **AUC del mejor modelo de v_anterior** (o 0.5 si es la primera version) en AUC test.
3. Ganador = mayor AUC test. Si ninguno supera el baseline de version anterior → revisar dataset/ETL antes de continuar.
4. Empate (<0.001): preferir el modelo mas simple (menor numero de features/hiperparametros).
5. Si LightGBM > CatBoost → usar LightGBM como modelo base para F2–F6. Registrar decision.

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

**Protocolo de decision**:
1. Correr todos en paralelo.
2. Comparar cada uno vs. el **ganador de F1** en AUC test.
3. Ganador = mayor AUC test. Si ninguno supera F1-winner → llevar F1-winner a F3 con su balance original.
4. Empate (<0.001): preferir la estrategia con mejor **Recall** (detectar fraude es el objetivo operacional).
5. Registrar la estrategia ganadora en "Decisiones Acumuladas" — todas las fases siguientes usan ese balance.

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

**Protocolo de decision**:
1. Correr exp1–3 en paralelo (independientes entre si). Correr exp4 después de evaluar exp1–3.
2. Comparar exp1–3 vs. el **ganador de F2** en AUC test. Marcar cada componente como "util" (mejora) o "descartado" (no mejora).
3. Ajustar exp4–exp7 para incluir solo componentes utiles. Correr exp4, luego exp5–6 en paralelo, luego exp7.
4. Ganador = mayor AUC test entre todos los experimentos **y** el baseline F2. Si ninguno supera F2 → llevar F2 a F4 sin FE nuevo.
5. Empate (<0.001): preferir el experimento con **menos transformers** (menos riesgo de overfit).

**Optional geo features**: Si lat/lon disponibles, agregar `GeoFeaturesETL` a `etl.yaml` y re-correr ETL primero.
El dataset de salida incluirá `geo_cluster`, `geo_estado`, etc. como columnas regulares — sin cambio en los YAMLs de training.
**NUNCA usar `geo_features` dentro de `global_transformers`** — no existe como transformer de preprocessing.

### FASE 4 — Encoding Optimization (3 experiments, parallel)

> **Objective**: Refine categorical encoding.
> **Base**: F3 winner FE + F2 winner sampling + F1 winner model.

| Exp  | Name                    | What varies                                  |
|------|-------------------------|----------------------------------------------|
| exp1 | all-target-enc          | ALL columns use target_encoding              |
| exp2 | dummy-plus-te           | to_dummy low-card + TE high-card             |
| exp3 | cardinality-thresholds  | More aggressive cardinality_reducer thresholds|

**Protocolo de decision**:
1. Correr todos en paralelo.
2. Comparar cada uno vs. el **ganador de F3** en AUC test.
3. Ganador = mayor AUC test. Si ninguno supera F3-winner → llevar F3-winner a F5 con su encoding original.
4. Empate (<0.001): preferir el encoding mas simple (menos transformaciones).

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

**Protocolo de decision**:
1. Correr en secuencia (exp1 → exp2 → exp3 → exp4).
2. Comparar cada uno vs. el **ganador de F4** (sin feature selection) en AUC test.
3. Feature selection SOLO se adopta si AUC test > F4-winner — la barra es alta.
4. Ganador = mayor AUC test **si supera F4-winner**; de lo contrario → llevar F4-winner a F6 sin seleccion.
5. Empate (<0.001): preferir el metodo con **menos features finales**.

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

**Protocolo de decision**:
1. Correr exp1–3 en paralelo (no-search, rapidos). Evaluar. Correr exp4–6 en paralelo (con search, lentos).
2. Comparar todos vs. el **ganador de F5** en AUC test. El tuning SOLO se adopta si AUC > F5-winner.
3. Ganador = mayor AUC test. Si ninguno supera F5-winner → llevar F5-winner a F7 con hiperparametros default.
4. Empate (<0.001): preferir exp sin search (menos riesgo de overfit en validacion).
5. Registrar el modelo ganador (tipo + hiperparametros) en "Decisiones Acumuladas".

**IMPORTANTE**: exp4–6 deben usar el MISMO pipeline para ser directamente comparables.
**TSS** = TimeSeriesSplit, respeta orden temporal (evita leakage).

### FASE 7 — Calibration (2 experiments, sequential)

> **Objective**: Optimize decision threshold and probability calibration.
> **Base**: TOP 1 model from F6.

| Exp  | Name                  | What varies                                    |
|------|-----------------------|------------------------------------------------|
| exp1 | threshold-calibration | `evaluation.calibration: cost_benefit(fp=1, fn=10)` |
| exp2 | prob-calibration      | `model.calibration: sigmoid(cv=3)` + cost_benefit |

**Protocolo de decision**:
1. Correr exp1 primero (establece threshold optimo sobre F6-winner). Correr exp2 despues.
2. Comparar exp1 y exp2 vs. **F6-winner con threshold=0.5** en AUC test + F1.
3. El threshold optimizado de exp1 es el **piso garantizado** — nunca salir peor que F6-winner.
4. Ganador = mejor F1 (o metrica de negocio definida). Si exp2 no supera exp1 → usar solo threshold calibration.
5. Registrar el threshold final en la tabla de resultados (columna "Threshold").

### FASE 8 — Ensemble (1+ experiments)

> **Objective**: Combine best models to maximize AUC.

| Exp  | Name                | What varies                                    |
|------|---------------------|------------------------------------------------|
| exp1 | stacking-ensemble   | TOP2 models + stacking + logistic meta-learner |

**Protocolo de decision**:
1. Correr el ensemble con los TOP 2 modelos de F6.
2. Comparar vs. el **ganador de F7** en AUC test + F1.
3. Ensemble se adopta SOLO si AUC test >= F7-winner Y F1 no degrada.
4. Si el ensemble no supera al modelo individual → entregar F7-winner como modelo final.
5. Registrar modelo final y threshold en "Decisiones Acumuladas".

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
