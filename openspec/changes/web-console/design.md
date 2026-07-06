# Design — web-console

> **SDD change**: `web-console` — Phase 1: async job runner + minimal web API + minimal UI
> **Status**: design
> **Author**: SDD design phase
> **Date**: 2026-07-05

## Executive Summary

Thin separation of concerns: a **FastAPI web process** serves HTTP/HTMX and reads job state from SQLite; a **worker process** owns job execution via `ConfigPipelineBuilder.run()` in child processes; **SQLite** is the single source of truth for queue and lifecycle. The web layer is a passthrough — it never reimplements framework logic, only orchestrates `energizados.api` calls and persists jobs. Two additive framework-core edits (API re-export, EDA metadata field) complete the "consume the API" contract without breaking existing CLI/notebook users.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser (HTMX)                             │
│  - Paste/upload YAML                                                │
│  - View job list + status                                           │
│  - Submit / cancel / retry                                          │
└──────────────────────────┬────────────────────────────────────────┘
                           │ HTTP / SSE (Phase 5)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Web Process                              │
│  (src/energizados/web/app.py)                                      │
│                                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │   Routes    │  │   Templates │  │  Static     │               │
│  │ (HTMX/JSON) │  │  (Jinja2)   │  │   Assets    │               │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘               │
│         │                │                                            │
│         └────────────────┴────────────┐                             │
│                                      ▼                             │
│         ┌─────────────────────────────────────────┐                │
│         │         JobStore (SQLite)                │                │
│         │  - jobs table (lifecycle, config)        │                │
│         │  - job_events table (reserved)           │                │
│         └─────────────────┬───────────────────────┘                │
│                           │                                           │
│                           ▼                                           │
│         ┌─────────────────────────────────────────┐                │
│         │     energizados.api (service layer)      │                │
│         │  - validate_dict()                       │                │
│         │  - RunManager.list_runs() / get_run()    │                │
│         │  - doctor(), format_error()             │                │
│         └──────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘

                           │ (worker reads jobs; web does NOT execute)

┌─────────────────────────────────────────────────────────────────────┐
│                    Worker Process (separate)                         │
│  (src/energizados/web/worker.py)                                     │
│                                                                       │
│  ┌─────────────────────────────────────────────┐                   │
│  │         JobRunner (FIFO, concurrency=1)      │                   │
│  │  - Polls `queued` jobs from SQLite           │                   │
│  │  - Spawns child process per job              │                   │
│  │  - Manages lifecycle (running→terminal)       │                   │
│  │  - Handles cancel / retry / purge            │                   │
│  └───────────────┬─────────────────────────────┘                   │
│                  │                                                  │
│                  ▼                                                  │
│  ┌─────────────────────────────────────────────┐                   │
│  │       Child Process (per job)                 │                   │
│  │  ConfigPipelineBuilder(config=...).run()     │                   │
│  │  ├── Builds pipeline steps                    │                   │
│  │  ├── Runs Pipeline (blocking, hours)          │                   │
│  │  ├── Emits ProgressEvent via callback          │                   │
│  │  └── Calls finalize_run → run_metadata.json   │                   │
│  └──────────────────────────────────────────────┘                   │
│                  │                                                  │
│                  ▼                                                  │
│  ┌─────────────────────────────────────────────┐                   │
│  │      output/<run_id>/ (persisted)            │                   │
│  │  - run_metadata.json                         │                   │
│  │  - models/model.pkl                          │                   │
│  │  - reports/evaluation/                        │                   │
│  │  - config/ (YAML copies)                     │                   │
│  └──────────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Separate processes** (web + worker) | `Pipeline.run()` blocks for hours — worker isolation keeps web responsive and enables clean restart/kill semantics. |
| 2 | **SQLite as single source of truth** | Zero new infra; durable across restarts; simple FIFO query; job_events table reserves for future SSE. |
| 3 | **Child-process execution per job** | Clean isolation: crash/timeout/terminate doesn't corrupt worker; framework global state (cwd/sys.path) is fresh per job. |
| 4 | **Web layer is passthrough only** | Never reimplements framework logic — all validation, run discovery, and error formatting go through `energizados.api`. |
| 5 | **Framework edits are additive only** | Re-export `ConfigPipelineBuilder` and add `eda_report` to `output_paths` — no breaking changes, CLI users unaffected. |

