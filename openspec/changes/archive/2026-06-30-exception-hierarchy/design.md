# Design: Exception Hierarchy & Boundary Error Preservation

> Change: `exception-hierarchy`. Implements the `error-handling` delta spec
> (capability greenfield). Approach 3A (minimal slice) per proposal.

## Technical Approach

Make the exception hierarchy a **public, typed, backward-compatible API** in one
additive slice: complete the per-layer type set via multiple inheritance, fix
`Pipeline.run`'s error-type erasure with an `isinstance(e, EnergizadosError)`
short-circuit, unify the fitted-state contract guards onto
`ModelNotFittedError`, and convert the one contract-layer `RuntimeError`. No
class moves, no pickle-format change, no behavioral loss for any existing
`except` clause.

## Architecture Decisions

### Decision: Exception class shape & MRO

**Choice** — `core/exceptions.py` final shape (one line of purpose each):

| Type | Bases | Purpose | Status |
|------|-------|---------|--------|
| `EnergizadosError` | `(Exception,)` | public base — `except EnergizadosError` catches all | unchanged |
| `PipelineError` | `(EnergizadosError,)` | pipeline-step execution failures (unexpected exceptions) | unchanged |
| `StepValidationError` | `(EnergizadosError,)` | step input/context validation | unchanged |
| `ConfigurationError` | `(EnergizadosError,)` | YAML config errors | unchanged |
| `ETLError` | `(EnergizadosError,)` | ETL extract/transform/load phase errors | unchanged |
| `ETLDependencyError` | `(EnergizadosError,)` | ETL DAG dependency/cycle errors | unchanged |
| `ModelNotFittedError` | `(EnergizadosError, ValueError)` | predict/transform on unfitted model/FE/selector | **MUTATED** |
| `TransformerError` | `(EnergizadosError, ValueError)` | feature-engineering transform failures | **NEW** |
| `FeatureSelectionError` | `(EnergizadosError, ValueError)` | feature-selection failures | **NEW** |
| `InferenceError` | `(EnergizadosError, RuntimeError)` | inference engine failures | **NEW** |
| `EvaluatorError` | `(EnergizadosError,)` | evaluation/reporting failures | **NEW (no site)** |

`ModelNotFittedError` keeps its existing `__init__(self, model_name=None)`.
Neither `EnergizadosError` nor `ValueError` defines a conflicting `__init__`,
so `super().__init__(message)` still resolves to `Exception.__init__`.

**MRO verified computable** (C3 linearization, no `TypeError`). Mutated type:

```
ModelNotFittedError.__mro__ = [
  ModelNotFittedError, EnergizadosError, ValueError,
  Exception, BaseException, object,
]
```

`TransformerError`/`FeatureSelectionError` share this shape;
`InferenceError` swaps `ValueError`→`RuntimeError`; `EvaluatorError` is linear.

**Alternatives considered** — single-base `EnergizadosError` only (breaks
`except ValueError` callers); runtime translation layer (rejected: invisible,
non-local, unpicklable).

**Rationale** — multiple inheritance is the only mechanism that preserves the
stdlib catch path *and* adds the framework catch path with zero runtime cost.
EvaluatorError has **no conversion site today** (no evaluator raises a bare
stdlib error), so it takes `(EnergizadosError,)` only — adding a stdlib base
without a conversion target would be a gratuitous API commitment. It exists for
symmetry/completeness and is the natural home for the next evaluator failure.

### Decision: Pipeline.run preservation mechanics

**Choice** — add an `isinstance` short-circuit inside the existing
`except Exception` block; `on_step_error` fires on **both** paths.

`core/pipeline.py` diff sketch (imports add `EnergizadosError`):

```python
except Exception as e:
    if self.on_step_error:                 # callback fires for BOTH paths
        self.on_step_error(step_name, e)
    if isinstance(e, EnergizadosError):    # framework error → re-raise AS-IS
        raise
    raise PipelineError(                   # unexpected → wrap, preserve cause
        f"Error executing step {step_name}: {e}", step=step_name
    ) from e
```

`StepValidationError` (raised at line 134, *outside* the try) and the
"No steps configured" `PipelineError` (line 116) are already unchanged — they
are unaffected. The bare `raise` re-raises the original object, preserving
type, attributes (`step`, `config_path`, `phase`, `model_name`), and traceback.

**Alternatives** — re-raise only a whitelist of subclasses (rejected: brittle,
every new type needs a code edit); drop `from e` on the wrap (rejected: loses
the cause chain spec REQ 2).

**Rationale** — `isinstance(e, EnergizadosError)` is the single, closed test
that matches the spec's "framework exceptions" definition. The whitelist lives
in the type hierarchy, not in `Pipeline.run`.

## Data Flow

```
step.execute(ctx)
      │ raises e
      ▼
 Pipeline.run except block
      │
      ├─ on_step_error(name, e)  ──► callback (BOTH paths)
      │
      ├─ isinstance(e, EnergizadosError)? ── YES ─► raise              [unchanged]
      │                                            │
      │                                            ▼
      │                                      caller sees e (e.g. ETLDependencyError)
      │
      └─ NO ─► raise PipelineError(...) from e
                                          │
                                          ▼
                        caller sees PipelineError(__cause__ = e)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/energizados/core/exceptions.py` | Modify | +`TransformerError`, `+FeatureSelectionError`, `+InferenceError`, `+EvaluatorError`; `ModelNotFittedError` → `(EnergizadosError, ValueError)` |
