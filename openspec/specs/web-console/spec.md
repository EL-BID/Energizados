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

### Requirement: Runs List Endpoint

The system MUST expose `GET /runs` to return a paginated list of completed pipeline runs from `RunManager.list_runs()`. MUST support optional `status` filter and `limit` parameter (default 100). Response MUST include run_id, timestamp, status, model_types, val_auc, val_f1, and duration_seconds for each run.

#### Scenario: list renders successfully

- GIVEN the system has completed pipeline runs with metadata
- WHEN `GET /runs` is called with no parameters
- THEN a JSON array returns runs sorted by timestamp descending with default limit applied

#### Scenario: empty state handling

- GIVEN the system has no completed pipeline runs
- WHEN `GET /runs` is called
- THEN an empty array is returned with 200 status code

#### Scenario: filter by status

- GIVEN the system has runs with mixed statuses (success, partial, failed)
- WHEN `GET /runs?status=success` is called
- THEN only runs with `status == "success"` are returned

#### Scenario: limit applied

- GIVEN the system has 200 completed runs
- WHEN `GET /runs?limit=50` is called
- THEN the response contains at most 50 runs ordered by timestamp descending

### Requirement: Run Detail Endpoint

The system MUST expose `GET /runs/{run_id}` to render comprehensive run metadata and artifacts. MUST handle both single-model runs (reading `evaluation_report.json`) and multi-model runs (reading `comparison.json`). MUST display evaluation metrics, generated plots, config files, run log, and embed EDA report when present. MUST return 404 for non-existent run_id.

#### Scenario: existing single-model run

- GIVEN a completed single-model training run with standard artifacts
- WHEN `GET /runs/{run_id}` is called
- THEN the detail page renders with metadata, metrics from evaluation_report.json, available plots, and config files

#### Scenario: existing multi-model run

- GIVEN a completed ensemble/stacking run with comparison.json
- WHEN `GET /runs/{run_id}` is called
- THEN the detail page renders with model ranking, best_model, and per-model metrics from comparison.json structure

#### Scenario: missing run returns 404

- GIVEN a request with a run_id that does not exist in output/
- WHEN `GET /runs/{run_id}` is called
- THEN a 404 status code is returned with error message

#### Scenario: run with EDA report

- GIVEN a completed run where RunMetadata.output_paths includes "eda_report"
- WHEN `GET /runs/{run_id}` is called
- THEN the detail page embeds the EDA HTML report via iframe using the artifact route

#### Scenario: run without EDA omits gracefully

- GIVEN a completed run where RunMetadata.output_paths lacks "eda_report"
- WHEN `GET /runs/{run_id}` is called
- THEN the detail page renders without iframe or EDA section (no error)

#### Scenario: run with and without log

- GIVEN a completed run with output/{run_id}/run.log present or absent
- WHEN `GET /runs/{run_id}` is called
- THEN the log section renders the log file contents if present or shows "No log available" message

### Requirement: Artifact Serving Endpoint

The system MUST expose `GET /runs/{run_id}/artifacts/{path:path}` to serve files under the run directory. MUST validate run_id via `RunManager.get_run()`, reject path traversal attempts (`..` segments, absolute paths), and verify resolved path starts within the run directory before serving. MUST return appropriate content-types for images, JSON, and HTML files.

#### Scenario: valid artifact served

- GIVEN a completed run with output/{run_id}/reports/evaluation/roc_curve.png
- WHEN `GET /runs/{run_id}/artifacts/reports/evaluation/roc_curve.png` is called
- THEN the file is returned with 200 status and correct content-type header

#### Scenario: missing run returns 404

- GIVEN a request with a run_id that does not exist
- WHEN `GET /runs/{run_id}/artifacts/any/path` is called
- THEN a 404 status code is returned without checking the artifact path

#### Scenario: missing artifact returns 404

- GIVEN a valid run_id but non-existent artifact path
- WHEN `GET /runs/{run_id}/artifacts/nonexistent/file.json` is called
- THEN a 404 status code is returned

#### Scenario: path traversal blocked

- GIVEN a request with run_id and artifact path containing `..` segments
- WHEN `GET /runs/{run_id}/artifacts/../../etc/passwd` is called
- THEN a 403 or 400 status code is returned and the file is not served

#### Scenario: absolute path blocked

- GIVEN a request with absolute artifact path starting with `/`
- WHEN `GET /runs/{run_id}/artifacts//etc/passwd` is called
- THEN a 403 or 400 status code is returned

#### Scenario: artifact outside run dir rejected

- GIVEN a request with path that escapes the run directory after resolution
- WHEN `GET /runs/{run_id}/artifacts/reports/../../../malicious` is called
- THEN validation rejects the resolved path and returns 403 or 400

### Requirement: Job-Run Navigation

The system MUST link job detail pages to corresponding run detail pages when `job.run_id` is populated. MUST NOT display the link when `run_id` is absent or None. Navigation MUST preserve the context of the originating job view.

#### Scenario: job with run_id shows link

- GIVEN a completed job where job metadata includes `run_id: "train-20260706_120000"`
- WHEN the job detail page renders
- THEN a clickable link to `/runs/{run_id}` is displayed in the job detail view

#### Scenario: job without run_id omits link

