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
modifying `validate_dict` to enforce the allowlist · CLI metadata fix · plan/dry-run preview (`Pipeline.plan()` — ETL-only, limited value) · drag-and-drop YAML editor · dataset versioning UI · hyperparameter search from UI · Event retention/cleanup TTL · SSE connection limiting · Authentication/authorization for SSE.

---

# Phase 4 Requirements (Metrics Dashboard)

### Requirement: Timeline Dashboard View

The system MUST expose `GET /dashboard` to render an interactive timeline chart showing AUC/F1 metric evolution across the last N runs. MUST use `RunMetadata.val_auc` and `RunMetadata.val_f1` only (NO evaluation JSON reads). MUST support optional `status` filter and `limit` parameter (default 20). MUST display Plotly line chart with click-to-navigate to run detail.

#### Scenario: timeline renders from RunMetadata only

- GIVEN the system has 20 completed runs with valid RunMetadata
- WHEN `GET /dashboard` is called with default parameters
- THEN the timeline chart renders using ONLY RunMetadata.val_auc and RunMetadata.val_f1 values
- AND no evaluation_report.json files are read
- AND the chart shows two series (AUC and F1) with timestamps on X-axis

#### Scenario: status filter works

- GIVEN the system has runs with mixed statuses (success, partial, failed)
- WHEN `GET /dashboard?status=success` is called
- THEN the timeline chart shows ONLY runs with `status == "success"`
- AND the chart updates via HTMX when status dropdown changes

#### Scenario: configurable limit

- GIVEN the system has 100 completed runs
- WHEN `GET /dashboard?limit=50` is called
- THEN the timeline chart shows at most 50 runs ordered by timestamp descending (newest first)

#### Scenario: click navigates to run detail

- GIVEN a user viewing the timeline chart
- WHEN the user clicks a data point (AUC or F1 value)
- THEN a new tab opens to `/runs/{run_id}` for that specific run
- AND the run_id is extracted from the clicked point's metadata

#### Scenario: empty state with no runs

- GIVEN the system has no completed runs
- WHEN `GET /dashboard` is called
- THEN the page renders with "No runs available" message
- AND the chart area shows empty state (not broken/missing chart)

#### Scenario: handles missing val_auc or val_f1 gracefully

- GIVEN the system has runs where RunMetadata.val_auc or RunMetadata.val_f1 is None
- WHEN `GET /dashboard` is called
- THEN the timeline chart plots available metrics only
- AND missing values appear as gaps in the line (not zeros or errors)

### Requirement: Timeline JSON Data Endpoint

The system MUST expose `GET /api/dashboard/timeline` to return structured timeline data for Plotly rendering. MUST accept `limit` (default 100) and optional `status` filter parameters. MUST return JSON with `timestamps`, `auc`, `f1`, and `run_ids` arrays. MUST reverse RunManager output to show newest runs first.

#### Scenario: returns timeline data structure

- GIVEN the system has completed runs with RunMetadata
- WHEN `GET /api/dashboard/timeline?limit=20` is called
- THEN JSON response contains: `{"timestamps": [...], "auc": [...], "f1": [...], "run_ids": [...]}`
- AND array lengths are equal (same N runs in each array)
- AND runs are ordered by timestamp descending (newest first)

#### Scenario: status filter applies to timeline endpoint

- GIVEN the system has runs with mixed statuses
- WHEN `GET /api/dashboard/timeline?status=success` is called
- THEN the response includes only runs where `status == "success"`
- AND the JSON arrays contain filtered runs only

#### Scenario: limit parameter caps result size

- GIVEN the system has 200 completed runs
- WHEN `GET /api/dashboard/timeline?limit=50` is called
- THEN each JSON array contains at most 50 elements
- AND the 50 most recent runs are returned

### Requirement: Comparison View

The system MUST expose `GET /runs/compare?ids=...` to render side-by-side metrics comparison for 2-10 selected runs. MUST read evaluation data via `_load_run_evaluation(run_id)` which handles both single-model (evaluation_report.json) and multi-model (comparison.json) structures. MUST display metrics table with AUC, F1, Precision, Recall, Accuracy, Confusion Matrix, and Threshold. MUST highlight best values across compared runs. MUST provide CSV download functionality.

