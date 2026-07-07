# Tasks: web-console-phase2

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~530 lines (app.py: ~250, templates: ~180, tests: ~100) |
| 400-line budget risk | High-but-exception (user-approved size:exception) |
| Chained PRs recommended | No (single PR acceptable complexity) |
| Suggested split | Single PR (all work units in one change) |
| Delivery strategy | exception-ok (user-approved size:exception) |
| Chain strategy | single-pr |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: single-pr
400-line budget risk: High-but-exception

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Implement runs list + detail views + artifact serving (complete Phase 2) | Single PR | Includes security guards, templates, tests, navigation; all additive web layer changes |

## Phase 1: Security-Critical Foundation (Artifact Serving)

- [x] 1.1 Write failing test: `test_get_artifact_not_found_run()` — validates 404 when run_id doesn't exist before checking artifact path
- [x] 1.2 Write failing test: `test_get_artifact_path_traversal()` — validates 403/400 for `..` segments, absolute paths, backslashes
- [x] 1.3 Write failing test: `test_get_artifact_symlink_escape()` — validates 403 when resolved path escapes run_dir
- [x] 1.4 Write failing test: `test_get_artifact_success()` — validates 200 with correct content-type for valid plot artifact
- [x] 1.5 Write failing test: `test_get_artifact_cache_headers()` — validates Cache-Control header for cacheable file types
- [x] 1.6 Implement `_guess_media_type()` helper in `src/energizados/web/app.py` — maps file extensions to MIME types
- [x] 1.7 Implement `_is_cacheable()` helper in `src/energizados/web/app.py` — returns True for images/HTML
- [x] 1.8 Implement `GET /runs/{run_id}/artifacts/{path:path}` route with security guard — validates run_id, rejects traversal, double-checks resolved path
- [x] 1.9 Run artifact serving tests — ensure all security tests pass (RED→GREEN)

## Phase 2: Runs List View

- [x] 2.1 Write failing test: `test_list_runs_html_renders()` — validates 200 HTML response with runs table structure
- [x] 2.2 Write failing test: `test_list_runs_empty_state()` — validates empty array handling with 200 status
- [x] 2.3 Write failing test: `test_list_runs_status_filter()` — validates status=success filter works correctly
- [x] 2.4 Write failing test: `test_list_runs_limit()` — validates limit parameter truncates results
- [x] 2.5 Implement `GET /runs` route in `src/energizados/web/app.py` — calls `RunManager.list_runs()`, supports status filter and limit
- [x] 2.6 Create `src/energizados/web/templates/runs_list.html` — extends base.html, renders runs table with status_badge macro
- [x] 2.7 Add navigation link in `base.html` or `index.html` — add "Runs" link to reach `/runs`
- [x] 2.8 Run list view tests — ensure HTML rendering and filtering work (RED→GREEN)

## Phase 3: Template Helpers (Shared Infrastructure)

- [x] 3.1 Implement `_load_run_evaluation()` helper in `src/energizados/web/app.py` — detects single vs multi-model JSON, normalizes structure
- [x] 3.2 Implement `_list_run_configs()` helper in `src/energizados/web/app.py` — lists YAML files in run config directory
- [x] 3.3 Implement `_has_run_log()` helper in `src/energizados/web/app.py` — checks run.log presence
- [x] 3.4 Implement `_read_run_log()` helper in `src/energizados/web/app.py` — tails last N lines from log file
- [x] 3.5 Implement `_get_artifact_relative_path()` helper in `src/energizados/web/app.py` — converts absolute path to relative for artifact route
- [x] 3.6 Write unit tests for helpers in `tests/web/test_helpers.py` — cover single-model, multi-model, missing files scenarios

## Phase 4: Run Detail View

