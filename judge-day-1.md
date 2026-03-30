# Judgment Day — Energizados ML Framework

**Fecha**: 2026-03-30  
**Target**: `src/energizados/` + `tests/` (~135 archivos Python)  
**Jueces**: 2 lanzados en paralelo (Judge B: timeout, Judge A: completo)  
**Skill Resolution**: injected — Project Standards from `.atl/skill-registry.md`

---

## Resumen Ejecutivo

| Severidad | Total | Verdaderos | Parciales | Falsos Positivos | Fixes Aplicados |
|-----------|-------|------------|-----------|------------------|-----------------|
| CRITICAL  | 8     | 0          | 0         | 6                | 2               |
| WARNING   | 8     | 5          | 1         | 1                | 0               |
| SUGGESTION| 6     | 4          | 1         | 1                | 0               |
| **Total** | **22**| **9**      | **2**     | **8**            | **2**           |

**Issues reales pendientes de fix**: 11 (9 verdaderos + 2 parciales)

---

## Round 1 — Veredicto

| # | Finding | Severidad | Archivo |
|---|---------|-----------|---------|
| 1 | `secure_load()` usa `pickle.load()` raw cuando `.sig` falta o `trust_pickle=True` | CRITICAL | `secure_pickle.py:46-81` |
| 2 | `trust_pickle=True` bypasea verificación de integridad silenciosamente | CRITICAL | `secure_pickle.py:67` |
| 1 | `secure_load()` usa `pickle.load()` raw cuando `.sig` falta o `trust_pickle=True` | ~~CRITICAL~~ FALSO POSITIVO | `core/utils/secure_pickle.py` — NO existe `trust_pickle`, `.sig` ausente levanta `FileNotFoundError` |
| 2 | `trust_pickle=True` bypasea verificación de integridad silenciosamente | ~~CRITICAL~~ FALSO POSITIVO | `core/utils/secure_pickle.py` — parámetro `trust_pickle` NO EXISTE en todo el codebase |
| 3 | `MinMaxScalerRow.transform` crea scaler por CADA FILA — O(n²) | ~~CRITICAL~~ FALSO POSITIVO | `preprocessing/preprocessing.py` — usa transpose trick vectorizado, no O(n²) |
| 4 | `MinMaxScalerRow` — filas all-zero producen features all-zero, rompe threshold 0.5 | ~~CRITICAL~~ FALSO POSITIVO | `preprocessing/preprocessing.py` — comportamiento correcto de sklearn |
| 5 | `EnsembleModel._clone_model` — filtro vacío copia estado corrupto | ~~CRITICAL~~ FIX APLICADO | `modeling/ensemble.py:161-182` — filtro era correcto, agregado logging de fallback |
| 6 | `_clone_model` copia estado interno (`_step_selectors`, `_pipe_features`) que no debería | ~~CRITICAL~~ FALSO POSITIVO | `modeling/ensemble.py:161-182` — filtro excluye `_` attrs correctamente |
| 7 | `cli/run.py:65` — `__import__("logging")` dentro de loop | ~~CRITICAL~~ FIX APLICADO | `cli/run.py` — reemplazado con `import logging` + logger module-level |
| 8 | Training step usa `pickle.dump` raw sin `.sig` para modelo | ~~CRITICAL~~ FALSO POSITIVO | `core/steps/training.py` — ya usa `secure_dump` en líneas 248, 477, 621 |
| 9 | Adapters usan threshold hardcoded 0.5 en `predict()`, no configurable | WARNING — pendiente | `modeling/adapters.py:859-968` |
| 10 | `X[self.cols_for_model]` ignora columnas nuevas de feature engineering | WARNING — pendiente | `modeling/adapters.py:105,225,344,568` |
| 11 | Duplicación de `_load_yaml_config` en `core/pipeline.py` y `core/builders/director.py` | ~~WARNING~~ FIX APLICADO | Extraído a `core/utils/yaml_utils.py` |
| 12 | `Pipeline.context` mutado via lambda closure — leak de estado entre steps | WARNING — pendiente | `core/pipeline.py:168` |
| 13 | `TeEncoder.transform` puede reordenar columnas silenciosamente | ~~WARNING~~ FALSO POSITIVO | Retorna `.values` numpy, índice irrelevante |
| 14 | Bug precedence en `normalize_text`: `(replace_null and text)` short-circuitea incorrectamente | ~~WARNING~~ FIX APLICADO | `replace_null is not None and (...)` — precedencia corregida |
| 15 | `XGBClassifier` usa `use_label_encoder=False` deprecado | ~~WARNING~~ FIX APLICADO | Parámetro eliminado — rompía en XGBoost >= 2.0 |
| 16 | `cli/run.py:449` accede a privado `_director.run_manager._run_dir` rompiendo encapsulación | WARNING — pendiente | `cli/run.py:451-454` |
| 17 | `PipelineError` envuelve excepción sin `from e`, pierde traceback original | ~~SUGGESTION~~ FIX APLICADO | `raise PipelineError(...) from e` |
| 18 | `SPLIT_SCHEMA` no incluye `stratified_time` como método válido | ~~SUGGESTION~~ FIX APLICADO | `"stratified_time"` agregado al enum |
| 19 | `ENSEMBLE_SCHEMA` lista `weighted_voting` pero no existe implementación en código | ~~SUGGESTION~~ FIX APLICADO | `"weighted_voting"` eliminado del schema y del test |
| 20 | Error handling en `BaseETL.run()` re-envuelve `ETLError` perdiendo causa original | ~~SUGGESTION~~ FIX APLICADO | `raise ETLError(...) from e` |
| 21 | `get_preprocesor()` raise `ValueError` confuso cuando columns es dict vacío `{}` | ~~SUGGESTION~~ FALSO POSITIVO | `{}` sin key `columns` no entra al bloque — lógica correcta |
| 22 | Stacking con `use_val_as_oof=True` re-entrena redundantemente datos de validación | SUGGESTION | `modeling/ensemble.py:89-93` |