#### Scenario: compare two runs successfully

- GIVEN the system has two completed runs with evaluation_report.json
- WHEN `GET /runs/compare?ids=run1,run2` is called
- THEN a comparison table renders with both runs' metrics side-by-side
- AND the table shows AUC, F1, Precision, Recall, Accuracy, Confusion Matrix, and Threshold
- AND best values per metric are highlighted (bold/color)

#### Scenario: compare multi-model runs

- GIVEN the system has two ensemble runs with comparison.json
- WHEN `GET /runs/compare?ids=ensemble1,ensemble2` is called
- THEN the comparison shows ranking, best_model, and per-model metrics from comparison.json
- AND multi-model runs display differently from single-model runs (ranking shown)

#### Scenario: reject single run ID

- GIVEN the system has at least one completed run
- WHEN `GET /runs/compare?ids=run1` is called
- THEN HTTP 400 is returned with error message "At least 2 run IDs required"
- AND no comparison page renders

#### Scenario: reject malformed run IDs

- GIVEN a user supplies run IDs with special characters or path traversal
- WHEN `GET /runs/compare?ids=run1,../../etc,run2` is called
- THEN the endpoint validates each run_id format
- AND HTTP 400 is returned with error message listing invalid IDs
- AND no comparison page renders

#### Scenario: cap comparison at 10 runs

- GIVEN a user attempts to compare more than 10 runs
- WHEN `GET /runs/compare?ids=run1,run2,...,run15` is called (15 IDs)
- THEN the endpoint validates the count and rejects with HTTP 400
- AND error message states "Maximum 10 runs can be compared at once"

#### Scenario: handle missing evaluation data gracefully

- GIVEN the system has 3 runs but run2 lacks evaluation_report.json
- WHEN `GET /runs/compare?ids=run1,run2,run3` is called
- THEN the comparison renders with run1 and run3 metrics
- AND run2 shows "Evaluation data not available" message in its column
- AND the table does not break or error

#### Scenario: CSV download functionality

- GIVEN a user viewing a comparison of 3 runs
- WHEN the user clicks "Download CSV" button
- THEN a CSV file downloads with metrics table content
- AND the CSV includes headers and all compared runs' metrics
- AND filename includes comparison date (e.g., `comparison_20260708.csv`)

### Requirement: Comparison JSON Data Endpoint

The system MUST expose `GET /api/runs/compare?ids=...` to return structured comparison data for client-side rendering or API usage. MUST use `_load_run_evaluations_batch(run_ids)` helper to load evaluation data tolerant to missing files. MUST return JSON with `runs` dictionary mapping run_id to evaluation data structure.

#### Scenario: returns comparison data for multiple runs

- GIVEN the system has completed runs with evaluation data
- WHEN `GET /api/runs/compare?ids=run1,run2,run3` is called
- THEN JSON response contains: `{"runs": {"run1": {...}, "run2": {...}, "run3": {...}}}`
- AND each run's evaluation data includes metrics, confusion_matrix, and threshold fields

#### Scenario: handles mixed single-model and multi-model runs

- GIVEN the system has both single-model and ensemble runs
- WHEN `GET /api/runs/compare?ids=single1,ensemble1` is called
- THEN the response normalizes both structures via `_load_run_evaluation`
- AND single-model runs return standard metrics
- AND multi-model runs return ranking and per-model metrics

#### Scenario: skips runs with missing evaluation data

- GIVEN the system has 3 runs but run2 lacks evaluation_report.json
- WHEN `GET /api/runs/compare?ids=run1,run2,run3` is called
- THEN the response includes run1 and run3 data only
- AND run2 is omitted from the `runs` dictionary (not present as key)
- AND HTTP 200 is returned (partial results, not error)

### Requirement: Threshold Exploration Data Endpoint

The system MUST expose `GET /api/runs/{run_id}/thresholds` to return threshold sweep data for interactive exploration. MUST read full `evaluation_report.json` to extract `threshold_metrics` (precisions/recalls/f1s vs threshold) and `metrics.cumulative_gains`. MUST return current threshold from `metrics.threshold`. MUST handle missing threshold_metrics or cumulative_gains gracefully (return null/empty arrays).

#### Scenario: returns threshold sweep data

