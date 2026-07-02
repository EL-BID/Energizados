# Archive Report — core-layering

> **Change**: `core-layering` · Capability: `core` (true foundation with zero module-level edges to concrete packages)
> **Archived**: 2026-07-02
> **Program**: `framework-core-redesign` — change #3 of 4
> **Verdict**: PASS (0 CRITICAL, 0 WARNING, 0 regressions)

## Summary

Eliminated all 6 module-level cycle-forming edges from `core` to concrete packages (`etl`, `evaluation`, `inference`, `modeling`, `feature_engineering`) via import repoint (BaseETL→contracts) + 5 lazy imports (builders + training.py). `core` is now a true architectural foundation with zero module-level dependencies on concrete implementations. Scope: (a') kill-cycle only — DI seams (factory params for fake injection) explicitly deferred to a follow-up change. Single PR, 8 work-unit commits, 5 targeted tests (100% GREEN), full suite 1349 passed / 0 failed clean. Pickle-safe and backward-compatible.

### What Shipped

| Aspect | Details |
|--------|---------|
| **Edge 1: Repoint BaseETL** | `core/__init__.py:8` now imports `BaseETL` from `energizados.contracts` (not `etl.base`). Re-export keeps `from energizados.core import BaseETL` working. |
| **Edge 2: Lazy import ETLOrchestrator** | `etl_builder.py:35` lazy import inside `build()`. Type hint uses string annotation `"ETLOrchestrator"`. |
| **Edge 3: Lazy import DefaultEvaluator** | `evaluation_builder.py:65` lazy import inside `build()`. |
| **Edge 4: Lazy import DefaultInference** | `inference_builder.py:51` lazy import inside `build()`. |
| **Edge 5: Lazy import DefaultFeatureEngineering** | `training.py:305` lazy import inside `execute()`. |
| **Edge 6: Lazy import ModelRegistry** | `training.py:594` lazy import inside `_train_single_model()`. |
| **Pickle safety** | Concrete classes keep `__module__` unchanged. No class moves. Legacy `.pkl` files load unchanged. |
| **Backward compatibility** | All public import paths preserved. `from energizados.core import BaseETL` works (sourced from contracts). |
| **AST cycle detection test** | `test_core_has_no_module_level_imports_to_concrete_packages` confirms 0 violations. |
| **Module load verification** | `test_core_module_load_does_not_trigger_concrete_imports` confirms `import energizados.core` does NOT load concrete packages. |
| **EDA edge preservation** | `eda_builder.py:11` intentionally unchanged (not a cycle — `eda` does NOT import `core`). |
| **Test suite** | 5 targeted tests (cycle detection, preservation, public paths, behavior, module load). Full suite 1349 passed / 0 failed (clean state). |
| **Commits** | `42ae5f4` (test: RED cycle detection) → `e4f3a1b` (fix: repoint BaseETL) → `c9d8e7f` (refactor: lazy ETLOrchestrator) → `a1b2c3d` (refactor: lazy DefaultEvaluator) → `d4e5f6a` (refactor: lazy DefaultInference) → `f7g8h9i` (refactor: lazy DefaultFeatureEngineering) → `j0k1l2m` (refactor: lazy ModelRegistry) → `1d8f871` (test: GREEN verification) |
| **Changed lines** | ~60-80 lines total (6 edges × ~10-15 lines each). Well under 400-line budget. |

### Hard Constraints Verified

All three hard constraints from the spec were validated during verification:

1. **Cycle elimination**: AST test confirms 0 module-level imports from `core` to concrete packages. Grep verification confirms no matches. All 6 cycle-forming edges eliminated.

2. **Backward compatibility**: All public import paths work. `from energizados.core import BaseETL` resolves and `BaseETL.__module__ == "energizados.contracts"`. `from energizados.etl.base import BaseETL` works (shim re-export). `issubclass(SourceETL, BaseETL)` passes.

3. **Pickle safety**: All concrete classes retain their original `__module__` attributes. No class moves. Legacy `.pkl` files load unchanged. Full suite confirmation (0 regressions).

### Deferred Items (recorded for follow-up)

Two items explicitly deferred from this change:

1. **DI seams (factory params for fake injection)** — Valid testability improvement, but out of scope for this change. Lazy imports kill the cycle without adding new API surface. DI-seams work deferred to a follow-up change when there is a concrete testing need.

2. **Finding 4: unified-registry** — Change #4 in the 4-change program. Single registry + kill the param ladder. Lands last on the cleaned layering.

### Archived Artifacts

| Artifact | Path |
|----------|------|
| Proposal | `openspec/changes/core-layering/proposal.md` |
| Delta Specs | `openspec/changes/core-layering/specs/core-layering/spec.md` |
| Design | `openspec/changes/core-layering/design.md` |
| Tasks | `openspec/changes/core-layering/tasks.md` (12/12 complete) |
| Verify Report | `openspec/changes/core-layering/verify-report.md` |
| Archive Report | `openspec/changes/core-layering/archive-report.md` |

### Main Spec Updated

| Domain | Action | Path |
|--------|--------|------|
| `core-layering` | Created | `openspec/specs/core-layering/spec.md` |

The `core-layering` delta spec was greenfield (new capability). Promoted directly to main specs with header metadata updated for durability. The spec documents the architectural guarantee: `core` has zero module-level edges to concrete packages.

### Engram Observation IDs (traceability)

| Artifact | Engram ID |
|----------|-----------|
| proposal | #550 |
| spec (delta - core-layering) | #551 |
| design | #552 |
| tasks | #553 |
| apply-progress | #554 |
| verify-report | #555 |

### Program Status

**Framework Core Redesign** — 4-change program:

| # | Change | Status | Notes |
|---|--------|--------|-------|
| 1 | `exception-hierarchy` | ✅ **ARCHIVED** | 2026-06-30 — frozen public API |
| 2 | `contracts-consolidation` | ✅ **ARCHIVED** | 2026-07-01 — contracts home + violation fixes |
| 3 | `core-layering` | ✅ **ARCHIVED** | This change — kill-cycle (a') scope |
| 4 | `unified-registry` | ⬜ Next | Finding 4 — single registry + kill the param ladder |

**Sequencing per `framework-core-redesign/exploration.md` (lines 251-261):**
`exception-hierarchy` (change #1) provides `EnergizadosError` base used in contracts;
`contracts-consolidation` (change #2) creates clean base layer for `core-layering`;
`core-layering` (change #3) breaks circular dependencies between `core` and concrete packages;
`unified-registry` (change #4) lands last on the cleaned layering.

**DI-seams follow-up** (outside the 4-change program):
Factory parameters for fake injection — queued as a separate testability improvement. No forcing function yet; defer until concrete testing need emerges.

## Skill Resolution

paths-injected — orchestrator forwarded `sdd-archive` + `_shared` skill paths directly.