| `src/energizados/core/pipeline.py` | Modify | import `EnergizadosError`; `isinstance` short-circuit + bare `raise` |
| `src/energizados/feature_engineering/base.py` | Modify | 3 guards (`save`, `get_feature_names_out`, `check_fitted`) → `ModelNotFittedError` |
| `src/energizados/feature_selection/base.py` | Modify | 2 guards (`get_selected_features`, `get_audit_stats`) → `ModelNotFittedError` |
| `src/energizados/inference/hierarchical.py` | Modify | `RuntimeError` (line 164) → `InferenceError` |
| `tests/test_exceptions.py` | Create | hierarchy, MRO, backward-compat, `Pipeline.run` preservation, fitted guards, inference conversion |
| `AGENTS.md` | Modify | new "Exception Hierarchy (Public API)" section |
| `CHANGELOG.md` | Modify | entry under **Changed** + migration note |

## Interfaces / Contracts

Fitted-guard conversions (before → after). `ModelNotFittedError` import is
lazily added inside each guard (matches the existing `core/base.py` pattern).

`feature_engineering/base.py`:
```python
# BEFORE (×3, lines 114 / 150 / 170)
raise ValueError("You must call fit() ...")
# AFTER
from energizados.core.exceptions import ModelNotFittedError
raise ModelNotFittedError(model_name=self.__class__.__name__)
```
`feature_selection/base.py` (lines 97 / 114): same pattern,
`ModelNotFittedError(model_name=self.__class__.__name__)`.

`inference/hierarchical.py`:
```python
# BEFORE (line 164)
raise RuntimeError("Models not loaded. Call load_model() before predict_proba().")
# AFTER
from energizados.core.exceptions import InferenceError
raise InferenceError("Models not loaded. Call load_model() before predict_proba().")
```

**Scope confirmation**: subclass-local guards in `feature_selection/methods.py`
(8 sites), `feature_selection/pipeline.py` (4 sites), and
`templates/.../custom_selector.py.tpl` (1 site) re-implement the check inline
rather than calling the base method. They are **explicitly out of scope**
(spec "Non-goals" requirement) — converting them is the ~94-site follow-up.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | 4 new types exist & subclass `EnergizadosError` | `tests/test_exceptions.py::TestExceptionHierarchy` |
| Unit | `except ValueError` catches new `ValueError`-backed types; `except RuntimeError` catches `InferenceError`; `except EnergizadosError` catches all | `TestBackwardCompat` |
| Unit | `ModelNotFittedError.__mro__` contains both bases; import raises no `TypeError` | `TestMROComputability` |
| Unit | `Pipeline.run` re-raises `ETLDependencyError`/`ConfigurationError` unchanged (`isinstance(err, PipelineError)` is False) | `TestPipelinePreservation` (fake `PipelineStep` raising each) |
| Unit | `Pipeline.run` wraps `KeyError` → `PipelineError` with `__cause__ is original` | `TestPipelineWrapping` |
| Unit | `on_step_error` fires once for both framework & unexpected paths | `TestPipelineCallback` |
| Unit | unfitted `BaseFeatureEngineering`/`BaseFeatureSelector` raise `ModelNotFittedError` (catchable by `except ValueError`) | `TestFittedGuards` |
| Unit | `HierarchicalInference.predict_proba` before `load_model` raises `InferenceError` (catchable by `except RuntimeError`) | extend `tests/test_inference/test_hierarchical_inference.py` |

`TestPipelinePreservation`/`TestPipelineCallback` build a minimal
`PipelineStep` subclass (override `execute` to `raise`) — no YAML, no real steps.

## Migration / Rollout

**Behavioral change at the `Pipeline.run` boundary (additive in catch-coverage):**
a caller that did `except PipelineError` to catch an *inner*
`ConfigurationError`/`ETLDependencyError` will **no longer catch it** — the
inner type now propagates unchanged. Migration: switch to
`except EnergizadosError` (superset; still catches `PipelineError`).
`except PipelineError` for genuinely unexpected step errors still works.

CHANGELOG entry:

```markdown
### Changed
- `Pipeline.run` now re-raises `EnergizadosError` subclasses (e.g.
  `ConfigurationError`, `ETLDependencyError`) unchanged instead of wrapping
  them as `PipelineError`. Only unexpected (`Exception`) step errors are
  wrapped as `PipelineError` with the original preserved on `__cause__`.
  **Migration:** catch `except EnergizadosError` where you previously caught
  `except PipelineError` for inner framework errors.

### Added
- Public exception types `TransformerError`, `FeatureSelectionError`,
  `InferenceError`, `EvaluatorError`. `ModelNotFittedError` now also subclasses
  `ValueError` (additive — `except ValueError` still catches it).
```

No feature flags, no data migration, no persisted artifacts. Pure revert
unwinds the change.

## Changed-files Estimate & PR Shape

~7 touched files + 1 new test ≈ **180–220 changed lines** (well under the
400-line budget). Single PR, no chaining needed. Forecast:
`Decision needed before apply: No`, `Chained PRs recommended: No`,
`400-line budget risk: Low`.

## Open Questions

None. Q1/Q2/Q3 from the proposal are resolved: Q1 accept (additive, MRO
verified), Q2 include `EvaluatorError(EnergizadosError,)` (no site, no stdlib
base), Q3 AGENTS.md section.
