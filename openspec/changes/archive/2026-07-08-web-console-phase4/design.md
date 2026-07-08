# Design: web-console-phase4

## Executive Summary

Add three new views to the web console: timeline dashboard, side-by-side comparison, and threshold exploration. Reuse existing `_load_run_evaluation` pattern, add Plotly CDN to base.html, and gracefully handle missing data for ensemble runs and old runs.

---

## 1. Route Architecture

### 1.1 HTML Routes (Browser-Rendered)

**GET /dashboard**
- Query params: `limit=20` (default), `status=success|partial|failed` (optional)
- Returns: HTML page with timeline chart
- Content negotiation: none (HTML only)

**GET /runs/compare**
- Query params: `ids=id1,id2,id3,...` (comma-separated, required, min 2 max 10)
- Returns: HTML comparison table
- Content negotiation: none (HTML only)

**GET /runs/{run_id}** (existing, extended)
- No changes to signature
- Template adds threshold exploration section if data available

### 1.2 JSON API Endpoints (Client-Side Fetch)

**GET /api/dashboard/timeline**
- Query params: `limit=100` (default), `status` (optional)
- Returns: `{timestamps: [], auc: [], f1: [], run_ids: []}`
- All values from RunMetadata only (no eval JSON reads)

**GET /api/runs/compare**
- Query params: `ids=id1,id2,id3,...`
- Returns: `{runs: {run_id: {run_metadata, evaluation, available_models}}}`
- `evaluation` follows `_load_run_evaluation` normalization
- `available_models`: list of model names for ensemble (null for single-model)
- 400 if <2 or >10 IDs

**GET /api/runs/{run_id}/thresholds**
- Returns: `{threshold_metrics: {...}, cumulative_gains: {...}, current_threshold, available_models}`
- `threshold_metrics`: null if not available (ensemble or old run)
- `cumulative_gains`: null if not available
- `available_models`: model name list for ensemble (threshold data per-model not available in current schema)
- 404 if run not found or eval JSON missing

---

## 2. Helper Functions (app.py)

### 2.1 Batch Evaluation Loader

```python
def _load_run_evaluations_batch(run_ids: List[str]) -> Dict[str, Dict]:
    """
    Load evaluation data for multiple runs, tolerant to missing files.

    Returns dict mapping run_id to normalized evaluation data (or None if missing).
    Uses _load_run_evaluation internally for consistency.
    """
    results = {}
    for run_id in run_ids:
        eval_data = _load_run_evaluation(run_id)
        if eval_data:
            results[run_id] = eval_data
    return results
```

**Location**: `app.py` (after existing `_load_run_evaluation`)

**Rationale**:
- Keep in app.py with other helpers
- Reuses `_load_run_evaluation` for single/multi normalization
- Skips missing eval JSONs gracefully (partial results)

### 2.2 Threshold Data Loader

```python
def _load_threshold_data(run_id: str) -> Optional[Dict]:
    """
    Load threshold sweep and cumulative gains data directly from eval JSON.

    Bypasses _load_run_evaluation because it normalizes away threshold_metrics.
    Reads evaluation_report.json directly; returns null for ensemble runs
    (comparison.json does not contain threshold_metrics per current schema).

    Returns:
        - threshold_metrics: {thresholds, precisions, recalls, f1s} or null
        - cumulative_gains: {deciles, cumulative_gain, cumulative_population} or null
        - current_threshold: float from metrics.threshold
        - available_models: list of model names if ensemble, null otherwise
        - is_multi: bool
    """
    manager = RunManager()
    run_dir = manager.run_dir(run_id)
    if not run_dir:
        return None

    # Check for multi-model first
    comparison_path = run_dir / "reports" / "evaluation" / "comparison.json"
    if comparison_path.is_file():
        try:
            data = json.loads(comparison_path.read_text())
            return {
                "threshold_metrics": None,  # Not available in comparison.json
                "cumulative_gains": None,
                "current_threshold": None,
                "available_models": data.get("ranking", []),
                "is_multi": True,
            }
        except (json.JSONDecodeError, IOError):
            pass

    # Single-model
    report_path = run_dir / "reports" / "evaluation" / "evaluation_report.json"
    if report_path.is_file():
        try:
            data = json.loads(report_path.read_text())
            metrics = data.get("metrics", {})
            return {
                "threshold_metrics": data.get("threshold_metrics"),
                "cumulative_gains": metrics.get("cumulative_gains"),
                "current_threshold": metrics.get("threshold", 0.5),
                "available_models": None,
                "is_multi": False,
            }
        except (json.JSONDecodeError, IOError):
            pass

    return None
```