## Components

### 1. JobStore (SQLite Persistence)

**Location**: `src/energizados/web/store.py`

**Responsibilities**:
- Schema initialization (`jobs`, `job_events` tables)
- CRUD operations for jobs
- Transactional state transitions
- Purge of old terminal jobs

**Schema**:

```sql
-- jobs table (single source of truth for job state)
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,          -- UUID or job-<timestamp>
    config TEXT NOT NULL,              -- JSON merged config
    config_type TEXT NOT NULL,         -- "etl" | "train" | "eda" | "infer"
    status TEXT NOT NULL,              -- "queued" | "running" | "success" | "failed" | "aborted"
    enqueued_at TEXT NOT NULL,         -- ISO timestamp
    started_at TEXT,                   -- ISO timestamp, null until running
    finished_at TEXT,                  -- ISO timestamp, null until terminal
    run_id TEXT,                       -- RunMetadata.run_id, null until running
    run_dir TEXT,                      -- Path to output/<run_id>, null until running
    error TEXT,                        -- JSON from format_error(exc), null on success
    retried_from TEXT,                 -- job_id of parent, null on first run
    FOREIGN KEY (retried_from) REFERENCES jobs(job_id)
);

-- job_events table (reserved for Phase 5 SSE; NOT populated in Phase 1)
CREATE TABLE job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    seq INTEGER NOT NULL,              -- Per-job monotonic sequence
    phase TEXT NOT NULL,               -- "start" | "progress" | "complete" | "error"
    step_name TEXT NOT NULL,
    message TEXT NOT NULL,
    percent INTEGER,                   -- NULL if not applicable
    timestamp TEXT NOT NULL,           -- ISO UTC
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- Indexes for FIFO ordering and queries
CREATE INDEX idx_jobs_status_enqueued ON jobs(status, enqueued_at);
CREATE INDEX idx_job_events_job_seq ON job_events(job_id, seq);
```

**Key methods**:
- `create_job(config, config_type) -> job_id`
- `get_job(job_id) -> JobRow | None`
- `list_jobs(status=None, limit=100) -> List[JobRow]`
- `update_status(job_id, status, **fields)` — transactional, validates legal transitions
- `cancel_job(job_id) -> bool` — marks `aborted` if `running`
- `retry_job(job_id) -> new_job_id` — creates new row with `retried_from`
- `purge_old_jobs(cutoff_days)` — deletes terminal jobs older than cutoff
- `reconcile_running_jobs()` — on startup, sets all `running` to `failed`

**Invariants enforced**:
- Status transitions: `queued → running → {success, failed, aborted}` only.
- `run_id` and `run_dir` are set atomically when transitioning to `running`.
- `error` is set only on `failed` or `aborted`.
- `retried_from` is immutable once set.

### 2. JobRunner (Worker Execution Engine)

**Location**: `src/energizados/web/runner.py`

**Responsibilities**:
- FIFO polling loop (`SELECT * FROM jobs WHERE status='queued' ORDER BY enqueued_at LIMIT 1`)
- Spawn child process per job via `multiprocessing.Process`
- Wire `on_*` callbacks and `progress_callback` to capture events
- Handle child process lifecycle (start, monitor, terminate, reap)
- Update job state in SQLite on terminal state

**Execution flow per job**:

```
1. JobRunner._poll()
   ├── SELECT queued job (FIFO)
   ├── UPDATE status='running', started_at=now
   ├── Spawn multiprocessing.Process(target=_run_job, args=(job_id, config, ...))
   ├── Wait for child (join or terminate on cancel)
   └── On exit:
       ├── If success: UPDATE status='success', run_id, run_dir
       ├── If exception: UPDATE status='failed', error=format_error(exc)
       └── If aborted: UPDATE status='aborted' (partial dir preserved)

2. _run_job(child process):
   ├── register_allowed_prefix("data")  # Security: BEFORE any import
   ├── builder = ConfigPipelineBuilder(config=merged_dict)
   ├── builder.on_step_start = _emit_event
   ├── builder.on_step_complete = _emit_event
   ├── builder.on_step_error = _emit_event
   ├── builder.on_phase_update = _emit_event
   ├── context = builder.run(progress_callback=_emit_event)
   └── finalize_run already called by builder.run → run_metadata.json
```