- GIVEN a completed run with evaluation_report.json containing threshold_metrics
- WHEN `GET /api/runs/{run_id}/thresholds` is called
- THEN JSON response contains: `{"threshold_metrics": {...}, "cumulative_gains": {...}, "current_threshold": 0.5}`
- AND threshold_metrics has structure: `{thresholds: [], precisions: [], recalls: [], f1s: []}`
- AND cumulative_gains has structure: `{deciles: [], cumulative_gain: [], cumulative_population: []}`

#### Scenario: handles missing threshold_metrics gracefully

- GIVEN a run from an old framework version lacking threshold_metrics in evaluation JSON
- WHEN `GET /api/runs/{run_id}/thresholds` is called
- THEN the response returns `{"threshold_metrics": null, "cumulative_gains": {...}, "current_threshold": 0.5}`
- AND HTTP 200 is returned (not 404 or 500)
- AND the client-side UI shows "Threshold data not available for this run"

#### Scenario: handles missing cumulative_gains gracefully

- GIVEN a run where evaluation_report.json lacks cumulative_gains data
- WHEN `GET /api/runs/{run_id}/thresholds` is called
- THEN the response returns `{"threshold_metrics": {...}, "cumulative_gains": null, "current_threshold": 0.5}`
- AND HTTP 200 is returned (not 404 or 500)

#### Scenario: returns 404 for missing evaluation report

- GIVEN a run_id where evaluation_report.json does not exist
- WHEN `GET /api/runs/{run_id}/thresholds` is called
- THEN HTTP 404 is returned with error message "Evaluation not found"
- AND no threshold data is returned

#### Scenario: multi-model run returns base model threshold data

- GIVEN an ensemble run with comparison.json and multiple base models
- WHEN `GET /api/runs/{run_id}/thresholds` is called
- THEN the endpoint reads evaluation_report.json for the ensemble's threshold data
- AND the response contains threshold_metrics for the ensemble model (not individual base models)

### Requirement: Threshold Exploration UI Integration

The system MUST extend the existing `run_detail.html` template to add a threshold exploration section. MUST load threshold data via `GET /api/runs/{run_id}/thresholds` and render two interactive Plotly charts: Precision/Recall vs Threshold and Cumulative Gains. MUST include interactive threshold slider to explore operating points and display dynamic metrics (Precision, Recall, F1 @ threshold). MUST gracefully degrade when threshold data is unavailable.

#### Scenario: threshold section renders on run detail

- GIVEN a user viewing `/runs/{run_id}` for a run with threshold_metrics
- WHEN the run detail page loads
- THEN a new `<section id="thresholds">` renders below existing sections
- AND the section contains Precision/Recall vs Threshold chart and Cumulative Gains chart
- AND a threshold slider widget allows interactive exploration

#### Scenario: interactive threshold slider updates metrics

- GIVEN a user viewing the threshold exploration section
- WHEN the user moves the threshold slider
- THEN the displayed metrics (Precision, Recall, F1) update dynamically based on selected threshold
- AND a vertical marker on the Precision/Recall chart moves to the selected threshold

#### Scenario: handles missing threshold data gracefully

- GIVEN a user viewing `/runs/{run_id}` for a run without threshold_metrics
- WHEN the threshold section loads
- THEN the section renders with "Threshold data not available for this run" message
- AND no charts are displayed (avoids broken/empty chart areas)
- AND the page does not error or break

#### Scenario: cumulative gains chart renders

- GIVEN a run with cumulative_gains data in evaluation_report.json
- WHEN the threshold exploration section loads
- THEN a Cumulative Gains chart renders showing cumulative gain vs population
- AND the chart uses standard cumulative gains visualization (deciles on X-axis)

### Requirement: Batch Evaluation Loader Helper

The system MUST implement `_load_run_evaluations_batch(run_ids: List[str])` helper function to load evaluation data for multiple runs efficiently. MUST tolerate missing evaluation files by skipping runs without data. MUST return dictionary mapping run_id to evaluation data structure (or omit run_id entirely if missing). MUST reuse existing `_load_run_evaluation(run_id)` for single-model/multi-model normalization.

#### Scenario: loads evaluation data for multiple runs