---

## Detalle de Hallazgos

### CRITICAL

#### 1. `secure_load()` — Pickle sin verificación cuando `.sig` falta o `trust_pickle=True`

- **Archivo**: `src/energizados/core/utils/secure_pickle.py:46-81`
- **Descripción**: `secure_load()` usa `pickle.load()` raw cuando el archivo `.sig` no existe o cuando `trust_pickle=True`. Un atacante podría reemplazar un archivo de modelo legítimo con uno malicioso y simplemente eliminar el `.sig` para bypassar la verificación.
- **Fix sugerido**: Hacer obligatoria la verificación `.sig` en producción, eliminar `trust_pickle=True` como opción por defecto, o fallar explícitamente cuando `.sig` falta.

#### 2. `trust_pickle=True` bypasea integridad silenciosamente

- **Archivo**: `src/energizados/core/utils/secure_pickle.py:67`
- **Descripción**: Cualquier caller puede pasar `trust_pickle=True` para saltear la verificación de integridad. Esto da una falsa sensación de seguridad — el sistema está diseñado para ser seguro pero permite bypass silencioso.
- **Fix sugerido**: Eliminar el flag `trust_pickle` o requiring explicit audit logging cuando se usa.

#### 1. ~~`secure_load()` pickle sin verificación~~ → FALSO POSITIVO

- **Archivo**: `src/energizados/core/utils/secure_pickle.py:46-85`
- **Descripción original**: `secure_load()` usa `pickle.load()` raw cuando `.sig` falta o `trust_pickle=True`
- **Realidad**: `secure_load()` levanta `FileNotFoundError` si `.sig` no existe (línea 70-74). Levanta `ValueError` si hash no coincide (línea 78-82). El parámetro `trust_pickle` NO EXISTE en todo el codebase (búsqueda global: 0 resultados). Solo carga DESPUÉS de verificar integridad con SHA-256.
- **Acción**: Cerrado. No aplica.

#### 2. ~~`trust_pickle=True` bypasea integridad~~ → FALSO POSITIVO

- **Archivo**: `src/energizados/core/utils/secure_pickle.py`
- **Descripción original**: Cualquier caller puede pasar `trust_pickle=True` para saltear verificación
- **Realidad**: El parámetro `trust_pickle` NO EXISTE. La función `secure_load()` no acepta ningún parámetro que pueda bypasear la verificación. El juez inventó este parámetro.
- **Acción**: Cerrado. No aplica.

#### 3. ~~`MinMaxScalerRow.transform` — O(n²)~~ → FALSO POSITIVO

- **Archivo**: `src/energizados/preprocessing/preprocessing.py:381-402`
- **Descripción original**: `MinMaxScalerRow.transform` crea scaler por cada fila (O(n²))
- **Realidad**: El código usa `scaler.fit_transform(X.T).T` — transpone, fittea UN scaler, transpone de vuelta. Es vectorizado y O(n). No hay loop por fila.
- **Acción**: Cerrado. No aplica.

