# Proposal: Exception Hierarchy & Boundary Error Preservation

## Intent

The framework's exception hierarchy is incoherent and `Pipeline.run` performs **error-type erasure** at the boundary: every step exception is re-wrapped as `PipelineError` (`core/pipeline.py:155-159`), so callers cannot `except ConfigurationError` / `except ETLDependencyError`. The same concept ("not fitted") raises different types — `BaseModel.check_fitted` → `ModelNotFittedError`, but `BaseFeatureEngineering.check_fitted` and `BaseFeatureSelector.get_selected_features` → bare `ValueError`. There is no `TransformerError`, `FeatureSelectionError`, `InferenceError`, or `EvaluatorError`. The hierarchy is unusable as a public API.

## Scope

### In Scope
- Extend `core/exceptions.py`: add `TransformerError`, `FeatureSelectionError`, `InferenceError`, `EvaluatorError`.
- Fix `Pipeline.run` erasure: re-raise `EnergizadosError` subclasses **unchanged**; wrap only unexpected `Exception` as `PipelineError` (`from e`).
- Unify fitted-state guards → `ModelNotFittedError`: `BaseFeatureEngineering.{check_fitted,save,get_feature_names_out}`, `BaseFeatureSelector.{get_selected_features,get_audit_stats}`.
- Convert contract-layer `RuntimeError` (`inference/hierarchical.py:164`) → `InferenceError`.
- **Backward-compat (hard constraint)**: each NEW/CONVERTED exception inherits `EnergizadosError` AND the stdlib type it replaces — `TransformerError(EnergizadosError, ValueError)`, `InferenceError(EnergizadosError, RuntimeError)`.
- Document the hierarchy as **public API** (AGENTS.md section).

### Out of Scope
- The ~94 OTHER bare `ValueError`/`RuntimeError` sites → deferred to a follow-up change.
- Findings 1/2/4 (layering, contracts, registry); the `_anterior` domain leak.

## Capabilities

### New Capabilities
- `error-handling`: typed exception hierarchy + boundary error-preservation contract.

### Modified Capabilities
- None (greenfield — `openspec/specs/` has no existing specs).

## Approach

Exploration approach **3A** (minimal slice). Multiple-inheritance buys backward compatibility: `except ValueError` still catches a `TransformerError`; `except EnergizadosError` still catches everything. `Pipeline.run` gains an `isinstance(e, EnergizadosError)` short-circuit before the wrap. No class moves → pickle-safe (exceptions aren't pickled; concrete model classes untouched).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/core/exceptions.py` | Modified | +4 types; `ModelNotFittedError` gains `ValueError` base (see Open Q1) |
| `src/energizados/core/pipeline.py` | Modified | `run()` preserves `EnergizadosError` subclasses |
| `src/energizados/feature_engineering/base.py` | Modified | fitted guards → `ModelNotFittedError` |
| `src/energizados/feature_selection/base.py` | Modified | fitted guards → `ModelNotFittedError` |
| `src/energizados/inference/hierarchical.py` | Modified | `RuntimeError:164` → `InferenceError` |
| `tests/test_exceptions.py` | New | per-type + erasure-preservation + backward-compat tests |
| `AGENTS.md` | Modified | public exception-hierarchy docs |

**Impact on existing experiments/models**: none. No class moves, no pickle format change. Existing `except ValueError` / `except EnergizadosError` callers keep working.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Multiple-inheritance MRO incorrect | Low | Python linearization is deterministic; add MRO assertion test |
| Public-API commitment → future changes need deprecation paths | Med | Document stability; record in CHANGELOG as a commitment |
| Mutating existing `ModelNotFittedError` to add `ValueError` base | Med | Additive (callers gain a catch path, none lost); gated by Q1 |

## Rollback Plan

Pure revert of the diff. No persisted artifacts produced by the framework change. If a downstream caller depended on the OLD erasure behavior (catching `PipelineError` for an inner `ConfigurationError`), they restore by catching `EnergizadosError` — documented in the AGENTS.md migration note.

## Dependencies

- None. This is change #1 of the 4-change program; explicitly independent (per exploration sequencing).

## Success Criteria

- [ ] `Pipeline.run` re-raises `EnergizadosError` subclasses unchanged (test asserts type preserved).
- [ ] All 4 new types exist and subclass `EnergizadosError`.
- [ ] `except ValueError` catches a `TransformerError`; `except RuntimeError` catches an `InferenceError`.
- [ ] Fitted-guard sites raise `ModelNotFittedError`.
- [ ] `pytest tests/` green; diff ≤ ~250 lines (under 400-line budget).
- [ ] Hierarchy documented in AGENTS.md.

## Open Questions

1. **`ModelNotFittedError` base mutation**: the converted fitted-guards currently raise `ValueError`; to honor the backward-compat constraint, `ModelNotFittedError` must gain `ValueError` as a second base. This mutates an existing public class (currently `ModelNotFittedError(EnergizadosError)` only). Confirm we accept `ModelNotFittedError(EnergizadosError, ValueError)` — additive and safe, but it is a change to an existing type. *(Default: accept, since it's strictly additive.)*
2. **`EvaluatorError` now or later**: no evaluator site currently raises a bare stdlib error, so it has no conversion target today. Include it speculatively for symmetry, or defer until a site needs it? *(Default: include — cheap and completes the per-layer set.)*
3. **Doc home**: AGENTS.md section vs. a dedicated `docs/exceptions.md`. *(Default: AGENTS.md section, matching existing convention.)*