**Cancel handling**:
- Web process: `POST /jobs/{id}/cancel` → `JobStore.cancel_job(job_id)`
- Worker: checks `jobs.status == 'aborted'` in loop; if true, `child.terminate()`
- Child process cleanup: worker reaps via `child.join(timeout=5)` then `child.kill()` if needed

**Retry handling**:
- Web process: `POST /jobs/{id}/retry` → `JobStore.retry_job(job_id)`
- JobStore: `INSERT new row with config=reloaded, status='queued', retried_from=original_job_id`
- Original row: left unchanged (preserves audit trail)

**Worker restart reconciliation**:
- On startup: `JobStore.reconcile_running_jobs()` — sets all `running` → `failed` with `error='worker restarted'`
- Pending `queued` jobs resume naturally on next poll

**Concurrency model**:
- Exactly one job at a time (`concurrency=1`)
- Single-threaded poll loop
- Child processes run in parallel with worker (worker stays responsive)

### 3. WebApp (FastAPI + Jinja2 + HTMX)

**Location**: `src/energizados/web/app.py`

**Responsibilities**:
- Serve HTTP endpoints (JSON and HTMX fragments)
- Render Jinja2 templates for UI
- Validate YAML on submit (including `custom_class` prefix check)
- Proxy to `energizados.api` for run metadata
- Serve static assets (HTMX JS, CSS)

**Routes (Phase 1)**:

| Method | Path | Request | Response | Purpose |
|--------|------|---------|----------|---------|
| GET | `/` | - | HTML (index page) | Main UI |
| POST | `/jobs` | YAML body | JSON (job_id) or errors | Enqueue job |
| GET | `/jobs` | - | HTML fragment (list) | Job list |
| GET | `/jobs/{id}` | - | HTML fragment (detail) or JSON | Job detail |
| POST | `/jobs/{id}/cancel` | - | JSON (status) | Cancel job |
| POST | `/jobs/{id}/retry` | - | JSON (new_job_id) | Retry job |
| GET | `/health` | - | JSON (`ok: true`) | Health check |
| GET | `/api/runs` | - | JSON (RunManager.list_runs) | Legacy run list (Phase 2) |

**Submit flow (POST /jobs)**:

```
1. Parse YAML (or multipart file upload)
2. Validate config type (etl/train/eda/infer) from form
3. Call validate_dict(config, config_type) → ValidationResult
4. If not valid: return 400 with errors
5. Check custom_class prefixes against ALLOWED_PREFIXES:
   - Parse YAML, extract all custom_class paths
   - For each: verify starts with "energizados." or "src."
   - If any fail: return 400 with prefix error
6. JobStore.create_job(config, config_type) → job_id
7. Return 201 with {job_id, status: "queued"}
```

**`custom_class` security check** (in web process):

```python
def _check_custom_class_prefixes(config: Dict) -> List[str]:
    """
    Extract all custom_class paths from config and verify against ALLOWED_PREFIXES.
    Returns list of invalid paths (empty if all valid).
    """
    invalid = []
    prefixes = _get_allowed_prefixes()  # Reads from energizados.core.utils.import_utils.ALLOWED_PREFIXES

    for path in _extract_custom_class_paths(config):
        if not any(path.startswith(p) for p in prefixes):
            invalid.append(path)
    return invalid
```

**Template structure**:

```
src/energizados/web/templates/
├── base.html           # Layout with HTMX CDN
├── index.html          # Main page (editor + job list)
├── job_list.html       # HTMX fragment: table of jobs
├── job_detail.html     # HTMX fragment: single job row
└── components/
    ├── editor.html     # YAML textarea + file upload
    ├── validation.html # Error messages from validate_dict
    └── status_badge.html # Color-coded status badge
```