#### 4. ~~`MinMaxScalerRow` — filas all-zero~~ → FALSO POSITIVO

- **Archivo**: `src/energizados/preprocessing/preprocessing.py:381-402`
- **Descripción original**: Filas constantes producen all-zero, rompe threshold 0.5
- **Realidad**: `MinMaxScaler` con `feature_range=(0,1)` produce `[0, 0, ...]` para filas constantes. Esto es comportamiento estándar y documentado de sklearn. No "rompe" nada — es predecible y consistente.
- **Acción**: Cerrado. Enhancement futuro posible (usar 0.5 para constant rows).

#### 5. ~~`EnsembleModel._clone_model` — filtro corrupto~~ → FIX APLICADO

- **Archivo**: `src/energizados/modeling/ensemble.py:161-182`
- **Descripción original**: Filtro `if not k:` siempre vacío, copia estado corrupto
- **Realidad**: El código usa `if not k.startswith("_") and k not in ("is_fitted_", "model_", "config")` — el filtro es correcto. El juez vio mal el código.
- **Problema real encontrado**: `sklearn_clone()` SIEMPRE falla para los adapters (no implementan `get_params()`), y la excepción se swallowed silenciosamente.
- **Fix aplicado**: Agregado `logger.debug()` cuando cae al fallback, mejorada documentación del método.
- **Tests**: 16/16 pasan.

#### 6. ~~`_clone_model` copia estado interno~~ → FALSO POSITIVO

- **Archivo**: `src/energizados/modeling/ensemble.py:161-182`
- **Descripción original**: Re-instancia usando `model.__dict__` que incluye estado fitted
- **Realidad**: El filtro `if not k.startswith("_")` excluye correctamente todos los atributos internos (`_model`, `_trained_pipeline`, `_meta_learner`, etc.). Verificado con `LGBMModelAdapter` real: solo pasan init params públicos.
- **Acción**: Cerrado. No aplica.

#### 7. ~~`__import__("logging")` en CLI~~ → FIX APLICADO

- **Archivo**: `src/energizados/cli/run.py:65`
- **Descripción original**: `merge_configs()` usa `__import__("logging").getLogger(__name__)` dentro de un loop, creando un nuevo logger en cada iteración. El archivo no tenía `import logging` a nivel módulo.
- **Fix aplicado**: Agregado `import logging` a nivel módulo, creado `logger = logging.getLogger(__name__)` a nivel módulo, eliminado `__import__("logging")` del loop.
- **Tests**: 77/77 pasan.

#### 8. ~~Training step usa pickle.dump raw~~ → FALSO POSITIVO

- **Archivo**: `src/energizados/core/steps/training.py`
- **Descripción original**: Training step usa `pickle.dump()` directamente, sin `.sig` de integridad
- **Realidad**: Training step importa y usa `secure_dump` (línea 15) en líneas 248, 477, 621. Todos los modelos y feature engineering se guardan con integridad SHA-256 verificada.
- **Acción**: Cerrado. No aplica.

#### 7. `__import__("logging")` dentro de loop en CLI

- **Archivo**: `src/energizados/cli/run.py:65`
- **Descripción**: `merge_configs()` usa `__import__("logging").getLogger(__name__)` dentro del cuerpo de un loop. Esto es un anti-pattern: overhead innecesario, código feo, y no sigue la convención del proyecto de usar `logging` a nivel módulo.
- **Fix sugerido**: Crear el logger a nivel módulo: `logger = logging.getLogger(__name__)`.

#### 8. Training step usa `pickle.dump` sin integridad

- **Archivo**: `src/energizados/core/steps/training.py`
- **Descripción**: El training step guarda modelos y feature engineering con `pickle.dump()` directamente, sin usar `secure_dump()` que genera el archivo `.sig`. Esto significa que los modelos entrenados NO tienen verificación de integridad.
- **Fix sugerido**: Reemplazar `pickle.dump()` con `secure_dump()` en el training step.

---

### WARNING

#### 9. Threshold hardcoded 0.5 en todos los adapters — VERDADERO

