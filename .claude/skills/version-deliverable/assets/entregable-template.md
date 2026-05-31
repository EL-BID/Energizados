# Entregable Template — _entregable_v{N}.md

> This is the reference template for the version deliverable document.
> Replace all `{PLACEHOLDERS}` with values from experiments.
> ALL prose must be in **Spanish**. Code/identifiers remain in English.

---

# Entregable — {PROJECT} v{VERSION}

> **Fecha**: {DATE}
> **Dataset**: {DATASET_NAME} ({DATASET_ROWS:,} registros, {DATASET_COLS} columnas)
> **Total experimentos**: {TOTAL_EXPERIMENTS} en {TOTAL_PHASES} fases
> **Métrica guía**: AUC (Area Under ROC Curve)
> **Resultado principal**: AUC test = **{BEST_AUC}** (modelo {MODEL_CLASS})

---

<!-- SECCIÓN EJECUTIVA -->

## Resumen Ejecutivo

### Resultado principal

El modelo ganador de esta versión alcanza un **AUC de {BEST_AUC}** en el conjunto de test, lo que significa que de cada 100 pares (fraude vs. no fraude), el modelo ordena correctamente el caso fraudulento ~{BEST_AUC_PCT} veces. Comparado con el azar (50%), esto representa una mejora sustancial en la capacidad de priorización de inspecciones.

| Métrica | Valor | Interpretación |
|---------|-------|----------------|
| **AUC** | **{BEST_AUC}** | De cada 100 pares, el modelo identifica correctamente ~{BEST_AUC_PCT}. |
| **Recall** | **{BEST_RECALL}** | De cada 100 fraudes reales, el modelo detecta ~{BEST_RECALL_PCT}. |
| **Precisión** | **{BEST_PRECISION}** | De cada 100 clientes marcados, ~{BEST_PRECISION_PCT} son fraude real. |
| **F1** | **{BEST_F1}** | Balance entre precisión y recall. |

### {COMPARATIVE_HEADER_IF_AVAILABLE}

{COMPARATIVE_SUMMARY_IF_AVAILABLE}

{SKIP_COMPARATIVE_IF_NO_PREVIOUS_VERSION}

### Recomendación operativa

- **Inspeccionar el top {SWEET_SPOT_PCT}% del ranking**: captura ~{SWEET_SPOT_FRAUD_PCT}% de los fraudes con {SWEET_SPOT_INSPECTIONS} inspecciones.
- **Threshold sugerido**: {THRESHOLD} (definido por análisis costo-beneficio).
- **Retraining**: mensual con nuevos resultados de inspección.

---

<!-- SECCIÓN TÉCNICA -->

## 1. Características del Experimento

### 1.1 Qué se probó

Se ejecutaron **{TOTAL_EXPERIMENTS} experimentos** en **{TOTAL_PHASES} fases**:

| Fase | Objetivo | Experimentos | Hipótesis principal |
|------|----------|--------------|---------------------|
| 1 | Baselines | {PHASE1_COUNT} | ¿Cuál modelo base funciona mejor sin feature engineering? |
| 2 | Sampling | {PHASE2_COUNT} | ¿Reduce el desbalance de clases el error? |
| 3 | Feature Engineering | {PHASE3_COUNT} | ¿Qué transformaciones agregan señal? |
| 4 | Encoding | {PHASE4_COUNT} | ¿Qué encoding funciona mejor para las categóricas? |
| 5 | Selección de variables | {PHASE5_COUNT} | ¿Eliminar variables ruidosas mejora la generalización? |
| 6 | Tuning | {PHASE6_COUNT} | ¿Optimizar hiperparámetros mejora sobre el config manual? |
| 7 | Calibración | {PHASE7_COUNT} | ¿Ajustar el threshold mejora el balance precision/recall? |
| 8 | Ensamble | {PHASE8_COUNT} | ¿Combinar modelos mejora sobre el mejor individual? |

### 1.2 Qué resultó

Los experimentos que superaron el baseline (AUC test > baseline + 0.001):

| Experimento | Fase | AUC test | Delta vs baseline | Driver |
|-------------|------|----------|-------------------|--------|
| {WINNER_NAME} | {WINNER_PHASE} | **{BEST_AUC}** | **{BEST_DELTA}** | {WINNER_DRIVER} |
{IMPROVED_ROWS}

### 1.3 Qué no resultó

Experimentos que no mejoraron el baseline (AUC test <= baseline + 0.001):

| Experimento | Fase | AUC test | Delta vs baseline | Razón probable |
|-------------|------|----------|-------------------|----------------|
{NO_IMPROVE_ROWS}

### 1.4 Mayor driver de performance

El **mayor salto de performance** provino de **{KEY_DRIVER_DESCRIPTION}**, con un incremento de **+{KEY_DRIVER_DELTA} AUC** respecto al baseline de la fase anterior.

{KEY_DRIVER_EXPLANATION}

---

## 2. Periodos de Datos