**HTMX patterns**:
- Job list refresh: `<div hx-get="/jobs" hx-trigger="every 2s" hx-swap="outerHTML">`
- Cancel button: `<button hx-post="/jobs/{id}/cancel" hx-swap="none">`
- Submit: `<form hx-post="/jobs" hx-target="#validation">`

**Error handling**:
- `ValidationResult.errors` → 400 with structured errors
- `ConfigurationError` from framework → 400 with `format_error` output
- Job not found → 404
- Worker disconnected → jobs stay `queued`, UI shows "worker unavailable"

### 4. Worker Entrypoint

**Location**: `src/energizados/web/worker.py`

**Responsibilities**:
- Parse CLI args (SQLite path, log level)
- Initialize JobStore and run reconciliation
- Start JobRunner poll loop
- Handle graceful shutdown (SIGTERM: finish current job, then exit)

**CLI interface**:

```bash
# Direct invocation
python -m energizados.web.worker --db-path data/web/jobs.db

# Via console script (from [web] extra)
energizados-web-worker --db-path data/web/jobs.db
```

**Shutdown behavior**:
- SIGTERM: set `_shutdown = True`, finish current job, exit loop
- SIGKILL: immediate termination (SQLite durable, partial run dir preserved)

## Integration with `energizados.api`

### Contract surface used

| API component | Used by | Purpose |
|---------------|---------|---------|
| `validate_dict(config, config_type)` | WebApp POST /jobs | Pre-flight validation |
| `ConfigPipelineBuilder(config=...).run()` | JobRunner child process | Execute pipeline |
| `RunManager.list_runs()` | WebApp GET /api/runs (Phase 2) | Show historical runs |
| `RunManager.get_run(run_id)` | WebApp GET /jobs/{id} detail (Phase 2) | Deep-link to run metadata |
| `format_error(exc)` | JobRunner, WebApp | Structured error JSON |
| `doctor()` | WebApp GET /health (future) | System health check |
| `register_allowed_prefix(prefix)` | JobRunner child process | Extend import allowlist |

### Framework-core edits bundled

**Edit 1: Re-export ConfigPipelineBuilder**

```python
# src/energizados/api/__init__.py
from energizados.core.pipeline import ConfigPipelineBuilder
from energizados.core.pipeline import Pipeline

__all__ = [
    # ... existing exports ...
    "ConfigPipelineBuilder",  # NEW
]
```

**Rationale**: Worker must import from public API surface, not `energizados.core.pipeline`. This keeps the "thin layer over API" contract honest. Additive, non-breaking.

**Edit 2: EDA report in output_paths**

```python
# src/energizados/core/builders/run_manager.py:_write_run_metadata
# After building output_paths for "model" and "feature_engineering":
eda_results = context.get("eda_results")
if isinstance(eda_results, dict) and eda_results.get("report_path"):
    output_paths["eda_report"] = eda_results["report_path"]
```

**Rationale**: Generic `Dict[str, str]` approach; benefits any future artifact. Enables Phase 2 iframe embed without EDA-specific special case.

## Data Model

### JobRow (dataclass)

```python
@dataclass
class JobRow:
    job_id: str
    config: Dict[str, Any]      # Parsed JSON
    config_type: str            # "etl" | "train" | "eda" | "infer"
    status: JobStatus           # Enum
    enqueued_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    run_id: Optional[str]
    run_dir: Optional[str]
    error: Optional[Dict[str, Any]]  # Parsed from format_error
    retried_from: Optional[str]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "JobRow":
        ...

    def to_dict(self) -> Dict[str, Any]:
        ...
```

### JobStatus (enum)

```python
class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"

    @property
    def is_terminal(self) -> bool:
        return self in {JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.ABORTED}
```

### State transitions

```
queued ──poll──> running ──success──> success
   ^               │
   │               └──exception──> failed
   │               │
   │               └──cancel──────> aborted
   │
   └──retry────────┘ (creates new row, original unchanged)
```

## Cross-Cutting Concerns

### Security

