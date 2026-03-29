# Análisis Comparativo Actualizado: Aguas vs CELESC vs Energizados

> Fecha: 2026-03-29
> Objetivo: Re-evaluar los gaps identificados en `mejoras_aguas.md` contrastando con la implementación real del proyecto CELESC (proyecto productivo usando el framework Energizados), Generar un plan de implementación ajustado.

---

## Resumen Ejecutivo

El proyecto **CELESC** es una implementación productiva del framework Energizados para detección de fraude en distribución eléctrica (Santa Catarina, Brasil). A diferencia del POC Aguas (standalone), CELESC usa el framework directamente con ETLs custom, Esto cambia significativamente el análisis: **algunos gaps de `mejoras_aguas.md` ya fueron resueltos por CELESC**, otros persisten, y se identifican **nuevos gaps** que CELESC expone.

---

## 1. Re-evaluación de Gaps: mejoras_aguas.md vs CELESC

### 2.1 ETL Incremental Mensual — RE-EVALUACIÓN

**Veredicto: GAP PARCIALMENTE RESUELTO (pero no con incremental)**

CELESC NO implementa ETL incremental mensual con Hive-partitioned output. Sin embargo, resolvió el problema de ETL custom de forma más simple:

**Cómo lo resuelve CELESC:**
- Crea ETLs custom que extienden `SourceETL`: `ConsumosETL`, `InspeccionesETL`, `MaestrosETL`
- Cada ETL overridea `transform()` con lógica de limpieza domain-specific
- Usa glob patterns en input (`data/raw/v0/consumo*.csv`) para leer múltiples archivos
- El framework maneja la concatenación automáticamente vía `SourceETL`

**Qué sigue faltando:**
- ❌ Procesamiento incremental (comparar raw vs interim y solo procesar pendientes)
- ❌ Estructura Hive-partitioned (`year=*/month=*/`)
- ❌ `overwrite` flag para reprocesar

**Qué ya NO hace falta:**
- ✅ Funciones de limpieza configurables por fuente → CELESC demuestra que extender `SourceETL` con `transform()` custom es el patrón correcto
- ✅ Logging detallado → ya funciona por herencia de `SourceETL`

**Conclusión:** El ETL incremental mensual de Aguas (Hive-partitioned, pendiente-only) es un caso de uso específico de EMCALI que tiene operación mensual. CELESC no lo necesita porque procesa datos estáticos (una foto de inspecciones, no flujo mensual). **El gap se reduce a: agregar soporte incremental como feature opcional del framework**, no como requisito fundamental.

---

### 2.2 Construcción de Dataset Wide Temporal — RE-EVALUACIÓN

**Veredicto: PARCIALMENTE RESUELTO con patrón diferente**

CELESC implementa `DatasetBuilderETL` — un ETL custom que hace el join + pivot long→wide. Pero el approach es diferente al de Aguas:

**Cómo lo resuelve CELESC (`dataset_builder_etl.py`, 187 líneas):**
- ✅ Recibe 3 parquets intermedios (maestros, consumos, inspecciones)
- ✅ Join inspecciones con consumos por cliente
- ✅ Filtra consumos anteriores a la inspección (`periodo_cons < periodo_insp`)
- ✅ Calcula rank (meses entre consumo e inspección) → `1_anterior`..`12_anterior`
- ✅ Pivot long→wide (consumo × rank → columnas `N_anterior`)
- ✅ Merge con maestros (atributos del cliente)
- ✅ `num_measures` y `num_measures_not_zero` como features auxiliares
- ✅ `fill_empty_values_cycle` (ffill/bfill) y `fill_empty_values_str`
- ✅ Filtro por geolocalización válida (lat/lon no NaN ni 0)
- ✅ `min_num_measures` y `min_num_measures_not_zero` como params configurables
- ✅ Ordenamiento de columnas (inspecciones → consumos → maestros)
- ✅ Se integra en el DAG del ETL (`depends_on: [maestros, consumos, inspecciones]`)

**Qué sigue faltando:**
- ❌ Features de proporción relativa por categoría (`prop_cons_ult3_mean_g`, etc.) — CELESC no tiene columna `categoria` en consumos
- ❌ Flags domain-specific por función/observación/causa — CELESC no tiene esos códigos
- ❌ `columns_filter` en inferencia (pre-tsfel) — no implementado
- ❌ Negatives sampling (`max_ctas_neg`) — CELESC usa inner join, no agrega negativos
- ❌ Separación train/inference dataset building — CELESC solo tiene dataset de train

