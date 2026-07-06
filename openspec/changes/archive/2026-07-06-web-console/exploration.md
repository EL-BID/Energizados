# Exploration — web-console

> SDD change: `web-console` · Phase 1 first slice (job runner + minimal web API + minimal UI).
> Artifact store: openspec. Read-only exploration; no code was modified and no pipeline was executed.

## Summary

The framework already exposes a clean service layer (`energizados.api`) with structured return
values and no stdout coupling, exactly as the PRD's "Contexto verificado" table claims. That
table was **re-verified against current code and is accurate** — every named symbol exists and
signatures match (one cosmetic note: `from_dict`/`plan` are module-level aliases, intentionally
kept out of `__all__`).

However, three non-obvious facts materially shape the job-runner design and **correct a
widespread assumption in the PRD**:

1. **`Pipeline.from_dict(config).run()` always raises "No steps configured".** `Pipeline.from_dict`
   only sets `self.config`; steps are constructed by `ConfigPipelineBuilder` / `PipelineDirector`.
   The class that actually runs a full pipeline (and writes `run_metadata.json`) is
   `ConfigPipelineBuilder` — which is **NOT exported from `energizados.api`** (it lives in
   `energizados.core.pipeline`). The "consume the API, don't reimplement" principle therefore
   needs either (a) the worker reaching into `energizados.core.pipeline`, or (b) a tiny framework
   change to re-export `ConfigPipelineBuilder` from the public API surface.
2. **The `energizados run` CLI path does NOT write `run_metadata.json`.** `execute_pipeline`
   calls bare `pipeline.run()` then only `copy_configs_to_run_dir()` + `generate_index_html()`,
   skipping `finalize_run(context)`. Runs produced this way are **invisible to
   `RunManager.list_runs()`** (it filters by presence of `run_metadata.json`). Only the
   `builder.run()` / `director.run()` path (used by generated `src/run/*.py` scripts) writes it.
3. **`ProgressEvent.run_id` is hardcoded to `"unknown"`** inside `Pipeline.run()`'s own event
   emissions. SSE consumers cannot correlate events to a job by `event.run_id`; correlation must
   be external (the worker associates events to the job it is running).

All three are facts for the proposal phase to address; none block starting it.

## Verified API surface

Source of truth: `src/energizados/api/__init__.py` (`__all__`). Re-verified line-by-line.

