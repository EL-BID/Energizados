# Proposal: web-console-phase4

## Intent

Add a metrics dashboard to the web console that enables users to:
1. **View evolution** of AUC/F1 metrics across the last N runs (timeline view)
2. **Compare 2+ runs** side-by-side with full metrics breakdown
3. **Explore thresholds** with precision/recall curves and cumulative gains charts per run

This addresses PRD requirement "Dashboard de métricas (evolución de AUC/F1, comparativa entre ejecuciones)" and enables data-driven model selection without opening individual reports.

## Scope

### In-Scope
1. **Timeline View** (`GET /dashboard`)
   - Line chart showing AUC/F1 evolution across last 20 runs (configurable limit)
   - Uses `RunMetadata.val_auc` and `RunMetadata.val_f1` only — NO eval JSON reads
   - Filters by status (success/partial/failed)
   - Click point to jump to run detail
   - Responsive Plotly chart (already loaded in base template)

2. **Comparison View** (`GET /runs/compare?ids=...`)
   - Side-by-side metrics table for 2-10 selected runs
   - Reads `evaluation_report.json` or `comparison.json` per run
   - Shows: AUC, F1, Precision, Recall, Accuracy, Confusion Matrix, Threshold
   - Highlights best values across compared runs
   - Download comparison as CSV

3. **Threshold Exploration** (per-run detail extension)
   - Add new section to `/runs/{run_id}` for threshold sweep visualization
   - Precision/Recall vs Threshold curve (from `threshold_metrics` in eval JSON)
   - Cumulative Gains chart (from `cumulative_gains` in eval JSON)
   - Interactive sliders to explore operating points
   - Display metrics-at-threshold dynamically

4. **New JSON data endpoints**
   - `GET /api/dashboard/timeline?limit=20` — timeline data (RunMetadata only)
   - `GET /api/runs/compare?ids=...` — full metrics for comparison (lazy eval JSON load)
   - `GET /api/runs/{run_id}/thresholds` — threshold sweep data

5. **Reuses existing helpers**
   - `_load_run_evaluation(run_id)` for single/multi-model normalization
   - `RunManager.list_runs()` for timeline metadata
   - Existing template patterns (HTMX fragments, Plotly)