- GIVEN the system has 5 runs with valid evaluation_report.json files
- WHEN `_load_run_evaluations_batch(["run1", "run2", "run3", "run4", "run5"])` is called
- THEN a dictionary returns with all 5 run_ids as keys
- AND each value contains the normalized evaluation data structure

#### Scenario: skips runs with missing evaluation files

- GIVEN the system has 3 runs but run2 lacks evaluation_report.json
- WHEN `_load_run_evaluations_batch(["run1", "run2", "run3"])` is called
- THEN the returned dictionary contains only run1 and run3 as keys
- AND run2 is omitted (not present as key with None or empty value)

#### Scenario: handles both single-model and multi-model runs

- GIVEN the system has mixed single-model and ensemble runs
- WHEN `_load_run_evaluations_batch(["single1", "ensemble1"])` is called
- THEN the returned dictionary contains normalized evaluation data for both
- AND single-model runs have standard metrics structure
- AND multi-model runs have ranking and per-model metrics structure

### Requirement: Cross-Cutting Graceful Degradation

All dashboard views and endpoints MUST handle partial/old runs gracefully. Missing `val_auc`/`val_f1` in RunMetadata MUST render as gaps in timeline (not zeros). Missing `evaluation_report.json` MUST skip runs in comparison (not error). Missing `threshold_metrics` or `cumulative_gains` MUST render "not available" messages (not broken UI). All endpoints MUST return HTTP 200 with partial data when possible, reserving 404 only for completely missing resources.

#### Scenario: timeline handles missing RunMetadata metrics

- GIVEN the system has runs where RunMetadata.val_auc or RunMetadata.val_f1 is None
- WHEN the timeline chart renders
- THEN missing metrics appear as gaps in the line chart
- AND no zeros or error bars appear for missing values
- AND the chart remains functional

#### Scenario: comparison skips runs without evaluation data

- GIVEN the system has 5 runs but 2 lack evaluation_report.json
- WHEN `GET /runs/compare?ids=all_5_runs` is called
- THEN the comparison renders 3 runs with available data
- AND the 2 missing runs show "Evaluation data not available" in their columns
- AND the table structure remains intact (no broken layout)

#### Scenario: threshold exploration shows unavailable message

- GIVEN a user viewing a run without threshold_metrics in evaluation JSON
- WHEN the threshold exploration section loads
- THEN the section renders with informative message: "Threshold data not available for this run (requires framework v0.2.7+)"
- AND no chart containers are created (avoids Plotly errors)

#### Scenario: JSON endpoints return partial data

- GIVEN a request to `/api/runs/compare?ids=run1,run2,run3` where run2 lacks evaluation data
- WHEN the endpoint processes the request
- THEN HTTP 200 is returned with `{"runs": {"run1": {...}, "run3": {...}}}`
- AND run2 is omitted from the response (not null or error)
- AND the response is valid JSON (no partial/corrupted structure)

### Requirement: Multi-Model Run First-Class Support

All dashboard views MUST handle both single-model runs (reading `evaluation_report.json`) and multi-model/ensemble runs (reading `comparison.json`) as first-class citizens. Timeline MUST show ensemble val_auc/val_f1 from RunMetadata (already normalized). Comparison MUST display ranking and per-model metrics for ensemble runs. Threshold exploration MUST use ensemble's threshold_metrics from evaluation_report.json (ensemble produces its own eval report).

#### Scenario: timeline shows ensemble runs

- GIVEN the system has ensemble runs with RunMetadata.val_auc and RunMetadata.val_f1 populated
- WHEN the timeline chart renders
- THEN ensemble runs appear on the timeline alongside single-model runs
- AND no distinction is visible (both show val_auc/val_f1 from metadata)

#### Scenario: comparison shows ensemble ranking

- GIVEN a comparison including an ensemble run
- WHEN the comparison view renders
- THEN the ensemble run displays ranking (e.g., "1. lightgbm, 2. catboost, 3. xgboost")
- AND per-model metrics are shown for each base model
- AND best_model is highlighted if present in comparison.json

#### Scenario: threshold exploration works for ensemble runs

