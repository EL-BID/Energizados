# Proposal: web-console-phase3

## Intent

Enable operators to preview the execution plan (DAG of ETL steps) **before** enqueuing a job. Closes the MVP workflow "validate config -> preview plan -> execute" (PRD section 6 item 3 + section 9 Phase 3). Prevents surprises from dependency ordering or circular references in complex ETL pipelines.

## Scope

### In Scope

- **`POST /plan` endpoint** — new route receiving YAML/JSON config, validating schema via `validate_dict()`, checking custom_class prefixes via `_check_custom_class_prefixes()`, and returning `ExecutionPlan` via `Pipeline.plan()`
- **Content negotiation (HTMX)** — returns HTML fragment (`components/plan_preview.html`) if `HX-Request` header present, JSON otherwise
- **"Preview Plan" button** — added to `templates/components/editor.html`, submits to `/plan` with `hx-target="#validation-output"`, displays plan inline
- **Error handling** — catches `ETLDependencyError` (cycles) and config errors via `format_error()`, returns structured error messages
- **Tests** — new test cases in `tests/web/test_app.py` for happy path, cycle detection, and unsupported config types

### Out of Scope

- **Extending `Pipeline.plan()` for train/eda/infer** — ETL only in this phase; non-ETL configs return HTTP 200 with informative message "Plan preview available for ETL configs only" (not an error)
- **Estimated duration calculation** — `ExecutionPlan.estimated_duration` remains `None`; no historical run analysis
- **Plan caching** — every `/plan` call re-validates and re-computes
- **Phase 4 (metrics dashboard)** and **Phase 5 (SSE progress)** from PRD

## Capabilities

### New Capabilities

- **execution-plan-preview**: Dry-run execution plan via `Pipeline.plan()` showing steps and dependencies for ETL configs

### Modified Capabilities

- **web-console**: Add plan preview endpoint and UI integration (extension, no breaking changes)

## Approach

**Separate POST endpoint from `/jobs`** — `/plan` validates config (same security checks as `/jobs`) but returns plan instead of enqueuing. Allows operator to inspect DAG before committing to execution.

**Reuse existing patterns**:
- Config parsing and validation (YAML/JSON, schema via `validate_dict()`)
- Security check (`_check_custom_class_prefixes()`)
- HTMX content negotiation (check `HX-Request` header)

**ETL-only guard** — if config has no `etl:` section or config_type != `etl`, return HTTP 200 with `{"available": false, "message": "Plan preview available for ETL configs only"}`. HTMX response shows message inline in `#validation-output`.

**Error handling** — `ETLDependencyError` (cycle detection from `ETLOrchestrator`) caught and formatted via `format_error()`. Returns 400 with structured error showing cycle.

**Template** — `components/plan_preview.html` receives `plan: ExecutionPlan` and renders:
- Steps list (execution order)
- Dependencies dict (ETL name -> list of dependencies)

**Minimal UI** — inline list, no modal, no hierarchy visualization (MVP).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/web/app.py` | Modified | Add `POST /plan` endpoint, import `Pipeline`, `format_error` |
| `src/energizados/web/templates/components/editor.html` | Modified | Add "Preview Plan" button with HTMX attributes |
| `src/energizados/web/templates/components/plan_preview.html` | New | HTMX fragment for plan display |
| `tests/web/test_app.py` | Modified | Add test cases for `/plan` endpoint |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `Pipeline.plan()` raises on non-ETL configs | Low | Explicit check for `etl:` section before calling, return info message |
| Large ETL DAG causes slow response | Low | Plan computation is declarative (no data loading), only validates dependencies |
| HTMX fragment layout breaks validation zone | Low | Reuse `#validation-output` target, test with sample configs |

## Rollback Plan

Remove `POST /plan` endpoint, revert `editor.html` button addition, delete `plan_preview.html`. No framework core changes to revert (pure web layer).

## Dependencies

- None (uses existing stable APIs: `Pipeline.plan()`, `validate_dict()`, `format_error()`, `_check_custom_class_prefixes()`)

## Success Criteria

- [ ] Operators can click "Preview Plan" and see ETL execution order before submitting
- [ ] Circular dependency errors surface clearly via `format_error()`
- [ ] Non-ETL configs show informative "not available" message (not 400 error)
- [ ] HTMX response renders correctly inline in validation zone
- [ ] Tests cover happy path, cycle detection, and unsupported config types