### Out-of-Scope
- Auth/RBAC (trust boundary unchanged)
- Real-time SSE/live updates (PRD #6)
- Hyperparameter search visualization (PRD #4)
- Dataset versioning integration
- Custom date ranges for timeline (last N runs only)
- Export comparison to PDF/PowerPoint
- Historical run aggregation (summary tables by week/month)

## Approach

### 1. Timeline View (Zero Eval JSON Reads)
```python
# GET /dashboard — new route
@app.get("/dashboard")
async def dashboard_page(request: Request, limit: int = 20, status: Optional[str] = None):
    manager = RunManager()
    filter_dict = {"status": status} if status else None
    runs = manager.list_runs(filter=filter_dict, limit=limit)
    # Reverse to show newest first (RunManager returns asc)
    runs = list(reversed(runs))
    return templates.TemplateResponse(request, "dashboard.html", {"runs": runs})

# GET /api/dashboard/timeline — JSON for Plotly
@app.get("/api/dashboard/timeline")
async def timeline_data(limit: int = 100, status: Optional[str] = None):
    manager = RunManager()
    filter_dict = {"status": status} if status else None
    runs = manager.list_runs(filter=filter_dict, limit=limit)
    runs = list(reversed(runs))
    return {
        "timestamps": [r.timestamp for r in runs],
        "auc": [r.val_auc for r in runs],
        "f1": [r.val_f1 for r in runs],
        "run_ids": [r.run_id for r in runs],
    }
```

**Template `dashboard.html`:**
- Extends `base.html` (already has Plotly CDN)
- Single Plotly line chart with two series (AUC, F1)
- X-axis: timestamp, Y-axis: metric value
- Click handler to open `/runs/{run_id}` in new tab
- Status filter dropdown (HTMX refresh)

### 2. Comparison View (Batch Eval JSON Loader)
```python
# New helper in app.py
def _load_run_evaluations_batch(run_ids: List[str]) -> Dict[str, Dict]:
    """Load evaluation data for multiple runs, tolerant to missing files."""
    results = {}
    for run_id in run_ids:
        eval_data = _load_run_evaluation(run_id)
        if eval_data:
            results[run_id] = eval_data
    return results

# GET /runs/compare?ids=id1,id2,id3
@app.get("/runs/compare")
async def compare_runs(request: Request, ids: str = ""):
    run_ids = ids.split(",") if ids else []
    if len(run_ids) < 2:
        raise HTTPException(400, "At least 2 run IDs required")

    manager = RunManager()
    runs_data = []
    for run_id in run_ids:
        run = manager.get_run(run_id)
        if run:
            eval_data = _load_run_evaluation(run_id)
            runs_data.append({"run": run, "eval": eval_data})

    return templates.TemplateResponse(request, "compare_runs.html", {"runs": runs_data})

# GET /api/runs/compare?ids=...
@app.get("/api/runs/compare")
async def compare_runs_json(ids: str = ""):
    run_ids = ids.split(",") if ids else []
    evals = _load_run_evaluations_batch(run_ids)
    return {"runs": evals}
```

**Template `compare_runs.html`:**
- Metrics table (AUC, F1, Precision, Recall, Accuracy, Threshold)
- Confusion matrix comparison side-by-side
- Best value highlighting
- Multi-model runs show ranking
- "Add to comparison" button (bookmarklet format)

### 3. Threshold Exploration (Per-Run Extension)
```python
# GET /api/runs/{run_id}/thresholds
@app.get("/api/runs/{run_id}/thresholds")
async def get_threshold_sweep(run_id: str):
    eval_data = _load_run_evaluation(run_id)
    if not eval_data:
        raise HTTPException(404, "Evaluation not found")

    # Load full JSON to get threshold_metrics
    manager = RunManager()
    run_dir = manager.run_dir(run_id)
    report_path = run_dir / "reports" / "evaluation" / "evaluation_report.json"

    if not report_path.exists():
        raise HTTPException(404, "Report not found")

    data = json.loads(report_path.read_text())
    threshold_metrics = data.get("threshold_metrics")
    cumulative_gains = data.get("metrics", {}).get("cumulative_gains")

    return {
        "threshold_metrics": threshold_metrics,
        "cumulative_gains": cumulative_gains,
        "current_threshold": data.get("metrics", {}).get("threshold", 0.5),
    }
```

**Extension to `run_detail.html`:**
- New `<section id="thresholds">` with:
  - Interactive Plotly Precision/Recall vs Threshold chart
  - Interactive Plotly Cumulative Gains chart
  - Slider widget to select threshold
  - Dynamic metrics display (Precision, Recall, F1 @ threshold)

### 4. File Structure
```
src/energizados/web/
├── app.py              # Add: dashboard_page, compare_runs, get_threshold_sweep, _load_run_evaluations_batch
├── templates/
│   ├── base.html       # (unchanged — Plotly already loaded)
│   ├── dashboard.html  # NEW: timeline view
│   ├── compare_runs.html  # NEW: comparison table
│   └── run_detail.html    # ADD: threshold exploration section
```

### 5. Design Decisions
- **Client-side charting**: Plotly already loaded; no server-side rendering complexity
- **Lazy loading**: Comparison endpoint reads eval JSONs on demand; no precomputation
- **RunMetadata for timeline**: Avoids N eval JSON reads; O(1) per run vs O(k) with full data
- **Threshold data in JSON**: Already written by `ReportGenerator.generate_json()` via `threshold_metrics` key
- **Multi-model handling**: `_load_run_evaluation` returns `is_multi=True` with `ranking` for comparison view
- **Missing data tolerance**: `_load_run_evaluations_batch` skips runs without eval JSONs (partial results)

### 6. Data Model Verification
- **`evaluation_report.json`** contains:
  - `metrics.auc`, `metrics.f1`, `metrics.precision`, `metrics.recall`, `metrics.threshold`
  - `threshold_metrics` = `{thresholds: [], precisions: [], recalls: [], f1s: []}`
  - `metrics.cumulative_gains` = `{deciles: [], cumulative_gain: [], cumulative_population: []}`
  - `metrics.confusion_matrix` = `{tp, fp, fn, tn, matrix: [[tn, fp], [fn, tp]]}`
- **`comparison.json`** contains:
  - `ranking: []` (model names sorted by AUC)
  - `models: {name: {metrics: {}, info: {}}}`
- **`RunMetadata`** contains:
  - `val_auc`, `val_f1`, `timestamp`, `status`, `duration_seconds`, `model_types`

All required data is present in existing files.

## Non-Goals
- Auth/RBAC
- Real-time updates
- Hyperparameter search integration
- Custom date range queries
- Export to slide formats
- Historical aggregation

## Constraints
- Must reuse existing Plotly.js (no new charting libraries)
- Must reuse `_load_run_evaluation` pattern
- No framework core changes
- No new external dependencies
- Must handle both single-model and multi-model (ensemble) runs
- Must tolerate missing/old runs (graceful degradation)

## Review Workload Note
**Expected PR size**: ~500-600 lines (3 templates + ~200 lines in app.py). This exceeds the 400-line PR budget guidance. Recommend a chained-PR split:
1. PR1: Timeline view (dashboard.html + api endpoint)
2. PR2: Comparison view (compare_runs.html + batch loader)
3. PR3: Threshold exploration (run_detail.html extension + threshold endpoint)

This will be resolved at the tasks phase; flagging here for planning.

## Dependencies
- None new (everything reuses existing code paths)
- Plotly.js already in base.html (loaded for EDA embed)

## Risks
1. **Performance**: Comparison view reads eval JSONs for N runs; if N=10 and JSONs are large, may be slow. Mitigation: client-side loading spinner, limit max N=10.
2. **Old runs**: Pre-v0.2 runs may lack `threshold_metrics` in JSON. Mitigation: graceful fallback (show "Threshold data not available" message).
3. **Multi-model runs**: Comparison view needs to handle both structures (single vs ranking). Mitigation: `_load_run_evaluation` already normalizes this.
4. **Path resolution**: `run_dir` resolution relies on `RunManager`. If run directory is manually deleted, 404 handling needed. Mitigation: `_load_run_evaluation` returns None, skip gracefully.

## Success Criteria
- Timeline renders within 200ms (RunMetadata-only read)
- Comparison of 5 runs completes within 2 seconds
- Threshold exploration loads per run in <500ms
- All views handle missing eval JSONs gracefully
- Comparison CSV download works
- Multi-model runs show ranking correctly