- GIVEN an ensemble run with evaluation_report.json containing threshold_metrics
- WHEN the threshold exploration section loads for that run
- THEN Precision/Recall vs Threshold chart renders using ensemble's threshold_metrics
- AND cumulative gains chart renders using ensemble's cumulative_gains data
- AND no distinction from single-model runs is visible

---

# Phase 5 Requirements (SSE Live Progress)

### Requirement: Job Events Progress Persistence

The system MUST persist each ProgressEvent from the pipeline to the job_events table via the worker's progress_callback. The callback MUST be integrated into JobRunner._run_job and capture job_id from the closure. Each event MUST include job_id, monotonically increasing seq number, phase, step_name, message, percent (nullable float), and timestamp. The callback MUST NOT abort the pipeline if event persistence fails — errors MUST be logged and isolated.

#### Scenario: worker writes step events

- GIVEN a running job executing a pipeline with multiple steps
- WHEN the pipeline emits ProgressEvent objects via the callback
- THEN each event is inserted into job_events with the correct job_id
- AND seq values increment monotonically (1, 2, 3, ...)
- AND phase, step_name, message, percent, timestamp match the ProgressEvent fields

#### Scenario: callback failure does not abort pipeline

- GIVEN a running job with progress_callback configured
- WHEN the job_events INSERT operation fails (database locked, I/O error)
- THEN the callback logs the error but does NOT raise
- AND the pipeline continues executing normally
- AND subsequent callbacks are still attempted

#### Scenario: callback captures job_id correctly

- GIVEN a worker process running multiple jobs sequentially
- WHEN progress_callback is invoked for a job
- THEN the callback uses the correct job_id from the closure
- AND events are written to the correct job_events row per job

### Requirement: SSE Endpoint for Live Progress

The system MUST expose GET /jobs/{job_id}/events as a Server-Sent Events endpoint returning text/event-stream via StreamingResponse. The endpoint MUST accept an optional last_seq query parameter to resume from a specific sequence number. MUST stream events WHERE job_id = ? AND seq > ? ORDER BY seq ASC. MUST return 404 for unknown job_id. MUST send a terminal event and close the stream when job reaches success/failed/aborted status.

#### Scenario: stream events for running job

- GIVEN a job with status running and existing job_events records
- WHEN GET /jobs/{job_id}/events is called with EventSource client
- THEN the endpoint returns text/event-stream content-type
- AND events are streamed as data: {json} lines with event: progress type
- AND each event includes id (seq), event (progress type), data (JSON with phase, step_name, message, percent, timestamp)
- AND the connection remains open waiting for new events

#### Scenario: job already finished at connect time

- GIVEN a job with status success and existing job_events records
- WHEN GET /jobs/{job_id}/events is called
- THEN the endpoint replays all existing events in seq order
- AND sends a terminal event with event: complete type and data: {status: success}
- AND closes the stream (no keep-alive)
- AND the client receives complete job history immediately

#### Scenario: unknown job returns 404

- GIVEN a request with job_id that does not exist in the jobs table
- WHEN GET /jobs/{unknown_id}/events is called
- THEN HTTP 404 is returned with error message
- AND no SSE stream is initiated

#### Scenario: last_seq parameter filters events

- GIVEN a job with 10 job_events records (seq 1-10)
- WHEN GET /jobs/{job_id}/events?last_seq=5 is called
- THEN only events with seq > 5 are streamed (6, 7, 8, 9, 10)
- AND earlier events (1-5) are not sent

#### Scenario: terminal event sent on job completion

- GIVEN a job with status running and active SSE connection
- WHEN the job completes and status changes to success
- THEN a final event is sent with event: complete type
- AND the event data includes {status: success, final_message: "..."}
- AND the endpoint closes the stream (ends SSE response)

#### Scenario: terminal event sent on job failure

- GIVEN a job with status running and active SSE connection
- WHEN the job fails and status changes to failed
- THEN a final event is sent with event: error type
- AND the event data includes {status: failed, error_message: "..."}
- AND the endpoint closes the stream

### Requirement: UI Integration with EventSource

The system MUST integrate EventSource into job_detail.html to render live progress events. MUST open EventSource to /jobs/{job_id}/events on page load. MUST append incoming progress events to a visible timeline or log area. MUST close EventSource on terminal event. MUST gracefully fallback if EventSource is unsupported.

