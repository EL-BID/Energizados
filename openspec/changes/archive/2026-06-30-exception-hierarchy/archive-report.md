# Archive Report — exception-hierarchy

> **Change**: `exception-hierarchy` · Capability: `error-handling` (greenfield)
> **Archived**: 2026-06-30
> **Program**: `framework-core-redesign` — change #1 of 4
> **Verdict**: PASS (0 CRITICAL, 0 WARNING, 3 suggestions)

## Summary

Implemented a coherent, public, backward-compatible exception hierarchy with
boundary error-preservation in `Pipeline.run`. 6 work-unit commits across
11 files, 399 insertions / 11 deletions.

### What Shipped

| Aspect | Details |
|--------|---------|
| **Exception types** | +`TransformerError(EnergizadosError, ValueError)`, `+FeatureSelectionError(EnergizadosError, ValueError)`, `+InferenceError(EnergizadosError, RuntimeError)`, `+EvaluatorError(EnergizadosError,)`; `ModelNotFittedError` mutated to `(EnergizadosError, ValueError)` |
| **Pipeline.run preservation** | `isinstance(e, EnergizadosError)` short-circuit → bare `raise` before `PipelineError(...) from e` wrap |
| **Fitted guards unified** | 5 sites converted (3 FE + 2 selector) → `ModelNotFittedError` with lazy import |
| **Inference conversion** | `RuntimeError` → `InferenceError` in `hierarchical.py:163` |
| **Docs** | Public API section in AGENTS.md + CHANGELOG entry with migration guide |
| **Test suite** | 87 targeted tests, 1221/1243 full-suite passing (17+1 pre-existing failures proven unrelated) |
| **Commits** | `a1c5cab` (feat: types) → `e74b85e` (fix: Pipeline.run) → `54f12fe` (refactor: guards) → `0be56e9` (refactor: inference) → `e24deee` (docs: API) → `168458b` (test: MI selector) |
| **Changed lines** | 399 ins / 11 del (11 files) — 10 lines over the soft 400 budget, all in mandatory TDD tests |

### Public-API Commitments Made

The exception hierarchy is **frozen public API**. The AGENTS.md section and this
archive document the commitment:

- All 11 exception types (`EnergizadosError` + 10 subclasses) are stable.
- Future changes (renames, base-class changes, removals) require a deprecation
  path — never a silent break.
- Adding new subclasses of `EnergizadosError` is allowed and non-breaking.
- `except EnergizadosError` catches all framework errors.
- `except ValueError` catches `ModelNotFittedError`, `TransformerError`,
  `FeatureSelectionError`; `except RuntimeError` catches `InferenceError`.

### Deferred Suggestions (recorded for follow-up)

Three non-blocking suggestions from verify-report that remain unaddressed:

1. **Guard docstrings now imprecise** — `save`/`get_feature_names_out`/
   `check_fitted` (FE) and `get_selected_features`/`get_audit_stats` (selector)
   docstrings still say `Raises: ValueError`. These remain *literally accurate*
   (`ModelNotFittedError` subclasses `ValueError`) but are less precise.
   Consider updating to `ModelNotFittedError` for documentation fidelity.

2. **Size forecast drift** — Actual PR = 410 lines vs ~200 forecast (309/410
   are mandatory TDD tests). Code surface itself (~66 src lines) was within
   estimate. Informational for future task sizing.

3. **Design-doc scope note** — `MutualInformationSelector` inherits
   `get_selected_features` from `BaseFeatureSelector` (design assumed
   re-implementation). This was handled correctly per spec but the design
   assumption should be corrected if reused as a template.

### Archived Artifacts

| Artifact | Path |
|----------|------|
| Proposal | `openspec/changes/archive/2026-06-30-exception-hierarchy/proposal.md` |
| Delta Spec | `openspec/changes/archive/2026-06-30-exception-hierarchy/specs/error-handling/spec.md` |
| Design | `openspec/changes/archive/2026-06-30-exception-hierarchy/design.md` |
| Tasks | `openspec/changes/archive/2026-06-30-exception-hierarchy/tasks.md` (11/11 complete) |
| Verify Report | `openspec/changes/archive/2026-06-30-exception-hierarchy/verify-report.md` |
| Archive Report | `openspec/changes/archive/2026-06-30-exception-hierarchy/archive-report.md` |

### Main Spec Updated

| Domain | Action | Path |
|--------|--------|------|
| `error-handling` | Created | `openspec/specs/error-handling/spec.md` |

The delta spec was a greenfield full spec. Promoted directly to main specs
with header metadata updated for durability (removed change-specific
references, added stability commitment).

### Engram Observation IDs (traceability)

| Artifact | Engram ID |
|----------|-----------|
| proposal | #527 |
| spec (delta) | #528 |
| design | #529 |
| tasks | #530 |
| apply-progress | #531 |
| verify-report | #532 |

### Program Status

**Framework Core Redesign** — 4-change program:

| # | Change | Status | Notes |
|---|--------|--------|-------|
| 1 | `exception-hierarchy` | ✅ **ARCHIVED** | This change |
| 2 | `contracts-consolidation` | ⬜ Next | Finding 2 — contracts home + violation fixes |
| 3 | `core-layering` | ⬜ Pending | Finding 1 — break `core↔etl` cycle via DI seams |
| 4 | `unified-registry` | ⬜ Pending | Finding 4 — single registry + kill the param ladder |

Sequencing per `framework-core-redesign/exploration.md` (lines 251-261):
`contracts-consolidation` benefits from having the exception hierarchy
available; `core-layering` benefits from contracts; `unified-registry`
lands last on the cleaned layering.

## Skill Resolution
paths-injected — orchestrator forwarded `sdd-archive` + `_shared` skill paths directly.