**Location**: `app.py`

**Design Decision**: Ensemble runs do NOT have threshold_metrics in the current schema. The `_load_threshold_data` helper returns `threshold_metrics: null` for ensemble runs with `available_models` populated so UI can show "Threshold exploration not available for ensemble runs" message.

---

## 3. Template Architecture

### 3.1 base.html Changes

Add Plotly CDN in `<head>` (before `extra_head` block):

```html
<!-- Plotly.js for interactive charts -->
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
```

**Justification**: All three new views use Plotly for charts. Adding to base.html avoids duplication and enables Plotly for future features.

### 3.2 dashboard.html (NEW)

**Structure**:
- Extends `base.html`
- Status filter dropdown (HTMX refresh)
- Timeline chart container (`<div id="timeline-chart">`)
- "No runs found" message if empty

**JavaScript**:
```javascript
fetch('/api/dashboard/timeline?limit={{ limit }}&status={{ status }}')
  .then(r => r.json())
  .then(data => {
    const traceAUC = { x: data.timestamps, y: data.auc, name: 'AUC', mode: 'lines+markers' };
    const traceF1 = { x: data.timestamps, y: data.f1, name: 'F1', mode: 'lines+markers' };
    const layout = { title: 'Metrics Evolution', xaxis: { title: 'Timestamp' }, yaxis: { title: 'Score' } };
    Plotly.newPlot('timeline-chart', [traceAUC, traceF1], layout);

    // Click handler to open run detail
    document.getElementById('timeline-chart').on('plotly_click', (data) => {
      const runId = data.points[0].data.runs[data.points[0].pointNumber];
      window.open(`/runs/${runId}`, '_blank');
    });
  });
```

**Custom Data**: Pass `run_ids` as custom data array to enable click-through.

### 3.3 compare_runs.html (NEW)

**Structure**:
- Extends `base.html`
- Comparison table with columns: Run ID, Model(s), AUC, F1, Precision, Recall, Threshold
- Best value highlighting (★ marker for highest AUC/F1/Precision/Recall)
- Multi-model runs show ranking table
- "Download CSV" button

**JavaScript**:
- Fetch from `/api/runs/compare?ids=...`
- Render table dynamically
- CSV export using `Blob` + `URL.createObjectURL`

**Template Logic**:
- Iterate through runs dict
- For `is_multi=true`: show ranking table from `evaluation.ranking`
- For `is_multi=false`: show single metrics row
- Highlight best values across all compared runs

### 3.4 run_detail.html Extension (EXISTING, MODIFIED)

**Add after Metrics section**:

```html
<!-- Threshold Exploration section -->
<section class="mb-4" id="thresholds-section">
    <h5>🎯 Threshold Exploration</h5>
    <div id="threshold-loading" class="text-muted">Loading...</div>
    <div id="threshold-charts" style="display: none;">
        <div id="pr-chart" style="height: 400px;"></div>
        <div id="gains-chart" style="height: 400px;"></div>
        <div id="threshold-controls" class="mt-3">
            <label>Threshold: <span id="threshold-value">0.50</span></label>
            <input type="range" id="threshold-slider" min="0" max="1" step="0.01" value="0.5">
            <div id="metrics-at-threshold" class="mt-2">
                <span>Precision: <strong id="precision-value">-</strong></span> |
                <span>Recall: <strong id="recall-value">-</strong></span> |
                <span>F1: <strong id="f1-value">-</strong></span>
            </div>
        </div>
    </div>
    <div id="threshold-unavailable" style="display: none;" class="alert alert-info">
        Threshold data not available. {{ threshold_unavailable_message }}
    </div>
</section>

<script>
fetch('/api/runs/{{ run.run_id }}/thresholds')
  .then(r => {
    if (!r.ok) throw new Error('Not found');
    return r.json();
  })
  .then(data => {
    if (data.threshold_metrics && data.cumulative_gains) {
      // Render charts
      document.getElementById('threshold-loading').style.display = 'none';
      document.getElementById('threshold-charts').style.display = 'block';

      // Precision/Recall vs Threshold
      const prTrace = {
        x: data.threshold_metrics.thresholds,
        y: data.threshold_metrics.precisions,
        name: 'Precision',
        mode: 'lines'
      };
      const recTrace = {
        x: data.threshold_metrics.thresholds,
        y: data.threshold_metrics.recalls,
        name: 'Recall',
        mode: 'lines'
      };
      Plotly.newPlot('pr-chart', [prTrace, recTrace], {
        title: 'Precision/Recall vs Threshold',
        xaxis: { title: 'Threshold' },
        yaxis: { title: 'Score' }
      });

      // Cumulative Gains
      const gainsTrace = {
        x: data.cumulative_gains.cumulative_population,
        y: data.cumulative_gains.cumulative_gain,
        mode: 'lines+markers'
      };
      Plotly.newPlot('gains-chart', [gainsTrace], {
        title: 'Cumulative Gains',
        xaxis: { title: 'Cumulative Population' },
        yaxis: { title: 'Cumulative Gain' }
      });

      // Slider interaction
      const slider = document.getElementById('threshold-slider');
      slider.addEventListener('input', (e) => {
        const t = parseFloat(e.target.value);
        // Interpolate metrics at threshold
        const idx = data.threshold_metrics.thresholds.findIndex(v => v >= t);
        if (idx >= 0) {
          document.getElementById('precision-value').textContent =
            data.threshold_metrics.precisions[idx].toFixed(3);
          document.getElementById('recall-value').textContent =
            data.threshold_metrics.recalls[idx].toFixed(3);
          document.getElementById('f1-value').textContent =
            data.threshold_metrics.f1s[idx].toFixed(3);
        }
      });
    } else {
      document.getElementById('threshold-loading').style.display = 'none';
      document.getElementById('threshold-unavailable').style.display = 'block';
    }
  })
  .catch(() => {
    document.getElementById('threshold-loading').style.display = 'none';
    document.getElementById('threshold-unavailable').style.display = 'block';
  });
</script>
```

**Template Variable**: Pass `threshold_unavailable_message` from route handler:
- For ensemble runs: "Threshold exploration is not available for ensemble runs (comparison.json does not contain threshold sweep data). View individual model reports for detailed threshold analysis."
- For old runs: "This run was created before threshold sweep data was added to evaluation reports."

---

## 4. Multi-Model Handling

### 4.1 Comparison View

**Ensemble runs**: Show ranking table from `evaluation.ranking`. Each row shows model name and metrics from `evaluation.models[name].metrics`.

**Single-model runs**: Show one row with metrics from `evaluation.metrics`.

**Best value highlighting**: Compute max across all runs' metrics, apply ★ marker.

### 4.2 Threshold Exploration

**Ensemble runs**: NOT SUPPORTED in current schema. `comparison.json` does not contain `threshold_metrics` per model. UI shows informative message directing users to individual model reports.

**Single-model runs**: Full support via `/api/runs/{run_id}/thresholds`.

**Future extension**: If threshold_metrics are added to comparison.json schema, the API can be extended to return `threshold_metrics_by_model: {model_name: {...}}`.