- **Archivo**: `src/energizados/modeling/adapters.py:859-968`
- **Descripción**: Todos los adapters (LGBM, CAT, XGB, NN, LSTM, IsolationForest) usan threshold 0.5 hardcoded en `predict()`. El threshold debería ser configurable desde config o inyectable vía context durante evaluación.
- **Verificación**: Confirmado. Todos los `predict()` usan `> 0.5` literal. `sampling_th` controla resampling en training, NO el threshold de clasificación. No hay forma de cambiar el boundary en inferencia.
- **Fix sugerido**: Recibir threshold como parámetro de config, con default 0.5.

#### 10. `X[self.cols_for_model]` ignora columnas nuevas — VERDADERO

- **Archivo**: `src/energizados/modeling/adapters.py:105,225,344,568`
- **Descripción**: Todos los adapters filtran columnas con `X[self.cols_for_model]` en `predict()` y `predict_proba()`. Si feature engineering agregó columnas nuevas, estas se ignoran silenciosamente. Si se eliminaron columnas, causa `KeyError`.
- **Verificación**: Confirmado. Cada adapter hace subset ciego a `self.cols_for_model`. Columnas nuevas se descartan sin warning, sin logging, sin validación.
- **Fix sugerido**: Loggear warning cuando hay mismatch entre columnas esperadas y disponibles.

#### 11. Duplicación de `_load_yaml_config` — VERDADERO

- **Archivo**: `src/energizados/core/pipeline.py:28-49` y `src/energizados/core/builders/director.py:28-49`
- **Descripción**: La función `_load_yaml_config` está duplicada en dos archivos. Cambios en uno no se reflejan en el otro.
- **Verificación**: Confirmado. Ambas funciones son byte-a-byte idénticas. `director.py` NO importa de `pipeline.py`. Cada una define la función independientemente.
- **Fix sugerido**: Extraer a un módulo compartido en `core/utils/`.

#### 12. `Pipeline.context` mutado via lambda — PARCIALMENTE VERDADERO

- **Archivo**: `src/energizados/core/pipeline.py:167-171`
- **Descripción original**: `Pipeline.__init__` guarda un lambda en `context["_on_phase_update"]` que captura `self` por closure. Cualquier step puede modificar `self.context` en medio de la ejecución de otro step, creando acoplamiento implícito y potencial corrupción de estado.
- **Verificación**: La lambda y la captura de `self` son reales. Sin embargo, el vector de corrupción real es el dict mutable compartido entre iteraciones (`self.context = step.execute(self.context)` reasigna en cada paso), no específicamente la lambda. Un step que retenga referencia al dict previo y lo mute después de retornar pierde esos cambios. La lambda es un code smell (acoplamiento implícito), pero no es la fuente directa de corrupción.
- **Fix sugerido**: Usar un mecanismo de eventos separado del context dict.

#### 13. ~~`TeEncoder.transform` reordena columnas~~ → FALSO POSITIVO

- **Archivo**: `src/energizados/preprocessing/preprocessing.py:214-223`
- **Descripción original**: `TeEncoder.transform()` usa `X_copy.merge()` (left-join) que puede reordenar los índices del DataFrame.
- **Realidad**: El método retorna `X_copy[[self.te_var_name]].values` — un array numpy, no un DataFrame. El índice se descarta completamente al retornar. Además, `how="left"` preserva el orden de filas del lado izquierdo. El finding no aplica.
- **Acción**: Cerrado. No aplica.

#### 14. Bug precedence en `normalize_text` — VERDADERO

- **Archivo**: `src/energizados/core/utils/strings.py:7`
- **Descripción**: La expresión `if replace_null and pd.isna(text) or text in ("nan", "None", "")` tiene bug de precedencia. `and` binds más fuerte que `or`, así que parsea como `(replace_null and pd.isna(text)) or (text in (...))`.
- **Verificación**: Confirmado. Cuando `replace_null=""` (falsy) y `text` es un `NaN` real de pandas, la primera cláusula short-circuitea a falsy, la segunda es `False` (NaN no está en la tupla de strings). La función cae al `str(text).strip()` y retorna `"nan"` en vez del valor de reemplazo esperado.
- **Fix sugerido**: Reescribir como `if replace_null is not None and (pd.isna(text) or text in ("nan", "None", ""))`.

#### 15. XGBoost deprecated `use_label_encoder=False` — VERDADERO

- **Archivo**: `src/energizados/modeling/supervised_models.py:496`
- **Descripción**: `XGBClassifier` usa `use_label_encoder=False` que fue deprecado en XGBoost 1.6 y **removido en XGBoost 2.0** (causa `TypeError`).
- **Verificación**: Confirmado en línea 496. Esto ROMPE en runtime con XGBoost >= 2.0.
- **Fix sugerido**: Eliminar el parámetro (ya no es necesario en XGBoost >= 1.6).

