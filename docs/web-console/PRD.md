# PRD — Consola Web para Energizados

> **Estado**: Borrador v1.0 (decisiones cerradas). Pendiente de iniciar implementación vía SDD.
> **Fecha**: 2025-07-05
> **Stack acordado**: FastAPI + Jinja2 + HTMX (Python nativo)
> **Alcance de usuarios**: Equipo interno chico (sin multi-tenant ni RBAC en el MVP)

---

## 1. Visión

Una interfaz web simple y efectiva para que un equipo interno chico opere el
framework a diario: disparar ETL / entrenamiento / inferencia, ver los resultados
de cada ejecución y comparar métricas — sin tocar terminal ni notebooks.

El objetivo es **bajar la barrera de uso** y **centralizar el monitoreo** de todas
las ejecuciones en un solo lugar, alineado para uso diario.

## 2. Problema

Hoy el framework se opera por CLI o notebooks. Para uso diario en una empresa eso
significa:

- **Barrera técnica**: hay que saber terminal.
- **Sin visibilidad central**: no hay un lugar único para ver qué corrió y qué dio.
- **Comparación manual**: comparar ejecuciones requiere abrir reportes sueltos.

## 3. Usuarios

- **Científico de datos / ingeniero ML** (uso diario): configura, dispara,
  compara métricas, itera.
- **Revisor / QA de modelo**: inspecciona resultados, métricas y reportes sin
  tocar código.
- _(Opcional)_ **Stakeholder**: ve un dashboard de alto nivel (AUC, tendencias).

## 4. Contexto técnico (lo que YA existe y se aprovecha)

El framework ya tiene `energizados.api`, una capa de servicio sin acoplamiento a
consola y con valores de retorno estructurados. La web app es una **capa fina**
sobre ella: **no se reimplementa nada del framework**, se consume la API.

| Función web | API del framework que la respalda |
|---|---|
| Validar config antes de correr | `validate_dict()` → `ValidationResult` |
| Previsualizar plan (DAG) | `Pipeline.plan()` → `ExecutionPlan` |
| Listar ejecuciones | `RunManager.list_runs(filter, limit)` |
| Detalle de una ejecución | `RunManager.get_run()` → `RunMetadata` |
| Métricas / outputs | `RunResult.from_context()` + `reports/evaluation/*.json` |
| Reporte EDA | `eda_results["report_path"]` (HTML autocontenido) |
| Progreso en vivo | callbacks `on_step_*` + `ProgressEvent` |
| Salud del sistema | `doctor()` |
| Errores formateados | `format_error()` |

**Detalle clave**: `Pipeline.run()` es **síncrono y bloqueante**. Los
entrenamientos duran horas. Por eso la pieza central de la arquitectura es un
**job runner asíncrono** (proceso worker separado).

## 5. Decisiones cerradas

- **Alcance de usuarios**: equipo interno chico. **Sin multi-tenant, sin RBAC**
  en el MVP. Auth mínima (workspace compartido; alcanza con auth básica o nada si
  está en red interna). RBAC queda fuera del MVP.
- **Stack**: **FastAPI + Jinja2 + HTMX** (Python nativo). Un solo lenguaje, mapeo
  1:1 con la API existente, evita sumar un segundo equipo/lenguaje.
- **EDA**: el `eda_report.html` (autocontenido) se embebe directo en la app vía
  iframe, sin post-procesado.

## 6. Alcance

### Dentro del MVP

1. **Listado de ejecuciones** (ETL / train / inferencia) — estado, modelo, AUC,
   F1, duración, timestamp.
2. **Detalle de ejecución** — metadatos, reporte JSON, gráficos, config usada,
   log, y el **reporte EDA embebido**.
3. **Disparar ejecuciones** — validar config → dry-run (plan) → ejecutar
   asincrónicamente.
4. **Editor de YAML** con validación en vivo.
5. **Dashboard de métricas** — por ejecución + evolución entre ejecuciones
   (AUC/F1, matriz de confusión, cumulative gains).
6. **Progreso en vivo** de la ejecución activa (SSE).

### Fuera del MVP

- Editor visual drag-and-drop de pipelines.
- Multi-tenant / gestión avanzada de usuarios y permisos (RBAC).
- Versionado de datasets.
- Hyperparameter search desde la UI (se ve el resultado, no se configura).

