# Tasks: web-console — Phase 1 (async job runner + minimal web API + minimal UI)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 1800-2200 (web layer ~1400, tests ~400, framework edits ~50) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Framework edits + JobStore + JobRunner + Worker entrypoint + tests (~800 lines). PR 2: WebApp routes + templates + tests (~600 lines). PR 3: Integration tests + docs (~400 lines). |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Framework edits + JobStore + JobRunner + Worker entrypoint + core tests | PR 1 | Base branch: release/0.3.x. Delivers async execution foundation. |
| 2 | WebApp FastAPI routes + Jinja2 templates + web tests | PR 2 | Base branch: main (after PR 1 merge). Delivers UI layer. |
| 3 | Integration tests + deployment docs | PR 3 | Base branch: main (after PR 2 merge). Verification and runbook. |

## Phase 1: Framework-Core Edits (Foundation)

- [x] 1.1 Add `ConfigPipelineBuilder` re-export to `src/energizados/api/__init__.py` (import from `core.pipeline`, add to `__all__`)
- [x] 1.2 Write test for `ConfigPipelineBuilder` import from `energizados.api` (`tests/test_api.py`)
- [x] 1.3 Add `output_paths["eda_report"]` append logic to `RunManager._write_run_metadata` in `src/energizados/core/builders/run_manager.py` (lines 313-322)
- [x] 1.4 Write test for EDA `output_paths` population with fake context dict (`tests/test_run_manager.py`)

## Phase 2: JobStore (SQLite Persistence)

- [x] 2.1 Create `src/energizados/web/` package directory structure (`__init__.py`, `store.py`, `runner.py`, `app.py`, `worker.py`, `models.py`)
- [x] 2.2 Implement SQLite schema initialization in `store.py` (`jobs` table + `job_events` table with indexes)
- [x] 2.3 Implement `JobRow` dataclass and `JobStatus` enum in `models.py` (with `from_row` factory and `to_dict` method)
- [x] 2.4 Implement `JobStore.create_job()` method (INSERT with UUID generation, timestamp defaults)
- [x] 2.5 Implement `JobStore.get_job()` and `list_jobs()` methods (SELECT by PK, SELECT with status filter + ORDER BY)
- [x] 2.6 Implement `JobStore.update_status()` with legal transition validation (queued→running, running→{success,failed,aborted})
- [x] 2.7 Implement `JobStore.cancel_job()` method (marks `aborted` if `running`, no-op otherwise)
- [x] 2.8 Implement `JobStore.retry_job()` method (INSERT new row with `retried_from` FK)
- [x] 2.9 Implement `JobStore.purge_old_jobs()` method (DELETE terminal jobs older than cutoff)
- [x] 2.10 Implement `JobStore.reconcile_running_jobs()` method (atomically set all `running`→`failed` on startup)
- [x] 2.11 Write unit tests for JobStore CRUD operations (`tests/web/test_store.py` with in-memory SQLite)
- [x] 2.12 Write unit tests for JobStore state transitions and validation (`tests/web/test_store.py`)

## Phase 3: JobRunner (Worker Execution Engine)

- [x] 3.1 Implement `JobRunner.__init__()` (store instance, shutdown flag, child process tracking)
- [x] 3.2 Implement `JobRunner._poll()` loop (SELECT queued FIFO, spawn child, wait for terminal)
- [x] 3.3 Implement `_run_job()` child process function (`register_allowed_prefix()`, `ConfigPipelineBuilder(config=...).run()`)
- [x] 3.4 Wire `on_*` callbacks and `progress_callback` in child process (stub event emission for Phase 1)
- [x] 3.5 Implement child process lifecycle handling (start, monitor, terminate, reap with timeout)
- [x] 3.6 Implement cancel handling in poll loop (check `aborted` status, call `child.terminate()`)
- [x] 3.7 Implement startup reconciliation in `JobRunner.run()` (call `store.reconcile_running_jobs()`)
- [x] 3.8 Implement graceful shutdown handling (SIGTERM: finish current job, set shutdown flag)
- [x] 3.9 Write unit tests for FIFO ordering and concurrency=1 (`tests/web/test_runner.py` with mocked child)
- [x] 3.10 Write unit tests for cancel, retry, and exception→`failed` flows (`tests/web/test_runner.py`)

## Phase 4: Worker Entrypoint

- [x] 4.1 Implement `src/energizados/web/worker.py` CLI argparser (`--db-path`, `--log-level`)
- [x] 4.2 Implement worker main function (init store, init runner, start poll loop with SIGTERM handler)
- [x] 4.3 Add `[project.scripts]` entry point `energizados-web-worker` to `pyproject.toml`
- [x] 4.4 Add `[project.optional-dependencies]` extra `web` with `fastapi>=0.100.0`, `uvicorn[standard]>=0.23.0`, `jinja2>=3.1.0`
- [x] 4.5 Write integration test for worker startup and shutdown (`tests/web/test_integration.py`)

## Phase 5: WebApp (FastAPI + Jinja2 + HTMX)

