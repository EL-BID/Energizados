# Design: web-console-phase3

## Technical Approach

Add `POST /plan` endpoint that reuses the validation pattern from `POST /jobs` but returns an execution plan instead of enqueuing a job. The endpoint validates config schema, checks custom_class prefixes, and calls `Pipeline.plan()` to compute the ETL DAG execution order. HTMX content negotiation returns an inline HTML fragment for the web UI.

Follows existing web console patterns: same validation flow, same error handling, same HTMX header detection (`HX-Request`), same template macro structure.

## Architecture Decisions

### Decision: POST /plan Endpoint Signature

**Choice**: `POST /plan` with `config_type` query parameter, YAML/JSON body, same content-type negotiation as `/jobs`

**Alternatives considered**:
- `GET /plan?config=...` — would require URL-encoding YAML, impractical for large configs
- Separate `/plan/etl`, `/plan/train` endpoints — unnecessary complexity, config_type param already exists

**Rationale**: Mirrors `/jobs` exactly. Operators already pass `config_type` from the dropdown selector. Reusing the pattern reduces cognitive load and code duplication.

### Decision: ETL-Only Detection

**Choice**: Check for presence of `etl:` key in config dict (case-sensitive)

**Alternatives considered**:
- Use `config_type == "etl"` only — would fail for configs with mixed sections
- Validate against all schema types — would require computing plans for unsupported types

**Rationale**: `Pipeline.plan()` already checks for `etl:` section internally. Frontend sends `config_type` but we need to validate the actual config structure. If no `etl:` section exists, return HTTP 200 with `available: false`.

### Decision: Error Status Codes

**Choice**: 
- Schema validation errors: HTTP 400
- `ETLDependencyError` (cycles): HTTP 400
- Unsupported config type: HTTP 200 (not an error)

**Alternatives considered**:
- Return 404 for unsupported configs — 404 implies "endpoint not found", not "feature unavailable"
- Return 400 for unsupported configs — would confuse users, validation passed but feature doesn't apply

**Rationale**: 400 indicates "client sent bad data". Unsupported config type is a constraint of the feature, not a client error. The 200 with `available: false` allows frontend to show "not available" messaging without error styling.

### Decision: Error Handling Strategy

**Choice**: Catch `ETLDependencyError` explicitly, let `ConfigurationError` propagate (already handled by `validate_dict`), wrap unexpected exceptions

**Alternatives considered**:
- Catch all `EnergizadosError` — would hide unexpected errors behind generic handling
- Let all exceptions propagate — would return 500 instead of structured validation errors

**Rationale**: `ETLDependencyError` has specific semantic meaning (cycle in DAG). `validate_dict` already handles `ConfigurationError`. For anything else, `format_error()` provides structured output.

### Decision: Template Structure

**Choice**: Create `components/plan_preview.html` with macro `plan_preview(plan, available, message)`

**Alternatives considered**:
- Put plan HTML inline in `editor.html` — violates single responsibility, harder to test
- Create `plan_preview.html` as full page — HTMX replaces target div, full page would break layout

**Rationale**: Following the pattern from `components/validation.html`, macros make templates composable. HTMX targets `#validation-output`, so we need a fragment not a full page.

### Decision: Import Additions

**Choice**: Add `from energizados.api import format_error` and `from energizados.core.pipeline import Pipeline`

**Alternatives considered**:
- Import from deeper modules (`energizados.core.pipeline.Pipeline`) — less flexible for future refactors

**Rationale**: `energizados.api` is the public service layer. `format_error` is already exported there. `Pipeline` needs to be imported directly since it's not re-exported in `api/__init__.py`.

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         POST /plan                                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │ Parse YAML/JSON body    │
                    │ Check content-type      │
                    └─────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │ Validate config         │
                    │ - validate_dict()      │
                    │ - _check_custom_prefix │
                    └─────────────────────────┘
                                  │
                        ┌────────┴────────┐
                        │                 │
                        ▼                 ▼
              ┌──────────────┐    ┌──────────────────┐
              │ Has etl:?    │    │ Validation Error? │
              └──────────────┘    └──────────────────┘
                   │ No                    │ Yes
                   ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐
        │ Return 200       │    │ Return 400       │
        │ available: false │    │ validation errors│
        └──────────────────┘    └──────────────────┘
                   │ Yes
                   ▼
        ┌──────────────────────┐
        │ Build Pipeline      │
        │ Call pipeline.plan()│
        └──────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌──────────────┐    ┌──────────────────┐
