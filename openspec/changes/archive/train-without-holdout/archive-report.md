# Archive Report: train-without-holdout

**Change:** `train-without-holdout`
**Status:** ✅ Archived
**Archived at:** 2026-07-27
**Merged in:** PR #33 (commit `efdc22e` on `release/0.3.x`)

---

## Outcome

Production-ready feature shipped. Framework now supports training on the full dataset via `split.method: "none"`, enabling production model training after offline evaluation is complete.

## Cycle summary

| Phase | Artifact | Notes |
|-------|----------|-------|
| Explore | `exploration.md` | Problem framing: framework forced a val split; production needs full data |
| Propose | `proposal.md` | Business problem, target users, product outcome, non-goals |
| Spec | `specs/no-holdout-training/spec.md` | 7 functional requirements (FR1–FR7), 5 acceptance scenarios |
| Design | `design.md` | 8 resolved design questions (DQ-1 through DQ-8), 14 guards (G1–G14), risk register |
| Tasks | `tasks.md` | 8 batches: A (schema), B (split), C1/C2/C3 (training), D (ensemble), E (director), F (evaluator) |
| Apply | commit `96d352c` | Single commit collapsed from 8 batches because `training.py` is modified by 4 of them and hunks are not cleanly separable |
| Verify | `pytest -m "not slow" --strict-markers` | 1906/1906 pass |
| Review | `review-9e788e3df1e100ef` | 4 lenses (risk, resilience, readability, reliability) — all clean |
| Merge | PR #33 | Merged to `release/0.3.x` via regular merge |

## Test results

- **17 new tests** added across 6 test files
- **2 pre-existing tests** updated to new contracts:
  - `test_required_keys_when_paths_not_provided` — `val_path` no longer required
  - `test_stacking_requires_val_when_blending` — `ValueError` → `ConfigurationError` (per Batch D)
- **Full regression:** 1906 passed, 0 failed

## Review summary

All four 4R lenses returned clean (`findings: []`):

| Lens | Result | Evidence highlights |
|------|--------|---------------------|
| `review-risk` | ✅ clean | Additive change; no new permissions/deps/data exposure; `ConfigurationError` is public type |
| `review-resilience` | ✅ clean | Evaluator returns `skipped=True` defensively; director logs WARNING; fail-fast raises `ConfigurationError` |
| `review-readability` | ✅ clean | Phase D if/else clear; actionable error messages; `holdout_mode` self-documenting |
| `review-reliability` | ✅ clean | Backward-compat: existing split methods byte-identical; no-holdout path returns honest `None` metrics |

## Scope change

The merged commit included 2 paths outside the review receipt (`tests/test_ensemble_model.py` test contract fix and `CHANGELOG.md` entry). Maintainer explicitly authorized the scope change at the pre-push gate. Documented in the PR description.

## Files in this archive

```
openspec/changes/archive/train-without-holdout/
├── archive-report.md         (this file)
├── exploration.md            (problem framing)
├── proposal.md               (business problem, target users, outcome)
├── design.md                 (architecture, resolved questions, risks)
├── tasks.md                  (8-batch implementation plan)
└── specs/
    └── no-holdout-training/
        └── spec.md           (technical specification)
```

## Backward compatibility

Every existing `split.method` (`stratified`, `random`, `time_series`, `group_based`, `stratified_time`) is **byte-identical** to before. No public API removals. The new `"none"` enum value is purely additive.

## Future work (out of scope, not blocking)

- `CONTEXT.md` glossary update: add `holdout_mode`, "no-holdout training", "internal split" terms. Tracked in `tasks.md` §5 as a docs follow-up.
- `sdd-status` tooling concern: `tasks.md` uses prose section headers rather than markdown checkboxes (`- [ ]`). The native SDD dispatcher prefers checkbox syntax for progress tracking. This is a tooling/UX nit, not a substantive issue. Can be addressed when `tasks.md` is next revised.