**Qué ya NO hace falta:**
- ✅ `get_fecha_fraud_list()` → CELESC no necesita fechas de corte (usa split temporal del framework)
- ✅ `load_interim_data()` con filtrado temporal → CELESC usa un solo parquet por fuente
- ✅ `load_maestro_latest()` → CELESC usa un solo maestro
- ✅ Estadísticas por categoría (12m, 6m, 3m) → CELESC no tiene categoría en consumos

**Conclusión:** CELESC demuestra que el patrón correcto es un **ETL custom que extiende SourceETL**, no un step genérico del framework. El Dataset Builder es demasiado específico del dominio (campos, lógica de join, features auxiliares) para generalizarlo. **Pero el patrón de implementación debería documentarse como template/best practice.**

---

### 2.3 Preprocesamiento de Entrada del Modelo — RE-EVALUACIÓN

**Veredicto: RESUELTO por patrón diferente**

**Cómo lo resuelve CELESC:**
- ✅ Usa `drop_columns` en `preprocessing` para eliminar `latitude`, `longitude` antes del modelo
- ✅ Usa `cast_dtype` para convertir `cliente` a `category`
- ✅ La limpieza de strings se hace en los ETLs custom (no en pre-cleaning del modelo)
- ✅ No necesita derivación de columnas (`medidor_2`, `estrato`) porque no tiene esas columnas

**Qué sigue faltando:**
- ❌ Mecanismo genérico de `pre_cleaning` configurable en YAML (antes de column transformers)
- ❌ `ColumnDeriver` para derivar columnas nuevas desde existentes

**Qué ya NO hace falta:**
- ✅ `preprocess_model_input()` específico de EMCALI → no aplica a CELESC

**Conclusión:** El pre-cleaning es domain-specific. CELESC lo resuelve limpiando en los ETLs. **No es un gap prioritario del framework**, pero un mecanismo genérico de pre-cleaning sería un nice-to-have.

---

### 2.4 Config Operativa y Output Custom — RE-EVALUACIÓN

**Veredicto: MAYORÍA PARCIALMENTE RESUELTO**

**Cómo lo resuelve CELESC:**
- ✅ Scripts `src/run/00_etl.py`, `02_training.py`, `03_inference.py` — equivalentes a los scripts de Aguas
- ✅ CLI `energizados run train -n expXX` para nombrar experimentos
- ✅ 30+ configs de experimentos con descripción, dependencias y hipótesis documentadas
- ✅ `calibration` config en evaluación (cost_benefit con cost_fp/cost_fn)

**Qué sigue faltando:**
- ❌ `columns_filter` en inferencia — no implementado
- ❌ `output_columns` para personalizar CSV de scores — no implementado
- ❌ `contratos_list` en inferencia — no implementado
- ❌ Logging a archivo por ejecución — no implementado
- ❌ Flag `overwrite` en CLI — no implementado

**Qué ya NO hace falta:**
- ✅ Config simplificada para operación mensual — CELESC no tiene operación mensual

**Conclusión:** `columns_filter` y `output_columns` son los gaps más importantes. El resto es nice-to-have.

---

### 2.5 Configuración Granular de ConsumptionPatterns — SIN CAMBIO

**Veredicto: SIN CAMBIO — sigue siendo prioridad BAJA**

CELESC usa `consumption_patterns` como global transformer con los params default (`num_periodos: 12`, `periods_suffix: "_anterior"`). No necesita la configuración granular de `CONFIG_CAIDAS` / `CONFIG_CONSTANTES` porque el framework ya tiene `ConsumptionPatterns` con features más avanzados.

---

## 2. Nuevos Gaps Identificados en CELESC

### N1. Inferencia Productiva (Prioridad ALTA)

CELESC tiene `infer.yaml` con `enabled: false` y un `03_inference.py` que requiere `--run-dir` manual. No hay:

- ❌ Pipeline de inferencia end-to-end: nuevo dataset → scoring → CSV
- ❌ `columns_filter` para filtrar contratos antes de feature engineering costoso (tsfel)
- ❌ `output_columns` para personalizar el CSV de scores
- ❌ `contratos_list` para scorer solo ciertos contratos
- ❌ Integración automática con el output del entrenamiento (model + feature_engineering)