## 7. Arquitectura

```
┌─────────────┐     HTMX/SSE      ┌──────────────────┐
│  Browser    │ ←────────────────→│  FastAPI + Jinja2│
│  (HTMX)     │                   │  (capa fina)     │
└─────────────┘                   └────────┬─────────┘
                                           │ energizados.api
                                           ▼
                                  ┌──────────────────┐
                                  │  Job Runner      │  ← worker + cola
                                  │  (proceso aparte)│     (Pipeline.run es
                                  └────────┬─────────┘      síncrono/bloqueante)
                                           │
                                           ▼
                                  ┌──────────────────┐
                                  │  output/<run>/   │  ← run_metadata.json,
                                  │  (persistencia)  │     reports/, eda HTML
                                  └──────────────────┘
```

**Punto no negociable**: el worker es un **proceso separado** porque
`Pipeline.run()` bloquea durante horas. Opciones concretas para equipo chico:

- **RQ + Redis** (recomendado): probado, simple, encaja con FastAPI. Redis es la
  única pieza de infraestructura extra.
- **Spawn del CLI como subproceso + tabla de jobs en SQLite**: cero infraestructura
  extra y máxima reutilización, pero control más frágil (parsing de output).

## 8. Detalle EDA (decisión de implementación pendiente)

El reporte EDA (`EDAReportGenerator`) produce **un solo HTML autocontenido**:
gráficos Plotly embebidos como strings HTML y plots estáticos como SVG/PNG en
base64. Ideal para embeber con un iframe — **cero post-procesado**.

**HALLAZGO**: el EDA hoy escribe a su propio `output_dir` (default `output/eda/`),
**fuera** del directorio del run (`output/eda-<ts>/`). El `report_path` queda en
`context["eda_results"]["report_path"]`. Para que la app ubique el reporte dentro
de la ejecución, dos caminos:

- **A)** Apuntar el `output_dir` del EDA al directorio del run (cambio de config
  o plantilla).
- **B)** Registrar `report_path` dentro de `run_metadata.json` (cambio en
  `RunManager._write_run_metadata`).

**Recomendación: B** — es genérico y beneficia a cualquier artefacto futuro, no
solo al EDA.

## 9. Fases de implementación sugeridas

1. **Job runner + API web mínima** — la pieza que falta: ejecución asíncrona sobre
   `energizados.api`. Desbloquea todo lo demás.
2. **Listado + detalle de ejecuciones** (sobre `RunManager`, ya persistido) +
   **EDA embebido**.
3. **Disparar ejecuciones** con validación y dry-run previo.
4. **Dashboard de métricas** (evolución de AUC/F1, comparativa entre ejecuciones).
5. **Progreso en vivo** (SSE sobre `ProgressEvent`).

---

## Próximo paso

Iniciar **SDD** (propuesta → spec → diseño → tareas) usando la **Fase 1 (job
runner)** como primer slice, porque es la pieza que desbloquea todo lo demás.

### Contexto verificado para la próxima sesión (no reinventar)

- API pública: `src/energizados/api/__init__.py` — `validate_dict`, `Pipeline`
  (`from_dict`, `plan`), `RunManager`, `RunMetadata`, `RunResult`, `ProgressEvent`,
  `console_progress`, `doctor`, `format_error`, `merge_configs`.
- Pipeline síncrono: `src/energizados/core/pipeline.py` — `Pipeline.run()` con
  callbacks `on_step_start` / `on_step_complete` / `on_step_error` /
  `on_phase_update` y `progress_callback` (`ProgressEvent`).
- Runs y metadata: `src/energizados/core/builders/run_manager.py` —
  `RunManager` (`list_runs`, `get_run`, `get_latest_run`), `RunMetadata` (campos:
  run_id, timestamp, duration_seconds, versiones, git_commit, model_types, status,
  val_auc, val_f1, feature_count, config_files, output_paths). Protegido contra
  path-traversal.
- Resultado estructurado: `src/energizados/api/run_state.py` —
  `RunResult.from_context()` (status, metrics, output_paths).
- EDA: `src/energizados/eda/report.py` — `EDAReportGenerator.generate()` produce
  HTML autocontenido en `output_dir/eda_report.html`. Integración con runs vía
  `src/energizados/core/builders/eda_builder.py` (pone `eda_results` en el
  contexto).