| Conjunto | Periodo | Registros | Tasa de fraude |
|----------|---------|------------|----------------|
| Entrenamiento | {TRAIN_PERIOD} | {TRAIN_ROWS:,} | {TRAIN_FRAUD_RATE}% |
| Validación | {VAL_PERIOD} | {VAL_ROWS:,} | {VAL_FRAUD_RATE}% |
| Test | {TEST_PERIOD} | {TEST_ROWS:,} | {TEST_FRAUD_RATE}% |

- **Método de split**: {SPLIT_METHOD}
- **Columna de fecha**: {DATE_COLUMN}
- **Estrategia de balanceo**: {SAMPLING_METHOD}
{STRATIFICATION_DETAILS}
{UNLABELED_NEGATIVES_DETAILS}

---

## 3. Características del Modelo Ganador

### 3.1 Tipo de modelo y sampling

| Característica | Valor |
|----------------|-------|
| **Modelo** | {MODEL_CLASS} |
| **Modelo interno** | {INNER_MODEL} |
| **Sampling** | {SAMPLING_METHOD} (threshold: {SAMPLING_THRESHOLD}) |
| **Class weight** | {CLASS_WEIGHT} |
| **Ensamble** | {ENSEMBLE_INFO} |

### 3.2 Pipeline de feature engineering

**Preprocessing por columna:**

| Columna | Transformación | Parámetros |
|---------|---------------|------------|
{FE_COLUMNS_TABLE}

**Transformadores globales:**

| Transformador | Parámetros |
|---------------|------------|
{GLOBAL_TRANSFORMERS_TABLE}

**Selección de variables:**

{FEATURE_SELECTION_INFO}

### 3.3 Hiperparámetros

```yaml
{HYPERPARAMS_YAML}
```

### 3.4 Features finales

Total: **{N_FEATURES}** features

{TOP_FEATURES_LIST}

---

## 4. Resultados del Modelo Ganador

### 4.1 Métricas principales

| Métrica | Valor |
|---------|-------|
| AUC (validación) | {AUC_VAL} |
| AUC (test) | {BEST_AUC} |
| Diff AUC (val − test) | {AUC_DIFF} |
| Precisión | {BEST_PRECISION} |
| Recall | {BEST_RECALL} |
| F1 | {BEST_F1} |
| Threshold | {THRESHOLD} |
| Accuracy | {ACCURACY} |

{OVERFITTING_ASSESSMENT}

### 4.2 Matriz de confusión (test)

| | Predicción: No fraude | Predicción: Fraude |
|---|---|---|
| **Real: No fraude** | {TN:,} (TN) | {FP:,} (FP) |
| **Real: Fraude** | {FN:,} (FN) | {TP:,} (TP) |

- Tasa de falsos positivos: **{FP_RATE}%** ({FP:,} de {TN+FP:,} legítimos marcados)
- Tasa de falsos negativos: **{FN_RATE}%** ({FN:,} de {FN+TP:,} fraudes no detectados)

### 4.3 Curva de ganancia acumulada

| % clientes inspeccionados | % fraudes detectados | Ventaja vs azar |
|---------------------------|----------------------|-----------------|
{GAINS_TABLE_ROWS}

> Punto óptimo sugerido: inspeccionar el **{SWEET_SPOT_PCT}%** permite capturar **{SWEET_SPOT_FRAUD_PCT}%** de los fraudes.

### 4.4 Calibración

{CALIBRATION_SECTION}

### 4.5 Métricas por segmento

{SEGMENT_METRICS_SECTION}

---

## 5. Comparativa vs Versión Anterior

> Comparación contra **{PREV_VERSION}** (AUC test: {PREV_AUC}).

| Métrica | {PREV_VERSION} | {CURRENT_VERSION} | Delta |
|---------|----------------|-------------------|-------|
| AUC (test) | {PREV_AUC} | {BEST_AUC} | {AUC_DELTA:+.4f} |
| Precisión | {PREV_PRECISION} | {BEST_PRECISION} | {PREC_DELTA:+.4f} |
| Recall | {PREV_RECALL} | {BEST_RECALL} | {REC_DELTA:+.4f} |
| F1 | {PREV_F1} | {BEST_F1} | {F1_DELTA:+.4f} |

### Cambios principales vs {PREV_VERSION}

| Aspecto | {PREV_VERSION} | {CURRENT_VERSION} |
|---------|----------------|-------------------|
| Modelo | {PREV_MODEL} | {CURR_MODEL} |
| Features | {PREV_N_FEATURES} | {CURR_N_FEATURES} |
| Sampling | {PREV_SAMPLING} | {CURR_SAMPLING} |
| FE principales | {PREV_FE} | {CURR_FE} |

### Análisis del delta

{DELTA_ANALYSIS}

---

## Anexo: Tabla Completa de Experimentos

| # | Fase | Experimento | Modelo | AUC val | AUC test | Prec | Recall | F1 | Diff AUC | vs Baseline |
|---|------|-------------|--------|---------|----------|------|--------|-----|---------|-------------|
{FULL_EXPERIMENT_TABLE}

> **Nota**: "vs Baseline" compara contra el AUC test del primer experimento (fase1_exp1). ✅ = mejoró, ➖ = sin cambio significativo, ❌ = empeoró.