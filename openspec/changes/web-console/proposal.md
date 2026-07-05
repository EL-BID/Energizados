# Proposal: web-console — Phase 1 (async job runner + minimal web API + minimal UI)

> **Lead decision**: a **SQLite-backed, API-import worker** (no Redis, no CLI subprocess) runs `ConfigPipelineBuilder` in a child process; FastAPI + Jinja2 + HTMX is a thin layer over `energizados.api`. Two small additive framework-core edits are bundled (re-export the builder; persist `output_paths["eda_report"]`).

## Why

The framework is operated today via CLI/notebooks — a terminal barrier, no central run visibility, manual metric comparison (PRD §2). `energizados.api` already makes the framework web-ready (structured returns, no stdout coupling). The missing piece is **async execution**: `Pipeline.run()` blocks for hours, so a separate worker process + queue is the prerequisite that unblocks every later phase (PRD §9). Phase 1 delivers exactly that prerequisite plus a minimal trigger/status UI.

## Key Decisions

> PRD §5 closed decisions (stack, no RBAC, EDA iframe) are honored as inputs — not re-litigated. PRD §7 "RQ+Redis recommended" was pre-exploration; the exploration's factual table is the evidence base below.

| # | Decision | Choice | Rationale (one line) |
|---|----------|--------|----------------------|
| 1 | Run entry point | **Re-export `ConfigPipelineBuilder` from `energizados.api`** | Exploration proved `Pipeline.from_dict(cfg).run()` always raises "No steps configured"; the builder is the real entry. Re-export keeps the "consume the API" promise honest instead of reaching into `energizados.core.pipeline`. Additive, non-breaking. |
| 2 | Job-runner option | **API-import worker + SQLite (hybrid)** | Meets all four lifecycle needs (cancel/retry/survive-restart/retention) with **zero new infra** and writes `run_metadata.json` (CLI-subprocess does not). Highest conceptual fit with PRD §4 per exploration table. PRD's Redis recommendation adds the only piece of infra the team doesn't have; SQLite avoids it. |
| 3 | Progress IPC | **SQLite `job_events` table** | Consistent with #2; one DB for jobs+events; durable replay; no Redis. Worker writes batched/offloaded (gotcha: hot callback must not stall training). SSE **consumer** deferred to Phase 5. |
| 4 | Cancel semantics | **Preserve partial run dir; retry = NEW job_id referencing original config** | Director already preserves partial output on failure — cancel matches that (no destructive surprise). Deletion is a separate explicit purge action. New job_id preserves audit trail; `retried_from` links child→parent. |
| 5 | Plan preview scope | **Keep `Pipeline.plan()` ETL-only this slice** | Extending `plan()` to train/eda/infer replicates builder logic without running = non-trivial. Phase 1 UI only triggers+shows status. Documented limitation; defer extension to Phase 3 (dry-run UI). |
| 6 | CLI metadata gap | **Defer (out of scope)** | Only the subprocess-CLI option needed it; we didn't pick that. It's an orthogonal framework bug affecting CLI users. Recommend a **separate** change (`fix: CLI runs should write run_metadata.json`). |
| 7 | `custom_class` vetting | **Web editor (submit) + worker (run); NOT `validate_dict`** | Two enforcement points: fast prefix-allowlist feedback on submit (web) + `register_allowed_prefix()` in worker before import (security-critical). Modifying `validate_dict` would force allowlist policy on all callers (CLI/programmatic) — separate framework decision. |
| 8 | EDA option B field | **`output_paths["eda_report"]` (generic dict)** | `output_paths` is already `Dict[str,str]` for "model"/"feature_engineering". A new top-level field special-cases EDA and bloats the dataclass. Generic benefits any future artifact (explainability, etc.). Matches exploration's exact edit (`run_manager.py:313-322`). |
| 9 | First-slice boundary | **Runner + 2 framework edits + minimal trigger/status UI** | User-narrowed. Listing/detail, EDA embed, dashboard, SSE consumer are explicitly Phase 2+. See IN/OUT below. |

## Capabilities

> Contract for sdd-spec. Existing main specs: `contracts`, `core-layering`, `error-handling`, `model-registry`. No existing main spec covers `api` or `run-management`.