---

## 5. Security Validation

### 5.1 Run ID Parsing

```python
def _parse_and_validate_run_ids(ids_str: str, max_count: int = 10) -> List[str]:
    """
    Parse comma-separated run IDs with validation.

    - Reject if > max_count IDs
    - Reject if any ID contains path traversal chars (.., /, \)
    - Reject if any ID is empty
    - Return validated list or raise HTTPException(400)
    """
    if not ids_str:
        raise HTTPException(status_code=400, detail="ids parameter required")

    raw_ids = ids_str.split(",")
    if len(raw_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 run IDs required")
    if len(raw_ids) > max_count:
        raise HTTPException(status_code=400, detail=f"Maximum {max_count} run IDs allowed")

    validated = []
    for run_id in raw_ids:
        run_id = run_id.strip()
        if not run_id:
            continue
        if ".." in run_id or "/" in run_id or "\\" in run_id:
            raise HTTPException(status_code=400, detail=f"Invalid run_id: {run_id}")
        validated.append(run_id)

    if len(validated) < 2:
        raise HTTPException(status_code=400, detail="At least 2 valid run IDs required")

    return validated
```

### 5.2 Run Existence Validation

After parsing IDs, validate each via `RunManager.get_run()`. Skip missing runs in comparison (log warning). Return 404 only if ALL runs are missing.

---

## 6. Error Handling

Follow `_HtmxErrorResponse` pattern for HTMX requests (though these endpoints are primarily JSON/HTML, not HTMX fragments).

For JSON endpoints, return structured errors:
```python
return JSONResponse(
    status_code=400,
    content={"error": "invalid_ids", "message": "At least 2 valid run IDs required"}
)
```

For HTML routes, raise `HTTPException` which FastAPI renders as error page (consistent with existing routes).

---

## 7. Graceful Degradation

### 7.1 Old Runs Without threshold_metrics

**Scenario**: Pre-v0.2 runs or runs where `threshold_metrics` calculation failed.

**Handling**:
- `/api/runs/{run_id}/thresholds` returns `threshold_metrics: null, cumulative_gains: null`
- Template shows "Threshold data not available" message
- Chart section not rendered

### 7.2 Runs Without Eval JSON

**Scenario**: Run directory exists but `evaluation_report.json` missing (failed run, partial execution).

**Handling**:
- `_load_run_evaluation` returns `None`
- `_load_threshold_data` returns `None`
- Comparison view skips run (logs warning)
- Timeline view still shows run (uses RunMetadata only)

### 7.3 Ensemble Runs Without Threshold Data

**Scenario**: Ensemble run where `comparison.json` exists but lacks `threshold_metrics`.

**Handling**:
- `_load_threshold_data` returns `threshold_metrics: null, available_models: [...]`
- UI shows ensemble-specific message explaining limitation

---

## 8. Route Implementation Summary

### 8.1 Dashboard

```python
@app.get("/dashboard")
async def dashboard_page(request: Request, limit: int = 20, status: Optional[str] = None):
    manager = RunManager()
    filter_dict = {"status": status} if status else None
    runs = manager.list_runs(filter=filter_dict, limit=limit)
    return templates.TemplateResponse(request, "dashboard.html", {
        "runs": runs,
        "limit": limit,
        "status": status,
    })

@app.get("/api/dashboard/timeline")
async def timeline_data(limit: int = 100, status: Optional[str] = None):
    manager = RunManager()
    filter_dict = {"status": status} if status else None
    runs = manager.list_runs(filter=filter_dict, limit=limit)
    return {
        "timestamps": [r.timestamp for r in runs],
        "auc": [r.val_auc for r in runs],
        "f1": [r.val_f1 for r in runs],
        "run_ids": [r.run_id for r in runs],
    }
```

### 8.2 Comparison