#### Scenario: EventSource connects and renders events

- GIVEN a user viewing job detail page for a running job
- WHEN the page loads and EventSource connects
- AND progress events are received
- THEN each event is appended to a progress timeline visible on the page
- AND events render with step name, phase (start/complete/error), and message
- AND the timeline updates without full page refresh

#### Scenario: EventSource closes on terminal event

- GIVEN a user viewing job detail page with active EventSource
- WHEN a terminal event (complete/error) is received
- THEN the EventSource closes automatically
- AND a final status message is displayed
- AND no reconnection attempts are made

#### Scenario: EventSource unsupported falls back gracefully

- GIVEN a browser without EventSource support
- WHEN the job detail page loads
- THEN a fallback message is displayed
- AND no JavaScript errors occur
- AND existing HTMX auto-refresh continues working

#### Scenario: EventSource connection error handled

- GIVEN a user viewing job detail page
- WHEN the EventSource connection fails (network error, 500 error)
- THEN the error is logged to console
- AND a visible error message appears
- AND the page does not break or freeze

#### Scenario: progress timeline renders step phases

- GIVEN a running job emitting events for steps: etl, split, training
- WHEN events arrive via EventSource
- THEN the timeline renders phases in order: etl (start) → etl (complete) → split (start) → split (complete) → training (start) → training (complete)
- AND each phase shows status badge (queued/running/complete/error)
- AND step names are clickable or highlighted

### Requirement: Schema Migration for Percent Column

The system MUST modify job_events.percent column from INTEGER to REAL (nullable). Existing data must be preserved (empty table in production). The schema change MUST support storing float values from ProgressEvent.percent. Backward compatibility MUST be maintained for existing deployments.

#### Scenario: percent column stores float values

- GIVEN a ProgressEvent with percent: 75.5 (float)
- WHEN the event is persisted to job_events
- THEN the percent column stores 75.5 as REAL
- AND querying returns the exact float value (not truncated to integer)

#### Scenario: percent column stores null

- GIVEN a ProgressEvent with percent: None (not set)
- WHEN the event is persisted to job_events
- THEN the percent column stores NULL
- AND querying returns NULL (not 0)

#### Scenario: coarse progress stored as 0 or 100

- GIVEN a ProgressEvent for step start with percent: None
- WHEN the event is persisted for coarse-grained progress
- THEN percent is stored as NULL (not forced to 0)
- AND UI renders step as "in progress" (no percentage)

#### Scenario: schema migration preserves existing data

- GIVEN an existing deployment with job_events table (empty)
- WHEN the ALTER TABLE percent INTEGER → REAL runs
- THEN the schema change succeeds
- AND existing rows (none) are preserved
- AND the column accepts NULL values

### Requirement: SSE Event Format Contract

The SSE endpoint MUST emit events in a consistent JSON format. Each event MUST include id (seq), event (progress/complete/error), and data (JSON object with phase, step_name, message, percent, timestamp). Event names MUST distinguish between progress events and terminal events.

#### Scenario: SSE event format matches contract

- GIVEN a job_events record with seq=1, phase="start", step_name="etl", message="Processing ETL", percent=0.0, timestamp="2025-01-01T12:00:00Z"
- WHEN the SSE endpoint streams this event
- THEN the output format is: id: 1\nevent: progress\ndata: {"phase": "start", "step_name": "etl", "message": "Processing ETL", "percent": 0.0, "timestamp": "2025-01-01T12:00:00Z"}\n\n

#### Scenario: terminal event format matches contract

- GIVEN a job completing with status success
- WHEN the SSE endpoint sends the terminal event
- THEN the output format is: id: {final_seq}\nevent: complete\ndata: {"status": "success", "message": "..."}\n\n

#### Scenario: event names distinguish progress vs terminal

- GIVEN a client receiving mixed events from SSE stream
- WHEN events arrive
- THEN progress events have event: progress
- AND completion events have event: complete
- AND error events have event: error
- AND client can switch handling logic based on event name

### Requirement: Seq Ordering Guarantee

The system MUST guarantee that events are streamed in strict seq order (monotonically ascending). The SSE endpoint MUST query ORDER BY seq ASC and rely on the job_events table index (job_id, seq) for efficient retrieval. Clients MUST receive events in the same order they were generated.