- [x] 4.1 Write failing test: `test_get_run_detail_existing()` — validates 200 with metadata section for valid run_id
- [x] 4.2 Write failing test: `test_get_run_detail_not_found()` — validates 404 for non-existent run_id
- [x] 4.3 Write failing test: `test_get_run_detail_single_model()` — validates metrics table renders from evaluation_report.json
- [x] 4.4 Write failing test: `test_get_run_detail_multi_model()` — validates ranking table renders from comparison.json
- [x] 4.5 Write failing test: `test_get_run_detail_with_eda()` — validates iframe present when eda_report exists
- [x] 4.6 Write failing test: `test_get_run_detail_without_eda()` — validates no iframe when eda_report missing
- [x] 4.7 Write failing test: `test_get_run_detail_with_log()` — validates log section renders when run.log present
- [x] 4.8 Implement `GET /runs/{run_id}` route in `src/energizados/web/app.py` — loads evaluation, configs, log, EDA path; returns 404 if run not found
- [x] 4.9 Create `src/energizados/web/templates/run_detail.html` — extends base.html, sections for metadata, metrics (single/multi), plots gallery, EDA iframe, configs, log
- [x] 4.10 Add plot detection logic in template or helper — glob `reports/evaluation/*.png` for gallery rendering
- [x] 4.11 Run detail view tests — ensure all variants render correctly (RED→GREEN)

## Phase 5: Job→Run Navigation

- [x] 5.1 Write failing test: `test_job_detail_with_run_id_shows_link()` — validates link to `/runs/{run_id}` present when job.run_id populated
- [x] 5.2 Write failing test: `test_job_detail_without_run_id_hides_link()` — validates no link when job.run_id absent
- [x] 5.3 Update `src/energizados/web/templates/job_detail.html` — conditional link to run detail based on job.run_id presence
- [x] 5.4 Run navigation tests — ensure link appears/disappears correctly (RED→GREEN)

## Phase 6: Integration Testing & Documentation

- [x] 6.1 Write integration test: `test_runs_list_to_detail_flow()` — validates user journey from list → detail → artifact
- [x] 6.2 Write integration test: `test_job_to_run_navigation_flow()` — validates job detail → run detail link flow
- [x] 6.3 Write security test: `test_artifact_traversal_comprehensive()` — validates multiple traversal vectors (nested ../, absolute, encoded dots)
- [x] 6.4 Update `docs/web-console/README.md` — add /runs and /runs/{run_id} endpoint documentation
- [x] 6.5 Update `docs/web-console/DEPLOYMENT.md` — mention new routes require no new infrastructure
- [x] 6.6 Run full test suite — `pytest tests/web/test_app.py tests/web/test_helpers.py tests/web/test_integration_runs.py`

## Traceability to Spec Requirements

| Spec Requirement | Task(s) | Phase |
|-----------------|---------|-------|
| Runs List Endpoint (all scenarios) | 2.1-2.8 | Phase 2 |
| Run Detail Endpoint (all scenarios) | 3.1-3.6, 4.1-4.11 | Phase 3-4 |
| Artifact Serving Endpoint (all scenarios) | 1.1-1.9 | Phase 1 |
| Job-Run Navigation (both scenarios) | 5.1-5.4 | Phase 5 |
| Security (path-traversal, symlink escape) | 1.2, 1.3, 6.3 | Phase 1, 6 |

## Implementation Order Notes

**Security-first approach**: Phase 1 (artifact serving) builds the critical foundation with path-traversal guards BEFORE any user-facing routes. This follows defense-in-depth: secure the file serving first, then build views on top.

**Helper extraction**: Phase 3 extracts shared logic (`_load_run_evaluation`, `_list_run_configs`, etc.) that both detail view and tests need, avoiding duplication.

**Template branching**: Phase 4 handles the key complexity — single vs multi-model evaluation structures. The template detects structure via `evaluation.is_multi` and renders appropriate table.

**Navigation integration**: Phase 5 is the "wiring" step — connecting the existing job detail to new run detail, completing the user journey.

**TDD discipline**: Each phase follows RED→GREEN→REFACTOR: write failing tests first, implement routes/templates, ensure tests pass.

**Risk profile**: Low complexity overall. The only security-sensitive code is Phase 1 (artifact serving), which has comprehensive test coverage for all attack vectors (traversal, symlinks, missing files).

**Dependencies**: Phase 3 (helpers) must complete before Phase 4 (detail view) can use them. Phase 1 (artifact serving) must complete before Phase 4 (detail view needs EDA iframe src) and Phase 2 (list view needs artifact links for plots).

**Parallel potential**: Phase 2 (list view) could theoretically run in parallel with Phase 1 (artifact serving), but security-first discipline recommends building the guarded foundation first. Phase 5 (navigation) is independent and could run anytime after Phase 4.
