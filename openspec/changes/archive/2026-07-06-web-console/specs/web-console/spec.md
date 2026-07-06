# web-console Specification

> Capability: `web-console` — thin FastAPI + Jinja2 + HTMX layer over
> `energizados.api` and `web-job-runner`. Phase 1 = trigger + status only.
>
> **Q5 — framework-core edits scoped here, not as a separate capability.** The two
> additive `[framework-core]` edits below exist solely to serve this change, are
> ≤5 lines and non-breaking, and split cleanly when an `api` main spec emerges.

## Purpose

Remove the terminal/notebook operating barrier: a browser UI to trigger and monitor
pipeline runs, backed by the async job runner. Thin layer only — consumes
`energizados.api` and `web-job-runner`, never reimplements framework logic.

## Requirements

### Requirement: Phase 1 HTTP Endpoints

MUST expose exactly: `POST /jobs` (enqueue), `GET /jobs` (list), `GET /jobs/{id}`
(detail), `POST /jobs/{id}/cancel`, `POST /jobs/{id}/retry`. Return HTMX fragments or
JSON. No other endpoints in Phase 1.

#### Scenario: enqueue returns job id

- GIVEN a valid YAML body
- WHEN `POST /jobs` is called
- THEN a `queued` job is created and the response includes its `job_id`

#### Scenario: cancel and retry target the right job

- GIVEN a `running` job R and a `failed` job F
- WHEN `POST /jobs/{R}/cancel` and `POST /jobs/{F}/retry` are called
- THEN R becomes `aborted` and a new `queued` job with `retried_from = F` is created

### Requirement: `custom_class` Vetted on Submit

MUST reject submitted YAML whose `custom_class` paths don't match registered
`ALLOWED_PREFIXES` BEFORE enqueue. Defense-in-depth alongside the worker check. MUST
NOT modify `validate_dict` itself.

#### Scenario: disallowed prefix rejected

- GIVEN YAML with `custom_class: "evil.malicious.Thing"`
- WHEN `POST /jobs` receives it
- THEN a validation error is returned and no job is enqueued

### Requirement: Minimal Jinja2 + HTMX UI

MUST allow paste/upload YAML, show `validate_dict` feedback, enqueue, and render a job
list with status + cancel/retry buttons. No drag-and-drop editor, no dashboard, no EDA
embed.

#### Scenario: round-trip submit and view

- GIVEN a user pastes valid YAML
- WHEN they submit
- THEN feedback is shown, the job is enqueued, and the list refreshes (HTMX) to show it

### Requirement: No Auth in Phase 1 (Assumption + Risk)

MUST NOT include auth/RBAC. Assumption: trusted, network-isolated deployment. The risk
(unauthenticated enqueue/cancel) MUST be documented for operators.

#### Scenario: endpoints reachable without credentials

- GIVEN a running web server
- WHEN any endpoint is called with no auth headers
- THEN the request is served (no `401`/`403`)

### Requirement: Web Dependencies Are Optional

FastAPI, Jinja2, Uvicorn MUST be gated behind `[web]` (`pip install energizados[web]`).
`energizados.web` MUST NOT be imported by `energizados/__init__.py`.

#### Scenario: base install has no web deps

- GIVEN `pip install energizados` (no extras)
- WHEN `import energizados` runs
- THEN `fastapi` is not required and `energizados.web` is not imported

### Requirement: [framework-core] Re-export ConfigPipelineBuilder

`energizados.api` MUST re-export `ConfigPipelineBuilder` and add it to `__all__`.
Class only — NO `run_pipeline(config)` wrapper — because the worker must set `on_*`
hooks and `progress_callback` before `.run()`, which a wrapper would forbid or re-expose.

#### Scenario: builder importable from public API

- GIVEN `energizados.api`
- WHEN `from energizados.api import ConfigPipelineBuilder` runs
- THEN it resolves to the same class as `energizados.core.pipeline.ConfigPipelineBuilder`

### Requirement: [framework-core] EDA Report in `output_paths`

`RunManager._write_run_metadata` MUST set `output_paths["eda_report"]` from
`context["eda_results"]["report_path"]` when present. Generic (reuses `Dict[str,str]`);
no new `RunMetadata` field. Additive only.

#### Scenario: EDA run populates output_paths

- GIVEN a fake context with `context["eda_results"]["report_path"] = "/x/eda_report.html"`
- WHEN `_write_run_metadata` runs
- THEN `run_metadata.json` has `output_paths["eda_report"] == "/x/eda_report.html"`

#### Scenario: non-EDA run unaffected

- GIVEN a fake context with no `eda_results` key
- WHEN `_write_run_metadata` runs
- THEN `output_paths` has no `eda_report` key (no regression)

## Non-goals

Auth/RBAC · multi-tenancy · drag-and-drop editor · dataset versioning · hyperparameter
search from UI · real-time SSE in Phase 1 · extending `Pipeline.plan()` beyond ETL ·
modifying `validate_dict` to enforce the allowlist · CLI metadata fix · EDA iframe (Phase 2).