#### Scenario: events streamed in seq order

- GIVEN a job with job_events records at seq=1, 2, 3, 4, 5
- WHEN GET /jobs/{job_id}/events is called
- THEN events are streamed in order: seq 1 → 2 → 3 → 4 → 5
- AND no event is skipped or reordered

#### Scenario: concurrent writes do not affect ordering

- GIVEN a running job writing events via progress_callback
- AND a web client reading via SSE endpoint simultaneously
- WHEN new events are inserted during an active SSE stream
- THEN the reader sees events in seq order (1, 2, 3, ...)
- AND no race condition causes out-of-order delivery

### Requirement: Concurrent Read-Write Isolation

The system MUST support concurrent reads (web SSE endpoint) and writes (worker progress_callback) on the job_events table. SQLite WAL mode MUST be enabled to allow non-blocking reads. The single writer (worker) and multiple readers (web clients) MUST operate without locks or deadlocks.

#### Scenario: worker writes while web reads

- GIVEN a running job with active SSE connections from multiple web clients
- WHEN the worker inserts a new job_events record
- THEN all active SSE connections receive the new event
- AND no database lock or deadlock occurs
- AND reads do not block writes

#### Scenario: multiple SSE clients read concurrently

- GIVEN a running job with 3 web clients connected to SSE endpoint
- WHEN new events are inserted by the worker
- THEN all 3 clients receive events in seq order
- AND no client blocks another (concurrent reads supported)

### Requirement: Coarse Progress Only Contract

The system MUST emit progress events ONLY for step boundaries (start, complete, error). Fine-grained percentage progress (e.g., "training iteration 450 of 1000") is OUT OF SCOPE for Phase 5. Events MUST have percent=NULL or coarse values (0 for start, 100 for complete).

#### Scenario: step start event has no percentage

- GIVEN a pipeline step starting execution
- WHEN ProgressEvent is emitted for phase="start"
- THEN percent is NULL (not forced to 0)
- AND UI shows "Step started" without percentage bar

#### Scenario: step complete event has coarse percentage

- GIVEN a pipeline step completing execution
- WHEN ProgressEvent is emitted for phase="complete"
- THEN percent is 100.0 (or NULL)
- AND UI shows "Step complete" with success indication

#### Scenario: step error event has no percentage

- GIVEN a pipeline step failing with error
- WHEN ProgressEvent is emitted for phase="error"
- THEN percent is NULL (error state)
- AND UI shows "Step failed" with error message

### Requirement: No Event Retention/Cleanup in Phase 5

The system MUST NOT implement event retention or cleanup logic in Phase 5. The job_events table MAY grow unbounded. Cleanup strategy (DELETE old events) is deferred to follow-up work. This is documented as technical debt.

#### Scenario: job_events table grows unbounded

- GIVEN a system running 1000 jobs over time
- WHEN each job writes 20 events to job_events
- THEN the table accumulates 20,000 rows
- AND no automatic cleanup or TTL is performed
- AND disk space grows linearly with job count

#### Scenario: old events remain queryable

- GIVEN a job completed 6 months ago with job_events records
- WHEN GET /jobs/{old_job_id}/events is called
- THEN old events are still returned
- AND no retention policy deletes or archives them

### Requirement: SSE Reconnect and Resume

The SSE live-progress stream MUST tolerate transient connection drops by relying on the browser's native EventSource reconnection, and MUST resume from the last received event using the `Last-Event-ID` header so that reconnection does not replay already-displayed events. Each event MUST carry an SSE `id:` field equal to its per-job `seq`.

#### Scenario: transient connection drop reconnects automatically

- GIVEN a user viewing the job detail page with an active SSE connection
- WHEN the network connection drops temporarily
- THEN the EventSource attempts automatic reconnection (native behavior)
- AND the client does not permanently close the stream on a transient error

#### Scenario: Last-Event-ID honored on reconnect

- GIVEN a client reconnecting after receiving events up to seq N
- WHEN the reconnection request hits GET /jobs/{job_id}/progress with `Last-Event-ID: N`
- THEN the endpoint starts streaming from seq > N (no replay of already-seen events)
- AND each streamed event carries an `id:` field equal to its `seq`