```python
@app.get("/runs/compare")
async def compare_runs_page(request: Request, ids: str = ""):
    run_ids = _parse_and_validate_run_ids(ids, max_count=10)
    manager = RunManager()

    runs_data = []
    for run_id in run_ids:
        run = manager.get_run(run_id)
        if run:
            eval_data = _load_run_evaluation(run_id)
            runs_data.append({
                "run_id": run_id,
                "run": run,
                "evaluation": eval_data,
            })
        else:
            logger.warning(f"Run not found: {run_id}")

    if not runs_data:
        raise HTTPException(status_code=404, detail="No valid runs found")

    return templates.TemplateResponse(request, "compare_runs.html", {
        "runs": runs_data,
        "ids": ids,
    })

@app.get("/api/runs/compare")
async def compare_runs_json(ids: str = ""):
    run_ids = _parse_and_validate_run_ids(ids, max_count=10)
    manager = RunManager()

    results = {}
    for run_id in run_ids:
        run = manager.get_run(run_id)
        if run:
            eval_data = _load_run_evaluation(run_id)
            results[run_id] = {
                "run_metadata": run.to_dict(),
                "evaluation": eval_data,
                "available_models": eval_data.get("ranking") if eval_data and eval_data.get("is_multi") else None,
            }

    return {"runs": results}
```

### 8.3 Threshold Exploration

```python
@app.get("/api/runs/{run_id}/thresholds")
async def get_threshold_sweep(run_id: str):
    manager = RunManager()
    run = manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    threshold_data = _load_threshold_data(run_id)
    if not threshold_data:
        raise HTTPException(status_code=404, detail="Evaluation data not found")

    return threshold_data
```

**Update to `/runs/{run_id}` route** (existing):
- Determine `threshold_unavailable_message` based on run type:
  - If `threshold_data["is_multi"]`: ensemble message
  - Else if `threshold_data["threshold_metrics"] is None`: old run message
  - Else: `None` (data available)
- Pass to template for threshold section

---

## 9. File Structure Changes

```
src/energizados/web/
├── app.py                          # ADD: dashboard_page, compare_runs_page, get_threshold_sweep,
                                    #      _load_run_evaluations_batch, _load_threshold_data,
                                    #      _parse_and_validate_run_ids
├── templates/
│   ├── base.html                   # ADD: Plotly CDN
│   ├── dashboard.html              # NEW
│   ├── compare_runs.html           # NEW
│   └── run_detail.html             # ADD: threshold exploration section
```

---

## 10. Open Design Questions

1. **Per-model threshold data for ensembles**: Current schema does not include `threshold_metrics` in `comparison.json`. Should this be added in a future PR, or is the current approach (direct users to individual model reports) sufficient?

2. **Timeline date range**: Proposal specifies "last N runs only". Should future work support custom date ranges (e.g., `?from=2024-01-01&to=2024-12-31`)?

3. **Comparison CSV format**: Should CSV include all metrics or a subset? Current design exports all metrics from evaluation.

---

## 11. Risks

1. **Performance**: Comparison of 10 ensemble runs may be slow (reads 10 comparison.json files). Mitigation: client-side loading spinner, cap at 10 runs.

2. **Browser memory**: Plotly charts with 1000+ timeline points may be slow. Mitigation: default limit to 20 on dashboard, API supports up to 100 for power users.

3. **Missing data**: Old runs without `threshold_metrics` or `cumulative_gains` show "not available" message. User education needed.

4. **Path traversal**: Run ID validation is critical. Double defense: parse validation + RunManager.get_run() rejection.

---

## 12. Testing Considerations

- Test timeline with empty runs list
- Test comparison with mix of single-model and ensemble runs
- Test comparison with missing/invalid run IDs
- Test threshold exploration with single-model run (verify charts render)
- Test threshold exploration with ensemble run (verify "not available" message)
- Test threshold exploration with old run (no threshold_metrics in JSON)
- Test path traversal attempts in ids parameter
- Test status filter on dashboard (success/partial/failed)