| Concern | Mitigation |
|---------|-----------|
| **Unauthenticated access** | Documented risk (Phase 1 assumption); deploy behind network-isolated reverse proxy; auth deferred to Phase 2+. |
| **`custom_class` injection** | Two-layer defense: (1) Web submit check against `ALLOWED_PREFIXES`, (2) Worker `register_allowed_prefix()` before import. |
| **Path traversal in run_dir** | `RunManager.get_run` already guards; web layer only reads from JobStore. |
| **SQL injection** | Parameterized queries only; never interpolate user input. |
| **YAML parsing attacks** | Use `yaml.safe_load` (already in framework via `config_validator`). |

### Logging

- **Worker process**: `logging` configured to `run.log` inside the run directory (framework already attaches handler in `finalize_run`).
- **Web process**: stdout/stderr to container logs; structured JSON in production.
- **Job logs**: Path stored in `JobRow.run_dir / "run.log"` for UI tail (Phase 2).

### Error handling strategy

| Error type | Worker handling | Web handling |
|------------|-----------------|---------------|
| `ConfigurationError` (invalid config) | Set status=`failed`, `error=format_error` | Return 400 with `ValidationResult.errors` |
| `EnergizadosError` subclasses | Set status=`failed`, preserve type in error | Format as JSON |
| Non-framework `Exception` | Set status=`failed`, `format_error` → generic error | Return 500 with `format_error` |
| Worker crash (exit code != 0) | Reconcile on restart (`running→failed`) | Jobs stay `queued`, UI shows "worker unavailable" |
| Child process timeout | `terminate()`, mark `aborted` | Show `aborted` with partial output |

### Concurrency and isolation

- **Worker**: Single-threaded poll loop; only one job `running` at a time.
- **Child processes**: `multiprocessing.Process` provides OS-level isolation; no shared memory.
- **Framework globals**: Fresh interpreter per job → no `cwd`/`sys.path` leakage between jobs.
- **SQLite**: Single-writer concurrency; web reads while worker writes — safe with WAL mode (default in Python 3.7+).

### Deployment considerations

**Process management**:
- Web: `uvicorn energizados.web.app:app --host 0.0.0.0 --port 8000`
- Worker: `energizados-web-worker --db-path data/web/jobs.db`
- Orchestrate via systemd, supervisord, or Docker Compose.

**Directory structure (runtime)**:

```
data/
├── web/
│   └── jobs.db                    # SQLite database
├── processed/                     # ETL outputs (framework)
├── temp/
│   └── splits/                    # Train/val/test splits
└── (existing framework dirs)
output/
└── train-YYYYMMDD_HHMM/          # Run directories (framework)
    ├── run_metadata.json
    ├── models/
    ├── reports/
    └── config/
```

**Environment variables**:

| Variable | Purpose | Default |
|----------|---------|---------|
| `ENERGIZADOS_WEB_DB_PATH` | SQLite database path | `data/web/jobs.db` |
| `ENERGIZADOS_WEB_LOG_LEVEL` | Logging verbosity | `INFO` |
| `ENERGIZADOS_WEB_ALLOWED_PREFIXES` | Comma-separated prefixes | (reads from framework) |

## ADR: Architectural Decisions Record

### ADR-001: Separate processes for web and worker

**Status**: Accepted

**Context**: `Pipeline.run()` blocks for hours during training. Running it in the web process would freeze all HTTP requests.

**Decision**: Run web (FastAPI) and worker (job runner) in separate OS processes. Web only reads/writes SQLite; worker owns execution.

**Consequences**:
- **Positive**: Web stays responsive; worker can be restarted independently; clean crash isolation.
- **Negative**: IPC is via SQLite polling (acceptable for FIFO single-worker); need to coordinate process lifecycle.

**Alternatives considered**:
- **Single process with thread pool**: Rejected — Python GIL + blocking `run()` defeats concurrency.
- **Celery/RQ**: Rejected — adds Redis requirement; overkill for single-worker FIFO.

### ADR-002: SQLite over Redis for job queue

**Status**: Accepted

**Context**: PRD §7 recommended RQ+Redis. Exploration found SQLite meets all lifecycle needs with zero new infra.

**Decision**: Use SQLite `jobs` table with `ORDER BY enqueued_at` for FIFO. Reserve `job_events` table for Phase 5 SSE.

**Consequences**:
- **Positive**: No new infra; durable across restarts; simple deployment; file-based backup.
- **Negative**: Polling required (no push); scaling beyond 1 worker requires external locking.