| Function / Class | Exact signature | Source location | Notes |
|---|---|---|---|
| `validate_dict` | `validate_dict(config: Dict, config_type: str) -> ValidationResult` | `api/validate.py:85` | `config_type ∈ {"etl","train","infer","eda"}`; raises `ConfigurationError(error_code="CONFIG_UNKNOWN_TYPE")` on bad type. `ValidationResult{is_valid, errors[ConfigError], warnings[ConfigWarning], info[ConfigInfo]}`, all `.to_dict()`. |
| `Pipeline` | `class Pipeline` (re-exported) | `api/pipeline.py:9` → `core/pipeline.py:42` | See run/plan/from_dict below. |
| `Pipeline.from_dict` | `classmethod from_dict(cls, config: Dict, context=None) -> Pipeline` | `core/pipeline.py:88` | **Returns a Pipeline with `steps=[]`** (only sets `self.config`). Calling `.run()` on it raises `PipelineError("No steps configured")`. Intended for `.plan()` / inspection, not direct execution. |
| `Pipeline.plan` | `plan(self) -> ExecutionPlan` | `core/pipeline.py:106` | `ExecutionPlan{steps: List[str], dependencies: Dict, estimated_duration: Optional[float]}`. **Only resolves the `etl:` section** — for train/eda/infer-only configs it returns an empty plan (`steps=[]`). |
| `Pipeline.run` | `run(self, progress_callback=None) -> Dict[str, Any]` | `core/pipeline.py:196` | **Synchronous & blocking.** Progress callbacks (see SSE section). Re-raises `EnergizadosError` subclasses unchanged; wraps other `Exception` as `PipelineError(... from e)`. |
| `ConfigPipelineBuilder` | `ConfigPipelineBuilder(config_path=None, config=None, config_paths=None, run_name=None, overwrite=False)`; `.run()->Dict`, `.build()->Pipeline` | `core/pipeline.py:331` | **The real entry point for running a full pipeline.** `.run()` delegates to `PipelineDirector.run()` → builds steps → runs → `finalize_run()` writes `run_metadata.json`. **NOT in `energizados.api`** (import from `energizados.core.pipeline`). |
| `RunManager` | `RunManager(config_paths=None, run_name=None, overwrite=False, output_dir=None)` | `core/builders/run_manager.py:80` (re-exported via `api/run_state.py:15`) | Query methods below. |
| `RunManager.list_runs` | `list_runs(self, filter: Optional[Dict]=None, limit: int=100) -> List[RunMetadata]` | `run_manager.py:411` | Globs `output/*-*`, reads `run_metadata.json` per dir, sorts by `(timestamp, run_id)` desc, applies `limit`. Returns `[]` if base dir missing. Filter only supports `{"status": ...}`. |
| `RunManager.get_run` | `get_run(self, run_id: str) -> Optional[RunMetadata]` | `run_manager.py:371` | **Path-traversal guarded**: rejects `None`/empty/non-str, rejects `/`, `\`, `..`, and double-checks `resolved.startswith(base_resolved)`. Returns `None` on any failure. |
| `RunManager.get_latest_run` | `get_latest_run(self) -> Optional[RunMetadata]` | `run_manager.py:452` | `list_runs(limit=1)[0]` or `None`. |
| `RunMetadata` | dataclass | `run_manager.py:20` | Fields: `run_id, timestamp, duration_seconds, energizados_version, python_version, git_commit, model_types: List[str], status("success"/"partial"/"failed"), val_auc?, val_f1?, feature_count?, config_files: List[str], output_paths: Dict[str,str]`. `from_dict` (tolerant), `to_dict`. |
| `RunResult` | dataclass | `api/run_state.py:22` | Fields: `run_id?, status, start_time?, end_time?, metrics: Dict, output_paths: Dict, _context` (ref, not copy). |
| `RunResult.from_context` | `classmethod from_context(cls, context: Dict) -> RunResult` | `api/run_state.py:49` | Bridges legacy dict return. `metrics = context.get("metrics") or context.get("model_metrics") or {}` (legacy key still tolerated). |
| `ProgressEvent` | dataclass | `api/progress.py:18` | Fields: `run_id, step_name, phase("start"/"progress"/"complete"/"error"), message, percent?, timestamp(UTC)`. `.to_dict()`. **`run_id` is set to `"unknown"` by `Pipeline.run` itself.** |
| `console_progress` | `console_progress() -> Callable[[ProgressEvent], None]` | `api/progress.py:50` | CLI helper; currently just `logger.debug`. For the web app, supply your own callback. |
| `doctor` | `doctor(include_optional: bool=False) -> DoctorReport` | `api/config.py:120` | `DoctorReport{system_info, checks[List[CheckResult]]}`; `.to_dict()`, `.is_healthy()`, `.has_warnings()`. |
| `format_error` | `format_error(exception: Exception) -> Dict[str, Any]` | `api/exceptions.py:16` | `EnergizadosError.to_dict()` if applicable, else `{error_code:"GENERIC_ERROR", error_type, message, details:{}}`. |
| `merge_configs` | `merge_configs(configs: List[Dict]) -> Dict[str, Any]` | `api/config.py:20` | Deep-merge; dicts merged key-by-key, scalars/lists last-wins. Skips non-dict entries with a warning. |

**Pipeline in-process progress hooks** (set as instance attributes on the `Pipeline` returned by
`ConfigPipelineBuilder(...).build()` or `director.build()`):

- `on_step_start    = callable(name: str, index: int, total: int)`
- `on_step_complete = callable(name: str, index: int, total: int)`
- `on_step_error    = callable(name: str, error: Exception)`
- `on_phase_update  = callable(step_name: str, phase: str, progress_pct: float, total_phases: Optional[int])`
- `progress_callback` (arg to `run()`) = `callable(ProgressEvent)`

Source: `core/pipeline.py:83-86` (attribute declarations) and `:230-309` (emission sites). The CLI
(`cli/run.py:451-454`) wires all four `on_*` callbacks for its Rich UI.

## Job runner gap analysis

### What exists today
- `Pipeline.run()` / `ConfigPipelineBuilder.run()` are **synchronous and block for hours** during
  training. They run in the caller's process/thread.
- `run_metadata.json` is persisted **only** via `PipelineDirector.run()` →
  `RunManager.finalize_run(context)` → `_write_run_metadata(context)` (`director.py:195`,
  `run_manager.py:347-365`). The CLI `execute_pipeline` path **skips** `finalize_run`, so
  `energizados run etl,train` produces a run dir with no `run_metadata.json`.
- There is **no** queue, no worker process, no job table, no job lifecycle, no cancel/retry.

### State that must be persisted per job (MVP)
1. `job_id` (server-generated, stable — e.g. UUID or `job-<ts>`).
2. `config` used (the merged dict — needed for retry and for the config-copy step).
3. `config_type` / requested configs (for routing validation: etl/train/infer/eda).
4. `status`: `queued` | `running` | `success` | `failed` | `aborted` (cancel) — aligns with
   `RunMetadata.status` vocab where possible.
5. Timestamps: `enqueued_at`, `started_at`, `finished_at`.
6. `run_id` / `run_dir` link (once the worker creates the run dir, so the UI can deep-link into
   `RunManager.get_run()` + reports).
7. Log capture: either a log file path (`run.log`) or captured stdout/stderr. `_write_run_metadata`
   already attaches a file handler to `run.log` when verbose logging is on (`run_manager.py:194-208`).
8. `error` summary on failure (use `format_error(exc)` → store as JSON).
9. Optional: progress-event ring buffer per job for SSE replay on reconnect.

### Lifecycle operations — what each needs
- **Enqueue**: validate config (`validate_dict`) → dry-run plan (`Pipeline.plan()` — note: ETL
  only) → INSERT job row `status='queued'` → wake worker.
- **Cancel in-flight**: `Pipeline.run()` is **not cooperatively cancelable** (no cancellation
  token checked inside steps). Cancel MUST be process-level: terminate the OS process/thread
  running the job, then mark `status='aborted'`. Cooperative cancel would require framework
  changes (out of scope for first slice).
- **Retry failed**: load job row → reset `status='queued'`, clear `error`, set
  `enqueued_at=now` → wake worker. (Decide: same `job_id` retry vs. new job referencing the old —
  proposal phase.)
- **Survive worker restart**: on worker startup, atomically `UPDATE ... SET status='failed',
  error='worker restarted' WHERE status='running'`; pending `queued` rows resume naturally.
- **Retention / purge**: `DELETE FROM jobs WHERE status IN ('success','failed','aborted') AND
  finished_at < :cutoff` (and optionally cascade-delete the run dir, with a guard).

## Progress streaming / SSE findings

### Callback + event shape (confirmed)
- `Pipeline.run(progress_callback)` emits `ProgressEvent` objects via the callback, **inside the
  worker process**. Fields: `run_id` (hardcoded `"unknown"`), `step_name`, `phase`, `message`,
  `percent`, `timestamp`.
- The four `on_*` callbacks carry richer semantics (step index `i/total`, phase names, pct) than
  the bare `ProgressEvent`. The CLI relies on `on_phase_update` for its per-phase bars
  (`cli/run.py:388`). For SSE, the worker can synthesize a richer event from the `on_*` callbacks
  and/or forward `ProgressEvent.to_dict()`.

### The IPC problem (worker process → web process)
The web (FastAPI) process and the worker process are separate. Callbacks fire **in the worker**.
To stream over SSE to the browser, events must cross the process boundary. Concrete options:

| IPC mechanism | Write side (worker) | Read side (web→SSE) | Tradeoff |
|---|---|---|---|
| **SQLite events table** | `INSERT INTO job_events(job_id, ...)` from `progress_callback` | poll `SELECT ... WHERE id > :last` per job, stream as SSE | Zero new infra; durable replay; small polling latency. Best fit if SQLite jobs table already chosen. |
| **Append-only log file per job** | worker writes JSONL to `run_dir/events.jsonl` | web tails the file | Simple, debuggable; reconnect replay = read from offset. Needs care with flushing. |
| **Redis Pub/Sub or List** | `RPUSH`/`PUBLISH` from callback | web subscribes/polls | Real-time; requires Redis (couples to RQ option). |

Recommendation is for the **proposal** phase to decide; SQLite-events and JSONL-tail both keep the
"no new infra" property. Note: SQLite writes from a hot progress callback should be batched or
offloaded to a side-thread to avoid stalling training.

### `run_id` correlation caveat
Because `Pipeline.run` hardcodes `run_id="unknown"` in its own `ProgressEvent`s, the worker must
stamp its own `job_id` onto every event it persists/forwards. Do not rely on `event.run_id`.

## EDA output location (option B edit point)

**PRD finding confirmed.** EDA writes to its own `output_dir`, default `"output/eda/"`, outside
the run dir:

- `EDAReportGenerator.generate()` writes to `output_path or str(self.output_dir / "eda_report.html")`
  (`eda/report.py:227`). `__init__` does `self.output_dir.mkdir(parents=True, exist_ok=True)`
  (`report.py:206`).
- Default `output_dir="output/eda/"` comes from `DatasetExplorer.__init__`
  (`eda/dataset_explorer.py:70`) and the builder fallback
  `output_cfg.get("output_dir", "output/eda/")` (`core/builders/eda_builder.py:56`).
- The path lands in context as **`context["eda_results"]["report_path"]`**
  (`eda_builder.py:61` sets `context["eda_results"] = results`; `dataset_explorer.py:303` sets
  `results["report_path"] = report_path`; docstring at `dataset_explorer.py:144`).

### Exact edit point for option B — `RunManager._write_run_metadata`
`run_manager.py:313-322` currently builds `output_paths` from only two keys:

```python
# Build output_paths dict (NEW for Phase 4)
output_paths = {}
if "model_path" in context and context["model_path"] is not None:
    output_paths["model"] = context["model_path"]
