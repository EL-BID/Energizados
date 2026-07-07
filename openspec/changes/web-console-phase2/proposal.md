# Proposal: web-console-phase2

## Intent

Enable operators to view completed pipeline run results (metrics, plots, EDA reports, and configs) directly in a web browser. Eliminates the need to open individual report files and completes the "centralized monitoring" vision for historical runs.

## Scope

### In Scope
- **Runs list view** (`GET /runs`) — paginated table of executions from `RunManager.list_runs()` showing status, model types, AUC, F1, duration, and timestamp
- **Run detail view** (`GET /runs/{run_id}`) — metadata, evaluation JSON (single-model and multi-model), generated plots, config files, run log, and embedded EDA report via iframe
- **Safe artifact serving** (`GET /runs/{run_id}/artifacts/{path:path}`) — guarded file serving for plots, reports, and EDA HTML
- **Navigation integration** — job detail page links to run detail when `job.run_id` is present

### Out of Scope
- Plan/dry-run preview (`Pipeline.plan()` — ETL-only, limited value)
- Metrics dashboard / evolution across runs (PRD #5)
- Real-time progress via SSE (PRD #6)
- Auth/RBAC (Phase 1 assumption still applies)

## Capabilities

### Modified Capabilities
- **web-console**: Add runs list/detail views and artifact serving routes (read-only extension, no framework changes)

## Approach

**Thin FastAPI view layer over existing `RunManager` APIs** — no framework core modifications. Add 3 new routes:
1. `GET /runs` — list runs with pagination/filter
2. `GET /runs/{run_id}` — render detail page with metadata, metrics, plots, EDA embed
3. `GET /runs/{run_id}/artifacts/{path:path}` — guarded file serving

**Jinja2 templates**: `runs_list.html` (table), `run_detail.html` (comprehensive detail), both extending `base.html`. Template branches for single-model (`evaluation_report.json`) vs multi-model (`comparison.json`) structures.

**Artifact serving security**: Reuse `RunManager.get_run()` to validate `run_id`, then guard `artifact_path` (reject `..`, absolute paths), resolve and double-check `resolved.startswith(run_resolved)` before serving.

**EDA embed**: Serve `eda_report.html` (autocontained) via artifact route, embed in `<iframe>`.

**Job-run navigation**: When `job.run_id` populated, link from job detail to run detail.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/web/app.py` | Modified | Add 3 new routes, update navigation in templates |
| `src/energizados/web/templates/` | New | Add `runs_list.html`, `run_detail.html` |
| `src/energizados/core/builders/run_manager.py` | None | Use existing APIs only (`list_runs`, `get_run`) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Path traversal in artifact serving | Low | Reuse proven guard pattern from exploration (validate run_id, reject `..`, resolve-and-check) |
| Large plot/EDA file serving performance | Medium | Add cache headers (`Cache-Control: public, max-age=3600`) |
| Multi-model JSON structure differs | Low | Template branches on structure detection (`comparison.json` vs `evaluation_report.json`) |
| `list_runs()` slowdown with many runs | Low | Default `limit=100`, pagination in UI |

## Rollback Plan

Remove the 3 new routes and 2 new templates. Revert navigation changes in job detail. No framework core changes to revert — pure web layer addition.

## Dependencies

- None (uses existing stable APIs: `RunManager`, `RunMetadata`, artifact structure)

## Success Criteria

- [ ] Operators can view all runs in a paginated list with key metrics
- [ ] Run detail page renders correctly for both single-model and multi-model runs
- [ ] Plots and EDA report load and display in browser
- [ ] Artifact serving blocks path traversal attempts
- [ ] Job detail page links to run detail when `run_id` present