**Alternatives considered**:
- **RQ + Redis**: Rejected — adds Redis requirement; job events cleaner with Redis but not needed in Phase 1.
- **In-memory queue**: Rejected — lost on restart; violates durability requirement.

### ADR-003: Child-process execution per job

**Status**: Accepted

**Context**: Framework has global state (`cwd`, `sys.path`) mutated by `import_class`. Running jobs in worker process directly risks leakage.

**Decision**: Spawn `multiprocessing.Process` per job; parent stays responsive for cancel.

**Consequences**:
- **Positive**: Clean isolation per job; fresh interpreter; no global state leakage.
- **Negative**: Process spawn overhead (~100ms) negligible vs. runtime; need to reap children.

**Alternatives considered**:
- **Thread pool**: Rejected — GIL blocks; not truly isolated; global state shared.
- **Asyncio**: Rejected — `Pipeline.run()` is synchronous; would require major framework refactor.

### ADR-004: Web layer is passthrough only

**Status**: Accepted

**Context**: Framework already exposes `energizados.api` with structured returns. Reimplementing logic couples web to internals.

**Decision**: Web process never reimplements framework logic. All validation, run discovery, error formatting go through API.

**Consequences**:
- **Positive**: Thin web layer (<500 LOC); framework improvements automatically benefit web; no duplicate logic.
- **Negative**: Must extend API for any new web capability (acceptable tradeoff).

**Alternatives considered**:
- **Web reimplements run discovery**: Rejected — duplicates `RunManager` logic; diverges on CLI vs web.

### ADR-005: API re-export over direct import

**Status**: Accepted

**Context**: Worker needs `ConfigPipelineBuilder`. Class lives in `energizados.core.pipeline` (private surface).

**Decision**: Re-export from `energizados.api` with additive `__all__` entry.

**Consequences**:
- **Positive**: Keeps "consume the API" promise; worker imports from public surface; non-breaking.
- **Negative**: Adds 1 line to public API (acceptable, class already stable).

**Alternatives considered**:
- **Worker imports from `energizados.core.pipeline`**: Rejected — couples worker to internals; violates contract.

### ADR-006: Generic output_paths over EDA-specific field

**Status**: Accepted

**Context**: Phase 2 needs `eda_report.html` location. PRD discussion: new top-level field vs. generic `output_paths` dict.

**Decision**: Append to `output_paths["eda_report"]` in `RunManager._write_run_metadata`.

**Consequences**:
- **Positive**: Generic pattern; benefits any future artifact; no new `RunMetadata` field.
- **Negative**: EDA-specific field would be more explicit (rejected for generality).

**Alternatives considered**:
- **New `RunMetadata.eda_report_path` field**: Rejected — special-cases EDA; less generic.

### ADR-007: Retry creates new job_id

**Status**: Accepted

**Context**: Failed jobs need re-run. Option: reset same row vs. create new with link to parent.

**Decision**: New `job_id` with `retried_from = original`; original unchanged.

**Consequences**:
- **Positive**: Full audit trail (parent→child chain); no lost history; idempotent retry.
- **Negative**: More rows (acceptable; SQLite handles millions).

**Alternatives considered**:
- **Same `job_id` reset**: Rejected — loses original failure context; breaks idempotency.

### ADR-008: Cancel preserves partial run dir

**Status**: Accepted

**Context**: Director already preserves partial output on failure. Cancel should match.

**Decision**: `terminate()` child → mark `aborted` → do NOT delete run dir.

**Consequences**:
- **Positive**: User can inspect partial output; matches failure behavior; no surprise deletion.
- **Negative**: Requires explicit purge action (acceptable).

**Alternatives considered**:
- **Cancel deletes partial dir**: Rejected — destructive; surprising; user loses debugging info.

### ADR-009: job_events reserved in Phase 1

**Status**: Accepted

**Context**: Phase 5 needs SSE progress streaming. Table schema depends on `ProgressEvent` shape.

**Decision**: Create `job_events` table at schema init; do NOT populate in Phase 1.

**Consequences**:
- **Positive**: Schema stable; no migration needed in Phase 5; implementation decoupled.
- **Negative**: Empty table in Phase 1 (acceptable).

