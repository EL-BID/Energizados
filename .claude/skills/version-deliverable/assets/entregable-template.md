# Entregable Template — _entregable_v{N}.md

> This is the reference template for the multi-version deliverable document.
> Replace all `{PLACEHOLDERS}` with values from experiments.
> ALL prose must be in **Spanish**. Code/identifiers remain in English.
> Repeat iteration/appendix sections for each version (v0, v1, v2, ...).
> The letter labels for appendices increment: A=v0, B=v1, C=v2, etc.
> The configuration appendix is always the second-to-last letter.
> The complete tables appendix is always the last letter.

---

# Entregable {DELIVERABLE_NUMBER}

{DATE}

# Empresa

- {COMPANY_NAME}

# Proyecto

- {PROJECT_NAME}

---

# Objetivo {#objetivo}

Los objetivos del presente entregable son los siguientes:

- {OBJETIVO_1}
- {OBJETIVO_2}
- {OBJETIVO_3}
- {OBJETIVO_4}
- {OBJETIVO_5}

# Iteraciones {#iteraciones}

A lo largo de este documento se encontrarán una serie de iteraciones, cada una de las cuales representa diferentes grupos de experimentos que se realizaron. Iniciamos con una iteración v0, analizamos sus resultados y sobre la misma planteamos la base para la iteración v1.
A continuación describimos cada una de estas iteraciones.

<!-- ============================================================ -->
<!-- ITERACIÓN V0 — Repeat this block for each version            -->
<!-- ============================================================ -->

## Iteración v0 — {V0_TITLE} {#iteración-v0-—-{v0_title_slug}}

{V0_SUMMARY_PARAGRAPH}