### N2. Experimentación Sistemática (Prioridad MEDIA — ya resuelto, documentar)

CELESC demuestra un patrón de experimentación excelente con 30+ configs:

```
exp01-lgbm-vanilla          → Baseline
exp02-catboost-vanilla      → Comparar modelos
exp03-simple-trend           → Modelos simples
exp04-simple-constant        → Modelos simples
exp05-lgbm-encoding          → Encoding strategies
exp06-undersample            → Sampling
exp07-oversample             → Sampling
exp08-smotetomek             → Sampling avanzado
exp09-class-weight           → Class weight
exp10-clip-outliers          → Preprocessing
exp11-extra-vars             → Feature engineering
exp12-consumption-patterns   → Feature engineering
exp13-extra-plus-patterns    → Feature engineering combinado
exp14-tsfel                  → Feature engineering avanzado
exp15-geo-hierarchy          → Geo features
exp16-kitchen-sink           → Todo junto
exp17-all-target-enc         → Encoding alternativo
exp18-dummy-plus-te          → Encoding combinado
exp19-cardinality-thresholds → Cardinality tuning
exp20-drop-constant          → Feature selection
exp21-drop-constant-corr     → Feature selection combinado
exp22-boruta                 → Feature selection avanzado
exp23-selection-pipeline     → Selection pipeline completo
exp24-lgbm-tuned             → Hyperparameter tuning
exp25-catboost-tuned         → Hyperparameter tuning
exp26-neural-network         → Neural networks
exp27-lstm                  → LSTM
exp28-threshold-calibration  → Threshold optimization
exp29-prob-calibration       → Probability calibration
exp30-stacking-ensemble      → Ensemble
```

**Esto debería documentarse como best practice / template.**

### N3. Normalización de Strings (Prioridad BAJA)

CELESC usa `normalize_strings()` de `data/_utils.py` que a su vez usa `normalize_text()` del framework. Esto demuestra que el framework necesita una utility de normalización de texto accesible desde ETLs custom.

**Verificar si ya existe:** `energizados.core.utils.strings.normalize_text` — CELESC lo usa, Si existe, no es un gap, pero debería documentarse mejor.

### N4. Config Versioning (Prioridad BAJA — ya resuelto)

CELESC usa `config/v0/` como directorio de versión. Esto es un buen patrón para evolucionar configs sin perder las anteriores.

---

## 3. Plan de Implementación Actualizado

### Fase 1: Inferencia Productiva (Prioridad ALTA) — NUEVA

**Qué:** Implementar pipeline de inferencia end-to-end con `columns_filter`, `output_columns` y `contratos_list`.

**Requisitos:**
- `columns_filter` en `infer.yaml`: filtra contratos por valores de columnas antes de feature engineering costoso (tsfel)
- `output_columns` en `infer.yaml`: personaliza columnas del CSV de scores
- `contratos_list` en `infer.yaml`: filtro por lista de contratos
- Integración automática con el último run de entrenamiento (auto-detect model + feature_engineering)
- Script `03_inference.py` que no requiera `--run-dir` manual

**Config YAML propuesta:**
```yaml
infer:
  enabled: true
  input_path: "data/processed/new_data.parquet"
  model_path: null  # auto-detect latest from output/
  feature_engineering_path: null  # auto-detect latest from output/
  threshold: 0.5
  columns_filter:  # opcional — filtra ANTES de tsfel
    zona: ["FLORIANOPOLIS"]
  contratos_list: null  # null = todos
  output_columns: [cliente, actividad, tipo_tarifa, zona, score]
  output_path: "output/predictions.csv"
```

**Archivos a crear/modificar:**
- `src/energizados/inference/default.py` → columns_filter, output_columns, contratos_list
- `src/energizados/cli/run.py` → auto-detect latest run
- Templates `config/infer.yaml` → nuevas opciones

**Estimación:** ~150-200 líneas nuevas/modificadas

---

### Fase 2: ETL Incremental Mensual (Prioridad ALTA → MEDIA) — AJUSTADA

**Qué:** Agregar `IncrementalETL` como feature opcional del framework.