**Alternatives considered**:
- **Defer table creation to Phase 5**: Rejected — requires migration; risks schema drift.

### ADR-010: No auth in Phase 1 (documented risk)

**Status**: Accepted (with documented risk)

**Context**: PRD §5 assumes trusted, network-isolated deployment. Auth is out of scope.

**Decision**: All endpoints reachable without credentials. Document in deployment guide.

**Consequences**:
- **Positive**: Simplest first slice; no auth overhead; focus on async execution.
- **Negative**: Unauthenticated enqueue/cancel (documented as Phase 1 risk).

**Alternatives considered**:
- **Basic auth in Phase 1**: Rejected — adds complexity; PRD explicitly deferred.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Hook wiring**: `build()→set hooks→run()` doesn't call `finalize_run` | Medium | High | Verify in implementation; if not, worker uses `builder.run()` path which does call it. |
| **Hot progress callback stalls training** | Medium | Medium | Defer `job_events` population to Phase 5; if implemented earlier, use batching/side-thread. |
| **`register_allowed_prefix` not thread-safe** | Low | Low | Worker calls once during setup; concurrency=1 avoids races. |
| **Child-process crash leaves orphan resources** | Low | Medium | Worker reaps children; startup reconciliation (`running→failed`) cleans state. |
| **`multiprocessing` + framework global state** | Medium | Medium | Child is fresh interpreter per job; confirm no shared-state assumptions in tests. |
| **SQLite write lock under web+worker concurrent access** | Low | Low | WAL mode (default) allows concurrent readers; single writer (worker) safe. |
| **Reviewer rejects framework-core edits in web change** | Low | Medium | Scope Honesty section + additive/non-breaking + TDD coverage; edits are ≤5 lines. |
| **Phase 2 needs `job_events` populated, schema changed** | Low | Medium | Schema reserved now; `job_events` contract stable; Phase 5 only fills it. |
| **HTMX CDN unreachable in air-gapped deployment** | Low | Low | Document how to bundle static HTMX.js locally. |
| **Unauthenticated access in production** | Medium | High | Documented risk; deployment guide must specify network isolation or reverse proxy auth. |

## Testing Strategy

### Unit tests (no real training)

**JobStore tests** (`tests/web/test_store.py`):
- CRUD operations: create, read, list, update
- Status transitions: legal vs illegal
- Cancel: `running` → `aborted`; `queued` no-op
- Retry: new row with `retried_from`
- Purge: only old terminal jobs deleted
- Concurrency: web reads while worker writes (mocked)

**JobRunner tests** (`tests/web/test_runner.py`):
- FIFO ordering: second job waits
- Child spawn: `ConfigPipelineBuilder` called with correct config
- Cancel: child terminated, status `aborted`, dir preserved
- Exception → `failed` with `format_error`
- Startup reconciliation: `running` → `failed`

**WebApp tests** (`tests/web/test_app.py`):
- POST /jobs: valid → 201 with job_id
- POST /jobs: invalid config → 400 with errors
- POST /jobs: disallowed custom_class → 400
- GET /jobs: list rendered
- POST /jobs/{id}/cancel: status changes
- POST /jobs/{id}/retry: new job created
- Prefix check: all paths validated

**Framework-core edit tests** (`tests/test_api.py`, `tests/test_run_manager.py`):
- `from energizados.api import ConfigPipelineBuilder` → resolves
- Fake context with `eda_results["report_path"]` → `output_paths["eda_report"]` set
- Fake context without `eda_results` → no regression

### Integration tests (minimal real execution)

**End-to-end stub** (`tests/web/test_integration.py`):
- Submit stub config (1-second ETL)
- Poll job until terminal
- Verify `run_id`, `run_dir` set
- Verify `run_metadata.json` exists
- Verify cancel/retry flows

## Dependencies

### Python packages (gated behind `[web]` extra)

```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "jinja2>=3.1.0",
]
```

### Stdlib only

- `sqlite3`
- `multiprocessing`
- `logging`
- `datetime` (timezone-aware)

### No external infrastructure

- No Redis
- No message queue
- No external database

## Deployment

### Development

