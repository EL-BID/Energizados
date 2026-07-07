# Exploration: web-console-phase2

**Change**: web-console-phase2 (PRD Fase 2 — listado + detalle de ejecuciones + EDA embebido)
**Status**: done
**Date**: 2026-07-06
**Backend**: openspec

## Goal

Phase 1 (`web-console`, archived) delivered the async job runner + a job
list/dashboard. This change delivers **PRD Phase 2**: let operators see the
actual **runs and their results**, not just job status.

Scope (from `docs/web-console/PRD.md` §6 items #1 and #2):
1. **Runs list view** — executions (ETL/train/inference) with run-level
   metadata: status, model type, AUC, F1, duration, timestamp.
2. **Run detail view** — metadata, evaluation JSON report, plots, config used,
   log, and the **EDA report embedded** (iframe of the autocontained
   `eda_report.html` whose path is in `RunMetadata.output_paths["eda_report"]`).

OUT of scope (future changes): metrics dashboard / evolution across runs
(PRD #5), live progress SSE (PRD #6).

## Verified API surface

### RunManager (`src/energizados/core/builders/run_manager.py`)
| Method | Signature | Notes |
|--------|-----------|-------|
| `list_runs()` | `(filter: Optional[Dict]=None, limit: int=100) -> List[RunMetadata]` (L455-494) | Globs `output/*-*`, reads `run_metadata.json`, sorts by `(timestamp, run_id)` desc, applies `limit`. Filter e.g. `{"status": "success"}`. |
| `get_run()` | `(run_id: str) -> Optional[RunMetadata]` (L415-453) | **Path-traversal guarded**: rejects None/empty/non-str, `/`, `\`, `..`, double-checks `resolved.startswith(base_resolved)`. Returns `None` on failure. |
| `get_latest_run()` | `() -> Optional[RunMetadata]` (L496-504) | `list_runs(limit=1)[0]` or `None`. |

### RunMetadata (run_manager.py:57-73)
Fields: `run_id, timestamp, duration_seconds, energizados_version,
python_version, git_commit, model_types: List[str],
status("success"/"partial"/"failed"), val_auc?, val_f1?, feature_count?,
config_files: List[str], output_paths: Dict[str,str]`.
- `output_paths["eda_report"]` IS populated (L365) via `eda_results["report_path"]`.
- Tolerant `from_dict()` loader; `to_dict()` serializer.

### RunResult (`src/energizados/api/run_state.py:50`)
`RunResult.from_context(context)` bridges legacy dict return;
`metrics = context.get("metrics") or context.get("model_metrics") or {}`.
**May not be needed** for Phase 2 — reading JSON reports directly is simpler.

## Evaluation artifacts structure

Location: `output/<run_id>/reports/evaluation/`.

Files per run:
- `evaluation_report.json` — single-model run (`evaluation/report.py:139`).
- `comparison.json` — multi-model/ensemble (`evaluation/comparative.py:83`).
- `evaluation_report.html` / `comparison.html` — HTML reports.
- Plot files: ROC, precision-recall, confusion matrix, cumulative gains, lift,
  calibration, probability distribution, feature importance, threshold sweep,
  SHAP (from `PlotGenerator`).

Single-model JSON (`evaluation_report.json`):
```json
{"metrics": {"auc": 0.85, "auc_val": 0.83, "auc_diff": 0.02, "f1": 0.78,
 "precision": 0.81, "recall": 0.75, "accuracy": 0.79, "threshold": 0.5},
 "model_info": {"model_class": "LGBMModelAdapter", "hyperparams": {...}},
 "timestamp": "..."}
```

Multi-model JSON (`comparison.json`):
```json
{"ranking": [{"name": "lgbm", "metrics": {...}, "info": {...}}, ...],
 "best_model": "lgbm", "threshold": 0.5, "timestamp": "..."}
```
**UI must handle BOTH structures** (single vs multi-model).

## EDA embed
- `eda_report.html` is **autocontained** — plots as base64 SVG/PNG or Plotly HTML
  strings (`eda/report.py:225-229`). iframe-ready, no external deps.
- Path: `RunMetadata.output_paths["eda_report"]`.
- Serve via a guarded artifact route and `<iframe src="/runs/{run_id}/artifacts/...">`.

## Config + log per run
- Config: `output/<run_id>/config/` via `copy_configs_to_run_dir()` (L263-272),
  original filenames preserved.
- Log: `output/<run_id>/run.log` when verbose logging active (`-v/-vv/-vvv`),
  attached as `FileHandler` (L237-247).
- Metadata: `output/<run_id>/run_metadata.json`.

## Existing web layer (reusable)
Routes (`src/energizados/web/app.py`): `GET /`, `POST /jobs`, `GET /jobs`,
`GET /jobs/{job_id}`, `POST /jobs/{job_id}/cancel|retry`, `GET /health`,
`GET /api/runs` (proxy to `RunManager.list_runs()`, L381-394).
Templates: `base.html`, `index.html`, `job_list.html`, `job_detail.html`.
StaticFiles mounted at `/static`.

**Gap**: no run list page, no run detail page, no artifact serving.

## Serving static artifacts — security
Serve run artifacts without path traversal: reuse `RunManager.get_run()` to
validate `run_id`, then guard `artifact_path` (no `..`, no absolute), resolve
and double-check `resolved.startswith(run_resolved)` before `FileResponse`.
Pattern mirrors the prior change's `_validate_run_name`.

## Plan / dry-run preview
`Pipeline.plan()` (`core/pipeline.py:106-166`) returns
`ExecutionPlan{steps, dependencies, estimated_duration: None}` but **only
resolves ETL dependencies**. For train/eda/infer-only configs → empty plan.
A `POST /jobs/plan` route is only useful for ETL configs; for others it would
show "no ETL steps". **Defer to follow-up** or handle gracefully.

## Approaches
1. **Minimal slice (runs list + detail + EDA embed + artifact serving)** —
   RECOMMENDED. Delivers PRD #1 + #2 completely, low risk. Effort: low-medium.
2. + plan preview (`POST /jobs/plan`) — adds PRD #3 partially; `plan()` limited
   to ETL. Effort: medium.
3. + metrics dashboard (PRD #5) — high value, larger scope; better as a
   SEPARATE change. Effort: high.

## Risks
- **Low**: API stability (all stable/tested); path traversal (reuse proven
  guards); EDA embed (autocontained, no cross-origin).
- **Medium**: artifact serving perf (large plots/EDA — add cache headers);
  `list_runs()` reads JSON in a loop (mitigate: `limit=100`); multi-model JSON
  structure differs (UI handles both).
- **High**: none — read-only view layer, no pipeline/job-runner changes.

## Conclusion
Ready for proposal. Integration clean, APIs stable, scope well-bounded. Open
question: include plan preview in this change or defer.