- GIVEN a queued or running job where `run_id` is None or absent
- WHEN the job detail page renders
- THEN no run detail link is displayed in the interface

### Requirement: Plan Preview Endpoint (Phase 3)

The system MUST expose `POST /plan` endpoint to receive YAML/JSON config, validate schema via `validate_dict()`, check custom_class prefixes via `_check_custom_class_prefixes()`, and return `ExecutionPlan` via `Pipeline.plan()`. The endpoint MUST validate the config structure and dependencies before returning the plan.

#### Scenario: successful plan preview

- GIVEN a valid ETL config with multiple steps and dependencies
- WHEN `POST /plan` is called with the config body
- THEN an `ExecutionPlan` is returned with steps in execution order and dependency graph

#### Scenario: config with custom classes passes security check

- GIVEN an ETL config with `custom_class: "energizados.etl.pipeline.SourceETL"`
- WHEN `POST /plan` is called
- THEN the plan is returned successfully without error

#### Scenario: invalid schema returns structured error

- GIVEN a config with invalid YAML syntax or missing required fields
- WHEN `POST /plan` is called
- THEN a 400 status code is returned with validation error details

### Requirement: HTMX Content Negotiation (Phase 3)

The system MUST support content negotiation on `POST /plan`. If the `HX-Request` header is present, the system MUST return an HTML fragment from `components/plan_preview.html`. Otherwise, the system MUST return JSON response.

#### Scenario: HTMX request returns HTML fragment

- GIVEN a valid ETL config
- WHEN `POST /plan` is called with `HX-Request: true` header
- THEN an HTML fragment is returned rendering the plan inline

#### Scenario: JSON request returns JSON response

- GIVEN a valid ETL config
- WHEN `POST /plan` is called without `HX-Request` header
- THEN a JSON response is returned with `ExecutionPlan` structure

### Requirement: Unsupported Config Type Handling (Phase 3)

The system MUST return HTTP 200 with `{"available": false, "message": "Plan preview available for ETL configs only"}` when config has no `etl:` section or config_type != `etl`. This MUST NOT be treated as an error (no 400 status code).

#### Scenario: train config returns unavailable message

- GIVEN a training config (`train.yaml`) with no `etl:` section
- WHEN `POST /plan` is called
- THEN HTTP 200 is returned with `available: false` and informative message

#### Scenario: eda config returns unavailable message

- GIVEN an EDA config (`eda.yaml`) with no `etl:` section
- WHEN `POST /plan` is called
- THEN HTTP 200 is returned with `available: false` and informative message

#### Scenario: infer config returns unavailable message

- GIVEN an inference config (`infer.yaml`) with no `etl:` section
- WHEN `POST /plan` is called
- THEN HTTP 200 is returned with `available: false` and informative message

### Requirement: Circular Dependency Error Handling (Phase 3)

The system MUST catch `ETLDependencyError` exceptions (indicating circular dependencies in the ETL DAG) and return HTTP 400 with structured error message via `format_error()`. The error MUST clearly indicate the cycle detected.

#### Scenario: circular dependency returns 400

- GIVEN an ETL config with circular dependencies (e.g., A depends on B, B depends on A)
- WHEN `POST /plan` is called
- THEN HTTP 400 is returned with structured error showing the cycle

#### Scenario: self-dependency returns 400

- GIVEN an ETL config where an ETL depends on itself
- WHEN `POST /plan` is called
- THEN HTTP 400 is returned with structured error indicating the self-dependency

### Requirement: Plan Preview UI Integration (Phase 3)

The system MUST include a "Preview Plan" button in `templates/components/editor.html`. The button MUST submit to `/plan` with `hx-post="/plan"` and `hx-target="#validation-output"` to display the plan inline in the validation zone.

#### Scenario: preview plan button triggers HTMX request

- GIVEN a user viewing the YAML editor with a valid ETL config
- WHEN the "Preview Plan" button is clicked
- THEN an HTMX POST request is sent to `/plan` targeting `#validation-output`

#### Scenario: plan renders inline in validation zone

- GIVEN a user clicks "Preview Plan" with a valid ETL config
- WHEN the HTML fragment response is received
- THEN the execution plan is displayed inline in the `#validation-output` zone

#### Scenario: unsupported config shows message inline

- GIVEN a user clicks "Preview Plan" with a training config (no `etl:` section)
- WHEN the HTML fragment response is received
- THEN the "not available for this config type" message is displayed inline

#### Scenario: circular dependency error shows inline

- GIVEN a user clicks "Preview Plan" with an ETL config containing circular dependencies
- WHEN the error response is received
- THEN the structured error message is displayed inline in the validation zone

## Non-goals

Auth/RBAC · multi-tenancy · drag-and-drop editor · dataset versioning · hyperparameter
search from UI · real-time SSE in Phase 1 · extending `Pipeline.plan()` beyond ETL ·
modifying `validate_dict` to enforce the allowlist · CLI metadata fix · plan/dry-run preview (`Pipeline.plan()` — ETL-only, limited value) · metrics dashboard and evolution across runs (PRD #5) · real-time progress via Server-Sent Events (PRD #6) · drag-and-drop YAML editor · dataset versioning UI · hyperparameter search from UI.