### New Capabilities
- `web-job-runner`: SQLite-backed async job engine — FIFO queue, concurrency=1, child-process execution via `ConfigPipelineBuilder`, lifecycle (enqueue/cancel/retry/survive-restart/retention), `job_events` table. Framework-agnostic (drivable by any client).
- `web-console`: FastAPI + Jinja2 + HTMX thin web layer — HTTP endpoints + templates consuming `energizados.api` + `web-job-runner`. Phase 1 = trigger + status only.

### Modified Capabilities
- None at the spec level. The two framework-core additions (api re-export; EDA metadata field) are **additive** to surfaces with no existing main spec; sdd-spec will capture them as requirements within this change (tagged `framework-core`). See Scope Honesty.

## Approach

```
Browser ──HTMX──▶ FastAPI (web proc) ──▶ SQLite (jobs + job_events) ◀── Worker (proc)
                       │                                                  │ spawn child
                       └── energizados.api (validate_dict, RunManager)     ▼
                                                          ConfigPipelineBuilder(cfg).run()
                                                                  │ finalize_run
                                                                  ▼
                                                        output/<run>/run_metadata.json
```

- **Web process** (`src/energizados/web/app.py`): serves HTTP, reads jobs/events from SQLite, enqueues by INSERT.
- **Worker process** (`src/energizados/web/worker.py`): separate entrypoint; loops `queued` rows FIFO; per job spawns a `multiprocessing.Process` running `ConfigPipelineBuilder(config=...).run()` (metadata path, not CLI). Parent stays responsive for cancel (`child.terminate()`).
- **SQLite** (`data/web/jobs.db`): single source of truth — `jobs` (lifecycle) + `job_events` (progress, schema reserved in Phase 1; populated+SSE in Phase 5).
- **Deploy**: `uvicorn energizados.web.app:app` + `energizados-web-worker` (or `python -m energizados.web.worker`). Web deps (fastapi/jinja2/uvicorn) gated behind optional extra `pip install energizados[web]` — framework users unaffected.

## Scope Honesty (framework-core changes bundled)

Two edits live in framework core, not the web layer. They are bundled into this change rather than split into a pre-slice because both are **additive, ≤5 lines, non-breaking, directly required by Phase 1, and front-loading them keeps Phases 2–5 web-layer-only**:

1. **`src/energizados/api/__init__.py`** — re-export `ConfigPipelineBuilder` (sanctioned "run a full pipeline" entry). Without it the worker cannot honor "consume the API".
2. **`src/energizados/core/builders/run_manager.py:313-322`** — append EDA report path to `output_paths["eda_report"]` when `context["eda_results"]["report_path"]` exists. Generic; run metadata stays consistent across all phases.

Both are TDD-coverable (import check; fake context dict). Flagged for reviewer attention as cross-cutting.

## First-slice scope