Para los detalles técnicos de la iteración por favor ver la sección [APÉNDICE TÉCNICO A](#apéndice-técnico-a-—-detalle-de-experimentos-v0)

### Métricas principales

| Métrica | Valor | Interpretación |
| :---- | :---- | :---- |
| AUC (test) | {V0_BEST_AUC} | De cada 100 pares (fraude vs. no fraude), el modelo ordena correctamente ~{V0_BEST_AUC_PCT}. |
| AUC (val) | {V0_BEST_AUC_VAL} | Generalización {V0_GAP_INTERPRETATION}. |
| Recall | {V0_BEST_RECALL} | De cada 100 fraudes reales, el modelo detecta ~{V0_BEST_RECALL_PCT}. |
| Precisión | {V0_BEST_PRECISION} | De cada 100 clientes marcados, ~{V0_BEST_PRECISION_PCT} son fraude real. |
| F1 | {V0_BEST_F1} | Balance entre precisión y recall. |

### Fases y experimentos ejecutados

| Fase | Objetivo | Experimentos | Que probamos? |
| :---- | :---- | ----- | :---- |
{V0_PHASES_TABLE}

### Hallazgos principales (v0)

{V0_KEY_FINDINGS_BULLETS}

---

<!-- ============================================================ -->
<!-- ITERACIÓN V1 — Repeat this block for each version            -->
<!-- ============================================================ -->

## Iteración v1 — {V1_TITLE} {#iteración-v1-—-{v1_title_slug}}

{V1_SUMMARY_PARAGRAPH}

### Métricas principales

| Métrica | Valor | Interpretación |
| :---- | :---- | :---- |
| AUC (test) | {V1_BEST_AUC} | De cada 100 pares, el modelo identifica correctamente ~{V1_BEST_AUC_PCT}. |
| AUC (val) | {V1_BEST_AUC_VAL} | Estimador honesto: ~{V1_BEST_AUC_VAL_PCT} de cada 100 pares ordenados correctamente. |
| Recall | {V1_BEST_RECALL} | De cada 100 fraudes reales, detecta ~{V1_BEST_RECALL_PCT}. |
| Precisión | {V1_BEST_PRECISION} | De cada 100 marcados, ~{V1_BEST_PRECISION_PCT} son fraude real. |
| F1 | {V1_BEST_F1} | Balance precisión/recall al threshold calibrado. |

{V1_GAP_WARNING}

### Fases ejecutadas

| Fase | Objetivo | Experimentos | Que probamos? |
| :---- | :---- | :---- | :---- |
{V1_PHASES_TABLE}

### El hallazgo central: {V1_KEY_FINDING_TITLE}

{V1_KEY_FINDING_EXPLANATION}

| Config | AUC test | AUC val | Delta |
| :---- | :---- | :---- | :---- |
{V1_KEY_FINDING_COMPARISON_TABLE}

{V1_KEY_FINDING_DETAILS}

### Modelos recomendados para producción

{V1_PRODUCTION_MODELS_INTRO}

| Recomendación | Experimento | AUC val | AUC test | P | R | F1 | Threshold |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
{V1_PRODUCTION_MODELS_TABLE}

### Métricas por segmento geográfico

{V1_SEGMENT_INTRO}

| Región | Registros | Fraudes | Tasa fraude | AUC | Precisión | Recall |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
{V1_SEGMENT_TABLE}

Hallazgos clave:

{V1_SEGMENT_FINDINGS}

---

<!-- ============================================================ -->
<!-- COMPARATIVA SECTION                                          -->
<!-- ============================================================ -->

# Comparativa v0 vs v1 {#comparativa-v0-vs-v1}

## Evolución de métricas {#evolución-de-métricas}

| Métrica | v0 | v1 | Delta |
| :---- | :---- | :---- | :---- |
| AUC (test) | {V0_BEST_AUC} | {V1_BEST_AUC} | {AUC_DELTA:+.4f} |
| AUC (val) | {V0_BEST_AUC_VAL} | {V1_BEST_AUC_VAL} | {AUC_VAL_DELTA:+.4f} |
| Precisión @ 0.5 | {V0_PRECISION_05} | {V1_PRECISION_05} | {PREC_DELTA:+.4f} |
| Recall @ 0.5 | {V0_RECALL_05} | {V1_RECALL_05} | {RECALL_DELTA:+.4f} |
| F1 @ 0.5 | {V0_F1_05} | {V1_F1_05} | {F1_DELTA:+.4f} |
| Total features | {V0_N_FEATURES} | {V1_N_FEATURES} | {FEAT_DELTA:+d} |
| Experimentos | {V0_TOTAL_EXPERIMENTS} en {V0_TOTAL_PHASES} fases | {V1_TOTAL_EXPERIMENTS} en {V1_TOTAL_PHASES} fases | {EFFICIENCY_NOTE} |

## Cambios principales entre versiones {#cambios-principales-entre-versiones}

| Aspecto | v0 | v1 |
| :---- | :---- | :---- |
| Modelo | {V0_MODEL_DESC} | {V1_MODEL_DESC} |
| Features | {V0_N_FEATURES} ({V0_FE_DESC}) | {V1_N_FEATURES} ({V1_FE_DESC}) |
| Sampling | {V0_SAMPLING_DESC} | {V1_SAMPLING_DESC} |
| {CHANGED_ASPECT_1} | {V0_ASPECT_1} | {V1_ASPECT_1} |
| {CHANGED_ASPECT_2} | {V0_ASPECT_2} | {V1_ASPECT_2} |
| Gap test/val | {V0_GAP} | {V1_GAP} |

## Análisis del delta {#análisis-del-delta}

{DELTA_MAIN_FINDING}

Evidencia:

{DELTA_EVIDENCE_NUMBERED_LIST}

Otros cambios que contribuyen marginalmente:

{DELTA_MARGINAL_CHANGES}

Lo que NO cambió o empeoró:

{DELTA_NO_CHANGE_OR_WORSE}

---

<!-- ============================================================ -->
<!-- EFICIENCIA OPERATIVA                                         -->
<!-- ============================================================ -->

# Eficiencia Operativa {#eficiencia-operativa}

## Curva de ganancia acumulada — Comparativa {#curva-de-ganancia-acumulada-—-comparativa}

La siguiente tabla establece una comparativa del % de fraudes detectados para cada una de las iteraciones tomando un top % de clientes a inspeccionar.

| % clientes inspeccionados | v0: % fraudes detectados | v1: % fraudes detectados | Mejora |
| :---- | :---- | :---- | :---- |
{GAINS_COMPARISON_TABLE}

## Escenario práctico {#escenario-práctico}

{LATEST_VERSION} dataset test: {TEST_TOTAL_CLIENTS:,} clientes, ~{TEST_TOTAL_FRAUDS:,} fraudes

| Estrategia | Inspecciones | Fraudes encontrados | Falsos positivos | Fraudes perdidos |
| :---- | ----: | ----: | ----: | ----: |
{PRACTICAL_SCENARIO_TABLE}

## Recomendación operativa {#recomendación-operativa}

- {OP_RECOMMENDATION_1}
- {OP_RECOMMENDATION_2}
- {OP_RECOMMENDATION_3}
- {OP_RECOMMENDATION_4}

---

<!-- ============================================================ -->
<!-- PERÍODO DE DATOS                                             -->
<!-- ============================================================ -->

# Período de datos utilizados {#período-de-datos-utilizados}

A continuación detallamos los períodos de datos usados para cada iteración.

## v0 {#v0}

| Conjunto | Periodo | Registros | Tasa de fraude |
| :---- | :---- | :---- | :---- |
| Entrenamiento | {V0_TRAIN_PERIOD} | {V0_TRAIN_ROWS:,} | {V0_TRAIN_FRAUD_RATE}% |
| Validación | {V0_VAL_PERIOD} | — | — |
| Test | {V0_TEST_PERIOD} | {V0_TEST_ROWS:,} | {V0_TEST_FRAUD_RATE}% |

## v1 {#v1}

| Conjunto | Periodo | Registros | Tasa de fraude |
| :---- | :---- | :---- | :---- |
| Entrenamiento | {V1_TRAIN_PERIOD} | {V1_TRAIN_ROWS:,} | {V1_TRAIN_FRAUD_RATE}% |
| Validación | {V1_VAL_PERIOD} | — | — |
| Test | {V1_TEST_PERIOD} | {V1_TEST_ROWS:,} | {V1_TEST_FRAUD_RATE}% |

- Método de split: {SPLIT_METHOD} (ordenamiento temporal estricto, sin leakage).
- Columna de fecha: {DATE_COLUMN}.
- El test set es {TEST_PERIOD_LENGTH} — simula deployment real.
{PERIOD_NOTES}

# Lecciones aprendidas {#lecciones-aprendidas}

{LECCIONES_BULLETS}

# Documentos relacionados {#documentos-relacionados}

{RELATED_DOCS}

# Repositorio de fuentes {#repositorio-de-fuentes}

- {REPO_URL}

# Próximos pasos {#próximos-pasos}

{PROXIMOS_PASOS_BULLETS}

---

<!-- ============================================================ -->
<!-- APÉNDICE TÉCNICO A — Detalle de Experimentos v0              -->
<!-- ============================================================ -->

# APÉNDICE TÉCNICO A — Detalle de Experimentos v0 {#apéndice-técnico-a-—-detalle-de-experimentos-v0}

Esta sección está dirigida a técnicos que deseen profundizar en las decisiones experimentales y resultados detalle por detalle.

## A.1 Análisis fase por fase (v0) {#a.1-análisis-fase-por-fase-(v0)}

<!-- Repeat for each phase -->
### Fase {PHASE_NUM} — {PHASE_NAME} ({PHASE_COUNT} experimentos)

Hipótesis: {PHASE_HYPOTHESIS}

| \# | Experimento | Modelo | AUC val | AUC test | vs Baseline |
| :---- | :---- | :---- | :---- | :---- | :---- |
{PHASE_RESULTS_TABLE}

Conclusiones:

{PHASE_CONCLUSIONS}
<!-- END repeat per phase -->

## A.2 Matriz de confusión v0 (test, threshold = {V0_THRESHOLD}) {#a.2-matriz-de-confusión-v0-(test,-threshold-=-{v0_threshold})}

|  | Predicción: No fraude | Predicción: Fraude |
| :---- | :---: | :---: |
| Real: No fraude | {V0_TN:,} (TN) | {V0_FP:,} (FP) |
| Real: Fraude | {V0_FN:,} (FN) | {V0_TP:,} (TP) |

- Tasa de falsos positivos: {V0_FP_RATE}% ({V0_FP:,} de {V0_TN_FP:,} legítimos marcados)
- Tasa de falsos negativos: {V0_FN_RATE}% ({V0_FN:,} de {V0_FN_TP:,} fraudes no detectados)
- Test set: {V0_TEST_ROWS:,} registros ({V0_TN_FP:,} no fraude, {V0_FN_TP:,} fraude, tasa {V0_TEST_FRAUD_RATE}%)

{V0_CONFUSION_INTERPRETATION}

## A.3 Calibración v0 {#a.3-calibración-v0}

| Parámetro | Valor |
| :---- | :---- |
| Método | {V0_CAL_METHOD} |
| Costo falso positivo (FP) | {V0_CAL_COST_FP} |
| Costo falso negativo (FN) | {V0_CAL_COST_FN} |
| Threshold resultante | {V0_CAL_THRESHOLD} |

Métricas al threshold calibrado ({V0_CAL_THRESHOLD}):

| Métrica | Valor |
| :---- | :---- |
| Precisión | {V0_CAL_PRECISION} |
| Recall | {V0_CAL_RECALL} |
| F1 | {V0_CAL_F1} |

## A.4 Features finales v0 {#a.4-features-finales-v0}

Total: {V0_N_FEATURES} features después del pipeline completo de feature engineering.

| Grupo | Origen | Features estimadas |
| :---- | :---- | :---- |
{V0_FEATURES_TABLE}

{V0_FEATURES_DETAIL}

---

---

<!-- ============================================================ -->
<!-- APÉNDICE TÉCNICO B — Detalle de Experimentos v1              -->
<!-- ============================================================ -->

# APÉNDICE TÉCNICO B — Detalle de Experimentos v1 {#apéndice-técnico-b-—-detalle-de-experimentos-v1}

## B.1 Análisis fase por fase (v1) {#b.1-análisis-fase-por-fase-(v1)}

<!-- Repeat for each phase -->
### Fase {PHASE_NUM} — {PHASE_NAME} ({PHASE_COUNT} experimentos)

Hipótesis: {PHASE_HYPOTHESIS}

| \# | Experimento | AUC val | AUC test | Prec | Recall | F1 |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
{PHASE_RESULTS_TABLE}

Conclusiones:

{PHASE_CONCLUSIONS}
<!-- END repeat per phase -->

## B.2 Matriz de confusión v1 (test, threshold = {V1_THRESHOLD}) {#b.2-matriz-de-confusión-v1-(test,-threshold-=-{v1_threshold})}

{V1_MODEL_DESCRIPTION}

|  | Predicción: No fraude | Predicción: Fraude |
| :---- | :---: | :---: |
| Real: No fraude | {V1_TN:,} (TN) | {V1_FP:,} (FP) |
| Real: Fraude | {V1_FN:,} (FN) | {V1_TP:,} (TP) |

- Tasa de falsos positivos: {V1_FP_RATE}% ({V1_FP:,} de {V1_TN_FP:,} legítimos marcados)
- Tasa de falsos negativos: {V1_FN_RATE}% ({V1_FN:,} de {V1_FN_TP:,} fraudes no detectados)
- Test set: {V1_TEST_ROWS:,} registros ({V1_TN_FP:,} no fraude, {V1_FN_TP:,} fraude, tasa {V1_TEST_FRAUD_RATE}%)

{V1_CONFUSION_ALTERNATIVE}

## B.3 Calibración v1 {#b.3-calibración-v1}

| Parámetro | Valor |
| :---- | :---- |
| Método | {V1_CAL_METHOD} |
| Costo falso positivo (FP) | {V1_CAL_COST_FP} |
| Costo falso negativo (FN) | {V1_CAL_COST_FN} |
| Threshold resultante | {V1_CAL_THRESHOLD} |

{V1_CAL_INTERPRETATION}

{V1_GAP_ANALYSIS_SECTION}

## B.{GAP_SECTION_NUM} Gap AUC test/val — Análisis detallado {#b.{gap_section_num}-gap-auc-test/val-—-análisis-detallado}

{V1_GAP_EXPLANATION}

El gap aparece en TODOS los experimentos con {V1_GAP_FEATURES_DESC} (no es específico del stacking):

| Experimento | AUC val | AUC test | Diff |
| :---- | :---- | :---- | :---- |
{V1_GAP_TABLE}

Posibles causas:

{V1_GAP_CAUSES}

{V1_GAP_RECOMMENDATION}

## B.5 Features finales v1 {#b.5-features-finales-v1}

Total: {V1_N_FEATURES} features después del pipeline completo de feature engineering.

| Grupo | Origen | Features estimadas | Novedad v1 |
| :---- | :---- | :---- | :---- |
{V1_FEATURES_TABLE}

Nuevas features en v1 (~{V1_NEW_FEATURES_COUNT} adicionales): {V1_NEW_FEATURES_LIST}.

---

---

<!-- ============================================================ -->
<!-- APÉNDICE TÉCNICO {CONFIG_LETTER} — Configuración de los Modelos -->
<!-- ============================================================ -->

# APÉNDICE TÉCNICO {CONFIG_LETTER} — Configuración de los Modelos {#apéndice-técnico-{config_letter}-—-configuración-de-los-modelos}

## {CONFIG_LETTER}.1 Pipeline de feature engineering v0 — Preprocessing por columna {#{config_letter}.1-pipeline-de-feature-engineering-v0-—-preprocessing-por-columna}

| Columna | Transformación | Parámetros |
| :---- | :---- | :---- |
{V0_FE_COLUMNS_TABLE}

Columnas eliminadas: {V0_DROP_COLUMNS}

Transformadores globales v0:

| Transformador | Parámetros |
| :---- | :---- |
{V0_GLOBAL_TRANSFORMERS_TABLE}

Selección de variables: {V0_FEATURE_SELECTION_STATUS}.

## {CONFIG_LETTER}.2 Pipeline de feature engineering v1 — Preprocessing por columna {#{config_letter}.2-pipeline-de-feature-engineering-v1-—-preprocessing-por-columna}

| Columna | Transformación | Parámetros | Novedad |
| :---- | :---- | :---- | :---- |
{V1_FE_COLUMNS_TABLE}

Columnas eliminadas: {V1_DROP_COLUMNS}

Transformadores globales v1:

| Transformador | Parámetros | Novedad |
| :---- | :---- | :---- |
{V1_GLOBAL_TRANSFORMERS_TABLE}

Selección de variables: {V1_FEATURE_SELECTION_STATUS}.

## {CONFIG_LETTER}.3 Hiperparámetros v0 {#{config_letter}.3-hiperparámetros-v0}

```yaml
{V0_HYPERPARAMS_YAML}
```

## {CONFIG_LETTER}.4 Hiperparámetros v1 {#{config_letter}.4-hiperparámetros-v1}

```yaml
{V1_HYPERPARAMS_YAML}
```

## {CONFIG_LETTER}.5 Diferencias clave en hiperparámetros v0 vs v1 {#{config_letter}.5-diferencias-clave-en-hiperparámetros-v0-vs-v1}

| Aspecto | v0 | v1 |
| :---- | :---- | :---- |
{CONFIG_DIFF_TABLE}

---

---

<!-- ============================================================ -->
<!-- APÉNDICE TÉCNICO {TABLES_LETTER} — Tablas Completas          -->
<!-- ============================================================ -->

# APÉNDICE TÉCNICO {TABLES_LETTER} — Tablas Completas de Experimentos {#apéndice-técnico-{tables_letter}-—-tablas-completas-de-experimentos}

## {TABLES_LETTER}.1 Tabla completa v0 ({V0_TOTAL_EXPERIMENTS} experimentos) {#{tables_letter}.1-tabla-completa-v0-({v0_total_experiments}-experimentos)}

| \# | Fase | Experimento | Modelo | AUC val | AUC test | Prec | Recall | F1 | Diff AUC | vs Baseline |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
{V0_FULL_EXPERIMENT_TABLE}

Nota: "vs Baseline" compara contra el AUC test del primer experimento (fase1_exp1, AUC={V0_BASELINE_AUC}). ✅ = mejoró (> +0.001), ➖ = sin cambio significativo (±0.001), ❌ = empeoró (< -0.001).

## {TABLES_LETTER}.2 Tabla completa v1 ({V1_TOTAL_EXPERIMENTS} experimentos) {#{tables_letter}.2-tabla-completa-v1-({v1_total_experiments}-experimentos)}

| \# | Fase | Experimento | Modelo | AUC val | AUC test | Prec | Recall | F1 | Diff AUC | vs Baseline |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
{V1_FULL_EXPERIMENT_TABLE}

Nota: "vs Baseline" compara contra el AUC test del primer experimento (fase1_exp1, AUC={V1_BASELINE_AUC}). ✅ = mejoró (> +0.001), ➖ = sin cambio significativo (±0.001), ❌ = empeoró (< -0.001).

Diff AUC = AUC val − AUC test. Valores negativos grandes indican que el test es "más fácil" que la validación.

# Glosario {#glosario}

## Términos generales {#términos-generales}

| Término | Definición |
| :---- | :---- |
| **AUC** | Area Under the ROC Curve. Capacidad del modelo para distinguir fraude vs. no fraude (0.5 = azar, 1.0 = perfecto). |
| **AUC test** | AUC sobre el conjunto de test (mes futuro no visto). Simula desempeño real en producción. |
| **AUC val** | AUC sobre validación. Estimador honesto de generalización cuando hay gap atípico con test. |
| **Baseline** | Modelo inicial simple como referencia. Incluye modelos vanilla y rule-based. |
| **Blending** | Stacking donde el meta-learner se entrena sobre predicciones de validación (`use_val_as_oof=true`). Más rápido, posible leakage. |
| **Calibración** | Ajuste del threshold según costos operativos. Relación cost_FN/cost_FP determina el threshold resultante. |
| **Costo-beneficio** | Método que determina threshold óptimo minimizando el costo esperado total de las inspecciones. |
| **Curva de ganancia acumulada** | % de fraudes detectados vs. % de clientes inspeccionados. Permite dimensionar la operación. |
| **Diff AUC / Gap test/val** | Diferencia AUC test − AUC val. Normal ≈ 0. Valores grandes indican test más "fácil" que validación. |
| **Encoding** | Transformación de categóricas a numéricas: target encoding (alta card.), ordinal (baja card.), dummy. |
| **Ensemble** | Combinación de modelos para mejorar predicciones. Stacking y soft voting probados. |
| **F1 Score** | Media armónica precisión/recall. Balance general del modelo. |
| **Feature engineering** | Creación de nuevas variables desde los datos. Mayor driver de mejora en ambas versiones. |
| **Feature selection** | Eliminación de variables ruidosas o redundantes. |
| **FN (Falso Negativo)** | Fraude no detectado. |
| **FP (Falso Positivo)** | Cliente legítimo marcado como fraude. Genera inspección innecesaria. |
| **Gradient boosting** | Algoritmos secuenciales donde cada modelo corrige errores del anterior. Incluye LGBM, CatBoost, XGBoost. |
| **Leakage** | Fuga de información futura al entrenamiento. Contamina la evaluación. |
| **Meta-learner** | Modelo que combina predicciones base en stacking. |
| **Non-technical losses** | Pérdidas por fraude, robo o manipulación de medidores. Objetivo del proyecto. |
| **Overfitting** | El modelo aprende patrones del entrenamiento que no generalizan. |
| **Oversample** | Duplicar registros de la clase minoritaria para balancear el dataset. |
| **Precisión (Precision)** | De 100 marcados, cuántos son fraude real. |
| **Recall** | De 100 fraudes reales, cuántos detecta. |
| **Rolling-window CV** | Validación cruzada con ventanas temporales deslizantes. |
| **Rule-based models** | Modelos sin ML: detectan patrones simples de consumo. |
| **Sampling** | Estrategias contra desbalance: undersample, oversample, SMOTETomek, class_weight. |
| **Soft voting** | Promedio ponderado de probabilidades de modelos base. |
| **Split (partición)** | División train/val/test por time_series. Test = siempre 1 mes futuro. |
| **Stacking** | Meta-learner sobre predicciones base. Aporte marginal en el proyecto. |
| **Target encoding (TE)** | Reemplaza categoría por probabilidad promedio del target. Parámetro `w` = suavización. |
| **Threshold** | Umbral de probabilidad para clasificar fraude. |
| **TN (True Negative)** | Cliente legítimo correctamente clasificado como no fraude. |
| **TP (True Positive)** | Fraude correctamente detectado. |
| **Undersample** | Reduce la clase mayoritaria para balancear el dataset. |

## Modelos y algoritmos {#modelos-y-algoritmos}

| Término | Definición |
| :---- | :---- |
| **Boruta** | Selección de variables por shadow features. |
| **CatBoost** | Gradient boosting con manejo nativo de categóricas. |
| **class_weight="balanced"** | Pesos de clase inversamente proporcionales a frecuencia. Compensa desbalance de clases. |
| **KMeans** | Clustering para geo_cluster sobre coordenadas. |
| **LightGBM** | Gradient boosting optimizado para velocidad. Modelo principal del proyecto. |
| **RandomSearch** | Búsqueda aleatoria de hiperparámetros. Overfitea en datasets temporales. |
| **Scale_pos_weight** | Parámetro LGBM para penalizar errores en clase minoritaria. |
| **XGBoost** | Gradient boosting alternativo. Sin tuning degrada vs. LightGBM. |

## Transformadores / Features {#transformadores-/-features}

| Término | Definición |
| :---- | :---- |
| **cardinality_reducer** | Agrupa categorías infrecuentes en "otros" según threshold de frecuencia. |
| **clip_outliers** | Recorta valores extremos en consumo. |
| **consumption_patterns** | Features de fraude: diff ratios, min_max_ratio, zscore, zero_ratio, slope, consistency, drastic_changes. |
| **extra_vars** | Variables estadísticas (media, desvío, pendiente, ceros) para ventanas de N meses. |
| **GeoFeaturesETL** | ETL de features geográficas: geo_cluster (KMeans), geo_region (IBGE), distancias haversine. |
| **Haversine** | Distancia entre dos puntos lat/lon sobre la Tierra. Genera features de distancia a ciudades de referencia. |
| **if_score** | Score de anomalía Isolation Forest. Alto = más anómalo. |
| **temporal_features** | Features calendario con encoding cíclico (sin/cos): month, quarter. Preserva circularidad (dic-ene son vecinos). |
| **tsfel_vars** | Features de series temporales vía TSFEL: mean, std, skewness, kurtosis, autocorrelation, slope, zero crossing. |

## Abreviaturas y siglas {#abreviaturas-y-siglas}

| Sigla | Significado |
| :---- | :---- |
| AUC | Area Under the ROC Curve |
| CB / CAT | CatBoost |
| CV | Cross-Validation |
| FN | Falso Negativo |
| FP | Falso Positivo |
| IBGE | Instituto Brasileiro de Geografia e Estatística |
| IF | Isolation Forest |
| LGBM | LightGBM |
| LR | Logistic Regression |
| MAD | Mean Absolute Deviation |
| ML | Machine Learning |
| NTL | Non-Technical Losses (pérdidas no técnicas) |
| OOF | Out-of-Fold predictions |
| P | Precisión (Precision) |
| R | Recall |
| ROC | Receiver Operating Characteristic |
| TE | Target Encoding |
| TN | True Negative |
| TP | True Positive |
| TSFEL | Time Series Feature Extraction Library |
| XGB | XGBoost |
