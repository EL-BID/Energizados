# Delta for web-console — Phase 4

## ADDED Requirements

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