### IN (Phase 1)
- SQLite `jobs` table + schema-reserved `job_events` table.
- Worker: FIFO loop, concurrency=1, child-process execution via `ConfigPipelineBuilder.run()`.
- Lifecycle: enqueue (validate→INSERT), cancel (terminate child→`aborted`, preserve dir), retry (new job_id, `retried_from`), survive-restart (`running→failed` on startup; resume `queued`), retention purge.
- Framework edit #1 (api re-export) + #2 (EDA `output_paths`).
- `custom_class` prefix vetting: web editor submit check + worker `register_allowed_prefix()`.
- Minimal FastAPI endpoints: `POST /jobs` (enqueue), `GET /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `POST /jobs/{id}/retry`.
- Minimal Jinja2+HTMX UI: paste/upload YAML → `validate_dict` → enqueue; job list with status + cancel/retry buttons.
- Worker entrypoint + optional `[web]` extra.

### OUT (deferred — phases 2+)
- Phase 2: rich run **listing/detail** (over `RunManager`), **EDA report iframe embed** (reads `output_paths["eda_report"]`).
- Phase 3: **dry-run plan preview UI** (+ possibly extending `plan()` to train/eda/infer).
- Phase 4: **metrics dashboard** (AUC/F1 evolution, run comparison).
- Phase 5: **SSE live progress consumer** (reads `job_events`; mechanism decided now).
- CLI metadata fix (separate change).
- Cooperative cancel (framework change; cancel stays process-termination).

## Non-goals

Multi-tenant · RBAC / auth · drag-and-drop pipeline editor · dataset versioning · hyperparameter search from UI · Redis/extra infra · cooperative (intra-step) cancel · multi-job concurrency (>1) · real-time SSE in Phase 1 · extending `Pipeline.plan()` beyond ETL this slice · modifying `validate_dict` to enforce the allowlist.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/web/` (new) | New | app, worker, jobs store/runner/models, routes, templates, static |
| `src/energizados/api/__init__.py` | Modified | re-export `ConfigPipelineBuilder` (+ `__all__`) |
| `src/energizados/core/builders/run_manager.py` | Modified | `output_paths["eda_report"]` in `_write_run_metadata` |
| `pyproject.toml` | Modified | optional `[web]` extra (fastapi, jinja2, uvicorn) |
| `data/web/jobs.db` | New (runtime) | SQLite jobs + events |
| `tests/` (web) | New | unit tests for store/runner/endpoints (stub configs, no real training) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Hook-vs-metadata wiring: does `build()→set hooks→run()` preserve `finalize_run`? | Med | Verify in design; if not, worker uses `builder.run()` path and hooks wired via director. Open Q for spec. |
| Hot progress callback writing SQLite stalls training | Med | Batch events / offload to side-thread; events table population deferred to Phase 5 anyway. |
| `register_allowed_prefix` not thread-safe (module global) | Low | Worker calls it once during one-shot setup before any job; concurrency=1 avoids races. |
| Child-process crash leaves orphan resources | Low | Worker reaps children; on startup `running→failed` reconciles orphans. |
| `multiprocessing` + framework global state (cwd/sys.path mutation in `import_class`) | Med | Worker child is a fresh interpreter per job; confirm no shared-state assumptions in design. |
| Reviewer flags framework-core edits in a "web" change | Low | Scope Honesty section + additive/non-breaking + TDD coverage. |

## Rollback Plan

- Web layer (`src/energizados/web/`, tests, `[web]` extra): delete the package and remove the extra — zero impact on framework users (subpackage never imported by `energizados/__init__.py`).
- Framework edit #1 (api re-export): remove the re-export line; no consumer outside web.
- Framework edit #2 (EDA field): remove the 3-line append; `output_paths` reverts to model/FE only.
- Runtime SQLite DB (`data/web/jobs.db`): delete file.
- No migrations, no persisted format changes — full revert is file deletion.

## Dependencies

- Optional Python deps (gated behind `[web]`): `fastapi`, `uvicorn`, `jinja2`. (HTMX is a static JS asset, no Python dep.)
- stdlib `sqlite3`, `multiprocessing` — no new infra.
- No Redis.

## Success Criteria

- [ ] A user can paste ETL/train YAML in the UI, validate it, and enqueue a job that runs to completion with `run_metadata.json` written and visible via `RunManager.get_run()`.
- [ ] Concurrency=1 FIFO: a second job stays `queued` until the first finishes.
- [ ] Cancel terminates the running job, marks it `aborted`, and preserves the partial run dir.
- [ ] Retry creates a new job referencing the original config and runs it.
- [ ] After a worker restart, in-flight jobs become `failed` and `queued` jobs resume.
- [ ] `energizados.api` exposes `ConfigPipelineBuilder`; EDA runs populate `output_paths["eda_report"]`.
- [ ] Unit tests cover store/runner/lifecycle/endpoints with stub configs (no real training); framework edits have targeted tests.

## Open questions deferred to spec/design

1. Hook wiring: exact pattern to get both `on_*`/`progress_callback` AND `finalize_run` metadata (does `build()→set hooks→run()` call finalize, or must the worker use `builder.run()` and pass hooks through?).
2. Whether to also add a convenience `run_pipeline(config)` wrapper alongside the re-exported class.
3. `job_events` table exact schema + whether Phase 1 populates it or only reserves it.
4. Worker entrypoint shape (CLI command vs `python -m`).
5. Whether sdd-spec introduces a `framework-api-extension` capability for the two core edits or scopes them under `web-console`.