if (
    "feature_engineering_path" in context
    and context["feature_engineering_path"] is not None
):
    output_paths["feature_engineering"] = context["feature_engineering_path"]
```

Option B = append, right after this block (before building `metadata` dict at `:324`):

```python
eda_results = context.get("eda_results")
if isinstance(eda_results, dict) and eda_results.get("report_path"):
    output_paths["eda_report"] = eda_results["report_path"]
```

Then the web app reads `run_metadata.output_paths["eda_report"]` and serves it (the PRD's iframe
embed). This is generic — benefits any future artifact that exposes a path in context.

> Caveat: this only works for runs that actually call `finalize_run` (i.e. `builder.run()` /
> `director.run()`). CLI `execute_pipeline` runs won't have metadata at all (see gap #2). The job
> runner must use the `builder.run()` path, not spawn the CLI.

## ALLOWED_PREFIXES state

Confirmed current state — narrowed to the secure minimum
(`core/utils/import_utils.py:15-18`):

```python
ALLOWED_PREFIXES: Set[str] = {
    "energizados.",
    "src.",
}
```

- `register_allowed_prefix(prefix: str) -> None` (`import_utils.py:33`) appends to the
  module-level set; auto-adds trailing dot. **Not thread-safe** — call during setup, before any
  framework usage.
- `import_class(class_path)` (`import_utils.py:53`) raises
  `ConfigurationError(error_code="CONFIG_INVALID_CLASS_PREFIX")` if the path doesn't start with an
  allowed prefix; then imports, temporarily adding `cwd` and `cwd/src` to `sys.path`.

**Web app implication**: the YAML editor is free-form, but any `custom_class` it accepts must be
vetted against `ALLOWED_PREFIXES`. Two distinct concerns:
1. **Validation (web process)**: `_validate_class_reference` in `api/validate.py:332` only does a
   format check (`len(parts) >= 2`) — it does **not** enforce the prefix allowlist. The web app
   should add a prefix check on submit (reuse `import_class`'s prefix logic or replicate it).
2. **Execution (worker process)**: `register_allowed_prefix(...)` must be called **in the worker**
   before the job runs, for any project-specific prefix the workspace needs (e.g. `data.`,
   `features.`, `models.`). Registering it only in the web process is not enough — the actual
   import happens in the worker.

## Job-runner options comparison (FACTUAL — no decision)

| Dimension | RQ + Redis | subprocess of CLI + SQLite | API-import worker + SQLite (hybrid) |
|---|---|---|---|
| **Extra infra** | Redis server (+ `rq`, `redis` pkgs) | None (sqlite3 stdlib) | None (sqlite3 stdlib) |
| **Queue / FIFO / concurrency=1** | Native: single RQ worker process | SQLite table + worker loop, ORDER BY created_at | SQLite table + worker loop, ORDER BY created_at |
| **How a job runs** | `queue.enqueue(run_fn, config)` in worker | `subprocess.Popen(["energizados","run",...])` | worker calls `ConfigPipelineBuilder(config=...).run()` in (child) process |
| **Writes `run_metadata.json`?** | YES if worker uses `ConfigPipelineBuilder.run()` (director→finalize_run) | **NO** — `execute_pipeline` skips `finalize_run` → run invisible to `RunManager.list_runs()`. Would need a CLI fix or use generated `src/run/*.py` scripts instead | YES — `ConfigPipelineBuilder.run()` → finalize_run → metadata |
| **Cancel in-flight** | `job.cancel()` + signal worker; RQ mid-exec cancel is limited (often SIGTERM/kill the worker handling it) | `proc.terminate()`/`proc.kill()`; mark row `aborted` | terminate the child process running the job (`multiprocessing.Process.terminate()`); mark row `aborted`. (Pipeline.run is not cooperatively cancelable in any option.) |
| **Retry failed** | re-enqueue from `FailedJobRegistry` | UPDATE row `status='queued'` | UPDATE row `status='queued'` |
| **Survive restart** | Redis persists jobs; RQ re-enqueues orphaned in-flight after worker timeout | on startup `running→failed`; resume `queued` | on startup `running→failed`; resume `queued` |
| **Retention / purge** | `job.cleanup(ttl)` / delete from registries | `DELETE WHERE finished_at < cutoff` | `DELETE WHERE finished_at < cutoff` |
| **Progress IPC to web process** | callback writes to Redis (pub/sub or list); web subscribes → SSE. Clean fit since Redis is present. | **Fragile**: CLI progress is Rich TTY rendering, not structured `ProgressEvent`. Would need `--json` streaming (only final result today) or log parsing. | callback writes `ProgressEvent` to SQLite events table / JSONL; web polls/tails → SSE. No new infra. |
| **Stdout/stderr capture** | capture in-worker → log file | `proc.stdout` PIPE → log file (natural) | capture in-worker → log file |
| **Consumes `energizados.api`?** | partially (needs `ConfigPipelineBuilder` from core) | reuses the CLI as-is (but inherits the metadata gap) | partially (needs `ConfigPipelineBuilder` from core, OR a small API re-export) |
| **Conceptual fit with PRD §4** | high (recommended in PRD) | medium (PRD's fallback; weakened by metadata+progress gaps) | highest ("consume the API, don't reimplement" + durable SQLite) |

All three are viable; the tradeoffs are infra footprint vs. control over metadata/progress. The
proposal phase decides.

## Risks & gotchas

1. **`Pipeline.from_dict(config).run()` does not work** (steps never built). Any design doc that
   shows this as the run path is wrong. Use `ConfigPipelineBuilder(config=...).run()`.
2. **`ConfigPipelineBuilder` is not in `energizados.api`** — reaching into `energizados.core.pipeline`
   couples the worker to core internals. Cleanest fix: re-export it from the public API (small,
   non-breaking framework change) — proposal should consider it.
3. **CLI runs are invisible to `RunManager.list_runs()`** (`execute_pipeline` skips
   `finalize_run`). The job runner must NOT spawn `energizados run` if it wants runs to appear in
   the UI — or the CLI must be fixed to call `finalize_run`/`builder.run()`.
4. **`ProgressEvent.run_id == "unknown"`** — never correlate SSE events by `event.run_id`; stamp
   the worker's `job_id` on every persisted/forwarded event.
5. **`Pipeline.run()` is not cooperatively cancelable.** Cancel is always process termination.
   Marking the job `aborted` and cleaning up partial output is the worker's responsibility (the
   director already preserves partial run dirs on failure — `director.py:199-240`).
6. **`Pipeline.plan()` only resolves the `etl:` section.** A "dry-run plan preview" for train/eda
   configs will show an empty DAG today; either scope the preview to ETL or extend `plan()`
   (proposal decision).
7. **`validate_dict` does not enforce the `custom_class` prefix allowlist** (`_validate_class_reference`
   only checks format). The web editor must add an explicit allowlist check on submit, and the
   worker must call `register_allowed_prefix()` for any workspace-specific prefix before running.
8. **`register_allowed_prefix` is not thread-safe** and mutates a module global — fine for
   one-shot setup in the worker, but not for concurrent mutation.
9. **Hot progress callback writing to SQLite** can stall training if done synchronously per event;
   batch/offload to a side-thread.
10. **`run_metadata.json` is written at the END of a successful run** (`finalize_run` after
    `pipeline.run()` returns). There is no "running" metadata row today — the job table is what
    provides in-flight status; `RunMetadata` only reflects finished runs.
11. **TDD note (strict_tdd=true in openspec/config.yaml):** the job runner, jobs table, and SSE
    bridge are all unit-testable without running real training (use a stub step / a tiny config).
    The metadata/EDA-option-B edit is testable against a fake context dict.

## Open questions for the proposal phase

1. **Run entry point**: should the worker use `ConfigPipelineBuilder` directly (reach into core),
   or should we first re-export it from `energizados.api` as the sanctioned "run a full pipeline"
   API? (Recommend the re-export — keeps the "thin layer over the API" promise honest.)
2. **Job-runner option**: RQ+Redis vs. subprocess-CLI vs. API-import+SQLite. (Facts gathered; no
   recommendation per scope.)
3. **Cancel semantics**: on cancel, do we delete the partial run dir or preserve it (director
   already preserves on failure)? And is retry a same-`job_id` reset or a new job referencing the
   original config?
4. **Progress IPC**: SQLite events table vs. JSONL tail vs. Redis pub/sub (the last only if RQ is
   chosen). Decide alongside the runner option.
5. **Plan preview scope**: keep `Pipeline.plan()` ETL-only for the first slice, or extend it to
   enumerate train/eda/infer steps?
6. **CLI metadata gap**: independently of the web console, should `execute_pipeline` call
   `finalize_run` so `energizados run` runs show up in `list_runs()`? (Affects option 2 directly.)
7. **`custom_class` vetting**: enforce the prefix allowlist in `validate_dict` itself (framework
   change) or only in the web editor layer?
8. **EDA option B field name**: `output_paths["eda_report"]` (generic, reuses existing dict) vs. a
   new top-level `eda_report_path` field on `RunMetadata`. (Generic dict is recommended; confirm
   in spec.)