**Ajuste respecto a mejoras_aguas.md:**
- CELESC demuestra que el patrón "extender SourceETL con transform() custom" funciona bien
- El incremental mensual es específico de EMCALI (operación mensual), no de todos los proyectos
- Se baja la prioridad de ALTA a MEDIA y se simplifica el scope

**Requisitos (simplificados):**
- Modo `incremental` en `SourceETL` o nuevo `IncrementalETL`
- Comparar archivos raw vs interim existentes
- Solo procesar meses pendientes
- Estructura de salida Hive-partitioned opcional
- `overwrite` flag

**Estimación:** ~200-250 líneas nuevas

---

### Fase 3: Dataset Builder Template (Prioridad ALTA → MEDIA) — AJUSTADA

**Qué:** Documentar el patrón `DatasetBuilderETL` como template/best practice, no implementarlo en el framework.

**Ajuste respecto a mejoras_aguas.md:**
- CELESC demuestra que el Dataset Builder es demasiado domain-specific para generalizarlo
- El patrón correcto es: ETL custom que extiende SourceETL, con lógica de join+pivot
- No vale la pena crear un `WideDatasetETL` genérico
- **En su lugar:** crear documentación/template que muestre cómo implementarlo

**Requisitos:**
- Template de `DatasetBuilderETL` en la documentación del framework
- Guía de cómo extender `SourceETL` para joins + pivots custom
- Ejemplo funcional basado en CELESC

**Estimación:** ~100-150 líneas de documentación + template

---

### Fase 4: Pre-cleaning y Column Derivation (Prioridad MEDIA → BAJA) — AJUSTADA

**Qué:** Agregar mecanismo de `pre_cleaning` configurable como nice-to-have.

**Ajuste:**
- CELESC demuestra que la limpieza se hace mejor en los ETLs custom
- El pre-cleaning del modelo es domain-specific
- Se baja prioridad de MEDIA a BAJA

**Requisitos (simplificados):**
- `pre_cleaning` step opcional en `feature_engineering`
- Operaciones básicas: split, conditional fillna, strip

**Estimación:** ~100-150 líneas nuevas

---

### Fase 5: Config Operativa (Prioridad MEDIA) — SIN CAMBIO

Permanece igual que en `mejoras_aguas.md`:
- Logging a archivo por ejecución
- Flag `overwrite` en CLI

**Nota:** `columns_filter`, `output_columns` y `contratos_list` se mueven a Fase 1 (Inferencia).

**Estimación:** ~100 líneas nuevas/modificadas

---

### Fase 6: ConsumptionPatterns Granular (Prioridad BAJA) — SIN CAMBIO

Permanece igual. Prioridad BAJA.

---

## 4. Comparativo Final: mejoras_aguas.md vs mejoras_aguas2.md

| Gap original (mejoras_aguas.md) | Estado en CELESC | Nueva prioridad | Acción |
|---|---|---|---|
| 2.1 ETL Incremental Mensual | **No implementado** (CELESC usa SourceETL custom) | ALTA → **MEDIA** | Simplificar: opcional, no fundamental |
| 2.2 Dataset Wide Temporal | **Resuelto** por `DatasetBuilderETL` custom | ALTA → **MEDIA** (documentar) | Documentar patrón como template |
| 2.3 Pre-cleaning Modelo | **Resuelto** por limpieza en ETLs | MEDIA → **BAJA** | Nice-to-have, no prioritario |
| 2.4 Config Operativa | **Parcial** (CLI + scripts, sin columns_filter/output_columns) | MEDIA → **Ver Fase 1+5** | Split entre inferencia y config |
| 2.5 ConsumptionPatterns config | Sin cambio | BAJA | Sin cambio |
| — | **NUEVO: Inferencia productiva** | **ALTA** | Pipeline end-to-end |
| — | **NUEVO: Experimentación sistemática** | **Documentar** | Template de 30+ experimentos |

---

## 5. Priorización y Dependencias Actualizadas

```
Fase 1 (Inferencia Productiva) ─────── ALTA, independiente
     │
Fase 2 (ETL Incremental opcional) ─── MEDIA, independiente
     │
Fase 3 (Dataset Builder template) ─── MEDIA, documentación
     │
Fase 4 (Pre-cleaning) ───────────── BAJA, independiente
     │
Fase 5 (Config Operativa) ──────── MEDIA, independiente
     │
Fase 6 (ConsumptionPatterns) ───── BAJA, independiente
```

