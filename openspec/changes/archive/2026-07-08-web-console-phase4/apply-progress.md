# Apply Progress: web-console-phase4

## Status: COMPLETE ✓

**Apply phase completed** — all 20 tasks implemented across 3 slices. Branch `feat/web-console-phase4` (base `release/0.3.x`). 184 web tests passing (baseline 129 → +55 new), 0 failed.

## Summary

### Implementation Completed
All 20 TDD tasks completed:
- **Tasks 1-5**: Foundation + Timeline (Plotly CDN, Timeline API, Dashboard page)
- **Tasks 6-13**: Comparison View (Validation, batch loader, API, page, template)
- **Tasks 14-19**: Threshold Exploration (Data loader, API, UI integration)
- **Task 20**: Integration testing (Cross-view consistency, security, graceful degradation)

### Test Results
- **184 tests passing** (baseline 129 → +55 new tests for Phase 4)
- 5 skipped (pre-existing)
- 0 failed
- All pre-commit hooks passed: isort ✓, black ✓, bandit ✓, flake8 ✓

## Implementation Commits

### Commit e7dde8d — Foundation + Timeline (Tasks 1-9)
- Plotly CDN added to base.html
- Timeline API endpoint `/api/dashboard/timeline` (RunMetadata-only reads)
- Dashboard page `/dashboard` with Plotly chart
- Comparison helpers: `_parse_and_validate_run_ids`, `_load_run_evaluations_batch`

### Commit 5a5d631, 2908148 — Comparison View (Tasks 10-13)
- Comparison API endpoint `/api/runs/compare`
- Comparison page `/runs/compare` with SSR table
- CSV download functionality
- Best value highlighting

### Commit 6e75e7f — Orchestrator Fixes (Critical)
- **Route ordering fix**: `/runs/compare` declared BEFORE `/runs/{run_id}` (FastAPI shadowing bug)
- **SSR rewrite**: `compare_runs.html` server-rendered (CSR-vs-SSR mismatch with tests)
- **Jinja2 Undefined fixes**: Use `.get()` instead of direct attribute access
- **Helper additions**: `fmt_metric` global, comparison_json data island

### Commit 39efc33 — Threshold + Integration (Tasks 14-20)
- `_load_threshold_data` helper (direct eval JSON read)
- Threshold API endpoint `/api/runs/{run_id}/thresholds`
- `run_detail.html` threshold section extension
- Integration tests for cross-view consistency

## Critical Implementation Details

### 1. Route Ordering Fix
**Bug Discovered**: FastAPI matches `/runs/{run_id}` before `/runs/compare`, causing "compare" to be swallowed as a run_id parameter → 404 error.

**Fix Applied**: Declared `/runs/compare` (line 840) BEFORE `/runs/{run_id}` (line 911). All other routes safe from shadowing.

### 2. CSR vs SSR Architecture
**Decision**: Comparison view is SSR (metrics in response.text for test assertions), while threshold charts are CSR (Plotly fetch).

**Rationale**: Tests assert metric values in HTML response for comparison, requiring SSR. Threshold charts legitimately CSR (interactive Plotly).

### 3. Ensemble Threshold Handling
**Implementation**: Ensemble runs return `{is_multi: true, threshold_metrics: null, available_models: [...]}` from threshold endpoint.

**UI**: Shows ensemble-specific message: "Threshold exploration is not available for ensemble runs (comparison.json does not contain threshold sweep data)."

### 4. _load_threshold_data Direct Read
**Design**: Reads `evaluation_report.json` directly because `_load_run_evaluation` normalizes away `threshold_metrics`.

**Ensemble detection**: Checks for `comparison.json` presence first; if found, returns null metrics with available_models.

### 5. Graceful Degradation
- Timeline: Missing `val_auc`/`val_f1` preserved as None (gaps in chart)
- Comparison: Runs without eval JSON skipped (logs warning)
- Threshold: Old runs without `threshold_metrics` show "not available" message

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `src/energizados/web/app.py` | Added routes, helpers | ~200 |
| `src/energizados/web/templates/base.html` | Plotly CDN | 1 |
| `src/energizados/web/templates/dashboard.html` | NEW | ~100 |
| `src/energizados/web/templates/compare_runs.html` | NEW | ~120 |
| `src/energizados/web/templates/run_detail.html` | Threshold section | ~80 |
| `tests/web/test_*.py` | 5 new test files, +55 tests | ~800 |

## Quality Gates Passed
- ✓ All 184 tests passing
- ✓ Pre-commit hooks (isort, black, bandit, flake8)
- ✓ Route shadowing resolved
- ✓ Jinja2 Undefined handling fixed
- ✓ SSR/CSR architecture consistent

## Ready for Verification
Apply phase complete with all tasks implemented. Ready for sdd-verify phase to validate against spec requirements.
