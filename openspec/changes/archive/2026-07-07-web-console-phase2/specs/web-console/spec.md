# Delta for web-console

## ADDED Requirements

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

## Non-goals

Plan/dry-run preview (`Pipeline.plan()` results) · metrics dashboard and evolution across runs (PRD #5) · real-time progress via Server-Sent Events (PRD #6) · authentication and RBAC (Phase 1 assumption still applies) · drag-and-drop YAML editor · dataset versioning UI · hyperparameter search from UI
