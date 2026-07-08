# Tasks: web-console-phase3 - POST /plan (ETL execution plan preview)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~150-200 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR (endpoint + template + tests + UI) |
| Delivery strategy | single-pr |
| Chain strategy | N/A (no chain needed) |
| Decision needed before apply | No |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: N/A
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | POST /plan endpoint (ETL plan preview) | PR 1 | Base: release/0.3.x; tests + docs included |

## Phase 1: Test Structure & POST /plan Happy Path

- [ ] 1.1 Create `TestPostPlan` class in `tests/web/test_app.py` following existing pattern (similar to `TestPostJobs`)
- [ ] 1.2 **TEST**: Write `test_post_plan_valid_etl_returns_json` — POST valid ETL config to `/plan`, assert 200, `response.json()` contains `steps` list and `dependencies` dict
- [ ] 1.3 **IMPLEMENT**: Add `POST /plan` endpoint in `src/energizados/web/app.py` with basic structure (parse YAML/JSON body, return 501 Not Implemented)
- [ ] 1.4 **IMPLEMENT**: Import `Pipeline` and `format_error` from `energizados.core.pipeline` and `energizados.api`
- [ ] 1.5 **IMPLEMENT**: Implement config parsing logic (YAML/JSON) and `validate_dict()` call in `/plan`
- [ ] 1.6 **IMPLEMENT**: Call `Pipeline.from_dict(config).plan()` and return JSON response with `steps` and `dependencies`
- [ ] 1.7 **GREEN**: Run `pytest tests/web/test_app.py::TestPostPlan::test_post_plan_valid_etl_returns_json` — assert test passes

## Phase 2: HTMX Content Negotiation

- [ ] 2.1 **TEST**: Write `test_post_plan_with_htmx_request_returns_html` — POST with `HX-Request: true` header, assert `response.text` contains HTML (not JSON)
- [ ] 2.2 **IMPLEMENT**: Add HTMX detection in `/plan` (`is_htmx = request.headers.get("HX-Request") == "true"`)
- [ ] 2.3 **IMPLEMENT**: Create `src/energizados/web/templates/components/plan_preview.html` with macro `plan_preview(plan, available, message, error)`
- [ ] 2.4 **IMPLEMENT**: Return `templates.TemplateResponse` with `plan_preview.html` when `is_htmx=True`, pass `plan` object
- [ ] 2.5 **GREEN**: Run `pytest tests/web/test_app.py::TestPostPlan::test_post_plan_with_htmx_request_returns_html` — assert HTML fragment returned

## Phase 3: Unsupported Config Type (No ETL Section)

- [ ] 3.1 **TEST**: Write `test_post_plan_train_config_returns_unavailable` — POST train config (no `etl:`), assert 200 with `{"available": false, "message": "..."}`
- [ ] 3.2 **IMPLEMENT**: Add check for `etl:` key in config dict before calling `Pipeline.plan()`
- [ ] 3.3 **IMPLEMENT**: Return HTTP 200 with `available: false` and message when no `etl:` section
- [ ] 3.4 **IMPLEMENT**: Update `plan_preview.html` macro to render unavailable message when `available=False`
- [ ] 3.5 **GREEN**: Run `pytest tests/web/test_app.py::TestPostPlan::test_post_plan_train_config_returns_unavailable` — assert 200 with unavailable message
- [ ] 3.6 **TEST**: Write `test_post_plan_eda_config_returns_unavailable` — POST EDA config, assert same unavailable behavior
- [ ] 3.7 **TEST**: Write `test_post_plan_infer_config_returns_unavailable` — POST inference config, assert same unavailable behavior

## Phase 4: Circular Dependency Error Handling

- [ ] 4.1 **TEST**: Write `test_post_plan_circular_dependency_returns_400` — POST ETL config with cycle (A→B→A), assert 400 with error containing cycle info
- [ ] 4.2 **TEST**: Write `test_post_plan_self_dependency_returns_400` — POST ETL with `depends_on: [self]`, assert 400
- [ ] 4.3 **IMPLEMENT**: Wrap `Pipeline.plan()` call in try/except for `ETLDependencyError`
- [ ] 4.4 **IMPLEMENT**: Catch `ETLDependencyError`, format via `format_error()`, return 400 with structured error
- [ ] 4.5 **IMPLEMENT**: Update `plan_preview.html` macro to render error message when `error` is present
- [ ] 4.6 **GREEN**: Run both cycle tests — assert 400 status and error message content

## Phase 5: Schema Validation Errors

