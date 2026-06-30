# Tasks: Exception Hierarchy & Boundary Error Preservation

> Change: `exception-hierarchy`. Implements `error-handling` delta spec. Approach 3A (minimal slice).
> Strict TDD is ON (`pytest tests/`). Every implementation task is paired with its failing test (RED → GREEN). All 13 spec scenarios map to a task; all 8 design files are touched.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~200 (180–220) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR (5 work-unit commits) |
| Delivery strategy | ask-always |
| Chain strategy | pending (single PR, under budget) |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

> Review-budget decision resolves to "No" — fits one PR under 400 lines. `ask-always` still has the orchestrator confirm before apply; no chained-PR / size-exception decision is required.

### Suggested Work Units

| Unit | Goal | Work-unit commit | Notes |
|------|------|------------------|-------|
| WU1 | Exception types + hierarchy tests | `feat(core): add public exception types` | tests + code together |
| WU2 | Pipeline.run preservation | `fix(core): preserve framework exceptions in Pipeline.run` | tests + code together |
| WU3 | Fitted-state guards | `refactor(feature): unify fitted guards on ModelNotFittedError` | tests + code together |
| WU4 | Inference conversion | `refactor(inference): raise InferenceError when models not loaded` | extends existing test |
| WU5 | Docs + scope audit | `docs: document exception hierarchy public API` | AGENTS.md + CHANGELOG |

## Phase 1: Exception Types (WU1)

- [x] 1.1 RED — Create `tests/test_exceptions.py` with `TestExceptionHierarchy`, `TestBackwardCompat`, `TestMROComputability`, `TestExistingTypesUnchanged`. **Files:** `tests/test_exceptions.py`. **Scenarios:** REQ1 (all 4). **Acceptance:** `pytest tests/test_exceptions.py` fails — new types absent, `ModelNotFittedError` not yet `ValueError`-backed. ~41 lines.
- [x] 1.2 GREEN — In `src/energizados/core/exceptions.py` add `TransformerError(EnergizadosError, ValueError)`, `FeatureSelectionError(EnergizadosError, ValueError)`, `InferenceError(EnergizadosError, RuntimeError)`, `EvaluatorError(EnergizadosError,)`; mutate `ModelNotFittedError` → `(EnergizadosError, ValueError)` keeping `__init__(model_name)`. **Files:** `core/exceptions.py`. **Scenarios:** REQ1. **Acceptance:** 1.1 passes; import raises no `TypeError`; `__mro__` contains both bases; existing types unchanged. ~17 lines.

## Phase 2: Pipeline.run Preservation (WU2)

- [x] 2.1 RED — Add `TestPipelinePreservation`, `TestPipelineWrapping`, `TestPipelineCallback` to `tests/test_exceptions.py` via a minimal `PipelineStep` subclass whose `execute` raises. **Files:** `tests/test_exceptions.py`. **Scenarios:** REQ2 (all 3). **Acceptance:** tests fail — `ETLDependencyError` gets wrapped (`isinstance(err, PipelineError)` True); callback/wrapping assertions fail. ~57 lines.
- [x] 2.2 GREEN — In `src/energizados/core/pipeline.py`: import `EnergizadosError`; in the `except Exception` block (lines 155–159), after `on_step_error`, insert `if isinstance(e, EnergizadosError): raise` before `raise PipelineError(...) from e`. **Files:** `core/pipeline.py`. **Scenarios:** REQ2. **Acceptance:** 2.1 passes; framework errors re-raised unchanged (type/attributes/traceback preserved); `KeyError` wrapped with `__cause__` set; callback fires on both paths. ~3 lines.

## Phase 3: Fitted-state Guards (WU3)

- [x] 3.1 RED — Add `TestFittedGuards` to `tests/test_exceptions.py`: unfitted `BaseFeatureEngineering` subclass raises `ModelNotFittedError` on `transform`/`get_feature_names_out`/`save`; unfitted `BaseFeatureSelector` raises on `get_selected_features`/`get_audit_stats`; both catchable by `except ValueError`. **Files:** `tests/test_exceptions.py`. **Scenarios:** REQ3 (all 3). **Acceptance:** tests fail — sites raise plain `ValueError`, not `ModelNotFittedError`. ~35 lines.
- [x] 3.2 GREEN — Convert guards: `feature_engineering/base.py` (lines 114/150/170) and `feature_selection/base.py` (lines 97/114) → `ModelNotFittedError(model_name=self.__class__.__name__)` (lazy import, matching `core/base.py`). **Files:** `feature_engineering/base.py`, `feature_selection/base.py`. **Scenarios:** REQ3. **Acceptance:** 3.1 passes; `BaseModel.check_fitted` left unchanged as the reference. ~10 lines.

## Phase 4: Inference Conversion (WU4)

- [x] 4.1 RED — Extend `tests/test_inference/test_hierarchical_inference.py`: assert `predict_proba` before `load_model` raises `InferenceError` AND is catchable by `except RuntimeError`; keep the existing `pytest.raises(RuntimeError)` test (line 249) as the backward-compat guard. **Files:** `tests/test_inference/test_hierarchical_inference.py`. **Scenarios:** REQ4. **Acceptance:** new `InferenceError` assertion fails (path raises `RuntimeError`). ~6 lines.
- [x] 4.2 GREEN — In `src/energizados/inference/hierarchical.py` line 164: `RuntimeError(...)` → `InferenceError(...)` (lazy import). **Files:** `inference/hierarchical.py`. **Scenarios:** REQ4. **Acceptance:** 4.1 passes; `except RuntimeError` still catches it. ~2 lines.

## Phase 5: Documentation & Scope Audit (WU5)

- [x] 5.1 — Add "Exception Hierarchy (Public API)" section to `AGENTS.md`: enumerate `EnergizadosError` + all 11 subclasses with bases and a stability commitment (future changes require deprecation paths). **Files:** `AGENTS.md`. **Scenarios:** REQ5. **Acceptance:** section lists every type from the design table. ~25 lines.
- [x] 5.2 — Add CHANGELOG entry under **Changed** (`Pipeline.run` preservation + migration: switch `except PipelineError` → `except EnergizadosError` for inner framework errors) and **Added** (4 new types + `ModelNotFittedError` `ValueError` base). **Files:** `CHANGELOG.md`. **Scenarios:** REQ2 migration, REQ1. **Acceptance:** matches design's CHANGELOG text. ~12 lines.
- [x] 5.3 — Scope audit (Non-goals, read-only): confirm bare `ValueError`/`RuntimeError` sites outside the 6 converted guards are untouched — `feature_selection/methods.py` (8), `feature_selection/pipeline.py` (4), `templates/.../custom_selector.py.tpl` (1), and the remaining ~84 sites. **Files:** none. **Scenarios:** REQ6. **Acceptance:** `rg "raise (ValueError|RuntimeError)"` diff shows only the 6 converted sites changed. 0 lines.

## Implementation Order

WU1 → WU2 → WU3 → WU4 → WU5. WU1 first (defines the types every later phase imports). WU2 next (boundary contract; independent of guards). WU3/WU4 convert call sites that depend on WU1's types. WU5 last (documents the now-frozen public API and audits scope). Each WU is a self-contained commit with its tests, so review stays focused within the single PR.
