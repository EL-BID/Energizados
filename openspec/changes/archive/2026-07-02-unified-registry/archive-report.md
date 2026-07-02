# Archive Report — unified-registry

> **Change**: `unified-registry` · Capability: `model-registry` (centralized registry with from_config pattern)
> **Archived**: 2026-07-02
> **Program**: `framework-core-redesign` — change #4 of 4 — FINAL
> **Verdict**: PASS (0 CRITICAL, 0 WARNING, 2 SUGGESTION)

## Summary

Eliminated the dual-edit requirement when adding model types by killing the `_prepare_model_params` ladder via per-adapter `from_config` classmethods, fixed the `_build_meta_learner` bug that broke non-sklearn meta-learners in stacking ensembles, and extracted a unified `Registry` abstraction to `core/registry.py` with per-domain instances (`model_registry`, `transformer_registry`, `selector_registry`). `ModelRegistry` became a backward-compatible silent alias. Scope: Approach 4B (PR1: ladder kill + meta-learner fix, PR2: Registry abstraction; PR3 transformer/selector migration explicitly deferred). Two chained PRs, 7 behavior-preservation tests (100% GREEN), 12 Registry tests (100% GREEN), full suite 1364 passed / 0 failed clean. Pickle-safe and backward-compatible.

### What Shipped

| Aspect | Details |
|--------|---------|
| **Ladder elimination** | `_prepare_model_params` method (lines 802-869) DELETED from `core/steps/training.py`. Replaced with `model_class.from_config(cfg, X_train)` at line 597. |
| **from_config classmethods** | Added to all 7 adapters: LGBMModelAdapter (line 97), CATModelAdapter (278), XGBModelAdapter (455), NNModelAdapter (619), LSTMNNModelAdapter (786), SimpleTrendAdapter (951), SimpleConstantAdapter (1072). Each converts YAML config + X_train into constructor kwargs. |
| **Meta-learner fix** | `_build_meta_learner` (modeling/ensemble.py:199-219) wraps registry-sourced adapters with `_SklearnCalibWrapper` for 2D `predict_proba`. Direct LogisticRegression path unchanged (zero overhead). |
| **Registry abstraction** | `Registry` class created at `core/registry.py` (108 lines). Instance methods: `register`, `get`, `is_registered`, `list_registered`. Case-insensitive storage via `name.lower()`, KeyError with available names. |
| **Per-domain instances** | `model_registry = Registry("models")`, `transformer_registry = Registry("transformers")`, `selector_registry = Registry("selectors")` (lines 102-107). |
| **ModelRegistry alias** | Converted to silent alias at `modeling/registry.py` (60 lines). All methods delegate to `model_registry`. No deprecation warning (public extension point preserved). |
| **Pickle safety** | All concrete adapter classes retain original `__module__` (`energizados.modeling.adapters`). No class moves. Legacy `.pkl` files load unchanged. |
| **Backward compatibility** | `from energizados.modeling.registry import ModelRegistry` resolves. `ModelRegistry.register/get/list_models/create` work. `custom_class` escape hatch unchanged. |
| **Behavior preservation** | 9 equivalence tests verify `from_config` produces identical kwargs to old ladder for all 7 adapters. |
| **Test suite** | 21 targeted tests (9 behavior preservation + 12 Registry). Full suite 1364 passed / 0 failed (clean state). |
| **Commits** | PR1: `64ae323` (from_config + ladder kill + meta-learner fix) → PR2: `41cbf44` (Registry abstraction + ModelRegistry alias) + `a320b4f` (docs). |
| **Changed lines** | PR1: ~300-350 lines (7 adapters + training + ensemble + tests). PR2: ~150-200 lines (Registry + alias migration). Total: ~450-550 lines. |

### Hard Constraints Verified

All three hard constraints from the spec were validated during verification:

1. **Pickle safety**: All concrete adapter classes remain in `energizados.modeling.adapters`. No `__module__` changes detected. Legacy `.pkl` files load unchanged.

2. **No module-level cycle**: Lazy import of `_SklearnCalibWrapper` from `core/steps/training.py` into `modeling/ensemble.py` at line 217 (inside `_build_meta_learner` method). Function-level import does NOT create module-level cycle.