- [ ] 5.1 **TEST**: Write `test_post_plan_invalid_schema_returns_400` — POST malformed YAML (missing required fields), assert 400 with validation error
- [ ] 5.2 **IMPLEMENT**: Ensure `validate_dict()` errors are caught and returned as 400 (reuse existing logic from `/jobs`)
- [ ] 5.3 **GREEN**: Run `pytest tests/web/test_app.py::TestPostPlan::test_post_plan_invalid_schema_returns_400` — assert validation error surfaced

## Phase 6: Custom Class Security Check

- [ ] 6.1 **TEST**: Write `test_post_plan_disallowed_custom_class_returns_400` — POST ETL with `custom_class: "evil.evil"`, assert 400 with prefix error
- [ ] 6.2 **IMPLEMENT**: Add `_check_custom_class_prefixes()` call after `validate_dict()` in `/plan`
- [ ] 6.3 **IMPLEMENT**: Return 400 with prefix error when disallowed prefix detected
- [ ] 6.4 **GREEN**: Run `pytest tests/web/test_app.py::TestPostPlan::test_post_plan_disallowed_custom_class_returns_400` — assert security check works

## Phase 7: UI Integration (Preview Plan Button)

- [ ] 7.1 **IMPLEMENT**: Add "Preview Plan" button in `src/energizados/web/templates/components/editor.html`
- [ ] 7.2 **IMPLEMENT**: Set button attributes: `hx-post="/plan"`, `hx-target="#validation-output"`, `hx-vals="js:getConfigType()"`
- [ ] 7.3 **IMPLEMENT**: Ensure button sends YAML content from editor textarea
- [ ] 7.4 **TEST**: Write manual integration test — load editor page, click Preview Plan, assert plan renders in `#validation-output` (can be manual test step)

## Phase 8: Edge Cases & Error Messages

- [ ] 8.1 **TEST**: Write `test_post_plan_empty_body_returns_400` — POST empty body, assert 400 error
- [ ] 8.2 **IMPLEMENT**: Handle empty body case in `/plan` (reuse logic from `/jobs`)
- [ ] 8.3 **TEST**: Write `test_post_plan_config_not_dict_returns_400` — POST non-dict config, assert 400
- [ ] 8.4 **GREEN**: Run all edge case tests — assert proper error handling

## Phase 9: Pre-commit & Verification

- [ ] 9.1 Run `pre-commit run --all-files` — fix any isort/black/bandit/flake8 issues in `app.py`, `templates/`, `tests/`
- [ ] 9.2 Run `pytest tests/web/test_app.py::TestPostPlan -v` — all 15+ tests should pass
- [ ] 9.3 Run full test suite `pytest tests/` — ensure no regressions in other tests
- [ ] 9.4 Verify `plan_preview.html` template macro renders correctly (check Jinja2 syntax)
- [ ] 9.5 Verify imports in `app.py` — `from energizados.core.pipeline import Pipeline`, `from energizados.api import format_error`

## Implementation Order

**TDD First**: Each phase follows strict red→green cycle. Tests are written FIRST (fail), then implementation makes them pass.

**Dependency Flow**:
1. Phase 1 establishes endpoint skeleton and happy path
2. Phase 2 adds HTMX content negotiation (no dependencies)
3. Phase 3 adds unsupported config guard (no dependencies)
4. Phase 4 adds cycle detection (depends on Phase 1 endpoint)
5. Phase 5-6 add validation/security (reuse existing patterns)
6. Phase 7 integrates UI (depends on Phase 2 HTMX)
7. Phase 8 handles edge cases (polish)
8. Phase 9 verifies quality gates

**Estimated Test Count**: ~15-18 test cases covering all spec scenarios

## Key Technical Notes

**Follow existing patterns** (verified via codebase exploration):
- HTMX detection: `is_htmx = request.headers.get("HX-Request") == "true"`
- Config parsing: `yaml.safe_load()` or `json.loads()` based on `content-type`
- Validation: `validate_dict(config, config_type)` from `energizados.api`
- Security: `_check_custom_class_prefixes(config)` (internal function in `app.py`)
- Error formatting: `format_error(exception)` from `energizados.api`
- Test fixtures: `client` (TestClient), `mock_store` (Mock JobStore)

**ExecutionPlan structure** (from `src/energizados/core/pipeline.py`):
```python
@dataclass
class ExecutionPlan:
    steps: List[str]          # Execution order
    dependencies: Dict[str, List[str]]  # ETL name -> dependencies
    estimated_duration: Optional[float] = None  # Always None in this phase
```

**Template macro signature** (to implement in `plan_preview.html`):
```jinja
{% macro plan_preview(plan, available, message, error) %}
  {# Renders plan steps, unavailable message, or error #}
{% endmacro %}
```