**Orden recomendado de implementación:**
1. **Fase 1: Inferencia Productiva** — Mayor impacto, independencia
2. **Fase 5: Config Operativa** (logging, overwrite) — Complementa Fase 1
3. **Fase 3: Dataset Builder template** — Documentación, habilita nuevos proyectos
4. **Fase 2: ETL Incremental opcional** — Para proyectos con operación mensual
5. **Fase 4: Pre-cleaning** — Nice-to-have
6. **Fase 6: ConsumptionPatterns granular** — Nice-to-have

---

## 6. Estimación de Esfuerzo Actualizada

| Fase | Líneas nuevas/modificadas | Complejidad | Prioridad | Cambio vs v1 |
|---|---|---|---|---|
| Fase 1: Inferencia Productiva | ~150-200 | Media | **ALTA** | **NUEVA** |
| Fase 2: ETL Incremental | ~200-250 | Media | MEDIA | ↓ ALTA→MEDIA |
| Fase 3: Dataset Builder template | ~100-150 (docs) | Baja | MEDIA | ↓ ALTA→MEDIA (docs) |
| Fase 4: Pre-cleaning | ~100-150 | Media | BAJA | ↓ MEDIA→BAJA |
| Fase 5: Config Operativa | ~100 | Baja | MEDIA | Sin cambio |
| Fase 6: ConsumptionPatterns | ~50-80 | Baja | BAJA | Sin cambio |
| **Total código** | **~700-930** | | | ↓ de ~900-1230 |

---

## 7. Lecciones Aprendidas de CELESC

### 7.1 Patrones de Implementación Validados

1. **Extender `SourceETL` con `transform()` custom es el patrón correcto** para ETLs domain-specific. No hace falta crear nuevas clases base.

2. **El Dataset Builder es un ETL más, no un step especial.** Se integra naturalmente en el DAG: `maestros → consumos → inspecciones → dataset_builder → geo_features`.

3. **La experimentación sistemática con configs numeradas** (`exp01`, `exp02`, ...) + descripción + hipótesis documentada es una práctica excelente que debería ser template del framework.

4. **`CleanFilesETL` para limpiar intermedios** — CELESC lo usa para eliminar maestros, consumos e inspecciones después del dataset_builder. Excelente patrón.

5. **`_utils.py` compartido entre ETLs** — Normalización de strings compartida via `normalize_text()` del framework.

### 7.2 Lo que CELESC NO necesita (validación del framework)

- ✅ El framework cubre TODO el pipeline de ML: split, feature engineering, entrenamiento, evaluación
- ✅ Los ETLs custom se integran limpiamente vía `custom_class` en YAML
- ✅ `@references` en input funcionan para conectar ETLs
- ✅ `depends_on` maneja el DAG correctamente
- ✅ 30+ experimentos demuestran que el sistema de config es flexible y potente
- ✅ `GeoFeaturesETL` funciona correctamente con custom lat/lon columns
- ✅ `ClipOutliersETL` está disponible (aunque CELESC lo comenta, los consumos no son extremos)
- ✅ Calibration (cost_benefit) está integrado en evaluación

### 7.3 Lo que CELESC NECESITA y no tiene

1. **Pipeline de inferencia productivo** — El `infer.yaml` está deshabilitado, `03_inference.py` requiere `--run-dir` manual
2. **`columns_filter`** — Para filtrar contratos por zona/región antes de feature engineering costoso
3. **`output_columns`** — Para personalizar el CSV de scores con columnas del negocio

---

## 8. Notas Adicionales

- CELESC usa `config/v0/` como versionado de configs. El framework debería soportar esto nativamente o documentarlo como best practice.
- Los notebooks de CELESC (`01_exploracion_consumo.ipynb`, etc.) usan ETLs y datos intermedios para exploración. Esto valida que guardar parquets intermedios es valioso.
- CELESC no usa EDA del framework (`eda.yaml` existe pero no se exploró su contenido). Podría ser un gap futuro.
- El `03_inference.py` carga el modelo con `pickle.load()` nativo en lugar de `secure_load()` del framework — debería actualizarse.
- `CustomModel`, `CustomInference` y `CustomSelector` son stubs sin implementar — CELESC usa los modelos built-in del framework (LightGBM, CatBoost, etc.)