```bash
# Terminal 1: web process
uvicorn energizados.web.app:app --reload

# Terminal 2: worker process
python -m energizados.web.worker
```

### Production (systemd example)

```ini
# /etc/systemd/system/energizados-web.service
[Unit]
Description=Energizados Web Console
After=network.target

[Service]
Type=notify
NotifyAccess=all
User=energizados
WorkingDirectory=/opt/energizados
Environment="ENERGIZADOS_WEB_DB_PATH=/var/lib/energizados/jobs.db"
ExecStart=/opt/energizados/venv/bin/uvicorn energizados.web.app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/energizados-worker.service
[Unit]
Description=Energizados Job Worker
After=network.target

[Service]
Type=simple
User=energizados
WorkingDirectory=/opt/energizados
Environment="ENERGIZADOS_WEB_DB_PATH=/var/lib/energizados/jobs.db"
ExecStart=/opt/energizados/venv/bin/energizados-web-worker
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker Compose (optional)

```yaml
version: '3.8'
services:
  web:
    image: energizados:latest
    command: uvicorn energizados.web.app:app --host 0.0.0.0
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    depends_on:
      - worker

  worker:
    image: energizados:latest
    command: energizados-web-worker
    volumes:
      - ./data:/app/data
```

## Rollback Plan

- **Web layer**: Delete `src/energizados/web/`, remove `[web]` extra, delete `data/web/jobs.db`.
- **Framework edit #1**: Remove `ConfigPipelineBuilder` from `api/__init__.__all__`.
- **Framework edit #2**: Remove EDA append block from `run_manager.py`.
- **No migrations**: SQLite schema is created fresh on startup; no persisted format changes.

## Open Questions (deferred to implementation / tasks)

1. **Worker entrypoint CLI shape**: `energizados-web-worker` vs `python -m energizados.web.worker` — implement both, document one as primary.
2. **job_events population strategy**: Batch writes vs side-thread — decision deferred to Phase 5.
3. **HTMX CDN vs bundled**: Document CDN as default; note air-gapped option.
4. **Environment variable naming**: Confirm `ENERGIZADOS_WEB_*` prefix doesn't conflict.

## Traceability to Specs

### web-job-runner spec coverage

| Spec requirement | Design element |
|------------------|-----------------|
| Jobs table → JobStore schema §Data Model |
| Lifecycle states → JobStatus enum, transitions §Data Model |
| Concurrency=1 FIFO → JobRunner poll loop §Component 2 |
| Enqueue validates → POST /jobs flow §Component 3 |
| Execute via ConfigPipelineBuilder → _run_job child process §Component 2 |
| Cancel non-destructive → ADR-008, JobRunner cancel handling §Component 2 |
| Retry creates new job → ADR-007, JobStore.retry_job §Component 1 |
| Worker restart reconciliation → JobRunner startup §Component 2 |
| Retention purge → JobStore.purge_old_jobs §Component 1 |
| custom_class security (worker) → register_allowed_prefix in child §Component 2 |
| job_events reserved → Schema definition §Data Model |
| Independent entrypoint → Component 4 §Worker Entrypoint |

### web-console spec coverage

| Spec requirement | Design element |
|------------------|-----------------|
| Phase 1 endpoints → Routes table §Component 3 |
| custom_class vetted → _check_custom_class_prefixes §Component 3 |
| Minimal Jinja2+HTMX UI → Template structure §Component 3 |
| No auth (Phase 1) → ADR-010 §Risks |
| Web dependencies optional → [web] extra §Dependencies |
| Re-export ConfigPipelineBuilder → Edit 1 §Framework-core edits |
| EDA report in output_paths → Edit 2 §Framework-core edits |

## Next Phase Recommendations

1. **Tasks phase**: Break down into actionable tasks (setup, store, runner, web, framework edits, tests).
2. **Implementation order**: (1) Framework edits → (2) JobStore → (3) JobRunner → (4) WebApp → (5) Tests → (6) Docs.
3. **Phase 2 preparation**: Design run listing/detail endpoints, EDA iframe embed, richer job metadata.
4. **Phase 5 SSE**: Design `job_events` writer (batching/threading) and SSE endpoint.