│ Cycle Error? │    │ Return 200/HTML   │
│ (ETLDepError)│    │ with ExecutionPlan│
└──────────────┘    └──────────────────┘
        │
        ▼
┌──────────────────┐
│ Return 400       │
│ cycle error via  │
│ format_error()   │
└──────────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/energizados/web/app.py` | Modify | Add `POST /plan` endpoint, imports for `Pipeline` and `format_error` |
| `src/energizados/web/templates/components/editor.html` | Modify | Add "Preview Plan" button with `hx-post="/plan"`, `hx-target="#validation-output"` |
| `src/energizados/web/templates/components/plan_preview.html` | Create | HTMX fragment template with `plan_preview()` macro |
| `tests/web/test_app.py` | Modify | Add `TestPostPlan` class with tests for happy path, cycle detection, unsupported config, HTMX content negotiation |

## Interfaces / Contracts

### POST /plan Endpoint

```python
@app.post("/plan")
async def get_execution_plan(request: Request):
    """
    Return execution plan without running the pipeline.
    
    Expects YAML/JSON body and config_type query parameter.
    Validates config via validate_dict() and checks custom_class prefixes.
    
    Returns:
        - 200 with ExecutionPlan (JSON) or plan HTML fragment (HTMX)
        - 200 with {"available": false, "message": "..."} for non-ETL configs
        - 400 with validation errors (JSON) or error HTML fragment (HTMX)
        - 400 with cycle error (ETLDependencyError formatted via format_error)
    """
```

### ExecutionPlan Response Structure

```python
# JSON response
{
    "steps": ["etl_a", "etl_b", "etl_c"],
    "dependencies": {
        "etl_a": [],
        "etl_b": ["etl_a"],
        "etl_c": ["etl_a", "etl_b"]
    },
    "estimated_duration": null
}

# HTMX fragment
<!-- renders plan_preview.html macro with plan data -->
```

### Template Macro Signature

```jinja
{% macro plan_preview(plan, available, message, error) %}
  {% if error %}
    <!-- error rendering -->
  {% elif not available %}
    <!-- unavailable message -->
  {% else %}
    <!-- plan steps and dependencies -->
  {% endif %}
{% endmacro %}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_check_custom_class_prefixes()` | Existing coverage, no changes |
| Integration | `POST /plan` with valid ETL config | Assert 200, steps in order, dependencies correct |
| Integration | `POST /plan` with cycle config | Assert 400, error contains cycle information |
| Integration | `POST /plan` with train/eda/infer config | Assert 200, `available: false` |
| Integration | `POST /plan` with invalid schema | Assert 400, validation error message |
| Integration | HTMX content negotiation | Assert `HX-Request: true` returns HTML |
| Integration | Security check (disallowed custom_class) | Assert 400, prefix error message |

## Migration / Rollout

No migration required. Pure addition to web layer with no breaking changes. Feature is behind a new button — users who don't click it see no change.

**Rollback**: Remove `POST /plan` endpoint, delete `plan_preview.html`, revert `editor.html` button addition. No framework core changes to revert.

## Open Questions

None — all decisions specified in proposal are resolvable from existing codebase patterns.

## Implementation Estimate

**Line Changes**: ~150-200 lines
- `app.py`: ~70 lines (endpoint + imports)
- `plan_preview.html`: ~40 lines
- `editor.html`: ~10 lines (button)
- `tests/test_app.py`: ~60-80 lines

**Review Workload**: Low — well within 400-line budget. Single PR sufficient.

**Decision needed before apply**: No
**Chained PRs recommended**: No
**400-line budget risk**: Low