#### 16. Acceso a atributo privado `_director.run_manager._run_dir` — VERDADERO

- **Archivo**: `src/energizados/cli/run.py:451-454`
- **Descripción**: El CLI accede a `builder._director` (privado) → `.run_manager` (público) → `._run_dir` (privado) — cadena de 2 niveles de violación de encapsulación.
- **Verificación**: Confirmado. `builder._director.run_manager._run_dir` cruza al menos 2 fronteras de módulo accediendo a atributos privados por convención (`_`).
- **Fix sugerido**: Exponer una property pública en `PipelineDirector` o `RunManager`.

---

### SUGGESTION

#### 17. Pérdida de traceback en `PipelineError` — VERDADERO

- **Archivo**: `src/energizados/core/pipeline.py:181`
- **Descripción**: `raise PipelineError(f"Error executing step {step_name}: {e}", step=step_name)` — falta `from e`. El traceback original se pierde.
- **Verificación**: Confirmado. Solo se preserva el mensaje vía string interpolation `{e}`, no la cadena de excepciones.
- **Fix sugerido**: Usar `raise PipelineError(...) from e`.

#### 18. Schema no incluye `stratified_time` — VERDADERO

- **Archivo**: `src/energizados/core/schemas/schemas.py:37-40`
- **Descripción**: `SPLIT_SCHEMA` enum: `["stratified", "random", "time_series", "group_based"]`. Falta `"stratified_time"`.
- **Verificación**: Confirmado. `stratified_time` está implementado en `split.py` (líneas 284-285, 377) y documentado en CLAUDE.md/AGENTS.md, pero ausente del schema. Un config válido sería rechazado por la validación.
- **Fix sugerido**: Agregar `"stratified_time"` al enum de métodos en el schema.

#### 19. Schema lista `weighted_voting` sin implementación — VERDADERO

- **Archivo**: `src/energizados/core/schemas/schemas.py:179`
- **Descripción**: `ENSEMBLE_SCHEMA` incluye `"weighted_voting"` en el enum pero no existe ninguna rama, función o lógica que lo maneje en `ensemble.py`.
- **Verificación**: Confirmado. Grep por `weighted_voting` en `ensemble.py` → 0 resultados. Pasaría validación de schema pero fallaría silenciosamente en runtime.
- **Fix sugerido**: Eliminar `weighted_voting` del schema o implementarlo.

#### 20. `BaseETL.run()` pierde causa original — VERDADERO

- **Archivo**: `src/energizados/etl/base.py:108-109`
- **Descripción**: `except Exception as e: raise ETLError(f"Error running ETL: {str(e)}")` — captura TODO (incluyendo `ETLError`), re-envuelve sin `from e`. Se pierde tipo original y traceback.
- **Verificación**: Confirmado.
- **Fix sugerido**: Usar `raise ETLError(...) from e`.

#### 21. ~~`get_preprocesor()` raise confuso con dict vacío~~ → FALSO POSITIVO

- **Archivo**: `src/energizados/feature_engineering/default.py:157-163`
- **Descripción original**: Acepta `dict` vacío `{}` sin warning.
- **Realidad**: El código chequea `if "columns" in preprocessing_config` primero. Un dict vacío `{}` no tiene la key `"columns"`, así que el guard es `False` y no entra al bloque. Si se pasa `{"columns": {}}`, el chequeo `if not columns_config` sí levanta `ValueError`. Los dos casos son distintos y la lógica es correcta.
- **Acción**: Cerrado. No aplica.

#### 22. Stacking re-entrena redundantemente con `use_val_as_oof=True` — PARCIALMENTE VERDADERO

- **Archivo**: `src/energizados/modeling/ensemble.py:89-122`
- **Descripción original**: Re-entrena redundantemente datos de validación para el meta-learner.
- **Verificación**: NO hay re-entrenamiento redundante — los base models se entrenan una vez sobre `X` (train), y sus predicciones sobre `X_val` se usan para entrenar el meta-learner. Es blending estándar. SIN EMBARGO, hay leakage sutil: los base models recibieron `X_val` para early stopping durante su propio entrenamiento, así que no son "ciegos" a `X_val`. Las predicciones del meta-learner no son truly out-of-fold.
- **Fix sugerido**: Documentar el trade-off explícitamente. Para blending sin leakage, usar un val set separado para early stopping vs meta-learner.