3. **Backward compatibility**: `ModelRegistry` silent alias works perfectly. All public import paths resolve. `custom_class` escape hatch verified.

### Deferred Items (recorded for follow-up)

Two items explicitly deferred from this change:

1. **PR3: Transformer/selector registry migration** — Migrating `transformer_map` and `_get_default_method_map` into unified registries. Valid extensibility improvement, but out of scope for Approach 4B. Current `custom_class` escape hatch already enables extension. Deferred to follow-up change.

2. **ENSEMBLE_SCHEMA meta_learner.type enum expansion** — Config schema enum (`logistic_regression`, `random_forest`, `gradient_boosting`) doesn't include Energizados model types like `lightgbm` or `catboost`. Verified PRE-EXISTING on release/0.2.x (NOT introduced by this change). Downgraded to INFO/follow-up in Judgment Day. Separate config-validation change.

### Archived Artifacts

| Artifact | Path |
|----------|------|
| Exploration | `openspec/changes/framework-core-redesign/unified-registry-exploration.md` |
| Proposal | `openspec/changes/framework-core-redesign/unified-registry/proposal.md` |
| Delta Specs | `openspec/changes/framework-core-redesign/unified-registry/specs/model-registry/spec.md` |
| Design | `openspec/changes/framework-core-redesign/unified-registry/design.md` |
| Tasks | `openspec/changes/framework-core-redesign/unified-registry/tasks.md` (12/14 complete; PR2 phases 1-3 unchecked but verified complete) |
| Verify Report | `openspec/changes/framework-core-redesign/unified-registry/verify-report.md` |
| Archive Report | `openspec/changes/framework-core-redesign/unified-registry/archive-report.md` |

### Main Spec Updated

| Domain | Action | Path |
|--------|--------|------|
| `model-registry` | Modified | `openspec/specs/model-registry/spec.md` |

The `model-registry` delta spec modified an existing capability (Approach 4B). Promoted to main specs with all requirements preserved (from_config classmethod pattern, ladder replacement, meta-learner fix, unified Registry abstraction, backward-compatible alias, pickle safety). The spec documents the architectural guarantee: single registry abstraction + per-adapter config logic.

### Engram Observation IDs (traceability)

| Artifact | Engram ID |
|----------|-----------|
| explore | #560 |
| proposal | #561 |
| spec (delta - model-registry) | #562 |
| design | #563 |
| tasks | #564 |
| apply-progress | N/A (tracked in tasks observation) |
| verify-report | #567 |
| judgment-day | #566 |
| prs | #568 |

### Program Status

**Framework Core Redesign** — 4-change program: **✅ COMPLETE**

| # | Change | Status | Notes |
|---|--------|--------|-------|
| 1 | `exception-hierarchy` | ✅ **ARCHIVED** | 2026-06-30 — frozen public API |
| 2 | `contracts-consolidation` | ✅ **ARCHIVED** | 2026-07-01 — contracts home + violation fixes |
| 3 | `core-layering` | ✅ **ARCHIVED** | 2026-07-02 — kill-cycle (a') scope |
| 4 | `unified-registry` | ✅ **ARCHIVED** | This change — single registry + kill the param ladder |

**Sequencing per `framework-core-redesign/exploration.md` (lines 251-261):**
`exception-hierarchy` (change #1) provides `EnergizadosError` base used in contracts;
`contracts-consolidation` (change #2) creates clean base layer for `core-layering`;
`core-layering` (change #3) breaks circular dependencies between `core` and concrete packages;
`unified-registry` (change #4) lands last on the cleaned layering.

**Program completion confirmed:** All 4 changes archived. Framework-core-redesign program COMPLETE. The framework now has:
- Frozen public API exception hierarchy
- Contracts as single home for base classes
- Core layer with zero module-level edges to concrete packages
- Unified registry abstraction with per-adapter config logic

**Follow-up changes (outside the 4-change program):**
Factory parameters for fake injection (DI seams) — queued as separate testability improvement. No forcing function yet; defer until concrete testing need emerges.
Transformer/selector registry migration — valid extensibility polish, deferred.
ENSEMBLE_SCHEMA meta_learner.type enum expansion — config validation improvement, deferred.

## Skill Resolution

paths-injected — orchestrator forwarded `sdd-archive` + `_shared` skill paths directly.