- [x] 5.1 Create `src/energizados/web/templates/` directory structure (`base.html`, `index.html`, `job_list.html`, `job_detail.html`, `components/`)
- [x] 5.2 Implement `base.html` layout with HTMX CDN script and Bootstrap CSS
- [x] 5.3 Implement `components/editor.html` (YAML textarea + file upload input)
- [x] 5.4 Implement `components/validation.html` (error messages from `validate_dict`)
- [x] 5.5 Implement `components/status_badge.html` (color-coded status badge)
- [x] 5.6 Implement `index.html` main page (editor + job list container)
- [x] 5.7 Implement `job_list.html` HTMX fragment (table of jobs with cancel/retry buttons)
- [x] 5.8 Implement `job_detail.html` HTMX fragment (single job row with status)
- [x] 5.9 Create FastAPI app in `src/energizados/web/app.py` (init, CORS middleware, static files)
- [x] 5.10 Implement `GET /` route (render index.html)
- [x] 5.11 Implement `POST /jobs` route (parse YAML, validate via `validate_dict`, check `custom_class` prefixes, enqueue via `JobStore.create_job()`)
- [x] 5.12 Implement `_check_custom_class_prefixes()` helper (extract all `custom_class` paths, validate against `ALLOWED_PREFIXES`)
- [x] 5.13 Implement `GET /jobs` route (render job_list.html HTMX fragment, auto-refresh every 2s)
- [x] 5.14 Implement `GET /jobs/{id}` route (render job_detail.html or JSON)
- [x] 5.15 Implement `POST /jobs/{id}/cancel` route (call `JobStore.cancel_job()`, return JSON status)
- [x] 5.16 Implement `POST /jobs/{id}/retry` route (call `JobStore.retry_job()`, return new job_id)
- [x] 5.17 Implement `GET /health` route (return JSON `{"ok": true}`)
- [x] 5.18 Implement `GET /api/runs` route (proxy `RunManager.list_runs()` for Phase 2 preparation)
- [x] 5.19 Write unit tests for all routes with TestClient (`tests/web/test_app.py`)
- [x] 5.20 Write unit tests for `custom_class` prefix validation (`tests/web/test_app.py`)

## Phase 6: Integration Tests

- [ ] 6.1 Write end-to-end test: submit stub config → poll job → verify terminal state + `run_id` + `run_dir`
- [ ] 6.2 Write end-to-end test: cancel running job → verify `aborted` + partial dir preserved
- [ ] 6.3 Write end-to-end test: retry failed job → verify new job_id with `retried_from` link
- [ ] 6.4 Write integration test: worker restart reconciliation (`running`→`failed`, queued resumes)
- [ ] 6.5 Write integration test: enqueue invalid config → verify 400 error, no row created

## Phase 7: Documentation

- [ ] 7.1 Update `CLAUDE.md` with web package architecture (under "Directory Structure")
- [ ] 7.2 Create `docs/web-console/DEPLOYMENT.md` (systemd units, Docker Compose, env vars)
- [ ] 7.3 Document Phase 1 security risk (unauthenticated endpoints) in deployment guide
- [ ] 7.4 Add `README.md` to `src/energizados/web/` with quickstart (uvicorn, worker commands)
- [ ] 7.5 Document HTMX CDN fallback (how to bundle locally for air-gapped deployments)
- [ ] 7.6 Add CHANGELOG entries for `feat(api): re-export ConfigPipelineBuilder` and `feat(web): add async job runner + web console`

## Traceability to Specs

### web-job-runner spec coverage

| Spec requirement | Tasks |
|------------------|-------|
| Jobs table → 2.2, 2.3 (schema + models) |
| Lifecycle states → 2.3, 2.6 (JobStatus enum + transition validation) |
| Concurrency=1 FIFO → 3.2 (poll loop ORDER BY) |
| Enqueue validates → 5.11, 5.12 (POST /jobs with validate_dict + prefix check) |
| Execute via ConfigPipelineBuilder → 3.3 (child process with builder.run()) |
| Cancel non-destructive → 2.7, 3.6 (cancel_job + terminate child) |
| Retry creates new job → 2.8 (retry_job with retried_from FK) |
| Worker restart reconciliation → 2.10, 3.7 (reconcile_running_jobs + startup call) |
| Retention purge → 2.9 (purge_old_jobs) |
| custom_class security (worker) → 3.3 (register_allowed_prefix before import) |
| job_events reserved → 2.2 (schema created, NOT populated) |
| Independent entrypoint → 4.1-4.3 (worker.py CLI + console script) |

### web-console spec coverage

| Spec requirement | Tasks |
|------------------|-------|
| Phase 1 endpoints → 5.10-5.17 (all 6 routes) |
| custom_class vetted → 5.12 (_check_custom_class_prefixes helper) |
| Minimal Jinja2+HTMX UI → 5.1-5.8 (all templates + HTMX patterns) |
| No auth (Phase 1) → 7.3 (documented risk, no implementation) |
| Web dependencies optional → 4.4 ([web] extra) |
| Re-export ConfigPipelineBuilder → 1.1-1.2 (api edit + test) |
| EDA report in output_paths → 1.3-1.4 (run_manager edit + test) |

## Parallel vs Sequential Execution

**Sequential (must run in order)**:
- Phases 1→2→3→4 (framework edits → store → runner → worker)
- Phases 5→6 (web app → integration tests)

**Parallel (can run simultaneously)**:
- Phase 7 (docs) can be written alongside any implementation phase
- Tests within each phase (2.11-2.12, 3.9-3.10, 5.19-5.20) parallel to implementation tasks in that phase

## Implementation Order Notes

1. **Foundation first**: Framework edits (1.1-1.4) enable all subsequent work — JobRunner needs `ConfigPipelineBuilder` importable from API.
2. **Store before runner**: JobStore (Phase 2) is a dependency of JobRunner (Phase 3).
3. **Worker before web**: Worker entrypoint (Phase 4) can be tested independently; web layer (Phase 5) consumes the same JobStore but runs in a separate process.
4. **Tests validate each phase**: Unit tests accompany each component; integration tests (Phase 6) verify end-to-end flows.
5. **Docs complete the slice**: Phase 7 documents deployment and security considerations for operators.