---

## Historia

- **Round 1**: Judge A completó — 22 findings (8 CRITICAL, 8 WARNING, 6 SUGGESTION)
- **Round 1**: Judge B — timeout, sin resultados

### Análisis manual de findings CRITICAL (#1-#8)

| # | Veredicto | Detalle |
|---|-----------|---------|
| 1 | FALSO POSITIVO | `trust_pickle` NO EXISTE en el codebase, `.sig` ausente levanta `FileNotFoundError` |
| 2 | FALSO POSITIVO | `trust_pickle` NO EXISTE — el juez inventó el parámetro |
| 3 | FALSO POSITIVO | Usa transpose trick vectorizado, no O(n²) |
| 4 | FALSO POSITIVO | Comportamiento correcto de sklearn para filas constantes |
| 5 | FIX APLICADO | Filtro correcto, pero agregado logging cuando sklearn_clone falla |
| 6 | FALSO POSITIVO | Filtro excluye `_` attrs correctamente |
| 7 | FIX APLICADO | `__import__("logging")` → `import logging` + logger module-level |
| 8 | FALSO POSITIVO | Training step ya usa `secure_dump` con SHA-256 |

**Resultado**: 8 CRITICAL → 6 falsos positivos, 2 fixes aplicados. 0 bugs reales críticos.

### Análisis manual de findings WARNING (#9-#16)

| # | Veredicto | Detalle |
|---|-----------|---------|
| 9 | VERDADERO | `> 0.5` hardcoded en todos los `predict()`, no configurable — pendiente |
| 10 | VERDADERO | `X[self.cols_for_model]` descarta columnas nuevas sin warning — pendiente |
| 11 | FIX APLICADO | Extraído a `core/utils/yaml_utils.py`, ambos archivos importan desde ahí |
| 12 | PARCIAL | Lambda captura `self`, riesgo real es dict mutable compartido — pendiente |
| 13 | FALSO POSITIVO | Retorna `.values` (numpy), índice irrelevante |
| 14 | FIX APLICADO | `replace_null is not None and (pd.isna(text) or ...)` — precedencia corregida |
| 15 | FIX APLICADO | `use_label_encoder=False` eliminado de `XGBClassifier` |
| 16 | VERDADERO | Acceso a `_run_dir` privado cruzando 2 fronteras de módulo — pendiente |

**Resultado**: 8 WARNING → 3 fixes aplicados, 3 verdaderos pendientes, 1 parcial pendiente, 1 falso positivo.

### Análisis manual de findings SUGGESTION (#17-#22)

| # | Veredicto | Detalle |
|---|-----------|---------|
| 17 | FIX APLICADO | `raise PipelineError(...) from e` — traceback preservado |
| 18 | FIX APLICADO | `"stratified_time"` agregado al enum de `SPLIT_SCHEMA` |
| 19 | FIX APLICADO | `"weighted_voting"` eliminado de `ENSEMBLE_SCHEMA` y del test |
| 20 | FIX APLICADO | `raise ETLError(...) from e` — causa original preservada |
| 21 | FALSO POSITIVO | `{}` sin key `columns` no entra al bloque, lógica correcta |
| 22 | PARCIAL | No hay re-entrenamiento redundante, pero sí leakage sutil vía early stopping — pendiente documentar |

**Resultado**: 6 SUGGESTION → 4 fixes aplicados, 1 parcial pendiente, 1 falso positivo.

---

## Resumen Final

| Severidad | Total | Fixes | Verdaderos pendientes | Parciales pendientes | Falsos Positivos |
|-----------|-------|-------|-----------------------|----------------------|------------------|
| CRITICAL  | 8     | 2     | 0                     | 0                    | 6                |
| WARNING   | 8     | 3     | 3                     | 1                    | 1                |
| SUGGESTION| 6     | 4     | 0                     | 1                    | 1                |
| **Total** | **22**| **9** | **3**                 | **2**                | **8**            |

**Pendientes**: #9 (threshold), #10 (column mismatch warn), #12 (lambda/context), #16 (run_dir privado), #22 (documentar leakage)

---

## Estado: EN PROGRESO

Quick wins (#14, #15, #17, #18, #19, #20) y moderado (#11) completados — 9 fixes aplicados, 5 issues pendientes (diseño/docs).
